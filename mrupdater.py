"""
Mauricio — El Actualizador Más Chachipén del Barrio
=====================================================
Sin addons.json. Lista los .py del repo directamente con la API de GitHub.
Mauricio se actualiza a sí mismo. Panel lateral ASCII. Humor negro garantizao.

Integración en FyreWall:
  - Pestaña propia:  "💃 Mauricio"
  - Comando CLI:     get-update
"""

import os
import sys
import threading
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error
import json
import shutil
import hashlib

# ── Manifest ───────────────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "Mauricio",
    "version":     "3.0.0",
    "author":      "El Barrio",
    "description": "Actualiza los add-ons desde GitHub sin JSON, ¡más rápido que un gitano huyendo del Hacienda!",
    "commands": [
        {
            "name":        "get-update",
            "kind":        "tab",
            "tab_builder": "_build_mauricio_tab",
            "description": "Abre el instalador Mauricio",
        },
    ],
}

# ── GitHub config ──────────────────────────────────────────────────────────────

GITHUB_API      = "https://api.github.com"
RAW_BASE        = "https://raw.githubusercontent.com"
ADDONS_REPO     = "luckicla/FyreWall-add-ons"
ADDONS_BRANCH   = "main"
FYREWALL_REPO   = "luckicla/FyreWall"   # repo principal — fyrewall.py y mauricio.py
FYREWALL_BRANCH = "main"
SELF_FILE       = "mauricio.py"
FYREWALL_FILE   = "fyrewall.py"
SELF_REPO       = FYREWALL_REPO
SELF_BRANCH     = FYREWALL_BRANCH

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# ── Colores ────────────────────────────────────────────────────────────────────

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
    "blue_btn":     "#1a4a8a",
    "blue_act":     "#2563c0",
    "console_bg":   "#0e1117",
    "console_text": "#c9d1d9",
    "sidebar_bg":   "#0a0c10",
    "sidebar_txt":  "#39ff14",   # verde terminal clásico
    "sidebar_dim":  "#1a6b0a",
    "sidebar_hdr":  "#4da6ff",
    "sidebar_warn": "#f5a623",
    "sidebar_err":  "#e05c5c",
}
F_MONO  = ("Consolas", 9)
F_BODY  = ("Segoe UI", 9)
F_BOLD  = ("Segoe UI", 9, "bold")
F_TITLE = ("Segoe UI", 12, "bold")
F_LBL   = ("Segoe UI", 8, "bold")
F_ASCII = ("Consolas", 8)

# ── Frases de Mauricio — barriobajero con humor negro ─────────────────────────
# Categorías: idle, checking, ok, update, missing, error, install_ok,
#             install_err, self_update_start, self_update_ok, self_update_err,
#             update_all, bored, filosofia

