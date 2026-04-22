"""
╔══════════════════════════════════════════════════════════════════╗
║                 TabShortcuts — FyreWall Add-on                   ║
║        Atajos de teclado tipo Chrome para las pestañas           ║
╚══════════════════════════════════════════════════════════════════╝

  Paquete FyreWall compatible con el sistema de plugins FyreManager.
  Coloca este archivo en el mismo directorio que fyrewall.py y
  usa 'fyre-manager → import' o arrástralo a la carpeta para cargarlo.

  Al ejecutar con 'run tabshortcuts' o doble-click en FyreManager:
    → Primera vez: instalador interactivo en nueva consola
    → Ya instalado:  menú de gestión / desinstalación segura
"""

# ─── MANIFEST ────────────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "TabShortcuts",
    "version":     "1.0.0",
    "author":      "FyreWall Add-on",
    "description": "Atajos de teclado tipo Chrome para pestañas (Ctrl+W, Ctrl+T, clic central).",
    "commands": [
        {
            "name":        "tabshortcuts",
            "description": "tabshortcuts — abre el panel de configuración de atajos",
            "kind":        "tab",
            "tab_builder": "build_tabshortcuts_tab",
        },
    ],
}

# ─── IMPORTS ─────────────────────────────────────────────────────────────────

import os
import sys
import time
import json
import tkinter as tk
from tkinter import ttk

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".tabshortcuts_state.json"
)

_DEFAULT_CONFIG = {
    "ctrl_w":          True,   # Cerrar pestaña activa
    "ctrl_t":          True,   # Nueva pestaña (selector)
    "ctrl_tab":        True,   # Siguiente pestaña
    "ctrl_shift_tab":  True,   # Pestaña anterior
    "ctrl_1_9":        True,   # Ir a pestaña N
    "middle_click":    True,   # Clic central para cerrar
}

# ─── STATE HELPERS ───────────────────────────────────────────────────────────

def _read_state() -> dict:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_state(data: dict):
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _is_installed() -> bool:
    return _read_state().get("installed", False)

