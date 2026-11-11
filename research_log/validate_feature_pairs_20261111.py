"""Synthetic-only implementation validation and source lock."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r
from research_log import run_feature_pairs_20261111 as runner


def main():
    out = runner.LOCK.parent
    r.require(not out.exists(), 'Refuse to overwrite validation')
    frozen = json.loads((runner.FREEZE / 'freeze.json').read_bytes())
    protected = dict(frozen['protected_input_sha256'])
    protected.update({p.relative_to(ROOT).as_posix(): r.sha(p) for p in runner.FREEZE.iterdir() if p.is_file()})
    sources = {name: r.sha(ROOT / name) for name in ('research_log/feature_pair_candidates_20261111.py',
               'research_log/run_feature_pairs_20261111.py', 'research_log/validate_feature_pairs_20261111.py',
               'tests/test_feature_pair_candidates.py')}
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_feature_pair_candidates.py')
    with patch.object(r, 'read_corpus', side_effect=AssertionError('Real corpus forbidden')), patch.object(r.pickle, 'load', side_effect=AssertionError('Stored models forbidden')):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'tests.log').open('x', encoding='utf-8') as stream: stream.write(log.getvalue())
    r.require(result.wasSuccessful(), 'Synthetic validation failed; log retained')
    evidence = sys.modules['test_feature_pair_candidates'].EVIDENCE
    r.require(len(evidence) == 133, 'Missing fixture evidence')
    r.write_json(out / 'fixtures.json', dict(data_kind='test_fixture', cases=evidence))
    for name, digest in {**protected, **sources}.items(): r.require(r.sha(ROOT / name) == digest, 'Changed file: '+name)
    value = dict(status='synthetic_validation_passed', at_utc=r.now(),
                 git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 source_sha256=sources, protected_input_sha256=protected,
                 tests=dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                            valid_inputs=133, invalid_inputs=5, variants=3),
                 corpus_execution=False, stored_model_execution=False, real_paired_measurement=False,
                 artifact_sha256={p.name:r.sha(p) for p in out.iterdir() if p.is_file()})
    r.write_json(runner.LOCK, value)
    print(json.dumps(dict(status=value['status'], tests=value['tests'], protected_files=len(protected))))


if __name__ == '__main__': main()