MAURICIO_FRASES = {
    "idle": [
        "...mirando el techo como mi tío en el paro.",
        "...en modo zen. O sea, durmiendo.",
        "...contando los pelos que me quedan.",
        "...esperando que me digas algo, primo.",
        "...haciéndome el muerto pa' que no me den curro.",
        "...pensando en la vida. Y la vida es una puta mierda.",
        "...recordando cuando mi abuelo me decía 'sé alguien'. Mira cómo quedé.",
        "...aquí, más perdido que un gitano en una biblioteca.",
        "...oyendo el silencio. Y el silencio me dice que aquí no hay ná.",
    ],
    "boot": [
        "oi, oi, oi... qué mañana más puta. ¡Voy, voy!",
        "me han despertao antes de las doce, esto es un abuso.",
        "arrancando motores, que pa' esto me pagan (mentira, no cobro ná).",
        "Mauricio en modo ON. Ya podéis temblar.",
        "buenas, si es que se puede llamar buenas a esto.",
    ],
    "checking": [
        "a ver qué tenemos aquí... mirando el repo como mi vecina los vecinos.",
        "consultando GitHub... si los servidores están vivos, que últimamente.",
        "conectando con el barrio virtual... espérate.",
        "oye, un momento que voy a mirar qué hay en el repo, ¿no te digo?",
        "inspeccionando archivos como si fueran droga en la aduana.",
        "a ver si hay algo que actualizar o me puedo volver a dormir.",
        "mirando el catálogo... esto es como el mercadillo pero sin tenderetes.",
        "consultando el repo más rápido que mi primo huye de las deudas.",
    ],
    "catalog_ok": [
        "¡olé! {n} archivos pillao del repo, ¡más rico que el Señor!",
        "{n} cositas encontradas. no está mal pa' un repo sin amo.",
        "¡{n} archivos! el repo está vivo, primo.",
        "pa' variar algo funciona: {n} archivos en el repo.",
    ],
    "all_ok": [
        "¡tó está de rechupete! ni una cosica pa' actualizar. de puta madre.",
        "sin pendientes, primo. pa' que luego digan que no trabajamos.",
        "¡to al día! como el DNI de mi tío... mentira, el de mi tío caducó en 2009.",
        "nada que hacer aquí. más limpio que los bolsillos de mi cuñao.",
        "¡perfecto! si es que cuando quiero, quiero.",
    ],
    "has_updates": [
        "¡{n} cosica(s) anticuás! vamos a ponerlas finas, ¡dale que es gratis!",
        "hay {n} update(s), primo. esto no se puede consentir.",
        "¡{n} archivo(s) por actualizar! más desactualizao que el Windows XP de tu padre.",
        "oye, {n} cositas necesitan arreglarse. ¿a qué esperamos, una invitación?",
    ],
    "ok_file": [
        "'{f}' está fino, como los dientes de mi abuela. los postizos.",
        "'{f}' al día. uno menos. queda lo que queda.",
        "'{f}' correcto. tampoco era pa' tanto.",
        "'{f}' — sin cambios. ni el archivo se mueve, ni yo me muevo.",
    ],
    "update_file": [
        "'{f}' está más anticuao que mi tío el que vende lotería.",
        "'{f}' necesita un arreglito, chaval.",
        "ojo, '{f}' tiene versión nueva. como los Iphone pero sin cobrar el riñón.",
        "'{f}' ha cambiado. igual que mi ex, pa' peor seguramente.",
    ],
    "missing_file": [
        "'{f}' ni está instalao. ¡menuda vergüenza!",
        "'{f}' no existe aquí. como la honradez política.",
        "'{f}' falta. pa' variar algo falta en este barrio.",
        "no hay ni rastro de '{f}'. como el sueldo de fin de mes.",
    ],
    "install_ok": [
        "¡'{f}' quedó más fino que el pelo de un gitano en boda! ¡olé!",
        "'{f}' instalao sin dramas, que ya era hora.",
        "¡'{f}' actualizado! esto sí que es un éxito. apunta.",
        "'{f}' listo. Mauricio lo ha petao otra vez. como siempre.",
        "¡'{f}' instalao! Mauricio para presidente.",
    ],
    "install_err": [
        "mardita sea, '{f}' no ha ido. mira la red, que yo ya no puedo más.",
        "'{f}' se ha resistido. como mi tío a trabajar.",
        "error en '{f}'. no todo puede salir bien, que si no esto sería el cielo.",
        "'{f}' ha fallao. igual que mi dieta, mi novia y mi coche.",
    ],
    "net_err": [
        "sin conexión, primo. ¿qué hacemos aquí sin internet, como los amish?",
        "no hay red. igual que en el extrarradio, que pa' eso estamos.",
        "internet se ha muerto. o GitHub. da igual, el caso es jodernos.",
        "sin red. esto es peor que no tener WhatsApp. casi.",
    ],
    "self_update_start": [
        "¡voy a actualizar MI PROPIO CÓDIGO! esto es como la cirugía propia. dios mío.",
        "Mauricio actualizándose a sí mismo... esto lo hacen solo los dioses y los lerdos.",
        "autoactualización iniciada. si me voy, ha sido un placer, primo.",
        "como la serpiente que se muerde la cola, pero en plan informático.",
        "actualizándome... si esto falla, me reencarn... me reinstalo.",
    ],
    "self_update_ok": [
        "¡me he actualizado y sigo vivo! ¡olé mis cojones!",
        "Mauricio 2.0 en el aire. mismo barrio, mejor código.",
        "autoactualización completada. soy mejor que antes. como siempre.",
        "¡hecho! ahora soy más fino. reinicia pa' que lo notes del todo.",
        "¡me he arreglado a mí mismo! que lo vea mi madre.",
    ],
    "self_update_err": [
        "no pude actualizarme. menos mal que guardé copia. no soy tonto del to.",
        "error en mi propia actualización. qué mal quedo.",
        "algo ha fallao al descargar mi nueva versión. GitHub de mierda.",
        "no me pude actualizar. igual que mi vecino, que sigue igual de inútil.",
    ],
    "self_already_ok": [
        "ya soy la versión más chachipén. no hay ná mejor que yo en el repo.",
        "estoy al día, primo. no necesito nada. soy perfecto.",
        "sin actualizaciones pa' mí. pa' variar, soy el más fino del barrio.",
    ],
    "bak": [
        "copia de seguridad guardada. Mauricio siempre cura las espaldas.",
        "backup hecho. que no se diga que somos imprudentes.",
        "guardao el original. por si acaso. que a veces los milagros no existen.",
    ],
    "update_all_start": [
        "¡Mauricio va a por tó! agárrate los calzones, primo.",
        "actualización masiva en marcha. como una redada pero con bytes.",
        "vamos a poner tó al día de una puta vez. ¡a la carga!",
    ],
    "no_pending": [
        "pos no hay ná pendiente, que te crees tú eso.",
        "ya está tó actualizado. ¿pa' qué me llamas?",
        "sin pendientes. puedes irte a fregar.",
    ],
    "filosofia": [
        "la vida es eso que pasa mientras esperas que cargue GitHub.",
        "actualizar código es como afeitarse: si no lo haces, pasa lo que pasa.",
        "en este barrio o te actualizas o te queda obsoleto. como los VHS.",
        "el código sin actualizar es como la leche caducada: huele mal.",
        "cada update es una segunda oportunidad. ojalá la vida diera updates.",
        "la copia de seguridad es el condón del informático. úsala siempre.",
        "si funciona, no lo toques. si no funciona, llama a Mauricio.",
        "el chaos no es un bug, es una feature. dijo alguien muy listo o muy gilipollas.",
    ],
    "reload": [
        "↺ volviendo a mirar. Mauricio no se rinde.",
        "↺ recargando, que igual han subido algo mientras tanto.",
        "↺ venga, otra vuelta. como en la mili pero sin la mili.",
    ],
}

def _frase(categoria, **kwargs):
    """Devuelve una frase aleatoria de la categoría, formateada si hace falta."""
    frases = MAURICIO_FRASES.get(categoria, ["..."])
    f = random.choice(frases)
    try:
        return f.format(**kwargs) if kwargs else f
    except Exception:
        return f

# ── App reference ──────────────────────────────────────────────────────────────

_app_ref = None

def _set_app(app):
    global _app_ref
    _app_ref = app

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _api_get(path: str):
    url = f"{GITHUB_API}/{path}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Mauricio/3.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _raw_get(repo: str, branch: str, filepath: str) -> bytes | None:
    url = f"{RAW_BASE}/{repo}/{branch}/{filepath}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mauricio/3.0"})
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

# ── Catálogo dinámico SIN JSON — lista el repo directamente ───────────────────

def fetch_addons_catalog() -> list[dict] | None:
    """
    Lista los .py del repo de add-ons usando la API de GitHub.
    No necesita ningún addons.json.
    Devuelve lista de dicts con 'file', 'name', 'description'.
    """
    data = _api_get(f"repos/{ADDONS_REPO}/contents?ref={ADDONS_BRANCH}")
    if data is None or not isinstance(data, list):
        return None
    catalog = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fname = item.get("name", "")
        if not fname.lower().endswith(".py"):
            continue
        catalog.append({
            "file":        fname,
            "name":        fname.replace(".py", "").replace("_", " ").title(),
            "description": f"Add-on del barrio ({fname})",
            "sha":         item.get("sha", ""),   # sha del árbol de git (no sha256)
        })
    return catalog if catalog else None


# ── Comprobación de actualizaciones ──────────────────────────────────────────

def check_all_updates(catalog: list[dict]) -> dict:
    results = {}
    for entry in catalog:
        fname      = entry["file"]
        local_path = os.path.join(APP_DIR, fname)
        local_exists = os.path.exists(local_path)
        local_sha    = _local_sha256(local_path) if local_exists else None
        remote_data  = _raw_get(ADDONS_REPO, ADDONS_BRANCH, fname)

        base = {
            "name":        entry["name"],
            "description": entry["description"],
            "repo":        ADDONS_REPO,
            "branch":      ADDONS_BRANCH,
            "file":        fname,
            "local_sha":   local_sha,
        }

        if remote_data is None:
            results[fname] = {**base, "status": "error",
                              "remote_sha": None, "_data": None,
                              "local_exists": local_exists}
            continue

        remote_sha = _sha256(remote_data)
        base["remote_sha"] = remote_sha
        base["_data"]      = remote_data
        base["local_exists"] = local_exists

        if not local_exists:
            results[fname] = {**base, "status": "missing"}
        elif local_sha == remote_sha:
            results[fname] = {**base, "status": "ok"}
        else:
            results[fname] = {**base, "status": "update"}

    return results


