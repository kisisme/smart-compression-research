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


def configure_theme(root):
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    font = ("맑은 고딕", 10)
    bold = (*font, "bold")
    ink, muted, navy = "#172d43", "#50657a", "#142b43"
    surface, border, blue = "#ffffff", "#cdd9e4", "#215dc2"
    style.configure(".", font=font, background=surface, foreground=ink)
    style.configure("Page.TFrame", background="#edf2f7")
    style.configure("Header.TFrame", background=navy)
    style.configure("Brand.TLabel", background=navy, foreground="white", font=("Segoe UI", 22, "bold"))
    style.configure("Header.TLabel", background=navy, foreground="#c0d4ea", font=font)
    style.configure("Section.TLabel", font=("맑은 고딕", 16, "bold"))
    style.configure("Muted.TLabel", foreground=muted, font=("맑은 고딕", 9))
    style.configure("Field.TLabel", foreground=ink, font=bold)
    style.configure("TButton", padding=(9, 5), background="#eff4f8", borderwidth=0, relief="flat")
    style.map("TButton", background=[("disabled", "#f3f5f7"), ("pressed", "#d3dfed"), ("active", "#e0eaf4")],
              foreground=[("disabled", "#718095")])
    style.configure("Accent.TButton", background=blue, foreground="white", font=bold, padding=(16, 8))
    style.map("Accent.TButton", background=[("disabled", "#ccd7e3"), ("pressed", "#164486"), ("active", "#174fa8")],
              foreground=[("disabled", "#58677a"), ("!disabled", "white")])
    for kind in ("TEntry", "TCombobox"):
        style.configure(kind, fieldbackground="#f8fafc", bordercolor=border, lightcolor=border,
                        darkcolor=border, padding=5, arrowsize=13)
        style.map(kind, bordercolor=[("focus", blue)], fieldbackground=[("readonly", "#f8fafc")])
    for name, foreground, background in (("Result", "#385875", "#eaf1f8"),
                                         ("Success", "#125941", "#e2f5ec"),
                                         ("Error", "#8c2839", "#ffeaec")):
        style.configure(name + ".TLabel", font=bold, foreground=foreground, background=background, padding=(10, 6))
    style.configure("TNotebook", background="#edf2f7", borderwidth=0, tabmargins=0)
    style.configure("TNotebook.Tab", padding=(22, 8), background="#edf2f7", foreground=muted, font=bold)
    style.map("TNotebook.Tab", background=[("selected", blue), ("active", "#dce6f1")],
              foreground=[("disabled", "#79899a"), ("selected", "white")], padding=[("selected", (22, 8))])
    style.configure("Treeview", background=surface, fieldbackground=surface, borderwidth=0, rowheight=30)
    style.configure("Treeview.Heading", font=bold, foreground=muted, relief="flat", background="#eef3f8", padding=6)
    style.map("Treeview", background=[("selected", "#d7e7ff")], foreground=[("selected", "#16345a")])
    style.configure("Horizontal.TProgressbar", background=blue, troughcolor="#e7edf3", borderwidth=0)


