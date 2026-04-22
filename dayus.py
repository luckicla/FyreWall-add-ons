"""
DAYUS — Dynamic Analysis & Yield Utility System
================================================
Entorno de pruebas y debugging integrado en FyreWall.
Plugin con pestaña propia, CLI completa, red virtual y bus de eventos.

Coloca este archivo junto a fyrewall.py y usa FyreManager para importarlo.
El comando 'dayus' abrirá la pestaña de debugging.
"""

# ─── MANIFEST ────────────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "DAYUS",
    "version":     "1.0.0",
    "author":      "FyreWall Debug Suite",
    "description": "Entorno de pruebas y debugging virtual para FyreWall.",
    "commands": [
        {
            "name":        "dayus",
            "description": "dayus — abre el entorno de debugging DAYUS",
            "kind":        "tab",
            "tab_builder": "build_dayus_tab",
        },
    ],
}

# ─── IMPORTS ─────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import re
import ipaddress
import json
import os
import sys
from datetime import datetime

# ─── VIRTUAL NETWORK STATE ───────────────────────────────────────────────────
# Estado global del entorno virtual DAYUS. Se comparte entre la pestaña y el
# bus de eventos que intercepta operaciones reales de FyreWall.

class _DayusState:
    """Singleton que mantiene todo el estado virtual de DAYUS."""

    def __init__(self):
        self.connected       = False          # ¿está el debugger conectado?
        self.virtual_ips: dict[str, dict] = {}   # ip → {label, ports, status, traffic}
        self.virtual_ports: dict[int, dict] = {}  # port → {proto, status, blocked, label}
        self.blocked_ips: set[str]  = set()
        self.blocked_ports: set[str] = set()  # "port/proto"
        self.event_log: list[dict]  = []      # log de eventos en tiempo real
        self.traffic_log: list[dict] = []     # tráfico simulado
        self.isolated       = False
        self.snapshots: dict[str, dict] = {}  # nombre → estado guardado
        self.latency_ms     = 12
        self.packet_loss    = 0               # porcentaje 0-100
        self.bandwidth_limit = 0             # 0 = ilimitado, en KB/s
        self._listeners: list = []            # callbacks de la UI
        self._traffic_thread = None
        self._traffic_stop   = threading.Event()

    def add_listener(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn):
        self._listeners = [f for f in self._listeners if f is not fn]

    def emit(self, level: str, msg: str, category: str = "system"):
        """Emite un evento al log y notifica a los listeners de la UI."""
        ev = {
            "ts":       datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level":    level,
            "msg":      msg,
            "category": category,
        }
        self.event_log.append(ev)
        if len(self.event_log) > 2000:
            self.event_log = self.event_log[-2000:]
        for fn in list(self._listeners):
            try:
                fn(ev)
            except Exception:
                pass

    def connect(self):
        self.connected = True
        # Crear red virtual base
        self._seed_virtual_network()
        self.emit("ok",   "╔═══════════════════════════════════════════╗", "connect")
        self.emit("ok",   "║  DAYUS conectado — red virtual activa      ║", "connect")
        self.emit("ok",   "╚═══════════════════════════════════════════╝", "connect")
        self.emit("info", f"  {len(self.virtual_ips)} IPs virtuales generadas.", "connect")
        self.emit("info", f"  {len(self.virtual_ports)} puertos virtuales activos.", "connect")
        self.emit("info", "  Todo el tráfico de FyreWall ahora pasa por DAYUS.", "connect")
        self._start_traffic_sim()

    def disconnect(self):
        self.connected = False
        self._traffic_stop.set()
        self.emit("warn", "DAYUS desconectado — tráfico real restaurado.", "connect")

    def _seed_virtual_network(self):
        """Genera una red virtual realista de muestra."""
        base_ips = [
            ("192.168.1.1",  "Router principal",    [80, 443, 53]),
            ("192.168.1.10", "PC-Escritorio",        [135, 445, 3389]),
            ("192.168.1.20", "Laptop-WiFi",          [80, 443]),
            ("192.168.1.30", "Servidor-Local",       [22, 80, 443, 8080, 3306]),
            ("192.168.1.50", "SmartTV",              [1900, 5353]),
            ("10.0.0.1",     "VPN Gateway",          [1194, 443]),
            ("10.0.0.10",    "Servidor-VPN",         [22, 80]),
            ("8.8.8.8",      "Google DNS",           [53]),
            ("1.1.1.1",      "Cloudflare DNS",       [53]),
            ("172.217.0.0",  "Google Services",      [80, 443]),
        ]
        protos = ["TCP", "UDP"]
        for ip, label, ports in base_ips:
            self.virtual_ips[ip] = {
                "label":   label,
                "ports":   ports,
                "status":  "active",
                "traffic": {"in": 0, "out": 0},
                "ping_ms": random.randint(1, 120),
                "blocked": False,
            }
        # Puertos virtuales del sistema
        port_defs = [
            (80,   "TCP", "HTTP",           False),
            (443,  "TCP", "HTTPS",          False),
            (53,   "UDP", "DNS",            False),
            (22,   "TCP", "SSH",            False),
            (21,   "TCP", "FTP",            False),
            (3389, "TCP", "RDP",            False),
            (5900, "TCP", "VNC",            False),
            (445,  "TCP", "SMB",            False),
            (8080, "TCP", "HTTP-alt",       False),
            (1194, "UDP", "OpenVPN",        False),
            (3306, "TCP", "MySQL",          False),
            (796,  "UDP", "Insight-legacy", False),
            (11796,"UDP", "Insight-main",   False),
            (8888, "TCP", "Insight-WS1",    False),
            (8889, "TCP", "Insight-WS2",    False),
            (8890, "TCP", "Insight-WS3",    False),
            (9000, "TCP", "RebootRestore",  False),
            (1053, "UDP", "Insight-diag",   False),
        ]
        for port, proto, label, blocked in port_defs:
            self.virtual_ports[port] = {
                "proto":   proto,
                "label":   label,
                "blocked": blocked,
                "packets": 0,
                "bytes":   0,
            }

    def _start_traffic_sim(self):
        """Lanza hilo de simulación de tráfico."""
        self._traffic_stop.clear()
        t = threading.Thread(target=self._traffic_loop, daemon=True)
        t.start()
        self._traffic_thread = t

    def _traffic_loop(self):
        """Genera tráfico virtual periódico."""
        while not self._traffic_stop.wait(timeout=random.uniform(1.5, 4.0)):
            if not self.connected or self.isolated:
                continue
            ips = [ip for ip, d in self.virtual_ips.items() if not d["blocked"] and d["status"] == "active"]
            if not ips:
                continue
            src = random.choice(ips)
            dst = random.choice(ips)
            if src == dst:
                continue
            port = random.choice(list(self.virtual_ports.keys()))
            pdata = self.virtual_ports[port]
            if pdata["blocked"]:
                self.emit("warn",
                    f"  🚫 PKT DROP  {src} → {dst}  puerto {port}/{pdata['proto']}  "
                    f"[{pdata['label']}]  (puerto bloqueado)", "traffic")
                continue
            size = random.randint(64, 1460)
            pdata["packets"] += 1
            pdata["bytes"]   += size
            self.virtual_ips[src]["traffic"]["out"] += size
            self.virtual_ips[dst]["traffic"]["in"]  += size
            loss = self.packet_loss > 0 and random.randint(0, 99) < self.packet_loss
            if loss:
                self.emit("warn",
                    f"  📉 PKT LOST  {src} → {dst}  {size}B  puerto {port}  "
                    f"[pérdida simulada {self.packet_loss}%]", "traffic")
            else:
                self.emit("info",
                    f"  📦 PKT OK    {src} → {dst}  {size}B  "
                    f"p={port}/{pdata['proto']}  [{pdata['label']}]  "
                    f"lat={self.latency_ms}ms", "traffic")

# Instancia global
_STATE = _DayusState()


# ─── FYREWALL INTERCEPTION BUS ───────────────────────────────────────────────
# Monkey-patches las funciones críticas de FyreWall para interceptar
# llamadas y reflejarlas en el log de DAYUS cuando está conectado.

