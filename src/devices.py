"""Per-device input configuration for Hyprland.

Hyprland 0.55+ exposes per-device settings through ``hl.device({ ... })``.  The
app writes overrides for the devices the user changes into a managed block in
``hypr-user.lua``; everything else keeps following the global input defaults.

This module is GTK-free so the parsers and the generated Lua can be unit-tested.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from src import lua
from src.config import BLOCK_INPUT_DEVICES, read_text

# (key, label, kind, min, max, step, hyprland option, enum values)
Field = tuple[str, str, str, float, float, float, str, tuple[str, ...]]

FIELDS: dict[str, list[Field]] = {
    "keyboard": [
        ("enabled", "Enabled", "bool", 0, 0, 0, "input:enabled", ()),
        ("kb_layout", "Keyboard layout", "str", 0, 0, 0, "input:kb_layout", ()),
        ("kb_variant", "Layout variant", "str", 0, 0, 0, "input:kb_variant", ()),
        ("kb_options", "Layout options", "str", 0, 0, 0, "input:kb_options", ()),
        ("kb_model", "Keyboard model", "str", 0, 0, 0, "input:kb_model", ()),
        ("repeat_rate", "Repeat rate", "int", 10, 100, 1, "input:repeat_rate", ()),
        ("repeat_delay", "Repeat delay", "int", 100, 1000, 10, "input:repeat_delay", ()),
        ("numlock_by_default", "NumLock on startup", "bool", 0, 0, 0, "input:numlock_by_default", ()),
        ("resolve_binds_by_sym", "Resolve binds by symbol", "bool", 0, 0, 0, "input:resolve_binds_by_sym", ()),
        ("keybinds", "Enable keybinds", "bool", 0, 0, 0, "input:keybinds", ()),
    ],
    "pointer": [
        ("enabled", "Enabled", "bool", 0, 0, 0, "input:enabled", ()),
        ("sensitivity", "Sensitivity", "float", -1.0, 1.0, 0.05, "input:sensitivity", ()),
        ("accel_profile", "Acceleration profile", "enum", 0, 0, 0, "input:accel_profile", ("adaptive", "flat")),
        ("natural_scroll", "Natural scrolling", "bool", 0, 0, 0, "input:natural_scroll", ()),
        ("scroll_factor", "Scroll factor", "float", 0.1, 3.0, 0.05, "input:scroll_factor", ()),
        ("left_handed", "Left-handed", "bool", 0, 0, 0, "input:left_handed", ()),
        ("middle_button_emulation", "Middle button emulation", "bool", 0, 0, 0, "input:middle_button_emulation", ()),
        ("scroll_method", "Scroll method", "enum", 0, 0, 0, "input:scroll_method", ("on_button_down", "on_button_up", "two_finger", "edge", "drag", "none")),
        ("clickfinger_behavior", "Clickfinger behaviour", "bool", 0, 0, 0, "input:clickfinger_behavior", ()),
    ],
    "touchpad": [
        ("enabled", "Enabled", "bool", 0, 0, 0, "input:enabled", ()),
        ("natural_scroll", "Natural scrolling", "bool", 0, 0, 0, "input:natural_scroll", ()),
        ("tap_to_click", "Tap to click", "bool", 0, 0, 0, "input:tap-to-click", ()),
        ("tap_and_drag", "Tap and drag", "bool", 0, 0, 0, "input:tap-and-drag", ()),
        ("tap_button_map", "Tap button map", "enum", 0, 0, 0, "input:tap_button_map", ("lrm", "lmr")),
        ("disable_while_typing", "Disable while typing", "bool", 0, 0, 0, "input:disable_while_typing", ()),
        ("scroll_factor", "Scroll factor", "float", 0.1, 3.0, 0.05, "input:scroll_factor", ()),
        ("left_handed", "Left-handed", "bool", 0, 0, 0, "input:left_handed", ()),
        ("drag_lock", "Drag lock", "bool", 0, 0, 0, "input:drag_lock", ()),
        ("clickfinger_behavior", "Clickfinger behaviour", "bool", 0, 0, 0, "input:clickfinger_behavior", ()),
    ],
    "touch": [
        ("enabled", "Enabled", "bool", 0, 0, 0, "input:enabled", ()),
        ("transform", "Transform", "int", 0, 7, 1, "input:transform", ()),
        ("left_handed", "Left-handed", "bool", 0, 0, 0, "input:left_handed", ()),
    ],
    "tablet": [
        ("enabled", "Enabled", "bool", 0, 0, 0, "input:enabled", ()),
        ("transform", "Transform", "int", 0, 7, 1, "input:transform", ()),
        ("left_handed", "Left-handed", "bool", 0, 0, 0, "input:left_handed", ()),
    ],
}


SYSTEM_DEVICE_PATTERNS = (
    "video-bus",
    "power-button",
    "sleep-button",
    "intel-hid",
    "dell-",
    "rustdesk",
    "uinput",
    "fake",
    "consumer-control",
    "system-control",
)


def is_system_device(name: str) -> bool:
    lowered = name.lower()
    return any(pattern in lowered for pattern in SYSTEM_DEVICE_PATTERNS)


@dataclass
class Device:
    name: str
    kind: str
    address: str = ""
    description: str = ""


def parse_devices(data: dict) -> list[Device]:
    devices: list[Device] = []
    seen: set[str] = set()

    for section, kind in (
        ("keyboards", "keyboard"),
        ("mice", "pointer"),
        ("touch", "touch"),
        ("tablets", "tablet"),
    ):
        for entry in data.get(section, []):
            name = str(entry.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            actual_kind = "touchpad" if kind == "pointer" and "touchpad" in name.lower() else kind
            devices.append(
                Device(
                    name=name,
                    kind=actual_kind,
                    address=str(entry.get("address", "")),
                    description=str(entry.get("description", "")),
                )
            )
    return devices


def list_devices() -> list[Device]:
    try:
        result = subprocess.run(
            ["hyprctl", "devices", "-j"], capture_output=True, text=True, timeout=3
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    return parse_devices(data)


def parse_overrides(text: str) -> dict[str, dict]:
    body = lua.strip_managed_block(text, BLOCK_INPUT_DEVICES)
    if not body:
        return {}
    overrides: dict[str, dict] = {}
    for call in lua.iter_calls(body, {"hl.device"}):
        table = call.table if isinstance(call.table, dict) else None
        if not table:
            continue
        name = str(table.get("name", "")).strip()
        if name:
            overrides[name] = table
    return overrides


def build_body(overrides: dict[str, dict]) -> str:
    blocks = []
    for name in sorted(overrides):
        fields = {"name": name, **{k: v for k, v in overrides[name].items() if k != "name"}}
        blocks.append(f"hl.device({lua.format_value(fields)})")
    return "\n\n".join(blocks)


def write_overrides(text: str, overrides: dict[str, dict]) -> str:
    body = build_body(overrides)
    if body:
        return lua.replace_managed_block(text, BLOCK_INPUT_DEVICES, body)
    return lua.remove_managed_block(text, BLOCK_INPUT_DEVICES)


def _getoption(name: str) -> str | None:
    try:
        result = subprocess.run(
            ["hyprctl", "getoption", name], capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    first = result.stdout.splitlines()[0].strip() if result.stdout else ""
    if ":" in first:
        return first.split(":", 1)[1].strip()
    return first or None


def _convert(raw: str | None, kind: str):
    if raw is None:
        return None
    raw = raw.strip()
    if kind == "bool":
        return raw.lower() in ("true", "1", "yes", "on")
    if kind == "int":
        try:
            return int(float(raw))
        except ValueError:
            return None
    if kind == "float":
        try:
            return float(raw)
        except ValueError:
            return None
    return raw


def global_defaults() -> dict[str, object]:
    defaults: dict[str, object] = {}
    for fields in FIELDS.values():
        for key, _label, kind, _min, _max, _step, option, _enum in fields:
            if key in defaults:
                continue
            value = _convert(_getoption(option), kind)
            if value is not None and value != "":
                defaults[key] = value
    return defaults


def default_for(key: str, kind: str):
    return {
        "enabled": True,
        "sensitivity": 0.0,
        "accel_profile": "adaptive",
        "natural_scroll": False,
        "scroll_factor": 1.0,
        "left_handed": False,
        "middle_button_emulation": False,
        "scroll_method": "",
        "clickfinger_behavior": False,
        "tap_to_click": False,
        "tap_and_drag": True,
        "tap_button_map": "lrm",
        "disable_while_typing": True,
        "drag_lock": False,
        "transform": 0,
        "kb_layout": "us",
        "kb_variant": "",
        "kb_options": "",
        "kb_model": "",
        "repeat_rate": 40,
        "repeat_delay": 250,
        "numlock_by_default": False,
        "resolve_binds_by_sym": False,
        "keybinds": True,
    }.get(key, "")


def load_overrides() -> dict[str, dict]:
    from src.config import HYPR_USER_LUA

    return parse_overrides(read_text(HYPR_USER_LUA))
