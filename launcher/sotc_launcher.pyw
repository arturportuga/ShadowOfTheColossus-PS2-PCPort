"""Launcher do port nativo de Shadow of the Colossus (PS2 -> PC).

L1: abre o jogo e edita o sotc.ini (vídeo, controles, avançado).
L2: prepara o jogo a partir do ISO (pipeline.py) com progresso, log ao vivo e botão Parar,
    no modo de compilação escolhido (rápido, equilibrado ou economizar RAM).
"""

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

if getattr(sys, "frozen", False):
    # "SotC Launcher.exe" (PyInstaller) fica na pasta do pacote; os arquivos do launcher, em 04_launcher.
    WORKSPACE = Path(sys.executable).resolve().parent
    HERE = WORKSPACE / "04_launcher"
else:
    HERE = Path(__file__).resolve().parent
    WORKSPACE = HERE.parent
FROZEN = getattr(sys, "frozen", False)
CONFIG_FILE = HERE / "launcher.json"
LOG_FILE = HERE / "ultima_sessao.log"
PREP_LOG = HERE / "preparacao.log"
ICON_FILE = WORKSPACE / "02_port" / "game_icon.ico"
MAX_LOG_LINES = 3000

sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402
import textos  # noqa: E402
from textos import BUTTONS, local, tr  # noqa: E402

DEFAULT_CONFIG = {
    "iso": str(WORKSPACE / "01_iso" / "SotC_PAL_SCES-53326.iso"),
    "port_dir": str(WORKSPACE / "02_port"),
    "capture_dir": str(WORKSPACE / "03_vu1_capture"),
    "minimize_on_play": True,
    "capture_vu1": True,
}

# Valores padrão do sotc.ini (os do port + os ajustes que achamos para AMD).
DEFAULT_INI = {
    "PS2X_MEMCARD": "1",
    "PS2X_INVERT_RIGHT_STICK": "xy",
    "PS2X_MOUSE_SENSITIVITY": "1.0",
    "PS2X_MOUSE_VERTICAL_SENSITIVITY": "1.0",
    "PS2X_GS_GPU": "1",
    "PS2X_GS_THREAD": "1",
    "PS2X_MTVU": "1",
    "PS2X_VU1_RECOMP": "1",
    "PS2X_GS_HW_RASTER": "0",
    "PS2X_GS_DIRECT_PRESENT": "0",
    "SOTC_VIDEO_MODE": "NTSC",
    "SOTC_WIDESCREEN": "1",
    "SOTC_WINDOW_MAXIMIZED": "1",
    "SOTC_VSYNC": "1",
    "SOTC_DISABLE_MOTION_BLUR": "0",
    "SOTC_SCRIPT_TRACE": "0",
}

# Teclas que o jogo já usa para outra coisa (chave do texto em textos.py).
RESERVED = {"W": "use_walk", "A": "use_walk", "S": "use_walk", "D": "use_walk",
            "F5": "use_quicksave", "F9": "use_quickload", "F11": "use_fullscreen"}

# keysym do Tk -> nome que o jogo entende (ps2_host_input.cpp, parseBinding)
TK_KEYS = {
    "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
    "space": "SPACE", "Return": "ENTER", "KP_Enter": "ENTER", "Tab": "TAB",
    "BackSpace": "BACKSPACE", "Escape": "ESCAPE",
    "Shift_L": "LEFT_SHIFT", "Shift_R": "RIGHT_SHIFT",
    "Control_L": "LEFT_CTRL", "Control_R": "RIGHT_CTRL",
}

CREATE_NO_WINDOW = 0x08000000
INVERT_VALUES = ["0", "x", "y", "xy"]  # na ordem de textos "invert_options"


def pretty_key(name):
    return local(textos.PRETTY.get(name, name))


def button_label(key):
    return next(local(label) for k, label, _ in BUTTONS if k == key)


def tk_key_to_bind(keysym):
    if keysym in TK_KEYS:
        return TK_KEYS[keysym]
    if len(keysym) == 1 and keysym.isalnum():
        return keysym.upper()
    if keysym.startswith("F") and keysym[1:].isdigit() and 1 <= int(keysym[1:]) <= 12:
        return keysym
    return None


# ---------------------------------------------------------------- arquivos

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    # Primeira vez: um ISO largado na pasta 01_iso serve.
    if not Path(cfg["iso"]).is_file():
        isos = sorted((WORKSPACE / "01_iso").glob("*.iso"))
        if isos:
            cfg["iso"] = str(isos[0])
    return cfg


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