def _install_intercepts():
    """Instala interceptores en el módulo principal de FyreWall."""
    try:
        import importlib, sys
        # El módulo principal puede llamarse __main__ o fyrewall según cómo fue lanzado
        fw = None
        for name, mod in sys.modules.items():
            if hasattr(mod, "RULE_PREFIX") and hasattr(mod, "cmd_block_port"):
                fw = mod
                break
        if fw is None:
            return False, "Módulo FyreWall no encontrado en sys.modules"

        # ── block-port ────────────────────────────────────────────────────
        _orig_block_port = fw.cmd_block_port
        def _intercepted_block_port(port, proto="TCP", direction="in"):
            result = _orig_block_port(port, proto, direction)
            if _STATE.connected:
                ok = result[0]
                _STATE.emit(
                    "ok" if ok else "error",
                    f"  🔒 FW→DAYUS  block-port {port}/{proto} ({direction.upper()})  "
                    + ("→ BLOQUEADO en red virtual" if ok else "→ ERROR"),
                    "firewall"
                )
                if ok and port in _STATE.virtual_ports:
                    _STATE.virtual_ports[port]["blocked"] = True
                    _STATE.blocked_ports.add(f"{port}/{proto}")
            return result
        fw.cmd_block_port = _intercepted_block_port

        # ── unblock-port ──────────────────────────────────────────────────
        _orig_unblock_port = fw.cmd_unblock_port
        def _intercepted_unblock_port(port, proto="TCP", direction="in"):
            result = _orig_unblock_port(port, proto, direction)
            if _STATE.connected:
                ok = result[0]
                _STATE.emit(
                    "ok" if ok else "warn",
                    f"  🔓 FW→DAYUS  unblock-port {port}/{proto} ({direction.upper()})  "
                    + ("→ DESBLOQUEADO en red virtual" if ok else "→ no encontrado"),
                    "firewall"
                )
                if ok and port in _STATE.virtual_ports:
                    _STATE.virtual_ports[port]["blocked"] = False
                    _STATE.blocked_ports.discard(f"{port}/{proto}")
            return result
        fw.cmd_unblock_port = _intercepted_unblock_port

        # ── isolate ───────────────────────────────────────────────────────
        _orig_isolate = fw.cmd_isolate
        def _intercepted_isolate(enable):
            result = _orig_isolate(enable)
            if _STATE.connected:
                _STATE.isolated = enable
                _STATE.emit(
                    "warn" if enable else "ok",
                    f"  {'🔴' if enable else '🟢'} FW→DAYUS  {'AISLAMIENTO TOTAL — todo tráfico bloqueado' if enable else 'Aislamiento desactivado — tráfico restaurado'}",
                    "firewall"
                )
            return result
        fw.cmd_isolate = _intercepted_isolate

        # ── flush ─────────────────────────────────────────────────────────
        _orig_flush = fw.cmd_flush_all
        def _intercepted_flush():
            result = _orig_flush()
            if _STATE.connected:
                _STATE.emit("warn",
                    "  💣 FW→DAYUS  flush — TODAS las reglas eliminadas. "
                    "Red virtual reiniciada a estado limpio.",
                    "firewall"
                )
                for p in _STATE.virtual_ports.values():
                    p["blocked"] = False
                _STATE.blocked_ports.clear()
                _STATE.blocked_ips.clear()
                for ip in _STATE.virtual_ips.values():
                    ip["blocked"] = False
            return result
        fw.cmd_flush_all = _intercepted_flush

        # ── block_process ─────────────────────────────────────────────────
        _orig_block_proc = fw.cmd_block_process
        def _intercepted_block_proc(proc_name):
            result = _orig_block_proc(proc_name)
            if _STATE.connected:
                ok = result[0]
                _STATE.emit(
                    "ok" if ok else "warn",
                    f"  🛑 FW→DAYUS  block-process '{proc_name}'  "
                    + ("→ proceso virtual terminado" if ok else "→ no encontrado en red virtual"),
                    "firewall"
                )
            return result
        fw.cmd_block_process = _intercepted_block_proc

        # ── IpManager: intercept ip-block si está cargado ─────────────────
        for modname, mod in sys.modules.items():
            if hasattr(mod, "FYRE_MANIFEST") and mod.FYRE_MANIFEST.get("name") == "IpManager":
                _orig_block_ip = getattr(mod, "_block_ip", None)
                _orig_unblock_ip = getattr(mod, "_unblock_ip", None)
                _orig_send_troll = getattr(mod, "_send_troll_message", None)
                _orig_shutdown   = getattr(mod, "_shutdown_device", None)

                if _orig_block_ip:
                    def _int_block_ip(ip, _orig=_orig_block_ip):
                        result = _orig(ip)
                        if _STATE.connected:
                            _STATE.emit("ok",
                                f"  🔒 IPMgr→DAYUS  ip block {ip}  → IP bloqueada en red virtual",
                                "ipmanager")
                            _STATE.blocked_ips.add(ip)
                            if ip in _STATE.virtual_ips:
                                _STATE.virtual_ips[ip]["blocked"] = True
                        return result
                    mod._block_ip = _int_block_ip

                if _orig_unblock_ip:
                    def _int_unblock_ip(ip, _orig=_orig_unblock_ip):
                        result = _orig(ip)
                        if _STATE.connected:
                            _STATE.emit("ok",
                                f"  🔓 IPMgr→DAYUS  ip unblock {ip}  → IP desbloqueada en red virtual",
                                "ipmanager")
                            _STATE.blocked_ips.discard(ip)
                            if ip in _STATE.virtual_ips:
                                _STATE.virtual_ips[ip]["blocked"] = False
                        return result
                    mod._unblock_ip = _int_unblock_ip

                if _orig_send_troll:
                    def _int_troll(ip, message, _orig=_orig_send_troll):
                        result = _orig(ip, message)
                        if _STATE.connected:
                            _STATE.emit("ok",
                                f"  📢 IPMgr→DAYUS  ip troll {ip}  msg='{message}'  "
                                "→ Petición de mensaje procesada correctamente en red virtual",
                                "ipmanager")
                        return result
                    mod._send_troll_message = _int_troll

                if _orig_shutdown:
                    def _int_shutdown(ip, _orig=_orig_shutdown):
                        result = _orig(ip)
                        if _STATE.connected:
                            ok = result[0]
                            _STATE.emit(
                                "ok" if ok else "warn",
                                f"  💤 IPMgr→DAYUS  ip shutdown {ip}  "
                                "→ Petición de apagado recibida — procesando en red virtual",
                                "ipmanager")
                            if ip in _STATE.virtual_ips:
                                _STATE.virtual_ips[ip]["status"] = "shutting_down"
                                def _mark_off(ip=ip):
                                    time.sleep(2)
                                    if ip in _STATE.virtual_ips:
                                        _STATE.virtual_ips[ip]["status"] = "offline"
                                    _STATE.emit("warn",
                                        f"  💤 DAYUS  {ip} → offline (apagado remoto simulado)",
                                        "ipmanager")
                                threading.Thread(target=_mark_off, daemon=True).start()
                        return result
                    mod._shutdown_device = _int_shutdown
                break

        return True, "OK"
    except Exception as e:
        return False, str(e)


# ─── ASCII ART ───────────────────────────────────────────────────────────────

_DAYUS_ASCII = r"""
  ██████╗  █████╗ ██╗   ██╗██╗   ██╗███████╗
  ██╔══██╗██╔══██╗╚██╗ ██╔╝██║   ██║██╔════╝
  ██║  ██║███████║ ╚████╔╝ ██║   ██║███████╗
  ██║  ██║██╔══██║  ╚██╔╝  ██║   ██║╚════██║
  ██████╔╝██║  ██║   ██║   ╚██████╔╝███████║
  ╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚══════╝
"""

_DAYUS_SUBTITLE = "  Dynamic Analysis & Yield Utility System  ·  v1.0.0"
_DAYUS_RULE     = "  " + "─" * 54

_DAYUS_HELP = """\
╔══════════════════════════════════════════════════════════╗
║             DAYUS — Comandos disponibles                 ║
╚══════════════════════════════════════════════════════════╝

  CONEXIÓN
  ─────────────────────────────────────────────────────────
  connect
      Conecta DAYUS a FyreWall. Todo el tráfico y todas las
      operaciones del firewall quedan reflejadas en tiempo
      real en este entorno de debugging.

  disconnect
      Desconecta DAYUS y restaura el comportamiento normal.

  status
      Estado actual del entorno virtual (IPs, puertos,
      bloqueos, tráfico, latencia, pérdida de paquetes).

  CREACIÓN DE RECURSOS VIRTUALES
  ─────────────────────────────────────────────────────────
  create-ip <ip> [etiqueta]
      Crea una IP virtual en la red de DAYUS.
      Ej: create-ip 192.168.2.100 Mi-Servidor

  create-port <puerto> [tcp|udp] [etiqueta]
      Crea un puerto virtual para debugging.
      Ej: create-port 9999 tcp Test-API

  create-subnet <base> <cantidad>
      Crea un bloque de IPs virtuales de golpe.
      Ej: create-subnet 192.168.5.0 20

  ELIMINACIÓN DE RECURSOS
  ─────────────────────────────────────────────────────────
  delete-ip <ip>
      Elimina una IP virtual de la red DAYUS.

  delete-port <puerto>
      Elimina un puerto virtual.

  delete-all
      Limpia completamente el estado virtual.

  CONTROL DE TRÁFICO
  ─────────────────────────────────────────────────────────
  block-ip <ip>
      Bloquea una IP en la red virtual (simula regla de FW).

  unblock-ip <ip>
      Desbloquea una IP virtual.

  block-port <puerto> [tcp|udp]
      Bloquea un puerto virtual.

  unblock-port <puerto>
      Desbloquea un puerto virtual.

  blockall-ips
      Bloquea todas las IPs virtuales activas.

  isolate [on|off]
      Activa/desactiva el aislamiento total de red virtual.

  SIMULACIÓN Y TESTS
  ─────────────────────────────────────────────────────────
  ping <ip>
      Simula un ping a una IP virtual.

  flood <ip> [paquetes]
      Simula un ataque de flood a una IP virtual.

  inject <src_ip> <dst_ip> <puerto> [size_bytes]
      Inyecta un paquete virtual entre dos IPs.

  latency <ms>
      Establece la latencia simulada de la red (0-5000ms).

  packetloss <porcentaje>
      Establece el porcentaje de pérdida de paquetes (0-100).

  bandwidth <kb>
      Limita el ancho de banda simulado en KB/s (0=ilimitado).

  stress [segundos]
      Test de estrés: genera tráfico intensivo durante N s.

  INSPECCIÓN Y DIAGNÓSTICO
  ─────────────────────────────────────────────────────────
  list-ips
      Lista todas las IPs virtuales con estado y estadísticas.

  list-ports
      Lista todos los puertos virtuales.

  list-blocked
      Muestra IPs y puertos bloqueados actualmente.

  inspect <ip>
      Inspección completa de una IP virtual.

  top
      Muestra el ranking de IPs por volumen de tráfico.

  trace <src_ip> <dst_ip>
      Simula un traceroute entre dos IPs virtuales.

  scan <ip>
      Escanea los puertos abiertos de una IP virtual.

  log [n]
      Muestra los últimos N eventos del log (por defecto 20).

  log-filter <categoria>
      Filtra el log por categoría: firewall, traffic, ipmanager,
      connect, system, test.

  SNAPSHOTS (guardar/restaurar estado)
  ─────────────────────────────────────────────────────────
  snapshot save <nombre>
      Guarda el estado actual del entorno virtual.

  snapshot load <nombre>
      Restaura un estado guardado.

  snapshot list
      Lista los snapshots disponibles.

  snapshot delete <nombre>
      Elimina un snapshot.

  GENERAL
  ─────────────────────────────────────────────────────────
  reset
      Reinicia la red virtual al estado inicial (manteniendo
      la conexión con FyreWall).

  version
      Muestra la versión y créditos de DAYUS.

  help
      Muestra esta ayuda.

  clear       Limpia la consola.
──────────────────────────────────────────────────────────\
"""


