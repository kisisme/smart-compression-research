"""Local Tk frontend for explicit Smart, restoration and measured comparison jobs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import uuid

from src.gui_jobs import ALGORITHMS, MODES, ROOT, JobRequest, JobResult, JobRunner

OPERATIONS = {"smart": "Smart 압축", "decompress": "복원", "compare": "실제 비교"}
MODEL_LABELS = {"decision_tree": "Decision Tree", "random_forest": "Random Forest"}
STATUS_LABELS = {"succeeded": "완료 · 검증 통과", "partial": "부분 실패 · 정상 추천 없음",
                 "invalidated": "입력/설정 무효 · 정상 추천 없음", "failed": "처리 실패", "inconclusive": "결과 확인 실패"}


def new_output_name(operation):
    return operation + "_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def output_path(parent, name):
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                *(p + n for p in ("COM", "LPT") for n in "123456789¹²³")}
    if (not name or name in (".", "..") or name.endswith((".", " "))
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or name.split(".", 1)[0].upper() in reserved):
        raise ValueError("새 결과 폴더 이름을 경로 없이 입력하세요. 예약 이름·끝의 점/공백은 사용할 수 없습니다.")
    if not parent.strip() or not Path(parent).expanduser().is_dir():
        raise ValueError("존재하는 출력 부모 폴더를 선택하세요.")
    result = Path(parent).expanduser().absolute() / name
    if result.exists() or result.is_symlink() or result.is_junction():
        raise ValueError("출력 경로가 이미 존재합니다. 새 결과 폴더 이름을 지정하세요.")
    return result


def demo_comparison(smart: JobResult | None, compared: JobResult | None, mode: str):
    """Join already verified results only; no inference, benchmark or file reads."""
    if not smart or not compared or smart.status != "succeeded" or compared.status != "succeeded":
        return None
    if smart.request.operation != "smart" or compared.request.operation != "compare" or smart.request.mode != mode:
        return None
    try:
        predicted, measured = smart.data, compared.data
        provenance = predicted["provenance"]
        config = measured["source_sha256"]["config/experiment_config.json"]
        if (not predicted["input_sha256"] or predicted["input_sha256"] != measured["input_sha256"]
                or provenance["config_sha256"] != config
                or provenance["compression_settings"] != measured["compression_settings"]
                or provenance["selection_weights"] != measured["selection_modes"][mode]
                or provenance["model_kind"] != smart.request.model_kind):
            return None
        selection = next(row for row in measured["selections"] if row["mode"] == mode)
        algorithm = predicted["algorithm"]
        if algorithm not in ALGORITHMS:
            return None
        predicted_score, best = selection["score_" + algorithm], selection["best_score"]
        difference = predicted_score - best
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (predicted_score, best, difference)):
            return None
        return dict(mode=mode, model_kind=smart.request.model_kind, predicted_algorithm=algorithm,
                    actual_best=selection["best_algorithm"], predicted_score=predicted_score, best_score=best,
                    score_difference=difference, input_sha256=predicted["input_sha256"],
                    model_sha256=provenance["model_sha256"])
    except (KeyError, TypeError, StopIteration):
        return None


def display(value):
    if value is None:
        return "—"
    if type(value) is float:
        return format(value, ".7g")
    return str(value)


class OperationPane:
    def __init__(self, app, operation):
        self.app, self.operation = app, operation
        self.frame = ttk.Frame(app.notebook, padding=16)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)
        self.last_result = None
        self.info_after = None
        self.source = tk.StringVar()
        self.parent = tk.StringVar(value=str(ROOT / "data/temp"))
        self.name = tk.StringVar(value=new_output_name(operation))
        self.mode = tk.StringVar()
        self.model = tk.StringVar()
        self.models = tk.StringVar()
        self.info = tk.StringVar(value="입력을 선택하세요. 파일 정보는 확장자·크기로 표시합니다.")
        self.summary = tk.StringVar(value="아직 실행하지 않았습니다.")
        self.best = tk.StringVar()
        self.demo = tk.StringVar(value="동일 파일·설정·사용 목적의 Smart 결과가 있으면 예측과 실측을 대조합니다.")
        self.view_mode = tk.StringVar(value="archive")
        self.controls = []
        card = ttk.LabelFrame(self.frame, text="입력과 새 출력", padding=14)
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        self._path_row(card, 0, "압축 결과 폴더" if operation == "decompress" else "입력 파일", self.source, self.browse_input)
        ttk.Label(card, textvariable=self.info, style="Muted.TLabel", wraplength=600).grid(row=1, column=1, columnspan=2, sticky="w", pady=(0, 9))
        self._path_row(card, 2, "출력 부모 폴더", self.parent, self.browse_parent)
        self._path_row(card, 3, "새 결과 폴더", self.name, self.fresh_name, "새 이름")
        if operation == "smart":
            choices = ttk.Frame(card)
            choices.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(6, 6))
            ttk.Label(choices, text="사용 목적").pack(side="left")
            self.mode_box = ttk.Combobox(choices, textvariable=self.mode, values=MODES, state="readonly", width=17)
            self.mode_box.pack(side="left", padx=(10, 24))
            ttk.Label(choices, text="모델").pack(side="left")
            self.model_box = ttk.Combobox(choices, textvariable=self.model, values=tuple(MODEL_LABELS.values()), state="readonly", width=20)
            self.model_box.pack(side="left", padx=10)
            self.controls.extend(((self.mode_box, "readonly"), (self.model_box, "readonly")))
            self._path_row(card, 5, "모델 폴더 (선택)", self.models, self.browse_models)
            ttk.Label(card, text="비워 두면 프로젝트 Pilot 모델을 사용합니다. 다른 폴더는 직접 만든 신뢰할 수 있는 모델만 선택하세요.",
                      style="Muted.TLabel", wraplength=600).grid(row=6, column=1, columnspan=2, sticky="w", pady=(2, 0))
        actions = ttk.Frame(self.frame)
        actions.grid(row=1, column=0, sticky="ew", pady=(12, 10))
        self.start_button = ttk.Button(actions, text={"smart":"예측해 압축", "decompress":"검증해 복원", "compare":"네 알고리즘 실제 비교"}[operation],
                                       style="Accent.TButton", command=lambda: app.start(operation))
        self.start_button.pack(side="right")
        self.controls.append((self.start_button, "normal"))
        self.details_button = ttk.Button(actions, text="실행 기록", command=lambda: app.details(operation), state="disabled")
        self.details_button.pack(side="left")
        self.copy_button = ttk.Button(actions, text="결과 경로 복사", command=lambda: app.copy_path(operation), state="disabled")
        self.copy_button.pack(side="left", padx=8)
        if operation == "smart":
            self.restore_button = ttk.Button(actions, text="이 결과 복원", command=app.prepare_restore, state="disabled")
            self.restore_button.pack(side="left", padx=(8, 0))
            self.compare_button = ttk.Button(actions, text="사용한 파일 실제 비교", command=app.prepare_compare, state="disabled")
            self.compare_button.pack(side="left", padx=8)
        self.summary_label = ttk.Label(self.frame, textvariable=self.summary, style="Result.TLabel", wraplength=850)
        self.summary_label.grid(row=2, column=0, sticky="ew", pady=(0, 9))
        table = ttk.Frame(self.frame)
        table.grid(row=3, column=0, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ("algorithm", "verified", "size", "ratio", "compress", "decompress", "score", "status") if operation == "compare" else ("field", "value")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=9)
        headings = ("알고리즘", "복원 검증", "압축 bytes", "압축률 ↓", "압축 ms ↓", "해제 ms ↓", "점수 ↓", "상태") if operation == "compare" else ("실행 당시 항목", "실제 값")
        for i, (column, heading) in enumerate(zip(columns, headings)):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=(230 if i == 0 else 700) if operation != "compare" else (100 if i != 7 else 120),
                             minwidth=85, stretch=operation != "compare" or i == 7)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        if operation == "compare":
            view = ttk.Frame(self.frame)
            view.grid(row=4, column=0, sticky="ew", pady=(9, 5))
            ttk.Label(view, text="점수를 표시할 사용 목적").pack(side="left")
            self.view_box = ttk.Combobox(view, textvariable=self.view_mode, values=MODES, state="readonly", width=18)
            self.view_box.pack(side="left", padx=10)
            self.controls.append((self.view_box, "readonly"))
            ttk.Label(self.frame, textvariable=self.best, wraplength=850).grid(row=5, column=0, sticky="w", pady=3)
            ttk.Label(self.frame, textvariable=self.demo, style="Muted.TLabel", wraplength=850).grid(row=6, column=0, sticky="w", pady=3)
            self.view_mode.trace_add("write", lambda *_: app.refresh_comparison())
        self.source.trace_add("write", lambda *_: app.input_changed(operation))
        if operation == "smart":
            for value in (self.mode, self.model, self.models):
                value.trace_add("write", lambda *_: app.invalidate_demo())

    def _path_row(self, parent, row, label, variable, callback, button="찾기"):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        action = ttk.Button(parent, text=button, command=callback)
        action.grid(row=row, column=2, padx=(10, 0), pady=5)
        self.controls.extend(((entry, "normal"), (action, "normal")))

    def browse_input(self):
        value = (filedialog.askdirectory(parent=self.app.root, title="압축 결과 폴더 선택") if self.operation == "decompress"
                 else filedialog.askopenfilename(parent=self.app.root, title="원본 파일 선택"))
        if value:
            self.source.set(value)

    def browse_parent(self):
        value = filedialog.askdirectory(parent=self.app.root, title="출력 부모 폴더 선택")
        if value:
            self.parent.set(value)

    def browse_models(self):
        value = filedialog.askdirectory(parent=self.app.root, title="직접 만든 신뢰할 수 있는 모델 폴더")
        if value:
            self.models.set(value)

    def fresh_name(self):
        self.name.set(new_output_name(self.operation))


class CompressionApp:
    def __init__(self, root: tk.Tk, *, runner=None, dialogs=messagebox):
        self.root, self.runner, self.dialogs = root, runner or JobRunner(), dialogs
        self.active = None
        self.smart_result = None
        self._programmatic = False
        self._closed = False
        self.root.title("Smart Compression — 압축·복원·비교")
        self.root.geometry("1120x840")
        self.root.minsize(960, 720)
        self.root.configure(background="#f3f6fa")
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("맑은 고딕", 10), background="#f3f6fa", foreground="#182d42")
        style.configure("TButton", padding=(12, 7))
        style.configure("Accent.TButton", background="#126c70", foreground="white", font=("맑은 고딕", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#0c5559"), ("disabled", "#b8c8cc")])
        style.configure("Muted.TLabel", foreground="#566979", font=("맑은 고딕", 9))
        style.configure("Title.TLabel", font=("맑은 고딕", 23, "bold"))
        style.configure("Result.TLabel", font=("맑은 고딕", 11, "bold"))
        style.configure("Success.TLabel", foreground="#11644e", font=("맑은 고딕", 11, "bold"))
        style.configure("Error.TLabel", foreground="#a32b36", font=("맑은 고딕", 11, "bold"))
        style.configure("Treeview", rowheight=29, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("맑은 고딕", 10, "bold"), padding=7)
        style.configure("TNotebook.Tab", padding=(20, 10))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(root, padding=(24, 17, 24, 10))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Smart Compression", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="무손실 압축 선택·검증  |  공식 3지표 · memory는 참고 지표로 보존", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=20)
        self.panes = {}
        for operation, title in OPERATIONS.items():
            pane = OperationPane(self, operation)
            self.panes[operation] = pane
            self.notebook.add(pane.frame, text=title)
        footer = ttk.Frame(root, padding=(24, 10, 24, 14))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.state_text = tk.StringVar(value="준비 · 작업을 선택하고 입력과 새 출력 경로를 지정하세요.")
        ttk.Label(footer, textvariable=self.state_text).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=210)
        self.progress.grid(row=0, column=1, sticky="e")
        ttk.Label(footer, text="모델 출력은 보정된 정답 확률이 아닙니다. Pilot의 최빈 baseline 대비 개선은 확인되지 않았습니다.",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self._after = self.root.after(100, self.poll_results)
        self._sync_actions()

    def input_changed(self, operation):
        if not self._programmatic:
            self.invalidate_demo()
        pane = self.panes.get(operation)
        if pane:
            if pane.info_after:
                self.root.after_cancel(pane.info_after)
            pane.info_after = self.root.after(200, lambda: self.refresh_info(operation))

    def refresh_info(self, operation):
        pane = self.panes[operation]
        pane.info_after = None
        try:
            path = Path(pane.source.get()).expanduser()
            if not pane.source.get().strip():
                raise ValueError("No input")
            if operation == "decompress":
                pane.info.set(f"{path.name} · 압축 결과 폴더" if path.is_dir() else "존재하는 압축 결과 폴더를 선택하세요.")
            else:
                stat = path.stat()
                pane.info.set(f"{path.name} · {stat.st_size:,} bytes · {path.suffix or '확장자 없음'}" if path.is_file() else "파일을 선택하세요.")
        except (OSError, ValueError):
            pane.info.set("존재하는 입력을 선택하세요. 큰 파일은 메모리에 읽어 처리합니다.")

    def invalidate_demo(self):
        if self._programmatic:
            return
        self.smart_result = None
        self.refresh_comparison()
        self._sync_actions()

    def _request(self, operation):
        pane = self.panes[operation]
        value = pane.source.get()
        if not value.strip():
            raise ValueError("입력을 선택하세요.")
        source = Path(value).expanduser().absolute()
        if operation == "decompress":
            if not source.is_dir() or not (source / "manifest.json").is_file():
                raise ValueError("manifest.json이 있는 압축 결과 폴더를 선택하세요.")
        elif not source.is_file() or source.stat().st_size <= 0:
            raise ValueError("비어 있지 않은 입력 파일을 선택하세요.")
        output = output_path(pane.parent.get(), pane.name.get())
        if operation == "decompress" and output.resolve().is_relative_to(source.resolve()):
            raise ValueError("복원 출력은 입력 package 밖에 지정하세요.")
        options = {}
        if operation == "smart":
            kind = next((k for k,v in MODEL_LABELS.items() if v == pane.model.get()), None)
            if pane.mode.get() not in MODES or not kind:
                raise ValueError("사용 목적과 모델을 명시적으로 선택하세요.")
            models = pane.models.get()
            if models.strip() and not Path(models).expanduser().is_dir():
                raise ValueError("존재하는 모델 폴더를 선택하거나 기본 모델을 사용하도록 비워 두세요.")
            options = dict(mode=pane.mode.get(), model_kind=kind, model_dir=Path(models).expanduser() if models.strip() else None)
        return JobRequest(operation, source, output, **options)

    def start(self, operation):
        if self.active is not None or self.runner.busy:
            return False
        pane = self.panes[operation]
        pane.last_result = None
        pane.tree.delete(*pane.tree.get_children())
        pane.best.set("")
        pane.summary_label.configure(style="Result.TLabel")
        if operation == "smart":
            self.smart_result = None
        try:
            request = self._request(operation)
            if operation == "compare" and self.smart_result and request.input_path.resolve() != self.smart_result.request.input_path.resolve():
                self.smart_result = None
            job_id = self.runner.submit(request)
        except (OSError, ValueError, RuntimeError) as exc:
            self.smart_result = None
            pane.summary.set("실행 전 확인 필요 · " + str(exc))
            pane.summary_label.configure(style="Error.TLabel")
            self.state_text.set("실행하지 않았습니다. 입력과 새 출력 경로를 확인하세요.")
            self.refresh_comparison()
            self._sync_actions()
            self.dialogs.showerror("입력 확인", str(exc), parent=self.root)
            return False
        self.active = (job_id, operation, request)
        pane.summary.set(OPERATIONS[operation] + " 실행 중 · 완료율은 추정하지 않습니다.")
        self.state_text.set(OPERATIONS[operation] + " 실행 중 · 입력과 중복 실행이 잠겨 있습니다.")
        self.notebook.select(pane.frame)
        self._set_busy(True, operation)
        self.progress.start(12)
        if operation == "compare":
            for algorithm in ALGORITHMS:
                pane.tree.insert("", "end", values=(algorithm,"—","—","—","—","—","—","결과 대기"))
        self.refresh_comparison()
        return True

    def _set_busy(self, busy, operation=None):
        for name, pane in self.panes.items():
            self.notebook.tab(pane.frame, state="disabled" if busy and name != operation else "normal")
            for control, normal in pane.controls:
                control.configure(state="disabled" if busy else normal)
        self._sync_actions()

    def _sync_actions(self):
        busy = self.active is not None or self.runner.busy
        for pane in self.panes.values():
            result = pane.last_result
            pane.details_button.configure(state="normal" if result and not busy else "disabled")
            pane.copy_button.configure(state="normal" if result and result.return_code is not None and not busy else "disabled")
        smart = self.panes.get("smart")
        if smart:
            success = smart.last_result and smart.last_result.status == "succeeded"
            smart.restore_button.configure(state="normal" if success and not busy else "disabled")
            smart.compare_button.configure(state="normal" if self.smart_result and not busy else "disabled")

    def poll_results(self):
        if self._closed:
            return
        while True:
            result = self.runner.poll()
            if result is None:
                break
            if self.active is None or result.job_id != self.active[0]:
                continue
            operation = self.active[1]
            self.active = None
            self.progress.stop()
            pane = self.panes[operation]
            pane.last_result = result
            if result.status == "succeeded" and operation == "smart":
                self.smart_result = result
            elif result.status != "succeeded":
                self.smart_result = None
            self._set_busy(False)
            self.render_result(operation)
            self.refresh_comparison()
            self._sync_actions()
        self._after = self.root.after(100, self.poll_results)

    def render_result(self, operation):
        pane = self.panes[operation]
        result = pane.last_result
        if not result:
            return
        pane.tree.delete(*pane.tree.get_children())
        normal = result.status == "succeeded"
        state = STATUS_LABELS.get(result.status, "알 수 없는 결과 상태")
        pane.summary.set(state + (" · 실행 로그 저장 경고" if result.log_error else ""))
        pane.summary_label.configure(style="Success.TLabel" if normal and not result.log_error else "Error.TLabel")
        self.state_text.set(OPERATIONS[operation] + " · " + state)
        data = result.data or {}
        if operation == "compare":
            self.refresh_comparison()
            return
        if not normal:
            pane.tree.insert("", "end", values=("오류", result.message))
            pane.tree.insert("", "end", values=("종료 코드", display(result.return_code)))
        elif operation == "smart":
            values = [("선택 알고리즘", data["algorithm"]), ("사용 목적 / 모델", f"{result.request.mode} / {MODEL_LABELS[result.request.model_kind]}"),
                ("원본 bytes", data["original_size"]), ("압축 bytes", data["compressed_size"]), ("압축률 (작을수록 유리)", data["compression_ratio"]),
                ("복원 검증", "통과"), ("모델 출력 (보정되지 않음)", data["prediction_confidence"])]
            values.extend(("특징 · " + key, value) for key, value in data["features"].items())
            for key,value in values:
                pane.tree.insert("", "end", values=(key,display(value)))
        else:
            for key,value in [("복원 파일",data["restored_file"]),("복원 bytes",data["restored_size"]),
                              ("알고리즘",data["algorithm"]),("복원 SHA-256",data["restored_sha256"]),("크기·해시 검증","통과")]:
                pane.tree.insert("", "end", values=(key,display(value)))
        pane.tree.insert("", "end", values=("요청 출력 경로",str(result.request.output_dir)))
        if result.log_error:
            pane.tree.insert("", "end", values=("로그 저장 오류",result.log_error))

    def refresh_comparison(self):
        pane = self.panes.get("compare")
        if not pane:
            return
        result = pane.last_result
        pane.best.set("")
        pane.demo.set("동일 파일·설정·사용 목적의 Smart 결과가 없습니다. 필요하면 Smart 압축부터 명시적으로 실행하세요.")
        if not result:
            return
        data = result.data or {}
        mode = pane.view_mode.get()
        normal = result.status == "succeeded"
        pane.tree.delete(*pane.tree.get_children())
        selection = next((r for r in data.get("selections",[]) if r.get("mode") == mode), None) if normal else None
        for row in data.get("measurements",[]):
            verified = "통과" if row.get("verified") is True else "실패"
            score = selection.get("score_"+row["algorithm"]) if selection else None
            pane.tree.insert("", "end", values=(row.get("algorithm"),verified,display(row.get("compressed_size")),
                display(row.get("compression_ratio")),display(row.get("compression_time_ms")),display(row.get("decompression_time_ms")),
                display(score),row.get("status","확인 불가")))
        if not data:
            pane.tree.insert("", "end", values=("결과 확인 실패","—","—","—","—","—","—",result.message))
        if normal:
            pane.best.set("실행 당시 mode별 best: " + "   |   ".join(f"{r['mode']}: {r['best_algorithm']}" for r in data["selections"]))
        else:
            pane.best.set("정상 best를 표시하지 않습니다. 상세 기록에서 오류·부분 산출물 위치를 확인하세요.")
        joined = demo_comparison(self.smart_result, result, mode)
        if joined:
            pane.demo.set(f"동일 입력 Demo · {MODEL_LABELS[joined['model_kind']]} / {mode}: 예측 {joined['predicted_algorithm']} → "
                          f"실측 best {joined['actual_best']} · 이 파일의 점수 차이 {display(joined['score_difference'])} (모델 평가 아님)")

    def prepare_compare(self):
        if not self.smart_result or self.active or self.runner.busy:
            return
        pane = self.panes["compare"]
        self._programmatic = True
        try:
            pane.source.set(str(self.smart_result.request.input_path))
            pane.view_mode.set(self.smart_result.request.mode)
            pane.fresh_name()
        finally:
            self._programmatic = False
        self.notebook.select(pane.frame)
        self.refresh_comparison()

    def prepare_restore(self):
        result = self.panes["smart"].last_result
        if not result or result.status != "succeeded" or self.active or self.runner.busy:
            return
        pane = self.panes["decompress"]
        self._programmatic = True
        try:
            pane.source.set(str(result.request.output_dir))
            pane.fresh_name()
        finally:
            self._programmatic = False
        self.notebook.select(pane.frame)

    def details(self, operation):
        result = self.panes[operation].last_result
        if not result:
            return
        window = tk.Toplevel(self.root)
        window.title("실행 기록 — " + OPERATIONS[operation])
        window.geometry("920x600")
        text = ScrolledText(window, wrap="word", font=("맑은 고딕",10))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        data = {k:v for k,v in result.as_dict().items() if k not in ("stdout_base64","stderr_base64")}
        text.insert("1.0",json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2))
        text.configure(state="disabled")

    def copy_path(self, operation):
        result = self.panes[operation].last_result
        if result:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(result.request.output_dir))
            self.state_text.set("요청 출력 경로를 복사했습니다.")

    def request_close(self):
        if self.active is not None or self.runner.busy:
            self.dialogs.showinfo("작업 진행 중", "작업을 중단하지 않습니다. 완료된 뒤 창을 닫아주세요.", parent=self.root)
            return False
        self._closed = True
        self.root.after_cancel(self._after)
        for pane in self.panes.values():
            if pane.info_after:
                self.root.after_cancel(pane.info_after)
        self.root.destroy()
        return True


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(arguments)
    root = tk.Tk()
    CompressionApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