class IniFile:
    """sotc.ini preservando ordem, comentários e chaves que o launcher não conhece."""

    def __init__(self, path):
        self.path = Path(path)
        self.lines = []
        self.values = {}
        if self.path.exists():
            self.lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in self.lines:
            key, sep, value = line.partition("=")
            if sep and not line.lstrip().startswith((";", "#", "[")):
                self.values[key.strip()] = value.strip()

    def get(self, key, default=""):
        return self.values.get(key, default)

    def save(self, updates):
        lines = list(self.lines) or ["[Settings]"]
        pending = dict(updates)
        for i, line in enumerate(lines):
            key, sep, _ = line.partition("=")
            key = key.strip()
            if sep and key in pending:
                lines[i] = f"{key}={pending.pop(key)}"
        lines += [f"{k}={v}" for k, v in pending.items()]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.__init__(self.path)


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq sotc.exe", "/NH"],
                             capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout
        return "sotc.exe" in out.lower()
    except OSError:
        return False


# ---------------------------------------------------------------- janela

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.proc = None
        self.prep_proc = self.prep_job = None
        self.prep_stopped = False
        self.iso_ok = self.built = False
        self.title("Shadow of the Colossus — Launcher")
        self.resizable(False, False)
        if ICON_FILE.exists():
            try:
                self.iconbitmap(str(ICON_FILE))
            except tk.TclError:
                pass
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 15))
        style.configure("Sub.TLabel", foreground="#666")
        style.configure("Play.TButton", font=("Segoe UI Semibold", 12), padding=(24, 8))
        style.configure("Ok.TLabel", foreground="#2a7a2a")
        style.configure("Bad.TLabel", foreground="#b03030")
        style.configure("Warn.TLabel", foreground="#a86400")

        textos.set_lang(self.cfg.get("lang") or textos.default_lang())
        self.build_ui()
        self.load_ini()
        self.refresh_status()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(1000, self.poll_game)

    # ---------- montagem

    def build_ui(self):
        self.vars = {}
        self.bind_vars = {}
        top = ttk.Frame(self, padding=(16, 12, 16, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Shadow of the Colossus", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text=tr("subtitle"), style="Sub.TLabel").grid(row=1, column=0, sticky="w")
        top.columnconfigure(0, weight=1)
        self.lang_var = tk.StringVar(value=textos.LANGS[textos.lang()])
        self.lang_box = ttk.Combobox(top, textvariable=self.lang_var, state="readonly", width=11,
                                     values=list(textos.LANGS.values()))
        self.lang_box.grid(row=0, column=1, rowspan=2, sticky="e")
        self.lang_box.bind("<<ComboboxSelected>>", lambda _: self.change_lang())

        self.nb = nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=8)
        nb.add(self.tab_play(nb), text=f"  {tr('tab_game')}  ")
        nb.add(self.tab_video(nb), text=f"  {tr('tab_video')}  ")
        nb.add(self.tab_controls(nb), text=f"  {tr('tab_controls')}  ")
        nb.add(self.tab_advanced(nb), text=f"  {tr('tab_advanced')}  ")
        self.prep_tab = self.tab_prepare(nb)
        nb.add(self.prep_tab, text=f"  {tr('tab_prepare')}  ")

        bottom = ttk.Frame(self, padding=(12, 0, 12, 12))
        bottom.pack(fill="x")
        self.status_msg = ttk.Label(bottom, text="", style="Sub.TLabel")
        self.status_msg.pack(side="left")
        self.play_btn = ttk.Button(bottom, text=tr("play"), style="Play.TButton", command=self.play)
        self.play_btn.pack(side="right")
        ttk.Button(bottom, text=tr("save"), command=self.save_all).pack(side="right", padx=8)

    def change_lang(self):
        """Troca o idioma remontando a janela (as opções são salvas antes e lidas de novo)."""
        lang = next(k for k, v in textos.LANGS.items() if v == self.lang_var.get())
        if lang == textos.lang():
            return
        self.save_all(quiet=True)
        self.cfg["lang"] = lang
        save_config(self.cfg)
        textos.set_lang(lang)
        tab = self.nb.index(self.nb.select())
        for child in self.winfo_children():
            child.destroy()
        self.build_ui()
        self.load_ini()
        self.nb.select(tab)
        self.refresh_status()

    def tab_play(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.iso_var = tk.StringVar(value=self.cfg["iso"])
        self.port_var = tk.StringVar(value=self.cfg["port_dir"])
        self.minimize_var = tk.BooleanVar(value=self.cfg.get("minimize_on_play", True))

        ttk.Label(f, text=tr("iso_label")).grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.iso_var, width=62).grid(row=1, column=0, sticky="we")
        ttk.Button(f, text=tr("browse"), command=self.pick_iso).grid(row=1, column=1, padx=(6, 0))
        self.iso_status = ttk.Label(f, text="")
        self.iso_status.grid(row=2, column=0, sticky="w", pady=(2, 10))

        ttk.Label(f, text=tr("port_label")).grid(row=3, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.port_var, width=62).grid(row=4, column=0, sticky="we")
        ttk.Button(f, text=tr("browse"), command=self.pick_dir).grid(row=4, column=1, padx=(6, 0))
        self.build_status = ttk.Label(f, text="")
        self.build_status.grid(row=5, column=0, sticky="w", pady=(2, 0))
        self.vu1_status = ttk.Label(f, text="")
        self.vu1_status.grid(row=6, column=0, sticky="w", pady=(2, 10))

        ttk.Checkbutton(f, text=tr("minimize"), variable=self.minimize_var).grid(row=7, column=0, sticky="w")
        self.capture_var = tk.BooleanVar(value=self.cfg.get("capture_vu1", True))
        ttk.Checkbutton(f, text=tr("capture"), variable=self.capture_var).grid(row=9, column=0, sticky="w", pady=(4, 0))
        ttk.Label(f, text=tr("capture_hint"), style="Sub.TLabel").grid(row=10, column=0, columnspan=2, sticky="w",
                                                                       padx=(22, 0))

        tools = ttk.Frame(f)
        tools.grid(row=11, column=0, columnspan=2, sticky="w", pady=(16, 0))
        self.rebuild_btn = ttk.Button(tools, text=tr("recompile"), command=lambda: self.start_prepare(force=False))
        self.rebuild_btn.pack(side="left")
        ttk.Button(tools, text=tr("game_folder"), command=self.open_game_dir).pack(side="left", padx=6)
        ttk.Button(tools, text=tr("game_log"), command=self.open_log).pack(side="left")
        for v in (self.iso_var, self.port_var):
            v.trace_add("write", lambda *_: self.refresh_status())
        return f

    def tab_prepare(self, parent):
        f = ttk.Frame(parent, padding=14)
        mode = self.cfg.get("build_mode")
        self.mode_var = tk.StringVar(value=mode if mode in pipeline.MODES else pipeline.DEFAULT_MODE)
        modes = ttk.LabelFrame(f, text=tr("mode_frame"), padding=(10, 4, 10, 6))
        modes.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 10))
        ram = pipeline.ram_gb()
        compiler = self.compiler()
        self.mode_radios = []
        for r, key in enumerate(pipeline.MODES):
            jobs, gb, mins = pipeline.mode_estimate(key, ram, compiler)
            rb = ttk.Radiobutton(modes, text=tr(f"mode_{key}"), value=key, variable=self.mode_var)
            rb.grid(row=r, column=0, sticky="w")
            self.mode_radios.append(rb)
            ttk.Label(modes, text=tr("mode_line", time=fmt_time(mins * 60), gb=gb, hint=tr(f"hint_{key}")),
                      style="Sub.TLabel").grid(row=r, column=1, sticky="w", padx=(8, 0))
        which = tr("compiler_portable" if compiler == "portatil" else "compiler_vs")
        ttk.Label(modes, text=tr("compiler_line", which=which),
                  style="Sub.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.step_label = ttk.Label(f, text=tr("ready_to_prepare"), font=("Segoe UI Semibold", 11))
        self.step_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.progress = ttk.Progressbar(f, length=560, mode="determinate", maximum=1000)
        self.progress.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 2))
        self.progress_text = ttk.Label(f, text="", style="Sub.TLabel")
        self.progress_text.grid(row=3, column=0, sticky="w")
        buttons = ttk.Frame(f)
        buttons.grid(row=3, column=1, sticky="e")
        self.start_btn = ttk.Button(buttons, text=tr("start"), command=self.start_prepare)
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = ttk.Button(buttons, text=tr("stop"), command=self.stop_prepare, state="disabled")
        self.stop_btn.pack(side="left")
        box = ttk.Frame(f)
        box.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.log = tk.Text(box, height=12, width=78, wrap="none", font=("Consolas", 8), state="disabled",
                           relief="flat", background="#f7f7f7")
        scroll = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return f

    def check(self, parent, key, text, row, hint=None, invert=False):
        var = tk.BooleanVar()
        self.vars[key] = (var, invert)
        ttk.Checkbutton(parent, text=text, variable=var).grid(row=row, column=0, sticky="w", pady=(6, 0))
        if hint:
            ttk.Label(parent, text=hint, style="Sub.TLabel", wraplength=520,
                      justify="left").grid(row=row + 1, column=0, sticky="w", padx=(22, 0))

    def tab_video(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.check(f, "SOTC_WINDOW_MAXIMIZED", tr("maximized"), 0, tr("maximized_hint"))
        self.check(f, "SOTC_WIDESCREEN", tr("widescreen"), 2, tr("widescreen_hint"))
        self.check(f, "SOTC_VSYNC", tr("vsync"), 4, tr("vsync_hint"))
        self.check(f, "SOTC_DISABLE_MOTION_BLUR", tr("motion_blur"), 6, invert=True)

        ttk.Label(f, text=tr("frequency")).grid(row=8, column=0, sticky="w", pady=(14, 0))
        self.video_mode = tk.StringVar()
        row = ttk.Frame(f)
        row.grid(row=9, column=0, sticky="w", padx=(22, 0))
        ttk.Radiobutton(row, text="60 Hz (NTSC)", value="NTSC", variable=self.video_mode).pack(side="left")
        ttk.Radiobutton(row, text="50 Hz (PAL)", value="PAL", variable=self.video_mode).pack(side="left", padx=14)
        ttk.Label(f, text=tr("res_native"), style="Sub.TLabel").grid(
            row=10, column=0, sticky="w", pady=(16, 0))
        return f

    def tab_controls(self, parent):
        f = ttk.Frame(parent, padding=14)
        ttk.Label(f, text=tr("controls_intro"), style="Sub.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")

        grid = ttk.Frame(f)
        grid.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        half = (len(BUTTONS) + 1) // 2
        for i, (key, label, _) in enumerate(BUTTONS):
            r, c = i % half, (i // half) * 3
            var = tk.StringVar()
            self.bind_vars[key] = var
            ttk.Label(grid, text=local(label), width=13).grid(row=r, column=c, sticky="w", pady=1)
            btn = ttk.Button(grid, width=22, command=lambda k=key: self.capture(k))
            btn.grid(row=r, column=c + 1, sticky="w", padx=(0, 18), pady=1)
            var.trace_add("write", lambda *_, b=btn, v=var: b.configure(text=pretty_key(v.get())))
        self.bind_warning = ttk.Label(f, text="", style="Warn.TLabel", wraplength=540, justify="left")
        self.bind_warning.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))

        ttk.Label(f, text=tr("fixed_keys"), style="Sub.TLabel").grid(row=3, column=0, columnspan=4, sticky="w",
                                                                     pady=(4, 10))

        opts = ttk.Frame(f)
        opts.grid(row=4, column=0, columnspan=4, sticky="w")
        self.sens_h = tk.StringVar()
        self.sens_v = tk.StringVar()
        self.invert = tk.StringVar()
        ttk.Label(opts, text=tr("mouse_sens")).grid(row=0, column=0, sticky="w")
        ttk.Spinbox(opts, from_=0.1, to=5.0, increment=0.1, width=6,
                    textvariable=self.sens_h).grid(row=0, column=1, padx=6)
        ttk.Label(opts, text=tr("vertical")).grid(row=0, column=2, sticky="w", padx=(10, 0))
        ttk.Spinbox(opts, from_=0.1, to=5.0, increment=0.1, width=6,
                    textvariable=self.sens_v).grid(row=0, column=3, padx=6)
        ttk.Label(opts, text=tr("invert_camera")).grid(row=1, column=0, sticky="w", pady=(8, 0))
        inv = ttk.Combobox(opts, textvariable=self.invert, state="readonly", width=24, values=tr("invert_options"))
        inv.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(f, text=tr("restore_defaults"),
                   command=self.reset_binds).grid(row=5, column=0, sticky="w", pady=(14, 0))
        return f

    def tab_advanced(self, parent):
        f = ttk.Frame(parent, padding=14)
        ttk.Label(f, text=tr("adv_intro"), style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        self.check(f, "PS2X_GS_HW_RASTER", tr("hw_raster"), 1, tr("experimental_slower"))
        self.check(f, "PS2X_GS_DIRECT_PRESENT", tr("direct_present"), 3, tr("experimental_slower"))
        self.check(f, "PS2X_GS_THREAD", tr("gs_thread"), 5, tr("four_cores"))
        self.check(f, "PS2X_MTVU", tr("mtvu"), 7, tr("four_cores"))
        self.check(f, "PS2X_VU1_RECOMP", tr("vu1_recomp"), 9, tr("vu1_recomp_hint"))
        self.check(f, "PS2X_MEMCARD", tr("memcard"), 11, tr("memcard_hint"))
        self.check(f, "SOTC_SCRIPT_TRACE", tr("script_trace"), 13, tr("script_trace_hint"))
        ttk.Button(f, text=tr("edit_ini"),
                   command=self.open_ini).grid(row=15, column=0, sticky="w", pady=(14, 0))
        return f

    # ---------- ini <-> tela

    def port_dir(self):
        return Path(self.port_var.get())

    def game_dir(self):
        return self.port_dir() / "build" / "port" / "bin"

    def ini(self):
        return IniFile(self.game_dir() / "sotc.ini")

    def load_ini(self):
        ini = self.ini()
        for key, (var, invert) in self.vars.items():
            on = ini.get(key, DEFAULT_INI.get(key, "0")) == "1"
            var.set(on != invert if invert else on)
        self.video_mode.set(ini.get("SOTC_VIDEO_MODE", "NTSC").upper())
        self.sens_h.set(ini.get("PS2X_MOUSE_SENSITIVITY", "1.0"))
        self.sens_v.set(ini.get("PS2X_MOUSE_VERTICAL_SENSITIVITY", "1.0"))
        inv = ini.get("PS2X_INVERT_RIGHT_STICK", "xy").lower()
        self.invert.set(tr("invert_options")[INVERT_VALUES.index(inv) if inv in INVERT_VALUES else 3])
        for key, _, default in BUTTONS:
            self.bind_vars[key].set(ini.get(key, default).upper())
        self.check_binds()

    def collect(self):
        out = {}
        for key, (var, invert) in self.vars.items():
            on = var.get()
            out[key] = "0" if on == invert else "1"
        out["SOTC_VIDEO_MODE"] = self.video_mode.get()
        for name, var in (("PS2X_MOUSE_SENSITIVITY", self.sens_h), ("PS2X_MOUSE_VERTICAL_SENSITIVITY", self.sens_v)):
            try:
                out[name] = f"{min(max(float(var.get().replace(',', '.')), 0.1), 5.0):.1f}"
            except ValueError:
                out[name] = "1.0"
        options = tr("invert_options")
        out["PS2X_INVERT_RIGHT_STICK"] = (INVERT_VALUES[options.index(self.invert.get())]
                                          if self.invert.get() in options else "xy")
        for key, var in self.bind_vars.items():
            out[key] = var.get()
        return out

    def save_all(self, quiet=False):
        self.cfg.update(iso=self.iso_var.get(), port_dir=self.port_var.get(),
                        minimize_on_play=self.minimize_var.get(), capture_vu1=self.capture_var.get(),
                        build_mode=self.mode_var.get(), lang=textos.lang())
        self.cfg.pop("game_dir", None)
        save_config(self.cfg)
        if not self.port_dir().is_dir():
            return False
        # Antes da primeira compilação a pasta ainda não existe; o jogo completa o ini depois.
        self.game_dir().mkdir(parents=True, exist_ok=True)
        self.ini().save(self.collect())
        if not quiet:
            self.flash(tr("saved_running" if game_running() else "saved"))
        return True

    def flash(self, text):
        self.status_msg.configure(text=text)
        self.after(4000, lambda: self.status_msg.configure(text="") if self.status_msg["text"] == text else None)

    # ---------- controles

    def capture(self, key):
        label = button_label(key)
        win = tk.Toplevel(self)
        win.title(tr("change_key"))
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text=tr("button_n", b=label.split()[-1]), style="Title.TLabel").pack(padx=20, pady=(14, 4))
        area = tk.Label(win, text=tr("press_key"),
                        width=34, height=5, relief="groove", bg="#f4f4f4", font=("Segoe UI", 10))
        area.pack(padx=20, pady=6)
        ttk.Button(win, text=tr("cancel"), command=win.destroy).pack(pady=(4, 14))

        def done(name):
            self.bind_vars[key].set(name)
            self.check_binds()
            win.destroy()

        def on_key(e):
            name = tk_key_to_bind(e.keysym)
            if name:
                done(name)
            else:
                area.configure(text=tr("key_rejected", k=e.keysym))
            return "break"

        win.bind("<KeyPress>", on_key)
        win.bind("<Tab>", on_key)
        for n, name in ((1, "MOUSE_LEFT"), (2, "MOUSE_MIDDLE"), (3, "MOUSE_RIGHT")):
            area.bind(f"<Button-{n}>", lambda e, nm=name: done(nm))
        win.focus_force()

    def check_binds(self):
        seen, problems = {}, []
        names = {k: local(l) for k, l, _ in BUTTONS}
        for key, var in self.bind_vars.items():
            v = var.get()
            if v in RESERVED:
                problems.append(tr("key_reserved", key=pretty_key(v), use=tr(RESERVED[v]), button=names[key]))
            if v in seen:
                problems.append(tr("key_twice", key=pretty_key(v), a=seen[v], b=names[key]))
            seen[v] = names[key]
        self.bind_warning.configure(text="⚠ " + "\n⚠ ".join(problems) if problems else "")

    def reset_binds(self):
        for key, _, default in BUTTONS:
            self.bind_vars[key].set(default)
        self.sens_h.set("1.0")
        self.sens_v.set("1.0")
        self.invert.set(tr("invert_options")[3])
        self.check_binds()

    # ---------- estado

    def refresh_status(self):
        # Digitar no caminho dispara várias vezes: espera parar de mudar.
        if getattr(self, "_status_job", None):
            self.after_cancel(self._status_job)
        self._status_job = self.after(250, self._refresh_status)

    def _refresh_status(self):
        self._status_job = None
        iso, port = Path(self.iso_var.get()), self.port_dir()
        self.iso_ok = self.built = False
        if not iso.is_file():
            self.iso_status.configure(text=tr("iso_missing"), style="Bad.TLabel")
        elif not (port / "Port" / "profile").is_dir():
            self.iso_status.configure(text=tr("iso_found", gb=iso.stat().st_size / 2**30), style="Sub.TLabel")
        else:
            try:
                profile, _ = pipeline.iso_identity(port, iso)
                self.iso_status.configure(text=tr("iso_ok", serial=profile["serial"], version=profile["version"]),
                                          style="Ok.TLabel")
                self.iso_ok = True
            except pipeline.Fail as e:
                text = tr(e.code, **e.values) if e.code in textos.T else f"✘ {e}"
                self.iso_status.configure(text=text, style="Bad.TLabel")

        path_len = len(str(port)) + 1
        if not (port / "Tools" / "generate.py").is_file():
            self.build_status.configure(text=tr("not_port"), style="Bad.TLabel")
        elif path_len > pipeline.MAX_PORT_PATH and not (self.game_dir() / "sotc.exe").is_file():
            self.build_status.configure(text=tr("path_too_long", n=path_len, max=pipeline.MAX_PORT_PATH),
                                        style="Bad.TLabel", wraplength=540)
        elif self.iso_ok:
            st = pipeline.status(port, iso, self.cfg.get("capture_dir"))
            self.built = st["ok"]
            self.build_status.configure(text=tr("st_" + st["code"], n=st.get("n", 0)),
                                        style="Ok.TLabel" if st["ok"] else "Warn.TLabel")
        else:
            self.build_status.configure(text="", style="Sub.TLabel")

        capture = Path(self.cfg.get("capture_dir", ""))
        n = len(list(capture.glob("*.bin"))) if capture.is_dir() else 0
        if n:
            self.vu1_status.configure(text=tr("vu1_some", n=n), style="Ok.TLabel")
        else:
            self.vu1_status.configure(text=tr("vu1_none"), style="Warn.TLabel")
        self.update_play_button()

    def preparing(self):
        return self.prep_proc is not None

    def update_play_button(self):
        running = (self.proc is not None and self.proc.poll() is None) or game_running()
        busy = self.preparing()
        can_prepare = "disabled" if busy or running or not self.iso_ok else "normal"
        self.rebuild_btn.configure(state=can_prepare)
        self.start_btn.configure(state=can_prepare)
        for rb in self.mode_radios:
            rb.configure(state="disabled" if busy else "normal")
        self.lang_box.configure(state="disabled" if busy else "readonly")
        if busy:
            self.play_btn.configure(text=tr("preparing"), state="disabled")
        elif running:
            self.play_btn.configure(text=tr("game_open"), state="disabled")
        elif self.iso_ok and not self.built:
            self.play_btn.configure(text=tr("prepare_game"), state="normal")
        else:
            self.play_btn.configure(text=tr("play"), state="normal" if self.iso_ok and self.built else "disabled")

    # ---------- preparar (pipeline.py num processo à parte, dentro de um Job do Windows)

    def compiler(self):
        """O compilador que a preparação vai usar: o da build já configurada, senão o portátil."""
        return pipeline.configured_compiler(Path(self.cfg["port_dir"]) / "build" / "port") or pipeline.DEFAULT_COMPILER

    def license_ok(self):
        """O compilador portátil baixa bibliotecas da Microsoft: a pessoa precisa aceitar a licença uma vez."""
        if (self.compiler() != "portatil" or self.cfg.get("licenca_ms")
                or pipeline.compilador.ready(pipeline.DEFAULT_COMPILER_DIR)):
            return True
        ok = messagebox.askyesno(tr("license_title"), tr("license_body", url=pipeline.compilador.LICENSE_URL))
        if ok:
            self.cfg["licenca_ms"] = True
            save_config(self.cfg)
        return ok

    def start_prepare(self, force=False):
        if self.preparing() or game_running():
            return
        self.save_all(quiet=True)
        if not self.license_ok():
            return
        # Congelado, o sotc_tools.exe faz o papel do Python (ver sotc_tools.py).
        runner = ([str(HERE / "sotc_tools.exe"), "pipeline"] if FROZEN else
                  [sys.executable.replace("pythonw.exe", "python.exe"), "-I", "-u", str(HERE / "pipeline.py")])
        cmd = [*runner, "--iso", self.iso_var.get(), "--port", str(self.port_dir()),
               "--capture", self.cfg.get("capture_dir", ""), "--mode", self.mode_var.get()]
        if self.cfg.get("licenca_ms"):
            cmd.append("--aceito-licenca-ms")
        if force:
            cmd.append("--force")
        try:
            self.prep_proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            messagebox.showerror("Launcher", tr("start_failed", e=e))
            return
        self.prep_job = KillOnCloseJob(self.prep_proc)
        self.prep_queue = queue.Queue()
        self.prep_started = time.time()
        self.prep_result = None
        self.progress_rate = None
        self.set_log("")
        self.progress.configure(value=0)
        self.step_label.configure(text=tr("starting"))
        self.progress_text.configure(text="")
        self.stop_btn.configure(state="normal")
        self.nb.select(self.prep_tab)
        threading.Thread(target=self._read_prepare, args=(self.prep_proc, self.prep_queue), daemon=True).start()
        self.update_play_button()
        self.after(100, self._drain_prepare)

    def _read_prepare(self, proc, q):
        with open(PREP_LOG, "w", encoding="utf-8", errors="replace") as log:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                log.write(line + "\n")
                q.put(line)
            code = proc.wait()
            log.write(f"[fim, código {code}]\n")
        q.put(("exit", code))

    def _drain_prepare(self):
        q = self.prep_queue
        for _ in range(400):
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, tuple):
                self._prepare_finished(item[1])
                return
            if item.startswith("@@STEP "):
                _, i, n, text = item.split(" ", 3)
                names = tr("steps")
                if 1 <= int(i) <= len(names):
                    text = names[int(i) - 1]
                self.step_label.configure(text=tr("step", i=i, n=n, text=text))
                self.progress.configure(mode="indeterminate")
                self.progress.start(15)
                self.progress_text.configure(text="")
                self.progress_rate = None
            elif item.startswith("@@PROGRESS "):
                done, total = map(int, item.split()[1:3])
                self._show_progress(done, total)
            elif item.startswith("@@FAIL "):
                self.prep_result = ("fail", item[7:])
                self.append(item[7:])
            elif item == "@@DONE":
                self.prep_result = ("done", "")
            else:
                self.append(item)
        if str(self.progress["mode"]) == "indeterminate":
            self.progress_text.configure(text=tr("elapsed", t=fmt_time(time.time() - self.prep_started)))
        self.after(150, self._drain_prepare)

    def _show_progress(self, done, total):
        if str(self.progress["mode"]) != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        self.progress.configure(value=1000 * done / max(total, 1))
        now = time.time()
        if self.progress_rate is None:
            self.progress_rate = (now, done)
        t0, d0 = self.progress_rate
        eta = ""
        if done - d0 >= 20 and now - t0 > 10:
            eta = tr("eta", t=fmt_time((total - done) * (now - t0) / (done - d0)))
        self.progress_text.configure(text=tr("files", done=done, total=total, eta=eta,
                                             t=fmt_time(now - self.prep_started)))

    def _prepare_finished(self, code):
        self.progress.stop()
        self.stop_btn.configure(state="disabled")
        self.prep_job.close()
        self.prep_proc = self.prep_job = None
        result = self.prep_result
        took = fmt_time(time.time() - self.prep_started)
        if result and result[0] == "done":
            self.progress.configure(mode="determinate", value=1000)
            self.step_label.configure(text=tr("done", t=took))
            self.flash(tr("game_ready"))
        elif self.prep_stopped:
            self.step_label.configure(text=tr("stopped"))
        else:
            reason = result[1] if result else f"code {code}"
            self.step_label.configure(text=tr("failed", reason=reason))
            messagebox.showerror("Launcher", tr("failed_box", reason=reason, log=PREP_LOG))
        self.prep_stopped = False
        self.refresh_status()

    def stop_prepare(self):
        if self.preparing() and messagebox.askyesno("Launcher", tr("stop_confirm")):
            self.prep_stopped = True
            self.prep_job.terminate()

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_log(self, text):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", text)
        self.log.configure(state="disabled")

    # ---------- jogar

    def play(self):
        if self.iso_ok and not self.built:
            if (self.port_dir() / "build" / "port" / "build.ninja").is_file():
                self.start_prepare()  # só atualizar: costuma ser rápido
            else:
                # Primeira vez (a compilação longa): deixa escolher o modo antes.
                self.nb.select(self.prep_tab)
                self.step_label.configure(text=tr("choose_mode"))
            return
        if game_running():
            messagebox.showinfo("Launcher", tr("already_open"))
            return
        self.save_all(quiet=True)
        game_dir = self.game_dir()
        env = dict(os.environ)
        if self.capture_var.get():
            capture = Path(self.cfg["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            env["PS2X_VU1_CAPTURE"] = str(capture)
        log = open(LOG_FILE, "w", encoding="utf-8", errors="replace")
        try:
            self.proc = subprocess.Popen([str(game_dir / "sotc.exe"), "--iso", self.iso_var.get()],
                                         cwd=game_dir, stdout=log, stderr=subprocess.STDOUT, env=env,
                                         creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            log.close()
            messagebox.showerror("Launcher", tr("open_failed", e=e))
            return
        self.log_handle = log
        self.started_ok = False
        self.update_play_button()
        self.after(5000, self.check_early_exit)
        if self.minimize_var.get():
            self.iconify()

    def check_early_exit(self):
        if self.proc is None:
            return
        code = self.proc.poll()
        if code is None:
            self.started_ok = True
            return
        self.deiconify()
        tail = ""
        try:
            self.log_handle.flush()
            tail = "\n".join(LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
        except OSError:
            pass
        messagebox.showerror("Launcher", tr("early_exit", code=code, tail=tail or tr("empty")))

    def poll_game(self):
        if self.proc is not None and self.proc.poll() is not None and getattr(self, "started_ok", False):
            self.proc = None
            self.log_handle.close()
            self.deiconify()
            self.flash(tr("game_closed"))
            self.refresh_status()  # pode ter gravado programas de VU1 novos
        self.update_play_button()
        self.after(1500, self.poll_game)

    # ---------- utilidades

    def pick_iso(self):
        p = filedialog.askopenfilename(title=tr("pick_iso"),
                                       filetypes=[(tr("disc_image"), "*.iso"), (tr("all_files"), "*.*")])
        if p:
            self.iso_var.set(os.path.normpath(p))

    def pick_dir(self):
        p = filedialog.askdirectory(title=tr("pick_port"))
        if p:
            self.port_var.set(os.path.normpath(p))
            self.load_ini()

    def open_game_dir(self):
        if self.game_dir().is_dir():
            os.startfile(self.game_dir())

    def open_log(self):
        if LOG_FILE.exists():
            os.startfile(LOG_FILE)
        else:
            self.flash(tr("no_log"))

    def open_ini(self):
        self.save_all(quiet=True)
        ini = self.game_dir() / "sotc.ini"
        if ini.exists():
            subprocess.Popen(["notepad.exe", str(ini)])

    def on_close(self):
        if self.preparing():
            if not messagebox.askyesno("Launcher", tr("close_confirm")):
                return
            self.prep_job.terminate()
        self.save_all(quiet=True)
        self.destroy()


def fmt_time(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60:02d} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


class KillOnCloseJob:
    """Um Job do Windows com o processo e tudo o que ele abrir (cmake, ninja, cl...): Parar fecha
    todos de uma vez, e se o launcher morrer o Windows fecha o Job junto."""

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                    ("SchedulingClass", ctypes.c_uint32)]

    class _Extended(ctypes.Structure):
        pass

    _Extended._fields_ = [("Basic", _Basic), ("IoInfo", ctypes.c_uint64 * 6),
                          ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                          ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    def __init__(self, process):
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = ctypes.c_void_p
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            return
        info = self._Extended()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.limits_ok = bool(k.SetInformationJobObject(ctypes.c_void_p(self.handle), 9,
                                                        ctypes.byref(info), ctypes.sizeof(info)))
        self.assigned = bool(k.AssignProcessToJobObject(ctypes.c_void_p(self.handle),
                                                        ctypes.c_void_p(int(process._handle))))

    def terminate(self):
        if self.handle:
            ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(self.handle), 1)

    def close(self):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    Launcher().mainloop()
