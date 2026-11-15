"""Caelestia ``shell.json`` helpers (global + per-monitor).

Caelestia reads ``~/.config/caelestia/shell.json`` and optionally overrides
values per monitor from ``~/.config/caelestia/monitors/<name>/shell.json``.
This module merges both, writes only the keys the user changes, and restarts
the shell afterwards so the change is visible immediately.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from src import backup
from src.config import MONITOR_SHELL_DIR, SHELL_JSON, restart_caelestia

__all__ = [
    "deep_merge",
    "delete_monitor_value",
    "delete_value",
    "get",
    "read_effective",
    "read_global",
    "read_monitor",
    "save_global",
    "save_monitor",
    "set_monitor_value",
    "set_value",
    "wallpaper_dir",
]

# Defaults for the handful of options the app exposes directly.  Anything not
# listed here is simply read from shell.json when present.
DEFAULTS: dict[str, Any] = {
    "background.enabled": True,
    "background.wallpaperEnabled": True,
    "background.desktopClock.enabled": False,
    "background.desktopClock.position": "bottom-right",
    "background.desktopClock.scale": 1,
    "background.desktopClock.invertColors": False,
    "background.desktopClock.background.enabled": False,
    "background.desktopClock.background.opacity": 0.7,
    "background.desktopClock.background.blur": True,
    "background.desktopClock.shadow.enabled": True,
    "background.desktopClock.shadow.opacity": 0.7,
    "background.desktopClock.shadow.blur": 0.4,
    "bar.persistent": True,
}


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def read_global() -> dict:
    try:
        if SHELL_JSON.exists():
            data = json.loads(SHELL_JSON.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {SHELL_JSON}: {exc}")
    return {}


def read_monitor(monitor: str) -> dict:
    if not monitor:
        return {}
    path = MONITOR_SHELL_DIR / monitor / "shell.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {path}: {exc}")
    return {}


def read_effective(monitor: str | None = None) -> dict:
    data = read_global()
    if monitor:
        data = deep_merge(data, read_monitor(monitor))
    return data


def _split(dotted: str) -> list[str]:
    return [part for part in dotted.split(".") if part]


def _lookup(data: dict, dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in _split(dotted):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _insert(data: dict, dotted: str, value: Any) -> None:
    parts = _split(dotted)
    if not parts:
        return
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _remove(data: dict, dotted: str) -> bool:
    parts = _split(dotted)
    if not parts:
        return False

    # Walk down, remembering the parents so empty containers can be pruned.
    parents: list[tuple[dict, str]] = []
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            return False
        parents.append((node, part))
        node = child
    if parts[-1] not in node:
        return False
    del node[parts[-1]]

    for parent, key in reversed(parents):
        if isinstance(parent.get(key), dict) and not parent[key]:
            del parent[key]
        else:
            break
    return True


def get(dotted: str, default: Any = None, monitor: str | None = None) -> Any:
    value = _lookup(read_effective(monitor), dotted, None)
    if value is None:
        value = DEFAULTS.get(dotted, default)
    return value if value is not None else default


def _save(path: Path, data: dict) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    return backup.atomic_write_text(path, json.dumps(data, indent=4) + "\n")


def save_global(data: dict, *, restart: bool = True) -> Path | None:
    backup_path = _save(SHELL_JSON, data)
    if restart:
        restart_caelestia()
    return backup_path


def save_monitor(monitor: str, data: dict, *, restart: bool = True) -> Path | None:
    if not monitor:
        raise ValueError("monitor name is required")
    backup_path = _save(MONITOR_SHELL_DIR / monitor / "shell.json", data)
    if restart:
        restart_caelestia()
    return backup_path


def set_value(dotted: str, value: Any) -> None:
    data = read_global()
    _insert(data, dotted, value)
    save_global(data)


def set_many(values: dict[str, Any], monitor: str | None = None, *, restart: bool = True) -> None:
    """Write several dotted keys in one pass (one backup, one restart)."""

    if monitor:
        data = read_monitor(monitor)
        for dotted, value in values.items():
            _insert(data, dotted, value)
        save_monitor(monitor, data, restart=restart)
    else:
        data = read_global()
        for dotted, value in values.items():
            _insert(data, dotted, value)
        save_global(data, restart=restart)


def apply_changes_tracked(
    changes: dict[str, Any],
    resets: set[str] | None = None,
    monitor: str | None = None,
    *,
    restart: bool = True,
) -> tuple[bool, dict[Path, Path]]:
    """Apply staged values and return ``(changed, {target: backup})``.

    The backup mapping lets the UI offer "Undo last apply".
    """

    resets = resets or set()
    if not changes and not resets:
        return False, {}

    if monitor:
        data = read_monitor(monitor)
    else:
        data = read_global()
    before = copy.deepcopy(data)

    for dotted, value in changes.items():
        _insert(data, dotted, value)
    for dotted in resets:
        _remove(data, dotted)

    if data == before:
        return False, {}

    if monitor:
        backup_path = save_monitor(monitor, data, restart=restart)
        target = MONITOR_SHELL_DIR / monitor / "shell.json"
    else:
        backup_path = save_global(data, restart=restart)
        target = SHELL_JSON

    return True, ({target: backup_path} if backup_path else {})


def apply_changes(
    changes: dict[str, Any],
    resets: set[str] | None = None,
    monitor: str | None = None,
    *,
    restart: bool = True,
) -> bool:
    """Apply staged values and report whether anything changed."""

    return apply_changes_tracked(
        changes, resets, monitor=monitor, restart=restart
    )[0]


def delete_value(dotted: str) -> bool:
    data = read_global()
    changed = _remove(data, dotted)
    if changed:
        save_global(data)
    return changed


def set_monitor_value(monitor: str, dotted: str, value: Any, *, restart: bool = True) -> None:
    data = read_monitor(monitor)
    _insert(data, dotted, value)
    save_monitor(monitor, data, restart=restart)


def delete_monitor_value(monitor: str, dotted: str, *, restart: bool = True) -> bool:
    data = read_monitor(monitor)
    changed = _remove(data, dotted)
    if changed:
        save_monitor(monitor, data, restart=restart)
    return changed


def _pictures_dir() -> Path:
    try:
        result = subprocess.run(
            ["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / "Pictures"


def expand_path(value: str) -> Path:
    value = (value or "").strip()
    if not value:
        return _pictures_dir() / "Wallpapers"
    if value.startswith("~"):
        value = str(Path.home()) + value[1:]
    return Path(value)


def wallpaper_dir() -> Path:
    configured = get("paths.wallpaperDir", "")
    if configured:
        return expand_path(str(configured))
    return _pictures_dir() / "Wallpapers"
