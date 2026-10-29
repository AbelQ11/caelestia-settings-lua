from src.lang import t
import os
import json
import re
from pathlib import Path

try:
    import caelestia_core
except ImportError:
    import sys
    app_data = Path(os.path.expanduser("~/.local/share/caelestia-settings"))
    if str(app_data) not in sys.path:
        sys.path.insert(0, str(app_data))
    try:
        import caelestia_core
    except ImportError:
        caelestia_core = None

# Pfade
CONFIG_DIR = Path(os.path.expanduser("~/.config/caelestia-settings"))
MONITOR_CONFIG_FILE = CONFIG_DIR / "monitors.json"
WINDOW_RULES_CONFIG_FILE = CONFIG_DIR / "window_rules.json"
APP_DATA_DIR = Path(os.path.expanduser("~/.local/share/caelestia-settings"))

HYPR_DIR = Path(os.path.expanduser("~/.config/hypr"))
CAELESTIA_DIR = Path(os.path.expanduser("~/.config/caelestia"))

HYPR_INPUT_LUA = HYPR_DIR / "hyprland" / "input.lua"
HYPR_USER_LUA = CAELESTIA_DIR / "hypr-user.lua"
HYPR_VARS_LUA = CAELESTIA_DIR / "hypr-vars.lua"
HYPR_VARIABLES_LUA = HYPR_DIR / "variables.lua"
HYPR_MONITORS_LUA = HYPR_DIR / "monitors.lua"
HYPR_RULES_LUA = HYPR_DIR / "hyprland" / "rules.lua"
HYPR_KEYBINDS_LUA = HYPR_DIR / "keybinds.lua"
HYPR_EXECS_LUA = HYPR_DIR / "hyprland" / "execs.lua"

# Backward compatibility aliases
HYPR_INPUT_CONF = HYPR_INPUT_LUA
HYPR_MONITORS_CONF = HYPR_MONITORS_LUA
HYPR_RULES_CONF = HYPR_USER_LUA
HYPR_KEYBINDS_CONF = HYPR_KEYBINDS_LUA

def get_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR

