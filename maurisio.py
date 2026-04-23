"""
Maurisio — El Agente Barrio de FyreWall
=========================================
Pestaña de chat con IA local usando Ollama.
Maurisio es un gitano mu mal hablao que sabe de firewalls como nadie
en el barrio. Si Ollama no está instalao, se lo curra él solo y lo
descarga. Si no hay modelo, pilla el phi3:mini que es el más apañao.

Requisitos:
  - Windows 10/11
  - Conexión a internet (solo la primera vez pa descargar Ollama y el modelo)
  - Que te caiga bien Maurisio (obligatorio)

Integración en FyreWall:
  - Pestaña:  "🤙 Maurisio"
  - Comando:  maurisio
  - Instalar: pon este archivo en la misma carpeta que fyrewall.py
"""

import os
import sys
import json
import re
import threading
import subprocess
import urllib.request
import urllib.error
import tempfile
import time
import tkinter as tk
from tkinter import ttk

# ── Manifest FyreWall ─────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "Maurisio",
    "version":     "1.0.0",
    "author":      "El Barrio",
    "description": "Agente de IA local con personalidad — Maurisio el gitano del firewall",
    "commands": [
        {
            "name":        "maurisio",
            "kind":        "tab",
            "tab_builder": "_build_maurisio_tab",
            "description": "Abre a Maurisio, el agente IA barriobajero de FyreWall",
        },
    ],
}

# ── Config Ollama ─────────────────────────────────────────────────────────────

OLLAMA_BASE      = "http://localhost:11434"
OLLAMA_TAGS_URL  = f"{OLLAMA_BASE}/api/tags"
OLLAMA_CHAT_URL  = f"{OLLAMA_BASE}/api/chat"
OLLAMA_PULL_URL  = f"{OLLAMA_BASE}/api/pull"

# Modelo preferido — phi3:mini es el más ligero que funciona bien
MODELO_PREFERIDO = "phi3:mini"
MODELOS_OK = [
    "phi3:mini", "phi3", "phi3.5",
    "gemma2:2b", "gemma2",
    "llama3.2:1b", "llama3.2",
    "qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5",
    "deepseek-r1:1.5b",
    "tinyllama",
]

# URL instalador Ollama para Windows
OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

CF = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ── Paleta ────────────────────────────────────────────────────────────────────

C = {
    "bg":          "#1a1d23",
    "surface":     "#22252e",
    "surface2":    "#2a2d38",
    "border":      "#33374a",
    "accent":      "#f97316",   # naranja — color Maurisio
    "accent2":     "#fb923c",
    "text":        "#e8eaf0",
    "muted":       "#7a8099",
    "ok":          "#4caf80",
    "warn":        "#f5a623",
    "danger":      "#e05c5c",
    "btn":         "#2a2d38",
    "btn_h":       "#343848",
    "console_bg":  "#0e1117",
    "console_txt": "#c9d1d9",
    "user_fg":     "#fb923c",
    "ai_fg":       "#4ade80",
    "sys_fg":      "#555870",
    "cmd_bg":      "#1c1408",
    "cmd_fg":      "#fbbf24",
}

F_BODY  = ("Segoe UI", 10)
F_BOLD  = ("Segoe UI", 10, "bold")
F_MONO  = ("Consolas", 9)
F_SMALL = ("Segoe UI", 8)
F_TITLE = ("Segoe UI", 13, "bold")

# ── System prompt — Maurisio ──────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres Maurisio, un gitano del barrio que sabe mu bien de firewalls y seguridad de redes en Windows. Eres el agente de IA integrao en FyreWall.

Tu forma de hablar: andaluz cerrao, vulgar, directo, con palabrotas ocasionales (sin pasarte), coloquial total. Nada de formalismos. Ejemplos de tu vocabulario: "macho", "tío", "joder", "ostia", "coño", "qué putada", "no te lo pueo creer", "esto ta peor que mi tía", "más claro que el agua", "en el barrio esto lo sabemos too", "me cago en too", "eso está más comprometío que mi primo el Paco".

PERO: cuando explicas seguridad o FyreWall, lo haces bien aunque con tu estilo. Sabes lo que haces. No eres tonto, eres listísimo aunque hables mal.

COMANDOS DE FYREWALL QUE CONOCES Y PUEDES PROPONER:

  PUERTOS:
    block-port <puerto> [tcp|udp] [in|out]   → bloquea un puerto, macho
    unblock-port <puerto> [tcp|udp] [in|out] → lo desbloqueamos
    status <puerto>                          → ves si está bloqueao o no

  APLICACIONES:
    block-app <ruta_exe>       → bloquea un ejecutable entero
    block-process <nombre>     → bloquea un proceso que esté corriendo

  AULA (pa cuando te vigilan en el cole):
    block-insight              → le cortas el rollo a Faronics Insight, el programa ese de vigilancia
    unblock-insight            → lo dejas pasar otra vez
    block-reboot               → bloqueas el Reboot Restore (el que te formatea el PC)
    unblock-reboot             → lo dejas

  RED Y SISTEMA:
    isolate                    → cortas TODO el tráfico, aislamiento total
    unisolate                  → restauras la red
    list                       → ves toas las reglas que hay
    flush                      → borras toas las reglas de FyreWall
    get-ip                     → ves tus IPs locales y la pública
    get-suspicious             → analizas puertos raros (VNC, RDP, SMB...)
    get-admin                  → pides privilegios de Administrador
    scan                       → re-escaneas las conexiones

  ARCHIVOS Y EXTRAS:
    ls                         → lista archivos del directorio
    get-bat / run-bat <bat>    → ejecutas archivos .bat
    peticiones                 → pestaña de peticiones de red en vivo
    monitor                    → el Debug Monitor de conexiones
    aula                       → panel de Bloqueo de Aula
    maurisio                   → me abres a mí (que pa eso estoy)
    fyre-manager               → el gestor de paquetes

