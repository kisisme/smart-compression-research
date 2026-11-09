"""Independent saved trace audit, without importing the bottleneck analyzer."""
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'data/results/usage_candidate_study_20261031_01'
OUT = ROOT / 'data/results/usage_pipeline_bottlenecks_20261109_01'


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(a, b, label):
    require(math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-10), label)


def main():
    target = OUT / 'verification.json'
    require(not target.exists(), 'Refuse to overwrite verification')
    audit = json.loads((OUT / 'audit.json').read_bytes())
    for name, digest in {**audit['protected_input_sha256'], **audit['output_sha256']}.items():
        require(sha(ROOT / name) == digest, f'Changed input/output: {name}')
    require(sha(ROOT / 'research_log/analyze_pipeline_bottlenecks_20261109.py') == audit['analyzer_sha256'], 'Changed analyzer')
    for root in (STUDY, ROOT / 'data/results/usage_zstd_misses_20261031_01'):
        expected = {name for name in audit['protected_input_sha256'] if name.startswith(root.relative_to(ROOT).as_posix() + '/')}
        require(expected == {p.relative_to(ROOT).as_posix() for p in root.rglob('*') if p.is_file()}, 'Input file set changed')
    groups = defaultdict(list)
    for r in read(STUDY / 'pipeline/raw_trials.csv'):
        groups[(r['sample_id'], r['strategy'])].append(r)
    def median(rows, *remove):
        return sorted(int(r['compression_ns']) - sum(int(r[k]) for k in remove) for r in rows)[2] / 1e6
    def timer(rows, key):
        return sorted(int(r[key]) for r in rows)[2] / 1e6
    for rows in groups.values():
        require(len(rows) == 5 and sorted(int(r['repeat_index']) for r in rows) == [1, 2, 3, 4, 5], 'Raw coverage')
    policy = {s['id']: {k: float(v) for k, v in s['policy'].items()} for s in json.loads((ROOT / 'research_log/usage_scenarios_frozen_20261031.json').read_bytes())['expanded_cost_scenarios']}
    codec = {(r['sample_id'], r['algorithm']): r for r in read(STUDY / 'benchmark/compression_results.csv')}
    metadata = {r['sample_id']: r for r in json.loads((STUDY / 'corpus/manifest.json').read_bytes())['candidates'] if r['selection_status'] == 'selected'}
    original = {(r['scenario_id'], r['model']): r for r in read(STUDY / 'evaluation/pipeline_metrics.csv')}
    files = read(OUT / 'file_decomposition.csv')
    require(len(files) == len({(r['sample_id'], r['scenario_id'], r['model']) for r in files}) == 1080, 'Saved file keys')
    for r in files:
        s, sid, model = r['sample_id'], r['scenario_id'], r['model']
        source, base = groups[(s, sid+'__'+model)], groups[(s, 'fixed_zstd')]
        p = policy[sid]
        ks, kc, kd = p['storage_cost_per_byte_day']*p['retention_days'], p['compression_cost_per_ms'], p['decompression_cost_per_ms']*p['expected_restorations']
        def objective(size, comp, restore):
            return math.fsum([ks*size, kc*comp, kd*restore])
        def codec_cost(v):
            return objective(int(v['compressed_size']), float(v['compression_time_ms']), float(v['decompression_time_ms']))
        def trace_cost(rows, *remove):
            return objective(int(rows[0]['package_bytes']), median(rows, *remove), timer(rows, 'restoration_ns'))
        observed, baseline = trace_cost(source), trace_cost(base)
        check(r['pipeline_cost'], observed, 'Observed cost')
        check(r['baseline_pipeline_cost'], baseline, 'Baseline cost')
        check(r['pipeline_cost_delta'], observed-baseline, 'File delta')
        selected, zstd = codec[(s, source[0]['algorithm'])], codec[(s, 'zstd')]
        f, pred = timer(source, 'feature_ns'), timer(source, 'prediction_ns')
        rest = median(source, 'feature_ns', 'prediction_ns')
        parts = dict(codec_selection_delta=codec_cost(selected)-codec_cost(zstd),
                     package_metadata_delta=ks*((int(source[0]['package_bytes'])-int(selected['compressed_size']))-(int(base[0]['package_bytes'])-int(zstd['compressed_size']))),
                     feature_cost=kc*f, prediction_cost=kc*pred,
                     compression_remainder_delta=kc*(rest-float(selected['compression_time_ms'])-median(base)+float(zstd['compression_time_ms'])),
                     median_alignment_delta=kc*(median(source)-f-pred-rest),
                     restoration_remainder_delta=kd*(timer(source, 'restoration_ns')-float(selected['decompression_time_ms'])-timer(base, 'restoration_ns')+float(zstd['decompression_time_ms'])))
        for field, value in parts.items():
            check(r[field], value, field)
        check(math.fsum(parts.values()), observed-baseline, 'Independent decomposition sum')
        for field, value in (('compression_ms', median(source)), ('restoration_ms', timer(source, 'restoration_ns')),
                             ('feature_ms', f), ('prediction_ms', pred), ('compression_remainder_ms', rest)):
            check(r[field], value, 'Saved median '+field)
        for name, removed in (('feature', ('feature_ns',)), ('prediction', ('prediction_ns',)), ('both', ('feature_ns', 'prediction_ns'))):
            check(r['without_'+name+'_cost'], trace_cost(source, *removed), 'Trial-wise hypothetical '+name)
        require(r['algorithm'] == source[0]['algorithm'] and int(r['package_bytes']) == int(source[0]['package_bytes']), 'Payload join')
        require(r['candidate_id'] == metadata[s]['candidate_id'] and r['origin_group_id'] == metadata[s]['origin_group_id'], 'Metadata join')
        check(r['codec_zstd_cost'], codec_cost(zstd), 'Codec baseline')
        check(r['codec_oracle_gain'], codec_cost(zstd)-min(codec_cost(codec[(s, a)]) for a in ('gzip', 'bz2', 'lzma', 'zstd')), 'Oracle gain')
    def verify_summaries(table, fields):
        expected = defaultdict(list)
        for row in files:
            expected[tuple(row[k] for k in fields)].append(row)
        require(len(table) == len(expected) and {tuple(r[k] for k in fields) for r in table} == set(expected), 'Summary keys')
        for r in table:
            rows = expected[tuple(r[k] for k in fields)]
            base = math.fsum(float(x['baseline_pipeline_cost']) for x in rows)
            total = math.fsum(float(x['pipeline_cost']) for x in rows)
            require(int(r['file_count']) == len(rows), 'Summary denominator')
            check(r['fixed_zstd_pipeline_cost'], base, 'Aggregate baseline')
            check(r['model_pipeline_cost'], total, 'Aggregate observed')
            check(r['actual_saving_pct'], 100*(base-total)/base, 'Aggregate saving')
            for term in parts:
                check(r[term], math.fsum(float(x[term]) for x in rows), 'Aggregate '+term)
            for name in ('feature', 'prediction', 'both'):
                check(r['hypothetical_without_'+name+'_saving_pct'], 100*(base-math.fsum(float(x['without_'+name+'_cost']) for x in rows))/base, 'Aggregate hypothetical')
            for field in ('feature', 'prediction'):
                check(r['mean_'+field+'_ms'], math.fsum(float(x[field+'_ms']) for x in rows)/len(rows), 'Aggregate timer mean')
                check(r[field+'_share_of_compression_pct'], 100*math.fsum(float(x[field+'_ms']) for x in rows)/math.fsum(float(x['compression_ms']) for x in rows), 'Aggregate timer share')
    summary = read(OUT / 'summary.csv')
    verify_summaries(summary, ('scenario_id', 'model'))
    verify_summaries(read(OUT / 'size_summary.csv'), ('scenario_id', 'model', 'size_bin'))
    verify_summaries(read(OUT / 'origin_summary.csv'), ('scenario_id', 'model', 'origin_group_id'))
    for r in summary:
        old = original[(r['scenario_id'], r['model'])]
        check(r['actual_saving_pct'], old['warm_pipeline_cost_saving_pct'], 'Original warm metric')
        check(r['model_load_median_ms'], old['median_verified_model_load_ms'], 'Original load metric')
        codec_base = math.fsum(float(x['codec_zstd_cost']) for x in files if x['scenario_id'] == r['scenario_id'] and x['model'] == r['model'])
        check(r['codec_saving_pct'], -100*float(r['codec_selection_delta'])/codec_base, 'Codec saving budget')
    report = ROOT / 'research_log/pipeline_bottlenecks_20261109.md'
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', report.read_text(encoding='utf-8'))
    require(all((report.parent / link).resolve().is_file() for link in links), 'Broken report link')
    value = dict(status='independently_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
                 verifier_sha256=sha(Path(__file__)), test_source_sha256=sha(ROOT / 'tests/test_pipeline_bottlenecks.py'),
                 audit_sha256=sha(OUT / 'audit.json'), coverage=audit['coverage'], report_link_count=len(links),
                 protected_file_count=len(audit['protected_input_sha256']),
                 checks=['Independent sorted-middle raw medians', 'Per-trial hypothetical timer removal',
                         'All 1080 independent component identities', 'All scenario/size/origin aggregates',
                         'Original warm/load metrics', 'Prior evidence/output hashes and file sets', 'Report links'],
                 negative_without_feature=sum(float(r['hypothetical_without_feature_saving_pct']) < 0 for r in summary),
                 negative_without_both=sum(float(r['hypothetical_without_both_saving_pct']) < 0 for r in summary))
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: value[k] for k in ('status', 'coverage', 'protected_file_count', 'negative_without_feature', 'negative_without_both')}))


if __name__ == '__main__':
    main()
