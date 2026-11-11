"""Isolated reference execution and exact checks; no codec or training functions."""
from contextlib import nullcontext
from datetime import datetime, timezone
import csv
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import pickle
import platform
import random
import subprocess
import time
import traceback
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / 'data/results/feature_profile_plan_20261109_01'
IMPLEMENTATION = ROOT / 'data/results/feature_profile_implementation_20261111_01/implementation.json'
ALGORITHMS = ('gzip', 'bz2', 'lzma', 'zstd')
MODES = ('extract_only', 'frame_only', 'extract_and_frame', 'instrumented_extract')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'CSV columns')
        rows = list(reader)
        require(all(None not in r and None not in r.values() for r in rows), 'Malformed CSV')
        return rows


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def emit(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
    stream.flush()


def failure(path, exc, phase):
    write_json(path, dict(status='failed', at_utc=now(), phase=phase, error_type=type(exc).__name__,
                          error=str(exc), traceback=traceback.format_exc()))


def under(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    require(result.is_relative_to(root), 'Path escapes root')
    return result


def load_context():
    frozen = json.loads((FREEZE / 'freeze.json').read_bytes())
    verified = json.loads((FREEZE / 'verification.json').read_bytes())
    require(verified['status'] == 'plan_references_and_schedule_verified', 'Plan not verified')
    require(sha(FREEZE / 'freeze.json') == verified['freeze_sha256'], 'Plan audit changed')
    require(sha(ROOT / 'research_log/verify_feature_profile_plan_20261109.py') == verified['verifier_sha256'], 'Plan verifier changed')
    plan = json.loads((FREEZE / 'plan.json').read_bytes())
    require(sha(ROOT / 'research_log/feature_profile_plan_20261109.json') == frozen['plan_sha256'], 'Plan source changed')
    require(plan == json.loads((ROOT / 'research_log/feature_profile_plan_20261109.json').read_bytes()), 'Plan mismatch')
    for name, value in frozen['protected_input_sha256'].items():
        require(sha(under(ROOT, name)) == value, f'Protected input changed: {name}')
    for name, value in frozen['artifact_sha256'].items():
        require(sha(under(FREEZE, name)) == value, f'Frozen reference changed: {name}')
    require({p.relative_to(FREEZE).as_posix() for p in FREEZE.rglob('*') if p.is_file()} == set(frozen['artifact_sha256']) | {'freeze.json', 'verification.json'}, 'Frozen file set changed')
    study = under(ROOT, plan['source_study'])
    training = json.loads((study / 'training.json').read_bytes())
    require(platform.python_version() == training['python'], 'Python version mismatch')
    require({name: version(name) for name in training['packages']} == training['packages'], 'Package version mismatch')
    require(training['feature_names'] == plan['feature_contract']['names_in_order'], 'Feature contract mismatch')
    inventory = read_csv(FREEZE / 'input_inventory.csv')
    require(len(inventory) == len({r['sample_id'] for r in inventory}) == 60, 'Input coverage')
    expected = {r['sample_id']: [] for r in inventory}
    for r in read_csv(FREEZE / 'expected_features.csv'):
        require(r['sample_id'] in expected, 'Unexpected feature sample')
        expected[r['sample_id']].append([r['feature'], r['builtin_type'], r['canonical_value']])
    for value in expected.values():
        decode_features(value, plan['feature_contract'])
    schedule = read_csv(FREEZE / 'schedule.csv')
    require(tuple(plan['timing']['modes_in_order']) == MODES, 'Unexpected modes')
    validate_schedule(schedule, inventory, plan)
    return dict(plan=plan, frozen=frozen, study=study, training=training, inventory=inventory,
                expected=expected, schedule=schedule, contract=plan['feature_contract'])


def validate_schedule(rows, inventory, plan):
    require(len(rows) == len(inventory)*6*len(MODES), 'Schedule length')
    ordered = sorted(inventory, key=lambda r: (r['origin_group_id'], r['sample_id']))
    expected = []
    for i, mode in enumerate(MODES):
        for round_index in range(6):
            shuffled = list(ordered)
            random.Random(plan['timing']['schedule_seed']+1000*i+round_index).shuffle(shuffled)
            expected.extend(dict(mode=mode, round_index=str(round_index), is_warmup=str(round_index == 0),
                                 order_in_round=str(pos), sample_id=r['sample_id']) for pos, r in enumerate(shuffled, 1))
    require(rows == expected, 'Schedule slots/order changed')


def check_implementation():
    lock = json.loads(IMPLEMENTATION.read_bytes())
    require(lock['status'] == 'fixture_validated_before_corpus_execution', 'Implementation not validated')
    require(lock['tests']['successful'] is True and lock['tests']['tests_run'] > 0, 'Fixture validation failed')
    for name, value in lock['source_sha256'].items():
        require(sha(ROOT / name) == value, f'Implementation changed: {name}')
        committed = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
        require(digest(committed) == value, f'Implementation not committed: {name}')
    require(subprocess.check_output(['git', 'show', 'HEAD:' + IMPLEMENTATION.relative_to(ROOT).as_posix()], cwd=ROOT) == IMPLEMENTATION.read_bytes(), 'Implementation lock not committed')
    return lock


def load_reference():
    # exec avoids __pycache__ writes inside the immutable reference tree.
    path = FREEZE / 'reference/src/feature_extractor.py'
    module = ModuleType('frozen_feature_profile_reference')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def load_frame_factory(names):
    import numpy as np
    import pandas as pd
    path = FREEZE / 'reference/feature_frame.py'
    namespace = dict(np=np, pd=pd, FEATURE_NAMES=tuple(names), require=require)
    exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
    return namespace['feature_frame']


def canonical_features(features, contract):
    require(type(features) is dict and list(features) == contract['names_in_order'], 'Feature names/order differ')
    result = []
    for name, value in features.items():
        integer = name in contract['integer_features']
        require(type(value) is (int if integer else float), f'Feature type differs: {name}')
        require(math.isfinite(value), f'Nonfinite feature: {name}')
        result.append([name, 'int' if integer else 'float', str(value) if integer else value.hex()])
    return result


def decode_features(canonical, contract):
    require(len(canonical) == len(contract['names_in_order']), 'Feature count differs')
    decoded = {}
    for name, kind, value in canonical:
        require(kind in ('int', 'float'), 'Unknown feature type')
        decoded[name] = int(value) if kind == 'int' else float.fromhex(value)
    require(canonical_features(decoded, contract) == canonical, 'Invalid canonical features')
    return decoded


def assert_features(features, expected, contract):
    actual = canonical_features(features, contract)
    require(actual == expected, f'Feature value mismatch: actual={actual!r}, expected={expected!r}')
    return actual


def frame_values(frame, features, contract):
    require(frame.shape == (1, len(contract['names_in_order'])), 'Frame shape differs')
    require(frame.columns.tolist() == contract['names_in_order'], 'Frame order differs')
    require(all(str(dtype) == 'float64' for dtype in frame.dtypes), 'Frame dtype differs')
    require(frame.index.tolist() == [0], 'Frame index differs')
    actual = [float(v).hex() for v in frame.to_numpy()[0]]
    expected = [float(features[n]).hex() for n in contract['names_in_order']]
    require(actual == expected, 'Frame values differ')
    return actual


def read_corpus(ctx):
    root = Path(json.loads((FREEZE / 'input_root.json').read_bytes())['original_input_root'])
    inputs = {}
    for entry in ctx['inventory']:
        data = under(root, entry['relative_path']).read_bytes()
        require(len(data) == int(entry['original_size']) and digest(data) == entry['input_sha256'], 'Original bytes differ: ' + entry['sample_id'])
        inputs[entry['sample_id']] = data
    return inputs


def reference_gate(ctx, inputs, reference):
    require(set(inputs) == set(ctx['expected']), 'Input/expected coverage differs')
    features = {}
    for sample, data in inputs.items():
        value = reference.extract_features(data)
        assert_features(value, ctx['expected'][sample], ctx['contract'])
        features[sample] = value
    return features


class CallProfiler:
    """Process-local wrappers; elapsed children are disjoint direct children only."""
    def __init__(self, module, targets, clock=time.perf_counter_ns):
        self.module, self.targets, self.clock = module, tuple(targets), clock
        self.originals, self.stack, self.events = {}, [], []
        self.next_id = 0

    def reset(self):
        require(not self.stack, 'Unfinished call tree')
        self.events = []
        self.next_id = 0

    def wrap(self, name, original):
        def timed(*args, **kwargs):
            self.next_id += 1
            parent = self.stack[-1] if self.stack else None
            node = dict(call_id=self.next_id, parent_id=parent['call_id'] if parent else None,
                        function=name, parent_function=parent['function'] if parent else None,
                        depth=len(self.stack), children_ns=0, status='ok')
            self.stack.append(node)
            start = self.clock()
            try:
                return original(*args, **kwargs)
            except BaseException as exc:
                node.update(status='error', error_type=type(exc).__name__, error=str(exc))
                raise
            finally:
                end = self.clock()
                self.stack.pop()
                elapsed = end-start
                node.update(start_ns=start, end_ns=end, elapsed_ns=elapsed, self_ns=elapsed-node.pop('children_ns'))
                if parent is not None:
                    parent['children_ns'] += elapsed
                self.events.append(node)
                require(elapsed > 0 and node['self_ns'] >= 0, 'Invalid nested timing')
        return timed

    def __enter__(self):
        require(not self.originals, 'Profiler already installed')
        try:
            for name in self.targets:
                original = getattr(self.module, name)
                self.originals[name] = original
                setattr(self.module, name, self.wrap(name, original))
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *unused):
        for name, value in self.originals.items():
            setattr(self.module, name, value)
        self.originals.clear()


def run_mode(mode, schedule, inputs, expected, reference, frame_factory, out, contract, targets,
             *, data_kind, clock=time.perf_counter_ns):
    require(mode in MODES, 'Unknown mode')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'started.json', dict(mode=mode, data_kind=data_kind, started_at_utc=now(), pid=os.getpid()))
    profiler = CallProfiler(reference, targets, clock)
    slot = None
    try:
        features = {s: decode_features(value, contract) for s, value in expected.items()}
        hashes = {s: digest(data) for s, data in inputs.items()}
        with (out / 'trials.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
            with profiler if mode == 'instrumented_extract' else nullcontext():
                for slot in schedule:
                    require(slot['mode'] == mode, 'Mixed-mode schedule')
                    s = slot['sample_id']
                    profiler.reset()
                    row = dict(slot, data_kind=data_kind, input_sha256=hashes[s], status='error')
                    try:
                        start = clock()
                        if mode == 'frame_only':
                            value, frame = features[s], frame_factory(features[s])
                        elif mode == 'extract_and_frame':
                            value = reference.extract_features(inputs[s])
                            frame = frame_factory(value)
                        else:
                            value, frame = reference.extract_features(inputs[s]), None
                        end = clock()
                        require(end > start, 'Nonpositive mode duration')
                        row.update(start_ns=start, end_ns=end, elapsed_ns=end-start,
                                   features=assert_features(value, expected[s], contract),
                                   frame=frame_values(frame, value, contract) if frame is not None else None,
                                   calls=profiler.events, status='ok')
                    except BaseException as exc:
                        row.update(error_type=type(exc).__name__, error=str(exc), calls=profiler.events)
                        emit(stream, row)
                        raise
                    emit(stream, row)
        write_json(out / 'complete.json', dict(status='mode_completed', mode=mode, slots=len(schedule), data_kind=data_kind))
    except BaseException as exc:
        failure(out / 'failure.json', exc, dict(mode=mode, slot=slot))
        raise


def prediction_record(model, frame, expected, classes):
    require(model.classes_.tolist() == classes, 'Prediction class order differs')
    chosen = str(model.predict(frame)[0])
    values = model.predict_proba(frame)[0]
    require(len(values) == len(classes), 'Probability shape differs')
    probabilities = {str(a): float(v) for a, v in zip(classes, values, strict=True)}
    require(chosen in ALGORITHMS and set(probabilities) <= set(ALGORITHMS), 'Unknown predicted class')
    require(all(math.isfinite(v) and 0 <= v <= 1 for v in probabilities.values()), 'Invalid probabilities')
    actual = dict(predicted_algorithm=chosen, uncalibrated_confidence=max(probabilities.values()),
                  **{'probability_'+a: probabilities.get(a, 0.) for a in ALGORITHMS})
    require(chosen == expected['predicted_algorithm'], 'Frozen predicted algorithm differs')
    for k, v in actual.items():
        if k != 'predicted_algorithm':
            require(v.hex() == float(expected[k]).hex(), 'Frozen probability/confidence differs: '+k)
    return dict(predicted_algorithm=chosen, **{k: v.hex() for k, v in actual.items() if k != 'predicted_algorithm'})


def prediction_gate(ctx, features, frame_factory, out):
    import numpy as np
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    training = ctx['training']
    config = json.loads((FREEZE / 'reference/config/experiment_config.json').read_bytes())
    frozen = read_csv(FREEZE / 'expected_predictions.csv')
    expected = {(r['sample_id'], r['scenario_id'], r['model']): r for r in frozen}
    models = {}
    for item in training['models']:
        path = under(ctx['study'], item['file'])
        require(sha(path) == item['sha256'], 'Model bytes changed')
        with path.open('rb') as stream:
            model = pickle.load(stream)
        klass = DecisionTreeClassifier if item['kind'] == 'decision_tree' else RandomForestClassifier
        require(type(model) is klass and model.get_params() == item['parameters'], 'Model class/settings differ')
        require(all(model.get_params().get(k) == v for k, v in config[item['kind']].items()), 'Explicit model settings differ')
        require(model.feature_names_in_.tolist() == training['feature_names'] and model.classes_.tolist() == item['classes'], 'Model schema/classes differ')
        models[(item['scenario_id'], item['kind'])] = (model, item)
    require(len(expected) == len(frozen) == len(features)*len(models), 'Prediction gate coverage')
    count = 0
    with Path(out).open('x', encoding='utf-8', newline='\n') as stream:
        for key, r in expected.items():
            try:
                model, item = models[(r['scenario_id'], r['model'])]
                require(item['sha256'] == r['model_sha256'], 'Frozen model identity differs')
                frame = frame_factory(features[r['sample_id']])
                frame_values(frame, features[r['sample_id']], ctx['contract'])
                require(np.isfinite(frame.to_numpy()).all(), 'Nonfinite model input')
                value = prediction_record(model, frame, r, item['classes'])
                emit(stream, dict(sample_id=key[0], scenario_id=key[1], model=key[2], model_sha256=item['sha256'], status='ok', **value))
                count += 1
            except BaseException as exc:
                emit(stream, dict(sample_id=key[0], scenario_id=key[1], model=key[2], status='error', error_type=type(exc).__name__, error=str(exc)))
                raise
    return count


class BytesFixture(bytes):
    pass


def fixture_inputs(plan):
    spec = plan['fixture_plan']
    for length in spec['lengths']:
        for pattern in spec['patterns']:
            rng = random.Random(spec['seed'])
            if pattern == 'constant_00': data = bytes(length)
            elif pattern == 'constant_41': data = b'A'*length
            elif pattern == 'cycle_00_to_ff': data = (bytes(range(256))*((length+255)//256))[:length]
            elif pattern == 'alternating_00_ff': data = (b'\0\xff'*((length+1)//2))[:length]
            elif pattern == 'seeded_full_byte_random': data = rng.randbytes(length)
            elif pattern == 'seeded_four_byte_alphabet': data = bytes(rng.randrange(4) for _ in range(length))
            else: raise ValueError('Unknown fixture pattern')
            yield pattern+'_'+str(length), data
    extra = dict(run_crosses_boundaries=b'A'*4097+b'B'*16+b'A', partial_duplicate_block=b'A'*32+b'B'*16+b'A'*15,
                 all_ordered_byte_pairs=b''.join(bytes((a, b)) for a in range(256) for b in range(256)),
                 mixed_entropy_segments=bytes(4096)+bytes((0, 1))*2048+b'X', bytes_subclass=BytesFixture(b'ABCABC'))
    require(set(extra) == set(spec['extra_valid_cases']), 'Extra fixture definitions differ')
    yield from extra.items()
