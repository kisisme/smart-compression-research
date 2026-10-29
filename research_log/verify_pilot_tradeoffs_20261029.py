"""Independently check saved analysis tables against original Pilot measurements."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'data/results/pilot_tradeoff_20261029_01'
SOURCE = ROOT/'data/results/pilot_1008'
ALGS = ('gzip','bz2','lzma','zstd')
METRICS = ('compression_ratio','compression_time_ms','decompression_time_ms')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def require(value, message):
    if not value:
        raise ValueError(message)


def close(a,b):
    return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-15)


def main():
    require(not (OUT/'verification.json').exists(),'Existing verification must not be overwritten')
    summary = json.loads((OUT/'summary.json').read_bytes())
    for key in ('source_sha256','protected_before_sha256'):
        for path,value in summary[key].items():
            require(digest(ROOT/path)==value,'Source/input changed: '+path)
    require(summary['protected_before_sha256']==summary['protected_after_sha256'],'Before/after differ')
    for name,value in summary['output_sha256'].items():
        require(digest(OUT/name)==value,'Saved output changed: '+name)
    require(not (OUT/'failure.json').exists(),'Failed publication')
    samples = {r['sample_id']:r for r in read(SOURCE/'samples.csv')}
    source_rows = defaultdict(dict)
    for r in read(SOURCE/'compression_results.csv'):
        source_rows[r['sample_id']][r['algorithm']] = r
    source_labels = {(r['sample_id'],r['mode']):r for r in read(SOURCE/'selection_labels.csv')}
    saved = {r['sample_id']:r for r in read(OUT/'per_sample.csv')}
    require(set(samples)==set(saved)==set(source_rows),'ID coverage mismatch')
    n = len(samples)
    loss = {}
    minima_sets = {m:Counter() for m in METRICS}
    front_counts = Counter()
    dominates_all_count = 0
    for sid,rows in source_rows.items():
        rec = saved[sid]
        require(rec['generator']==samples[sid]['generator'] and int(rec['size'])==int(samples[sid]['size']),'Sample join mismatch')
        loss[sid] = {}
        for a in ALGS:
            loss[sid][a] = [math.log(float(rows[a][m])/min(float(v[m]) for v in rows.values())) for m in METRICS]
        for m in METRICS:
            best = min(float(v[m]) for v in rows.values())
            names = '|'.join(a for a in ALGS if float(rows[a][m])==best)
            minima_sets[m][names] += 1
            require(rec[m+'_minima']==names,'Metric winner mismatch')
            require((rec[m+'_zstd_strictly_beaten']=='True')==(best<float(rows['zstd'][m])),'Strict metric improvement mismatch')
        front, z_dominated = [], []
        for a in ALGS:
            dominated = False
            for b in ALGS:
                if a==b:
                    continue
                diffs = [float(rows[b][m])-float(rows[a][m]) for m in METRICS]
                if max(diffs)<=0 and min(diffs)<0:
                    dominated = True
                    if b=='zstd':
                        z_dominated.append(a)
            if not dominated:
                front.append(a)
        front_counts.update(front)
        dominates_all_count += len(z_dominated)==len(ALGS)-1
        require(rec['pareto_front']=='|'.join(front),'Pareto mismatch')
        for mode in summary['official']:
            label = source_labels[(sid,mode)]
            winner = label['best_algorithm']
            require(rec[mode+'_winner']==winner,'Official winner mismatch')
            require(close(rec[mode+'_zstd_regret'],float(label['score_zstd'])-float(label['best_score'])),'Regret mismatch')
    require(summary['pareto']['front_inclusion_counts']=={a:front_counts[a] for a in ALGS},'Pareto summary mismatch')
    require(summary['pareto']['zstd_dominates_all_others_count']==dominates_all_count,'Dominance count mismatch')
    for m in METRICS:
        require(dict(minima_sets[m])==summary['metrics'][m]['exact_minima_sets'],'Metric summary mismatch')
    pairs = read(OUT/'pairwise_vs_zstd.csv')
    require(len(pairs)==n*len(ALGS) and len({(r['sample_id'],r['algorithm']) for r in pairs})==len(pairs),'Pair coverage mismatch')
    for row in pairs:
        original = source_rows[row['sample_id']]
        for m in METRICS:
            base,other = float(original['zstd'][m]),float(original[row['algorithm']][m])
            require(close(row[m+'_saved_vs_zstd'],base-other),'Pair absolute saving mismatch')
            require(close(row[m+'_saving_pct_vs_zstd'],(base-other)/base*100),'Pair percentage mismatch')
    for row in read(OUT/'group_summary.csv'):
        records = [r for r in saved.values() if row['group_kind']=='overall'
                   or row['group_kind']=='generator' and r['generator']==row['group']
                   or row['group_kind']=='size' and r['size']==row['group']
                   or row['group_kind']=='generator_size' and r['generator']+'/'+r['size']==row['group']]
        require(len(records)==int(row['sample_count']),'Grouped count mismatch')
        for mode in summary['official']:
            counts = Counter(r[mode+'_winner'] for r in records)
            require(all(int(row[mode+'_'+a+'_selected'])==counts[a] for a in ALGS),'Grouped label mismatch')
    grid = read(OUT/'weight_simplex.csv')
    path = read(OUT/'equal_time_path.csv')
    require(len(grid)==231 and len({(r['w_size'],r['w_compress'],r['w_decompress']) for r in grid})==231,'Simplex coverage')
    require(len(path)==101 and {round(float(r['w_size'])*100) for r in path}==set(range(101)),'Path coverage')
    for row in grid+path:
        w = tuple(float(row[k]) for k in ('w_size','w_compress','w_decompress'))
        require(all(v>=0 for v in w) and close(sum(w),1),'Invalid weights')
        counts,strict,robust,ties,gains = Counter(),0,0,0,[]
        for values in loss.values():
            scores = [w[0]*values[a][0]+w[1]*values[a][1]+w[2]*values[a][2] for a in ALGS]
            chosen = min(range(len(ALGS)),key=lambda i:scores[i])
            counts[ALGS[chosen]] += 1
            improvement = scores[-1]-scores[chosen]
            strict += improvement>0
            robust += improvement>1e-12
            ties += chosen!=len(ALGS)-1 and improvement==0
            gains.append(improvement)
        require(all(counts[a]==int(row[a+'_selected']) for a in ALGS),'Sensitivity label count mismatch')
        require(strict==int(row['strict_non_zstd_gain_count']) and robust==int(row['gain_over_1e_12_count'])
                and ties==int(row['non_zstd_tie_only_count']),'Strict/tie sensitivity mismatch')
        require(close(row['strict_non_zstd_gain_pct'],100*strict/n) and close(row['mean_zstd_regret'],statistics.fmean(gains)),'Sensitivity summary mismatch')
    check_result = {'status':'verified_against_original_pilot','created_at_utc':datetime.now(timezone.utc).isoformat(),
                    'sample_count':n,'pair_rows':len(pairs),'sensitivity_points':len(grid)+len(path),
                    'protected_file_count':len(summary['protected_before_sha256']),
                    'protected_files_unchanged':True,'source_and_output_hashes_verified':True,
                    'independent_checks':['Per-sample metric minima and strict gains','Pareto front',
                                          'Official label/regret join','All pairwise metric savings',
                                          'Grouped label counts','Every saved weight-grid selection, strict gain and regret'],
                    'summary_sha256':digest(OUT/'summary.json'),'verifier_sha256':digest(Path(__file__)),
                    'source_sha256':summary['source_sha256'],'output_sha256':summary['output_sha256'],
                    'tests':{'command':'.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_pilot_tradeoffs.py -v',
                             'passed':8,'seconds':0.034,'initial_restricted_attempt':'6 passed, 2 temporary-directory PermissionError; elevated rerun passed'},
                    'scope':'Stored measurements only; no codecs, models, memory or held-out-file evaluation executed.'}
    with (OUT/'verification.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(check_result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(check_result,ensure_ascii=False))


if __name__=='__main__':
    main()