def apply_update(info: dict) -> tuple[bool, str]:
    data = info.get("_data")
    if data is None:
        data = _raw_get(info["repo"], info["branch"], info["file"])
    if data is None:
        return False, _frase("install_err", f=info["file"])

    dest = os.path.join(APP_DIR, info["file"])
    bak  = dest + ".bak"
    if os.path.exists(dest):
        try:
            shutil.copy2(dest, bak)
        except Exception:
            pass

    try:
        with open(dest, "wb") as fh:
            fh.write(data)
        return True, _frase("install_ok", f=info["file"])
    except Exception as e:
        if os.path.exists(bak):
            shutil.copy2(bak, dest)
        return False, _frase("install_err", f=info["file"]) + f" ({e})"


# ── Self-update: Mauricio se actualiza a sí mismo ─────────────────────────────

def check_self_update() -> dict:
    """Comprueba si hay una versión nueva de mauricio.py en el repo principal."""
    self_path = os.path.abspath(__file__)
    local_sha  = _local_sha256(self_path)
    remote_data = _raw_get(SELF_REPO, SELF_BRANCH, SELF_FILE)
    if remote_data is None:
        return {"status": "error", "local_sha": local_sha, "remote_sha": None, "_data": None}
    remote_sha = _sha256(remote_data)
    if local_sha == remote_sha:
        return {"status": "ok", "local_sha": local_sha, "remote_sha": remote_sha, "_data": remote_data}
    return {"status": "update", "local_sha": local_sha, "remote_sha": remote_sha, "_data": remote_data}


def apply_self_update(info: dict) -> tuple[bool, str]:
    """Sobreescribe mauricio.py con la versión descargada del repo."""
    data = info.get("_data")
    if data is None:
        return False, _frase("self_update_err")
    self_path = os.path.abspath(__file__)
    bak = self_path + ".bak"
    if os.path.exists(self_path):
        try:
            shutil.copy2(self_path, bak)
        except Exception:
            pass
    try:
        with open(self_path, "wb") as fh:
            fh.write(data)
        return True, _frase("self_update_ok")
    except Exception as e:
        if os.path.exists(bak):
            shutil.copy2(bak, self_path)
        return False, _frase("self_update_err") + f" ({e})"


# ── Pixel-art de Mauricio — cara única dibujada en Canvas ────────────────────
#
# Grid de 15 cols x 16 filas, bloques de 8px => Canvas 120x128px
# Leyenda: H=pelo  S=skin  E=ojos  M=boca  B=sombra  C=camisa  .=vacío
MAURICIO_PIXELS = [
    ". . . . H H H H H H H . . . .",
    ". . H H H H H H H H H H H . .",
    ". H H H H H H H H H H H H H .",
    ". H S S S S S S S S S S S H .",
    ". H S S S S S S S S S S S H .",
    "H H S S E S S S S S E S S H H",
    "H H S S E S S S S S E S S H H",
    "H H S S S S S S S S S S S H H",
    ". H S S S M M M M M S S S H .",
    ". H S S S S B B B S S S S H .",
    ". H H S S S S S S S S S H H .",
    ". . H H C C C C C C C H H . .",
    ". . . C C C C C C C C C . . .",
    ". . . C C C C C C C C C . . .",
    ". . . C C . . . . . C C . . .",
    ". . . C C . . . . . C C . . .",
]

_MOOD_PALETTES = {
    "idle": {
        "H": "#2d1b0e", "S": "#c8956a", "E": "#1a0a00",
        "M": "#7a3030", "B": "#9a6848", "C": "#1e3f6e",
    },
    "working": {
        "H": "#2d1b0e", "S": "#c8956a", "E": "#f5a623",
        "M": "#d4820a", "B": "#9a6848", "C": "#6b3a08",
    },
    "ok": {
        "H": "#2d1b0e", "S": "#c8956a", "E": "#27ae60",
        "M": "#1e8040", "B": "#9a6848", "C": "#1a5c2a",
    },
    "error": {
        "H": "#2d1b0e", "S": "#c8956a", "E": "#e05c5c",
        "M": "#b01818", "B": "#9a6848", "C": "#4a0f0f",
    },
}
_PX = 8   # píxeles reales por "pixel" de arte
_CW = 15 * _PX   # 120
_CH = 16 * _PX   # 128


def draw_mauricio(canvas: tk.Canvas, mood: str = "idle"):
    """Redibuja la cara pixel-art de Mauricio en el canvas."""
    canvas.delete("all")
    pal = _MOOD_PALETTES.get(mood, _MOOD_PALETTES["idle"])
    for r, row in enumerate(MAURICIO_PIXELS):
        for c, cell in enumerate(row.split()):
            if cell == ".":
                continue
            col = pal.get(cell, "#ffffff")
            x0, y0 = c * _PX, r * _PX
            canvas.create_rectangle(x0, y0, x0 + _PX, y0 + _PX,
                                    fill=col, outline="", width=0)
    # Brillo en ojos cuando está activo
    if mood in ("working", "ok"):
        for r, row in enumerate(MAURICIO_PIXELS):
            for c, cell in enumerate(row.split()):
                if cell == "E":
                    x0, y0 = c * _PX + 1, r * _PX + 1
                    canvas.create_rectangle(x0, y0, x0 + 3, y0 + 3,
                                            fill="#ffffff", outline="", width=0)

# ── FyreWall update: lista el repo y busca fyrewall.py ───────────────────────

def check_fyrewall_update() -> dict:
    """
    Busca fyrewall.py en el repo luckicla/FyreWall usando la API de GitHub.
    No necesita ningún JSON. Devuelve dict con status ok/update/error.
    """
    local_path = os.path.join(APP_DIR, FYREWALL_FILE)
    local_sha  = _local_sha256(local_path) if os.path.exists(local_path) else None

    # Listamos el repo para confirmar que fyrewall.py existe (sin json)
    items = _api_get(f"repos/{FYREWALL_REPO}/contents?ref={FYREWALL_BRANCH}")
    if items is None or not isinstance(items, list):
        return {"status": "error", "local_sha": local_sha, "remote_sha": None, "_data": None}

    found = any(
        isinstance(i, dict) and i.get("name", "").lower() == FYREWALL_FILE
        for i in items
    )
    if not found:
        return {"status": "error", "local_sha": local_sha, "remote_sha": None, "_data": None,
                "msg": f"{FYREWALL_FILE} no encontrado en el repo"}

    remote_data = _raw_get(FYREWALL_REPO, FYREWALL_BRANCH, FYREWALL_FILE)
    if remote_data is None:
        return {"status": "error", "local_sha": local_sha, "remote_sha": None, "_data": None}

    remote_sha = _sha256(remote_data)
    if local_sha == remote_sha:
        return {"status": "ok", "local_sha": local_sha, "remote_sha": remote_sha, "_data": remote_data}
    return {"status": "update", "local_sha": local_sha, "remote_sha": remote_sha, "_data": remote_data}


