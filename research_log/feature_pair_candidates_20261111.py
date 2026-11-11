"""Isolated exact-feature candidates and pair kernel; not an adoption path."""
import time
import numpy as np
from research_log import feature_profile_runtime_20261111 as r

VARIANTS = ('reference', 'bigram_numpy', 'run_numpy', 'both_numpy')


def build(variant):
    r.require(variant in VARIANTS, 'Unknown candidate')
    module = r.load_reference()
    original_bigram, original_run = module._bigram_diversity, module._run_statistics

    def bigram(data):
        if type(data) is not bytes or len(data) < 2:
            return original_bigram(data)
        a = np.frombuffer(data, dtype=np.uint8)
        codes = (a[:-1].astype(np.uint16) << np.uint16(8)) | a[1:].astype(np.uint16)
        unique = int(np.count_nonzero(np.bincount(codes, minlength=65536)))
        return unique / min(len(data)-1, 65536)

    def runs(data):
        if type(data) is not bytes or len(data) < 2:
            return original_run(data)
        a = np.frombuffer(data, dtype=np.uint8)
        changes = np.flatnonzero(a[1:] != a[:-1]) + 1
        count = int(changes.size)+1
        boundaries = np.concatenate((np.array([0], dtype=np.intp), changes,
                                     np.array([len(data)], dtype=np.intp)))
        longest = int(np.max(np.diff(boundaries)))
        return (len(data)-count)/(len(data)-1), len(data)/count, longest

    if variant in ('bigram_numpy', 'both_numpy'):
        module._bigram_diversity = bigram
    if variant in ('run_numpy', 'both_numpy'):
        module._run_statistics = runs
    return module


def execute_pairs(schedule, inputs, expected, contract, frame_factory, stream, *, data_kind,
                  clock=time.perf_counter_ns):
    """Caller supplies validated inputs/schedule; flush failures and never retry."""
    modules = {v: build(v) for v in VARIANTS}
    for pair in schedule:
        candidate, sample, mode = pair['comparison'], pair['sample_id'], pair['mode']
        r.require(candidate in VARIANTS[1:] and mode in ('extract_only', 'extract_and_frame'), 'Invalid pair')
        r.require({pair['first'], pair['second']} == {'reference', candidate}, 'Pair order invalid')
        for position in ('first', 'second'):
            variant = pair[position]
            row = dict(pair, position=position, variant=variant, data_kind=data_kind,
                       input_sha256=r.digest(inputs[sample]), status='error')
            try:
                started = clock()
                value = modules[variant].extract_features(inputs[sample])
                frame = frame_factory(value) if mode == 'extract_and_frame' else None
                ended = clock()
                r.require(ended > started, 'Nonpositive timer')
                row.update(start_ns=started, end_ns=ended, elapsed_ns=ended-started,
                           features=r.assert_features(value, expected[sample], contract),
                           frame=r.frame_values(frame, value, contract) if frame is not None else None, status='ok')
            except BaseException as exc:
                row.update(error_type=type(exc).__name__, error=str(exc))
                r.emit(stream, row)
                raise
            r.emit(stream, row)


def verify_pairs(schedule, rows, expected, inventory, *, data_kind):
    """Saved-record audit independent of timing execution; no candidate calls."""
    r.require(len(rows) == 2*len(schedule), 'Incomplete or extra pair calls')
    deltas = []
    for index, pair in enumerate(schedule):
        calls = rows[2*index:2*index+2]
        for position, row in zip(('first', 'second'), calls, strict=True):
            r.require(all(row[k] == v for k, v in pair.items()), 'Pair schedule differs')
            r.require(row['position'] == position and row['variant'] == pair[position], 'Call order differs')
            r.require(row['status'] == 'ok' and row['data_kind'] == data_kind, 'Failed/wrong-scope call')
            r.require(row['input_sha256'] == inventory[pair['sample_id']]['input_sha256'], 'Input hash differs')
            r.require(row['features'] == expected[pair['sample_id']], 'Exact output differs')
            r.require(all(type(row[k]) is int for k in ('start_ns', 'end_ns', 'elapsed_ns')), 'Timer type differs')
            r.require(row['end_ns']-row['start_ns'] == row['elapsed_ns'] > 0, 'Timer differs')
            wanted = [float(int(v) if kind == 'int' else float.fromhex(v)).hex()
                      for _, kind, v in expected[pair['sample_id']]] if pair['mode'] == 'extract_and_frame' else None
            r.require(row['frame'] == wanted, 'Frame differs')
        r.require(calls[0]['end_ns'] <= calls[1]['start_ns'], 'Pair calls overlap')
        by_variant = {row['variant']: row for row in calls}
        deltas.append(dict(pair, delta_ns=by_variant[pair['comparison']]['elapsed_ns']-by_variant['reference']['elapsed_ns']))
    return deltas
