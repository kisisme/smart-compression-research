"""Real Tk widgets with controlled queue fixtures, not research measurements.

No operating-system input automation; mapped-window/backend integration is logged
separately. These tests verify the event callbacks and visible widget state.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock

from gui_app import CompressionApp, MODEL_LABELS, demo_comparison, new_output_name, output_path
from src.gui_jobs import ALGORITHMS, MODES, JobRequest, JobResult


def result_fixture(request, job_id="job1", status="succeeded"):
    """Artificial response values for presentation contracts only."""
    weights = dict(ratio=1.0, compression=0.0, decompression=0.0)
    if request.operation == "smart":
        data = dict(algorithm="gzip", input_sha256="a" * 64, original_size=100, compressed_size=50,
            compression_ratio=.5, prediction_confidence=.75, features={"file_size":100},
            provenance=dict(config_sha256="c"*64, compression_settings={"gzip":6}, selection_weights=weights,
                            model_kind=request.model_kind, model_sha256="m"*64))
    elif request.operation == "decompress":
        data = dict(algorithm="gzip", restored_file="인위적 fixture.bin", restored_size=100, restored_sha256="a"*64)
    else:
        data = dict(input_sha256="a"*64,source_sha256={"config/experiment_config.json":"c"*64},
            compression_settings={"gzip":6},selection_modes={m:weights for m in MODES},
            measurements=[dict(algorithm=a,verified=True,compressed_size=50,compression_ratio=.5,
                compression_time_ms=.1,decompression_time_ms=.2,status="ok") for a in ALGORITHMS],
            selections=[dict(mode=m,best_algorithm="bz2",best_score=0.,score_gzip=.25,score_bz2=0.,score_lzma=.5,score_zstd=1.) for m in MODES])
    if status != "succeeded":
        if request.operation == "compare" and status in ("partial", "invalidated"):
            data["selections"] = []
            data["measurements"][0].update(verified=False,status="failed",compressed_size=None,
                compression_ratio=None,compression_time_ms=None,decompression_time_ms=None)
        else:
            data = None
    return JobResult(job_id,request,status,"Artificial test message",("fixture",),"fixture start","fixture end",
                     return_code=0 if status == "succeeded" else 1,data=data)


class FakeRunner:
    def __init__(self):
        self.busy, self.requests, self.results = False, [], []

    def submit(self, request):
        if self.busy:
            raise RuntimeError("Busy")
        self.requests.append(request)
        self.busy = True
        return "job" + str(len(self.requests))

    def poll(self):
        return self.results.pop(0) if self.results else None

    def wait(self, *args, **kwargs):
        raise AssertionError("Tk callbacks must not wait")


class JoinTests(unittest.TestCase):
    def setUp(self):
        source, output = Path("fixture-input"), Path("fixture-output")
        self.smart = result_fixture(JobRequest("smart",source,output,mode="archive",model_kind="decision_tree"))
        self.compared = result_fixture(JobRequest("compare",source,output))

    def test_join_uses_measured_score_for_prediction(self):
        joined = demo_comparison(self.smart,self.compared,"archive")
        self.assertEqual((joined["predicted_algorithm"],joined["actual_best"],joined["score_difference"]),("gzip","bz2",.25))
        self.assertIsNone(demo_comparison(self.smart,self.compared,"balanced"))

    def test_join_rejects_input_config_weights_settings_model_and_status_changes(self):
        for change in ("input", "config", "weights", "settings", "model", "bad_score", "missing"):
            with self.subTest(change=change):
                smart = replace(self.smart,data=deepcopy(self.smart.data))
                if change == "input": smart.data["input_sha256"] = "different"
                if change == "config": smart.data["provenance"]["config_sha256"] = "different"
                if change == "weights": smart.data["provenance"]["selection_weights"] = {}
                if change == "settings": smart.data["provenance"]["compression_settings"] = {}
                if change == "model": smart.data["provenance"]["model_kind"] = "random_forest"
                if change == "bad_score": smart.data["algorithm"] = "unknown"
                if change == "missing": del smart.data["provenance"]["model_sha256"]
                self.assertIsNone(demo_comparison(smart,self.compared,"archive"))
        for status in ("partial","failed","invalidated","inconclusive"):
            self.assertIsNone(demo_comparison(self.smart,replace(self.compared,status=status),"archive"))

    def test_join_rejects_nonfinite_negative_or_boolean_scores(self):
        for score in (float("nan"),float("inf"),-.1,True):
            compared = replace(self.compared,data=deepcopy(self.compared.data))
            compared.data["selections"][0]["score_gzip"] = score
            self.assertIsNone(demo_comparison(self.smart,compared,"archive"))


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tk_gui_artificial_")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.source = self.directory / "한글 🧪 & input.bin"
        self.source.write_bytes(b"Artificial fixture input")
        self.root = tk.Tk()
        self.root.withdraw()
        self.runner = FakeRunner()
        self.dialogs = Mock()
        self.app = CompressionApp(self.root,runner=self.runner,dialogs=self.dialogs)
        self.addCleanup(self.close)
        for pane in self.app.panes.values():
            pane.parent.set(str(self.directory))
        self.fill()

    def close(self):
        self.runner.busy = False
        self.app.active = None
        if not self.app._closed:
            self.app.request_close()

    def fill(self, operation="smart"):
        pane = self.app.panes[operation]
        pane.source.set(str(self.source))
        if operation == "smart":
            pane.mode.set("archive")
            pane.model.set(MODEL_LABELS["decision_tree"])
        return pane

    def complete(self, status="succeeded", **kwargs):
        job_id, operation, request = self.app.active
        result = replace(result_fixture(request,job_id,status),**kwargs)
        self.runner.busy = False
        self.runner.results.append(result)
        # Use the scheduled Tk poll callback, not a direct call that duplicates timers.
        self.root.after_cancel(self.app._after)
        self.app.poll_results()
        return result

    def rows(self, operation):
        tree = self.app.panes[operation].tree
        return [tree.item(i,"values") for i in tree.get_children()]

    def test_explicit_request_locks_all_controls_and_rejects_duplicate_and_close(self):
        self.assertEqual(self.runner.requests,[])
        self.assertTrue(self.app.start("smart"))
        request = self.runner.requests[0]
        self.assertEqual((request.mode,request.model_kind),("archive","decision_tree"))
        self.assertEqual(request.input_path,self.source)
        self.assertFalse(self.app.start("compare"))
        self.assertEqual(len(self.runner.requests),1)
        for name,pane in self.app.panes.items():
            self.assertTrue(all(str(control.cget("state")) == "disabled" for control,_ in pane.controls))
            if name != "smart": self.assertEqual(self.app.notebook.tab(pane.frame,"state"),"disabled")
        self.assertFalse(self.app.request_close())
        self.dialogs.showinfo.assert_called_once()
        self.assertTrue(self.root.winfo_exists())
        self.complete()
        self.assertEqual(str(self.app.panes["smart"].mode_box.cget("state")),"readonly")
        self.assertEqual(str(self.app.panes["smart"].start_button.cget("state")),"normal")
        self.assertTrue(any(row[0] == "선택 알고리즘" and row[1] == "gzip" for row in self.rows("smart")))

    def test_transfers_only_prepare_and_explicit_compare_joins(self):
        self.app.start("smart")
        smart = self.complete()
        self.app.prepare_restore()
        self.assertEqual(self.app.panes["decompress"].source.get(),str(smart.request.output_dir))
        self.app.prepare_compare()
        pane = self.app.panes["compare"]
        self.assertEqual(pane.source.get(),str(self.source))
        self.assertEqual(len(self.runner.requests),1)
        self.assertTrue(self.app.start("compare"))
        self.complete()
        self.assertIn("예측 gzip",pane.demo.get())
        self.assertIn("실측 best bz2",pane.demo.get())
        self.assertEqual(len(self.rows("compare")),4)
        pane.view_mode.set("balanced")
        self.assertNotIn("예측 gzip",pane.demo.get())
        pane.view_mode.set("archive")
        self.assertIn("예측 gzip",pane.demo.get())
        self.app.panes["smart"].model.set(MODEL_LABELS["random_forest"])
        self.assertIsNone(self.app.smart_result)
        self.assertNotIn("예측 gzip",pane.demo.get())

    def test_input_and_mode_edits_invalidate_comparison(self):
        for edit in (lambda p:p.mode.set("balanced"),lambda p:p.source.set(str(self.source)+"missing"),
                     lambda p:p.models.set(str(self.directory))):
            pane = self.fill()
            self.app.start("smart")
            self.complete()
            edit(pane)
            self.assertIsNone(self.app.smart_result)

    def test_partial_compare_hides_scores_and_best_and_clears_demo(self):
        self.app.start("smart")
        self.complete()
        self.app.prepare_compare()
        self.app.start("compare")
        self.complete("partial")
        pane = self.app.panes["compare"]
        self.assertEqual(pane.summary_label.cget("style"),"Error.TLabel")
        self.assertIsNone(self.app.smart_result)
        self.assertTrue(all(row[6] == "—" for row in self.rows("compare")))
        self.assertIn("정상 best를 표시하지",pane.best.get())
        self.assertNotIn("실측 best",pane.demo.get())

    def test_failed_and_inconclusive_jobs_show_error_and_unlock(self):
        for status in ("failed","inconclusive","invalidated"):
            self.app.start("smart")
            self.complete(status)
            pane = self.app.panes["smart"]
            self.assertEqual(pane.summary_label.cget("style"),"Error.TLabel")
            self.assertEqual(self.rows("smart")[0],("오류","Artificial test message"))
            self.assertEqual(str(pane.restore_button.cget("state")),"disabled")
            self.assertEqual(str(pane.start_button.cget("state")),"normal")

    def test_log_failure_is_warning_without_hiding_valid_success(self):
        self.app.start("smart")
        self.complete(log_error="Artificial log write failure")
        pane = self.app.panes["smart"]
        self.assertIn("로그 저장 경고",pane.summary.get())
        self.assertEqual(pane.last_result.status,"succeeded")
        self.assertEqual(str(pane.restore_button.cget("state")),"normal")
        self.assertTrue(any(row[0] == "로그 저장 오류" for row in self.rows("smart")))

    def test_missing_choices_and_existing_output_block_before_submit(self):
        pane = self.app.panes["smart"]
        pane.mode.set("")
        self.assertFalse(self.app.start("smart"))
        pane.mode.set("archive")
        target = self.directory / pane.name.get()
        target.mkdir()
        marker = target / "preserve.bin"
        marker.write_bytes(b"must remain")
        self.assertFalse(self.app.start("smart"))
        self.assertEqual(marker.read_bytes(),b"must remain")
        self.assertEqual(self.runner.requests,[])
        self.assertEqual(self.dialogs.showerror.call_count,2)

    def test_restore_rejects_missing_manifest_or_output_inside_package(self):
        pane = self.app.panes["decompress"]
        pane.source.set(str(self.directory))
        self.assertFalse(self.app.start("decompress"))
        (self.directory / "manifest.json").write_text("{}")
        self.assertFalse(self.app.start("decompress"))
        self.assertEqual(self.runner.requests,[])

    def test_stale_queue_result_does_not_unlock_active_job(self):
        self.app.start("smart")
        self.runner.results.append(result_fixture(self.runner.requests[0],"stale"))
        self.root.after_cancel(self.app._after)
        self.app.poll_results()
        self.assertIsNotNone(self.app.active)
        self.assertIsNone(self.app.panes["smart"].last_result)
        self.complete()

    def test_idle_close_destroys_root(self):
        self.assertTrue(self.app.request_close())
        self.assertTrue(self.app._closed)

    def test_mapped_window_minimum_size_keeps_actions_and_tables_inside(self):
        self.root.geometry("960x720")
        self.root.deiconify()
        for pane in self.app.panes.values():
            self.app.notebook.select(pane.frame)
            self.root.update()
            self.assertTrue(pane.frame.winfo_ismapped())
            for widget in (pane.start_button,pane.tree,pane.summary_label):
                self.assertGreater(widget.winfo_height(),20)
                self.assertGreaterEqual(widget.winfo_rootx(),self.root.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),self.root.winfo_rootx()+self.root.winfo_width())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height())


class PathTests(unittest.TestCase):
    def test_portable_new_directory_and_unique_names(self):
        with tempfile.TemporaryDirectory(prefix="tk_paths_artificial_") as name:
            parent = Path(name)
            self.assertEqual(output_path(name,"한글 결과"),parent / "한글 결과")
            for invalid in ("", ".", "..", "../escape", "a/b", "a\\b", "trailing.","space ","CON","NUL.txt","COM¹", "bad?", "bad\n"):
                with self.subTest(name=invalid), self.assertRaises(ValueError):
                    output_path(name,invalid)
            (parent / "exists").mkdir()
            with self.assertRaises(ValueError): output_path(name,"exists")
            with self.assertRaises(ValueError): output_path("","new")
        self.assertNotEqual(new_output_name("smart"),new_output_name("smart"))


if __name__ == "__main__":
    unittest.main()
