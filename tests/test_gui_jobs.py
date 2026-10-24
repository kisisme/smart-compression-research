"""Artificial subprocess/artifact fixtures; no fixture values are research data.

Unit payloads only exercise the GUI bridge contract. Real CLI tests cover codecs.
"""
import base64
import csv
from dataclasses import FrozenInstanceError
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from src import gui_jobs as jobs


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class BridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gui_jobs_artificial_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "한글 입력 🧪 & test.bin"
        self.original = b"ARTIFICIAL INPUT" * 64
        self.source.write_bytes(self.original)
        self.output, self.logs = self.root / "output", self.root / "logs"
        self.models = self.root / "models"
        self.models.mkdir()
        (self.models / "decision_tree_archive.pkl").write_bytes(b"Artificial, never deserialized")
        (self.models / "decision_tree_summary.json").write_bytes(b"{}")

    def request(self, operation="smart", output=None):
        return jobs.JobRequest(operation, self.source, output or self.output,
            **(dict(mode="archive", model_kind="decision_tree", model_dir=self.models) if operation == "smart" else {}))

    def run_job(self, operation="smart", output=None, backend=None, log_root=None):
        with patch.object(jobs.subprocess, "run", side_effect=backend or self.smart_backend) as process:
            result = jobs.run_job(self.request(operation, output), log_root=log_root or self.logs)
        return result, process

    def smart_backend(self, command, **kwargs):
        output = Path(command[-1])
        output.mkdir()
        payload = b"ARTIFICIAL PAYLOAD, not a real gzip stream"
        (output / "payload.gz").write_bytes(payload)
        manifest = dict(smart_mode_version=1, mode="archive", algorithm="gzip", verified=True,
            input_path=str(self.source.resolve()), input_sha256=jobs._file_sha(self.source), original_size=len(self.original),
            original_filename=self.source.name, compressed_file="payload.gz", compressed_size=len(payload),
            compressed_sha256=jobs._sha(payload), compression_ratio=len(payload)/len(self.original),
            prediction_confidence=.75, features=dict(file_size=len(self.original)),
            provenance=dict(model_kind="decision_tree", config_sha256=jobs._file_sha(jobs.ROOT / "config/experiment_config.json"),
                model_path=str(self.models / "decision_tree_archive.pkl"), model_sha256=jobs._file_sha(self.models / "decision_tree_archive.pkl"),
                model_summary_sha256=jobs._file_sha(self.models / "decision_tree_summary.json")))
        (output / "manifest.json").write_bytes(json_bytes(manifest))
        response=dict(mode="archive", algorithm="gzip", prediction_confidence=.75, verified=True, output_dir=str(output))
        return subprocess.CompletedProcess(command,0,json_bytes(response),b"")

    def compare_backend(self, command, *, status="completed", **kwargs):
        output = Path(command[-1])
        output.mkdir()
        measured = [dict(sample_id="artificial", algorithm=a, original_size=len(self.original), compressed_size=200,
            compression_ratio=200/len(self.original), compression_time_ms=.01, decompression_time_ms=.02,
            verified=True, status="ok", error="") for a in jobs.ALGORITHMS]
        selected = [dict(sample_id="artificial", mode=m, best_algorithm="gzip", best_score=0.,
                         **{"score_"+a:0. for a in jobs.ALGORITHMS}) for m in jobs.MODES] if status == "completed" else []
        if status == "completed_with_failures":
            measured[0].update(verified=False,status="failed",error="Artificial failure",
                              compression_ratio=None,compression_time_ms=None,decompression_time_ms=None,compressed_size=None)
        repeats = [dict(sample_id="artificial",algorithm=a,phase=p,repeat_index=i,elapsed_ns=10000 if p=="compress" else 20000,
                        status="ok",verified=p=="decompress") for a in jobs.ALGORITHMS for p in ("compress","decompress") for i in range(1,6)]
        config = (jobs.ROOT / "config/experiment_config.json").read_bytes()
        artifacts = {"timing_repeats.csv":csv_bytes(repeats),"compression_results.csv":csv_bytes(measured),
                     "selection_labels.csv":csv_bytes(selected) if selected else b"sample_id,mode\n",
                     "config_snapshot.json":config,".gitattributes":b"* -text\n"}
        for name,data in artifacts.items():
            (output / name).write_bytes(data)
        report = dict(compare_mode_version=1,status=status,input_path=str(self.source.resolve()),output_dir=str(output),
            input_sha256=jobs._file_sha(self.source),original_size=len(self.original),measurements=measured,selections=selected,
            errors=[] if status=="completed" else ["Artificial failure/invalidated input"],
            source_sha256={"config/experiment_config.json":jobs._sha(config)},memory_measured=False,memory_score_inclusion=False,
            artifact_sha256={name:jobs._sha(data) for name,data in artifacts.items()})
        (output / "comparison.json").write_bytes(json_bytes(report))
        response={k:report[k] for k in ("status","output_dir","measurements","selections","errors")}
        return subprocess.CompletedProcess(command,0 if status=="completed" else 1,json_bytes(response),b"")

    def package(self):
        package = self.root / "package"
        package.mkdir()
        payload = b"Artificial encoded input"
        (package / "payload.gz").write_bytes(payload)
        manifest=dict(smart_mode_version=1,verified=True,algorithm="gzip",compressed_file="payload.gz",
                      original_filename=self.source.name,original_size=len(self.original),input_sha256=jobs._sha(self.original))
        (package / "manifest.json").write_bytes(json_bytes(manifest))
        return package

    def restore_backend(self, command, **kwargs):
        package, output = Path(command[4]), Path(command[-1])
        manifest=json.loads((package / "manifest.json").read_bytes())
        output.mkdir()
        (output / self.source.name).write_bytes(self.original)
        response=dict(smart_decompress_version=1,algorithm="gzip",verified=True,output_dir=str(output),package_dir=str(package),
            manifest_sha256=jobs._file_sha(package / "manifest.json"),compressed_sha256=jobs._file_sha(package / "payload.gz"),
            restored_file=manifest["original_filename"],restored_size=len(self.original),restored_sha256=jobs._sha(self.original))
        return subprocess.CompletedProcess(command,0,json_bytes(response),b"")

    def test_request_is_frozen_and_command_preserves_paths_without_shell(self):
        request=self.request()
        with self.assertRaises(FrozenInstanceError):
            request.operation="compare"
        result,process=self.run_job()
        self.assertEqual(result.status,"succeeded")
        command=process.call_args.args[0]
        self.assertIsInstance(command,list)
        self.assertEqual(command,list(jobs.build_command(request)))
        self.assertEqual(command[4],str(self.source))
        self.assertFalse(process.call_args.kwargs["shell"])
        self.assertEqual(process.call_args.kwargs["env"]["PYTHONIOENCODING"],"utf-8")
        self.assertEqual(process.call_args.kwargs["cwd"],jobs.ROOT)
        self.assertEqual(process.call_args.kwargs["creationflags"],subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.assertEqual(json.loads(result.log_path.read_bytes())["request"],request.as_dict())
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_pure_request_validation_and_explicit_smart_options(self):
        for values in [dict(operation="bad"),dict(operation="smart"),dict(operation="compare",mode="archive"),
                       dict(operation="decompress",model_kind="decision_tree"),dict(operation="smart",mode="archive",model_kind="bad")]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                jobs.JobRequest(input_path=self.source,output_dir=self.output,**values)
        with self.assertRaises(ValueError):
            jobs.run_job(object(),log_root=self.logs)
        with self.assertRaises(ValueError):
            jobs.JobRunner(log_root=self.logs).submit(object())

    def test_preflight_failures_never_spawn_or_touch_existing_outputs(self):
        self.output.mkdir()
        (self.output / "keep").write_bytes(b"keep")
        with patch.object(jobs.subprocess,"run",side_effect=AssertionError("No spawn")) as process:
            result=jobs.run_job(self.request(),log_root=self.logs)
        process.assert_not_called()
        self.assertEqual(result.status,"failed")
        self.assertIsNone(result.return_code)
        self.assertIsNone(result.data)
        self.assertEqual((self.output / "keep").read_bytes(),b"keep")
        self.source.write_bytes(b"")
        with patch.object(jobs.subprocess,"run",side_effect=AssertionError("No spawn")) as process:
            result=jobs.run_job(self.request(output=self.root / "new"),log_root=self.logs)
        process.assert_not_called()
        self.assertEqual(result.status,"failed")
        self.assertFalse((self.root / "new").exists())

    def test_smart_missing_corrupt_mismatched_artifacts_are_inconclusive(self):
        for problem in ("missing_payload","payload_hash","manifest_verified","mode","confidence","config","model_summary"):
            output=self.root / problem
            def damaged(command,**kwargs):
                completed=self.smart_backend(command,**kwargs)
                path=Path(command[-1]) / "manifest.json"
                manifest=json.loads(path.read_bytes())
                if problem=="missing_payload": (path.parent / "payload.gz").unlink()
                elif problem=="payload_hash": (path.parent / "payload.gz").write_bytes(b"changed")
                elif problem=="manifest_verified": manifest["verified"]=1
                elif problem=="mode": manifest["mode"]="balanced"
                elif problem=="confidence": manifest["prediction_confidence"]=True
                elif problem=="config": manifest["provenance"]["config_sha256"]="0"*64
                else: manifest["provenance"]["model_summary_sha256"]="0"*64
                path.write_bytes(json_bytes(manifest))
                return completed
            with self.subTest(problem=problem):
                result,process=self.run_job(output=output,backend=damaged)
                self.assertEqual(result.status,"inconclusive")
                self.assertIsNone(result.data)
                self.assertEqual(process.call_count,1)
                self.assertIsNotNone(result.log_path)

    def test_invalid_json_utf8_duplicates_and_unverified_response_are_preserved(self):
        invalid=[b"not json",b"[]",b"\xff",b'{"verified":true,"verified":false}',b'{"x":NaN}']
        for index,value in enumerate(invalid):
            def malformed(command,**kwargs):
                completed=self.smart_backend(command,**kwargs)
                return subprocess.CompletedProcess(command,0,value,b"diagnostic")
            result,_=self.run_job(output=self.root / str(index),backend=malformed)
            self.assertEqual(result.status,"inconclusive")
            self.assertEqual(result.stdout,value)
            saved=json.loads(result.log_path.read_bytes())
            self.assertEqual(base64.b64decode(saved["stdout_base64"]),value)
            self.assertEqual(saved["stderr"],"diagnostic")
        def unverified(command,**kwargs):
            completed=self.smart_backend(command,**kwargs)
            response=json.loads(completed.stdout)
            response["verified"]="True"
            return subprocess.CompletedProcess(command,0,json_bytes(response),b"")
        result,_=self.run_job(output=self.root / "unverified",backend=unverified)
        self.assertEqual(result.status,"inconclusive")

    def test_nonzero_smart_exit_never_uses_claimed_success_artifacts(self):
        for code in (1,2,-9):
            def failed(command,**kwargs):
                completed=self.smart_backend(command,**kwargs)
                return subprocess.CompletedProcess(command,code,completed.stdout,b"failure")
            result,_=self.run_job(output=self.root / str(code),backend=failed)
            self.assertEqual(result.status,"failed")
            self.assertEqual(result.return_code,code)
            self.assertIsNone(result.data)

    def test_compare_success_partial_and_invalidated_are_distinct(self):
        for status,expected in (("completed","succeeded"),("completed_with_failures","partial"),("invalidated","invalidated")):
            with self.subTest(status=status):
                result,_=self.run_job("compare",output=self.root / status,
                    backend=lambda command,**kw:self.compare_backend(command,status=status,**kw))
                self.assertEqual(result.status,expected)
                self.assertEqual(result.data["status"],status)
                if expected!="succeeded": self.assertEqual(result.data["selections"],[])

    def test_compare_publication_marker_hash_and_response_mismatch_block_success(self):
        for problem in ("marker","csv_hash","stdout","scores","verified"):
            output=self.root / problem
            def damaged(command,**kwargs):
                completed=self.compare_backend(command,**kwargs)
                path=Path(command[-1]) / "comparison.json"
                report=json.loads(path.read_bytes())
                response=json.loads(completed.stdout)
                if problem=="marker": (path.parent / "publication_failed.json").write_bytes(b"{}")
                elif problem=="csv_hash": (path.parent / "timing_repeats.csv").write_bytes(b"changed")
                elif problem=="stdout": response["output_dir"]=str(self.root / "elsewhere")
                else:
                    if problem=="scores": report["selections"][0]["best_algorithm"]="zstd"
                    else: report["measurements"][0]["verified"]="True"
                    response={k:report[k] for k in response}
                    path.write_bytes(json_bytes(report))
                return subprocess.CompletedProcess(command,0,json_bytes(response),b"")
            with self.subTest(problem=problem):
                result,_=self.run_job("compare",output,damaged)
                self.assertEqual(result.status,"inconclusive")
                self.assertIsNone(result.data)

    def test_restore_binds_package_hash_and_actual_restored_file(self):
        package=self.package()
        request=jobs.JobRequest("decompress",package,self.output)
        with patch.object(jobs.subprocess,"run",side_effect=self.restore_backend):
            result=jobs.run_job(request,log_root=self.logs)
        self.assertEqual(result.status,"succeeded")
        self.assertEqual(result.data["restored_sha256"],jobs._sha(self.original))
        for problem in ("wrong_bytes","manifest_hash","path"):
            output=self.root / problem
            def damaged(command,**kwargs):
                completed=self.restore_backend(command,**kwargs)
                response=json.loads(completed.stdout)
                if problem=="wrong_bytes": (Path(command[-1]) / self.source.name).write_bytes(b"wrong")
                elif problem=="manifest_hash": response["manifest_sha256"]="0"*64
                else: response["restored_file"]="../outside"
                return subprocess.CompletedProcess(command,0,json_bytes(response),b"")
            with patch.object(jobs.subprocess,"run",side_effect=damaged):
                result=jobs.run_job(jobs.JobRequest("decompress",package,output),log_root=self.logs)
            self.assertEqual(result.status,"inconclusive")
            self.assertIsNone(result.data)

    def test_changed_input_model_or_backend_source_invalidates_success(self):
        for problem in ("input","model"):
            path=self.source if problem=="input" else self.models / "decision_tree_archive.pkl"
            original=path.read_bytes()
            def change(command,**kwargs):
                completed=self.smart_backend(command,**kwargs)
                path.write_bytes(original+b"changed")
                return completed
            result,_=self.run_job(output=self.root / problem,backend=change)
            self.assertEqual(result.status,"inconclusive")
            self.assertIsNone(result.data)
            path.write_bytes(original)
        sha=jobs._file_sha
        target=jobs.ROOT / "main.py"
        calls=0
        def drift(path):
            nonlocal calls
            value=sha(path)
            if Path(path)==target:
                calls+=1
                if calls>1: return "0"*64
            return value
        with patch.object(jobs,"_file_sha",side_effect=drift):
            result,_=self.run_job(output=self.root / "source")
        self.assertEqual(result.status,"inconclusive")
        self.assertIn("source/config changed",result.message)

    def test_log_failure_is_separate_and_never_retries_successful_backend(self):
        blocker=self.root / "not_a_directory"
        blocker.write_bytes(b"keep")
        result,process=self.run_job(log_root=blocker / "logs")
        self.assertEqual(result.status,"succeeded")
        self.assertIsNotNone(result.data)
        self.assertIsNone(result.log_path)
        self.assertIsNotNone(result.log_error)
        self.assertEqual(process.call_count,1)
        self.assertEqual(blocker.read_bytes(),b"keep")
        self.assertTrue((self.output / "payload.gz").exists())

    def test_log_sync_failure_keeps_partial_log_without_changing_backend_success(self):
        with patch.object(jobs.os,"fsync",side_effect=OSError("Artificial log sync failure")):
            result,process=self.run_job()
        self.assertEqual(result.status,"succeeded")
        self.assertIsNone(result.log_path)
        self.assertIn("Artificial log sync failure",result.log_error)
        self.assertTrue((self.logs / result.job_id / "job.json").exists())
        self.assertTrue((self.output / "payload.gz").exists())
        self.assertEqual(process.call_count,1)

    def test_existing_log_session_is_preserved_on_id_collision(self):
        job_id="a"*32
        directory=self.logs / job_id
        directory.mkdir(parents=True)
        path=directory / "job.json"
        path.write_bytes(b"keep existing log")
        with patch.object(jobs.subprocess,"run",side_effect=self.smart_backend) as process:
            result=jobs.run_job(self.request(),log_root=self.logs,job_id=job_id)
        self.assertEqual(result.status,"succeeded")
        self.assertIsNone(result.log_path)
        self.assertIsNotNone(result.log_error)
        self.assertEqual(path.read_bytes(),b"keep existing log")
        self.assertEqual(process.call_count,1)

    def test_logging_inside_backend_output_or_input_package_is_never_written(self):
        result,process=self.run_job(log_root=self.output / "logs")
        self.assertEqual(result.status,"failed")
        process.assert_not_called()
        self.assertIsNotNone(result.log_error)
        self.assertFalse(self.output.exists())
        package=self.package()
        before={p.name:p.read_bytes() for p in package.iterdir()}
        with patch.object(jobs.subprocess,"run",side_effect=AssertionError("No spawn")) as process:
            result=jobs.run_job(jobs.JobRequest("decompress",package,self.output),log_root=package / "logs")
        process.assert_not_called()
        self.assertIsNotNone(result.log_error)
        self.assertEqual(before,{p.name:p.read_bytes() for p in package.iterdir()})

    def test_spawn_error_returns_logged_failure_and_preserves_inputs(self):
        result,process=self.run_job(backend=lambda *a,**k:(_ for _ in ()).throw(PermissionError("Artificial spawn denial")))
        self.assertEqual(result.status,"failed")
        self.assertIsNone(result.return_code)
        self.assertIn("Artificial spawn denial",result.message)
        self.assertIsNotNone(result.log_path)
        self.assertEqual(process.call_count,1)
        self.assertEqual(self.source.read_bytes(),self.original)


class RunnerTests(unittest.TestCase):
    def test_single_non_daemon_worker_rejects_duplicates_and_correlates_queue_ids(self):
        started,release=threading.Event(),threading.Event()
        runner=jobs.JobRunner()
        first=jobs.JobRequest("compare",Path("input"),Path("output_one"))
        second=jobs.JobRequest("compare",Path("input"),Path("output_two"))
        def controlled(request,*,job_id,log_root):
            started.set()
            release.wait(3)
            return jobs.JobResult(job_id,request,"failed","ARTIFICIAL CONTROL",jobs.build_command(request),"fixture","fixture")
        with patch.object(jobs,"run_job",side_effect=controlled):
            try:
                first_id=runner.submit(first)
                self.assertTrue(started.wait(2))
                self.assertTrue(runner.busy)
                self.assertFalse(runner._thread.daemon)
                self.assertIsNone(runner.poll())
                with self.assertRaisesRegex(RuntimeError,"already running"):
                    runner.submit(second)
            finally:
                release.set()
                self.assertTrue(runner.wait(3))
            result=runner.poll()
            self.assertEqual(result.job_id,first_id)
            self.assertEqual(result.request,first)
            self.assertIsNone(runner.poll())
            second_id=runner.submit(second)
            self.assertTrue(runner.wait(3))
            self.assertNotEqual(first_id,second_id)
            self.assertEqual(runner.poll().job_id,second_id)

    def test_unexpected_worker_exception_still_releases_busy_and_returns_failure(self):
        runner=jobs.JobRunner()
        request=jobs.JobRequest("compare",Path("input"),Path("output"))
        with patch.object(jobs,"run_job",side_effect=RuntimeError("Artificial worker error")):
            job_id=runner.submit(request)
            self.assertTrue(runner.wait(3))
        result=runner.poll()
        self.assertEqual(result.job_id,job_id)
        self.assertEqual(result.status,"failed")
        self.assertIn("Artificial worker error",result.message)
        self.assertFalse(runner.busy)

    def test_import_has_no_gui_model_codec_or_scoring_dependency(self):
        guard="""import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'tkinter','numpy','pandas','sklearn','zstandard'} or fullname in {
            'main','smart_compress','smart_decompress','compare_compress','src.compressors','src.scoring','src.feature_extractor','src.memory_benchmark'}:
            raise RuntimeError('Prohibited import: '+fullname)
sys.meta_path.insert(0,Guard())
from src.gui_jobs import JobRequest,JobRunner,build_command
request=JobRequest('compare','input','new_output')
assert build_command(request)[3]=='compare'
assert not JobRunner().busy
print('import and pure construction passed')
"""
        result=subprocess.run([sys.executable,"-B","-c",guard],cwd=jobs.ROOT,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b"passed",result.stdout)


if __name__ == "__main__":
    unittest.main()