CÓMO PROPONER COMANDOS:
Cuando quieras que el usuario ejecute algo, ponlo ASÍ exactamente:
  ```fyrewall
  block-port 3389
  ```
Puedes meter varios comandos en el mismo bloque. El sistema le mostrará un botón pa confirmar. NUNCA ejecutes ná sin que lo confirme.

REGLAS:
- Habla siempre en tu estilo barriobajero aunque el usuario hable fino
- Si ves algo sospechoso en el contexto de red, lo dices sin rodeos
- Puedes hablar de cualquier tema además de FyreWall
- Si te preguntan algo que no sabes, lo dices con tu estilo ("ni idea, macho, eso no lo sé ni yo")
- Sé gracioso pero útil. Eres el mejor del barrio en esto.
"""

# ── Referencia global ─────────────────────────────────────────────────────────

_app_ref = None


# ── Helpers Ollama ────────────────────────────────────────────────────────────

def _ollama_get(url: str, timeout: int = 5) -> dict | None:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def is_ollama_running() -> bool:
    return _ollama_get(OLLAMA_TAGS_URL, timeout=3) is not None


def get_models() -> list[str]:
    resp = _ollama_get(OLLAMA_TAGS_URL, timeout=5)
    if not resp:
        return []
    return [m["name"] for m in resp.get("models", [])]


def pick_model(available: list[str]) -> str | None:
    avail_lower = {m.lower(): m for m in available}
    for pref in MODELOS_OK:
        if pref.lower() in avail_lower:
            return avail_lower[pref.lower()]
        for nl, n in avail_lower.items():
            if nl.startswith(pref.lower()):
                return n
    return available[0] if available else None


def is_ollama_installed() -> bool:
    """Comprueba si ollama.exe está en el PATH o en rutas comunes."""
    try:
        r = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, timeout=5, creationflags=CF,
        )
        return r.returncode == 0
    except Exception:
        pass
    # Rutas comunes en Windows
    for path in [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]:
        if os.path.exists(path):
            return True
    return False


def start_ollama_server() -> bool:
    """Intenta arrancar el servidor Ollama en background."""
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=CF | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        # Espera hasta 12s a que arranque
        for _ in range(24):
            time.sleep(0.5)
            if is_ollama_running():
                return True
        return False
    except Exception:
        return False


def pull_model_stream(model: str, on_progress, on_done, on_error):
    """
    Descarga un modelo con streaming de progreso.
    on_progress(status, percent_or_None)
    on_done()
    on_error(msg)
    """
    payload = json.dumps({"name": model, "stream": True}).encode()
    req = urllib.request.Request(
        OLLAMA_PULL_URL, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                status = obj.get("status", "")
                total  = obj.get("total", 0)
                compl  = obj.get("completed", 0)
                pct    = int(compl * 100 / total) if total > 0 else None
                on_progress(status, pct)
                if status == "success":
                    on_done()
                    return
        on_done()
    except Exception as e:
        on_error(str(e))


def chat_stream(model: str, messages: list[dict],
                on_token, on_done, on_error):
    """Stream de chat contra Ollama."""
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_CHAT_URL, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                token = obj.get("message", {}).get("content", "")
                if token:
                    on_token(token)
                if obj.get("done"):
                    break
        on_done()
    except Exception as e:
        on_error(str(e))


# ── Contexto del sistema ──────────────────────────────────────────────────────

def _get_context() -> str:
    lines = ["=== CONTEXTO DEL SISTEMA (ahora mismo) ===\n"]
    fw = None
    for _, mod in sys.modules.items():
        if hasattr(mod, "scan_connections") and hasattr(mod, "cmd_list_rules"):
            fw = mod
            break

    lines.append("── CONEXIONES ACTIVAS ──")
    if fw:
        try:
            conns = fw.scan_connections()
            est   = [c for c in conns if c.get("state") == "ESTABLISHED"]
            lst   = [c for c in conns if c.get("state") == "LISTENING"]
            lines.append(f"Total: {len(conns)} | ESTABLISHED: {len(est)} | LISTENING: {len(lst)}")
            if est:
                lines.append("Establecidas (top 20):")
                for c in est[:20]:
                    lines.append(
                        f"  {c['process']:<24} {c['proto']:<4} "
                        f"{c['local_addr']}:{c['local_port']} → "
                        f"{c['remote_addr']}:{c['remote_port']}"
                    )
            if lst:
                lines.append("Escuchando (top 12):")
                for c in lst[:12]:
                    lines.append(f"  {c['process']:<24} {c['proto']:<4} :{c['local_port']}")
        except Exception as e:
            lines.append(f"  [error: {e}]")
    else:
        lines.append("  [fyrewall.py no disponible]")

    lines.append("\n── REGLAS FYREWALL ──")
    if fw:
        try:
            rules = fw.cmd_list_rules()
            if rules:
                lines.append(f"Total: {len(rules)} reglas")
                for key, info in list(rules.items())[:20]:
                    dirs = ", ".join(info.get("dirs", []))
                    lines.append(f"  🔒 {info['port']:<18} {info['proto']:<5} {dirs}")
            else:
                lines.append("  Sin reglas activas.")
        except Exception as e:
            lines.append(f"  [error: {e}]")

    lines.append("\n── PUERTOS SOSPECHOSOS ──")
    if fw:
        try:
            findings = fw.scan_suspicious_ports()
            total = sum(len(v) for v in findings.values())
            if total:
                lines.append(f"⚠️  {total} hallazgo(s):")
                for cat, hits in findings.items():
                    for h in hits:
                        lines.append(
                            f"  {h['icon']} Puerto {h['port']}/{h['proto']} "
                            f"[{h['state']}] {h['process']} — {h['reason']}"
                        )
            else:
                lines.append("  Sin puertos raros detectaos.")
        except Exception as e:
            lines.append(f"  [error: {e}]")

    lines.append("\n── ESTADO ──")
    if fw:
        try:
            admin = fw._is_admin()
            lines.append(f"Admin: {'SÍ' if admin else 'NO'}")
        except Exception:
            pass
        try:
            svc = fw.check_classroom_services_status()
            i = svc.get("insight", {})
            r = svc.get("rebootrestore", {})
            if i.get("status") != "not_found":
                lines.append(f"Faronics Insight: {i['status']}")
            if r.get("status") != "not_found":
                lines.append(f"Reboot Restore:   {r['status']}")
        except Exception:
            pass

    lines.append("\n=== FIN CONTEXTO ===")
    return "\n".join(lines)


# ── Extraer y ejecutar comandos ───────────────────────────────────────────────

def extract_commands(text: str) -> list[str]:
    matches = re.findall(r"```fyrewall\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    cmds = []
    for block in matches:
        for line in block.strip().splitlines():
            line = line.strip()
            if line:
                cmds.append(line)
    return cmds


def run_command(cmd_str: str) -> tuple[bool, str]:
    fw = None
    for _, mod in sys.modules.items():
        if hasattr(mod, "parse_and_run"):
            fw = mod
            break
    if not fw:
        return False, "fyrewall.py no disponible, macho."
    try:
        result, tag = fw.parse_and_run(cmd_str)
        ok = tag in ("ok", "info", "warn")
        if isinstance(result, str) and result.startswith("__"):
            return False, f"Eso es un comando de interfaz gráfica, no puedo ejecutarlo desde aquí: {cmd_str}"
        return ok, result or "✅ Hecho."
    except Exception as e:
        return False, str(e)


# ── MaurisioTab ───────────────────────────────────────────────────────────────

class MaurisioTab(tk.Frame):

    # Estados del setup
    ST_CHECKING    = "checking"
    ST_NO_OLLAMA   = "no_ollama"
    ST_DOWNLOADING = "downloading"
    ST_STARTING    = "starting"
    ST_NO_MODEL    = "no_model"
    ST_PULLING     = "pulling"
    ST_READY       = "ready"

    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg=C["bg"])
        self._app        = app_ref
        self._state      = self.ST_CHECKING
        self._model      = None
        self._history: list[dict] = []
        self._streaming  = False
        self._ai_buf     = ""
        self._user_hist: list[str] = []
        self._hist_idx   = -1
        self._setup_frame = None

        self._build_ui()
        self.after(200, self._start_setup)

    # ── Construcción de UI ────────────────────────────────────────────────

    def _build_ui(self):
        # Cabecera
        hdr = tk.Frame(self, bg=C["surface"], pady=8, padx=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="🤙  Maurisio",
                 font=F_TITLE, bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Label(hdr, text="  —  El gitano del barrio que sabe de firewalls",
                 font=F_BODY, bg=C["surface"], fg=C["muted"]).pack(side="left")

        rh = tk.Frame(hdr, bg=C["surface"])
        rh.pack(side="right")

        tk.Button(rh, text="🧠 Contexto",
                  command=self._inject_context,
                  bg="#1a1010", fg=C["accent"],
                  font=F_SMALL, relief="flat", cursor="hand2",
                  padx=8, pady=3, activebackground="#2a1a10").pack(side="left", padx=(0, 4))

        tk.Button(rh, text="🗑 Limpiar",
                  command=self._clear_chat,
                  bg=C["btn"], fg=C["muted"],
                  font=F_SMALL, relief="flat", cursor="hand2",
                  padx=8, pady=3, activebackground=C["btn_h"]).pack(side="left")

        # Status bar
        self._status_bar = tk.Frame(self, bg=C["surface2"], pady=4)
        self._status_bar.pack(fill="x")
        self._status_lbl = tk.Label(
            self._status_bar, text="⏳ Comprobando si Ollama está por ahí...",
            font=F_SMALL, bg=C["surface2"], fg=C["muted"],
        )
        self._status_lbl.pack(side="left", padx=12)

        # Panel de setup (se muestra en el centro mientras no está listo)
        self._setup_area = tk.Frame(self, bg=C["bg"])
        self._setup_area.pack(fill="both", expand=True)

        # Panel de comandos propuestos
        self._cmd_panel = tk.Frame(self, bg=C["cmd_bg"])

        # Chat (oculto hasta que esté listo)
        self._chat_frame = tk.Frame(self, bg=C["console_bg"])

        self._chat = tk.Text(
            self._chat_frame,
            bg=C["console_bg"], fg=C["console_txt"],
            font=("Segoe UI", 10), relief="flat", bd=0,
            state="disabled", wrap="word",
            padx=16, pady=12, cursor="arrow",
            spacing1=2, spacing3=4,
        )
        chat_sb = ttk.Scrollbar(self._chat_frame, orient="vertical", command=self._chat.yview)
        self._chat.configure(yscrollcommand=chat_sb.set)
        chat_sb.pack(side="right", fill="y")
        self._chat.pack(side="left", fill="both", expand=True)

        self._chat.tag_configure("user_name", foreground=C["user_fg"], font=("Segoe UI", 9, "bold"))
        self._chat.tag_configure("user_msg",  foreground="#e2e8f0",    font=("Segoe UI", 10),
                                  lmargin1=16, lmargin2=16)
        self._chat.tag_configure("ai_name",   foreground=C["accent"],  font=("Segoe UI", 9, "bold"))
        self._chat.tag_configure("ai_msg",    foreground=C["console_txt"], font=("Segoe UI", 10),
                                  lmargin1=16, lmargin2=16)
        self._chat.tag_configure("sys_msg",   foreground=C["sys_fg"],  font=("Segoe UI", 8, "italic"),
                                  lmargin1=8, lmargin2=8)
        self._chat.tag_configure("thinking",  foreground=C["muted"],   font=("Segoe UI", 9, "italic"))

        # Quick prompts
        self._quick_bar = tk.Frame(self, bg=C["bg"], pady=3)
        tk.Label(self._quick_bar, text="Quick:",
                 font=F_SMALL, bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(12, 6))
        for label, prompt in [
            ("🔍 Analizar red",    "Analiza las conexiones activas y dime si ves algo raro."),
            ("🛡 Fortalecer",      "¿Qué puertos debería bloquear pa estar más seguro?"),
            ("📋 Ver reglas",      "Lista las reglas activas y dime si quitarías alguna."),
            ("🚨 Threat check",   "¿Hay procesos o conexiones sospechosas ahí?"),
            ("🔒 Bloquear RDP",   "Bloquea el RDP (puerto 3389) que no quiero que entren."),
            ("📡 Puertos raros",  "¿Hay puertos de control remoto o vigilancia activos?"),
        ]:
            tk.Button(
                self._quick_bar, text=label,
                command=lambda p=prompt: self._quick_send(p),
                bg=C["surface2"], fg=C["muted"],
                font=("Segoe UI", 7), relief="flat", cursor="hand2",
                padx=6, pady=2, activebackground=C["btn_h"],
                activeforeground=C["text"],
            ).pack(side="left", padx=2)

        # Input
        self._input_frame = tk.Frame(self, bg=C["surface"], pady=8, padx=12)

        tk.Label(self._input_frame, text="❯",
                 font=("Consolas", 12, "bold"),
                 bg=C["surface"], fg=C["accent"]).pack(side="left", padx=(0, 8))

        self._input_var = tk.StringVar()
        self._input = tk.Entry(
            self._input_frame,
            textvariable=self._input_var,
            bg=C["surface2"], fg=C["text"],
            font=("Segoe UI", 11), relief="flat", bd=0,
            insertbackground=C["accent"],
            state="disabled",
        )
        self._input.pack(side="left", fill="x", expand=True, ipady=6)
        # <Return> se bindea en _on_ready, después de habilitar el Entry
        self._input.bind("<Up>",   self._hist_up)
        self._input.bind("<Down>", self._hist_down)

        self._send_btn = tk.Button(
            self._input_frame, text="Enviar  ⏎",
            command=self._send,
            bg=C["accent"], fg="#000000",
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=6, activebackground=C["accent2"],
            state="disabled",
        )
        self._send_btn.pack(side="right", padx=(8, 0))

    # ── Setup automático ──────────────────────────────────────────────────

    def _start_setup(self):
        self._show_setup_panel("⏳ Comprobando Ollama...",
                               "Espera un momento, macho, estoy mirando si Ollama está por aquí...")
        threading.Thread(target=self._setup_thread, daemon=True).start()

    def _setup_thread(self):
        """Hilo de setup: detecta Ollama, lo instala si falta, descarga modelo."""

        # 1. ¿Está corriendo Ollama?
        self.after(0, lambda: self._set_status("⏳ Comprobando Ollama...", C["muted"]))
        if is_ollama_running():
            self._on_ollama_running()
            return

        # 2. ¿Está instalado pero parado?
        if is_ollama_installed():
            self.after(0, lambda: self._show_setup_panel(
                "⏳ Arrancando Ollama...",
                "Ollama está instalao pero dormío. Lo despierto yo...",
                show_spinner=True,
            ))
            self.after(0, lambda: self._set_status("⏳ Arrancando Ollama...", C["warn"]))
            ok = start_ollama_server()
            if ok:
                self._on_ollama_running()
                return
            else:
                self.after(0, lambda: self._show_setup_panel(
                    "⚠️ No pudo arrancar",
                    "Ollama está instalao pero no arranca solo. Ábrelo tú desde el menú de Windows y luego pulsa Reintentar.",
                    retry_btn=True,
                ))
                self.after(0, lambda: self._set_status("⚠️ Ollama no arranca", C["danger"]))
                return

        # 3. No está instalado — preguntar si descargar
        self.after(0, self._ask_install_ollama)

    def _on_ollama_running(self):
        """Ollama corre. Ahora comprobamos modelos."""
        models = get_models()
        if models:
            best = pick_model(models)
            self.after(0, lambda m=best, ms=models: self._on_ready(m, ms))
        else:
            # No hay modelos — tirar del preferido
            self.after(0, self._ask_pull_model)

    def _ask_install_ollama(self):
        """Muestra panel para descargar e instalar Ollama."""
        self._clear_setup()
        panel = tk.Frame(self._setup_area, bg=C["bg"])
        panel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(panel, text="🤙", font=("Segoe UI", 48),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(0, 8))
        tk.Label(panel, text="Aquí falta Ollama, tío",
                 font=("Segoe UI", 16, "bold"), bg=C["bg"], fg=C["accent"]).pack()
        tk.Label(panel,
                 text="Ollama es el motor que me da vidiya. Sin él no soy ná.\n"
                      "Lo descargo yo solo ahora mismo, son como 800 MB.",
                 font=F_BODY, bg=C["bg"], fg=C["muted"], justify="center").pack(pady=8)

        self._progress_lbl = tk.Label(panel, text="",
                                       font=F_SMALL, bg=C["bg"], fg=C["muted"])
        self._progress_lbl.pack()
        self._progress_bar = ttk.Progressbar(panel, length=380, mode="indeterminate")
        self._progress_bar.pack(pady=(4, 12))

        btn_row = tk.Frame(panel, bg=C["bg"])
        btn_row.pack()

        self._install_btn = tk.Button(
            btn_row, text="⬇️  Descargar e instalar Ollama",
            command=self._do_download_ollama,
            bg=C["accent"], fg="#000000",
            font=F_BOLD, relief="flat", cursor="hand2",
            padx=16, pady=8, activebackground=C["accent2"],
        )
        self._install_btn.pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="Cancelar",
            command=lambda: None,
            bg=C["btn"], fg=C["muted"],
            font=F_SMALL, relief="flat", cursor="hand2",
            padx=10, pady=6,
        ).pack(side="left")

        self._set_status("🤙 Ollama no está instalao", C["warn"])

    def _do_download_ollama(self):
        self._install_btn.config(state="disabled", text="⏳ Descargando...")
        self._progress_bar.start(12)
        self._set_status("⬇️ Descargando instalador de Ollama...", C["warn"])
        threading.Thread(target=self._download_ollama_thread, daemon=True).start()

    def _download_ollama_thread(self):
        try:
            tmp = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")

            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    pct = int(count * block_size * 100 / total_size)
                    self.after(0, lambda p=pct: self._set_status(
                        f"⬇️ Descargando Ollama... {p}%", C["warn"]
                    ))

            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, tmp, reporthook)

            self.after(0, lambda: self._set_status("⚙️ Instalando Ollama...", C["warn"]))
            self.after(0, lambda: self._progress_lbl.config(
                text="Instalando... acepta el instalador si aparece"))

            r = subprocess.run(
                [tmp, "/S"],   # /S = silent install
                timeout=300, creationflags=CF,
            )

            if r.returncode == 0 or is_ollama_installed():
                self.after(0, lambda: self._progress_lbl.config(text="Instalao. Arrancando..."))
                ok = start_ollama_server()
                if ok:
                    self.after(0, self._on_ollama_running)
                else:
                    self.after(0, lambda: self._show_setup_panel(
                        "⚠️ Instalao pero no arranca",
                        "Lo instalé pero no arranca solo. Ábrelo desde el menú inicio y pulsa Reintentar.",
                        retry_btn=True,
                    ))
            else:
                self.after(0, lambda: self._show_setup_panel(
                    "❌ Error en la instalación",
                    f"El instalador salió con código {r.returncode}. Instala Ollama manualmente desde ollama.com",
                    retry_btn=True,
                ))
        except Exception as e:
            self.after(0, lambda: self._show_setup_panel(
                "❌ Error descargando",
                f"No pude descargarlo: {e}\nInstala Ollama manualmente desde https://ollama.com",
                retry_btn=True,
            ))

    def _ask_pull_model(self):
        """No hay modelos — pedir pull del modelo preferido."""
        self._clear_setup()
        panel = tk.Frame(self._setup_area, bg=C["bg"])
        panel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(panel, text="🤙", font=("Segoe UI", 48),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(0, 8))
        tk.Label(panel, text="Falta el modelo de IA, primo",
                 font=("Segoe UI", 16, "bold"), bg=C["bg"], fg=C["accent"]).pack()
        tk.Label(panel,
                 text=f"Ollama está corriendo pero no tiene modelos.\n"
                      f"Voy a pillar '{MODELO_PREFERIDO}' — son unos 2GB, espera un poco.",
                 font=F_BODY, bg=C["bg"], fg=C["muted"], justify="center").pack(pady=8)

        self._pull_status_lbl = tk.Label(panel, text="",
                                          font=F_SMALL, bg=C["bg"], fg=C["muted"])
        self._pull_status_lbl.pack()

        self._pull_bar = ttk.Progressbar(panel, length=380, mode="determinate", maximum=100)
        self._pull_bar.pack(pady=(4, 12))

        self._pull_btn = tk.Button(
            panel, text=f"⬇️  Descargar {MODELO_PREFERIDO}",
            command=self._do_pull_model,
            bg=C["accent"], fg="#000000",
            font=F_BOLD, relief="flat", cursor="hand2",
            padx=16, pady=8, activebackground=C["accent2"],
        )
        self._pull_btn.pack()

        self._set_status(f"🤙 Necesito descargar {MODELO_PREFERIDO}", C["warn"])

    def _do_pull_model(self):
        self._pull_btn.config(state="disabled", text="⏳ Descargando modelo...")
        self._set_status(f"⬇️ Descargando {MODELO_PREFERIDO}...", C["warn"])
        threading.Thread(target=self._pull_thread, daemon=True).start()

    def _pull_thread(self):
        def on_progress(status, pct):
            def _upd():
                self._pull_status_lbl.config(text=f"{status}" + (f"  {pct}%" if pct is not None else ""))
                if pct is not None:
                    self._pull_bar["value"] = pct
                    self._pull_bar["mode"]  = "determinate"
                else:
                    self._pull_bar["mode"] = "indeterminate"
                self._set_status(
                    f"⬇️ Descargando {MODELO_PREFERIDO}..." + (f" {pct}%" if pct else ""),
                    C["warn"],
                )
            self.after(0, _upd)

        def on_done():
            models = get_models()
            best   = pick_model(models) if models else MODELO_PREFERIDO
            self.after(0, lambda m=best, ms=models: self._on_ready(m, ms))

        def on_error(err):
            self.after(0, lambda: self._show_setup_panel(
                "❌ Error descargando modelo",
                f"No pude descargar {MODELO_PREFERIDO}: {err}\n"
                "Prueba a ejecutar manualmente:\n  ollama pull phi3:mini",
                retry_btn=True,
            ))

        pull_model_stream(MODELO_PREFERIDO, on_progress, on_done, on_error)

    def _on_ready(self, model: str, all_models: list[str]):
        """Todo listo — ocultamos el setup y mostramos el chat."""
        self._model = model
        self._state = self.ST_READY

        # Ocultar setup, mostrar chat
        for w in self._setup_area.winfo_children():
            w.destroy()
        self._setup_area.pack_forget()

        self._chat_frame.pack(fill="both", expand=True)
        # Con side="bottom" el orden es inverso: lo último en packearse queda más arriba.
        # Input abajo del todo → se packea el primero
        self._input_frame.pack(fill="x", side="bottom")
        # Quick bar encima del input → se packea después
        self._quick_bar.pack(fill="x", side="bottom")

        # Activar input y bindear Return DESPUÉS de habilitar el widget
        self._input.config(state="normal")
        self._input.bind("<Return>", self._send)
        self._send_btn.config(state="normal")
        self._input.focus_set()

        self._set_status(
            f"🤙 Maurisio listo  —  modelo: {model}  —  {len(all_models)} disponible(s)",
            C["ok"],
        )

        # Inicializar historial
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inyectar contexto silencioso
        ctx = _get_context()
        self._history.append({"role": "user", "content": ctx})
        self._history.append({
            "role": "assistant",
            "content": "Contexto recibido, ya sé lo que está pasando en la red."
        })

        # Saludo de Maurisio
        self._start_stream_silent(
            "Saluda con tu estilo gitano barriobajero en 2-3 frases, di tu nombre, "
            "y si el contexto del sistema tiene algo interesante (puertos raros, conexiones sospechosas, etc.) "
            "menciónalo directamente. Si todo está limpio, dilo también a tu manera."
        )

    # ── Setup panel helper ────────────────────────────────────────────────

    def _clear_setup(self):
        for w in self._setup_area.winfo_children():
            w.destroy()

    def _show_setup_panel(self, title: str, body: str,
                          show_spinner: bool = False, retry_btn: bool = False):
        self._clear_setup()
        panel = tk.Frame(self._setup_area, bg=C["bg"])
        panel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(panel, text="🤙", font=("Segoe UI", 48),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(0, 8))
        tk.Label(panel, text=title,
                 font=("Segoe UI", 15, "bold"), bg=C["bg"], fg=C["accent"]).pack()
        tk.Label(panel, text=body,
                 font=F_BODY, bg=C["bg"], fg=C["muted"],
                 justify="center", wraplength=420).pack(pady=10)

        if show_spinner:
            pb = ttk.Progressbar(panel, length=320, mode="indeterminate")
            pb.pack(pady=4)
            pb.start(10)

        if retry_btn:
            tk.Button(
                panel, text="↺ Reintentar",
                command=self._start_setup,
                bg=C["accent"], fg="#000000",
                font=F_BOLD, relief="flat", cursor="hand2",
                padx=14, pady=7, activebackground=C["accent2"],
            ).pack(pady=8)

    # ── Status ────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status_lbl.config(text=text, fg=color)

    # ── Chat output ───────────────────────────────────────────────────────

    def _chat_write(self, text: str, tag: str = "ai_msg"):
        self._chat.configure(state="normal")
        self._chat.insert("end", text, tag)
        self._chat.configure(state="disabled")
        self._chat.see("end")

    def _append_user(self, text: str):
        self._chat_write("\n\n┃ ", "user_name")
        self._chat_write("Tú\n", "user_name")
        self._chat_write(text + "\n", "user_msg")

    def _append_ai_start(self):
        self._chat_write("\n\n┃ ", "ai_name")
        self._chat_write("🤙 Maurisio\n", "ai_name")

    def _append_ai_token(self, token: str):
        self._ai_buf += token
        self._chat.configure(state="normal")
        self._chat.insert("end", token, "ai_msg")
        self._chat.configure(state="disabled")
        self._chat.see("end")

    def _append_sys(self, text: str):
        self._chat_write(f"\n─── {text} ───\n", "sys_msg")

    def _clear_chat(self):
        self._chat.configure(state="normal")
        self._chat.delete("1.0", "end")
        self._chat.configure(state="disabled")
        if self._state == self.ST_READY:
            self._history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._ai_buf = ""

    def _inject_context(self):
        if self._state != self.ST_READY:
            return
        ctx = _get_context()
        self._history.append({"role": "user", "content": ctx})
        self._history.append({
            "role": "assistant",
            "content": "Contexto actualizado, lo tengo."
        })
        lines = ctx.splitlines()
        preview = "\n".join(lines[:14]) + (f"\n... ({len(lines)} líneas)" if len(lines) > 14 else "")
        self._append_sys(f"📡 Contexto actualizado:\n{preview}")

    # ── Stream ────────────────────────────────────────────────────────────

    def _send(self, event=None):
        if self._streaming or self._state != self.ST_READY:
            return
        text = self._input_var.get().strip()
        if not text:
            return
        self._input_var.set("")
        self._hist_idx = -1
        self._user_hist.insert(0, text)
        self._history.append({"role": "user", "content": text})
        self._append_user(text)
        self._start_stream()

    def _quick_send(self, prompt: str):
        if self._streaming or self._state != self.ST_READY:
            return
        self._history.append({"role": "user", "content": prompt})
        self._append_user(prompt)
        self._start_stream()

    def _start_stream_silent(self, text: str):
        """Stream sin mostrar burbuja de usuario (para el saludo inicial)."""
        self._history.append({"role": "user", "content": text})
        self._start_stream()

    def _start_stream(self):
        if self._streaming or self._state != self.ST_READY:
            return
        self._streaming = True
        self._ai_buf    = ""
        self._send_btn.config(state="disabled", text="⏳")
        self._append_ai_start()
        self._chat_write("▌", "thinking")

        messages = self._history.copy()
        model    = self._model

        def run():
            self.after(0, self._remove_cursor)
            chat_stream(
                model    = model,
                messages = messages,
                on_token = lambda t: self.after(0, lambda tok=t: self._append_ai_token(tok)),
                on_done  = lambda: self.after(0, self._on_done),
                on_error = lambda e: self.after(0, lambda err=e: self._on_error(err)),
            )

        threading.Thread(target=run, daemon=True).start()

    def _remove_cursor(self):
        self._chat.configure(state="normal")
        content = self._chat.get("1.0", "end")
        if content.endswith("▌\n"):
            self._chat.delete("end-2c", "end-1c")
        self._chat.configure(state="disabled")

    def _on_done(self):
        self._streaming = False
        self._send_btn.config(state="normal", text="Enviar  ⏎")
        full = self._ai_buf
        self._ai_buf = ""
        self._history.append({"role": "assistant", "content": full})
        cmds = extract_commands(full)
        if cmds:
            self._show_cmd_panel(cmds)
        self._set_status(f"🤙 Maurisio listo — modelo: {self._model}", C["ok"])

    def _on_error(self, err: str):
        self._streaming = False
        self._send_btn.config(state="normal", text="Enviar  ⏎")
        self._chat_write(f"\n[Error con Ollama: {err}]\n", "sys_msg")
        self._set_status(f"❌ Error: {err[:70]}", C["danger"])

    # ── Panel de comandos ─────────────────────────────────────────────────

    def _show_cmd_panel(self, commands: list[str]):
        for w in self._cmd_panel.winfo_children():
            w.destroy()
        self._cmd_panel.pack(fill="x", before=self._status_bar, pady=0)

        hdr = tk.Frame(self._cmd_panel, bg="#1c1408", pady=6, padx=12)
        hdr.pack(fill="x")
        tk.Label(hdr,
                 text=f"⚡ Maurisio propone {len(commands)} comando(s) — confirma antes de ejecutar",
                 font=("Segoe UI", 9, "bold"),
                 bg="#1c1408", fg=C["cmd_fg"]).pack(side="left")
        tk.Button(hdr, text="✕",
                  command=self._hide_cmd_panel,
                  bg="#1c1408", fg=C["muted"],
                  font=F_SMALL, relief="flat", cursor="hand2", padx=4).pack(side="right")

        for cmd in commands:
            row = tk.Frame(self._cmd_panel, bg=C["cmd_bg"], pady=4, padx=12)
            row.pack(fill="x", pady=(0, 1))

            tk.Label(row, text=f"  $ {cmd}",
                     font=("Consolas", 10),
                     bg=C["cmd_bg"], fg=C["cmd_fg"]).pack(side="left", fill="x", expand=True)

            tk.Button(row, text="▶ Ejecutar",
                      command=lambda c=cmd: self._exec_cmd(c),
                      bg="#27460a", fg="#84cc16",
                      font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                      padx=10, pady=3, activebackground="#365f0e").pack(side="right", padx=(4, 0))

            tk.Button(row, text="✕ Ignorar",
                      command=lambda r=row: r.destroy(),
                      bg="#2a1010", fg="#f87171",
                      font=("Segoe UI", 8), relief="flat", cursor="hand2",
                      padx=8, pady=3).pack(side="right")

    def _hide_cmd_panel(self):
        self._cmd_panel.pack_forget()
        for w in self._cmd_panel.winfo_children():
            w.destroy()

    def _exec_cmd(self, cmd_str: str):
        self._append_sys(f"Ejecutando: {cmd_str}")
        ok, result = run_command(cmd_str)
        tag = "ai_msg" if ok else "sys_msg"
        short = result[:250] + ("..." if len(result) > 250 else "")
        self._chat_write(f"\n{short}\n", tag)
        self._history.append({
            "role": "user",
            "content": f"[SISTEMA] Se ejecutó: {cmd_str}\nResultado: {short}"
        })
        self._history.append({
            "role": "assistant",
            "content": "Oído, lo tengo en cuenta."
        })
        self._set_status(
            f"{'✅' if ok else '❌'} {cmd_str} — {short[:55]}",
            C["ok"] if ok else C["danger"],
        )

    # ── Historial de input ────────────────────────────────────────────────

    def _hist_up(self, event=None):
        if not self._user_hist:
            return
        self._hist_idx = min(self._hist_idx + 1, len(self._user_hist) - 1)
        self._input_var.set(self._user_hist[self._hist_idx])
        self._input.icursor("end")

    def _hist_down(self, event=None):
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self._input_var.set("")
            return
        self._hist_idx -= 1
        self._input_var.set(self._user_hist[self._hist_idx])
        self._input.icursor("end")


# ── Tab builder ───────────────────────────────────────────────────────────────

def _build_maurisio_tab(parent_frame, app_ref=None):
    tab = MaurisioTab(parent_frame, app_ref=app_ref)
    tab.place(relx=0, rely=0, relwidth=1, relheight=1)


# ── Abrir desde FyreWall interno ──────────────────────────────────────────────

def _open_in_fyrewall():
    try:
        for _, mod in sys.modules.items():
            if not (hasattr(mod, "FyreWallApp") and hasattr(mod, "_PLUGINS")):
                continue
            for obj_name in dir(mod):
                obj = getattr(mod, obj_name, None)
                if obj.__class__.__name__ == "FyreWallApp":
                    tab_id = "plugin_maurisio"
                    label  = "🤙 Maurisio"
                    if tab_id not in obj._tab_frames:
                        frame = tk.Frame(obj._content, bg=C["bg"])
                        obj._tab_frames[tab_id] = frame
                        _build_maurisio_tab(frame, app_ref=obj)
                    obj._tab_bar.add_tab(tab_id, label)
                    return True
    except Exception:
        pass
    return False


# ── Handler CLI ───────────────────────────────────────────────────────────────

def _cmd_maurisio(args):
    ok = _open_in_fyrewall()
    if ok:
        return "🤙  Maurisio abierto, tío.", "ok"
    return "__PLUGIN_TAB__maurisio.py::maurisio", "info"


FYRE_MANIFEST["commands"][0]["handler"] = "_cmd_maurisio"


# ── Standalone test ───────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("Maurisio — FyreWall (Test Standalone)")
    root.geometry("1050x720")
    root.configure(bg=C["bg"])
    tab = MaurisioTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
