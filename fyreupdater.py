"""
FyreUpdater — Plugin de actualización para FyreWall
=====================================================
Comprueba y descarga actualizaciones desde GitHub para:
  - fyrewall.py        (repo principal: luckicla/FyreWall)
  - add-ons instalados (repo add-ons:   luckicla/FyreWall-add-ons)

Integración en FyreManager:
  - Botón azul "🔄 Actualizar" en la UI del gestor (a la izquierda del rojo)
  - Comando CLI: get-update

Pestaña propia: "🔄 Instalador"
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error
import json
import shutil
import hashlib

# ── Manifest FyreWall ──────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "FyreUpdater",
    "version":     "1.0.0",
    "author":      "FyreWall",
    "description": "Actualiza FyreWall y sus add-ons desde GitHub",
    "commands": [
        {
            "name":        "get-update",
            "kind":        "tab",
            "tab_builder": "_build_updater_tab",
            "description": "Abre el instalador / actualizador de FyreWall",
        },
    ],
}

# ── GitHub config ─────────────────────────────────────────────────────────────

GITHUB_API   = "https://api.github.com"
RAW_BASE     = "https://raw.githubusercontent.com"

MAIN_REPO    = "luckicla/FyreWall"
ADDONS_REPO  = "luckicla/FyreWall-add-ons"

MAIN_FILE    = "fyrewall.py"
ADDONS_FILES = ["dayus.py", "ipmanager.py", "tabshortcuts.py"]

APP_DIR      = os.path.dirname(os.path.abspath(sys.argv[0]))

# ── Colors (mirror fyrewall.py theme) ─────────────────────────────────────────

C = {
    "bg":           "#1a1d23",
    "surface":      "#22252e",
    "surface2":     "#2a2d38",
    "border":       "#33374a",
    "accent":       "#4da6ff",
    "accent_h":     "#6ab8ff",
    "text":         "#e8eaf0",
    "muted":        "#7a8099",
    "ok":           "#4caf80",
    "warn":         "#f5a623",
    "danger":       "#e05c5c",
    "btn":          "#2a2d38",
    "btn_h":        "#343848",
    "red_btn":      "#8b2020",
    "red_act":      "#c0392b",
    "blue_btn":     "#1a4a8a",
    "blue_act":     "#2563c0",
    "console_bg":   "#0e1117",
    "console_text": "#c9d1d9",
}
F_MONO  = ("Consolas", 9)
F_BODY  = ("Segoe UI", 9)
F_BOLD  = ("Segoe UI", 9, "bold")
F_TITLE = ("Segoe UI", 12, "bold")
F_LBL   = ("Segoe UI", 8, "bold")

# ── App reference (set by fyrewall.py boot) ────────────────────────────────────

_app_ref = None

def _set_app(app):
    global _app_ref
    _app_ref = app

# ── GitHub helpers ────────────────────────────────────────────────────────────

def _api_get(path: str) -> dict | list | None:
    """GET from GitHub API. Returns parsed JSON or None on error."""
    url = f"{GITHUB_API}/{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json",
                                                "User-Agent": "FyreUpdater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _raw_get(repo: str, branch: str, filepath: str) -> bytes | None:
    """Download raw file from GitHub."""
    url = f"{RAW_BASE}/{repo}/{branch}/{filepath}"
    req = urllib.request.Request(url, headers={"User-Agent": "FyreUpdater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _local_sha256(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return _sha256(f.read())
    except Exception:
        return None


def _get_remote_sha(repo: str, branch: str, filepath: str) -> str | None:
    """Get SHA-256 of the remote file (by downloading it)."""
    data = _raw_get(repo, branch, filepath)
    if data is None:
        return None
    return _sha256(data)


# ── Update check ──────────────────────────────────────────────────────────────

def check_all_updates() -> dict:
    """
    Returns a dict with update status for all tracked files.
    {
      "fyrewall.py": {"status": "update"|"ok"|"error", "remote_sha": ..., "local_sha": ...},
      "dayus.py":    {"status": "update"|"ok"|"missing"|"error", ...},
      ...
    }
    """
    results = {}

    # ── Main app ─────────────────────────────────────────────────────────
    local_path = os.path.join(APP_DIR, MAIN_FILE)
    local_sha  = _local_sha256(local_path)
    remote_data = _raw_get(MAIN_REPO, "main", MAIN_FILE)
    if remote_data is None:
        results[MAIN_FILE] = {"status": "error", "local_sha": local_sha, "remote_sha": None,
                               "repo": MAIN_REPO, "branch": "main", "file": MAIN_FILE}
    else:
        remote_sha = _sha256(remote_data)
        if local_sha == remote_sha:
            results[MAIN_FILE] = {"status": "ok", "local_sha": local_sha, "remote_sha": remote_sha,
                                   "repo": MAIN_REPO, "branch": "main", "file": MAIN_FILE,
                                   "_data": remote_data}
        else:
            results[MAIN_FILE] = {"status": "update", "local_sha": local_sha, "remote_sha": remote_sha,
                                   "repo": MAIN_REPO, "branch": "main", "file": MAIN_FILE,
                                   "_data": remote_data}

    # ── Add-ons ──────────────────────────────────────────────────────────
    for fname in ADDONS_FILES:
        local_path = os.path.join(APP_DIR, fname)
        local_exists = os.path.exists(local_path)
        local_sha = _local_sha256(local_path) if local_exists else None
        remote_data = _raw_get(ADDONS_REPO, "main", fname)
        if remote_data is None:
            results[fname] = {"status": "error", "local_sha": local_sha, "remote_sha": None,
                               "local_exists": local_exists, "repo": ADDONS_REPO,
                               "branch": "main", "file": fname}
            continue
        remote_sha = _sha256(remote_data)
        if not local_exists:
            results[fname] = {"status": "missing", "local_sha": None, "remote_sha": remote_sha,
                               "local_exists": False, "repo": ADDONS_REPO,
                               "branch": "main", "file": fname, "_data": remote_data}
        elif local_sha == remote_sha:
            results[fname] = {"status": "ok", "local_sha": local_sha, "remote_sha": remote_sha,
                               "local_exists": True, "repo": ADDONS_REPO,
                               "branch": "main", "file": fname, "_data": remote_data}
        else:
            results[fname] = {"status": "update", "local_sha": local_sha, "remote_sha": remote_sha,
                               "local_exists": True, "repo": ADDONS_REPO,
                               "branch": "main", "file": fname, "_data": remote_data}

    return results


def apply_update(info: dict) -> tuple[bool, str]:
    """Download and overwrite the file. Returns (ok, message)."""
    data = info.get("_data")
    if data is None:
        # Re-download
        data = _raw_get(info["repo"], info["branch"], info["file"])
    if data is None:
        return False, f"No se pudo descargar {info['file']}"
    dest = os.path.join(APP_DIR, info["file"])
    # Backup
    bak = dest + ".bak"
    if os.path.exists(dest):
        try:
            shutil.copy2(dest, bak)
        except Exception:
            pass
    try:
        with open(dest, "wb") as f:
            f.write(data)
        return True, f"✅ {info['file']} actualizado correctamente."
    except Exception as e:
        # Restore backup
        if os.path.exists(bak):
            shutil.copy2(bak, dest)
        return False, f"❌ Error al escribir {info['file']}: {e}"


# ── Installer / Updater Tab ───────────────────────────────────────────────────

class UpdaterTab(tk.Frame):
    """Pestaña 'Instalador' completa con comprobación y aplicación de updates."""

    STATUS_ICONS = {
        "ok":      ("✅", C["ok"]),
        "update":  ("⬆️", C["warn"]),
        "missing": ("📥", C["accent"]),
        "error":   ("❌", C["danger"]),
        "loading": ("⏳", C["muted"]),
    }

    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg=C["bg"])
        self._app = app_ref or _app_ref
        self._check_results: dict = {}
        self._row_widgets: dict = {}   # fname → dict of label refs
        self._checking = False
        self._build()
        self.after(300, self._do_check)   # auto-check on open

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["surface"], pady=10, padx=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="🔄  FyreUpdater",
                 font=F_TITLE, bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Label(hdr, text="  —  Actualiza FyreWall y sus add-ons desde GitHub",
                 font=F_BODY, bg=C["surface"], fg=C["muted"]).pack(side="left")

        # Right: reload button
        self._reload_btn = tk.Button(
            hdr, text="↺  Recargar",
            command=self._do_check,
            bg=C["btn"], fg=C["muted"],
            font=F_BODY, relief="flat", cursor="hand2",
            padx=10, pady=4,
            activebackground=C["btn_h"],
        )
        self._reload_btn.pack(side="right")

        # ── Status banner (updates available / all ok) ─────────────────
        self._banner_frame = tk.Frame(self, bg=C["warn"], pady=0)
        # Hidden initially, shown after check

        self._banner_lbl = tk.Label(
            self._banner_frame,
            text="",
            font=F_BOLD, bg=C["warn"], fg="#000000",
            padx=16, pady=8,
        )
        self._banner_lbl.pack(side="left")

        self._update_all_btn = tk.Button(
            self._banner_frame,
            text="⬆️  Actualizar todo",
            command=self._update_all,
            bg="#7a5000", fg="#ffffff",
            font=F_BOLD, relief="flat", cursor="hand2",
            padx=12, pady=6,
            activebackground="#9a6500",
        )
        self._update_all_btn.pack(side="right", padx=12, pady=4)

        # ── Content: two sections ─────────────────────────────────────────
        scroll_outer = tk.Frame(self, bg=C["bg"])
        scroll_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_outer, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * int(e.delta / 120), "units"))

        # Section: Main app
        self._build_section("🔥  FYREWALL PRINCIPAL", [MAIN_FILE], "main")
        # Separator
        tk.Frame(self._inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)
        # Section: Add-ons
        self._build_section("📦  ADD-ONS", ADDONS_FILES, "addons")

        # ── Log area ──────────────────────────────────────────────────────
        log_hdr = tk.Frame(self._inner, bg=C["surface"], pady=6, padx=12)
        log_hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(log_hdr, text="REGISTRO", font=F_LBL, bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Button(log_hdr, text="🗑 Limpiar",
                  command=self._clear_log,
                  bg=C["btn"], fg=C["muted"],
                  font=("Segoe UI", 7), relief="flat", cursor="hand2",
                  padx=6, pady=2).pack(side="right")

        log_frame = tk.Frame(self._inner, bg=C["console_bg"])
        log_frame.pack(fill="x", padx=20, pady=(0, 20))

        self._log = tk.Text(
            log_frame,
            bg=C["console_bg"], fg=C["console_text"],
            font=F_MONO, relief="flat", bd=0,
            height=10, state="disabled", wrap="word", padx=10, pady=8,
        )
        log_sb = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        for tag, color in [("ok", C["ok"]), ("warn", C["warn"]), ("err", C["danger"]),
                            ("info", C["console_text"]), ("muted", C["muted"]),
                            ("header", C["accent"])]:
            self._log.tag_configure(tag, foreground=color)

    def _build_section(self, title: str, files: list, section_key: str):
        sec = tk.Frame(self._inner, bg=C["bg"], padx=20, pady=10)
        sec.pack(fill="x")

        hdr = tk.Frame(sec, bg=C["surface"], pady=8, padx=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=F_LBL, bg=C["surface"], fg=C["accent"]).pack(side="left")

        for fname in files:
            self._build_file_row(sec, fname)

    def _build_file_row(self, parent, fname: str):
        row = tk.Frame(parent, bg=C["surface2"], pady=0)
        row.pack(fill="x", pady=(1, 0))

        inner = tk.Frame(row, bg=C["surface2"], padx=12, pady=10)
        inner.pack(fill="x")

        # Status icon
        icon_lbl = tk.Label(inner, text="⏳", font=("Segoe UI", 14),
                             bg=C["surface2"], fg=C["muted"])
        icon_lbl.pack(side="left", padx=(0, 10))

        # File info
        info_col = tk.Frame(inner, bg=C["surface2"])
        info_col.pack(side="left", fill="x", expand=True)

        name_lbl = tk.Label(info_col, text=fname, font=F_BOLD,
                             bg=C["surface2"], fg=C["text"])
        name_lbl.pack(anchor="w")

        status_lbl = tk.Label(info_col, text="Comprobando...", font=F_BODY,
                               bg=C["surface2"], fg=C["muted"])
        status_lbl.pack(anchor="w")

        sha_lbl = tk.Label(info_col, text="", font=F_MONO,
                            bg=C["surface2"], fg=C["muted"])
        sha_lbl.pack(anchor="w")

        # Action buttons
        btn_frame = tk.Frame(inner, bg=C["surface2"])
        btn_frame.pack(side="right", padx=(8, 0))

        install_btn = tk.Button(
            btn_frame, text="📥 Instalar",
            command=lambda f=fname: self._install_single(f),
            bg=C["blue_btn"], fg="#ffffff",
            font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
            padx=8, pady=4, activebackground=C["blue_act"],
        )
        # Hidden by default, shown when needed
        install_btn.pack_forget()

        update_btn = tk.Button(
            btn_frame, text="⬆️ Actualizar",
            command=lambda f=fname: self._install_single(f),
            bg=C["blue_btn"], fg="#ffffff",
            font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
            padx=8, pady=4, activebackground=C["blue_act"],
        )
        update_btn.pack_forget()

        self._row_widgets[fname] = {
            "icon":       icon_lbl,
            "status_lbl": status_lbl,
            "sha_lbl":    sha_lbl,
            "install":    install_btn,
            "update":     update_btn,
            "row":        row,
            "inner":      inner,
        }

    # ── Check ─────────────────────────────────────────────────────────────

    def _do_check(self):
        if self._checking:
            return
        self._checking = True
        self._reload_btn.config(state="disabled", text="⏳ Comprobando...")
        self._log_write("🔍  Comprobando actualizaciones desde GitHub...", "header")

        # Reset all rows to loading state
        for fname, widgets in self._row_widgets.items():
            icon, color = self.STATUS_ICONS["loading"]
            widgets["icon"].config(text=icon, fg=color)
            widgets["status_lbl"].config(text="Comprobando...", fg=C["muted"])
            widgets["sha_lbl"].config(text="")
            widgets["install"].pack_forget()
            widgets["update"].pack_forget()

        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        results = check_all_updates()
        self.after(0, lambda r=results: self._render_check(r))

    def _render_check(self, results: dict):
        self._check_results = results
        self._checking = False
        self._reload_btn.config(state="normal", text="↺  Recargar")

        updates = 0
        missing = 0

        for fname, info in results.items():
            status = info["status"]
            widgets = self._row_widgets.get(fname)
            if not widgets:
                continue

            icon_txt, icon_color = self.STATUS_ICONS.get(status, ("❓", C["muted"]))
            widgets["icon"].config(text=icon_txt, fg=icon_color)
            widgets["install"].pack_forget()
            widgets["update"].pack_forget()

            lsha = (info.get("local_sha") or "—")[:12]
            rsha = (info.get("remote_sha") or "—")[:12]

            if status == "ok":
                widgets["status_lbl"].config(text="Al día", fg=C["ok"])
                widgets["sha_lbl"].config(text=f"SHA: {lsha}", fg=C["muted"])
                self._log_write(f"  ✅ {fname} — sin cambios.", "ok")

            elif status == "update":
                widgets["status_lbl"].config(
                    text="⚠️  Actualización disponible", fg=C["warn"])
                widgets["sha_lbl"].config(
                    text=f"Local: {lsha}  →  Remoto: {rsha}", fg=C["warn"])
                widgets["update"].pack(side="left", padx=(0, 4))
                self._log_write(f"  ⬆️  {fname} — actualización disponible.", "warn")
                updates += 1

            elif status == "missing":
                widgets["status_lbl"].config(
                    text="📥 Add-on no instalado (disponible en GitHub)", fg=C["accent"])
                widgets["sha_lbl"].config(text=f"Remoto: {rsha}", fg=C["muted"])
                widgets["install"].pack(side="left", padx=(0, 4))
                self._log_write(f"  📥 {fname} — no instalado, disponible.", "info")
                missing += 1

            elif status == "error":
                widgets["status_lbl"].config(text="❌ Error al comprobar", fg=C["danger"])
                widgets["sha_lbl"].config(text="Sin conexión o repo no disponible", fg=C["danger"])
                self._log_write(f"  ❌ {fname} — error de red.", "err")

        # ── Banner ────────────────────────────────────────────────────────
        total_pending = updates + missing
        if total_pending > 0:
            msg_parts = []
            if updates:
                msg_parts.append(f"{updates} actualización{'es' if updates != 1 else ''} disponible{'s' if updates != 1 else ''}")
            if missing:
                msg_parts.append(f"{missing} add-on{'s' if missing != 1 else ''} sin instalar")
            banner_text = "⚠️  " + "  •  ".join(msg_parts)
            self._banner_lbl.config(text=banner_text)
            self._banner_frame.config(bg=C["warn"])
            self._banner_lbl.config(bg=C["warn"])
            self._update_all_btn.pack(side="right", padx=12, pady=4)
            self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
            self._log_write(f"\n  → {total_pending} elemento(s) pendiente(s).", "warn")
        else:
            # All ok or errors only
            has_ok = any(i["status"] == "ok" for i in results.values())
            if has_ok:
                ver_text = "✅  Todo al día"
                self._banner_frame.config(bg=C["ok"])
                self._banner_lbl.config(text=ver_text, bg=C["ok"], fg="#000000")
                self._update_all_btn.pack_forget()
                self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
                self._log_write("\n  ✅ Todo está al día.", "ok")

    # ── Actions ───────────────────────────────────────────────────────────

    def _install_single(self, fname: str):
        info = self._check_results.get(fname)
        if not info:
            self._log_write(f"❌ No hay datos para {fname}", "err")
            return
        status = info["status"]
        action = "instalar" if status == "missing" else "actualizar"

        if not messagebox.askyesno(
            "Confirmar",
            f"¿{action.capitalize()} '{fname}'?\n\n"
            f"El archivo se descargará de GitHub y se guardará en:\n{APP_DIR}",
            parent=self._app,
        ):
            return

        self._log_write(f"\n  ▶  {action.capitalize()}ando {fname}...", "info")
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="disabled")

        def run():
            ok, msg = apply_update(info)
            self.after(0, lambda o=ok, m=msg, f=fname: self._after_install(o, m, f))

        threading.Thread(target=run, daemon=True).start()

    def _after_install(self, ok: bool, msg: str, fname: str):
        tag = "ok" if ok else "err"
        self._log_write(f"  {msg}", tag)
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="normal")

        if ok:
            # Re-check this file
            self._do_check()
            if fname != MAIN_FILE and _app_ref:
                # Reload plugin in FyreManager
                try:
                    path = os.path.join(APP_DIR, fname)
                    from importlib import import_module
                    import fyreupdater as _self_mod
                    # Trigger global reload
                    _load_plugin_external(path)
                    self._log_write(f"  🔄 Plugin {fname} recargado en FyreManager.", "info")
                except Exception:
                    self._log_write(f"  ℹ️  Reinicia FyreWall para activar {fname}.", "muted")
            elif fname == MAIN_FILE:
                self._log_write(
                    "  ℹ️  fyrewall.py actualizado. Reinicia la aplicación para aplicar los cambios.",
                    "muted"
                )

    def _update_all(self):
        pending = {
            f: info for f, info in self._check_results.items()
            if info["status"] in ("update", "missing")
        }
        if not pending:
            self._log_write("  ℹ️  No hay nada que actualizar.", "muted")
            return

        names = ", ".join(pending.keys())
        if not messagebox.askyesno(
            "Actualizar todo",
            f"¿Actualizar / instalar los siguientes archivos?\n\n{names}\n\n"
            "Los archivos actuales se guardarán como .bak",
            parent=self._app,
        ):
            return

        self._log_write(f"\n  ▶  Actualizando {len(pending)} elemento(s)...", "header")
        self._update_all_btn.config(state="disabled")

        def run():
            for fname, info in pending.items():
                ok, msg = apply_update(info)
                self.after(0, lambda o=ok, m=msg: self._log_write(f"  {m}", "ok" if o else "err"))
            self.after(200, self._do_check)
            self.after(0, lambda: self._update_all_btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    # ── Log ───────────────────────────────────────────────────────────────

    def _log_write(self, text: str, tag: str = "info"):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.configure(state="disabled")
        self._log.see("end")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")


# ── Tab builder called by FyreWall plugin system ──────────────────────────────

def _build_updater_tab(parent_frame, app_ref=None):
    """Called by fyrewall.py when the user opens the 'get-update' tab."""
    tab = UpdaterTab(parent_frame, app_ref=app_ref or _app_ref)
    tab.place(relx=0, rely=0, relwidth=1, relheight=1)


# ── FyreManager GUI integration ───────────────────────────────────────────────
# Adds a blue "🔄 Actualizar" button to every package row in FyreManager's
# GUI list, placed to the LEFT of the red "🗑 Eliminar" button.
# This is injected at runtime by patching FyreManagerTab._populate_gui_list.

def _inject_update_button_into_manager():
    """
    Monkey-patch FyreManagerTab._populate_gui_list to insert a blue
    '🔄 Actualizar' button for each row, left of the red delete button.
    Also registers 'get-update' in the CLI autocomplete.
    """
    try:
        # Import the main module — it's already loaded as __main__ or via importlib
        import sys
        main_mod = None
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "FyreManagerTab") and hasattr(mod, "_PLUGINS"):
                main_mod = mod
                break
        if main_mod is None:
            return

        FyreManagerTab = main_mod.FyreManagerTab
        original_populate = FyreManagerTab._populate_gui_list

        def patched_populate(self_mgr):
            original_populate(self_mgr)
            # After the original builds all rows, find the rows and add button
            _add_update_btns_to_gui(self_mgr, main_mod)

        FyreManagerTab._populate_gui_list = patched_populate

        # Also register the get-update command in the main CLI autocomplete
        cmds = main_mod.COMMANDS
        existing_names = {c for c, _ in cmds}
        if "get-update" not in existing_names:
            cmds.append(("get-update", "get-update — abre el instalador/actualizador de FyreWall"))

    except Exception:
        pass


def _add_update_btns_to_gui(mgr, main_mod):
    """Add blue update button to each package row in FyreManager GUI."""
    try:
        gui_list = mgr._gui_list
        for row_widget in gui_list.winfo_children():
            # Each row has a right-aligned "🗑 Eliminar" button; we add before it
            # Find the filename from the Labels inside
            fname = None
            for w in row_widget.winfo_children():
                if isinstance(w, tk.Frame):
                    for inner in w.winfo_children():
                        if isinstance(inner, tk.Label):
                            txt = inner.cget("text")
                            if txt.endswith(".py"):
                                fname = txt
                                break
                elif isinstance(w, tk.Label):
                    txt = w.cget("text")
                    if txt.endswith(".py"):
                        fname = txt
                        break
            if fname:
                # Check if update button already added
                already = any(
                    isinstance(w, tk.Button) and "Actualizar" in (w.cget("text") or "")
                    for w in row_widget.winfo_children()
                )
                if not already:
                    tk.Button(
                        row_widget, text="🔄 Actualizar",
                        command=lambda f=fname: _quick_update_file(f, mgr, main_mod),
                        bg=C["blue_btn"], fg="#ffffff",
                        font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                        padx=6, pady=2, activebackground=C["blue_act"],
                    ).pack(side="right", padx=(0, 4), before=_get_delete_btn(row_widget))
    except Exception:
        pass


def _get_delete_btn(row):
    """Return the first red delete button in the row, or None."""
    for w in row.winfo_children():
        if isinstance(w, tk.Button) and "Eliminar" in (w.cget("text") or ""):
            return w
    return None


def _quick_update_file(fname: str, mgr, main_mod):
    """Triggered by the blue update button in FyreManager GUI."""
    mgr._write(f"\n🔄  Comprobando actualización de {fname}...", "info")

    def run():
        # Determine repo
        repo = MAIN_REPO if fname == MAIN_FILE else ADDONS_REPO
        local_path = os.path.join(APP_DIR, fname)
        local_sha  = _local_sha256(local_path)
        remote_data = _raw_get(repo, "main", fname)
        if remote_data is None:
            mgr.after(0, lambda: mgr._write(f"  ❌ No se pudo descargar {fname} (sin red o no encontrado).", "error"))
            return
        remote_sha = _sha256(remote_data)
        if local_sha == remote_sha:
            mgr.after(0, lambda: mgr._write(f"  ✅ {fname} ya está al día.", "ok"))
            return
        info = {"repo": repo, "branch": "main", "file": fname, "_data": remote_data,
                "local_sha": local_sha, "remote_sha": remote_sha,
                "status": "update" if local_sha else "missing"}
        ok, msg = apply_update(info)
        mgr.after(0, lambda o=ok, m=msg: mgr._write(f"  {m}", "ok" if o else "error"))
        if ok and fname != MAIN_FILE:
            try:
                _load_plugin_external(os.path.join(APP_DIR, fname))
            except Exception:
                pass

    threading.Thread(target=run, daemon=True).start()


def _load_plugin_external(path: str):
    """Reload a plugin file into the FyreWall plugin registry."""
    try:
        import sys
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "_load_plugin") and hasattr(mod, "_PLUGINS"):
                mod._load_plugin(path)
                break
    except Exception:
        pass


# ── CLI command handler ────────────────────────────────────────────────────────

def _cmd_get_update(args):
    """Handler for 'get-update' CLI command — opens the updater tab."""
    return "__PLUGIN_TAB__fyreupdater.py::get-update", "info"


# Update the manifest commands to point to the correct handler
FYRE_MANIFEST["commands"][0]["handler"] = "_cmd_get_update"

# ── Entry point (standalone test) ─────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("FyreUpdater — Standalone Test")
    root.geometry("900x700")
    root.configure(bg=C["bg"])
    tab = UpdaterTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()


# Auto-inject the blue update button into FyreManager GUI on load
_inject_update_button_into_manager()

if __name__ == "__main__":
    main()
