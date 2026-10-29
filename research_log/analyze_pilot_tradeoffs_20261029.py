"""Read-only, standard-library reanalysis; no codec/model execution or label edits."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.scoring import ALGORITHMS, MODE_WEIGHTS, score_sample

PLAN = ROOT / 'research_log/pilot_tradeoff_plan_20261029.json'
METRICS = ('compression_ratio', 'compression_time_ms', 'decompression_time_ms')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        check(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Duplicate CSV columns')
        rows = list(reader)
        check(all(None not in r and None not in r.values() for r in rows), 'Malformed CSV row')
        return rows


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def write_csv(path, rows):
    check(bool(rows), 'Empty output table')
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0, 'min': None, 'median': None, 'p90': None, 'max': None, 'mean': None}
    # Linear-interpolated empirical 90th percentile, including a singleton case.
    position = (len(values) - 1) * .9
    lo, hi = math.floor(position), math.ceil(position)
    p90 = values[lo] + (values[hi] - values[lo]) * (position - lo)
    return {'count': len(values), 'min': values[0], 'median': statistics.median(values),
            'p90': p90, 'max': values[-1], 'mean': statistics.fmean(values)}


def losses(rows):
    minima = [min(float(rows[a][m]) for a in ALGORITHMS) for m in METRICS]
    return {a: tuple(math.log(float(rows[a][m]) / minima[i]) for i, m in enumerate(METRICS))
            for a in ALGORITHMS}


def select(loss, weights):
    # Same operation order and exact tie rule as the production three-term score.
    scores = {a: weights[0]*loss[a][0] + weights[1]*loss[a][1] + weights[2]*loss[a][2]
              for a in ALGORITHMS}
    return min(ALGORITHMS, key=scores.__getitem__), scores


def pareto(rows):
    values = {a: tuple(float(rows[a][m]) for m in METRICS) for a in ALGORITHMS}
    dominators = {a: [b for b in ALGORITHMS if b != a
                      and all(x <= y for x, y in zip(values[b], values[a]))
                      and any(x < y for x, y in zip(values[b], values[a]))] for a in ALGORITHMS}
    return [a for a in ALGORITHMS if not dominators[a]], dominators


def load_inputs(source, config):
    samples = read_csv(source/'samples.csv')
    results = read_csv(source/'compression_results.csv')
    labels = read_csv(source/'selection_labels.csv')
    metadata = json.loads((source/'experiment_metadata.json').read_bytes())
    for name in ('samples.csv', 'compression_results.csv'):
        check(sha(source/name) == metadata['output_files'][name]['sha256'], 'Historical input hash mismatch: '+name)
    for old, new in (('compression_settings', 'compression'), ('timing', 'timing'), ('feature_settings', 'features')):
        check(metadata[old] == config[new], 'Config differs from historical measurement: '+old)
    check(metadata['verification_failure_count'] == 0 and metadata['verification_failures'] == [], 'Historical failures')
    check(config['selection_modes'] == MODE_WEIGHTS, 'Loaded scoring config differs')
    sample_map = {r['sample_id']: r for r in samples}
    check(len(sample_map) == len(samples) == metadata['sample_count'], 'Sample count/IDs mismatch')
    grouped = defaultdict(dict)
    for row in results:
        sid, a = row['sample_id'], row['algorithm']
        check(sid in sample_map and a in ALGORITHMS and a not in grouped[sid], 'Unknown/duplicate measurement')
        check(row['verified'] == 'True' and row.get('status', 'ok') == 'ok', 'Unverified/failed measurement')
        for m in METRICS:
            value = float(row[m])
            check(math.isfinite(value) and value > 0, 'Invalid metric: '+m)
        size, compressed = int(row['original_size']), int(row['compressed_size'])
        check(size == int(sample_map[sid]['size']) == int(sample_map[sid]['file_size']) and size > 0 and compressed > 0,
              'Size mismatch')
        check(math.isclose(float(row['compression_ratio']), compressed/size, rel_tol=1e-12), 'Ratio mismatch')
        grouped[sid][a] = row
    check(len(results) == metadata['compression_result_count'] == len(samples)*len(ALGORITHMS), 'Result count mismatch')
    check(set(grouped) == set(sample_map) and all(set(r) == set(ALGORITHMS) for r in grouped.values()), 'Incomplete algorithm coverage')
    label_map = {(r['sample_id'], r['mode']): r for r in labels}
    check(len(labels) == len(label_map) == len(samples)*len(MODE_WEIGHTS), 'Duplicate/missing labels')
    for sid, rows in grouped.items():
        for mode, selection in score_sample(rows.values()).items():
            label = label_map[(sid, mode)]
            check(selection.best_algorithm == label['best_algorithm'], 'Label differs: '+sid+'/'+mode)
            for a, value in selection.scores.items():
                check(math.isclose(float(label['score_'+a]), value, rel_tol=1e-12, abs_tol=1e-15), 'Score differs')
            check(math.isclose(float(label['best_score']), selection.scores[selection.best_algorithm], rel_tol=1e-12, abs_tol=1e-15), 'Best score differs')
    return sample_map, dict(grouped), label_map, metadata


def sensitivity_row(all_losses, weights, kind):
    counts, ties, strict, robust, gains = Counter(), 0, 0, 0, []
    for loss in all_losses.values():
        winner, scores = select(loss, weights)
        counts[winner] += 1
        gain = scores['zstd'] - scores[winner]
        gains.append(gain)
        strict += gain > 0
        robust += gain > 1e-12
        ties += winner != 'zstd' and gain == 0
    n = len(all_losses)
    return {'kind': kind, 'w_size': weights[0], 'w_compress': weights[1], 'w_decompress': weights[2],
            'zero_weight_edge': any(w == 0 for w in weights), 'sample_count': n,
            **{a+'_selected': counts[a] for a in ALGORITHMS},
            'non_zstd_selected_pct': 100*(n-counts['zstd'])/n, 'strict_non_zstd_gain_count': strict,
            'strict_non_zstd_gain_pct': 100*strict/n, 'gain_over_1e_12_count': robust,
            'non_zstd_tie_only_count': ties, 'mean_zstd_regret': statistics.fmean(gains), 'max_zstd_regret': max(gains)}


def analyze(samples, grouped, labels):
    all_losses = {sid: losses(rows) for sid, rows in grouped.items()}
    pairs, per_sample, groups = [], [], defaultdict(list)
    fronts, z_dominates_all = Counter(), 0
    for sid in sorted(samples):
        sample, rows, loss = samples[sid], grouped[sid], all_losses[sid]
        front, dominators = pareto(rows)
        fronts.update(front)
        z_all = all(a == 'zstd' or 'zstd' in dominators[a] for a in ALGORITHMS)
        z_dominates_all += z_all
        record = {'sample_id': sid, 'generator': sample['generator'], 'size': int(sample['size']),
                  'seed': int(sample['seed']), 'entropy': float(sample['entropy']),
                  'pareto_front': '|'.join(front), 'zstd_dominates_all_others': z_all}
        for m in METRICS:
            best = min(float(rows[a][m]) for a in ALGORITHMS)
            record[m+'_minima'] = '|'.join(a for a in ALGORITHMS if float(rows[a][m]) == best)
            record[m+'_zstd_strictly_beaten'] = best < float(rows['zstd'][m])
        for mode, weights in MODE_WEIGHTS.items():
            winner, scores = select(loss, (weights['compression_ratio'], weights['compression_time'], weights['decompression_time']))
            check(winner == labels[(sid, mode)]['best_algorithm'], 'Independent official selection mismatch')
            record[mode+'_winner'] = winner
            record[mode+'_zstd_regret'] = scores['zstd'] - scores[winner]
            record[mode+'_size_saved_bytes'] = int(rows['zstd']['compressed_size']) - int(rows[winner]['compressed_size'])
            record[mode+'_compress_saved_ms'] = float(rows['zstd']['compression_time_ms']) - float(rows[winner]['compression_time_ms'])
            record[mode+'_decompress_saved_ms'] = float(rows['zstd']['decompression_time_ms']) - float(rows[winner]['decompression_time_ms'])
        per_sample.append(record)
        for kind, key in (('overall','all'), ('generator',sample['generator']), ('size',sample['size']),
                          ('generator_size',sample['generator']+'/'+sample['size'])):
            groups[(kind,key)].append(record)
        for a in ALGORITHMS:
            pair = {'sample_id': sid, 'algorithm': a, 'generator': sample['generator'], 'size': int(sample['size']),
                    'pareto_optimal': a in front, 'dominators': '|'.join(dominators[a]),
                    'size_saved_bytes_vs_zstd': int(rows['zstd']['compressed_size'])-int(rows[a]['compressed_size'])}
            for m in METRICS:
                ref, value = float(rows['zstd'][m]), float(rows[a][m])
                pair[m+'_saved_vs_zstd'] = ref-value
                pair[m+'_saving_pct_vs_zstd'] = 100*(ref-value)/ref
            pairs.append(pair)
    grouped_stats = []
    for (kind,key), records in sorted(groups.items()):
        result = {'group_kind':kind, 'group':key, 'sample_count':len(records)}
        for m in METRICS:
            result[m+'_zstd_strictly_beaten_count'] = sum(r[m+'_zstd_strictly_beaten'] for r in records)
        for mode in MODE_WEIGHTS:
            for a in ALGORITHMS:
                result[mode+'_'+a+'_selected'] = sum(r[mode+'_winner']==a for r in records)
            result[mode+'_mean_zstd_regret'] = statistics.fmean(r[mode+'_zstd_regret'] for r in records)
        grouped_stats.append(result)
    metric_summary = {}
    for m in METRICS:
        winners = Counter(r[m+'_minima'] for r in per_sample)
        benefits = [100*(float(rows['zstd'][m])-min(float(rows[a][m]) for a in ALGORITHMS))/float(rows['zstd'][m])
                    for rows in grouped.values()]
        metric_summary[m] = {'exact_minima_sets':dict(winners), 'zstd_strictly_beaten_count':sum(v>0 for v in benefits),
                             'best_saving_pct_all_samples':distribution(benefits),
                             'best_saving_pct_strict_improvements_only':distribution([v for v in benefits if v>0])}
    official = {}
    for mode in MODE_WEIGHTS:
        wins = Counter(r[mode+'_winner'] for r in per_sample)
        official[mode] = {'selected_counts':{a:wins[a] for a in ALGORITHMS},
                         'non_zstd_pct':100*(len(samples)-wins['zstd'])/len(samples),
                         'zstd_regret':distribution([r[mode+'_zstd_regret'] for r in per_sample]),
                         **{k:distribution([r[mode+'_'+k] for r in per_sample]) for k in
                            ('size_saved_bytes','compress_saved_ms','decompress_saved_ms')}}
    pair_summary = {}
    for a in ALGORITHMS:
        records = [r for r in pairs if r['algorithm']==a]
        pair_summary[a] = {}
        for m in METRICS:
            values = [r[m+'_saving_pct_vs_zstd'] for r in records]
            absolute = [r[m+'_saved_vs_zstd'] for r in records]
            pair_summary[a][m] = {'better':sum(v>0 for v in values),'equal':sum(v==0 for v in values),
                                  'worse':sum(v<0 for v in values),'saving_pct_all':distribution(values),
                                  'saving_pct_when_better':distribution([v for v in values if v>0]),
                                  'absolute_saving_when_better':distribution([v for v in absolute if v>0])}
        pair_summary[a]['bytes_saved_when_smaller'] = distribution([r['size_saved_bytes_vs_zstd'] for r in records if r['size_saved_bytes_vs_zstd']>0])
    grid = [sensitivity_row(all_losses,(i/20,j/20,(20-i-j)/20),'simplex_0.05')
            for i in range(21) for j in range(21-i)]
    path = [sensitivity_row(all_losses,(i/100,(1-i/100)/2,(1-i/100)/2),'equal_time_path_0.01')
            for i in range(101)]
    summary = {'sample_count':len(samples), 'metrics':metric_summary, 'pairwise_vs_zstd':pair_summary,
               'official':official, 'pareto':{'front_inclusion_counts':{a:fronts[a] for a in ALGORITHMS},
                                            'zstd_dominates_all_others_count':z_dominates_all},
               'simplex':{'grid_point_count':len(grid),
                          'positive_weight_point_count':sum(not r['zero_weight_edge'] for r in grid),
                          'points_with_strict_non_zstd_gain_at_least_10pct':sum(r['strict_non_zstd_gain_pct']>=10 for r in grid),
                          'positive_points_with_strict_non_zstd_gain_at_least_10pct':sum(not r['zero_weight_edge'] and r['strict_non_zstd_gain_pct']>=10 for r in grid)},
               'equal_time_path':{'grid_point_count':len(path),
                                  'size_weights_with_strict_gain_at_least_10pct':[r['w_size'] for r in path if r['strict_non_zstd_gain_pct']>=10]}}
    return summary, {'per_sample.csv':per_sample,'pairwise_vs_zstd.csv':pairs,'group_summary.csv':grouped_stats,
                     'weight_simplex.csv':grid,'equal_time_path.csv':path}


def main():
    plan = json.loads(PLAN.read_bytes())
    source, out = ROOT/plan['input_root'], ROOT/plan['output_root']
    check(not out.exists(), 'Existing output must not be overwritten')
    started = datetime.now(timezone.utc).isoformat()
    command = ['git','ls-files','-z','data/results/pilot_1008','models','config','src/scoring.py','research_protocol_v2.md']
    paths = subprocess.check_output(command,cwd=ROOT).decode().split('\0')
    protected = {p:sha(ROOT/p) for p in paths if p}
    code_paths = [PLAN, Path(__file__), ROOT/'src/scoring.py', ROOT/'tests/test_pilot_tradeoffs.py']
    code_hashes = {p.relative_to(ROOT).as_posix():sha(p) for p in code_paths}
    config = json.loads((ROOT/'config/experiment_config.json').read_bytes())
    samples, grouped, labels, metadata = load_inputs(source,config)
    summary, tables = analyze(samples,grouped,labels)
    check(all(sha(ROOT/p)==h for p,h in protected.items()), 'Protected inputs changed')
    check(all(sha(ROOT/p)==h for p,h in code_hashes.items()), 'Analysis source changed')
    out.mkdir(parents=True,exist_ok=False)
    try:
        for name, rows in tables.items():
            write_csv(out/name,rows)
        summary.update({'schema_version':1,'status':'exploratory_completed','plan':plan,
                        'started_at_utc':started,'completed_at_utc':datetime.now(timezone.utc).isoformat(),
                        'python':platform.python_version(),'platform':platform.platform(),
                        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                        'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                        'command':sys.argv,'historical_measurement_metadata':metadata,
                        'source_sha256':code_hashes,'protected_before_sha256':protected,
                        'protected_after_sha256':{p:sha(ROOT/p) for p in protected},
                        'output_sha256':{name:sha(out/name) for name in tables},
                        'memory_score_computed':False,'new_model_evaluation':False,
                        'limitations':['All historical Pilot samples including prior train/test used for descriptive exploration.',
                                       'No held-out or real-file generalization assessment; no weight recommendation or adoption.',
                                       'Stored medians only: original raw repeat timings and noise inference are unavailable here.',
                                       'Codec times exclude feature extraction, prediction, I/O and end-to-end costs.',
                                       'Zero-weight faces may select earlier tied algorithms without an improvement over zstd.',
                                       'Finite weight grids do not exhaust all continuous weight choices.']})
        check(summary['protected_after_sha256']==protected,'Protected files changed during publication')
        write_json(out/'summary.json',summary)
    except Exception as exc:
        write_json(out/'failure.json',{'error':repr(exc),'started_at_utc':started})
        raise
    print(json.dumps({'output':str(out),'sample_count':len(samples),'official':summary['official'],
                      'metrics':summary['metrics'],'simplex':summary['simplex'],
                      'equal_time_path':summary['equal_time_path']},ensure_ascii=False,allow_nan=False))


if __name__ == '__main__':
    main()
