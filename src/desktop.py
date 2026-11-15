"""Desktop entry helpers and AppImage integration.

Used by the keybind action picker and the Applications page.  AppImage entries
are written to ``~/.local/share/applications`` with a marker so the app can
manage only the entries it created.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from src import backup

APP_DIRS = [
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]
USER_APP_DIR = APP_DIRS[0]
APPIMAGE_DIR = Path.home() / "Applications"
MANAGED_KEY = "X-Caelestia-Settings-Managed"
MANAGED_VALUE = "true"


def _parse_desktop(path: Path) -> dict | None:
    data: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            in_entry = False
            for line in handle:
                line = line.strip()
                if line == "[Desktop Entry]":
                    in_entry = True
                    continue
                if line.startswith("[") and line != "[Desktop Entry]":
                    in_entry = False
                    continue
                if not in_entry or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if "[" not in key:
                    data[key] = value.strip()
    except OSError:
        return None

    if data.get("Type") != "Application":
        return None
    if data.get("NoDisplay", "false").lower() == "true":
        return None
    if data.get("Hidden", "false").lower() == "true":
        return None

    exec_value = data.get("Exec", "")
    wm_class = data.get("StartupWMClass", "")
    if not wm_class and exec_value:
        binary = exec_value.split()[0].strip("\"'")
        wm_class = Path(binary).name
    desktop_id = path.name[:-8] if path.name.endswith(".desktop") else path.stem

    return {
        "name": data.get("Name", path.stem),
        "comment": data.get("Comment", ""),
        "icon": data.get("Icon", "application-x-executable"),
        "exec": exec_value,
        "desktop_id": desktop_id,
        "path": str(path),
        "terminal": data.get("Terminal", "false").lower() == "true",
        "categories": data.get("Categories", ""),
        "wm_class": wm_class,
        "managed": data.get(MANAGED_KEY, "").lower() == MANAGED_VALUE,
        "appimage": data.get("X-Caelestia-AppImage", ""),
    }


def scan_desktop_files() -> list[dict]:
    entries: dict[str, dict] = {}
    for directory in APP_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.desktop")):
            entry = _parse_desktop(path)
            if entry is not None:
                entries.setdefault(entry["desktop_id"], entry)
    return sorted(entries.values(), key=lambda item: item["name"].lower())


def managed_entries() -> list[dict]:
    if not USER_APP_DIR.exists():
        return []
    result = []
    for path in sorted(USER_APP_DIR.glob("*.desktop")):
        entry = _parse_desktop(path)
        if entry is not None and entry["managed"]:
            result.append(entry)
    return result


def launch_command(entry: dict) -> str:
    """Command used by a keybind to launch a desktop entry."""

    return f"gtk-launch {entry['desktop_id']}"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "application"


def _quote_exec(path: Path) -> str:
    value = str(path)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_desktop_entry(
    *,
    name: str,
    exec_path: Path,
    icon: str = "",
    categories: str = "Utility;",
    terminal: bool = False,
    extract_and_run: bool = False,
    appimage_path: Path | None = None,
) -> str:
    exec_line = _quote_exec(exec_path)
    if extract_and_run:
        exec_line += " --appimage-extract-and-run"
    exec_line += " %U"
    icon_value = icon or "application-x-executable"
    categories_value = categories.strip() or "Utility;"
    if not categories_value.endswith(";"):
        categories_value += ";"

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={exec_line}",
        f"Icon={icon_value}",
        f"Terminal={'true' if terminal else 'false'}",
        f"Categories={categories_value}",
        "Comment=Added by Caelestia Settings",
        f"{MANAGED_KEY}={MANAGED_VALUE}",
    ]
    if appimage_path is not None:
        lines.append(f"X-Caelestia-AppImage={appimage_path}")
    return "\n".join(lines) + "\n"


def _validate(path: Path) -> str:
    if shutil.which("desktop-file-validate") is None:
        return ""
    try:
        result = subprocess.run(
            ["desktop-file-validate", str(path)],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() or result.stderr.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def update_database() -> None:
    if shutil.which("update-desktop-database") is None:
        return
    try:
        subprocess.run(
            ["update-desktop-database", str(USER_APP_DIR)],
            capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def install_appimage(
    source: Path,
    *,
    name: str,
    icon: str = "",
    categories: str = "Utility;",
    terminal: bool = False,
    copy_to_applications: bool = True,
    extract_and_run: bool = False,
) -> tuple[Path, str]:
    """Install an AppImage desktop entry. Returns ``(desktop_path, validation)``."""

    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)

    executable = source
    if copy_to_applications:
        APPIMAGE_DIR.mkdir(parents=True, exist_ok=True)
        destination = APPIMAGE_DIR / source.name
        if destination != source:
            shutil.copy2(source, destination)
        executable = destination

    try:
        mode = executable.stat().st_mode
        executable.chmod(mode | 0o111)
    except OSError:
        pass

    USER_APP_DIR.mkdir(parents=True, exist_ok=True)
    desktop_path = USER_APP_DIR / f"caelestia-appimage-{_slug(name)}.desktop"
    content = build_desktop_entry(
        name=name.strip() or source.stem,
        exec_path=executable,
        icon=icon,
        categories=categories,
        terminal=terminal,
        extract_and_run=extract_and_run,
        appimage_path=executable,
    )
    backup.atomic_write_text(desktop_path, content)
    errors = _validate(desktop_path)
    update_database()
    return desktop_path, errors


def remove_entry(entry: dict, *, delete_appimage: bool = False) -> bool:
    path = Path(entry.get("path", ""))
    if not path.exists():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    appimage = entry.get("appimage")
    if delete_appimage and appimage:
        appimage_path = Path(appimage)
        try:
            if appimage_path.is_relative_to(APPIMAGE_DIR):
                appimage_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    update_database()
    return True


def ensure_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass
