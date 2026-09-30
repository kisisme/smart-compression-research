"""Descriptive diagnostics from independently audited runtime-baseline evidence.

No measurement, codec execution, score update or scientific acceptance decision.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
from itertools import combinations
import json
from pathlib import Path
import statistics

from research_log import verify_memory_runtime_validation as verification


def _stats(values):
    return dict(values=values, median=statistics.median(values), min=min(values), max=max(values))


def _sign(value):
    return (value > 0) - (value < 0)


def _across(values, *, reference=0):
    signs = [_sign(value - reference) for value in values]
    return dict(run_ids=[1, 2, 3], run_values=values, min=min(values), max=max(values),
                sign_reference=reference, signs=signs, sign_consistent=len(set(signs)) == 1)


def _comparison(left, right):
    difference = statistics.median(left) - statistics.median(right)
    return dict(median_difference_bytes=difference, sign=_sign(difference), tied=difference == 0,
                left_range_bytes=[min(left), max(left)], right_range_bytes=[min(right), max(right)],
                ranges_overlap=max(min(left), min(right)) <= min(max(left), max(right)))


def _calculate(rows):
    """Internal calculation on audit-validated rows, ordered explicitly by round."""
    groups = defaultdict(dict)
    for row in rows:
        key = (int(row['run_id']), row['sample_id'], row['algorithm'], row['phase'], row['arm'])
        groups[key][int(row['round_index'])] = int(row['peak_process_working_set_bytes'])
    peaks, paired, arm_pairs, algorithm_pairs = [], [], [], []
    arrays = {key: [rounds[i] for i in range(1, 6)] for key, rounds in groups.items()}
    for key in sorted(arrays):
        run, sample, algorithm, phase, arm = key
        values = arrays[key]
        std = statistics.pstdev(values)
        peaks.append(dict(run_id=run, sample_id=sample, algorithm=algorithm, phase=phase, arm=arm,
                          round_indices=[1, 2, 3, 4, 5], unit='bytes', **_stats(values),
                          population_std=std, cv=std / statistics.mean(values)))
    blocks = sorted({key[:4] for key in arrays})
    for run, sample, algorithm, phase in blocks:
        identity = dict(run_id=run, sample_id=sample, algorithm=algorithm, phase=phase)
        arms = {arm: arrays[(run, sample, algorithm, phase, arm)] for arm in verification.ARMS}
        for name, values, unit in (
            ('D_input', [a - b for a, b in zip(arms['input_only'], arms['import_only'])], 'bytes'),
            ('D_codec', [a - b for a, b in zip(arms['codec'], arms['input_only'])], 'bytes'),
            ('R_input', [a / b for a, b in zip(arms['input_only'], arms['codec'])], 'ratio'),
        ):
            paired.append(dict(**identity, contrast=name, unit=unit, round_indices=[1, 2, 3, 4, 5],
                               **_stats(values)))
        for left, right in combinations(verification.ARMS, 2):
            arm_pairs.append(dict(**identity, left=left, right=right, **_comparison(arms[left], arms[right])))
    for run, sample, phase in sorted({(k[0], k[1], k[3]) for k in arrays}):
        for left, right in combinations(verification.ALGORITHMS, 2):
            algorithm_pairs.append(dict(run_id=run, sample_id=sample, phase=phase, left=left, right=right,
                                        **_comparison(arrays[(run, sample, left, phase, 'codec')],
                                                      arrays[(run, sample, right, phase, 'codec')])))

    def cross(records, keys, value_field, ratio=False):
        indexed = defaultdict(dict)
        for record in records:
            indexed[tuple(record[k] for k in keys)][record['run_id']] = record[value_field]
        return [dict(zip(keys, key), **_across([by_run[i] for i in (1, 2, 3)],
                    reference=1 if ratio and key[-1] == 'R_input' else 0))
                for key, by_run in sorted(indexed.items())]

    return dict(peak_by_run=peaks, paired_by_run=paired, arm_pairs_by_run=arm_pairs,
                algorithm_pairs_by_run=algorithm_pairs,
                peak_across_runs=cross(peaks, ('sample_id', 'algorithm', 'phase', 'arm'), 'median'),
                paired_across_runs=cross(paired, ('sample_id', 'algorithm', 'phase', 'contrast'), 'median', True),
                arm_pairs_across_runs=cross(arm_pairs, ('sample_id', 'algorithm', 'phase', 'left', 'right'),
                                           'median_difference_bytes'),
                algorithm_pairs_across_runs=cross(algorithm_pairs, ('sample_id', 'phase', 'left', 'right'),
                                                 'median_difference_bytes'))


def analyze(directory: Path) -> dict:
    directory = directory.resolve()
    script = Path(__file__).resolve()
    source_paths = [script, Path(verification.__file__).resolve(),
                    *(verification.ROOT / name for name in verification.SOURCES)]
    source_bytes = {path: path.read_bytes() for path in source_paths}
    audited = verification.audit(directory)
    snapshots = {}
    for name, expected_hash in audited['input_sha256'].items():
        data = (directory / name).read_bytes()
        verification.require(verification.digest(data) == expected_hash, f'Evidence changed after audit: {name}')
        snapshots[name] = data
    rows = []
    for run in (1, 2, 3):
        rows.extend(csv.DictReader(io.StringIO(snapshots[f'run_{run:02d}/repeats.csv'].decode('utf-8'), newline='')))
    diagnostics = _calculate(rows)
    for name, data in snapshots.items():
        verification.require((directory / name).read_bytes() == data, f'Evidence changed during analysis: {name}')
    for path, data in source_bytes.items():
        verification.require(path.read_bytes() == data, f'Source changed during analysis: {path}')
    return dict(schema_version=1, design_id=verification.DESIGN, attempt_id=audited['attempt_id'],
                analysis_status='completed_descriptive_diagnostics', measurement_status='validation_only',
                score_inclusion=False, analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
                analysis_script_sha256=verification.digest(source_bytes[script]), audit=audited,
                samples=list(csv.DictReader(io.StringIO(snapshots['samples.csv'].decode('utf-8'), newline=''))),
                conventions=dict(pair_difference='left median minus right median; unadjusted peaks',
                                 paired_difference='difference within the same run, round and block, then summarize',
                                 ratio='input_only / codec; sign across runs is relative to 1',
                                 overlap='closed observed min/max ranges; touching endpoints overlap',
                                 ties='exact equality; sign 0; never broken', cv='population std / mean'),
                limitations=['Descriptive diagnostics only; no scientific acceptance threshold or score activation.',
                             'Separate process peaks do not isolate pure runtime or codec allocations.',
                             'Observed range overlap is not a confidence interval or equivalence test.',
                             'Runs are reported separately, not pooled as independent samples.',
                             'Negative differences and ratios above one are preserved.',
                             'No memory measurement, compression or restoration was rerun.'], **diagnostics)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Optional new diagnostic JSON; never overwrite')
    args = parser.parse_args(arguments)
    try:
        report = analyze(args.experiment_dir)
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(serialized)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error) as exc:
        parser.exit(1, f'Diagnostics failed: {exc}\n')
    print(serialized)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