def apply_fyrewall_update(info: dict) -> tuple[bool, str]:
    """Actualiza fyrewall.py. Guarda .bak primero."""
    data = info.get("_data")
    if data is None:
        return False, "no hay datos descargados, chato."
    dest = os.path.join(APP_DIR, FYREWALL_FILE)
    bak  = dest + ".bak"
    if os.path.exists(dest):
        try:
            shutil.copy2(dest, bak)
        except Exception:
            pass
    try:
        with open(dest, "wb") as fh:
            fh.write(data)
        return True, f"¡{FYREWALL_FILE} actualizado! reinicia pa que surta efecto, primo."
    except Exception as e:
        if os.path.exists(bak):
            shutil.copy2(bak, dest)
        return False, f"error actualizando {FYREWALL_FILE}: {e}"


# ── Tab principal ──────────────────────────────────────────────────────────────

class MauricioTab(tk.Frame):

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
        self._catalog: list   = []
        self._check_results: dict = {}
        self._row_widgets: dict   = {}
        self._checking        = False
        self._sidebar_lines: list = []   # buffer de líneas del log lateral
        self._mauricio_mood   = "idle"   # idle | working | ok | error
        self._idle_timer: str | None = None
        self._build_shell()
        self.after(300, self._do_check)
        self._schedule_idle_chatter()

    # ─────────────────────────────────────────────────────────────────────
    # Construcción del layout principal
    # ─────────────────────────────────────────────────────────────────────

    def _build_shell(self):
        # ── Cabecera ──────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["surface"], pady=10, padx=16)
        hdr.pack(fill="x")

        tk.Label(hdr, text="💃  Mauricio",
                 font=F_TITLE, bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Label(hdr, text="  —  El actualizador más chachipén del barrio",
                 font=F_BODY, bg=C["surface"], fg=C["muted"]).pack(side="left")

        # Botones cabecera
        self._self_update_btn = tk.Button(
            hdr, text="🔄 Mauricio",
            command=self._do_self_update,
            bg="#3a2060", fg="#c084fc",
            font=F_BODY, relief="flat", cursor="hand2",
            padx=8, pady=4, activebackground="#4a3070",
        )
        self._self_update_btn.pack(side="right", padx=(0, 4))

        self._fyrewall_update_btn = tk.Button(
            hdr, text="🔥 FyreWall",
            command=self._do_fyrewall_update,
            bg="#3a1010", fg="#ff7070",
            font=F_BODY, relief="flat", cursor="hand2",
            padx=8, pady=4, activebackground="#5a1818",
        )
        self._fyrewall_update_btn.pack(side="right", padx=(0, 4))

        tk.Label(hdr, text="Actualizar →",
                 font=("Segoe UI", 7), bg=C["surface"], fg=C["muted"]).pack(side="right", padx=(0, 2))

        self._reload_btn = tk.Button(
            hdr, text="↺  Recargar",
            command=self._do_check,
            bg=C["btn"], fg=C["muted"],
            font=F_BODY, relief="flat", cursor="hand2",
            padx=10, pady=4, activebackground=C["btn_h"],
        )
        self._reload_btn.pack(side="right", padx=(0, 8))

        # ── Banner (oculto inicialmente) ──────────────────────────────────
        self._banner_frame = tk.Frame(self, bg=C["warn"], pady=0)
        self._banner_lbl   = tk.Label(
            self._banner_frame, text="",
            font=F_BOLD, bg=C["warn"], fg="#000000", padx=16, pady=8,
        )
        self._banner_lbl.pack(side="left")
        self._update_all_btn = tk.Button(
            self._banner_frame,
            text="⬆️  Actualizar tó",
            command=self._update_all,
            bg="#7a5000", fg="#ffffff",
            font=F_BOLD, relief="flat", cursor="hand2",
            padx=12, pady=6, activebackground="#9a6500",
        )

        # ── Cuerpo: área principal + sidebar ─────────────────────────────
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # Sidebar (columna derecha) — log de Mauricio en ASCII
        self._sidebar = tk.Frame(body, bg=C["sidebar_bg"], width=260)
        self._sidebar.pack(side="right", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Separador vertical
        tk.Frame(body, bg=C["border"], width=1).pack(side="right", fill="y")

        # Área principal (scroll + filas)
        main_area = tk.Frame(body, bg=C["bg"])
        main_area.pack(side="left", fill="both", expand=True)

        # Scroll area para las filas de add-ons
        scroll_outer = tk.Frame(main_area, bg=C["bg"])
        scroll_outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_outer, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=C["bg"])
        win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(win_id, width=e.width)
        )
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * int(e.delta / 120), "units")
        )

        # Placeholder mientras carga
        self._placeholder = tk.Label(
            self._inner,
            text="⏳  Mauricio está mirando el repo, ¡aguanta un momento, primo!",
            font=F_BODY, bg=C["bg"], fg=C["muted"], pady=30,
        )
        self._placeholder.pack()

    # ─────────────────────────────────────────────────────────────────────
    # Sidebar: zona de registros ASCII con Mauricio hablando
    # ─────────────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        # ── Cabecera del sidebar ──────────────────────────────────────────
        hdr = tk.Frame(self._sidebar, bg=C["surface"], pady=4)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📟 MAURICIO DICE",
                 font=F_LBL, bg=C["surface"], fg=C["sidebar_hdr"]).pack(side="left", padx=8)
        tk.Button(
            hdr, text="🗑",
            command=self._clear_sidebar,
            bg=C["surface"], fg=C["muted"],
            font=("Segoe UI", 7), relief="flat", cursor="hand2",
            padx=4, pady=0,
        ).pack(side="right", padx=4)

        # ── Cara pixel-art centrada ───────────────────────────────────────
        art_frame = tk.Frame(self._sidebar, bg=C["sidebar_bg"], pady=8)
        art_frame.pack(fill="x")
        self._face_canvas = tk.Canvas(
            art_frame,
            width=_CW, height=_CH,
            bg=C["sidebar_bg"], highlightthickness=0,
        )
        self._face_canvas.pack(anchor="center")
        draw_mauricio(self._face_canvas, "idle")

        # ── Label de estado bajo la cara ──────────────────────────────────
        self._mood_lbl = tk.Label(
            self._sidebar, text="idle...",
            font=("Consolas", 7), bg=C["sidebar_bg"], fg=C["sidebar_dim"],
        )
        self._mood_lbl.pack()

        # ── Speech bubble ─────────────────────────────────────────────────
        self._bubble_var = tk.StringVar(value="...")
        bubble_frame = tk.Frame(self._sidebar, bg=C["sidebar_bg"], pady=2)
        bubble_frame.pack(fill="x", padx=6)
        tk.Label(bubble_frame, text="┌───────────────────┐",
                 font=F_ASCII, bg=C["sidebar_bg"], fg=C["sidebar_dim"]).pack(anchor="w")
        self._bubble_lbl = tk.Label(
            bubble_frame, textvariable=self._bubble_var,
            font=F_ASCII, bg=C["sidebar_bg"], fg=C["sidebar_txt"],
            justify="left", wraplength=220, anchor="w",
        )
        self._bubble_lbl.pack(anchor="w", padx=6)
        tk.Label(bubble_frame, text="└───────────────────┘",
                 font=F_ASCII, bg=C["sidebar_bg"], fg=C["sidebar_dim"]).pack(anchor="w")
        tk.Label(bubble_frame, text="   ^",
                 font=F_ASCII, bg=C["sidebar_bg"], fg=C["sidebar_dim"]).pack(anchor="w", padx=12)

        # ── Separador ─────────────────────────────────────────────────────
        tk.Frame(self._sidebar, bg=C["border"], height=1).pack(fill="x", pady=2)

        # ── Log scrollable ────────────────────────────────────────────────
        log_frame = tk.Frame(self._sidebar, bg=C["sidebar_bg"])
        log_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._sidebar_log = tk.Text(
            log_frame,
            bg=C["sidebar_bg"], fg=C["sidebar_txt"],
            font=F_ASCII, relief="flat", bd=0,
            state="disabled", wrap="word", padx=6, pady=4,
            width=30,
        )
        sb_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._sidebar_log.yview)
        self._sidebar_log.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side="right", fill="y")
        self._sidebar_log.pack(side="left", fill="both", expand=True)

        # Tags del log lateral
        self._sidebar_log.tag_configure("ok",     foreground=C["ok"])
        self._sidebar_log.tag_configure("warn",   foreground=C["warn"])
        self._sidebar_log.tag_configure("err",    foreground=C["danger"])
        self._sidebar_log.tag_configure("info",   foreground=C["sidebar_txt"])
        self._sidebar_log.tag_configure("muted",  foreground=C["sidebar_dim"])
        self._sidebar_log.tag_configure("header", foreground=C["sidebar_hdr"],
                                        font=("Consolas", 8, "bold"))
        self._sidebar_log.tag_configure("purple", foreground="#c084fc")

    def _sidebar_write(self, text: str, tag: str = "info"):
        """Escribe en el log lateral y actualiza el bubble de Mauricio."""
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}"
        self._sidebar_log.configure(state="normal")
        self._sidebar_log.insert("end", line + "\n", tag)
        self._sidebar_log.configure(state="disabled")
        self._sidebar_log.see("end")
        # Actualiza el speech bubble con las últimas palabras
        short = text[:60] + ("..." if len(text) > 60 else "")
        self._bubble_var.set(short)

    def _clear_sidebar(self):
        self._sidebar_log.configure(state="normal")
        self._sidebar_log.delete("1.0", "end")
        self._sidebar_log.configure(state="disabled")
        self._bubble_var.set("...")

    def _set_mood(self, mood: str):
        """Redibuja la cara pixel-art según el mood."""
        self._mauricio_mood = mood
        draw_mauricio(self._face_canvas, mood)
        mood_texts = {
            "idle":    "en modo zen...",
            "working": "currando...",
            "ok":      "todo fino!",
            "error":   "mardita sea!",
        }
        mood_colors = {
            "idle":    C["sidebar_dim"],
            "working": C["warn"],
            "ok":      C["ok"],
            "error":   C["danger"],
        }
        self._mood_lbl.config(
            text=mood_texts.get(mood, "..."),
            fg=mood_colors.get(mood, C["sidebar_dim"]),
        )

    def _schedule_idle_chatter(self):
        """Mauricio habla solo de vez en cuando cuando está aburrido."""
        def chatter():
            if self._mauricio_mood == "idle":
                frase = _frase(random.choice(["idle", "filosofia"]))
                self._sidebar_write(frase, "muted")
                self._bubble_var.set(frase[:60] + ("..." if len(frase) > 60 else ""))
            # Próxima charla en 15-40 segundos
            delay = random.randint(15000, 40000)
            self._idle_timer = self.after(delay, chatter)
        delay = random.randint(8000, 18000)
        self._idle_timer = self.after(delay, chatter)

    # ─────────────────────────────────────────────────────────────────────
    # Construir filas dinámicamente
    # ─────────────────────────────────────────────────────────────────────

    def _rebuild_rows(self, catalog: list[dict]):
        if self._placeholder and self._placeholder.winfo_exists():
            self._placeholder.destroy()
            self._placeholder = None

        for w in list(self._row_widgets.values()):
            try:
                w["row"].destroy()
            except Exception:
                pass
        self._row_widgets.clear()

        sec = tk.Frame(self._inner, bg=C["bg"], padx=20, pady=10)
        sec.pack(fill="x")

        hdr = tk.Frame(sec, bg=C["surface"], pady=8, padx=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📦  ADD-ONS DEL BARRIO", font=F_LBL,
                 bg=C["surface"], fg=C["accent"]).pack(side="left")
        tk.Label(hdr, text=f"  ({len(catalog)} disponibles en el repo)",
                 font=F_BODY, bg=C["surface"], fg=C["muted"]).pack(side="left")

        self._addon_sec = sec
        for entry in catalog:
            self._build_file_row(sec, entry)

    def _build_file_row(self, parent, entry: dict):
        fname = entry["file"]
        row   = tk.Frame(parent, bg=C["surface2"], pady=0)
        row.pack(fill="x", pady=(1, 0))

        inner = tk.Frame(row, bg=C["surface2"], padx=12, pady=10)
        inner.pack(fill="x")

        icon_lbl = tk.Label(inner, text="⏳", font=("Segoe UI", 14),
                            bg=C["surface2"], fg=C["muted"])
        icon_lbl.pack(side="left", padx=(0, 10))

        info_col = tk.Frame(inner, bg=C["surface2"])
        info_col.pack(side="left", fill="x", expand=True)

        name_lbl = tk.Label(info_col, text=entry.get("name", fname),
                            font=F_BOLD, bg=C["surface2"], fg=C["text"])
        name_lbl.pack(anchor="w")

        if entry.get("description"):
            tk.Label(info_col, text=entry["description"], font=("Segoe UI", 8),
                     bg=C["surface2"], fg=C["muted"]).pack(anchor="w")

        status_lbl = tk.Label(info_col, text="Mauricio está mirando...",
                              font=F_BODY, bg=C["surface2"], fg=C["muted"])
        status_lbl.pack(anchor="w")

        sha_lbl = tk.Label(info_col, text="", font=F_MONO,
                           bg=C["surface2"], fg=C["muted"])
        sha_lbl.pack(anchor="w")

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
        }

    # ─────────────────────────────────────────────────────────────────────
    # Check de actualizaciones
    # ─────────────────────────────────────────────────────────────────────

    def _do_check(self):
        if self._checking:
            return
        self._checking = True
        self._set_mood("working")
        self._reload_btn.config(state="disabled", text="⏳ mirando...")
        frase = _frase("checking")
        self._sidebar_write(f"[CHECK] {frase}", "header")
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        catalog = fetch_addons_catalog()
        if catalog is None:
            self.after(0, self._on_catalog_error)
            return
        results = check_all_updates(catalog)
        self.after(0, lambda c=catalog, r=results: self._render_check(c, r))

    def _on_catalog_error(self):
        self._checking = False
        self._set_mood("error")
        self._reload_btn.config(state="normal", text="↺  Recargar")
        frase = _frase("net_err")
        self._sidebar_write(f"[ERROR] {frase}", "err")
        self._sidebar_write("       (el repo está on vacation o no hay net)", "muted")

    def _render_check(self, catalog: list[dict], results: dict):
        self._catalog       = catalog
        self._check_results = results
        self._checking      = False
        self._reload_btn.config(state="normal", text="↺  Recargar")

        n_catalog = len(catalog)
        frase_cat = _frase("catalog_ok", n=n_catalog)
        self._sidebar_write(f"[REPO] {frase_cat}", "info")

        known = set(self._row_widgets.keys())
        fresh = {e["file"] for e in catalog}
        if known != fresh:
            self._rebuild_rows(catalog)

        for fname, widgets in self._row_widgets.items():
            icon, color = self.STATUS_ICONS["loading"]
            widgets["icon"].config(text=icon, fg=color)
            widgets["status_lbl"].config(text="Mauricio está mirando...", fg=C["muted"])
            widgets["sha_lbl"].config(text="")
            widgets["install"].pack_forget()
            widgets["update"].pack_forget()

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

            if status == "ok":
                widgets["status_lbl"].config(text="Al día, ¡dale que sí!", fg=C["ok"])
                widgets["sha_lbl"].config(text=f"SHA: {lsha}", fg=C["muted"])
                frase = _frase("ok_file", f=fname)
                self._sidebar_write(f"  ✅ {frase}", "ok")

            elif status == "update":
                widgets["status_lbl"].config(text="⚠️  ¡Hay actualización, chaval!", fg=C["warn"])
                widgets["sha_lbl"].config(text=f"Local: {lsha}  →  Remoto: {rsha}", fg=C["warn"])
                widgets["update"].pack(side="left", padx=(0, 4))
                frase = _frase("update_file", f=fname)
                self._sidebar_write(f"  ⬆️  {frase}", "warn")
                updates += 1

            elif status == "missing":
                widgets["status_lbl"].config(text="📥 Sin instalar — ¡ponlo ya, hombre!", fg=C["accent"])
                widgets["sha_lbl"].config(text=f"Remoto: {rsha}", fg=C["muted"])
                widgets["install"].pack(side="left", padx=(0, 4))
                frase = _frase("missing_file", f=fname)
                self._sidebar_write(f"  📥 {frase}", "info")
                missing += 1

            elif status == "error":
                widgets["status_lbl"].config(text="❌ Mauricio no pudo comprobarlo", fg=C["danger"])
                widgets["sha_lbl"].config(text="Sin red o el repo de vacaciones", fg=C["danger"])
                self._sidebar_write(f"  ❌ {fname} — {_frase('net_err')}", "err")

        total_pending = updates + missing
        if total_pending > 0:
            self._set_mood("working")
            banner_text = _frase("has_updates", n=total_pending)
            self._banner_lbl.config(text=banner_text, bg=C["warn"], fg="#000000")
            self._banner_frame.config(bg=C["warn"])
            self._update_all_btn.pack(side="right", padx=12, pady=4)
            self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
            self._sidebar_write(f"\n  → {total_pending} cosa(s) pa arreglar. ¡venga ya!", "warn")
        else:
            self._set_mood("ok")
            has_ok = any(i["status"] == "ok" for i in results.values())
            if has_ok:
                self._banner_frame.config(bg=C["ok"])
                self._banner_lbl.config(text=_frase("all_ok"), bg=C["ok"], fg="#000000")
                self._update_all_btn.pack_forget()
                self._banner_frame.pack(fill="x", after=self.winfo_children()[0])
            frase = _frase("all_ok")
            self._sidebar_write(f"\n  🏆 {frase}", "ok")
            # Pequeño chiste filosófico tras checkear
            self.after(2000, lambda: self._sidebar_write(
                "  " + _frase("filosofia"), "muted"))
            # Volver a idle tras 3 segundos
            self.after(3000, lambda: self._set_mood("idle"))

    # ─────────────────────────────────────────────────────────────────────
    # Instalar / actualizar add-on
    # ─────────────────────────────────────────────────────────────────────

    def _install_single(self, fname: str):
        info   = self._check_results.get(fname)
        if not info:
            self._sidebar_write(f"❌ Mauricio no sabe ná de {fname}. ¿de qué barrio eres?", "err")
            return
        status = info["status"]
        action = "instalar" if status == "missing" else "actualizar"

        if not messagebox.askyesno(
            "¿Le damos?",
            f"¿{action.capitalize()} '{fname}', primo?\n\n"
            f"Mauricio lo baja de GitHub y lo mete en:\n{APP_DIR}\n\n"
            "El original se guarda como .bak, que Mauricio no es un irresponsable.",
            parent=self,
        ):
            return

        self._set_mood("working")
        self._sidebar_write(f"\n  ▶  Mauricio va a {action} {fname}...", "header")
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="disabled")

        def run():
            ok, msg = apply_update(info)
            self.after(0, lambda o=ok, m=msg, f=fname: self._after_install(o, m, f))

        threading.Thread(target=run, daemon=True).start()

    def _after_install(self, ok: bool, msg: str, fname: str):
        self._sidebar_write(f"  {msg}", "ok" if ok else "err")
        self._set_mood("ok" if ok else "error")
        widgets = self._row_widgets.get(fname, {})
        for btn_key in ("install", "update"):
            if widgets.get(btn_key):
                widgets[btn_key].config(state="normal")
        if ok:
            # Nota sobre backup
            self._sidebar_write(f"  💾 {_frase('bak')}", "muted")
            self._do_check()
            if _app_ref:
                try:
                    _load_plugin_external(os.path.join(APP_DIR, fname))
                    self._sidebar_write(f"  🔄 {fname} recargao en el manager, ¡olé!", "info")
                except Exception:
                    self._sidebar_write(f"  ℹ️  Reinicia pa que coja {fname}, anda.", "muted")
        self.after(4000, lambda: self._set_mood("idle"))

    def _update_all(self):
        pending = {
            f: info for f, info in self._check_results.items()
            if info["status"] in ("update", "missing")
        }
        if not pending:
            self._sidebar_write(_frase("no_pending"), "muted")
            return

        names = ", ".join(pending.keys())
        if not messagebox.askyesno(
            "¿Actualizamos tó?",
            f"Mauricio va a por:\n\n{names}\n\n"
            "Los archivos actuales se guardan como .bak.\n¿Le damos, primo?",
            parent=self,
        ):
            return

        self._set_mood("working")
        self._sidebar_write(f"\n  {_frase('update_all_start')}", "header")
        self._update_all_btn.config(state="disabled")

        def run():
            for fname, info in pending.items():
                ok, msg = apply_update(info)
                self.after(0, lambda o=ok, m=msg: self._sidebar_write(
                    f"  {m}", "ok" if o else "err"))
            self.after(200, self._do_check)
            self.after(0, lambda: self._update_all_btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    # Self-update: Mauricio se actualiza a sí mismo
    # ─────────────────────────────────────────────────────────────────────

    def _do_self_update(self):
        if not messagebox.askyesno(
            "¿Actualizar Mauricio?",
            "Mauricio va a descargarse a sí mismo del repo.\n\n"
            "Si algo falla, se guarda una copia .bak.\n"
            "Tras la actualización reinicia FyreWall pa' que surta efecto.\n\n"
            "¿Le damos, primo?",
            parent=self,
        ):
            return

        self._set_mood("working")
        self._self_update_btn.config(state="disabled", text="⏳ actualizándome...")
        self._sidebar_write(f"\n  🔄 {_frase('self_update_start')}", "purple")

        def run():
            info = check_self_update()
            if info["status"] == "ok":
                self.after(0, lambda: self._after_self_update_ok_already())
                return
            if info["status"] == "error":
                self.after(0, lambda: self._after_self_update_fail(_frase("self_update_err")))
                return
            # Hay actualización: aplicarla
            ok, msg = apply_self_update(info)
            lsha = (info.get("local_sha") or "—")[:12]
            rsha = (info.get("remote_sha") or "—")[:12]
            self.after(0, lambda o=ok, m=msg, l=lsha, r=rsha: self._after_self_update(o, m, l, r))

        threading.Thread(target=run, daemon=True).start()

    def _after_self_update_ok_already(self):
        self._set_mood("ok")
        self._self_update_btn.config(state="normal", text="🔄 Actualizar Mauricio")
        msg = _frase("self_already_ok")
        self._sidebar_write(f"  ✅ {msg}", "ok")
        self.after(3000, lambda: self._set_mood("idle"))

    def _after_self_update_fail(self, msg: str):
        self._set_mood("error")
        self._self_update_btn.config(state="normal", text="🔄 Actualizar Mauricio")
        self._sidebar_write(f"  ❌ {msg}", "err")
        self.after(3000, lambda: self._set_mood("idle"))

    def _after_self_update(self, ok: bool, msg: str, lsha: str, rsha: str):
        self._self_update_btn.config(state="normal", text="🔄 Mauricio")
        if ok:
            self._set_mood("ok")
            self._sidebar_write(f"  🎉 {msg}", "ok")
            self._sidebar_write(f"  📦 {lsha} → {rsha}", "muted")
            self._sidebar_write("  💾 " + _frase("bak"), "muted")
            self._sidebar_write("  ↺  Reinicia FyreWall pa que el nuevo Mauricio despierte.", "warn")
        else:
            self._set_mood("error")
            self._sidebar_write(f"  ❌ {msg}", "err")
        self.after(4000, lambda: self._set_mood("idle"))

    # ─────────────────────────────────────────────────────────────────────
    # FyreWall update: actualiza fyrewall.py desde el repo principal
    # ─────────────────────────────────────────────────────────────────────

    def _do_fyrewall_update(self):
        if not messagebox.askyesno(
            "¿Actualizar FyreWall?",
            f"Mauricio va a buscar {FYREWALL_FILE} en:\n{FYREWALL_REPO}\n\n"
            "Si hay versión nueva la descarga y guarda .bak del original.\n"
            "Reinicia la app pa que surta efecto.\n\n"
            "¿Le damos, primo?",
            parent=self,
        ):
            return

        self._set_mood("working")
        self._fyrewall_update_btn.config(state="disabled", text="⏳ buscando...")
        self._sidebar_write(
            "\n  🔥 Mauricio va a por FyreWall... esto sí que es serio.", "header")

        def run():
            info = check_fyrewall_update()
            if info["status"] == "ok":
                self.after(0, self._after_fyrewall_already_ok)
                return
            if info["status"] == "error":
                err_msg = info.get("msg", _frase("net_err"))
                self.after(0, lambda m=err_msg: self._after_fyrewall_fail(m))
                return
            ok, msg = apply_fyrewall_update(info)
            lsha = (info.get("local_sha") or "—")[:12]
            rsha = (info.get("remote_sha") or "—")[:12]
            self.after(0, lambda o=ok, m=msg, l=lsha, r=rsha:
                       self._after_fyrewall_update(o, m, l, r))

        threading.Thread(target=run, daemon=True).start()

    def _after_fyrewall_already_ok(self):
        self._set_mood("ok")
        self._fyrewall_update_btn.config(state="normal", text="🔥 FyreWall")
        self._sidebar_write(
            "  ✅ FyreWall ya está al día. ni yo lo hubiera hecho mejor.", "ok")
        self.after(3000, lambda: self._set_mood("idle"))

    def _after_fyrewall_fail(self, msg: str):
        self._set_mood("error")
        self._fyrewall_update_btn.config(state="normal", text="🔥 FyreWall")
        self._sidebar_write(f"  ❌ {msg}", "err")
        self.after(3000, lambda: self._set_mood("idle"))

    def _after_fyrewall_update(self, ok: bool, msg: str, lsha: str, rsha: str):
        self._fyrewall_update_btn.config(state="normal", text="🔥 FyreWall")
        if ok:
            self._set_mood("ok")
            self._sidebar_write(f"  🔥 {msg}", "ok")
            self._sidebar_write(f"  📦 {lsha} → {rsha}", "muted")
            self._sidebar_write("  💾 " + _frase("bak"), "muted")
            self._sidebar_write("  ↺  Cierra y abre FyreWall pa que se note, primo.", "warn")
        else:
            self._set_mood("error")
            self._sidebar_write(f"  ❌ {msg}", "err")
        self.after(4000, lambda: self._set_mood("idle"))


# ── Tab builder (llamado por FyreWall) ────────────────────────────────────────

def _build_mauricio_tab(parent_frame, app_ref=None):
    tab = MauricioTab(parent_frame, app_ref=app_ref or _app_ref)
    tab.place(relx=0, rely=0, relwidth=1, relheight=1)


# ── Abrir pestaña dentro de FyreWall (NO ventana externa) ─────────────────────

def _open_mauricio_in_fyrewall():
    """
    Abre Mauricio como una pestaña dentro de la app FyreWall,
    usando el sistema de tabs interno de FyreWallApp.
    No abre ninguna ventana Toplevel ni ventana externa.
    """
    try:
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "FyreWallApp") and hasattr(mod, "_PLUGINS"):
                # Buscar la instancia viva de FyreWallApp
                app_instance = getattr(mod, "_APP_INSTANCE", None)
                if app_instance is None:
                    # Intentar encontrar la instancia por widgets Tk
                    for obj_name in dir(mod):
                        obj = getattr(mod, obj_name, None)
                        if isinstance(obj, mod.FyreWallApp):
                            app_instance = obj
                            break
                if app_instance:
                    # Usar _open_tab como cualquier pestaña nativa
                    tab_id = "plugin_mauricio"
                    label  = "💃 Mauricio"
                    if tab_id not in app_instance._tab_frames:
                        frame = tk.Frame(app_instance._content, bg=C["bg"])
                        app_instance._tab_frames[tab_id] = frame
                        _build_mauricio_tab(frame, app_ref=app_instance)
                    app_instance._tab_bar.add_tab(tab_id, label)
                    return True
        return False
    except Exception:
        return False


