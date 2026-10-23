"""Unified CLI routing/operation tests; controlled models are not research data."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import main as cli
import smart_compress as smart
import smart_decompress as restore
import compare_compress as compare
from src import compressors
from test_smart_compress import fixture as model_fixture
from test_smart_decompress import package_fixture


class DispatchTests(unittest.TestCase):
    def test_only_selected_handler_receives_arguments_unchanged_and_exit_status(self):
        for command, module in cli.COMMANDS.items():
            for code in (0, 1):
                with self.subTest(command=command, code=code):
                    forwarded = ["한글 입력 🧪.bin", "--output-dir", "output with spaces", "--unknown", "literal"]
                    handler = Mock(return_value=code)
                    original = ["tool.py", "outside arguments"]
                    def check(arguments, *, prog):
                        self.assertIs(sys.argv, original)
                        self.assertEqual(prog, expected_prog)
                        return code
                    handler.side_effect = check
                    with patch.object(sys, "argv", original), \
                         patch.object(cli.importlib, "import_module", return_value=SimpleNamespace(main=handler)) as imported:
                        expected_prog = argparse.ArgumentParser().prog + " " + command
                        self.assertEqual(cli.main([command, *forwarded]), code)
                        self.assertIs(sys.argv, original)
                    imported.assert_called_once_with(module)
                    handler.assert_called_once_with(forwarded, prog=expected_prog)

    def test_child_help_and_parser_errors_restore_argv_without_masking_system_exit(self):
        for code in (0, 2):
            original = ["main.py"]
            handler = Mock(side_effect=SystemExit(code))
            with patch.object(sys, "argv", original), \
                 patch.object(cli.importlib, "import_module", return_value=SimpleNamespace(main=handler)):
                expected_prog = argparse.ArgumentParser().prog + " smart"
                with self.assertRaises(SystemExit) as raised:
                    cli.main(["smart", "--help"])
                self.assertEqual(raised.exception.code, code)
                self.assertIs(sys.argv, original)
            handler.assert_called_once_with(["--help"], prog=expected_prog)

    def test_unexpected_handler_exception_restores_argv_and_is_not_hidden(self):
        original = ["main.py"]
        with patch.object(sys, "argv", original), \
             patch.object(cli.importlib, "import_module", return_value=SimpleNamespace(main=Mock(side_effect=RuntimeError("fixture error")))):
            with self.assertRaisesRegex(RuntimeError, "fixture error"):
                cli.main(["compare", "file"])
            self.assertIs(sys.argv, original)

    def test_root_help_missing_and_unknown_commands_never_import_handlers(self):
        for arguments, code in ((["--help"], 0), ([], 2), (["unknown"], 2), (["--unknown", "compare"], 2)):
            with self.subTest(arguments=arguments), \
                 patch.object(cli.importlib, "import_module", side_effect=AssertionError("No handler import")) as imported, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(arguments)
                self.assertEqual(raised.exception.code, code)
                imported.assert_not_called()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="unified_cli_fixture_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "한글 입력 🧪.bin"
        self.original = b"ABC\x00" * 1024 + bytes(range(256))
        self.source.write_bytes(self.original)

    def test_smart_roundtrip_both_models_all_modes_has_one_codec_and_no_benchmark(self):
        for kind, algorithm in (("decision_tree", "gzip"), ("random_forest", "zstd")):
            models = self.root / kind
            model_fixture(models, kind, algorithm)
            before = {p.name:p.read_bytes() for p in models.iterdir()}
            for mode in ("archive", "balanced", "fast_access"):
                package = self.root / (kind + "_" + mode)
                output = self.root / (kind + "_" + mode + "_restored")
                with self.subTest(kind=kind, mode=mode), \
                     patch.object(smart, "_git_information", return_value={"commit_hash":None,"worktree_dirty":None}), \
                     patch.object(compare, "compare_file", side_effect=AssertionError("No Compare on Smart path")), \
                     patch.object(compressors, "benchmark_compressor", side_effect=AssertionError("No benchmark")), \
                     patch.object(compressors, "compress_data", wraps=compressors.compress_data) as encode, \
                     patch.object(compressors, "decompress_data", wraps=compressors.decompress_data) as decode, \
                     contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(cli.main(["smart",str(self.source),"--mode",mode,"--model",kind,
                        "--model-dir",str(models),"--output-dir",str(package)]), 0)
                    self.assertTrue(json.loads(stdout.getvalue())["verified"])
                    encode.assert_called_once_with(self.original, algorithm)
                    self.assertEqual(decode.call_count, 1)
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(cli.main(["decompress",str(package),"--output-dir",str(output)]), 0)
                self.assertTrue(json.loads(stdout.getvalue())["verified"])
                self.assertEqual((output / self.source.name).read_bytes(), self.original)
            self.assertEqual(before, {p.name:p.read_bytes() for p in models.iterdir()})
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_existing_outputs_return_failure_unchanged_for_all_commands(self):
        output = self.root / "existing"
        output.mkdir()
        (output / "keep").write_bytes(b"keep")
        cases = [["smart",str(self.source),"--mode","archive","--model","decision_tree"],
                 ["decompress",str(self.root / "package")], ["compare",str(self.source)]]
        for arguments in cases:
            with self.subTest(command=arguments[0]), contextlib.redirect_stderr(io.StringIO()) as stderr, \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(cli.main([*arguments,"--output-dir",str(output)]), 1)
            self.assertIn("already exists", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()}, {"keep":b"keep"})

    def test_invalid_child_options_use_child_usage_and_never_create_output(self):
        output = self.root / "never_created"
        for command in cli.COMMANDS:
            original_argv = sys.argv
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    cli.main([command,str(self.source),"--output-dir",str(output),"--unknown"])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn(" " + command + " ", stderr.getvalue())
            self.assertIs(sys.argv, original_argv)
        self.assertFalse(output.exists())

    def test_compare_partial_failure_exit_and_diagnostics_are_preserved(self):
        output = self.root / "failed_compare"
        with patch.object(compressors, "compress_data", side_effect=OSError("Artificial failure")), \
             contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(cli.main(["compare",str(self.source),"--output-dir",str(output)]), 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "completed_with_failures")
        self.assertIn("incomplete", stderr.getvalue())
        report = json.loads((output / "comparison.json").read_bytes())
        self.assertEqual(report["selections"], [])
        self.assertTrue((output / "timing_repeats.csv").exists())

    def test_fresh_root_help_imports_no_operation_modules(self):
        guard = """import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in {'smart_compress','smart_decompress','compare_compress'} or fullname.startswith('src.') or fullname.split('.')[0] in {'numpy','pandas','sklearn'}:
            raise RuntimeError('Prohibited import: '+fullname)