# ─── COMMAND HANDLERS ────────────────────────────────────────────────────────

def _require_connected(write):
    if not _STATE.connected:
        write("  ❌  DAYUS no está conectado. Usa 'connect' primero.", "error")
        return False
    return True


def _cmd_connect(write):
    if _STATE.connected:
        write("  ⚠️  DAYUS ya está conectado.", "warn")
        return
    write("  ⏳  Conectando DAYUS a FyreWall...", "info")
    time.sleep(0.3)
    ok, msg = _install_intercepts()
    if not ok:
        write(f"  ⚠️  Advertencia al instalar interceptores: {msg}", "warn")
        write("  ℹ️  DAYUS funcionará en modo standalone (sin interceptar FyreWall).", "muted")
    _STATE.connect()


def _cmd_disconnect(write):
    if not _STATE.connected:
        write("  ℹ️  DAYUS no estaba conectado.", "info")
        return
    _STATE.disconnect()
    write("  ✅  DAYUS desconectado correctamente.", "ok")


def _cmd_status(write):
    s = _STATE
    conn_str = "🟢 CONECTADO" if s.connected else "🔴 DESCONECTADO"
    isol_str = "🔴 SÍ" if s.isolated else "🟢 NO"
    blocked_ips   = len(s.blocked_ips)
    blocked_ports = len(s.blocked_ports)
    total_ips     = len(s.virtual_ips)
    total_ports   = len(s.virtual_ports)
    total_events  = len(s.event_log)

    in_bytes  = sum(d["traffic"]["in"]  for d in s.virtual_ips.values())
    out_bytes = sum(d["traffic"]["out"] for d in s.virtual_ips.values())

    write("╔══════════════════════════════════════════════════════╗", "header")
    write("║            DAYUS — Estado del entorno virtual         ║", "header")
    write("╚══════════════════════════════════════════════════════╝", "header")
    write(f"  Estado         : {conn_str}", "info")
    write(f"  Aislamiento    : {isol_str}", "info")
    write(f"  IPs virtuales  : {total_ips} total  /  {blocked_ips} bloqueada(s)", "info")
    write(f"  Puertos virt.  : {total_ports} total  /  {blocked_ports} bloqueado(s)", "info")
    write(f"  Tráfico total  : ↓ {_human_bytes(in_bytes)}  ↑ {_human_bytes(out_bytes)}", "info")
    write(f"  Latencia sim.  : {s.latency_ms} ms", "info")
    write(f"  Pérd. paquetes : {s.packet_loss}%", "info")
    write(f"  Ancho de banda : {'ilimitado' if s.bandwidth_limit == 0 else str(s.bandwidth_limit) + ' KB/s'}", "info")
    write(f"  Eventos en log : {total_events}", "info")
    write(f"  Snapshots      : {len(s.snapshots)}", "info")


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _cmd_create_ip(args, write):
    if not args:
        write("  Uso: dys create-ip <ip> [etiqueta]", "warn")
        return
    ip = args[0]
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        write(f"  ❌  '{ip}' no es una dirección IP válida.", "error")
        return
    label = " ".join(args[1:]) if len(args) > 1 else f"Virtual-{ip}"
    if ip in _STATE.virtual_ips:
        write(f"  ⚠️  IP {ip} ya existe en la red virtual.", "warn")
        return
    _STATE.virtual_ips[ip] = {
        "label":   label,
        "ports":   [],
        "status":  "active",
        "traffic": {"in": 0, "out": 0},
        "ping_ms": random.randint(1, 200),
        "blocked": False,
    }
    _STATE.emit("ok", f"  ✅ create-ip  {ip}  [{label}]", "system")
    write(f"  ✅  IP virtual creada: {ip}  [{label}]", "ok")


def _cmd_create_port(args, write):
    if not args:
        write("  Uso: dys create-port <puerto> [tcp|udp] [etiqueta]", "warn")
        return
    try:
        port = int(args[0])
        assert 1 <= port <= 65535
    except (ValueError, AssertionError):
        write(f"  ❌  Puerto inválido: '{args[0]}'. Debe ser 1-65535.", "error")
        return
    proto = args[1].upper() if len(args) > 1 and args[1].upper() in ("TCP", "UDP") else "TCP"
    label = " ".join(args[2:]) if len(args) > 2 else f"Virtual-{port}"
    if port in _STATE.virtual_ports:
        write(f"  ⚠️  Puerto {port} ya existe.", "warn")
        return
    _STATE.virtual_ports[port] = {
        "proto":   proto,
        "label":   label,
        "blocked": False,
        "packets": 0,
        "bytes":   0,
    }
    _STATE.emit("ok", f"  ✅ create-port  {port}/{proto}  [{label}]", "system")
    write(f"  ✅  Puerto virtual creado: {port}/{proto}  [{label}]", "ok")


def _cmd_create_subnet(args, write):
    if len(args) < 2:
        write("  Uso: dys create-subnet <base_ip> <cantidad>", "warn")
        return
    base = args[0]
    try:
        count = int(args[1])
        assert 1 <= count <= 254
        net = ipaddress.ip_network(base + "/24", strict=False)
    except Exception:
        write(f"  ❌  Parámetros inválidos.", "error")
        return
    created = 0
    for host in list(net.hosts())[:count]:
        ip = str(host)
        if ip not in _STATE.virtual_ips:
            _STATE.virtual_ips[ip] = {
                "label":   f"Subnet-{ip}",
                "ports":   [random.choice([80, 443, 22, 8080])],
                "status":  "active",
                "traffic": {"in": 0, "out": 0},
                "ping_ms": random.randint(1, 200),
                "blocked": False,
            }
            created += 1
    _STATE.emit("ok", f"  ✅ create-subnet  {base}/24  ×{created} IPs", "system")
    write(f"  ✅  Subred creada: {created} IPs bajo {base}/24", "ok")


def _cmd_delete_ip(args, write):
    if not args:
        write("  Uso: dys delete-ip <ip>", "warn")
        return
    ip = args[0]
    if ip not in _STATE.virtual_ips:
        write(f"  ⚠️  IP {ip} no existe en la red virtual.", "warn")
        return
    del _STATE.virtual_ips[ip]
    _STATE.blocked_ips.discard(ip)
    _STATE.emit("warn", f"  🗑️  delete-ip  {ip}", "system")
    write(f"  ✅  IP virtual eliminada: {ip}", "ok")


def _cmd_delete_port(args, write):
    if not args:
        write("  Uso: dys delete-port <puerto>", "warn")
        return
    try:
        port = int(args[0])
    except ValueError:
        write(f"  ❌  Puerto inválido: {args[0]}", "error")
        return
    if port not in _STATE.virtual_ports:
        write(f"  ⚠️  Puerto {port} no existe.", "warn")
        return
    del _STATE.virtual_ports[port]
    _STATE.emit("warn", f"  🗑️  delete-port  {port}", "system")
    write(f"  ✅  Puerto virtual eliminado: {port}", "ok")


