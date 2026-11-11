"""Run synthetic tests with corpus/model execution disabled; freeze implementation."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r

SOURCES = ('research_log/feature_profile_runtime_20261111.py', 'research_log/run_feature_profile_20261111.py',
           'research_log/verify_feature_profile_run_20261111.py', 'tests/test_feature_profile.py',
           'research_log/validate_feature_profile_implementation_20261111.py', 'research_log/feature_profile_implementation_20261111.md')


def main():
    out = r.IMPLEMENTATION.parent
    r.require(not out.exists(), 'Refuse to overwrite implementation validation')
    ctx = r.load_context()  # Hashes and runtime only; does not read original inputs or deserialize models.
    protected = dict(ctx['frozen']['protected_input_sha256'])
    protected.update({p.relative_to(ROOT).as_posix(): r.sha(p) for p in r.FREEZE.rglob('*') if p.is_file()})
    source_hashes = {name: r.sha(ROOT / name) for name in SOURCES}
    r.require(not (ROOT / ctx['plan']['future_profile_root']).exists(), 'Corpus profile already exists')
    out.mkdir(parents=True, exist_ok=False)
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_feature_profile.py')
    try:
        with (
            patch.object(r, 'read_corpus', side_effect=AssertionError('Real corpus reads forbidden during fixture validation')) as corpus,
            patch.object(r, 'prediction_gate', side_effect=AssertionError('Stored model execution forbidden during fixture validation')) as models,
            patch.object(r.pickle, 'load', side_effect=AssertionError('Pickle loading forbidden during fixture validation')),
        ):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        corpus.assert_not_called()
        models.assert_not_called()
        with (out / 'tests.log').open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(log.getvalue())
        r.require(result.wasSuccessful(), 'Fixture suite failed; tests.log preserved')
        tests = sys.modules['test_feature_profile']
        evidence = tests.FIXTURE_EVIDENCE
        valid = [e for e in evidence if e['kind'] == 'valid_test_fixture']
        invalid = [e for e in evidence if e['kind'] == 'invalid_test_fixture']
        r.require(len(valid) == 131 and len(invalid) == 5 and all(e['verified'] for e in evidence), 'Fixture evidence incomplete')
        r.write_json(out / 'fixture_results.json', dict(data_kind='test_fixture', valid_inputs=valid, invalid_inputs=invalid,
                     timings='No fixture timing is a research measurement; deterministic StepClock is used for timer-accounting tests.'))
        for name, value in {**protected, **source_hashes}.items():
            r.require(r.sha(ROOT / name) == value, f'File changed during validation: {name}')
        r.require(not (ROOT / ctx['plan']['future_profile_root']).exists(), 'Fixture suite created corpus profile')
        value = dict(status='fixture_validated_before_corpus_execution', created_at_utc=datetime.now(timezone.utc).isoformat(),
                     source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                     plan_freeze_sha256=r.sha(r.FREEZE / 'freeze.json'), python=sys.version, platform=platform.platform(),
                     source_sha256=source_hashes, protected_input_sha256=protected,
                     tests=dict(successful=result.wasSuccessful(), tests_run=result.testsRun, failures=len(result.failures),
                                errors=len(result.errors), skipped=len(result.skipped), valid_fixtures=len(valid), invalid_fixtures=len(invalid)),
                     safeguards=dict(original_corpus_reads=False, stored_model_deserialization=False, stored_model_predictions=False,
                                     corpus_profile_measurement=False, optimization=False),
                     development_note='Initial sandbox run had 6 temporary-directory ACL errors; general-permission run passed. Added child-interruption/exit checks before final validation. Existing failed temporary paths left intact.',
                     artifact_sha256={p.name: r.sha(p) for p in out.iterdir() if p.is_file()})
        r.write_json(r.IMPLEMENTATION, value)
        print(json.dumps(dict(status=value['status'], tests=value['tests'], protected_files=len(protected))))
    except BaseException as exc:
        if not (out / 'tests.log').exists():
            with (out / 'tests.log').open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(log.getvalue())
        r.failure(out / 'validation_failed.json', exc, 'synthetic_fixture_validation')
        raise


if __name__ == '__main__':
    main()
