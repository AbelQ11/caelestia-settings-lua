"""Paths and shared configuration helpers.

All user-facing files the app may modify are defined here.  Writes go through
:mod:`src.backup`, which guarantees a timestamped backup and an atomic
replacement for every change.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from src import backup
from src.lua import iter_calls
from src.lang import t

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "caelestia-settings"
MONITOR_CONFIG_FILE = CONFIG_DIR / "monitors.json"
WINDOW_RULES_CONFIG_FILE = CONFIG_DIR / "window_rules.json"
APP_DATA_DIR = HOME / ".local" / "share" / "caelestia-settings"

HYPR_DIR = Path(os.getenv("XDG_CONFIG_HOME", HOME / ".config")) / "hypr"
CAELESTIA_DIR = Path(os.getenv("XDG_CONFIG_HOME", HOME / ".config")) / "caelestia"

HYPR_HYPRLAND_DIR = HYPR_DIR / "hyprland"
HYPR_INPUT_LUA = HYPR_HYPRLAND_DIR / "input.lua"
HYPR_EXECS_LUA = HYPR_HYPRLAND_DIR / "execs.lua"
HYPR_RULES_LUA = HYPR_HYPRLAND_DIR / "rules.lua"
HYPR_KEYBINDS_DEFAULT_LUA = HYPR_HYPRLAND_DIR / "keybinds.lua"
HYPR_DEFAULT_KEYBINDS_LUA = HYPR_KEYBINDS_DEFAULT_LUA
HYPR_MONITORS_LUA = HYPR_DIR / "monitors.lua"
HYPR_VARIABLES_LUA = HYPR_DIR / "variables.lua"

HYPR_USER_LUA = CAELESTIA_DIR / "hypr-user.lua"
HYPR_VARS_LUA = CAELESTIA_DIR / "hypr-vars.lua"
SHELL_JSON = CAELESTIA_DIR / "shell.json"
SHELL_TOKENS_JSON = CAELESTIA_DIR / "shell-tokens.json"
MONITOR_SHELL_DIR = CAELESTIA_DIR / "monitors"

# The file a user can safely extend.  Everything written by this app goes here
# (or into monitors.lua) so that caelestia updates never overwrite it.
HYPR_USER_OVERRIDES = HYPR_USER_LUA
HYPR_WORKSPACES_LUA = HYPR_MONITORS_LUA

# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------

HYPR_INPUT_CONF = HYPR_INPUT_LUA
HYPR_MONITORS_CONF = HYPR_MONITORS_LUA
HYPR_RULES_CONF = HYPR_USER_LUA
HYPR_KEYBINDS_CONF = HYPR_KEYBINDS_DEFAULT_LUA
HYPR_KEYBINDS_LUA = HYPR_KEYBINDS_DEFAULT_LUA
HYPR_EXECS_CONF = HYPR_EXECS_LUA

# Managed block identifiers
BLOCK_INPUT = "input"
BLOCK_KEYBINDS = "custom keybinds"
BLOCK_RULES = "window rules"
BLOCK_INPUT_DEVICES = "input devices"
BLOCK_AUTOSTART = "autostart"
BLOCK_HYPR_VARS = "hyprland styling"


# ---------------------------------------------------------------------------
# Small file helpers
# ---------------------------------------------------------------------------


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def write_text(path: Path, content: str) -> Path | None:
    """Write a user file, creating a timestamped backup first."""

    return backup.atomic_write_text(path, content)


def reload_hyprland() -> bool:
    try:
        result = subprocess.run(
            ["hyprctl", "reload"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def hyprctl_config_errors() -> str:
    """Return Hyprland's current configuration errors, or an empty string."""

    try:
        result = subprocess.run(
            ["hyprctl", "configerrors"], capture_output=True, text=True, timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def reload_hyprland_checked() -> tuple[bool, str]:
    """Reload Hyprland and return ``(reload_ok, config_errors)``."""

    ok = reload_hyprland()
    return ok, hyprctl_config_errors()


def restart_caelestia() -> bool:
    """Ask the Caelestia shell to reload ``shell.json`` changes."""

    try:
        result = subprocess.run(
            ["caelestia", "shell", "-r"], capture_output=True, timeout=8, check=False
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------------------
# App-owned JSON (monitor layout cache + window-rule cache)
# ---------------------------------------------------------------------------


def load_monitor_config() -> dict:
    try:
        if MONITOR_CONFIG_FILE.exists():
            return json.loads(MONITOR_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not load {MONITOR_CONFIG_FILE}: {exc}")
    return {}


def save_monitor_config(config_data: dict) -> None:
    try:
        write_text(MONITOR_CONFIG_FILE, json.dumps(config_data, indent=2) + "\n")
    except Exception as exc:  # pragma: no cover - defensive UI path
        print(f"Could not save {MONITOR_CONFIG_FILE}: {exc}")


def load_window_rules_config() -> dict:
    try:
        if WINDOW_RULES_CONFIG_FILE.exists():
            return json.loads(WINDOW_RULES_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not load {WINDOW_RULES_CONFIG_FILE}: {exc}")
    return {}


def save_window_rules_config(config_data: dict) -> None:
    try:
        write_text(WINDOW_RULES_CONFIG_FILE, json.dumps(config_data, indent=2) + "\n")
    except Exception as exc:  # pragma: no cover - defensive UI path
        print(f"Could not save {WINDOW_RULES_CONFIG_FILE}: {exc}")


# ---------------------------------------------------------------------------
# Lua parsing
# ---------------------------------------------------------------------------


def _as_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _monitor_candidates() -> list[Path]:
    candidates = [HYPR_MONITORS_LUA, HYPR_HYPRLAND_DIR / "monitors.lua", HYPR_USER_LUA]
    return [path for path in candidates if path.exists()]


def parse_monitors_conf() -> dict:
    """Read monitors and workspace rules from the Hyprland Lua config.

    ``monitors.lua`` is used when present; ``hyprland/monitors.lua`` and
    ``hypr-user.lua`` are fallbacks.  Unknown fields are returned too, so the
    monitor page can preserve them when saving.
    """

    monitors: list[dict] = []
    workspaces: list[dict] = []

    for target in _monitor_candidates():
        try:
            text = read_text(target)
        except OSError:
            continue
        if not text:
            continue

        found_monitor = False
        for call in iter_calls(text, {"hl.monitor"}):
            table = call.table if isinstance(call.table, dict) else None
            if not table or "output" not in table:
                continue
            found_monitor = True
            entry = {
                "name": _as_string(table.get("output")),
                "resolution": _as_string(table.get("mode", "?")),
                "position": _as_string(table.get("position", "auto")),
                "scale": _as_string(table.get("scale", "1")),
                "disabled": bool(table.get("disabled", False)),
                "bitdepth": _as_string(table.get("bitdepth", "")),
                "transform": _as_string(table.get("transform", "")),
                "cm": _as_string(table.get("cm", "")),
                "vrr": table.get("vrr"),
                "mirror": _as_string(table.get("mirror", "")),
                "_fields": table,
            }
            monitors.append(entry)

        for call in iter_calls(text, {"hl.workspace_rule"}):
            table = call.table if isinstance(call.table, dict) else None
            if not table or "workspace" not in table:
                continue
            raw = _as_string(table.get("workspace")).strip()
            entry = {
                "workspace": raw,
                "number": int(raw) if raw.isdigit() else None,
                "monitor": _as_string(table.get("monitor", "")),
                "default": bool(table.get("default", False)),
                "persistent": bool(table.get("persistent", False)),
                "gaps_in": table.get("gaps_in"),
                "gaps_out": table.get("gaps_out"),
                "layout": _as_string(table.get("layout", "")),
                "no_rounding": bool(table.get("no_rounding", False)),
                "no_border": bool(table.get("no_border", False)),
                "no_shadow": bool(table.get("no_shadow", False)),
                "decorate": bool(table.get("decorate", True)),
                "_fields": table,
            }
            workspaces.append(entry)

        if found_monitor or workspaces:
            break

    workspaces.sort(key=lambda item: (item["number"] is None, item["number"] or 0, item["workspace"]))

    ws_options: list[tuple[str, str]] = [("default", t("Default (no rule)"))]
    for ws in workspaces:
        label = f"Workspace {ws['workspace']}"
        if ws["monitor"]:
            label += f"  –  {ws['monitor']}"
        if ws["default"]:
            label += "  ★"
        ws_options.append((ws["workspace"], label))

    for special in ("sysmon", "music", "communication", "todo", "scratch"):
        ws_options.append((f"special:{special}", f"Special: {special}"))

    return {"monitors": monitors, "workspaces": workspaces, "workspace_options": ws_options}


parse_monitors_lua = parse_monitors_conf


def _managed_ranges(text: str) -> list[tuple[int, int]]:
    import re

    ranges = []
    pattern = re.compile(
        r"(?ms)^[ \t]*-- BEGIN Caelestia Settings: window rules.*?^[ \t]*-- END Caelestia Settings: window rules[ \t]*$"
    )
    for match in pattern.finditer(text):
        ranges.append((match.start(), match.end()))
    # Legacy flat markers: everything after the marker is managed.
    for legacy in (
        "-- Auto-generated by Caelestia Settings – Fenster-Regeln",
        "-- Auto-generated by Caelestia Settings – Window Rules",
        "# Auto-generated by Caelestia Settings – Fenster-Regeln",
    ):
        idx = text.find(legacy)
        if idx >= 0:
            ranges.append((idx, len(text)))
    return ranges


def _rule_summary(table: dict) -> str:
    parts = []
    for key, value in table.items():
        if key in ("match", "name", "enabled", "__array__"):
            continue
        if isinstance(value, bool):
            parts.append("float true" if key == "float" and value else f"{key} true")
        elif isinstance(value, dict):
            inner = " ".join(_as_string(v) for v in value.values())
            parts.append(f"{key} {inner}")
        else:
            parts.append(f"{key} {_as_string(value)}")
    return ", ".join(parts)


def parse_rules_conf() -> list[dict]:
    """Read window rules from ``rules.lua`` and ``hypr-user.lua``."""

    result: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for target in (HYPR_RULES_LUA, HYPR_USER_LUA):
        if not target.exists():
            continue
        text = read_text(target)
        if not text:
            continue
        ranges = _managed_ranges(text)

        for call in iter_calls(text, {"hl.window_rule"}):
            table = call.table if isinstance(call.table, dict) else None
            if not table:
                continue
            match = table.get("match")
            match_type = "class"
            match_val = ""
            if isinstance(match, dict):
                for field in ("class", "initial_class", "title", "initial_title"):
                    if field in match:
                        match_type = field
                        match_val = _as_string(match[field])
                        break
            elif isinstance(match, list):
                match_val = "|".join(_as_string(v) for v in match)
            if not match_val:
                # Tag-only rules (rules.lua internals) are not app-targeted.
                continue

            managed = any(start <= call.start < end for start, end in ranges)
            rule = _rule_summary(table)
            signature = (match_type, match_val, rule)
            if signature in seen:
                continue
            seen.add(signature)

            result.append(
                {
                    "rule": rule,
                    "match_type": match_type,
                    "match_val": match_val,
                    "raw": text[call.start:call.end].strip(),
                    "managed": managed,
                    "source": str(target),
                    "fields": table,
                }
            )

    return result


parse_rules_lua = parse_rules_conf
