"""Restore a Smart Mode package into a new directory, checking both SHA-256s.

Uses the saved algorithm only. No model, feature extraction, benchmark, or memory
measurement is needed. Reads whole files into memory, as smart_compress.py does.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile

from src import compressors


_PAYLOADS = {"gzip": "payload.gz", "bz2": "payload.bz2", "lzma": "payload.xz", "zstd": "payload.zst"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError(f"Non-finite manifest number: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        _nonfinite(value)
    return number


def _read_file(path: Path) -> bytes:
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError(f"Expected a regular package file: {path}")
    return path.read_bytes()


def _validate_manifest(data: bytes) -> dict:
    manifest = json.loads(data, object_pairs_hook=_object, parse_constant=_nonfinite, parse_float=_finite_float)
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")
    if type(manifest.get("smart_mode_version")) is not int or manifest["smart_mode_version"] != 1:
        raise ValueError("Unsupported smart_mode_version; expected 1")
    if manifest.get("verified") is not True:
        raise ValueError("Manifest does not record successful lossless verification")
    algorithm = manifest.get("algorithm")
    if not isinstance(algorithm, str) or algorithm not in _PAYLOADS:
        raise ValueError("Unsupported saved algorithm")
    if manifest.get("compressed_file") != _PAYLOADS[algorithm]:
        raise ValueError("Compressed filename does not match the saved algorithm")
    name = manifest.get("original_filename")
    # Original names are data, never paths. Use Windows-portable file names even
    # when this CLI is run on another platform; do not follow recorded input_path.
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                *(prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³")}
    if (not isinstance(name, str) or not name or name in (".", "..")
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or name.endswith((".", " ")) or name.split(".", 1)[0].upper() in reserved):
        raise ValueError("Original filename must be one valid file name, without a path")
    for field in ("original_size", "compressed_size"):
        if type(manifest.get(field)) is not int or manifest[field] <= 0:
            raise ValueError(f"Expected a positive integer: {field}")
    for field in ("input_sha256", "compressed_sha256"):
        value = manifest.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError(f"Invalid SHA-256: {field}")
    ratio = manifest.get("compression_ratio")
    if (type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0
            or ratio != manifest["compressed_size"] / manifest["original_size"]):
        raise ValueError("Compression ratio differs from recorded sizes")
    return manifest


def smart_decompress(package_dir: str | Path, output_dir: str | Path) -> dict:
    """Validate a version-1 package, decode once, and publish the original name.

    SHA-256 and size are compared with the saved original metadata. The original
    file and model are not accessed. Hash agreement does not authenticate a
    package whose manifest and payload have both been replaced.
    """
    package = Path(package_dir).resolve()
    destination = Path(output_dir).absolute()
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise FileExistsError(f"Output directory already exists: {destination}")
    # Refuse publication inside the package, including through a linked parent.
    if destination.resolve().is_relative_to(package):
        raise ValueError("Output directory must be outside the input package")
    if not package.is_dir():
        raise ValueError(f"Package directory does not exist: {package}")
    manifest_path = package / "manifest.json"
    manifest_bytes = _read_file(manifest_path)
    manifest = _validate_manifest(manifest_bytes)
    payload_path = package / manifest["compressed_file"]
    compressed = _read_file(payload_path)
    if len(compressed) != manifest["compressed_size"] or _digest(compressed) != manifest["compressed_sha256"]:
        raise ValueError("Compressed payload size or SHA-256 mismatch")
    algorithm = manifest["algorithm"]
    try:
        restored = compressors.decompress_data(compressed, algorithm)
    except Exception as exc:
        raise ValueError(f"Cannot decompress {algorithm} payload: {exc}") from exc
    if (len(restored) != manifest["original_size"] or _digest(restored) != manifest["input_sha256"]):
        raise ValueError("Restored size or SHA-256 mismatch (verified=False); no output published")
    result = {
        "smart_decompress_version": 1, "smart_mode_version": manifest["smart_mode_version"],
        "algorithm": algorithm, "package_dir": str(package), "manifest_sha256": _digest(manifest_bytes),
        "compressed_file": manifest["compressed_file"], "compressed_size": len(compressed),
        "compressed_sha256": _digest(compressed), "output_dir": str(destination),
        "restored_file": manifest["original_filename"], "restored_size": len(restored),
        "restored_sha256": _digest(restored), "verified": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "smart_decompress_source_sha256": _digest(Path(__file__).read_bytes()),
        "operation": "One saved-algorithm decompression; size/SHA-256 verification; no model or benchmark.",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".smart_decompress_", dir=destination.parent) as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        restored_path = staged / manifest["original_filename"]
        restored_path.write_bytes(restored)
        if restored_path.read_bytes() != restored:
            raise OSError("Saved restored bytes differ from verified bytes")
        if _read_file(manifest_path) != manifest_bytes or _read_file(payload_path) != compressed:
            raise ValueError("Input package changed during restoration; no output published")
        if destination.exists() or destination.is_symlink() or destination.is_junction():
            raise FileExistsError(f"Output directory already exists: {destination}")
        # Windows directory rename refuses an existing destination. All checks
        # and writes happen in staging before the directory is published.
        staged.rename(destination)
    return result


def main(arguments: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, prog=prog)
    parser.add_argument("package_dir", type=Path, help="Smart Mode directory containing manifest.json and payload")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for the restored original file")
    args = parser.parse_args(arguments)
    try:
        result = smart_decompress(args.package_dir, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        print(f"Smart decompression failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