sys.meta_path.insert(0,Guard())
from main import main
raise SystemExit(main(sys.argv[1:]))
"""
        result = subprocess.run([sys.executable,"-B","-c",guard,"--help"],cwd=smart._ROOT,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertIn(b"smart,decompress,compare", result.stdout)

    def test_fresh_restore_and_compare_import_only_the_selected_operation(self):
        package = self.root / "package"
        original, manifest = package_fixture(package)
        for command in ("decompress", "compare"):
            guard = """import importlib.abc,sys
selected=sys.argv[1]
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'numpy','pandas','sklearn'} or fullname in {
            'smart_compress','src.feature_extractor','src.memory_benchmark','src.memory_validation'} or (fullname=='compare_compress' and selected!='compare') or (fullname=='smart_decompress' and selected!='decompress'):
            raise RuntimeError('Prohibited import: '+fullname)
sys.meta_path.insert(0,Guard())
from main import main
raise SystemExit(main(sys.argv[1:]))
"""
            output = self.root / (command + "_output")
            source = package if command == "decompress" else self.source
            result = subprocess.run([sys.executable,"-B","-c",guard,command,str(source),"--output-dir",str(output)],
                                    cwd=smart._ROOT,capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            if command == "decompress":
                self.assertEqual((output / manifest["original_filename"]).read_bytes(), original)
            else:
                self.assertEqual(json.loads(result.stdout)["status"], "completed")

    def test_fresh_child_help_shows_unified_command_prefix(self):
        for command in cli.COMMANDS:
            result = subprocess.run([sys.executable,"-B","main.py",command,"--help"],cwd=smart._ROOT,capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(("usage: main.py " + command + " ").encode(), result.stdout)
            self.assertIn(b"--output-dir", result.stdout)

    def test_module_execution_help_keeps_command_prefix(self):
        result = subprocess.run([sys.executable,"-B","-m","main","compare","--help"],cwd=smart._ROOT,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"-m main compare", result.stdout)
        self.assertIn(b"--output-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