def load_monitor_config():
    try:
        if MONITOR_CONFIG_FILE.exists():
            with open(MONITOR_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden von {MONITOR_CONFIG_FILE}: {e}")
    return {}

def save_monitor_config(config_data):
    try:
        get_config_dir().mkdir(parents=True, exist_ok=True)
        with open(MONITOR_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Monitor-Konfiguration gespeichert in {MONITOR_CONFIG_FILE}")
    except Exception as e:
        print(f"Fehler beim Speichern von {MONITOR_CONFIG_FILE}: {e}")

def load_window_rules_config():
    try:
        if WINDOW_RULES_CONFIG_FILE.exists():
            with open(WINDOW_RULES_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden von {WINDOW_RULES_CONFIG_FILE}: {e}")
    return {}

def save_window_rules_config(config_data):
    try:
        get_config_dir().mkdir(parents=True, exist_ok=True)
        with open(WINDOW_RULES_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Window-Rules gespeichert in {WINDOW_RULES_CONFIG_FILE}")
    except Exception as e:
        print(f"Fehler beim Speichern von {WINDOW_RULES_CONFIG_FILE}: {e}")


def _python_parse_monitors(text: str) -> tuple[list, list]:
    monitors = []
    workspaces = []

    if "hl.monitor" in text or "hl.workspace_rule" in text:
        for m in re.finditer(r'hl\.monitor\s*\(\s*\{([^}]+)\}\s*\)', text, re.DOTALL):
            fields = {}
            for line in m.group(1).splitlines():
                line = line.strip().strip(",")
                if "=" in line:
                    k, _, v = line.partition("=")
                    fields[k.strip()] = v.strip().strip('"\'')
            if "output" in fields:
                monitors.append({
                    "name": fields["output"],
                    "resolution": fields.get("mode", "?"),
                    "position": fields.get("position", "auto"),
                    "scale": fields.get("scale", "1"),
                })
        for m in re.finditer(r'hl\.workspace_rule\s*\(\s*\{([^}]+)\}\s*\)', text, re.DOTALL):
            fields = {}
            for line in m.group(1).splitlines():
                line = line.strip().strip(",")
                if "=" in line:
                    k, _, v = line.partition("=")
                    fields[k.strip()] = v.strip().strip('"\'')
            if "workspace" in fields:
                try:
                    num = int(fields["workspace"])
                    workspaces.append({
                        "number": num,
                        "monitor": fields.get("monitor", ""),
                        "default": fields.get("default", "false").lower() == "true",
                    })
                except ValueError:
                    pass
        return monitors, workspaces
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("monitor") and "=" in line and not line.startswith("monitor = desc:") and "{" not in line:
            parts = [p.strip() for p in line.split("=", 1)[1].split(",")]
            if parts and parts[0]:
                monitors.append({
                    "name": parts[0],
                    "resolution": parts[1] if len(parts) > 1 else "?",
                    "position": parts[2] if len(parts) > 2 else "auto",
                    "scale": parts[3] if len(parts) > 3 else "1",
                })
        elif line.startswith("workspace") and "=" in line and "{" not in line:
            parts = [p.strip() for p in line.split("=", 1)[1].split(",")]
            if parts:
                try:
                    num = int(parts[0])
                    mon = ""
                    default = False
                    for tok in parts[1:]:
                        if tok.startswith("monitor:"):
                            mon = tok.split("monitor:")[1]
                        if "default:true" in tok:
                            default = True
                    workspaces.append({"number": num, "monitor": mon, "default": default})
                except ValueError:
                    pass
    return monitors, workspaces


def parse_monitors_conf() -> dict:
    """
    Liest ~/.config/hypr/monitors.lua (oder Fallbacks) und gibt zurück:
    {
      "monitors":  [ {"name": "DP-1", "resolution": "2560x1440@179.95", ...}, ... ],
      "workspaces": [ {"number": 1, "monitor": "DP-1", "default": True}, ... ],
      "workspace_options": [ ("default", "Standard (keine Regel)"), ("1", "WS 1  –  DP-1  ★"), ... ]
    }
    """
    monitors  = []
    workspaces = []

    target_file = HYPR_MONITORS_LUA
    if not target_file.exists():
        fallback_lua = HYPR_DIR / "hyprland" / "monitors.lua"
        if fallback_lua.exists():
            target_file = fallback_lua
        elif HYPR_USER_LUA.exists():
            target_file = HYPR_USER_LUA

    if not target_file.exists():
        return {"monitors": [], "workspaces": [], "workspace_options": _fallback_ws_options()}

    try:
        text = target_file.read_text()
        if caelestia_core is not None:
            rust_monitors, rust_workspaces = caelestia_core.parse_monitors_conf(text)
            monitors = [
                {
                    "name":       m.name,
                    "resolution": m.resolution,
                    "position":   m.position,
                    "scale":      m.scale,
                }
                for m in rust_monitors
            ]
            workspaces = [
                {"number": w.number, "monitor": w.monitor, "default": w.default}
                for w in rust_workspaces
            ]
        else:
            monitors, workspaces = _python_parse_monitors(text)
    except Exception as e:
        print(f"Fehler beim Parsen von monitors.lua: {e}")

    workspaces.sort(key=lambda w: w["number"])

    ws_options = [("default", t("Standard (no rule)"))]
    for ws in workspaces:
        label = f"WS {ws['number']}  –  {ws['monitor']}" if ws["monitor"] else f"Workspace {ws['number']}"
        if ws["default"]:
            label += "  ★"
        ws_options.append((str(ws["number"]), label))

    for sp in ["sysmon", "music", "communication", "todo", "scratch"]:
        ws_options.append((f"special:{sp}", f"Special: {sp}"))

    return {"monitors": monitors, "workspaces": workspaces, "workspace_options": ws_options}

parse_monitors_lua = parse_monitors_conf


def _fallback_ws_options() -> list:
    opts = [("default", t("Standard (no rule)"))]
    for i in range(1, 21):
        opts.append((str(i), f"Workspace {i}"))
    for sp in ["sysmon", "music", "communication", "todo", "scratch"]:
        opts.append((f"special:{sp}", f"Special: {sp}"))
    return opts


def _python_parse_rules(text: str) -> list[dict]:
    result = []
    in_managed = False
    for line in text.splitlines():
        s = line.strip()
        if "Auto-generated by Caelestia Settings – Fenster-Regeln" in s:
            in_managed = True
            continue
        if s.startswith("--") or s.startswith("#") or not s:
            continue
        if "hl.window_rule" in s:
            match_m = re.search(r'match\s*=\s*\{\s*(class|title|initial_title|initial_class)\s*=\s*["\']([^"\']+)["\']', s)
            if match_m:
                m_type = match_m.group(1)
                m_val = match_m.group(2)
                ws_m = re.search(r'workspace\s*=\s*["\']?([^"\',}]+)["\']?', s)
                if ws_m:
                    result.append({
                        "rule": f"workspace {ws_m.group(1).strip()}",
                        "match_type": m_type,
                        "match_val": m_val,
                        "raw": s,
                        "managed": in_managed,
                    })
                if "float = true" in s or "float = 1" in s:
                    result.append({
                        "rule": "float true",
                        "match_type": m_type,
                        "match_val": m_val,
                        "raw": s,
                        "managed": in_managed,
                    })
        elif s.startswith("windowrule") and "=" in s:
            rest = s.split("=", 1)[1].strip()
            rule_part, match_type, match_val = rest, "class", ""
            if ", match:" in rest:
                idx = rest.rfind(", match:")
                rule_part = rest[:idx].strip()
                match_part = rest[idx + len(", match:"):].strip().split(None, 1)
                match_type = match_part[0] if match_part else "class"
                match_val = match_part[1] if len(match_part) > 1 else ""
            result.append({
                "rule": rule_part,
                "match_type": match_type,
                "match_val": match_val,
                "raw": s,
                "managed": in_managed,
            })
    return result


def parse_rules_conf() -> list:
    """
    Liest rules.lua und hypr-user.lua und gibt alle windowrule-Einträge strukturiert zurück.
    { "rule": "workspace special:music", "match_type": "class",
      "match_val": "feishin|Spotify", "raw": "...", "managed": False }
    """
    result = []
    candidates = []
    if HYPR_RULES_LUA.exists():
        candidates.append(HYPR_RULES_LUA)
    if HYPR_USER_LUA.exists():
        candidates.append(HYPR_USER_LUA)

    for target in candidates:
        try:
            content = target.read_text()
            if caelestia_core is not None:
                for r in caelestia_core.parse_rules_conf(content):
                    result.append({
                        "rule":       r.rule,
                        "match_type": r.match_type,
                        "match_val":  r.match_val,
                        "raw":        r.raw,
                        "managed":    r.managed,
                    })
            else:
                result.extend(_python_parse_rules(content))
        except Exception as e:
            print(f"Fehler beim Parsen von {target}: {e}")

    return result

parse_rules_lua = parse_rules_conf