# ── Inyección en FyreManager ──────────────────────────────────────────────────

def _inject_update_button_into_manager():
    try:
        main_mod = None
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "FyreManagerTab") and hasattr(mod, "_PLUGINS"):
                main_mod = mod
                break
        if main_mod is None:
            return

        FyreManagerTab = main_mod.FyreManagerTab
        orig_populate  = FyreManagerTab._populate_gui_list

        def patched_populate(self_mgr):
            orig_populate(self_mgr)
            _add_update_btns_to_gui(self_mgr, main_mod)

        FyreManagerTab._populate_gui_list = patched_populate

        cmds = main_mod.COMMANDS
        existing = {c for c, _ in cmds}
        if "get-update" not in existing:
            cmds.append(("get-update", "get-update — abre el instalador Mauricio"))

    except Exception:
        pass


def _add_update_btns_to_gui(mgr, main_mod):
    try:
        gui_list = mgr._gui_list
        for row_widget in gui_list.winfo_children():
            fname = None
            for w in row_widget.winfo_children():
                if isinstance(w, tk.Frame):
                    for inner in w.winfo_children():
                        if isinstance(inner, tk.Label) and inner.cget("text").endswith(".py"):
                            fname = inner.cget("text"); break
                elif isinstance(w, tk.Label) and w.cget("text").endswith(".py"):
                    fname = w.cget("text"); break
            if fname:
                already = any(
                    isinstance(w, tk.Button) and "Actualizar" in (w.cget("text") or "")
                    for w in row_widget.winfo_children()
                )
                if not already:
                    del_btn = next(
                        (w for w in row_widget.winfo_children()
                         if isinstance(w, tk.Button) and "Eliminar" in (w.cget("text") or "")),
                        None
                    )
                    tk.Button(
                        row_widget, text="🔄 Actualizar",
                        command=lambda f=fname: _quick_update_file(f, mgr, main_mod),
                        bg=C["blue_btn"], fg="#ffffff",
                        font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                        padx=6, pady=2, activebackground=C["blue_act"],
                    ).pack(side="right", padx=(0, 4), before=del_btn)
    except Exception:
        pass