class OperationPane:
    def __init__(self, app, operation):
        self.app, self.operation = app, operation
        self.frame = ttk.Frame(app.notebook, padding=(0, 12, 0, 2), style="Page.TFrame")
        stacked = operation == "compare"
        self.frame.columnconfigure(0, weight=1, uniform="panels")
        if not stacked:
            self.frame.columnconfigure(1, weight=1, uniform="panels")
        self.frame.rowconfigure(1 if stacked else 0, weight=1)
        self.last_result = None
        self.info_after = None
        self.source = tk.StringVar()
        temp = ROOT / "data/temp"
        self.parent = tk.StringVar(value=str(temp if temp.is_dir() else ROOT / "data"))
        self.name = tk.StringVar(value=new_output_name(operation))
        self.mode, self.model, self.models = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.info = tk.StringVar(value="manifest.json이 있는 폴더를 선택하세요." if operation == "decompress"
                                 else "파일을 선택하면 크기와 형식을 확인할 수 있습니다.")
        self.summary = tk.StringVar(value="실행 대기")
        self.best, self.demo = tk.StringVar(), tk.StringVar()
        self.view_mode = tk.StringVar(value="archive")
        self.controls = []

        card = ttk.Frame(self.frame, padding=(17, 13))
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 0 if stacked else 5))
        card.columnconfigure(0, weight=1)
        title = {"smart": "압축 설정", "decompress": "복원 설정", "compare": "비교 설정"}[operation]
        ttk.Label(card, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        form = ttk.Frame(card)
        form.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        form.columnconfigure(0, weight=1)
        source_fields = ttk.Frame(form)
        source_fields.grid(row=0, column=0, sticky="new", padx=(0, 10 if stacked else 0))
        source_fields.columnconfigure(0, weight=1)
        if stacked:
            form.columnconfigure(1, weight=2)
        self._field(source_fields, 0, "압축 결과 폴더" if operation == "decompress" else "원본 파일",
                    self.source, self.browse_input, "선택")
        ttk.Label(source_fields, textvariable=self.info, style="Muted.TLabel", wraplength=370).grid(row=2, column=0, columnspan=2, sticky="w")
        if operation == "smart":
            choices = ttk.Frame(form)
            choices.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 3))
            choices.columnconfigure((0, 1), weight=1, uniform="choice")
            for col, (label, var, values) in enumerate((("사용 목적", self.mode, MODES),
                    ("예측 모델", self.model, tuple(MODEL_LABELS.values())))):
                ttk.Label(choices, text=label, style="Field.TLabel").grid(row=0, column=col, sticky="w")
                box = ttk.Combobox(choices, textvariable=var, values=values, state="readonly", width=12)
                box.grid(row=1, column=col, sticky="ew", padx=(0 if col == 0 else 4, 4 if col == 0 else 0), pady=3)
                self.controls.append((box, "readonly"))
                if col == 0:
                    self.mode_box = box
                else:
                    self.model_box = box
        output = ttk.Frame(form)
        output.grid(row=0 if stacked else 4, column=1 if stacked else 0, columnspan=1 if stacked else 2, sticky="new")
        output.columnconfigure(0, weight=1)
        if stacked:
            output.columnconfigure(1, weight=1)
        for i, (label, var, command, action) in enumerate((
                ("저장 위치", self.parent, self.browse_parent, "선택"),
                ("새 결과 폴더 이름", self.name, self.fresh_name, "새 이름"))):
            field = ttk.Frame(output)
            field.grid(row=0 if stacked else i, column=i if stacked else 0, sticky="ew", padx=(8 if stacked and i else 0, 0))
            field.columnconfigure(0, weight=1)
            self._field(field, 0, label, var, command, action)

        if operation == "smart":
            self.custom_model = tk.BooleanVar()
            custom = ttk.Frame(form)
            custom.columnconfigure(0, weight=1)
            custom.grid(row=6, column=0, columnspan=2, sticky="ew")
            self._field(custom, 0, "직접 만든 모델 폴더", self.models, self.browse_models, "선택")
            custom.grid_remove()
            def toggle_model():
                if self.custom_model.get():
                    custom.grid()
                else:
                    self.models.set("")
                    custom.grid_remove()
            toggle = ttk.Checkbutton(form, text="별도 모델 폴더 사용", variable=self.custom_model, command=toggle_model)
            toggle.grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))
            self.controls.append((toggle, "normal"))

        self.start_button = ttk.Button(card, text={"smart": "예측해 압축하기", "decompress": "검증해 복원하기",
                                      "compare": "네 알고리즘 비교하기"}[operation], style="Accent.TButton",
                                      command=lambda: app.start(operation))
        self.start_button.grid(row=0 if stacked else 2, column=0, sticky="e" if stacked else "ew", pady=(0 if stacked else 9, 0))
        self.controls.append((self.start_button, "normal"))

        result = ttk.Frame(self.frame, padding=(17, 13))
        result.grid(row=1 if stacked else 0, column=0 if stacked else 1, sticky="nsew",
                    padx=(0 if stacked else 5, 0), pady=(8 if stacked else 0, 0))
        result.columnconfigure(0, weight=1)
        result.rowconfigure(3, weight=1)
        header = ttk.Frame(result)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text={"smart":"압축 결과", "decompress":"복원 결과", "compare":"알고리즘별 실측"}[operation],
                  style="Section.TLabel").pack(side="left")
        if stacked:
            self.view_box = ttk.Combobox(header, textvariable=self.view_mode, values=MODES, state="readonly", width=12)
            self.view_box.pack(side="right")
            ttk.Label(header, text="점수 기준", style="Muted.TLabel").pack(side="right", padx=7)
            self.controls.append((self.view_box, "readonly"))
        self.summary_label = ttk.Label(result, textvariable=self.summary, style="Result.TLabel", wraplength=360)
        self.summary_label.grid(row=1, column=0, sticky="ew", pady=(7, 8))

        if operation == "smart":
            self.size_card = ttk.Frame(result)
            self.size_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
            self.size_card.columnconfigure(1, weight=1)
            self.size_bars = []
            for i, (label, color) in enumerate((("원본", "#a8b9cb"), ("압축", "#215dc2"))):
                ttk.Label(self.size_card, text=label, style="Field.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 7))
                track = tk.Frame(self.size_card, height=8, bg="#eef2f7")
                track.grid(row=i, column=1, sticky="ew")
                bar = tk.Frame(track, bg=color)
                value = tk.StringVar()
                ttk.Label(self.size_card, textvariable=value).grid(row=i, column=2, sticky="e", padx=(8, 0))
                self.size_bars.append((bar, value))
            self.size_card.grid_remove()
        table = ttk.Frame(result)
        table.grid(row=3, column=0, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ("algorithm", "verified", "size", "ratio", "compress", "decompress", "score", "status") if stacked else ("field", "value")
        headings = ("알고리즘", "복원 검증", "압축 크기 (B)", "압축률 ↓", "압축 ms ↓", "해제 ms ↓", "점수 ↓", "상태") if stacked else ("측정 항목", "결과값")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=4)
        for i, (column, heading) in enumerate(zip(columns, headings)):
            align = "e" if stacked and 2 <= i <= 6 else "w"
            self.tree.heading(column, text=heading, anchor=align)
            self.tree.column(column, anchor=align, width=96 if stacked else (180 if i == 0 else 210), minwidth=80)
        self.tree.tag_configure("best", background="#e2f5ec", foreground="#125941")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.empty = ttk.Label(self.tree, style="Muted.TLabel", justify="center", text={
            "smart": "압축을 실행하면 선택한 알고리즘과\n원본 대비 압축 크기가 표시됩니다.",
            "decompress": "복원을 실행하면 파일 크기와\n해시 검증 결과가 표시됩니다.",
            "compare": "비교를 실행하면 네 알고리즘의 측정값이 표시됩니다."}[operation])
        self.empty.place(relx=.5, rely=.58, anchor="center")
        if stacked:
            ttk.Label(result, textvariable=self.best, wraplength=850).grid(row=4, column=0, sticky="w")
            ttk.Label(result, textvariable=self.demo, style="Muted.TLabel", wraplength=850).grid(row=5, column=0, sticky="w")
            self.view_mode.trace_add("write", lambda *_: app.refresh_comparison())
        actions = ttk.Frame(result)
        actions.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.details_button = ttk.Button(actions, text="실행 기록", command=lambda: app.details(operation))
        self.details_button.grid(row=0, column=0, sticky="w")
        self.copy_button = ttk.Button(actions, text="경로 복사", command=lambda: app.copy_path(operation))
        self.copy_button.grid(row=0, column=1, sticky="w", padx=(4, 0))
        if operation == "smart":
            self.restore_button = ttk.Button(actions, text="이 결과 복원", command=app.prepare_restore)
            self.restore_button.grid(row=1, column=0, sticky="w", pady=(3, 0))
            self.compare_button = ttk.Button(actions, text="같은 파일 비교", command=app.prepare_compare)
            self.compare_button.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(3, 0))
        self.source.trace_add("write", lambda *_: app.input_changed(operation))
        if operation == "smart":
            for value in (self.mode, self.model, self.models):
                value.trace_add("write", lambda *_: app.invalidate_demo())

    def _field(self, parent, row, label, variable, command, action):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 2))
        entry = ttk.Entry(parent, textvariable=variable, width=10)
        entry.grid(row=row + 1, column=0, sticky="ew")
        button = ttk.Button(parent, text=action, command=command, width=6)
        button.grid(row=row + 1, column=1, sticky="ns", padx=(6, 0))
        self.controls.extend(((entry, "normal"), (button, "normal")))

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
        self.root.geometry("1120x760")
        self.root.minsize(960, 720)
        self.root.configure(background="#edf2f7")
        configure_theme(root)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(root, style="Header.TFrame", padding=(23, 13))
        header.grid(row=0, column=0, sticky="ew")
        mark = tk.Canvas(header, width=42, height=42, bg="#142b43", highlightthickness=0)
        mark.pack(side="left", padx=(0, 12))
        for y, color in ((21, "#6395f2"), (14, "#7bc8ef"), (7, "#aeedde")):
            mark.create_polygon(3, y+6, 21, y, 39, y+6, 21, y+13, fill=color)
        ttk.Label(header, text="Smart Compression", style="Brand.TLabel").pack(side="left")
        ttk.Label(header, text="무손실 압축 연구", style="Header.TLabel").pack(side="right")
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=18, pady=(12, 0))
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
        self.progress.grid_remove()
        ttk.Label(footer, text="공식 평가 기준   압축률 · 압축 시간 · 해제 시간     |     메모리는 참고 지표입니다.",
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
        pane.empty.place_forget()
        if operation == "smart":
            pane.size_card.grid_remove()
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
        self.progress.grid()
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
            self.progress.grid_remove()
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
            sizes = (data["original_size"], data["compressed_size"])
            for (bar, value), size in zip(pane.size_bars, sizes):
                bar.place(x=0, y=0, relheight=1, relwidth=size / max(sizes))
                value.set(f"{size:,} B")
            pane.size_card.grid()
            values = [("선택 알고리즘", data["algorithm"]), ("사용 목적 / 모델", f"{result.request.mode} / {MODEL_LABELS[result.request.model_kind]}"),
                ("원본 bytes", data["original_size"]), ("압축 bytes", data["compressed_size"]), ("압축률 (작을수록 유리)", data["compression_ratio"]),
                ("복원 검증", "통과"), ("모델 출력 (미보정)", data["prediction_confidence"])]
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
        pane.demo.set("같은 파일과 목적으로 Smart 압축을 실행하면 예측과 실측을 대조할 수 있습니다." if result else "")
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
                display(score),row.get("status","확인 불가")),
                tags=("best",) if selection and row["algorithm"] == selection["best_algorithm"] else ())
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
