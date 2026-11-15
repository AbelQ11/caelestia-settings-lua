"""Kanshi integration.

Kanshi applies output profiles independently of Hyprland.  If it is running,
it will override monitor scale/position/mode on every output event, so the
Monitor page must keep ``~/.config/kanshi/config`` in sync.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from src import backup

CONFIG_PATH = Path.home() / ".config" / "kanshi" / "config"
OUTPUT_RE = re.compile(r'^(?P<indent>\s*)output\s+"(?P<name>[^"]+)"\s*(?P<rest>.*)$')


def available() -> bool:
    return CONFIG_PATH.exists()


def is_running() -> bool:
    try:
        return (
            subprocess.run(
                ["pgrep", "-x", "kanshi"], capture_output=True, timeout=2, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def _hz(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _mode(model) -> str:
    resolution = str(getattr(model, "resolution", "") or "")
    hz = _hz(getattr(model, "hz", ""))
    if resolution and hz:
        return f"{resolution}@{hz}Hz"
    return resolution or "preferred"


def _number(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "1"
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _extras(rest: str) -> list[str]:
    text = re.sub(r"(?<!\S)(enable|disable)(?!\S)", "", rest)
    text = re.sub(r"(?<!\S)mode\s+\S+", "", text)
    text = re.sub(r"(?<!\S)position\s+\S+", "", text)
    text = re.sub(r"(?<!\S)scale\s+\S+", "", text)
    return text.split()


def _output_line(indent: str, model, extras: list[str]) -> str:
    name = str(getattr(model, "name", ""))
    disabled = bool(getattr(model, "disabled", False))
    parts = [f'output "{name}"', "disable" if disabled else "enable"]
    if not disabled:
        parts += [
            "mode",
            _mode(model),
            "position",
            f"{int(float(getattr(model, 'x', 0)))},{int(float(getattr(model, 'y', 0)))}",
            "scale",
            _number(getattr(model, "scale", 1)),
        ]
    parts.extend(extras)
    return f"{indent}{' '.join(parts)}"


def update_text(text: str, models) -> str:
    by_name = {str(getattr(model, "name", "")): model for model in models}
    lines = []
    for line in text.splitlines():
        match = OUTPUT_RE.match(line)
        if not match:
            lines.append(line)
            continue
        model = by_name.get(match.group("name"))
        if model is None:
            lines.append(line)
            continue
        # Preserve unknown options for this output.
        extras = _extras(match.group("rest"))
        lines.append(_output_line(match.group("indent"), model, extras))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def update_config(models) -> bool:
    if not CONFIG_PATH.exists():
        return False
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = update_text(text, models)
    if new_text == text:
        return False
    backup.atomic_write_text(CONFIG_PATH, new_text)
    return True


def reload() -> bool:
    if shutil.which("kanshictl"):
        try:
            return (
                subprocess.run(
                    ["kanshictl", "reload"], capture_output=True, timeout=10, check=False
                ).returncode
                == 0
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return False