def _quick_update_file(fname: str, mgr, main_mod):
    mgr._write(f"\n🔄  Mauricio comprueba {fname}...", "info")

    def run():
        local_path  = os.path.join(APP_DIR, fname)
        local_sha   = _local_sha256(local_path)
        remote_data = _raw_get(ADDONS_REPO, ADDONS_BRANCH, fname)
        if remote_data is None:
            mgr.after(0, lambda: mgr._write(_frase("net_err"), "error"))
            return
        remote_sha = _sha256(remote_data)
        if local_sha == remote_sha:
            mgr.after(0, lambda: mgr._write(f"  ✅ {fname} ya está fino, ¡ole!", "ok"))
            return
        info = {
            "repo": ADDONS_REPO, "branch": ADDONS_BRANCH, "file": fname,
            "_data": remote_data, "local_sha": local_sha, "remote_sha": remote_sha,
            "status": "update" if local_sha else "missing",
        }
        ok, msg = apply_update(info)
        mgr.after(0, lambda o=ok, m=msg: mgr._write(f"  {m}", "ok" if o else "error"))
        if ok:
            try:
                _load_plugin_external(os.path.join(APP_DIR, fname))
            except Exception:
                pass

    threading.Thread(target=run, daemon=True).start()


def _load_plugin_external(path: str):
    try:
        for mod_name, mod in sys.modules.items():
            if hasattr(mod, "_load_plugin") and hasattr(mod, "_PLUGINS"):
                mod._load_plugin(path)
                break
    except Exception:
        pass


# ── CLI handler ────────────────────────────────────────────────────────────────

def _cmd_get_update(args):
    # Intenta abrir como pestaña interna de FyreWall
    opened = _open_mauricio_in_fyrewall()
    if opened:
        return "💃  Mauricio abierto en FyreWall.", "ok"
    # Fallback: señal de tab para el sistema de plugins
    return "__PLUGIN_TAB__mauricio.py::get-update", "info"


FYRE_MANIFEST["commands"][0]["handler"] = "_cmd_get_update"

# ── Auto-inyección ─────────────────────────────────────────────────────────────

_inject_update_button_into_manager()

# ── Standalone test ────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("Mauricio — El Actualizador del Barrio (Test Standalone)")
    root.geometry("1100x700")
    root.configure(bg=C["bg"])
    tab = MauricioTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