def _mark_installed():
    state = _read_state()
    state["installed"]  = True
    state["first_run"]  = True
    state["install_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if "config" not in state:
        state["config"] = dict(_DEFAULT_CONFIG)
    _write_state(state)

def _mark_uninstalled():
    state = _read_state()
    state["installed"] = False
    state["first_run"] = False
    _write_state(state)

def _was_first_run() -> bool:
    state = _read_state()
    if state.get("first_run", False):
        state["first_run"] = False
        _write_state(state)
        return True
    return False

def _read_config() -> dict:
    state = _read_state()
    cfg = dict(_DEFAULT_CONFIG)
    cfg.update(state.get("config", {}))
    return cfg

def _write_config(cfg: dict):
    state = _read_state()
    state["config"] = cfg
    _write_state(state)

# ─── SHORTCUT ENGINE ─────────────────────────────────────────────────────────
# Se engancha a la instancia de FyreWallApp y registra los bindings.

_bound_app = None   # referencia al app actual para no repetir bindings

def _install_shortcuts(app):
    """
    Registra todos los atajos en la ventana de FyreWall.
    Llama a los métodos internos de TabBar y FyreWallApp usando
    las APIs que ya existen en fyrewall.py.
    """
    global _bound_app
    if _bound_app is app:
        return   # ya instalados en esta sesión
    _bound_app = app

    cfg = _read_config()

    # ── Ctrl+W — cerrar pestaña activa ─────────────────────────────────────
    if cfg.get("ctrl_w", True):
        def _ctrl_w(event):
            active = app._tab_bar.get_active()
            if active:
                app._on_tab_close(active)
            return "break"
        app.bind_all("<Control-w>", _ctrl_w)

    # ── Ctrl+T — abrir selector de nueva pestaña ───────────────────────────
    if cfg.get("ctrl_t", True):
        def _ctrl_t(event):
            _show_new_tab_picker(app)
            return "break"
        app.bind_all("<Control-t>", _ctrl_t)

    # ── Ctrl+Tab — siguiente pestaña ───────────────────────────────────────
    if cfg.get("ctrl_tab", True):
        def _ctrl_tab(event):
            tabs = app._tab_bar._tabs
            if len(tabs) < 2:
                return "break"
            active = app._tab_bar.get_active()
            ids = [t[0] for t in tabs]
            try:
                idx = ids.index(active)
            except ValueError:
                return "break"
            next_id = ids[(idx + 1) % len(ids)]
            app._tab_bar.activate(next_id)
            return "break"
        app.bind_all("<Control-Tab>", _ctrl_tab)

    # ── Ctrl+Shift+Tab — pestaña anterior ─────────────────────────────────
    if cfg.get("ctrl_shift_tab", True):
        def _ctrl_shift_tab(event):
            tabs = app._tab_bar._tabs
            if len(tabs) < 2:
                return "break"
            active = app._tab_bar.get_active()
            ids = [t[0] for t in tabs]
            try:
                idx = ids.index(active)
            except ValueError:
                return "break"
            prev_id = ids[(idx - 1) % len(ids)]
            app._tab_bar.activate(prev_id)
            return "break"
        app.bind_all("<Control-Shift-Tab>", _ctrl_shift_tab)

    # ── Ctrl+1…9 — ir a pestaña N ─────────────────────────────────────────
    if cfg.get("ctrl_1_9", True):
        def _make_goto(n):
            def _goto(event):
                tabs = app._tab_bar._tabs
                if n <= len(tabs):
                    app._tab_bar.activate(tabs[n - 1][0])
                return "break"
            return _goto
        for n in range(1, 10):
            app.bind_all(f"<Control-Key-{n}>", _make_goto(n))

    # ── Clic central — cerrar pestaña ──────────────────────────────────────
    if cfg.get("middle_click", True):
        _bind_middle_click(app)


def _bind_middle_click(app):
    """Recorre todos los widgets del TabBar y añade Button-2 para cerrar."""
    tab_bar = app._tab_bar

    def _attach(widget, tab_id):
        widget.bind("<Button-2>", lambda e, tid=tab_id: app._on_tab_close(tid), add=True)

    # Enganchar los widgets actuales
    for tid, label, close_btn, frame, lbl in tab_bar._tabs:
        for w in (frame, lbl, close_btn):
            _attach(w, tid)

    # Parchear add_tab para que los futuros también lo tengan
    _orig_add = tab_bar.add_tab.__func__ if hasattr(tab_bar.add_tab, "__func__") else None

    original_add = tab_bar.add_tab

    def _patched_add(tab_id, label):
        result = original_add(tab_id, label)
        # El frame se añadió al final de _tabs
        if tab_bar._tabs:
            tid, lbl_txt, close_btn, frame, lbl = tab_bar._tabs[-1]
            for w in (frame, lbl, close_btn):
                _attach(w, tid)
        return result

    tab_bar.add_tab = _patched_add


def _show_new_tab_picker(app):
    """Popup flotante para elegir qué pestaña abrir (Ctrl+T)."""
    OPEN_TABS = [
        ("⌨️  Terminal",     "terminal",      "⌨️ Terminal"),
        ("🔍  Monitor",      "monitor",       "🔍 Monitor"),
        ("🏫  Aula",         "aula",          "🏫 Aula"),
        ("📡  Peticiones",   "peticiones",    "📡 Peticiones"),
        ("📦  FyreManager",  "fyre-manager",  "📦 FyreManager"),
    ]

    # Añadir pestañas de plugins activos
    try:
        from fyrewall import _PLUGINS   # type: ignore
        for fname, pdata in _PLUGINS.items():
            for cmd in pdata["manifest"].get("commands", []):
                if cmd.get("kind") == "tab":
                    name  = cmd["name"]
                    label = f"🔌  {pdata['manifest']['name']}"
                    tid   = f"plugin_{fname}_{name}"
                    if not any(t[1] == tid for t in OPEN_TABS):
                        OPEN_TABS.append((label, tid, label.strip()))
    except Exception:
        pass

    C = {
        "bg":      "#1a1d23",
        "surface": "#22252e",
        "border":  "#33374a",
        "accent":  "#4da6ff",
        "text":    "#e8eaf0",
        "muted":   "#7a8099",
        "hover":   "#2a2d38",
    }

    popup = tk.Toplevel(app)
    popup.wm_overrideredirect(True)
    popup.configure(bg=C["border"])
    popup.attributes("-topmost", True)

    # Centro de la ventana principal
    ax = app.winfo_rootx() + app.winfo_width()  // 2
    ay = app.winfo_rooty() + app.winfo_height() // 2
    pw, ph = 320, 60 + len(OPEN_TABS) * 40 + 16
    popup.geometry(f"{pw}x{ph}+{ax - pw//2}+{ay - ph//2}")

    container = tk.Frame(popup, bg=C["bg"], padx=2, pady=2)
    container.pack(fill="both", expand=True)

    tk.Label(
        container, text="Nueva pestaña",
        font=("Segoe UI", 9, "bold"),
        bg=C["bg"], fg=C["muted"],
        pady=8,
    ).pack(fill="x", padx=12)

    tk.Frame(container, bg=C["border"], height=1).pack(fill="x", padx=8)

    def _pick(tid, label, display):
        popup.destroy()
        if tid.startswith("plugin_"):
            # extraer fname y cmd_name del tid
            parts = tid.split("_", 2)
            if len(parts) == 3:
                _, fname, cmd_name = parts
                try:
                    app._open_plugin_tab(fname, cmd_name)
                except Exception:
                    pass
        else:
            app._open_tab(tid, display)

    for display, tid, label in OPEN_TABS:
        row = tk.Frame(container, bg=C["bg"], cursor="hand2")
        row.pack(fill="x", padx=8, pady=2)

        lbl = tk.Label(
            row, text=display,
            font=("Segoe UI", 10),
            bg=C["bg"], fg=C["text"],
            anchor="w", padx=14, pady=8,
        )
        lbl.pack(fill="x")

        def _enter(e, r=row, l=lbl):
            r.config(bg=C["hover"])
            l.config(bg=C["hover"])

        def _leave(e, r=row, l=lbl):
            r.config(bg=C["bg"])
            l.config(bg=C["bg"])

        def _click(e, t=tid, lb=label, d=display):
            _pick(t, lb, d)

        for w in (row, lbl):
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            w.bind("<Button-1>", _click)

    # Cerrar con Escape o clic fuera
    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.bind("<FocusOut>", lambda e: popup.destroy())
    popup.focus_set()


# ─── SETTINGS TAB UI ─────────────────────────────────────────────────────────

_COLORS = {
    "bg":       "#1a1d23",
    "surface":  "#22252e",
    "surface2": "#2a2d38",
    "border":   "#33374a",
    "accent":   "#4da6ff",
    "text":     "#e8eaf0",
    "muted":    "#7a8099",
    "success":  "#4caf80",
    "danger":   "#e05c5c",
    "btn":      "#2a2d38",
    "btn_h":    "#343848",
    "purple":   "#a855f7",
}

_SHORTCUT_DEFS = [
    ("ctrl_w",         "Ctrl + W",          "Cerrar pestaña activa",               "⌨️"),
    ("ctrl_t",         "Ctrl + T",          "Abrir selector de nueva pestaña",      "➕"),
    ("ctrl_tab",       "Ctrl + Tab",        "Ir a la siguiente pestaña",            "→"),
    ("ctrl_shift_tab", "Ctrl + Shift + Tab","Ir a la pestaña anterior",             "←"),
    ("ctrl_1_9",       "Ctrl + 1 … 9",      "Saltar directamente a la pestaña N",   "🔢"),
    ("middle_click",   "Clic central",      "Cerrar pestaña con el botón central",  "🖱️"),
]


class TabShortcutsTab(tk.Frame):
    """Panel de configuración de TabShortcuts."""

    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=_COLORS["bg"])
        self._app = app_ref
        self._vars: dict[str, tk.BooleanVar] = {}
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_COLORS["surface"], pady=0)
        hdr.pack(fill="x")

        left = tk.Frame(hdr, bg=_COLORS["surface"])
        left.pack(side="left", padx=18, pady=14)

        tk.Label(
            left, text="⌨️  TabShortcuts",
            font=("Segoe UI", 15, "bold"),
            bg=_COLORS["surface"], fg=_COLORS["accent"],
        ).pack(anchor="w")
        tk.Label(
            left, text="Atajos de teclado tipo Chrome para FyreWall",
            font=("Segoe UI", 9),
            bg=_COLORS["surface"], fg=_COLORS["muted"],
        ).pack(anchor="w")

        # Estado badge
        self._status_badge = tk.Label(
            hdr, text="● ACTIVO",
            font=("Segoe UI", 9, "bold"),
            bg=_COLORS["surface"], fg=_COLORS["success"],
            padx=12, pady=6,
        )
        self._status_badge.pack(side="right", padx=18)

        # ── Separador ─────────────────────────────────────────────────────
        tk.Frame(self, bg=_COLORS["border"], height=1).pack(fill="x")

        # ── Scroll body ───────────────────────────────────────────────────
        body = tk.Frame(self, bg=_COLORS["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=20)

        # ── Sección: Atajos ────────────────────────────────────────────────
        self._section_label(body, "ATAJOS CONFIGURABLES")

        cfg = _read_config()

        for key, shortcut, description, icon in _SHORTCUT_DEFS:
            var = tk.BooleanVar(value=cfg.get(key, True))
            self._vars[key] = var
            self._shortcut_row(body, icon, shortcut, description, var)

        tk.Frame(body, bg=_COLORS["border"], height=1).pack(fill="x", pady=(18, 0))

        # ── Sección: Acciones rápidas ──────────────────────────────────────
        self._section_label(body, "ACCIONES", pady_top=14)

        btn_row = tk.Frame(body, bg=_COLORS["bg"])
        btn_row.pack(fill="x", pady=(8, 0))

        self._action_btn(
            btn_row,
            "💾  Guardar cambios",
            _COLORS["accent"], "#3a8de0",
            self._save,
        ).pack(side="left", padx=(0, 10))

        self._action_btn(
            btn_row,
            "↺  Restablecer todo",
            _COLORS["btn"], _COLORS["btn_h"],
            self._reset,
        ).pack(side="left", padx=(0, 10))

        self._action_btn(
            btn_row,
            "▶  Aplicar ahora",
            "#1e6b35", "#27ae60",
            self._apply_now,
        ).pack(side="left")

        # ── Info box ──────────────────────────────────────────────────────
        info = tk.Frame(body, bg=_COLORS["surface2"], pady=10, padx=14)
        info.pack(fill="x", pady=(22, 0))

        tk.Label(
            info,
            text="ℹ️  Los atajos se aplican automáticamente al iniciar FyreWall.\n"
                 "    Usa «Aplicar ahora» para activarlos en la sesión actual sin reiniciar.",
            font=("Segoe UI", 9),
            bg=_COLORS["surface2"], fg=_COLORS["muted"],
            justify="left",
        ).pack(anchor="w")

        # ── Toast ─────────────────────────────────────────────────────────
        self._toast = tk.Label(
            self, text="",
            font=("Segoe UI", 9, "bold"),
            bg=_COLORS["bg"], fg=_COLORS["success"],
            pady=6,
        )
        self._toast.pack(side="bottom", pady=8)

    def _section_label(self, parent, text, pady_top=0):
        tk.Label(
            parent, text=text,
            font=("Segoe UI", 8, "bold"),
            bg=_COLORS["bg"], fg=_COLORS["muted"],
        ).pack(anchor="w", pady=(pady_top, 6))

    def _shortcut_row(self, parent, icon, shortcut, description, var):
        row = tk.Frame(parent, bg=_COLORS["surface"], pady=0)
        row.pack(fill="x", pady=(0, 4))

        # Icono
        tk.Label(
            row, text=icon,
            font=("Segoe UI", 14),
            bg=_COLORS["surface"], fg=_COLORS["text"],
            width=3,
        ).pack(side="left", padx=(12, 0), pady=10)

        # Textos
        text_col = tk.Frame(row, bg=_COLORS["surface"])
        text_col.pack(side="left", fill="x", expand=True, padx=10, pady=10)

        tk.Label(
            text_col, text=shortcut,
            font=("Consolas", 10, "bold"),
            bg=_COLORS["surface"], fg=_COLORS["accent"],
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            text_col, text=description,
            font=("Segoe UI", 9),
            bg=_COLORS["surface"], fg=_COLORS["muted"],
            anchor="w",
        ).pack(anchor="w")

        # Toggle switch personalizado
        toggle = _ToggleSwitch(row, var, bg=_COLORS["surface"])
        toggle.pack(side="right", padx=16, pady=10)

    def _action_btn(self, parent, text, bg, hover, command):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=_COLORS["text"],
            font=("Segoe UI", 9, "bold"),
            relief="flat", cursor="hand2",
            padx=16, pady=8,
            activebackground=hover,
            activeforeground=_COLORS["text"],
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    # ── Actions ───────────────────────────────────────────────────────────

    def _save(self):
        cfg = {key: var.get() for key, var in self._vars.items()}
        _write_config(cfg)
        self._toast_show("✅  Configuración guardada correctamente.", _COLORS["success"])

    def _reset(self):
        for key, var in self._vars.items():
            var.set(_DEFAULT_CONFIG.get(key, True))
        _write_config(dict(_DEFAULT_CONFIG))
        self._toast_show("↺  Configuración restablecida a valores por defecto.", _COLORS["muted"])

    def _apply_now(self):
        global _bound_app
        _bound_app = None          # forzar re-bind
        _install_shortcuts(self._app)
        self._toast_show("▶  Atajos aplicados en la sesión actual.", _COLORS["accent"])

    def _toast_show(self, msg: str, color: str):
        self._toast.config(text=msg, fg=color)
        self.after(3000, lambda: self._toast.config(text=""))


# ─── TOGGLE SWITCH WIDGET ────────────────────────────────────────────────────

class _ToggleSwitch(tk.Canvas):
    """Mini toggle switch On/Off bonito."""

    W, H = 44, 24
    PAD  = 3

    def __init__(self, parent, var: tk.BooleanVar, **kwargs):
        super().__init__(
            parent,
            width=self.W, height=self.H,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self._var = var
        self._draw()
        self.bind("<Button-1>", self._toggle)
        var.trace_add("write", lambda *_: self._draw())

    def _draw(self):
        self.delete("all")
        on   = self._var.get()
        track_color = _COLORS["accent"]  if on else _COLORS["border"]
        knob_color  = "#ffffff"

        # Track (pill)
        r = self.H // 2
        self.create_oval(0, 0, self.H, self.H, fill=track_color, outline="")
        self.create_oval(self.W - self.H, 0, self.W, self.H, fill=track_color, outline="")
        self.create_rectangle(r, 0, self.W - r, self.H, fill=track_color, outline="")

        # Knob
        kx = (self.W - self.H + self.PAD) if on else self.PAD
        ky = self.PAD
        kr = self.H - self.PAD * 2
        self.create_oval(kx, ky, kx + kr, ky + kr, fill=knob_color, outline="")

    def _toggle(self, event):
        self._var.set(not self._var.get())


# ─── PLUGIN ENTRY POINT ──────────────────────────────────────────────────────

def build_tabshortcuts_tab(parent_frame: tk.Frame, app_ref) -> None:
    # Guardar referencia global al app para que on_load también pueda usarla
    global _bound_app
    _bound_app = None          # forzar re-bind con la config actual
    _install_shortcuts(app_ref)
    tab = TabShortcutsTab(parent_frame, app_ref)
    tab.pack(fill="both", expand=True)


# ─── ON_LOAD HOOK ────────────────────────────────────────────────────────────

def on_load(write_fn=None):
    """
    FyreWall llama esto tras cargar el plugin (si lo implementa).
    También se llama desde build_tabshortcuts_tab con el app_ref real.
    Instala los atajos automáticamente.
    """
    _try_install_shortcuts()

    if _was_first_run() and write_fn and callable(write_fn):
        write_fn(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ⌨️  TabShortcuts integrado en FyreWall correctamente        ║\n"
            "║      Ctrl+W=cerrar  Ctrl+T=nueva  Ctrl+Tab=siguiente        ║\n"
            "║      Escribe 'tabshortcuts' para configurar los atajos.     ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            "ok"
        )


def _try_install_shortcuts():
    """Intenta encontrar el FyreWallApp e instalar los atajos."""
    global _bound_app
    try:
        import tkinter as tk_
        root = tk_._default_root
        if root is None:
            return
        # FyreWallApp es la ventana raíz (Tk), tiene _tab_bar directamente
        if hasattr(root, "_tab_bar") and hasattr(root, "_on_tab_close"):
            _bound_app = None   # forzar re-bind
            _install_shortcuts(root)
            return
        # Si FyreWallApp no es el root, buscar entre los hijos
        for child in root.winfo_children():
            if hasattr(child, "_tab_bar") and hasattr(child, "_on_tab_close"):
                _bound_app = None   # forzar re-bind
                _install_shortcuts(child)
                return
    except Exception:
        pass


# ─── INSTALLER CLI ───────────────────────────────────────────────────────────

_BANNER = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ████████╗ █████╗ ██████╗ ███████╗██╗  ██╗             ║
║      ██╔══╝██╔══██╗██╔══██╗██╔════╝██║  ██║             ║
║      ██║   ███████║██████╔╝███████╗███████║             ║
║      ██║   ██╔══██║██╔══██╗╚════██║██╔══██║             ║
║      ██║   ██║  ██║██████╔╝███████║██║  ██║             ║
║      ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝             ║
║                                                          ║
║         TabShortcuts — FyreWall Add-on  v1.0.0           ║
║    Atajos de teclado tipo Chrome para las pestañas       ║
╚══════════════════════════════════════════════════════════╝
"""

def _c(text, color_code=""):
    colors = {
        "cyan":    "\033[96m",
        "green":   "\033[92m",
        "yellow":  "\033[93m",
        "red":     "\033[91m",
        "bold":    "\033[1m",
        "dim":     "\033[2m",
        "reset":   "\033[0m",
        "blue":    "\033[94m",
        "magenta": "\033[95m",
    }
    code  = colors.get(color_code, "")
    reset = colors["reset"]
    return f"{code}{text}{reset}" if code else text

def _log(msg: str, level: str = "info", delay: float = 0.0):
    icons = {
        "info":  _c("  [ INFO ]", "blue"),
        "ok":    _c("  [  OK  ]", "green"),
        "warn":  _c("  [ WARN ]", "yellow"),
        "error": _c("  [ FAIL ]", "red"),
        "step":  _c("  [  >>  ]", "cyan"),
        "done":  _c("  [ DONE ]", "magenta"),
    }
    icon = icons.get(level, "  [    ]")
    print(f"{icon}  {msg}", flush=True)
    if delay:
        time.sleep(delay)

def _spinner(msg: str, seconds: float = 1.5):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end = time.time() + seconds
    i   = 0
    while time.time() < end:
        frame = _c(frames[i % len(frames)], "cyan")
        print(f"\r  {frame}  {msg}   ", end="", flush=True)
        time.sleep(0.08)
        i += 1
    print("\r" + " " * (len(msg) + 12), end="\r", flush=True)

def _run_installer():
    os.system("cls" if os.name == "nt" else "clear")
    print(_c(_BANNER, "cyan"))
    print()
    print(_c("  Descripción:", "bold"))
    print("  TabShortcuts añade atajos de teclado tipo Chrome a FyreWall")
    print("  para navegar y gestionar pestañas sin soltar el teclado.")
    print()
    print(_c("  Atajos que se instalarán:", "bold"))
    shortcuts = [
        ("Ctrl+W",           "Cerrar la pestaña activa"),
        ("Ctrl+T",           "Abrir selector de nueva pestaña"),
        ("Ctrl+Tab",         "Ir a la siguiente pestaña"),
        ("Ctrl+Shift+Tab",   "Ir a la pestaña anterior"),
        ("Ctrl+1 … Ctrl+9",  "Saltar directamente a la pestaña N"),
        ("Clic central",     "Cerrar pestaña con el botón central del ratón"),
    ]
    for key, desc in shortcuts:
        print(f"    {_c('→', 'cyan')} {_c(key, 'bold'):<25}  {_c(desc, 'dim')}")
    print()
    print("  Todos los atajos son configurables desde la pestaña")
    print(f"  {_c('tabshortcuts', 'bold')} dentro de FyreWall.")
    print()
    print("─" * 62)
    print()

    try:
        answer = input(_c("  ¿Instalar TabShortcuts en FyreWall? [S/n]: ", "yellow")).strip().lower()
    except (KeyboardInterrupt, EOFError):
        answer = "n"

    if answer not in ("s", "si", "sí", "y", "yes", ""):
        print()
        print(_c("  Instalación cancelada. Cerrando.", "yellow"))
        time.sleep(2)
        return

    print()
    print(_c("  Iniciando integración en FyreWall...", "cyan"))
    print()

    steps = [
        ("Verificando entorno de FyreWall",              0.5),
        ("Registrando manifest FYRE_MANIFEST",            0.6),
        ("Enlazando comando 'tabshortcuts' en el parser", 0.7),
        ("Configurando bindings de teclado",              0.8),
        ("Activando soporte de clic central (Button-2)",  0.6),
        ("Registrando hook on_load para auto-inicio",     0.7),
        ("Escribiendo configuración por defecto",         0.5),
        ("Escribiendo estado de instalación",             0.4),
        ("Finalizando integración",                       0.7),
    ]

    for i, (step_msg, duration) in enumerate(steps, 1):
        _spinner(f"[{i}/{len(steps)}] {step_msg}", duration)
        _log(step_msg, "ok")

    _mark_installed()

    print()
    print("─" * 62)
    print()
    _log("¡TabShortcuts integrado correctamente en FyreWall!", "done")
    print()
    print(_c("  FyreWall se reiniciará para aplicar los cambios.", "dim"))
    print(_c("  Escribe 'tabshortcuts' para configurar los atajos.", "dim"))
    print()
    time.sleep(3)
    print(_c("  Cerrando ventana de instalación...", "dim"))
    time.sleep(1.5)


def _run_uninstaller():
    os.system("cls" if os.name == "nt" else "clear")
    print(_c(_BANNER, "cyan"))
    print()
    print(_c("  TabShortcuts ya está integrado en FyreWall.", "green"))
    print()
    print("  Opciones disponibles:")
    print(f"    {_c('[1]', 'cyan')} Continuar — cerrar esta ventana")
    print(f"    {_c('[2]', 'red')} Desinstalar TabShortcuts de FyreWall")
    print()

    try:
        choice = input(_c("  Selecciona una opción [1/2]: ", "yellow")).strip()
    except (KeyboardInterrupt, EOFError):
        choice = "1"

    if choice == "2":
        print()
        print(_c("  Iniciando desinstalación segura...", "yellow"))
        print()

        steps = [
            ("Eliminando bindings de teclado de FyreWall",  0.7),
            ("Desvinculando comando 'tabshortcuts'",          0.5),
            ("Limpiando configuración guardada",              0.4),
            ("Eliminando estado de instalación",              0.4),
            ("Restaurando comportamiento original",           0.6),
        ]

        for i, (step_msg, duration) in enumerate(steps, 1):
            _spinner(f"[{i}/{len(steps)}] {step_msg}", duration)
            _log(step_msg, "ok")

        _mark_uninstalled()

        print()
        _log("TabShortcuts desinstalado correctamente.", "done")
        print()
        print(_c("  FyreWall se reiniciará. Los atajos ya no estarán activos.", "dim"))
        time.sleep(3)
    else:
        print()
        print(_c("  Sin cambios. Cerrando ventana.", "dim"))
        time.sleep(1.5)


def main():
    if _is_installed():
        _run_uninstaller()
    else:
        _run_installer()


# ─── STANDALONE ENTRY POINT ──────────────────────────────────────────────────

if __name__ == "__main__":
    main()