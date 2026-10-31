"""Independent saved-artifact audit, using frozen strategy costs as reference."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'data/results/usage_candidate_study_20261031_01'
OUT = ROOT / 'data/results/usage_zstd_misses_20261031_01'
ALGS = ('gzip', 'bz2', 'lzma', 'zstd')
MODELS = ('decision_tree', 'random_forest')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(name):
    with name.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = OUT / 'verification.json'
    require(not target.exists(), 'Refuse to overwrite verification')
    audit = json.loads((OUT / 'audit.json').read_bytes())
    for path, digest in {**audit['protected_input_sha256'], **audit['output_sha256']}.items():
        require(sha(ROOT / path) == digest, f'Changed evidence: {path}')
    analyzer = ROOT / 'research_log/analyze_zstd_misses_20261031.py'
    require(sha(analyzer) == audit['analyzer_sha256'], 'Changed analyzer')
    original = read(STUDY / 'evaluation/strategy_choices.csv')
    fixed = {(r['sample_id'], r['scenario_id'], r['strategy']): float(r['policy_cost']) for r in original if r['strategy'] in ALGS}
    candidates = [r for r in original if r['strategy'] in MODELS]
    expected_cases, expected_pairs, expected_ties = set(), set(), set()
    for r in candidates:
        s, sid, model = r['sample_id'], r['scenario_id'], r['strategy']
        if r['chosen_algorithm'] != 'zstd':
            continue
        zstd = fixed[(s, sid, 'zstd')]
        for alg in ALGS:
            if fixed[(s, sid, alg)] < zstd:
                expected_cases.add((s, sid, model))
                expected_pairs.add((s, sid, model, alg))
            elif alg != 'zstd' and fixed[(s, sid, alg)] == zstd:
                expected_ties.add((s, sid, model, alg))
    cases = read(OUT / 'missed_cases.csv')
    actual_cases = {(r['sample_id'], r['scenario_id'], r['model']) for r in cases}
    require(actual_cases == expected_cases and len(cases) == len(expected_cases), 'Incomplete/duplicate case enumeration')
    pairs = read(OUT / 'better_alternatives.csv')
    actual_pairs = {(r['sample_id'], r['scenario_id'], r['model'], r['alternative']) for r in pairs}
    require(actual_pairs == expected_pairs and len(pairs) == len(expected_pairs), 'Incomplete/duplicate alternative enumeration')
    ties = read(OUT / 'ties.csv')
    actual_ties = {(r['sample_id'], r['scenario_id'], r['model'], a) for r in ties for a in r['equal_to_zstd'].split(';')}
    require(actual_ties == expected_ties, 'Tie enumeration')
    metadata = {r['sample_id']: r for r in json.loads((STUDY / 'corpus/manifest.json').read_bytes())['candidates'] if r['selection_status'] == 'selected'}
    raw = {(r['sample_id'], r['algorithm']): r for r in read(STUDY / 'benchmark/compression_results.csv')}
    for r in cases:
        s, sid = r['sample_id'], r['scenario_id']
        costs = {a: fixed[(s, sid, a)] for a in ALGS}
        best = min(ALGS, key=costs.__getitem__)
        require(r['best_algorithm'] == best and r['better_algorithms'].split(';') == [a for a in ALGS if costs[a] < costs['zstd']], 'Wrong alternatives')
        require(float(r['regret']) == costs['zstd'] - costs[best], 'Wrong regret')
        require(float(r['saving_pct']) == 100 * (costs['zstd'] - costs[best]) / costs['zstd'], 'Wrong saving')
        for a in ALGS:
            require(float(r[a + '_cost']) == costs[a], 'Wrong saved cost')
            for field in ('compressed_size', 'compression_time_ms', 'decompression_time_ms'):
                require(r[a + '_' + field] == raw[(s, a)][field], 'Wrong measurement join')
        for field in ('candidate_id', 'input_sha256', 'relative_path', 'source_locator', 'format', 'origin_group_id'):
            require(r[field] == metadata[s][field], 'Wrong source join')
    for r in pairs:
        s, sid, a = r['sample_id'], r['scenario_id'], r['alternative']
        require(float(r['alternative_cost']) == fixed[(s, sid, a)] and float(r['zstd_cost']) == fixed[(s, sid, 'zstd')], 'Pair cost')
        require(float(r['saving']) == fixed[(s, sid, 'zstd')] - fixed[(s, sid, a)], 'Pair saving')
        require(math.isclose(math.fsum(float(r[k + '_saving']) for k in ('storage', 'compression', 'restoration')), float(r['saving']), rel_tol=1e-12, abs_tol=1e-12), 'Component saving sum')
    files = read(OUT / 'unique_files.csv')
    require({r['sample_id'] for r in files} == {s for s, sid, m in expected_cases} and len(files) == len({s for s, sid, m in expected_cases}), 'Unique file coverage')
    counts = Counter(r['sample_id'] for r in cases)
    require(all(int(r['missed_cases']) == counts[r['sample_id']] for r in files), 'File case counts')
    summaries = read(OUT / 'scenario_model_summary.csv')
    require(len(summaries) == 18 and len({(r['scenario_id'], r['model']) for r in summaries}) == 18, 'Summary coverage')
    for r in summaries:
        bucket = [x for x in candidates if (x['scenario_id'], x['strategy']) == (r['scenario_id'], r['model'])]
        missed = [x for x in cases if (x['scenario_id'], x['model']) == (r['scenario_id'], r['model'])]
        require(int(r['total_files']) == len(bucket) == 60, 'Summary denominator')
        require(int(r['zstd_choices']) == sum(x['chosen_algorithm'] == 'zstd' for x in bucket), 'Summary zstd count')
        require(int(r['missed_cases']) == len(missed), 'Summary misses')
        require(float(r['missed_regret_sum']) == math.fsum(float(x['regret']) for x in missed), 'Summary regret')
        require(int(r['non_zstd_strictly_worse_than_zstd']) == sum(x['chosen_algorithm'] != 'zstd' and float(x['policy_cost']) > float(x['zstd_cost']) for x in bucket), 'Reverse errors')
    report = (ROOT / 'research_log/zstd_misses_20261031.md').read_text(encoding='utf-8')
    for r in cases:
        require(f"| {r['scenario_id']} | {r['model']} | {r['candidate_id']} | {r['best_algorithm']} | {r['better_algorithms']} | {float(r['saving_pct']):.4f}% |" in report, 'Report omitted a case')
    coverage = audit['coverage']
    require(coverage['missed_cases'] == len(cases) and coverage['better_alternative_pairs'] == len(pairs), 'Audit counts')
    value = dict(status='independently_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
                 verifier_sha256=sha(Path(__file__)), audit_sha256=sha(OUT / 'audit.json'),
                 test_source_sha256=sha(ROOT / 'tests/test_zstd_misses.py'), coverage=coverage,
                 zstd_miss_rate_pct=100*len(cases)/coverage['zstd_choices'],
                 reverse_error_cases=sum(int(r['non_zstd_strictly_worse_than_zstd']) for r in summaries),
                 checks=['Frozen strategy cost enumeration independent of analyzer/scorer', 'Exact all cases/all alternatives/ties sets',
                         'Every measurement and source join', 'Per-file and per-condition counts/regret/reverse errors',
                         'Every missed case present in report', 'Input and saved output hashes'],
                 implementation_note='Initial analysis guard required compression-only consistency on decompression slots and halted before output. Corrected to phase-specific status/hash checks; dedicated fixture added. No original study failure or new measurement.',
                 verified_output_sha256=audit['output_sha256'])
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: value[k] for k in ('status', 'zstd_miss_rate_pct', 'reverse_error_cases')}))


if __name__ == '__main__':
    main()
