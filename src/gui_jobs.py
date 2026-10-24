"""Widget-free, single-job bridge to the existing CLI; standard library only.

No Tk, model deserialization, feature extraction, codecs or scoring run here.
Only a succeeded result may be presented as a normally verified GUI outcome.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_ROOT = ROOT / "data/temp/gui_sessions"
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
MODES = ("archive", "balanced", "fast_access")
MODELS = ("decision_tree", "random_forest")
PAYLOADS = dict(zip(ALGORITHMS, ("payload.gz", "payload.bz2", "payload.xz", "payload.zst")))
SOURCE_FILES = ("main.py", "smart_compress.py", "smart_decompress.py", "compare_compress.py", "src/gui_jobs.py",
                "src/compressors.py", "src/scoring.py", "src/feature_extractor.py", "config/experiment_config.json")


@dataclass(frozen=True, slots=True)
class JobRequest:
    operation: str
    input_path: Path
    output_dir: Path
    mode: str | None = None
    model_kind: str | None = None
    model_dir: Path | None = None

    def __post_init__(self):
        if self.operation not in ("smart", "decompress", "compare"):
            raise ValueError("Unknown GUI operation")
        if self.operation == "smart":
            if self.mode not in MODES or self.model_kind not in MODELS:
                raise ValueError("Smart requires an explicit supported mode and model")
        elif any(v is not None for v in (self.mode, self.model_kind, self.model_dir)):
            raise ValueError("Model and mode options are only valid for Smart")
        for field in ("input_path", "output_dir", "model_dir"):
            value = getattr(self, field)
            if value is not None:
                if not str(value).strip():
                    raise ValueError(f"Empty {field}")
                object.__setattr__(self, field, Path(value).expanduser().absolute())

    def as_dict(self):
        return dict(operation=self.operation, input_path=str(self.input_path), output_dir=str(self.output_dir),
                    mode=self.mode, model_kind=self.model_kind, model_dir=str(self.model_dir) if self.model_dir else None)


@dataclass(frozen=True, slots=True)
class JobResult:
    job_id: str
    request: JobRequest
    status: str
    message: str
    command: tuple[str, ...]
    started_at_utc: str
    finished_at_utc: str
    return_code: int | None = None
    stdout: bytes = b""
    stderr: bytes = b""
    data: dict | None = None
    input_snapshot: dict | None = None
    log_path: Path | None = None
    log_error: str | None = None

    def as_dict(self):
        return dict(job_id=self.job_id, request=self.request.as_dict(), status=self.status, message=self.message,
            command=list(self.command), started_at_utc=self.started_at_utc, finished_at_utc=self.finished_at_utc,
            return_code=self.return_code, stdout=self.stdout.decode("utf-8", errors="replace"),
            stderr=self.stderr.decode("utf-8", errors="replace"), stdout_base64=base64.b64encode(self.stdout).decode("ascii"),
            stderr_base64=base64.b64encode(self.stderr).decode("ascii"), data=self.data, input_snapshot=self.input_snapshot,
            log_path=str(self.log_path) if self.log_path else None, log_error=self.log_error,
            environment_overrides={"PYTHONIOENCODING": "utf-8"}, cwd=str(ROOT))


def build_command(request: JobRequest) -> tuple[str, ...]:
    args = [sys.executable, "-B", str(ROOT / "main.py"), request.operation, str(request.input_path)]
    if request.operation == "smart":
        args.extend(("--mode", request.mode, "--model", request.model_kind))
        if request.model_dir:
            args.extend(("--model-dir", str(request.model_dir)))
    args.extend(("--output-dir", str(request.output_dir)))
    return tuple(args)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _bytes(path):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink() and not path.is_junction(), f"Expected a regular artifact: {path}")
    return path.read_bytes()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"Duplicate response key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Non-finite response number: {value}")
    def floating(value):
        number = float(value)
        _require(math.isfinite(number), "Non-finite response number")
        return number
    result = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid, parse_float=floating)
    _require(isinstance(result, dict), "Expected a JSON object response")
    return result


def _child(root, name):
    _require(isinstance(name, str) and name not in ("", ".", "..") and not any(c in name for c in "/\\:"),
             "Artifact name must be a single file name")
    path = Path(root) / name
    _require(path.resolve().parent == Path(root).resolve(), "Artifact escapes its output directory")
    _bytes(path)  # Reject missing/linked artifacts before using them.
    return path


def _same_path(value, expected):
    return isinstance(value, str) and Path(value).resolve() == Path(expected).resolve()


def _preflight(request, log_root):
    source, output = request.input_path, request.output_dir
    _require(not (output.exists() or output.is_symlink() or output.is_junction()), "Output directory already exists")
    _require(not Path(log_root).resolve().is_relative_to(output.resolve()), "Log directory must be outside backend output")
    files = {str(ROOT / name): _file_sha(ROOT / name) for name in SOURCE_FILES}
    snapshot = dict(source_sha256={name: files[str(ROOT / name)] for name in SOURCE_FILES}, input_files={})
    if request.operation == "decompress":
        _require(source.is_dir(), "Expected a package directory")
        _require(not output.resolve().is_relative_to(source.resolve()), "Output must be outside input package")
        _require(not Path(log_root).resolve().is_relative_to(source.resolve()), "Log directory must be outside input package")
        path = _child(source, "manifest.json")
        raw = _bytes(path)
        manifest = _json(raw)
        _require(type(manifest.get("smart_mode_version")) is int and manifest["smart_mode_version"] == 1
                 and manifest.get("verified") is True, "Package is not a verified version-1 package")
        algorithm = manifest.get("algorithm")
        _require(isinstance(algorithm, str) and algorithm in PAYLOADS, "Unsupported package algorithm")
        _require(manifest.get("compressed_file") == PAYLOADS[algorithm], "Package payload name mismatch")
        payload = _child(source, PAYLOADS[algorithm])
        snapshot.update(manifest_sha256=_sha(raw), algorithm=algorithm, input_sha256=manifest.get("input_sha256"),
                        original_size=manifest.get("original_size"), original_filename=manifest.get("original_filename"),
                        compressed_sha256=_file_sha(payload))
        snapshot["input_files"] = {str(path): _sha(raw), str(payload): snapshot["compressed_sha256"]}
    else:
        _require(source.is_file() and source.stat().st_size > 0, "Expected a non-empty input file")
        snapshot.update(input_sha256=_file_sha(source), original_size=source.stat().st_size)
        snapshot["input_files"][str(source)] = snapshot["input_sha256"]
        if request.operation == "smart":
            models = request.model_dir or ROOT / "data/results/pilot_1008" / request.model_kind
            for filename in (f"{request.model_kind}_{request.mode}.pkl", f"{request.model_kind}_summary.json"):
                path = _child(models, filename)
                snapshot["input_files"][str(path)] = _file_sha(path)
    snapshot["config_sha256"] = files[str(ROOT / "config/experiment_config.json")]
    return snapshot


def _recheck(snapshot):
    for name, checksum in snapshot["source_sha256"].items():
        _require(_file_sha(ROOT / name) == checksum, f"Backend source/config changed: {name}")
    for name, checksum in snapshot["input_files"].items():
        _require(_file_sha(name) == checksum, f"Input/model changed during operation: {name}")


def _check_file(path, size, checksum):
    _require(type(size) is int and size > 0, "Invalid artifact size")
    _require(isinstance(checksum, str) and len(checksum) == 64, "Invalid artifact SHA-256")
    _require(path.stat().st_size == size and _file_sha(path) == checksum, "Saved artifact size/SHA-256 mismatch")


def _number(value, *, zero=False):
    return type(value) in (int, float) and math.isfinite(value) and (value >= 0 if zero else value > 0)


def _assess(request, code, stdout, snapshot):
    response = _json(stdout)
    _require(_same_path(response.get("output_dir"), request.output_dir), "Response output path differs from request")
    output = request.output_dir
    if request.operation == "compare":
        _require(not (output / "publication_failed.json").exists(), "Comparison has a publication failure marker")
        report = _json(_bytes(_child(output, "comparison.json")))
        _require(type(report.get("compare_mode_version")) is int and report["compare_mode_version"] == 1, "Unsupported comparison version")
        _require(_same_path(report.get("input_path"), request.input_path) and _same_path(report.get("output_dir"), output),
                 "Comparison paths differ from request")
        _require(all(response.get(k) == report.get(k) for k in ("status", "output_dir", "measurements", "selections", "errors")),
                 "CLI response and comparison report disagree")
        artifacts = report.get("artifact_sha256")
        required = {"timing_repeats.csv", "compression_results.csv", "selection_labels.csv", "config_snapshot.json", ".gitattributes"}
        _require(isinstance(artifacts, dict) and set(artifacts) == required, "Incomplete comparison artifacts")
        for name, checksum in artifacts.items():
            _require(_file_sha(_child(output, name)) == checksum, f"Comparison artifact hash mismatch: {name}")
        status = report.get("status")
        if code == 1 and status in ("completed_with_failures", "invalidated"):
            _require(report.get("selections") == [], "Failed comparison contains normal selections")
            return ("partial" if status == "completed_with_failures" else "invalidated"), "Comparison retained failed/invalid measurements", report
        _require(code == 0 and status == "completed", "Comparison did not complete normally")
        measured, selected = report.get("measurements"), report.get("selections")
        _require(isinstance(measured, list) and len(measured) == 4 and {r.get("algorithm") for r in measured} == set(ALGORITHMS)
                 and all(r.get("verified") is True and r.get("status") == "ok" for r in measured), "Comparison has unverified/incomplete measurements")
        _require(isinstance(selected, list) and len(selected) == 3 and {r.get("mode") for r in selected} == set(MODES),
                 "Comparison has incomplete mode selections")
        for row in measured:
            _require(type(row.get("original_size")) is int and row["original_size"] == snapshot["original_size"]
                     and type(row.get("compressed_size")) is int and row["compressed_size"] > 0
                     and all(_number(row.get(k)) for k in ("compression_ratio", "compression_time_ms", "decompression_time_ms")),
                     "Invalid comparison measurement values")
        for row in selected:
            scores = {a: row.get("score_" + a) for a in ALGORITHMS}
            _require(all(_number(v, zero=True) for v in scores.values()) and _number(row.get("best_score"), zero=True),
                     "Invalid comparison scores")
            chosen = min(ALGORITHMS, key=scores.__getitem__)
            _require(row.get("best_algorithm") == chosen and row["best_score"] == scores[chosen], "Comparison selection/score mismatch")
        _require(report.get("input_sha256") == snapshot["input_sha256"] and report.get("original_size") == snapshot["original_size"],
                 "Comparison input differs from job snapshot")
        _require(report.get("source_sha256", {}).get("config/experiment_config.json") == snapshot["config_sha256"], "Comparison config differs from job snapshot")
        _require(report.get("memory_measured") is False and report.get("memory_score_inclusion") is False, "Unexpected memory measurement/score")
        return "succeeded", "Comparison completed and saved reports agree", report
    _require(code == 0 and response.get("verified") is True, "Backend did not report a verified success")
    algorithm = response.get("algorithm")
    _require(isinstance(algorithm, str) and algorithm in ALGORITHMS, "Invalid response algorithm")
    if request.operation == "smart":
        manifest = _json(_bytes(_child(output, "manifest.json")))
        _require(type(manifest.get("smart_mode_version")) is int and manifest["smart_mode_version"] == 1
                 and manifest.get("verified") is True, "Invalid Smart manifest verification/version")
        _require(manifest.get("algorithm") == algorithm and manifest.get("mode") == request.mode == response.get("mode"),
                 "Smart algorithm/mode response mismatch")
        _require(_same_path(manifest.get("input_path"), request.input_path) and manifest.get("input_sha256") == snapshot["input_sha256"]
                 and manifest.get("original_size") == snapshot["original_size"], "Smart input differs from job snapshot")
        provenance = manifest.get("provenance", {})
        _require(provenance.get("model_kind") == request.model_kind and provenance.get("config_sha256") == snapshot["config_sha256"],
                 "Smart model/config response mismatch")
        models = request.model_dir or ROOT / "data/results/pilot_1008" / request.model_kind
        model_path = models / f"{request.model_kind}_{request.mode}.pkl"
        _require(_same_path(provenance.get("model_path"), model_path)
                 and provenance.get("model_sha256") == snapshot["input_files"][str(model_path)], "Smart model bytes differ from job snapshot")
        summary_path = models / f"{request.model_kind}_summary.json"
        _require(provenance.get("model_summary_sha256") == snapshot["input_files"][str(summary_path)], "Smart summary differs from job snapshot")
        confidence = manifest.get("prediction_confidence")
        _require(_number(confidence, zero=True) and confidence <= 1 and response.get("prediction_confidence") == confidence,
                 "Smart confidence response mismatch")
        _require(isinstance(manifest.get("features"), dict) and manifest["features"], "Smart features missing")
        _require(manifest.get("compressed_file") == PAYLOADS[algorithm], "Unexpected Smart payload name")
        _check_file(_child(output, PAYLOADS[algorithm]), manifest.get("compressed_size"), manifest.get("compressed_sha256"))
        return "succeeded", "Smart package and verified response agree", manifest
    _require(type(response.get("smart_decompress_version")) is int and response["smart_decompress_version"] == 1,
             "Unsupported restoration response version")
    _require(_same_path(response.get("package_dir"), request.input_path) and response.get("manifest_sha256") == snapshot["manifest_sha256"]
             and algorithm == snapshot["algorithm"] and response.get("compressed_sha256") == snapshot["compressed_sha256"],
             "Restoration package differs from job snapshot")
    _require(response.get("restored_file") == snapshot["original_filename"] and response.get("restored_size") == snapshot["original_size"]
             and response.get("restored_sha256") == snapshot["input_sha256"], "Restoration original metadata mismatch")
    _check_file(_child(output, response.get("restored_file")), response.get("restored_size"), response.get("restored_sha256"))
    return "succeeded", "Restored artifact and verified response agree", response


def _save_log(result, log_root):
    directory = Path(log_root) / result.job_id
    try:
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
        path = directory / "job.json"
        logged = replace(result, log_path=path)
        data = (json.dumps(logged.as_dict(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _require(path.read_bytes() == data, "Saved GUI log bytes mismatch")
        return logged
    except Exception as exc:
        return replace(result, log_error=f"{type(exc).__name__}: {exc}; attempted log: {directory}")


def run_job(request: JobRequest, *, log_root: Path = DEFAULT_LOG_ROOT, job_id: str | None = None) -> JobResult:
    """Blocking worker API. Preserve exit/output bytes and never retry a backend."""
    _require(isinstance(request, JobRequest), "Expected a frozen JobRequest")
    job_id = job_id or uuid.uuid4().hex
    _require(isinstance(job_id, str) and len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id), "Invalid job ID")
    command, started = build_command(request), datetime.now(timezone.utc).isoformat()
    code, stdout, stderr, data, snapshot = None, b"", b"", None, None
    status, message = "failed", "Job did not run"
    try:
        snapshot = _preflight(request, log_root)
        environment = dict(os.environ, PYTHONIOENCODING="utf-8")
        completed = subprocess.run(list(command), cwd=ROOT, env=environment, shell=False, capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        if code != 0 and request.operation != "compare":
            message = f"Backend failed with exit code {code}"
        else:
            try:
                status, message, data = _assess(request, code, stdout, snapshot)
                if status == "succeeded":
                    _recheck(snapshot)
            except Exception as exc:
                status, message, data = ("inconclusive" if code == 0 or request.output_dir.exists() else "failed"), f"{type(exc).__name__}: {exc}", None
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
    result = JobResult(job_id, request, status, message, command, started, datetime.now(timezone.utc).isoformat(),
                       code, stdout, stderr, data, snapshot)
    # Never let a logging path inside an input package/backend output alter it,
    # including when preflight rejected the request before the child was started.
    try:
        unsafe_log = (Path(log_root).resolve().is_relative_to(request.output_dir.resolve()) or
                      (request.operation == "decompress" and Path(log_root).resolve().is_relative_to(request.input_path.resolve())))
    except Exception as exc:
        return replace(result, log_error=f"Log path cannot be resolved: {type(exc).__name__}: {exc}")
    if unsafe_log:
        return replace(result, log_error="Log directory overlaps input package/backend output; log not written")
    return _save_log(result, log_root)


class JobRunner:
    """One non-daemon worker; GUI consumes terminal JobResults via poll()."""
    def __init__(self, *, log_root: Path = DEFAULT_LOG_ROOT):
        self.log_root = Path(log_root)
        self._results = queue.Queue()
        self._lock = threading.Lock()
        self._active_id = None
        self._thread = None

    @property
    def busy(self):
        with self._lock:
            return self._active_id is not None

    def submit(self, request: JobRequest) -> str:
        _require(isinstance(request, JobRequest), "Expected a frozen JobRequest")
        with self._lock:
            if self._active_id is not None:
                raise RuntimeError("A GUI job is already running")
            job_id = uuid.uuid4().hex
            thread = threading.Thread(target=self._work, args=(request, job_id), name="gui-job-" + job_id, daemon=False)
            self._active_id, self._thread = job_id, thread
            try:
                thread.start()
            except Exception:
                self._active_id, self._thread = None, None
                raise
            return job_id

    def _work(self, request, job_id):
        try:
            result = run_job(request, log_root=self.log_root, job_id=job_id)
        except Exception as exc:
            now = datetime.now(timezone.utc).isoformat()
            result = JobResult(job_id, request, "failed", f"Worker failed: {type(exc).__name__}: {exc}", build_command(request), now, now)
        with self._lock:
            self._active_id = None
            self._results.put(result)

    def poll(self) -> JobResult | None:
        try:
            return self._results.get_nowait()
        except queue.Empty:
            return None

    def wait(self, timeout: float | None = None) -> bool:
        """For tests/non-GUI callers only. GUI event handlers must use poll()."""
        with self._lock:
            thread = self._thread
        if thread:
            thread.join(timeout)
        return not self.busy
