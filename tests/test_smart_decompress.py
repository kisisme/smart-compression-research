"""Operational restoration fixtures, not research measurements or evaluations."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import smart_compress as producer
import smart_decompress as smart
from src import compressors
from test_smart_compress import fixture as model_fixture


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_fixture(directory, algorithm="gzip", filename="복원 🧪.bin"):
    directory.mkdir()
    original = b"ABC\x00" * 4096 + bytes(range(256))
    compressed = compressors.compress_data(original, algorithm)
    manifest = dict(smart_mode_version=1, algorithm=algorithm, original_filename=filename,
                    original_size=len(original), input_sha256=digest(original),
                    compressed_file=smart._PAYLOADS[algorithm], compressed_size=len(compressed),
                    compressed_sha256=digest(compressed), compression_ratio=len(compressed) / len(original),
                    verified=True, input_path="Z:/nonexistent/original.bin")
    (directory / manifest["compressed_file"]).write_bytes(compressed)
    save(directory, manifest)
    return original, manifest


def save(directory, manifest):
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


class SmartDecompressTests(unittest.TestCase):
    def test_four_algorithms_decode_once_without_compression_or_model_and_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for algorithm in smart._PAYLOADS:
                with self.subTest(algorithm=algorithm):
                    package = root / algorithm
                    original, manifest = package_fixture(package, algorithm)
                    before = {p.name: p.read_bytes() for p in package.iterdir()}
                    forbidden = AssertionError("No compression, benchmark or model during restoration")
                    with patch.object(compressors, "decompress_data", wraps=compressors.decompress_data) as decode, \
                         patch.object(compressors, "compress_data", side_effect=forbidden), \
                         patch.object(compressors, "benchmark_compressor", side_effect=forbidden), \
                         patch.object(producer, "load_selector", side_effect=forbidden):
                        result = smart.smart_decompress(package, root / (algorithm + "_restored"))
                    decode.assert_called_once_with(before[manifest["compressed_file"]], algorithm)
                    self.assertTrue(result["verified"])
                    self.assertEqual(result["manifest_sha256"], digest(before["manifest.json"]))
                    self.assertEqual(result["restored_sha256"], digest(original))
                    self.assertEqual((Path(result["output_dir"]) / result["restored_file"]).read_bytes(), original)
                    self.assertEqual({p.name for p in Path(result["output_dir"]).iterdir()}, {manifest["original_filename"]})
                    self.assertEqual(before, {p.name: p.read_bytes() for p in package.iterdir()})
                    self.assertFalse(list(root.glob(".smart_decompress_*")))

    def test_current_producer_both_models_all_modes_and_codecs_are_compatible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "manifest.json"  # Original name may equal package metadata name.
            original = b"source-content\x00" * 512
            source.write_bytes(original)
            for kind in producer.MODEL_TYPES:
                for algorithm in smart._PAYLOADS:
                    models = root / (kind + "_" + algorithm)
                    model_fixture(models, kind, algorithm)
                    before = {p.name: p.read_bytes() for p in models.iterdir()}
                    for mode in ("archive", "balanced", "fast_access"):
                        with self.subTest(model=kind, mode=mode, algorithm=algorithm):
                            package = root / (kind + "_" + algorithm + "_" + mode)
                            with patch.object(producer, "_git_information", return_value={"commit_hash": None, "worktree_dirty": None}):
                                producer.smart_compress(source, package, mode=mode, model_kind=kind, model_dir=models)
                            result = smart.smart_decompress(package, root / (package.name + "_restored"))
                            self.assertEqual((Path(result["output_dir"]) / source.name).read_bytes(), original)
                            self.assertEqual(result["algorithm"], algorithm)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in models.iterdir()})
            self.assertEqual(source.read_bytes(), original)

    def test_invalid_manifest_fields_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            _, base = package_fixture(package)
            changes = [("smart_mode_version", v) for v in (True, 2, "1", None)]
            changes += [("verified", v) for v in (False, 1, "True", None)]
            changes += [("algorithm", v) for v in (None, [], "unsupported")]
            changes += [("compressed_file", v) for v in ("../outside", "payload.zst", "C:/file", "sub/payload.gz")]
            changes += [("original_filename", v) for v in ("", ".", "..", "../out", "sub/out", "sub\\out", "C:\\out",
                "stream:name", "/absolute", "NUL", "con.txt", "COM1.dat", "LPT²", "CONOUT$", "trailing.", "trailing ", "bad\x00", "bad?", None)]
            changes += [(field, v) for field in ("original_size", "compressed_size") for v in (True, 0, -1, "10", 1.5)]
            changes += [(field, v) for field in ("input_sha256", "compressed_sha256") for v in (None, "x" * 64, "0" * 63, [])]
            changes += [("compression_ratio", v) for v in (None, True, -1, 0, .123)]
            with patch.object(compressors, "decompress_data", side_effect=AssertionError("Must reject first")) as decode:
                for field in base.keys() - {"input_path"}:
                    with self.subTest(missing=field):
                        changed = dict(base)
                        del changed[field]
                        save(package, changed)
                        with self.assertRaises(ValueError):
                            smart.smart_decompress(package, root / "output")
                for field, value in changes:
                    with self.subTest(field=field, value=value):
                        save(package, {**base, field: value})
                        with self.assertRaises(ValueError):
                            smart.smart_decompress(package, root / "output")
                decode.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_duplicate_malformed_and_nonfinite_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            _, manifest = package_fixture(package)
            valid = json.dumps(manifest).encode()
            invalid = [b"[]", b"null", b"{", b"\xff", b'{"algorithm":"gzip","algorithm":"zstd"}']
            invalid += [valid[:-1] + b',"unused":' + token + b'}' for token in (b"NaN", b"Infinity", b"1e999")]
            with patch.object(compressors, "decompress_data", side_effect=AssertionError("Must reject first")) as decode:
                for value in invalid:
                    with self.subTest(value=value[:30]):
                        (package / "manifest.json").write_bytes(value)
                        with self.assertRaises((ValueError, UnicodeError)):
                            smart.smart_decompress(package, root / "output")
                decode.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_payload_hash_and_size_mismatches_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            _, manifest = package_fixture(package)
            path = package / manifest["compressed_file"]
            original = path.read_bytes()
            with patch.object(compressors, "decompress_data", side_effect=AssertionError("Must reject first")) as decode:
                for data in (original + b"x", original[:-1], bytes([original[0] ^ 1]) + original[1:]):
                    path.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, "payload size or SHA-256 mismatch"):
                        smart.smart_decompress(package, root / "output")
                decode.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_bad_codec_stream_has_clear_cli_error_for_all_algorithms(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for algorithm in smart._PAYLOADS:
                with self.subTest(algorithm=algorithm):
                    package = root / algorithm
                    _, manifest = package_fixture(package, algorithm)
                    invalid = b"invalid compressed stream"
                    (package / manifest["compressed_file"]).write_bytes(invalid)
                    manifest.update(compressed_size=len(invalid), compressed_sha256=digest(invalid),
                                    compression_ratio=len(invalid) / manifest["original_size"])
                    save(package, manifest)
                    with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
                        self.assertEqual(smart.main([str(package), "--output-dir", str(root / "output")]), 1)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("Cannot decompress " + algorithm, stderr.getvalue())
                    self.assertFalse((root / "output").exists())

    def test_restored_size_and_hash_must_match_saved_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            original, base = package_fixture(package)
            changed_size = {**base, "original_size": len(original) + 1,
                            "compression_ratio": base["compressed_size"] / (len(original) + 1)}
            for manifest in ({**base, "input_sha256": "0" * 64}, changed_size):
                save(package, manifest)
                with patch.object(compressors, "decompress_data", wraps=compressors.decompress_data) as decode:
                    with self.assertRaisesRegex(ValueError, "Restored size or SHA-256 mismatch"):
                        smart.smart_decompress(package, root / "output")
                self.assertEqual(decode.call_count, 1)
            self.assertFalse((root / "output").exists())

    def test_existing_outputs_and_package_internal_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package_fixture(package)
            directory = root / "existing"
            directory.mkdir()
            keep = directory / "keep"
            keep.write_bytes(b"keep")
            existing = root / "existing_file"
            existing.write_bytes(b"existing")
            before = {p.name:p.read_bytes() for p in package.iterdir()}
            with patch.object(compressors, "decompress_data", side_effect=AssertionError("Must reject first")):
                for output in (package, directory, existing, package / "manifest.json"):
                    with self.assertRaises(FileExistsError):
                        smart.smart_decompress(package, output)
                with self.assertRaisesRegex(ValueError, "outside the input package"):
                    smart.smart_decompress(package, package / "new_output")
            self.assertEqual(keep.read_bytes(), b"keep")
            self.assertEqual(existing.read_bytes(), b"existing")
            self.assertEqual(before, {p.name:p.read_bytes() for p in package.iterdir()})

    def test_package_change_during_decode_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            _, manifest = package_fixture(package)
            decode = compressors.decompress_data
            for target in (package / "manifest.json", package / manifest["compressed_file"]):
                saved = target.read_bytes()
                def change(*args):
                    result = decode(*args)
                    target.write_bytes(saved + b" ")
                    return result
                with patch.object(compressors, "decompress_data", side_effect=change):
                    with self.assertRaisesRegex(ValueError, "package changed"):
                        smart.smart_decompress(package, root / "output")
                target.write_bytes(saved)
                self.assertFalse((root / "output").exists())
                self.assertFalse(list(root.glob(".smart_decompress_*")))

    def test_missing_or_linked_package_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                smart.smart_decompress(root / "missing", root / "output")
            package = root / "package"
            package.mkdir()
            with self.assertRaises(ValueError):
                smart.smart_decompress(package, root / "output")
            package.rmdir()
            _, manifest = package_fixture(package)
            payload = package / manifest["compressed_file"]
            original_is_symlink = Path.is_symlink
            def linked(path):
                return path == payload or original_is_symlink(path)
            with patch.object(Path, "is_symlink", linked):
                with self.assertRaisesRegex(ValueError, "regular package file"):
                    smart.smart_decompress(package, root / "output")
            payload.unlink()
            with self.assertRaises(ValueError):
                smart.smart_decompress(package, root / "output")
            self.assertFalse((root / "output").exists())

    def test_staging_write_corruption_and_publication_failure_leave_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            _, manifest = package_fixture(package)
            read = Path.read_bytes
            def corrupt(path):
                data = read(path)
                return b"wrong saved bytes" if path.name == manifest["original_filename"] else data
            cases = [patch.object(Path, "write_bytes", side_effect=OSError("Artificial disk failure")),
                     patch.object(Path, "read_bytes", corrupt),
                     patch.object(Path, "rename", side_effect=OSError("Artificial rename failure"))]
            before = {p.name:p.read_bytes() for p in package.iterdir()}
            for patched in cases:
                with patched, self.assertRaises(OSError):
                    smart.smart_decompress(package, root / "output")
                self.assertFalse((root / "output").exists())
                self.assertFalse(list(root.glob(".smart_decompress_*")))
                self.assertEqual(before, {p.name:p.read_bytes() for p in package.iterdir()})

    def test_output_created_during_decode_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package_fixture(package)
            output = root / "output"
            decode = compressors.decompress_data
            def create(*args):
                data = decode(*args)
                output.mkdir()
                (output / "keep").write_bytes(b"keep")
                return data
            with patch.object(compressors, "decompress_data", side_effect=create):
                with self.assertRaises(FileExistsError):
                    smart.smart_decompress(package, output)
            self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()}, {"keep": b"keep"})
            self.assertFalse(list(root.glob(".smart_decompress_*")))

    def test_cli_success_without_models_features_scoring_or_memory_imports(self):
        guard = """import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy','pandas','sklearn'} or fullname in {
            'smart_compress','src.feature_extractor','src.scoring','src.memory_benchmark',
            'src.memory_validation','src.memory_stability_validation','src.memory_repeatability_validation'}:
            raise RuntimeError('Prohibited import: ' + fullname)
sys.meta_path.insert(0, Guard())
from smart_decompress import main
raise SystemExit(main(sys.argv[1:]))
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            original, manifest = package_fixture(package, "zstd")
            output = root / "output"
            args = [str(package), "--output-dir", str(output)]
            result = subprocess.run([sys.executable, "-B", "-c", guard, *args], capture_output=True, cwd=producer._ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            self.assertTrue(json.loads(result.stdout)["verified"])
            self.assertEqual((output / manifest["original_filename"]).read_bytes(), original)
            result = subprocess.run([sys.executable, "-B", "smart_decompress.py", str(root / "missing"),
                                     "--output-dir", str(root / "new")], capture_output=True, cwd=producer._ROOT)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"Smart decompression failed", result.stderr)
            self.assertFalse((root / "new").exists())


if __name__ == "__main__":
    unittest.main()
