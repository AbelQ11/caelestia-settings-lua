"""Health checks and repair actions.

The Health page is intentionally read-mostly: it reports the state of the app,
Caelestia, Hyprland and the wallpaper stack, and exposes a few explicit repair
actions (all of which back up every file before touching it).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src import backup, shell_config, shell_schema
from src.config import (
    APP_DATA_DIR,
    HYPR_USER_LUA,
    MONITOR_SHELL_DIR,
    SHELL_JSON,
    read_text,
    reload_hyprland,
    restart_caelestia,
    write_text,
)

HOME = Path.home()
_REPO_ROOT = Path(__file__).resolve().parents[1]
_WALLPAPER_STATE = HOME / ".local" / "state" / "caelestia" / "wallpaper" / "path.txt"


@dataclass
class CheckResult:
    key: str
    title: str
    status: str  # ok | info | warning | error
    detail: str
    data: dict = field(default_factory=dict)


def _run(command: list[str], timeout: int = 4) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


def _version(text: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(number) for number in numbers[:3])


def _same_version(a: str, b: str) -> bool:
    return _version(a) == _version(b)


def _pgrep(pattern: str, exact: bool = False) -> bool:
    command = ["pgrep", "-x" if exact else "-f", pattern]
    return _run(command)[0] == 0


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def app_version_check() -> CheckResult:
    repo_manifest = _REPO_ROOT / "manifest.json"
    installed_manifest = APP_DATA_DIR / "manifest.json"

    repo_version = "?"
    installed_version = "not installed"
    try:
        repo_version = json.loads(repo_manifest.read_text(encoding="utf-8")).get("version", "?")
    except (OSError, json.JSONDecodeError):
        pass
    try:
        installed_version = json.loads(
            installed_manifest.read_text(encoding="utf-8")
        ).get("version", "?")
    except (OSError, json.JSONDecodeError):
        pass

    if installed_version == "not installed":
        return CheckResult(
            "app_version",
            "Application version",
            "warning",
            f"Repository is {repo_version}, but the app is not installed. "
            "Run ./install.sh to update the menu entry and caelestia-settings command.",
            {"repo": repo_version, "installed": None},
        )

    if _same_version(repo_version, installed_version):
        return CheckResult(
            "app_version",
            "Application version",
            "ok",
            f"Repository and installed copy are both {repo_version}.",
            {"repo": repo_version, "installed": installed_version},
        )

    return CheckResult(
        "app_version",
        "Application version",
        "warning",
        f"Installed copy is {installed_version}, repository is {repo_version}. "
        "Run ./install.sh so the menu and caelestia-settings command use the new build.",
        {"repo": repo_version, "installed": installed_version},
    )


def installed_shell_version() -> str:
    code, output, _ = _run(["pacman", "-Q", "caelestia-shell"])
    if code == 0 and output:
        return output.split()[-1].rsplit("-", 1)[0]
    version_file = Path("/usr/lib/caelestia/version")
    try:
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    code, output, _ = _run(["caelestia", "-v"])
    match = re.search(r"caelestia-shell\s+([\d.]+)", output)
    return match.group(1) if match else "?"


def shell_version_check() -> CheckResult:
    installed = installed_shell_version()
    schema = shell_schema.source_tag().lstrip("v")
    if installed == "?":
        return CheckResult(
            "shell_version",
            "Caelestia shell version",
            "warning",
            f"Could not detect the installed shell version (schema is for {schema}).",
            {"installed": None, "schema": schema},
        )
    if _same_version(installed, schema):
        return CheckResult(
            "shell_version",
            "Caelestia shell version",
            "ok",
            f"Installed caelestia-shell {installed} matches schema {schema}.",
            {"installed": installed, "schema": schema},
        )
    return CheckResult(
        "shell_version",
        "Caelestia shell version",
        "warning",
        f"Installed caelestia-shell is {installed}, bundled schema is {schema}. "
        "New options may be missing. Regenerate with "
        "scripts/gen_shell_schema.py --tag vX.Y.Z.",
        {"installed": installed, "schema": schema},
    )


def dependency_checks() -> list[CheckResult]:
    dependencies = [
        ("caelestia", "Caelestia CLI", True),
        ("hyprctl", "Hyprland control", True),
        ("nmcli", "NetworkManager CLI", True),
        ("pactl", "PulseAudio/PipeWire control", True),
        ("pamixer", "Volume control", True),
        ("paplay", "Audio test sound", False),
        ("bluetoothctl", "Bluetooth control (BlueZ)", False),
        ("ffmpeg", "Video thumbnails", False),
        ("pkexec", "Polkit authentication", True),
        ("gsettings", "GTK settings", False),
        ("xdg-open", "Opening folders and files", False),
        ("qs", "Quickshell", False),
        ("xrandr", "XWayland primary monitor", False),
    ]
    results = []
    for command, label, required in dependencies:
        found = shutil.which(command)
        if found:
            results.append(
                CheckResult(
                    f"dep:{command}",
                    label,
                    "ok",
                    f"Found: {found}",
                    {"command": command, "required": required},
                )
            )
        else:
            results.append(
                CheckResult(
                    f"dep:{command}",
                    label,
                    "error" if required else "warning",
                    f"Missing from PATH ({'required' if required else 'optional'}).",
                    {"command": command, "required": required},
                )
            )
    return results


def hyprland_errors_check() -> CheckResult:
    code, output, error = _run(["hyprctl", "configerrors"])
    if code != 0:
        return CheckResult(
            "hyprland_errors",
            "Hyprland configuration",
            "warning",
            f"Could not query Hyprland: {error or 'hyprctl is not running'}",
        )
    if not output:
        return CheckResult(
            "hyprland_errors",
            "Hyprland configuration",
            "ok",
            "Hyprland reports no configuration errors.",
        )
    text = output if len(output) < 1200 else output[:1200] + "…"
    return CheckResult(
        "hyprland_errors",
        "Hyprland configuration",
        "error",
        text,
        {"errors": output},
    )


def _load_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else None), None
    except FileNotFoundError:
        return None, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def config_validity_checks() -> list[CheckResult]:
    files = [("Global shell.json", SHELL_JSON)]
    if MONITOR_SHELL_DIR.exists():
        for directory in sorted(MONITOR_SHELL_DIR.iterdir()):
            if directory.is_dir():
                files.append((f"{directory.name} shell.json", directory / "shell.json"))

    results = []
    for label, path in files:
        if not path.exists():
            continue
        data, error = _load_json_file(path)
        if error:
            results.append(
                CheckResult(
                    f"json:{path}", label, "error", f"Invalid JSON: {error}",
                    {"path": str(path)},
                )
            )
        elif data is None:
            results.append(
                CheckResult(
                    f"json:{path}", label, "warning", "Top-level value is not an object.",
                    {"path": str(path)},
                )
            )
    if not results:
        results.append(
            CheckResult(
                "json",
                "shell.json files",
                "ok",
                "All Caelestia shell configuration files parse correctly.",
            )
        )
    return results


def collect_leaf_paths(data: dict, prefix: str = "") -> list[str]:
    paths = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            paths.extend(collect_leaf_paths(value, path))
        else:
            paths.append(path)
    return paths


def unknown_shell_keys() -> dict[str, list[str]]:
    known = set(shell_schema.option_map())
    result: dict[str, list[str]] = {}

    global_data = shell_config.read_global()
    unknown_global = sorted(
        path for path in collect_leaf_paths(global_data) if path not in known
    )
    if unknown_global:
        result[""] = unknown_global

    if MONITOR_SHELL_DIR.exists():
        for directory in sorted(MONITOR_SHELL_DIR.iterdir()):
            if not directory.is_dir():
                continue
            data = shell_config.read_monitor(directory.name)
            unknown = sorted(
                path for path in collect_leaf_paths(data) if path not in known
            )
            if unknown:
                result[directory.name] = unknown

    return result


def unknown_keys_check() -> CheckResult:
    unknown = unknown_shell_keys()
    if not unknown:
        return CheckResult(
            "unknown_keys",
            "Unknown settings",
            "ok",
            "Every key in shell.json is known to the bundled schema.",
        )
    total = sum(len(paths) for paths in unknown.values())
    scopes = ", ".join(
        (scope or "global") for scope in unknown
    )
    return CheckResult(
        "unknown_keys",
        "Unknown settings",
        "warning",
        f"{total} unknown key(s) in {scopes}. They are ignored by the shell and can be removed.",
        {"unknown": unknown},
    )


def wallpaper_check() -> CheckResult:
    path = None
    try:
        if _WALLPAPER_STATE.exists():
            path = _WALLPAPER_STATE.read_text(encoding="utf-8").strip()
    except OSError:
        pass

    hyprpaper = _pgrep("hyprpaper", exact=True)
    shell = _pgrep("qs -c caelestia")

    if not path:
        status = "warning"
        detail = "No wallpaper has been set through Caelestia yet."
    else:
        wallpaper = Path(path)
        if not wallpaper.exists():
            status = "error"
            detail = f"The wallpaper file no longer exists: {path}"
        elif hyprpaper and shell:
            status = "warning"
            detail = (
                "Two wallpaper daemons are running: hyprpaper and the Caelestia shell. "
                "They can fight over monitors and leave one black. "
                "Disable hyprpaper's autostart and keep Caelestia's wallpaper, or "
                "turn off Wallpaper enabled for the affected monitor."
            )
        elif not shell:
            status = "warning"
            detail = (
                "The Caelestia shell is not running, so its wallpaper layer is not drawn. "
                "Start it with 'caelestia shell -d'."
            )
        else:
            status = "ok"
            detail = f"Wallpaper: {path}"

    return CheckResult(
        "wallpaper",
        "Wallpaper",
        status,
        detail,
        {"path": path, "hyprpaper": hyprpaper, "shell": shell},
    )


def kanshi_check() -> CheckResult:
    from src import kanshi

    if not kanshi.available():
        return CheckResult(
            "kanshi",
            "Kanshi",
            "ok",
            "Kanshi is not configured.",
        )
    running = kanshi.is_running()
    return CheckResult(
        "kanshi",
        "Kanshi",
        "info",
        (
            "Kanshi is running; the Monitor page syncs scale/position/mode changes "
            "into its profiles and reloads it."
            if running
            else "Kanshi config detected; monitor changes are written to its profiles."
        ),
        {"running": running},
    )


def backup_check() -> CheckResult:
    entries = backup.list_backups()
    if not entries:
        return CheckResult(
            "backups",
            "Backups",
            "info",
            "No backups yet. One is created automatically before every write.",
        )
    newest = entries[0]
    return CheckResult(
        "backups",
        "Backups",
        "ok",
        f"{len(entries)} backup(s). Newest: {newest.timestamp:%Y-%m-%d %H:%M:%S} "
        f"({newest.target}).",
        {"count": len(entries)},
    )


def run_all() -> list[CheckResult]:
    results = [
        app_version_check(),
        shell_version_check(),
        hyprland_errors_check(),
        wallpaper_check(),
        unknown_keys_check(),
        kanshi_check(),
        backup_check(),
    ]
    results.extend(config_validity_checks())
    results.extend(dependency_checks())
    return results


# ---------------------------------------------------------------------------
# Repair actions
# ---------------------------------------------------------------------------


def restart_shell() -> bool:
    try:
        subprocess.Popen(["caelestia", "shell", "-r"])
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def reload_hypr() -> bool:
    return reload_hyprland()


def reapply_wallpaper() -> bool:
    path = None
    try:
        if _WALLPAPER_STATE.exists():
            path = _WALLPAPER_STATE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    command = ["caelestia", "wallpaper"]
    if path:
        command += ["-f", path]
    else:
        command += ["-r"]
    try:
        subprocess.Popen(command)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def disable_hyprpaper() -> tuple[bool, bool]:
    """Comment out hyprpaper's autostart and stop the running daemon.

    Returns ``(file_changed, process_stopped)``.
    """

    text = read_text(HYPR_USER_LUA)
    lines = text.splitlines()
    changed = False
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if (
            not stripped.startswith("--")
            and "hl.exec_cmd" in line
            and "hyprpaper" in line
        ):
            lines[index] = f"-- {line}  -- disabled by Caelestia Settings"
            changed = True
    if changed:
        write_text(HYPR_USER_LUA, "\n".join(lines) + "\n")

    stopped = False
    try:
        result = subprocess.run(
            ["pkill", "-x", "hyprpaper"], capture_output=True, timeout=3, check=False
        )
        stopped = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass

    if changed or stopped:
        restart_caelestia()
    return changed, stopped


def remove_unknown_keys(scope_paths: dict[str, list[str]]) -> int:
    removed = 0
    for scope, paths in scope_paths.items():
        if not paths:
            continue
        changed, _backups = shell_config.apply_changes_tracked(
            {}, set(paths), monitor=scope or None, restart=False
        )
        if changed:
            removed += len(paths)
    if removed:
        restart_caelestia()
    return removed