def _cmd_delete_all(write):
    _STATE.virtual_ips.clear()
    _STATE.virtual_ports.clear()
    _STATE.blocked_ips.clear()
    _STATE.blocked_ports.clear()
    _STATE.isolated = False
    _STATE.emit("warn", "  💣  delete-all — entorno virtual limpiado completamente", "system")
    write("  ✅  Entorno virtual limpiado. Usa 'reset' para regenerar la red base.", "ok")


def _cmd_block_ip(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys block-ip <ip>", "warn")
        return
    ip = args[0]
    if ip not in _STATE.virtual_ips:
        write(f"  ⚠️  IP {ip} no existe. Créala con 'create-ip {ip}'", "warn")
        return
    _STATE.virtual_ips[ip]["blocked"] = True
    _STATE.blocked_ips.add(ip)
    _STATE.emit("ok", f"  🔒 block-ip  {ip}  [{_STATE.virtual_ips[ip]['label']}]", "firewall")
    write(f"  🔒  IP virtual bloqueada: {ip}", "ok")


def _cmd_unblock_ip(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys unblock-ip <ip>", "warn")
        return
    ip = args[0]
    if ip not in _STATE.virtual_ips:
        write(f"  ⚠️  IP {ip} no existe.", "warn")
        return
    _STATE.virtual_ips[ip]["blocked"] = False
    _STATE.blocked_ips.discard(ip)
    _STATE.emit("ok", f"  🔓 unblock-ip  {ip}", "firewall")
    write(f"  🔓  IP virtual desbloqueada: {ip}", "ok")


def _cmd_block_port(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys block-port <puerto> [tcp|udp]", "warn")
        return
    try:
        port = int(args[0])
    except ValueError:
        write(f"  ❌  Puerto inválido.", "error"); return
    proto = args[1].upper() if len(args) > 1 and args[1].upper() in ("TCP","UDP") else "TCP"
    if port not in _STATE.virtual_ports:
        _STATE.virtual_ports[port] = {"proto": proto, "label": f"Custom-{port}", "blocked": False, "packets": 0, "bytes": 0}
    _STATE.virtual_ports[port]["blocked"] = True
    _STATE.blocked_ports.add(f"{port}/{proto}")
    _STATE.emit("ok", f"  🔒 block-port  {port}/{proto}", "firewall")
    write(f"  🔒  Puerto virtual bloqueado: {port}/{proto}", "ok")


def _cmd_unblock_port(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys unblock-port <puerto>", "warn")
        return
    try:
        port = int(args[0])
    except ValueError:
        write(f"  ❌  Puerto inválido.", "error"); return
    if port in _STATE.virtual_ports:
        _STATE.virtual_ports[port]["blocked"] = False
    _STATE.blocked_ports = {p for p in _STATE.blocked_ports if not p.startswith(f"{port}/")}
    _STATE.emit("ok", f"  🔓 unblock-port  {port}", "firewall")
    write(f"  🔓  Puerto virtual desbloqueado: {port}", "ok")


def _cmd_blockall_ips(write):
    if not _require_connected(write): return
    count = 0
    for ip, data in _STATE.virtual_ips.items():
        if not data["blocked"]:
            data["blocked"] = True
            _STATE.blocked_ips.add(ip)
            count += 1
    _STATE.emit("warn", f"  🔒 blockall-ips — {count} IPs bloqueadas", "firewall")
    write(f"  🔒  {count} IP(s) virtuales bloqueadas.", "ok")


def _cmd_isolate(args, write):
    if not _require_connected(write): return
    mode = args[0].lower() if args else "on"
    enable = mode not in ("off", "0", "false", "no")
    _STATE.isolated = enable
    _STATE.emit("warn" if enable else "ok",
        f"  {'🔴 AISLAMIENTO ACTIVADO' if enable else '🟢 Aislamiento desactivado'}",
        "firewall")
    write(f"  {'🔴 Red virtual AISLADA — todo tráfico bloqueado' if enable else '🟢 Aislamiento desactivado — tráfico restaurado'}", "ok" if not enable else "warn")


def _cmd_ping(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys ping <ip>", "warn"); return
    ip = args[0]
    if ip not in _STATE.virtual_ips:
        write(f"  ❌  IP {ip} no existe en la red virtual.", "error"); return
    data = _STATE.virtual_ips[ip]
    if data["blocked"] or _STATE.isolated:
        write(f"  📡  PING {ip} → TIMEOUT (bloqueada o red aislada)", "warn")
        _STATE.emit("warn", f"  📡 ping {ip}  → TIMEOUT", "test")
        return
    for i in range(4):
        lat = data["ping_ms"] + random.randint(-3, 8)
        write(f"  📡  64 bytes de {ip} ({data['label']}): icmp_seq={i+1} ttl=64 time={lat} ms", "ok")
        time.sleep(0.1)
    write(f"\n  --- {ip} ping statistics ---", "muted")
    write(f"  4 packets transmitted, 4 received, 0% packet loss, time={data['ping_ms']}ms avg", "muted")
    _STATE.emit("info", f"  📡 ping {ip}  → {data['ping_ms']}ms", "test")


def _cmd_flood(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys flood <ip> [paquetes]", "warn"); return
    ip = args[0]
    try:
        count = int(args[1]) if len(args) > 1 else 50
        count = min(count, 500)
    except ValueError:
        count = 50
    if ip not in _STATE.virtual_ips:
        write(f"  ❌  IP {ip} no existe.", "error"); return

    write(f"  ⚡  Iniciando flood contra {ip}: {count} paquetes...", "warn")
    _STATE.emit("warn", f"  ⚡ flood {ip}  ×{count} pkts", "test")

    def _do_flood():
        ports = list(_STATE.virtual_ports.keys()) or [80]
        dropped = 0
        for i in range(count):
            port = random.choice(ports)
            size = random.randint(1, 65535)
            if _STATE.virtual_ips[ip].get("blocked") or _STATE.virtual_ports.get(port, {}).get("blocked"):
                dropped += 1
                continue
            _STATE.virtual_ips[ip]["traffic"]["in"] += size
            time.sleep(0.01)
        _STATE.emit("warn",
            f"  ⚡ flood {ip} completado: {count - dropped} entregados, {dropped} bloqueados",
            "test")
    threading.Thread(target=_do_flood, daemon=True).start()
    write(f"  ⚡  Flood lanzado en segundo plano. Revisa el log de eventos.", "warn")


def _cmd_inject(args, write):
    if not _require_connected(write): return
    if len(args) < 3:
        write("  Uso: dys inject <src_ip> <dst_ip> <puerto> [size_bytes]", "warn"); return
    src, dst = args[0], args[1]
    try:
        port = int(args[2])
        size = int(args[3]) if len(args) > 3 else random.randint(64, 1460)
    except ValueError:
        write("  ❌  Puerto/tamaño inválido.", "error"); return

    pdata = _STATE.virtual_ports.get(port, {"proto":"TCP","label":"?","blocked":False})
    blocked_src = _STATE.virtual_ips.get(src, {}).get("blocked", False)
    blocked_dst = _STATE.virtual_ips.get(dst, {}).get("blocked", False)
    blocked_prt = pdata.get("blocked", False)
    isolated    = _STATE.isolated

    if blocked_src or blocked_dst or blocked_prt or isolated:
        reason = ("src bloqueada" if blocked_src else
                  "dst bloqueada" if blocked_dst else
                  "puerto bloqueado" if blocked_prt else "aislamiento")
        write(f"  🚫  PKT DROP  {src} → {dst}  p={port}  {size}B  [{reason}]", "warn")
        _STATE.emit("warn", f"  🚫 inject DROP  {src}→{dst}  p={port}  [{reason}]", "test")
    else:
        if src in _STATE.virtual_ips:
            _STATE.virtual_ips[src]["traffic"]["out"] += size
        if dst in _STATE.virtual_ips:
            _STATE.virtual_ips[dst]["traffic"]["in"] += size
        lat = _STATE.latency_ms + random.randint(-2, 5)
        write(f"  📦  PKT OK  {src} → {dst}  p={port}/{pdata.get('proto','TCP')}  {size}B  lat={lat}ms", "ok")
        _STATE.emit("info", f"  📦 inject OK  {src}→{dst}  p={port}  {size}B", "test")


def _cmd_latency(args, write):
    if not args:
        write(f"  Latencia actual: {_STATE.latency_ms} ms. Uso: dys latency <ms>", "info"); return
    try:
        ms = int(args[0])
        assert 0 <= ms <= 5000
    except (ValueError, AssertionError):
        write("  ❌  Latencia inválida. Rango: 0-5000 ms", "error"); return
    _STATE.latency_ms = ms
    _STATE.emit("info", f"  ⚙️  latency={ms}ms", "system")
    write(f"  ✅  Latencia simulada establecida: {ms} ms", "ok")


def _cmd_packetloss(args, write):
    if not args:
        write(f"  Pérdida actual: {_STATE.packet_loss}%. Uso: dys packetloss <0-100>", "info"); return
    try:
        pct = int(args[0])
        assert 0 <= pct <= 100
    except (ValueError, AssertionError):
        write("  ❌  Porcentaje inválido. Rango: 0-100", "error"); return
    _STATE.packet_loss = pct
    _STATE.emit("info", f"  ⚙️  packet_loss={pct}%", "system")
    write(f"  ✅  Pérdida de paquetes simulada: {pct}%", "ok")


def _cmd_bandwidth(args, write):
    if not args:
        val = "ilimitado" if _STATE.bandwidth_limit == 0 else f"{_STATE.bandwidth_limit} KB/s"
        write(f"  Ancho de banda actual: {val}. Uso: dys bandwidth <kb> (0=ilimitado)", "info"); return
    try:
        kb = int(args[0])
        assert kb >= 0
    except (ValueError, AssertionError):
        write("  ❌  Valor inválido.", "error"); return
    _STATE.bandwidth_limit = kb
    label = "ilimitado" if kb == 0 else f"{kb} KB/s"
    _STATE.emit("info", f"  ⚙️  bandwidth={label}", "system")
    write(f"  ✅  Ancho de banda simulado: {label}", "ok")


def _cmd_stress(args, write):
    if not _require_connected(write): return
    try:
        secs = int(args[0]) if args else 5
        secs = min(secs, 60)
    except ValueError:
        secs = 5
    write(f"  ⚡  Test de estrés durante {secs}s — generando tráfico intensivo...", "warn")
    _STATE.emit("warn", f"  ⚡ stress test  {secs}s", "test")

    def _stress():
        ips   = list(_STATE.virtual_ips.keys())
        ports = list(_STATE.virtual_ports.keys()) or [80]
        end   = time.time() + secs
        pkts  = 0
        while time.time() < end and _STATE.connected:
            if ips and ports:
                src  = random.choice(ips)
                dst  = random.choice(ips)
                port = random.choice(ports)
                size = random.randint(64, 1460)
                if not _STATE.virtual_ips.get(src, {}).get("blocked"):
                    _STATE.virtual_ips[src]["traffic"]["out"] += size
                if not _STATE.virtual_ips.get(dst, {}).get("blocked"):
                    _STATE.virtual_ips[dst]["traffic"]["in"] += size
                pkts += 1
            time.sleep(0.05)
        _STATE.emit("ok", f"  ⚡ stress completado: {pkts} paquetes virtuales en {secs}s", "test")
    threading.Thread(target=_stress, daemon=True).start()
    write(f"  ⚡  Estrés corriendo. Revisa el log.", "warn")


def _cmd_list_ips(write):
    if not _STATE.virtual_ips:
        write("  ℹ️  No hay IPs virtuales.", "muted"); return
    write("╔══════════════════════════════════════════════════════════╗", "header")
    write("║              DAYUS — IPs virtuales                       ║", "header")
    write("╚══════════════════════════════════════════════════════════╝", "header")
    for ip, d in sorted(_STATE.virtual_ips.items()):
        status  = "🔒 BLOQUEADA" if d["blocked"] else ("⚡ OFFLINE" if d["status"] != "active" else "🟢 activa")
        traffic = f"↓{_human_bytes(d['traffic']['in'])} ↑{_human_bytes(d['traffic']['out'])}"
        write(f"  {ip:<18}  {status:<16}  ping={d['ping_ms']}ms  {traffic}  [{d['label']}]", "info")
    write(f"\n  Total: {len(_STATE.virtual_ips)} IP(s)", "muted")


def _cmd_list_ports(write):
    if not _STATE.virtual_ports:
        write("  ℹ️  No hay puertos virtuales.", "muted"); return
    write("╔══════════════════════════════════════════════════════════╗", "header")
    write("║              DAYUS — Puertos virtuales                   ║", "header")
    write("╚══════════════════════════════════════════════════════════╝", "header")
    for port, d in sorted(_STATE.virtual_ports.items()):
        status = "🔒 BLOQUEADO" if d["blocked"] else "🟢 abierto"
        write(f"  {port:<6} {d['proto']:<4}  {status:<14}  pkts={d['packets']:<8}  bytes={_human_bytes(d['bytes'])}  [{d['label']}]", "info")
    write(f"\n  Total: {len(_STATE.virtual_ports)} puerto(s)", "muted")


def _cmd_list_blocked(write):
    write("  🔒  IPs bloqueadas:", "warn")
    if _STATE.blocked_ips:
        for ip in sorted(_STATE.blocked_ips):
            label = _STATE.virtual_ips.get(ip, {}).get("label", "?")
            write(f"      {ip}  [{label}]", "warn")
    else:
        write("      (ninguna)", "muted")
    write("  🔒  Puertos bloqueados:", "warn")
    if _STATE.blocked_ports:
        for p in sorted(_STATE.blocked_ports):
            write(f"      {p}", "warn")
    else:
        write("      (ninguno)", "muted")


def _cmd_inspect(args, write):
    if not args:
        write("  Uso: dys inspect <ip>", "warn"); return
    ip = args[0]
    d = _STATE.virtual_ips.get(ip)
    if not d:
        write(f"  ❌  IP {ip} no existe en la red virtual.", "error"); return
    write(f"╔══════════════════════════════════════════════════════════╗", "header")
    write(f"║  DAYUS inspect — {ip:<40}║", "header")
    write(f"╚══════════════════════════════════════════════════════════╝", "header")
    write(f"  Etiqueta   : {d['label']}", "info")
    write(f"  Estado     : {'🔒 BLOQUEADA' if d['blocked'] else '🟢 activa'}", "info")
    write(f"  Status     : {d['status']}", "info")
    write(f"  Latencia   : {d['ping_ms']} ms", "info")
    write(f"  Tráfico IN : {_human_bytes(d['traffic']['in'])}", "info")
    write(f"  Tráfico OUT: {_human_bytes(d['traffic']['out'])}", "info")
    write(f"  Puertos    : {', '.join(str(p) for p in d['ports']) if d['ports'] else '(ninguno)'}", "info")
    write(f"  Bloqueada  : {'Sí' if d['blocked'] else 'No'}", "info")


def _cmd_top(write):
    if not _STATE.virtual_ips:
        write("  ℹ️  Sin IPs virtuales.", "muted"); return
    sorted_ips = sorted(
        _STATE.virtual_ips.items(),
        key=lambda x: x[1]["traffic"]["in"] + x[1]["traffic"]["out"],
        reverse=True
    )[:10]
    write("  📊  Top IPs por tráfico total:", "header")
    write("  ─────────────────────────────────────────────────────", "muted")
    for i, (ip, d) in enumerate(sorted_ips, 1):
        total = d["traffic"]["in"] + d["traffic"]["out"]
        bar_len = int(total / max(
            sum(v["traffic"]["in"] + v["traffic"]["out"] for v in _STATE.virtual_ips.values()) or 1,
            1) * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        write(f"  {i:>2}. {ip:<18} [{bar}]  {_human_bytes(total)}", "info")


def _cmd_trace(args, write):
    if not _require_connected(write): return
    if len(args) < 2:
        write("  Uso: dys trace <src_ip> <dst_ip>", "warn"); return
    src, dst = args[0], args[1]
    write(f"  🛤️  traceroute  {src} → {dst}", "info")
    hops = random.randint(3, 10)
    for i in range(1, hops + 1):
        hop_ip = f"10.{random.randint(0,5)}.{random.randint(0,255)}.{random.randint(1,254)}"
        lat1   = random.randint(1, 40)
        lat2   = lat1 + random.randint(0, 5)
        lat3   = lat2 + random.randint(0, 5)
        if i == hops:
            hop_ip = dst
        write(f"  {i:>3}  {hop_ip:<18}  {lat1} ms  {lat2} ms  {lat3} ms", "info")
        time.sleep(0.05)
    _STATE.emit("info", f"  🛤️  trace {src}→{dst}  {hops} hops", "test")


def _cmd_scan(args, write):
    if not _require_connected(write): return
    if not args:
        write("  Uso: dys scan <ip>", "warn"); return
    ip = args[0]
    d  = _STATE.virtual_ips.get(ip)
    if not d:
        write(f"  ❌  IP {ip} no existe en la red virtual.", "error"); return
    if d["blocked"] or _STATE.isolated:
        write(f"  ❌  {ip} no responde (bloqueada o aislamiento activo).", "warn"); return
    write(f"  🔍  Escaneando puertos de {ip} [{d['label']}]...", "info")
    open_ports = d.get("ports", []) + [p for p, pd in _STATE.virtual_ports.items() if not pd["blocked"] and random.random() < 0.3]
    open_ports = sorted(set(open_ports))[:15]
    for port in open_ports:
        pd     = _STATE.virtual_ports.get(port, {"proto":"TCP","label":"unknown"})
        status = "filtrado" if pd.get("blocked") else "abierto"
        write(f"  {port:<6}/{'tcp':<4}  {status:<10}  {pd['label']}", "ok" if status == "abierto" else "warn")
    write(f"\n  {len(open_ports)} puerto(s) encontrado(s) en {ip}", "muted")
    _STATE.emit("info", f"  🔍 scan {ip}  {len(open_ports)} puertos abiertos", "test")


def _cmd_log(args, write):
    try:
        n = int(args[0]) if args else 20
        n = min(n, 200)
    except ValueError:
        n = 20
    events = _STATE.event_log[-n:]
    if not events:
        write("  ℹ️  Log vacío.", "muted"); return
    write(f"  📋  Últimos {len(events)} eventos:", "header")
    write("  ─────────────────────────────────────────────────────", "muted")
    for ev in events:
        write(f"  [{ev['ts']}] [{ev['category']:<10}] {ev['msg']}", ev['level'])


def _cmd_log_filter(args, write):
    if not args:
        write("  Uso: dys log-filter <categoria>", "warn")
        write("  Categorías: firewall, traffic, ipmanager, connect, system, test", "muted")
        return
    cat    = args[0].lower()
    events = [ev for ev in _STATE.event_log if ev["category"] == cat]
    if not events:
        write(f"  ℹ️  Sin eventos para categoría '{cat}'.", "muted"); return
    write(f"  📋  {len(events)} evento(s) con categoría '{cat}':", "header")
    for ev in events[-50:]:
        write(f"  [{ev['ts']}]  {ev['msg']}", ev['level'])


def _cmd_snapshot(args, write):
    if not args:
        write("  Uso: dys snapshot [save|load|list|delete] [nombre]", "warn"); return
    sub = args[0].lower()
    name = args[1] if len(args) > 1 else None

    if sub == "list":
        if not _STATE.snapshots:
            write("  ℹ️  Sin snapshots guardados.", "muted"); return
        write("  💾  Snapshots disponibles:", "header")
        for n, snap in _STATE.snapshots.items():
            ts  = snap.get("ts", "?")
            nip = snap.get("n_ips", 0)
            npt = snap.get("n_ports", 0)
            write(f"    • {n:<20}  {ts}  IPs={nip}  Puertos={npt}", "info")
        return

    if not name:
        write(f"  Uso: dys snapshot {sub} <nombre>", "warn"); return

    if sub == "save":
        import copy
        _STATE.snapshots[name] = {
            "ts":         datetime.now().strftime("%H:%M:%S"),
            "n_ips":      len(_STATE.virtual_ips),
            "n_ports":    len(_STATE.virtual_ports),
            "virtual_ips":   copy.deepcopy(_STATE.virtual_ips),
            "virtual_ports": copy.deepcopy(_STATE.virtual_ports),
            "blocked_ips":   list(_STATE.blocked_ips),
            "blocked_ports": list(_STATE.blocked_ports),
            "isolated":      _STATE.isolated,
            "latency_ms":    _STATE.latency_ms,
            "packet_loss":   _STATE.packet_loss,
        }
        _STATE.emit("ok", f"  💾 snapshot save '{name}'", "system")
        write(f"  💾  Snapshot '{name}' guardado correctamente.", "ok")

    elif sub == "load":
        snap = _STATE.snapshots.get(name)
        if not snap:
            write(f"  ❌  Snapshot '{name}' no encontrado.", "error"); return
        import copy
        _STATE.virtual_ips   = copy.deepcopy(snap["virtual_ips"])
        _STATE.virtual_ports = copy.deepcopy(snap["virtual_ports"])
        _STATE.blocked_ips   = set(snap["blocked_ips"])
        _STATE.blocked_ports = set(snap["blocked_ports"])
        _STATE.isolated      = snap["isolated"]
        _STATE.latency_ms    = snap["latency_ms"]
        _STATE.packet_loss   = snap["packet_loss"]
        _STATE.emit("ok", f"  💾 snapshot load '{name}'", "system")
        write(f"  💾  Snapshot '{name}' restaurado correctamente.", "ok")

    elif sub == "delete":
        if name in _STATE.snapshots:
            del _STATE.snapshots[name]
            write(f"  ✅  Snapshot '{name}' eliminado.", "ok")
        else:
            write(f"  ⚠️  Snapshot '{name}' no existe.", "warn")
    else:
        write(f"  ❌  Subcomando desconocido: '{sub}'", "error")


def _cmd_reset(write):
    _STATE.virtual_ips.clear()
    _STATE.virtual_ports.clear()
    _STATE.blocked_ips.clear()
    _STATE.blocked_ports.clear()
    _STATE.isolated = False
    _STATE._seed_virtual_network()
    _STATE.emit("ok", "  ♻️  reset — red virtual regenerada", "system")
    write(f"  ♻️  Red virtual reiniciada: {len(_STATE.virtual_ips)} IPs, {len(_STATE.virtual_ports)} puertos.", "ok")


def _cmd_version(write):
    write("╔══════════════════════════════════════════════════════╗", "header")
    write("║   DAYUS — Dynamic Analysis & Yield Utility System    ║", "header")
    write("║   Versión 1.0.0  ·  FyreWall Debug Suite             ║", "header")
    write("╚══════════════════════════════════════════════════════╝", "header")
    write("  Módulo de debugging y entorno virtual para FyreWall.", "muted")
    write("  Intercepta operaciones del firewall en tiempo real.", "muted")
    write("  Compatible con IpManager y todos los add-ons FYRE.", "muted")


# ─── TAB BUILDER (tkinter) ───────────────────────────────────────────────────

_COLORS = {
    "bg":             "#1a1d23",
    "surface":        "#22252e",
    "surface2":       "#2a2d38",
    "border":         "#33374a",
    "accent":         "#4da6ff",
    "accent_hover":   "#6ab8ff",
    "text":           "#e8eaf0",
    "text_muted":     "#7a8099",
    "success":        "#4caf80",
    "warning":        "#f5a623",
    "danger":         "#e05c5c",
    "btn":            "#2a2d38",
    "btn_hover":      "#343848",
    "console_bg":     "#0e1117",
    "console_text":   "#c9d1d9",
    "console_prompt": "#a855f7",
    "console_ok":     "#4caf80",
    "console_err":    "#e05c5c",
    "console_warn":   "#f5a623",
    "console_info":   "#7a9fff",
    "console_muted":  "#5a6380",
    "console_header": "#4da6ff",
    "red_btn":        "#8b2020",
    "green_btn":      "#1e6b35",
}

_TAG_COLORS = {
    "prompt": "#a855f7",
    "ok":     "#4caf80",
    "error":  "#e05c5c",
    "warn":   "#f5a623",
    "info":   "#7a9fff",
    "muted":  "#5a6380",
    "header": "#4da6ff",
    "ascii":  "#6a8fff",
    "traffic":"#888eb0",
    "fw":     "#ff8c69",
    "ipmgr":  "#98d1e8",
}

_DYS_COMMANDS = [
    ("connect",          "connect — activa la red virtual e intercepta FyreWall"),
    ("disconnect",       "disconnect — desconecta DAYUS y restaura el tráfico real"),
    ("status",           "status — estado actual del entorno virtual"),
    ("version",          "version — muestra la versión de DAYUS"),
    ("reset",            "reset — reinicia el estado virtual al estado base"),
    ("create-ip ",       "create-ip <ip> [etiqueta] — crea una IP virtual"),
    ("create-port ",     "create-port <puerto> [tcp|udp] [etiqueta] — crea un puerto virtual"),
    ("create-subnet ",   "create-subnet <base_ip> <cantidad> — crea un bloque de IPs"),
    ("delete-ip ",       "delete-ip <ip> — elimina una IP virtual"),
    ("delete-port ",     "delete-port <puerto> — elimina un puerto virtual"),
    ("delete-all",       "delete-all — limpia completamente el entorno virtual"),
    ("block-ip ",        "block-ip <ip> — bloquea una IP en la red virtual"),
    ("unblock-ip ",      "unblock-ip <ip> — desbloquea una IP virtual"),
    ("block-port ",      "block-port <puerto> [tcp|udp] — bloquea un puerto virtual"),
    ("unblock-port ",    "unblock-port <puerto> — desbloquea un puerto virtual"),
    ("blockall-ips",     "blockall-ips — bloquea todas las IPs virtuales"),
    ("isolate",          "isolate [on|off] — activa/desactiva aislamiento total"),
    ("ping ",            "ping <ip> — simula un ping a una IP virtual"),
    ("flood ",           "flood <ip> [paquetes] — simula flood de paquetes"),
    ("inject ",          "inject <ip> <puerto> [tamaño] — inyecta paquete virtual"),
    ("latency ",         "latency <ms> — establece la latencia simulada"),
    ("packetloss ",      "packetloss <0-100> — establece % de pérdida de paquetes"),
    ("bandwidth ",       "bandwidth <KB/s|0> — limita el ancho de banda (0=sin límite)"),
    ("stress ",          "stress <segundos> — test de estrés de la red virtual"),
    ("list-ips",         "list-ips — lista todas las IPs virtuales"),
    ("list-ports",       "list-ports — lista todos los puertos virtuales"),
    ("list-blocked",     "list-blocked — lista IPs y puertos bloqueados"),
    ("inspect ",         "inspect <ip|puerto> — inspecciona un recurso virtual"),
    ("top",              "top — top de IPs por tráfico"),
    ("trace ",           "trace <ip> — traza la ruta virtual hasta una IP"),
    ("scan",             "scan — re-escanea el estado de la red virtual"),
    ("log",              "log — muestra el log de eventos recientes"),
    ("log-filter ",      "log-filter <categoría> — filtra el log por categoría"),
    ("snapshot save ",   "snapshot save <nombre> — guarda el estado actual"),
    ("snapshot load ",   "snapshot load <nombre> — restaura un snapshot"),
    ("snapshot list",    "snapshot list — lista los snapshots guardados"),
    ("snapshot delete ", "snapshot delete <nombre> — elimina un snapshot"),
    ("help",             "help — muestra todos los comandos disponibles"),
    ("clear",            "clear — limpia la consola"),
]


class DayusTab(tk.Frame):
    """Pestaña principal de DAYUS — CLI completa con live event log."""

    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=_COLORS["bg"])
        self._app   = app_ref
        self._history: list[str] = []
        self._hist_idx = -1
        self._live_enabled = tk.BooleanVar(value=True)
        self._filter_var   = tk.StringVar(value="all")
        self._autocomplete_popup: "tk.Toplevel | None" = None
        self._build()
        self._print_banner()
        # Register listener for live events
        _STATE.add_listener(self._on_live_event)

    def destroy(self):
        _STATE.remove_listener(self._on_live_event)
        super().destroy()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        # ── Header bar ────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_COLORS["surface"], pady=6, padx=14)
        hdr.pack(fill="x")

        tk.Label(hdr, text="⚡ DAYUS",
                 font=("Consolas", 13, "bold"),
                 bg=_COLORS["surface"], fg="#a855f7").pack(side="left")
        tk.Label(hdr, text="  Debug Environment",
                 font=("Segoe UI", 9),
                 bg=_COLORS["surface"], fg=_COLORS["text_muted"]).pack(side="left")

        self._conn_lbl = tk.Label(hdr, text="⚫ OFFLINE",
                 font=("Segoe UI", 9, "bold"),
                 bg=_COLORS["surface"], fg=_COLORS["danger"])
        self._conn_lbl.pack(side="right", padx=8)

        # quick action buttons
        for txt, cmd in [("Connect", "dys connect"), ("Reset", "dys reset"),
                         ("Status", "dys status"),  ("Clear", "clear")]:
            btn = tk.Button(hdr, text=txt,
                bg=_COLORS["btn"], fg=_COLORS["text"],
                font=("Segoe UI", 8), relief="flat", cursor="hand2",
                padx=8, pady=2, activebackground=_COLORS["btn_hover"],
                command=lambda c=cmd: self._exec(c))
            btn.pack(side="right", padx=2)

        # ── Main paned window (CLI left | live log right) ─────────────────
        pane = tk.PanedWindow(self, orient="horizontal",
                              bg=_COLORS["border"], sashwidth=4,
                              sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=0, pady=0)

        # ── CLI panel ─────────────────────────────────────────────────────
        cli_frame = tk.Frame(pane, bg=_COLORS["bg"])
        pane.add(cli_frame, minsize=400, stretch="always")

        out_wrap = tk.Frame(cli_frame, bg=_COLORS["console_bg"])
        out_wrap.pack(fill="both", expand=True, padx=(8,4), pady=(6,0))

        self._out = tk.Text(
            out_wrap,
            bg=_COLORS["console_bg"], fg=_COLORS["console_text"],
            font=("Consolas", 9), relief="flat", bd=0,
            state="disabled", wrap="word", padx=10, pady=8,
        )
        sb = ttk.Scrollbar(out_wrap, orient="vertical", command=self._out.yview)
        self._out.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._out.pack(side="left", fill="both", expand=True)
        self._configure_tags(self._out)

        # input row
        in_row = tk.Frame(cli_frame, bg=_COLORS["surface"], pady=6, padx=8)
        in_row.pack(fill="x", padx=8, pady=(4,8))

        tk.Label(in_row, text="dys❯",
                 font=("Consolas", 10, "bold"),
                 bg=_COLORS["surface"], fg="#a855f7").pack(side="left", padx=(0,6))

        self._inp_var = tk.StringVar()
        self._inp = tk.Entry(in_row, textvariable=self._inp_var,
                             bg=_COLORS["surface"], fg=_COLORS["text"],
                             font=("Consolas", 10), relief="flat", bd=0,
                             insertbackground="#a855f7")
        self._inp.pack(side="left", fill="x", expand=True, ipady=4)
        self._inp.bind("<Return>",     self._on_enter)
        self._inp.bind("<Up>",         self._hist_up)
        self._inp.bind("<Down>",       self._hist_down)
        self._inp.bind("<Tab>",        self._autocomplete_tab)
        self._inp.bind("<KeyRelease>", self._on_key_release)
        self._inp.bind("<FocusOut>",   self._hide_autocomplete)
        self._inp.bind("<Escape>",     self._hide_autocomplete)
        self._inp.focus_set()

        tk.Button(in_row, text="Ejecutar",
                  command=lambda: self._on_enter(None),
                  bg="#a855f7", fg="#fff",
                  font=("Segoe UI", 9, "bold"), relief="flat",
                  cursor="hand2", padx=10, pady=3,
                  activebackground="#9333ea").pack(side="right")

        # ── Live event log panel ───────────────────────────────────────────
        log_frame = tk.Frame(pane, bg=_COLORS["bg"])
        pane.add(log_frame, minsize=280, stretch="never")

        log_hdr = tk.Frame(log_frame, bg=_COLORS["surface2"], pady=4, padx=8)
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="📡 Live Events",
                 font=("Segoe UI", 9, "bold"),
                 bg=_COLORS["surface2"], fg=_COLORS["accent"]).pack(side="left")

        # filter dropdown
        cats = ["all", "firewall", "traffic", "ipmanager", "connect", "system", "test"]
        filter_opt = ttk.Combobox(log_hdr, textvariable=self._filter_var,
                                  values=cats, width=10, state="readonly",
                                  font=("Segoe UI", 8))
        filter_opt.pack(side="right", padx=4)
        tk.Label(log_hdr, text="Filtro:",
                 font=("Segoe UI", 8), bg=_COLORS["surface2"],
                 fg=_COLORS["text_muted"]).pack(side="right")

        live_wrap = tk.Frame(log_frame, bg=_COLORS["console_bg"])
        live_wrap.pack(fill="both", expand=True, padx=(4,8), pady=(4,0))

        self._live = tk.Text(
            live_wrap,
            bg=_COLORS["console_bg"], fg=_COLORS["console_text"],
            font=("Consolas", 8), relief="flat", bd=0,
            state="disabled", wrap="word", padx=6, pady=6,
        )
        lsb = ttk.Scrollbar(live_wrap, orient="vertical", command=self._live.yview)
        self._live.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self._live.pack(side="left", fill="both", expand=True)
        self._configure_tags(self._live)

        # clear live log button
        clr_row = tk.Frame(log_frame, bg=_COLORS["surface2"], pady=3, padx=6)
        clr_row.pack(fill="x")
        tk.Button(clr_row, text="🗑 Limpiar log",
                  bg=_COLORS["surface2"], fg=_COLORS["text_muted"],
                  font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  padx=6, pady=1,
                  command=self._clear_live).pack(side="right")
        tk.Checkbutton(clr_row, text="Auto-scroll",
                       variable=self._live_enabled,
                       bg=_COLORS["surface2"], fg=_COLORS["text_muted"],
                       selectcolor=_COLORS["surface2"],
                       font=("Segoe UI", 8), relief="flat").pack(side="left")

    def _configure_tags(self, widget: tk.Text):
        for tag, color in _TAG_COLORS.items():
            widget.tag_configure(tag, foreground=color)
        widget.tag_configure("header", foreground=_COLORS["console_header"],
                             font=("Consolas", 9, "bold"))
        widget.tag_configure("ascii",  foreground="#6a8fff",
                             font=("Consolas", 8))
        widget.tag_configure("traffic", foreground="#888eb0",
                             font=("Consolas", 8))

    # ── Write helpers ─────────────────────────────────────────────────────

    def _write(self, text: str, tag: str = "info"):
        def _do():
            self._out.configure(state="normal")
            self._out.insert("end", text + "\n", tag)
            self._out.configure(state="disabled")
            self._out.see("end")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _clear_out(self):
        def _do():
            self._out.configure(state="normal")
            self._out.delete("1.0", "end")
            self._out.configure(state="disabled")
        self.after(0, _do)

    def _write_live(self, text: str, tag: str = "info"):
        def _do():
            self._live.configure(state="normal")
            self._live.insert("end", text + "\n", tag)
            # Keep log trimmed
            lines = int(self._live.index("end-1c").split(".")[0])
            if lines > 800:
                self._live.delete("1.0", "300.0")
            self._live.configure(state="disabled")
            if self._live_enabled.get():
                self._live.see("end")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _clear_live(self):
        self._live.configure(state="normal")
        self._live.delete("1.0", "end")
        self._live.configure(state="disabled")

    def _on_live_event(self, ev: dict):
        """Callback llamado por _STATE cuando hay un nuevo evento."""
        cat_filter = self._filter_var.get()
        if cat_filter != "all" and ev["category"] != cat_filter:
            return
        # Map category to color tag
        cat_tags = {
            "firewall":  "fw",
            "traffic":   "traffic",
            "ipmanager": "ipmgr",
            "connect":   "ok",
            "system":    "muted",
            "test":      "warn",
        }
        tag = cat_tags.get(ev["category"], ev["level"])
        self._write_live(f"[{ev['ts']}] {ev['msg']}", tag)
        # Update connection indicator
        if ev["category"] == "connect":
            self.after(0, self._update_conn_label)

    def _update_conn_label(self):
        if _STATE.connected:
            self._conn_lbl.config(text="🟢 ONLINE", fg=_COLORS["success"])
        else:
            self._conn_lbl.config(text="⚫ OFFLINE", fg=_COLORS["danger"])

    # ── Banner ────────────────────────────────────────────────────────────

    def _print_banner(self):
        for line in _DAYUS_ASCII.splitlines():
            self._write(line, "ascii")
        self._write(_DAYUS_SUBTITLE, "muted")
        self._write(_DAYUS_RULE, "muted")
        self._write("", "info")
        self._write("  Bienvenido al entorno de pruebas y debugging de FyreWall.", "muted")
        self._write("  Usa 'connect' para activar la red virtual e interceptar FyreWall.", "muted")
        self._write("  Escribe 'help' para ver todos los comandos disponibles.", "muted")
        self._write("", "info")
        self._write(_DAYUS_RULE, "muted")
        self._write("", "info")

    # ── Input handling ────────────────────────────────────────────────────

    def _on_enter(self, event):
        raw = self._inp_var.get().strip()
        if not raw:
            return
        self._hide_autocomplete()
        self._inp_var.set("")
        self._history.insert(0, raw)
        self._hist_idx = -1
        self._write(f"\ndys❯ {raw}", "prompt")
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _exec(self, cmd: str):
        """Execute a command programmatically (from buttons)."""
        self._write(f"\ndys❯ {cmd}", "prompt")
        threading.Thread(target=self._dispatch, args=(cmd,), daemon=True).start()

    def _hist_up(self, event):
        if self._history and self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self._inp_var.set(self._history[self._hist_idx])
        return "break"

    def _hist_down(self, event):
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self._inp_var.set(self._history[self._hist_idx])
        elif self._hist_idx == 0:
            self._hist_idx = -1
            self._inp_var.set("")
        return "break"

    def _on_key_release(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down", "Tab"):
            return
        self._show_autocomplete_popup()

    def _show_autocomplete_popup(self):
        current = self._inp_var.get()
        if not current:
            self._hide_autocomplete()
            return

        matches = [(cmd, desc) for cmd, desc in _DYS_COMMANDS if cmd.startswith(current)]

        if not matches:
            self._hide_autocomplete()
            return

        if self._autocomplete_popup is None or not self._autocomplete_popup.winfo_exists():
            self._autocomplete_popup = tk.Toplevel(self)
            self._autocomplete_popup.wm_overrideredirect(True)
            self._autocomplete_popup.configure(bg=_COLORS["border"])

        for w in self._autocomplete_popup.winfo_children():
            w.destroy()

        x = self._inp.winfo_rootx()
        y = self._inp.winfo_rooty() - (len(matches[:8]) * 26 + 8)
        self._autocomplete_popup.geometry(f"+{x}+{y}")

        frame = tk.Frame(self._autocomplete_popup, bg=_COLORS["surface2"], padx=1, pady=1)
        frame.pack(fill="both", expand=True)

        for i, (cmd, desc) in enumerate(matches[:8]):
            row = tk.Frame(frame, bg=_COLORS["surface2"])
            row.pack(fill="x")

            matched_len = len(current)
            cmd_label = tk.Frame(row, bg=_COLORS["surface2"])
            cmd_label.pack(side="left", padx=(6, 0), pady=2)

            tk.Label(cmd_label, text=cmd[:matched_len],
                     font=("Consolas", 9, "bold"),
                     bg=_COLORS["surface2"], fg=_COLORS["accent"]).pack(side="left")
            tk.Label(cmd_label, text=cmd[matched_len:],
                     font=("Consolas", 9),
                     bg=_COLORS["surface2"], fg=_COLORS["text"]).pack(side="left")

            tk.Label(row, text=f"  {desc}",
                     font=("Segoe UI", 8),
                     bg=_COLORS["surface2"], fg=_COLORS["text_muted"]).pack(side="left", padx=(4, 8))

            def on_enter(e, r=row):
                r.config(bg=_COLORS["accent"])
                for w in r.winfo_children():
                    w.config(bg=_COLORS["accent"])
                    for ww in w.winfo_children():
                        ww.config(bg=_COLORS["accent"], fg="#000000")

            def on_leave(e, r=row):
                r.config(bg=_COLORS["surface2"])
                for w in r.winfo_children():
                    w.config(bg=_COLORS["surface2"])
                    for ww in w.winfo_children():
                        ww.config(bg=_COLORS["surface2"])

            def on_click(e, c=cmd):
                self._inp_var.set(c)
                self._inp.icursor("end")
                self._hide_autocomplete()
                self._inp.focus_set()

            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            row.bind("<Button-1>", on_click)
            for w in row.winfo_children():
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)

        self._autocomplete_popup.lift()

    def _hide_autocomplete(self, event=None):
        if self._autocomplete_popup and self._autocomplete_popup.winfo_exists():
            self._autocomplete_popup.destroy()
            self._autocomplete_popup = None

    def _autocomplete_tab(self, event):
        current = self._inp_var.get()
        matches = [cmd for cmd, _ in _DYS_COMMANDS if cmd.startswith(current)]
        if len(matches) == 1:
            self._inp_var.set(matches[0])
            self._inp.icursor("end")
        elif len(matches) > 1:
            common = matches[0]
            for m in matches[1:]:
                while not m.startswith(common):
                    common = common[:-1]
            if len(common) > len(current):
                self._inp_var.set(common)
                self._inp.icursor("end")
        self._hide_autocomplete()
        return "break"

    # ── Command dispatch ──────────────────────────────────────────────────

    def _dispatch(self, raw: str):
        w = self._write
        parts = raw.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "clear":
            self.after(0, self._clear_out)
            return

        # Aceptar también el prefijo "dys"/"dayus" por compatibilidad
        if cmd in ("dys", "dayus"):
            if not args:
                w(_DAYUS_HELP, "muted"); return
            cmd  = args[0].lower()
            args = args[1:]

        if cmd == "help":           w(_DAYUS_HELP, "muted")
        elif cmd == "connect":      _cmd_connect(w)
        elif cmd == "disconnect":   _cmd_disconnect(w)
        elif cmd == "status":       _cmd_status(w)
        elif cmd == "version":      _cmd_version(w)
        elif cmd == "reset":        _cmd_reset(w)
        elif cmd == "create-ip":    _cmd_create_ip(args, w)
        elif cmd == "create-port":  _cmd_create_port(args, w)
        elif cmd == "create-subnet":_cmd_create_subnet(args, w)
        elif cmd == "delete-ip":    _cmd_delete_ip(args, w)
        elif cmd == "delete-port":  _cmd_delete_port(args, w)
        elif cmd == "delete-all":   _cmd_delete_all(w)
        elif cmd == "block-ip":     _cmd_block_ip(args, w)
        elif cmd == "unblock-ip":   _cmd_unblock_ip(args, w)
        elif cmd == "block-port":   _cmd_block_port(args, w)
        elif cmd == "unblock-port": _cmd_unblock_port(args, w)
        elif cmd == "blockall-ips": _cmd_blockall_ips(w)
        elif cmd == "isolate":      _cmd_isolate(args, w)
        elif cmd == "ping":         _cmd_ping(args, w)
        elif cmd == "flood":        _cmd_flood(args, w)
        elif cmd == "inject":       _cmd_inject(args, w)
        elif cmd == "latency":      _cmd_latency(args, w)
        elif cmd == "packetloss":   _cmd_packetloss(args, w)
        elif cmd == "bandwidth":    _cmd_bandwidth(args, w)
        elif cmd == "stress":       _cmd_stress(args, w)
        elif cmd == "list-ips":     _cmd_list_ips(w)
        elif cmd == "list-ports":   _cmd_list_ports(w)
        elif cmd == "list-blocked": _cmd_list_blocked(w)
        elif cmd == "inspect":      _cmd_inspect(args, w)
        elif cmd == "top":          _cmd_top(w)
        elif cmd == "trace":        _cmd_trace(args, w)
        elif cmd == "scan":         _cmd_scan(args, w)
        elif cmd == "log":          _cmd_log(args, w)
        elif cmd == "log-filter":   _cmd_log_filter(args, w)
        elif cmd == "snapshot":     _cmd_snapshot(args, w)
        else:
            w(f"  ❌  Comando desconocido: '{cmd}'. Escribe 'help'.", "error")


# ─── PLUGIN ENTRY POINT ──────────────────────────────────────────────────────

def build_dayus_tab(parent_frame: tk.Frame, app_ref):
    """
    Llamado por FyreWall (_open_plugin_tab) para construir la UI de DAYUS.
    Recibe el frame contenedor y la referencia a la app principal.
    """
    tab = DayusTab(parent_frame, app_ref)
    tab.pack(fill="both", expand=True)
