"""Launch the unmodified GUI and observe native-input QA; never invoke controls.

All interaction is performed separately through the Computer Use plugin. The
observer only records widget values/results, geometry, callbacks and input hashes.
README copy is a smoke input, never an unseen research candidate.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tkinter as tk
import traceback

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gui_app import CompressionApp
from src.gui_jobs import JobRunner


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.absolute()
    if output.parent != ROOT / "data/temp":
        parser.error("Use a fresh direct child of data/temp")
    output.mkdir(exist_ok=False)
    fixture = output / ("긴 경로 확인 " * 5 + "원본") / "한글 공백 & 실제 GUI 입력 🧪.md"
    fixture.parent.mkdir()
    fixture.write_bytes((ROOT / "README.md").read_bytes())
    protected = json.loads((ROOT / "data/results/real_unseen/synthetic_overlap_20261027_01/protected_after.json").read_bytes())
    for path in (ROOT / "gui_app.py", Path(__file__), ROOT / "README.md", fixture):
        protected[path.relative_to(ROOT).as_posix()] = sha(path)
    for rel, digest in protected.items():
        if sha(ROOT / rel) != digest:
            raise ValueError("Protected file changed: " + rel)
    save(output / "protected_before.json", protected)
    root = tk.Tk()
    app = CompressionApp(root, runner=JobRunner(log_root=output / "sessions"))
    errors, jobs = [], {}
    heartbeat = [0]
    def callback_error(*exc):
        errors.append("".join(traceback.format_exception(*exc)))
    root.report_callback_exception = callback_error
    last = [None]
    def observe():
        heartbeat[0] += 1
        panes = {}
        for key, pane in app.panes.items():
            result = pane.last_result
            if result:
                jobs[result.job_id] = result.as_dict()
            panes[key] = dict(source=pane.source.get(), parent=pane.parent.get(), name=pane.name.get(),
                              mode=pane.mode.get(), model=pane.model.get(), summary=pane.summary.get(),
                              demo=pane.demo.get(), best=pane.best.get(), view_mode=pane.view_mode.get(),
                              tree=[pane.tree.item(i, "values") for i in pane.tree.get_children()],
                              start_state=str(pane.start_button.cget("state")))
        state = dict(geometry=root.geometry(), selected_tab=str(app.notebook.select()),
                     active=str(app.active), runner_busy=app.runner.busy, panes=panes, footer=app.state_text.get())
        if state != last[0]:
            with (output / "observations.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(dict(at_utc=datetime.now(timezone.utc).isoformat(), heartbeat=heartbeat[0], **state), ensure_ascii=False)+"\n")
            last[0] = state
        root.after(500, observe)
    root.after(100, observe)
    save(output / "launch.json", dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
         head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         python=sys.version, platform=platform.platform(), fixture_path=str(fixture), fixture_sha256=sha(fixture),
         tk_patchlevel=root.tk.call("info", "patchlevel"), tk_scaling=float(root.tk.call("tk", "scaling")),
         pixels_per_inch=root.winfo_fpixels("1i"), screen_pixels=[root.winfo_screenwidth(), root.winfo_screenheight()],
         scope="Read-only Tk observer; native UI actions must use Computer Use; README smoke input only"))
    root.mainloop()
    after = {rel: sha(ROOT / rel) for rel in protected}
    save(output / "protected_after.json", after)
    save(output / "completed.json", dict(closed_at_utc=datetime.now(timezone.utc).isoformat(),
         callback_errors=errors, observed_heartbeat_ticks=heartbeat[0], jobs=list(jobs.values()),
         protected_unchanged=after == protected, final_state=last[0],
         all_user_actions_external=True))
    if after != protected or errors:
        raise RuntimeError("Native QA preservation/callback failure")


if __name__ == "__main__":
    main()
