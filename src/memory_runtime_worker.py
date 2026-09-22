"""One fresh-process arm of the validation-only runtime baseline design.

Invoke with python -B -m src.memory_runtime_worker. This module neither prepares
reference compressed inputs nor launches workers, aggregates, or saves results.
The future parent runner must verify reference round trips before invoking it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from src import compressors, memory_benchmark


DESIGN_ID = "memory_runtime_baseline_v1"
ARMS = ("import_only", "input_only", "codec")
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
PHASES = ("compress", "decompress")
EXPECTED_COMPRESSION = {
    "gzip": {"level": 9}, "bz2": {"level": 9},
    "lzma": {"preset": 6}, "zstd": {"level": 3},
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _response(request_id: str, arm: str, phase: str, algorithm: str) -> dict:
    return {
        "schema_version": 1, "design_id": DESIGN_ID,
        "measurement_status": "validation_only", "score_inclusion": False,
        "measurement_method": "windows_get_process_memory_info_peak_working_set",
        "request_id": request_id, "arm": arm, "phase": phase, "algorithm": algorithm,
        "peak_process_working_set_bytes": None, "observed_input_size": None,
        "verified": None, "input_verified": None, "status": "worker_failed", "error": "",
    }


def measure_arm(*, request_id: str, arm: str, phase: str, algorithm: str,
                input_path: Path, input_sha256: str, expected_output_sha256: str) -> dict:
    """Measure exactly one arm; both digest arguments are required for every arm.

    Controls never assert lossless verification. A codec arm checks only its
    output digest; reference round-trip evidence belongs to the parent runner.
    Exceptions propagate to the caller, and CLI errors cannot report success.
    """
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a nonempty string")
    if arm not in ARMS or phase not in PHASES or algorithm not in ALGORITHMS:
        raise ValueError("Unsupported arm, phase, or algorithm")
    for name, value in (("input_sha256", input_sha256),
                        ("expected_output_sha256", expected_output_sha256)):
        if (not isinstance(value, str) or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    if sys.platform != "win32":
        raise RuntimeError("Runtime baseline requires the Windows backend")
    if not sys.dont_write_bytecode:
        raise RuntimeError("Disable bytecode writes with python -B or PYTHONDONTWRITEBYTECODE=1")
    config = memory_benchmark._load_config()
    repeats, _ = memory_benchmark._memory_config(config)
    if (config != compressors._CONFIG or repeats != 5
            or config["compression"] != EXPECTED_COMPRESSION):
        raise ValueError("Configuration differs from the loaded modules or baseline design")

    # Keep the same request validation and config/import overhead in every arm.
    # Do not resolve/stat/open the supplied input path in import_only.
    verified = input_verified = None
    observed_input_size = None
    if arm != "import_only":
        input_data = input_path.read_bytes()
        if not input_data:
            raise ValueError("Phase input must not be empty")
        observed_input_size = len(input_data)
        if arm == "input_only":
            input_verified = _sha256(input_data) == input_sha256
        else:
            if phase == "compress":
                output_data = compressors.compress_data(input_data, algorithm)
            else:
                output_data = compressors.decompress_data(input_data, algorithm)
            verified = _sha256(output_data) == expected_output_sha256

    # Input/output bytes remain live here. Build/serialize the response afterwards.
    peak = memory_benchmark.current_process_peak_working_set_bytes()
    if type(peak) is not int or peak <= 0:
        raise ValueError("Peak working set must be a positive integer")
    result = _response(request_id, arm, phase, algorithm)
    failed = verified is False or input_verified is False
    result.update(peak_process_working_set_bytes=peak, observed_input_size=observed_input_size,
                  verified=verified, input_verified=input_verified,
                  status="verification_failed" if failed else "ok",
                  error="SHA-256 mismatch" if failed else "")
    return result


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--algorithm", choices=ALGORITHMS, required=True)
    parser.add_argument("--input", dest="input_path", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--expected-output-sha256", required=True)
    args = parser.parse_args(arguments)
    try:
        result = measure_arm(**vars(args))
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        result = _response(args.request_id, args.arm, args.phase, args.algorithm)
        result["error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return {"ok": 0, "verification_failed": 2}.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
