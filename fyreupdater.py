"""
FyreUpdater — Plugin de actualización para FyreWall
=====================================================
Comprueba y descarga actualizaciones desde GitHub para:
  - fyrewall.py        (repo principal: luckicla/FyreWall)
  - fyreupdater.py     (este mismo archivo — auto-actualizable)
  - add-ons instalados (repo add-ons:   luckicla/FyreWall-add-ons)

La lista de add-ons es dinámica: se lee desde
  https://raw.githubusercontent.com/luckicla/FyreWall-add-ons/main/manifest.json

Formato esperado de manifest.json en el repo de add-ons:
  {
    "addons": [
      {
        "file":        "dayus.py",
        "name":        "Dayus",
        "description": "Descripción del add-on",
        "author":      "Autor",
        "version":     "1.2.0"
      },
      ...
    ]
  }

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
    "version":     "1.1.0",
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

GITHUB_API    = "https://api.github.com"
RAW_BASE      = "https://raw.githubusercontent.com"

MAIN_REPO     = "luckicla/FyreWall"
ADDONS_REPO   = "luckicla/FyreWall-add-ons"
UPDATER_REPO  = "luckicla/FyreWall"          # fyreupdater.py vive en el repo principal

MAIN_FILE     = "fyrewall.py"
UPDATER_FILE  = "fyreupdater.py"             # este mismo archivo
ADDONS_MANIFEST_FILE = "manifest.json"       # manifest dinámico en el repo de add-ons

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

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
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FyreUpdater/1.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _raw_get(repo: str, branch: str, filepath: str) -> bytes | None:
    """Download raw file from GitHub."""
    url = f"{RAW_BASE}/{repo}/{branch}/{filepath}"
    req = urllib.request.Request(url, headers={"User-Agent": "FyreUpdater/1.1"})
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


# ── Dynamic add-ons manifest ──────────────────────────────────────────────────

def fetch_addons_manifest() -> list[dict]:
    """
    Fetches manifest.json from the add-ons repo.
    Returns a list of addon dicts:
      [{"file": "dayus.py", "name": "Dayus", "description": "...", ...}, ...]
    Falls back to empty list on error.
    """
    data = _raw_get(ADDONS_REPO, "main", ADDONS_MANIFEST_FILE)
    if data is None:
        return []
    try:
        manifest = json.loads(data.decode())
        addons = manifest.get("addons", [])
        # Ensure each entry has at least a "file" key
        return [a for a in addons if isinstance(a, dict) and "file" in a]
    except Exception:
        return []


# ── Update check ──────────────────────────────────────────────────────────────

def _check_file(repo: str, branch: str, fname: str, is_addon: bool = False) -> dict:
    """
    Check a single file and return its status dict.
    """
    local_path   = os.path.join(APP_DIR, fname)
    local_exists = os.path.exists(local_path)
    local_sha    = _local_sha256(local_path) if local_exists else None
    remote_data  = _raw_get(repo, branch, fname)

    base = {"repo": repo, "branch": branch, "file": fname,
            "local_exists": local_exists, "local_sha": local_sha}

    if remote_data is None:
        return {**base, "status": "error", "remote_sha": None}

    remote_sha = _sha256(remote_data)

    if not local_exists:
        status = "missing"
    elif local_sha == remote_sha:
        status = "ok"
    else:
        status = "update"

    return {**base, "status": status, "remote_sha": remote_sha, "_data": remote_data}


def check_all_updates(addons_manifest: list[dict]) -> dict:
    """
    Returns a dict with update status for all tracked files.
    Keys: filename → status dict.

    Sections:
      - "fyrewall.py"    (main app)
      - "fyreupdater.py" (self)
      - one entry per addon in addons_manifest
    """
    results = {}

    # ── Main app ──────────────────────────────────────────────────────────
    results[MAIN_FILE] = _check_file(MAIN_REPO, "main", MAIN_FILE)

    # ── FyreUpdater (self) ────────────────────────────────────────────────
    results[UPDATER_FILE] = _check_file(UPDATER_REPO, "main", UPDATER_FILE)
    results[UPDATER_FILE]["is_self"] = True   # flag for restart warning

    # ── Add-ons (dynamic) ─────────────────────────────────────────────────
    for addon in addons_manifest:
        fname = addon["file"]
        info  = _check_file(ADDONS_REPO, "main", fname, is_addon=True)
        info["addon_meta"] = addon           # name, description, author, version
        results[fname] = info

    return results


def apply_update(info: dict) -> tuple[bool, str]:
    """Download and overwrite the file. Returns (ok, message)."""
    data = info.get("_data")
    if data is None:
        data = _raw_get(info["repo"], info["branch"], info["file"])
    if data is None:
        return False, f"No se pudo descargar {info['file']}"

    dest = os.path.join(APP_DIR, info["file"])
    bak  = dest + ".bak"

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
        if os.path.exists(bak):
            shutil.copy2(bak, dest)
        return False, f"❌ Error al escribir {info['file']}: {e}"


# ── Installer / Updater Tab ───────────────────────────────────────────────────

class UpdaterTab(tk.Frame):
    """Pestaña 'Instalador' con manifest dinámico y auto-actualización."""

    STATUS_ICONS = {
        "ok":      ("✅", C["ok"]),
        "update":  ("⬆️",  C["warn"]),
        "missing": ("📥", C["accent"]),
        "error":   ("❌", C["danger"]),
        "loading": ("⏳", C["muted"]),
    }

    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg=C["bg"])
        self._app             = app_ref or _app_ref
        self._check_results:  dict       = {}
        self._addons_manifest: list[dict] = []
        self._row_widgets:    dict       = {}
        self._checking        = False
        self._build_skeleton()
        self.after(300, self._do_check)

    # ── Build skeleton UI (before check) ─────────────────────────────────

    def _build_skeleton(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["surface"], pady=10, padx=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="🔄  FyreUpdater",
                 font=F_TITLE, bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Label(hdr, text="  —  Actualiza FyreWall y sus add-ons desde GitHub",
                 font=F_BODY, bg=C["surface"], fg=C["muted"]).pack(side="left")

        self._reload_btn = tk.Button(
            hdr, text="↺  Recargar",
            command=self._do_check,
            bg=C["btn"], fg=C["muted"],
            font=F_BODY, relief="flat", cursor="hand2",
            padx=10, pady=4, activebackground=C["btn_h"],
        )
        self._reload_btn.pack(side="right")

        # ── Status banner ─────────────────────────────────────────────────
        self._banner_frame = tk.Frame(self, bg=C["warn"], pady=0)
        self._banner_lbl = tk.Label(
            self._banner_frame, text="",
            font=F_BOLD, bg=C["warn"], fg="#000000", padx=16, pady=8,
        )
        self._banner_lbl.pack(side="left")
        self._update_all_btn = tk.Button(
            self._banner_frame, text="⬆️  Actualizar todo",
            command=self._update_all,
            bg="#7a5000", fg="#ffffff",
            font=F_BOLD, relief="flat", cursor="hand2",
            padx=12, pady=6, activebackground="#9a6500",
        )
        self._update_all_btn.pack(side="right", padx=12, pady=4)

        # ── Scrollable content area ───────────────────────────────────────
        scroll_outer = tk.Frame(self, bg=C["bg"])
        scroll_outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_outer, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=C["bg"])
        win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(win_id, width=e.width))
        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(-1 * int(e.delta / 120), "units"))

        # placeholder while loading
        self._placeholder = tk.Label(
            self._inner, text="⏳  Obteniendo manifest de add-ons desde GitHub...",
            font=F_BODY, bg=C["bg"], fg=C["muted"], pady=30,
        )
        self._placeholder.pack()

        # ── Log ───────────────────────────────────────────────────────────
        self._build_log()

    def _build_log(self):
        log_hdr = tk.Frame(self._inner, bg=C["surface"], pady=6, padx=12)
        log_hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(log_hdr, text="REGISTRO", font=F_LBL,
                 bg=C["surface"], fg=C["accent"]).pack(side="left")
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

        for tag, color in [
            ("ok",     C["ok"]),
            ("warn",   C["warn"]),
            ("err",    C["danger"]),
            ("info",   C["console_text"]),
            ("muted",  C["muted"]),
            ("header", C["accent"]),
        ]:
            self._log.tag_configure(tag, foreground=color)

    # ── Build dynamic rows after manifest is fetched ───────────────────────

    def _rebuild_rows(self):
        """Destroy old rows and rebuild based on current manifest."""
        # Keep log widget references before destroying inner children
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._row_widgets = {}

        # ── Section: FyreWall principal ───────────────────────────────────
        self._build_section(
            "🔥  FYREWALL PRINCIPAL",
            [{"file": MAIN_FILE, "name": "FyreWall", "description": "Aplicación principal"}],
            show_meta=False,
        )

        # ── Section: FyreUpdater (self) ───────────────────────────────────
        tk.Frame(self._inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)
        self._build_section(
            "🔄  FYREUPDATER (este plugin)",
            [{"file": UPDATER_FILE, "name": "FyreUpdater",
              "description": "Plugin de actualización — se actualiza a sí mismo"}],
            show_meta=False,
        )

        # ── Section: Add-ons ──────────────────────────────────────────────
        tk.Frame(self._inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)
        if self._addons_manifest:
            self._build_section(
                f"📦  ADD-ONS  ({len(self._addons_manifest)} disponibles)",
                self._addons_manifest,
                show_meta=True,
            )
        else:
            no_addons = tk.Frame(self._inner, bg=C["bg"], padx=20, pady=10)
            no_addons.pack(fill="x")
            hdr = tk.Frame(no_addons, bg=C["surface"], pady=8, padx=12)
            hdr.pack(fill="x")
            tk.Label(hdr, text="📦  ADD-ONS", font=F_LBL,
                     bg=C["surface"], fg=C["accent"]).pack(side="left")
            tk.Label(no_addons,
                     text="⚠️  No se pudo obtener el manifest de add-ons (sin red o repo no disponible).",
                     font=F_BODY, bg=C["bg"], fg=C["warn"], pady=8).pack(anchor="w")

        # ── Rebuild log ───────────────────────────────────────────────────
        self._build_log()

    def _build_section(self, title: str, items: list[dict], show_meta: bool = True):
        sec = tk.Frame(self._inner, bg=C["bg"], padx=20, pady=10)
        sec.pack(fill="x")

        hdr = tk.Frame(sec, bg=C["surface"], pady=8, padx=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=F_LBL,
                 bg=C["surface"], fg=C["accent"]).pack(side="left")

        for item in items:
            self._build_file_row(sec, item, show_meta=show_meta)

    def _build_file_row(self, parent, item: dict, show_meta: bool = True):
        fname = item["file"]
        row   = tk.Frame(parent, bg=C["surface2"], pady=0)
        row.pack(fill="x", pady=(1, 0))

        inner = tk.Frame(row, bg=C["surface2"], padx=12, pady=10)
        inner.pack(fill="x")

        # Status icon
        icon_lbl = tk.Label(inner, text="⏳", font=("Segoe UI", 14),
                             bg=C["surface2"], fg=C["muted"])
        icon_lbl.pack(side="left", padx=(0, 10))

        # File info column
        info_col = tk.Frame(inner, bg=C["surface2"])
        info_col.pack(side="left", fill="x", expand=True)

        # Filename + optional addon name
        name_text = fname
        if show_meta and item.get("name") and item["name"] != fname:
            name_text = f"{item['name']}  ({fname})"
        name_lbl = tk.Label(info_col, text=name_text, font=F_BOLD,
                             bg=C["surface2"], fg=C["text"])
        name_lbl.pack(anchor="w")

        # Description (only for addons)
        if show_meta and item.get("description"):
            tk.Label(info_col, text=item["description"], font=F_BODY,
                     bg=C["surface2"], fg=C["muted"]).pack(anchor="w")

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

    # ── Check flow ────────────────────────────────────────────────────────

    def _do_check(self):
        if self._checking:
            return
        self._checking = True
        self._reload_btn.config(state="disabled", text="⏳ Comprobando...")
        self._log_write("🔍  Obteniendo manifest y comprobando actualizaciones...", "header")
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        # Step 1: fetch dynamic manifest
        manifest = fetch_addons_manifest()
        # Step 2: check all files
        results  = check_all_updates(manifest)
        self.after(0, lambda m=manifest, r=results: self._on_check_done(m, r))

    def _on_check_done(self, manifest: list[dict], results: dict):
        self._addons_manifest = manifest
        self._check_results   = results
        self._checking        = False
        self._reload_btn.config(state="normal", text="↺  Recargar")

        # Rebuild rows to match manifest (handles added/removed add-ons)
        self._rebuild_rows()
        self._render_results(results)

    def _render_results(self, results: dict):
        updates = 0
        missing = 0

        for fname, info in results.items():
            status  = info["status"]
            widgets = self._row_widgets.get(fname)
            if not widgets:
                continue

            icon_txt, icon_color = self.STATUS_ICONS.get(status, ("❓", C["muted"]))
            widgets["icon"].config(text=icon_txt, fg=icon_color)
            widgets["install"].pack_forget()
            widgets["update"].pack_forget()

            lsha = (info.get("local_sha") or "—")[:12]
            rsha = (info.get("remote_sha") or "—")[:12]

            is_self = info.get("is_self", False)

            if status == "ok":
                widgets["status_lbl"].config(text="Al día", fg=C["ok"])
                widgets["sha_lbl"].config(text=f"SHA: {lsha}", fg=C["muted"])
                self._log_write(f"  ✅ {fname} — sin cambios.", "ok")

            elif status == "update":
                label = "⚠️  Actualización disponible"
                if is_self:
                    label += "  (requiere reinicio)"
                widgets["status_lbl"].config(text=label, fg=C["warn"])
                widgets["sha_lbl"].config(
                    text=f"Local: {lsha}  →  Remoto: {rsha}", fg=C["warn"])
                widgets["update"].pack(side="left", padx=(0, 4))
                self._log_write(f"  ⬆️  {fname} — actualización disponible.", "warn")
                updates += 1

            elif status == "missing":
                widgets["status_lbl"].config(
                    text="📥 No instalado (disponible en GitHub)", fg=C["accent"])
                widgets["sha_lbl"].config(text=f"Remoto: {rsha}", fg=C["muted"])
                widgets["install"].pack(side="left", padx=(0, 4))
                self._log_write(f"  📥 {fname} — no instalado, disponible.", "info")
                missing += 1

            elif status == "error":
                widgets["status_lbl"].config(text="❌ Error al comprobar", fg=C["danger"])
                widgets["sha_lbl"].config(
                    text="Sin conexión o repo no disponible", fg=C["danger"])
                self._log_write(f"  ❌ {fname} — error de red.", "err")

        # ── Banner ────────────────────────────────────────────────────────
        total_pending = updates + missing
        if total_pending > 0:
            parts = []
            if updates:
                parts.append(f"{updates} actualización{'es' if updates != 1 else ''}")
            if missing:
                parts.append(f"{missing} add-on{'s' if missing != 1 else ''} sin instalar")
            self._banner_lbl.config(text="⚠️  " + "  •  ".join(parts))
            self._banner_frame.config(bg=C["warn"])
            self._banner_lbl.config(bg=C["warn"])
            self._update_all_btn.pack(side="right", padx=12, pady=4)
            self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
            self._log_write(f"\n  → {total_pending} elemento(s) pendiente(s).", "warn")
        else:
            has_ok = any(i["status"] == "ok" for i in results.values())
            if has_ok:
                self._banner_frame.config(bg=C["ok"])
                self._banner_lbl.config(text="✅  Todo al día", bg=C["ok"], fg="#000000")
                self._update_all_btn.pack_forget()
                self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
                self._log_write("\n  ✅ Todo está al día.", "ok")

    # ── Actions ───────────────────────────────────────────────────────────

    def _install_single(self, fname: str):
        info = self._check_results.get(fname)
        if not info:
            self._log_write(f"❌ No hay datos para {fname}", "err")
            return

        is_self = info.get("is_self", False)
        action  = "instalar" if info["status"] == "missing" else "actualizar"

        confirm_msg = (
            f"¿{action.capitalize()} '{fname}'?\n\n"
            f"Se descargará de GitHub y se guardará en:\n{APP_DIR}"
        )
        if is_self:
            confirm_msg += (
                "\n\n⚠️  Este es el propio plugin de actualización.\n"
                "Deberás reiniciar FyreWall para aplicar los cambios."
            )

        if not messagebox.askyesno("Confirmar", confirm_msg, parent=self._app):
            return

        self._log_write(f"\n  ▶  {action.capitalize()}ando {fname}...", "info")
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="disabled")

        def run():
            ok, msg = apply_update(info)
            self.after(0, lambda o=ok, m=msg, f=fname, s=is_self:
                       self._after_install(o, m, f, s))

        threading.Thread(target=run, daemon=True).start()

    def _after_install(self, ok: bool, msg: str, fname: str, is_self: bool):
        self._log_write(f"  {msg}", "ok" if ok else "err")
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="normal")

        if ok:
            if is_self:
                self._log_write(
                    "  ℹ️  FyreUpdater actualizado. Reinicia FyreWall para aplicar los cambios.",
                    "muted",
                )
            elif fname == MAIN_FILE:
                self._log_write(
                    "  ℹ️  fyrewall.py actualizado. Reinicia la aplicación para aplicar los cambios.",
                    "muted",
                )
            else:
                # Hot-reload add-on
                try:
                    path = os.path.join(APP_DIR, fname)
                    _load_plugin_external(path)
                    self._log_write(f"  🔄 Plugin {fname} recargado en FyreManager.", "info")
                except Exception:
                    self._log_write(
                        f"  ℹ️  Reinicia FyreWall para activar {fname}.", "muted")
            self._do_check()

    def _update_all(self):
        pending = {
            f: info for f, info in self._check_results.items()
            if info["status"] in ("update", "missing")
        }
        if not pending:
            self._log_write("  ℹ️  No hay nada que actualizar.", "muted")
            return

        has_self    = any(info.get("is_self") for info in pending.values())
        has_main    = MAIN_FILE in pending
        names       = ", ".join(pending.keys())

        confirm_msg = f"¿Actualizar / instalar los siguientes archivos?\n\n{names}\n\nLos archivos actuales se guardarán como .bak"
        if has_self:
            confirm_msg += "\n\n⚠️  Incluye FyreUpdater — requiere reinicio."
        if has_main:
            confirm_msg += "\n\n⚠️  Incluye fyrewall.py — requiere reinicio."

        if not messagebox.askyesno("Actualizar todo", confirm_msg, parent=self._app):
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

    # ── Log helpers ───────────────────────────────────────────────────────

    def _log_write(self, text: str, tag: str = "info"):
        try:
            self._log.configure(state="normal")
            self._log.insert("end", text + "\n", tag)
            self._log.configure(state="disabled")
            self._log.see("end")
        except Exception:
            pass  # log may be rebuilding

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

def _inject_update_button_into_manager():
    """
    Monkey-patch FyreManagerTab._populate_gui_list to insert a blue
    '🔄 Actualizar' button for each row, left of the red delete button.
    Also registers 'get-update' in the CLI autocomplete.
    """
    try:
        main_mod = None
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "FyreManagerTab") and hasattr(mod, "_PLUGINS"):
                main_mod = mod
                break
        if main_mod is None:
            return

        FyreManagerTab   = main_mod.FyreManagerTab
        original_populate = FyreManagerTab._populate_gui_list

        def patched_populate(self_mgr):
            original_populate(self_mgr)
            _add_update_btns_to_gui(self_mgr, main_mod)

        FyreManagerTab._populate_gui_list = patched_populate

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
    for w in row.winfo_children():
        if isinstance(w, tk.Button) and "Eliminar" in (w.cget("text") or ""):
            return w
    return None


def _quick_update_file(fname: str, mgr, main_mod):
    """Triggered by the blue update button in FyreManager GUI."""
    mgr._write(f"\n🔄  Comprobando actualización de {fname}...", "info")

    def run():
        repo = MAIN_REPO if fname in (MAIN_FILE, UPDATER_FILE) else ADDONS_REPO
        local_path  = os.path.join(APP_DIR, fname)
        local_sha   = _local_sha256(local_path)
        remote_data = _raw_get(repo, "main", fname)
        if remote_data is None:
            mgr.after(0, lambda: mgr._write(
                f"  ❌ No se pudo descargar {fname} (sin red o no encontrado).", "error"))
            return
        remote_sha = _sha256(remote_data)
        if local_sha == remote_sha:
            mgr.after(0, lambda: mgr._write(f"  ✅ {fname} ya está al día.", "ok"))
            return
        info = {
            "repo": repo, "branch": "main", "file": fname,
            "_data": remote_data, "local_sha": local_sha, "remote_sha": remote_sha,
            "status": "update" if local_sha else "missing",
            "is_self": fname == UPDATER_FILE,
        }
        ok, msg = apply_update(info)
        mgr.after(0, lambda o=ok, m=msg: mgr._write(f"  {m}", "ok" if o else "error"))
        if ok and fname not in (MAIN_FILE, UPDATER_FILE):
            try:
                _load_plugin_external(os.path.join(APP_DIR, fname))
            except Exception:
                pass
        elif ok and fname == UPDATER_FILE:
            mgr.after(0, lambda: mgr._write(
                "  ℹ️  FyreUpdater actualizado. Reinicia FyreWall para aplicar los cambios.",
                "info"))

    threading.Thread(target=run, daemon=True).start()


def _load_plugin_external(path: str):
    """Reload a plugin file into the FyreWall plugin registry."""
    try:
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
