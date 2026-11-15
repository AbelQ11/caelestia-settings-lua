"""Keybind editor.

Three sources are shown separately because Caelestia generates its binds from
``variables.lua`` (``kb*`` keys):

* **Caelestia shortcuts** — edit the ``kb*`` variables.  User overrides are
  stored in ``hypr-vars.lua`` and merged by Caelestia's loader, so dotfiles
  updates never overwrite them.
* **Custom shortcuts** — the user's own ``config.binds`` table and the
  ``hl.bind(...)`` lines in the managed block of ``hypr-user.lua``.
* **Active binds** — the resolved list reported by ``hyprctl binds -j``
  (read-only).

Every write creates a timestamped backup and reloads Hyprland.
"""

from __future__ import annotations

import json
import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, lua
from src.action_menu import ActionMenuButton
from src.shortcut import ShortcutCaptureDialog
from src.config import (
    BLOCK_KEYBINDS,
    HYPR_DEFAULT_KEYBINDS_LUA,
    HYPR_USER_LUA,
    HYPR_VARIABLES_LUA,
    HYPR_VARS_LUA,
    read_text,
)
from src.lang import t

# Compatibility aliases
KEYBINDS_LUA = HYPR_DEFAULT_KEYBINDS_LUA
VARIABLES_LUA = HYPR_VARIABLES_LUA
KEYBINDS_CONF = KEYBINDS_LUA
VARIABLES_CONF = VARIABLES_LUA

BIND_TYPE_LABELS = {
    "bind": "Normal",
    "binde": "Repeat",
    "bindl": "Locked",
    "bindle": "Locked + repeat",
    "bindr": "Release",
    "bindm": "Mouse",
    "bindi": "Ignore inhibit",
    "bindin": "Ignore + non-consuming",
}

DISPATCHERS = sorted([
    "exec", "killactive", "closewindow", "workspace", "movetoworkspace",
    "movetoworkspacesilent", "togglefloating", "fullscreen", "fakefullscreen",
    "dpms", "pin", "movefocus", "movewindow", "resizewindow", "resizeactive",
    "cyclenext", "swapnext", "focuswindow", "focusmonitor", "splitratio",
    "toggleopaque", "movecursortocorner", "workspaceopt", "exit",
    "forcerendererreload", "movecurrentworkspacetomonitor",
    "focusworkspaceoncurrentmonitor", "togglespecialworkspace",
    "swapactiveworkspaces", "bringactivetotop", "alterzorder", "togglesplit",
    "layoutmsg", "global", "submap", "moveoutofgroup", "changegroupactive",
    "togglegroup", "lockactivegroup", "centerwindow",
])

MOD_LABELS = [
    ("CTRL", "CTRL"),
    ("ALT", "ALT"),
    ("SHIFT", "SHIFT"),
    ("SUPER", "SUPER"),
]


# ── Generic helpers ──────────────────────────────────────────────────────────


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            quote = c
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _read_variables() -> dict:
    result: dict = {}
    for path in (VARIABLES_LUA, HYPR_VARS_LUA):
        if path.exists():
            result.update(lua.read_table_values(read_text(path)))
    return result


def _write_vars(updates: dict) -> None:
    text = read_text(HYPR_VARS_LUA)
    if not text.strip():
        text = "return {\n}\n"
    apply.write_and_reload(HYPR_VARS_LUA, lua.set_table_values(text, updates))


def _split_combo(combo: str) -> tuple[str, str]:
    combo = combo.strip()
    if " + " in combo:
        mod, key = combo.rsplit(" + ", 1)
        return mod.strip(), key.strip()
    if "," in combo:
        mod, key = combo.rsplit(",", 1)
        return mod.strip(), key.strip()
    return "", combo


def _humanize(name: str) -> str:
    name = name[2:] if name.startswith("kb") else name
    words = re.sub(r"([A-Z])", r" \1", name).strip()
    replacements = {
        "Ws": "Workspace", "Win": "Window", "Prev": "Previous", "Next": "Next",
        "Toggle": "Toggle", "Special": "Special", "Notifs": "Notifications",
        "Clipboard": "Clipboard", "Screenshot": "Screenshot",
        "Terminal": "Terminal", "Browser": "Browser", "Editor": "Editor",
        "File Explorer": "File explorer", "Media": "Media", "Volume": "Volume",
        "Lock": "Lock", "Sleep": "Sleep", "Session": "Session",
    }
    for old, new in replacements.items():
        words = words.replace(old, new)
    return words or name


# ── Caelestia variables (`kb*`) ──────────────────────────────────────────────


def parse_caelestia_shortcuts() -> list[dict]:
    variables = _read_variables()
    defaults = lua.read_table_values(read_text(VARIABLES_LUA)) if VARIABLES_LUA.exists() else {}
    overrides = lua.read_table_values(read_text(HYPR_VARS_LUA)) if HYPR_VARS_LUA.exists() else {}
    shortcuts: list[dict] = []
    for key in sorted(variables):
        if not key.startswith("kb"):
            continue
        value = variables[key]
        if not isinstance(value, (str, list)):
            continue
        shortcuts.append(
            {
                "key": key,
                "title": _humanize(key),
                "value": value,
                "is_list": isinstance(value, list),
                "default": defaults.get(key),
                "overridden": key in overrides,
            }
        )
    return shortcuts


def _format_shortcut(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


# ── Custom binds (`config.binds` + managed `hl.bind`) ───────────────────────


def _parse_action(action: str) -> tuple[str, str]:
    action = action.strip()
    patterns = [
        (r"hl\.dsp\.exec_cmd\s*\(\s*(['\"])(.*?)\1\s*\)", "exec"),
        (r"hl\.dsp\.global\s*\(\s*(['\"])(.*?)\1\s*\)", "global"),
    ]
    for pattern, dispatcher in patterns:
        match = re.search(pattern, action, re.S)
        if match:
            return dispatcher, match.group(2)
    if "hl.dsp.focus" in action:
        match = re.search(r"workspace\s*=\s*(['\"]?)([^,'\"}]+)\1", action)
        return "workspace", match.group(2).strip() if match else ""
    if "hl.dsp.window.move" in action:
        match = re.search(r"workspace\s*=\s*(['\"]?)([^,'\"}]+)\1", action)
        return "movetoworkspace", match.group(2).strip() if match else ""
    if "hl.dsp.exec_raw" in action:
        match = re.search(r"hl\.dsp\.exec_raw\s*\(\s*(['\"])(.*?)\1\s*\)", action, re.S)
        raw = match.group(2) if match else ""
        dispatcher, _, argument = raw.partition(" ")
        return dispatcher.strip(), argument.strip()
    if action.startswith("function"):
        return "function", action
    return _unquote(action), ""


def _flags_to_type(flags: dict) -> str:
    repeating = bool(flags.get("repeating"))
    locked = bool(flags.get("locked"))
    release = bool(flags.get("release"))
    mouse = bool(flags.get("mouse"))
    if mouse:
        return "bindm"
    if locked and repeating:
        return "bindle"
    if repeating:
        return "binde"
    if locked:
        return "bindl"
    if release:
        return "bindr"
    return "bind"


def _type_to_flags(bind_type: str) -> dict:
    flags: dict = {}
    if bind_type in ("binde", "bindle"):
        flags["repeating"] = True
    if bind_type in ("bindl", "bindle"):
        flags["locked"] = True
    if bind_type == "bindr":
        flags["release"] = True
    if bind_type == "bindm":
        flags["mouse"] = True
    return flags


def _parse_managed_binds(text: str) -> list[dict]:
    body = lua.strip_managed_block(text, BLOCK_KEYBINDS)
    if not body:
        return []
    binds: list[dict] = []
    for call in lua.iter_calls(body, {"hl.bind"}):
        parts = _split_top_level(call.args)
        if not parts:
            continue
        combo = _unquote(parts[0])
        action = parts[1] if len(parts) > 1 else ""
        flags: dict = {}
        if len(parts) > 2 and parts[2].strip().startswith("{"):
            try:
                parsed, _ = lua.parse_table(parts[2], parts[2].find("{"))
                if isinstance(parsed, dict):
                    flags = parsed
            except lua.LuaParseError:
                pass
        dispatcher, argument = _parse_action(action)
        mod, key = _split_combo(combo)
        trailing = body[call.end:].split("\n", 1)[0]
        comment_match = re.search(r"--\s*(.*)", trailing)
        binds.append(
            {
                "source": "managed",
                "index": len(binds),
                "modifier_raw": mod,
                "modifier_resolved": mod,
                "key_raw": key,
                "key_resolved": key,
                "dispatcher": dispatcher,
                "argument": argument,
                "bind_type": _flags_to_type(flags),
                "comment": comment_match.group(1).strip() if comment_match else "",
                "raw": body[call.start:call.end],
            }
        )
    return binds


def _parse_config_binds(text: str) -> list[dict]:
    match = re.search(r"config\.binds\s*=\s*", text)
    if not match:
        return []
    start = match.end()
    brace = text.find("{", start)
    if brace < 0:
        return []
    try:
        table, _ = lua.parse_table(text, brace)
    except lua.LuaParseError:
        return []
    if not isinstance(table, list):
        return []
    binds: list[dict] = []
    for index, entry in enumerate(table):
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        mod = str(entry[0])
        key = str(entry[1])
        dispatcher = str(entry[2])
        argument = str(entry[3]) if len(entry) > 3 else ""
        binds.append(
            {
                "source": "config",
                "index": index,
                "modifier_raw": mod,
                "modifier_resolved": mod,
                "key_raw": key,
                "key_resolved": key,
                "dispatcher": dispatcher,
                "argument": argument,
                "bind_type": "bind",
                "comment": str(entry[4]) if len(entry) > 4 else "",
                "raw": lua.format_value(entry),
            }
        )
    return binds


def parse_keybinds() -> list[dict]:
    """Custom binds only (kept as the public helper other modules import)."""

    text = read_text(HYPR_USER_LUA)
    return _parse_config_binds(text) + _parse_managed_binds(text)


def _build_line(data: dict) -> str:
    mod = data.get("modifier", "")
    key = data.get("key", "")
    combo = f"{mod} + {key}" if mod else key
    dispatcher = data.get("dispatcher", "exec")
    argument = data.get("argument", "")
    comment = f"  -- {data['comment']}" if data.get("comment") else ""

    if dispatcher == "exec":
        action = f"hl.dsp.exec_cmd({lua.lua_string(argument)})"
    elif dispatcher == "global":
        action = f"hl.dsp.global({lua.lua_string(argument)})"
    elif dispatcher == "workspace":
        action = f"hl.dsp.focus({{ workspace = {lua.lua_string(argument)} }})"
    elif dispatcher == "movetoworkspace":
        action = f"hl.dsp.window.move({{ workspace = {lua.lua_string(argument)} }})"
    elif dispatcher == "function":
        action = argument
    else:
        # Generic Hyprland dispatchers are sent through exec_raw so the
        # generated file always uses a real HL.Dispatcher object.
        command = f"{dispatcher} {argument}".strip()
        action = f"hl.dsp.exec_raw({lua.lua_string(command)})"

    flags = _type_to_flags(data.get("bind_type", "bind"))
    flags_str = f", {lua.format_value(flags)}" if flags else ""
    return f"hl.bind({lua.lua_string(combo)}, {action}{flags_str}){comment}"


def _write_managed_binds(binds: list[dict]) -> None:
    text = read_text(HYPR_USER_LUA)
    if not text.strip():
        text = "local config = {}\n\nreturn config\n"
    body_lines = []
    for bind in binds:
        body_lines.append(
            _build_line(
                {
                    "modifier": bind.get("modifier_raw", ""),
                    "key": bind.get("key_raw", ""),
                    "dispatcher": bind.get("dispatcher", "exec"),
                    "argument": bind.get("argument", ""),
                    "bind_type": bind.get("bind_type", "bind"),
                    "comment": bind.get("comment", ""),
                }
            )
        )
    body = "\n".join(body_lines)
    new_text = lua.replace_managed_block(text, BLOCK_KEYBINDS, body) if body else lua.remove_managed_block(text, BLOCK_KEYBINDS)
    apply.write_and_reload(HYPR_USER_LUA, new_text)


def _write_config_binds(binds: list[dict]) -> None:
    text = read_text(HYPR_USER_LUA)
    if not text.strip():
        text = "local config = {}\n\nreturn config\n"

    rows = []
    for bind in binds:
        row = [bind.get("modifier_raw", ""), bind.get("key_raw", ""), bind.get("dispatcher", "exec")]
        argument = bind.get("argument", "")
        if argument:
            row.append(argument)
        rows.append(row)

    match = re.search(r"config\.binds\s*=\s*", text)
    if match:
        brace = text.find("{", match.end())
        if brace >= 0:
            try:
                _old, end = lua.parse_table(text, brace)
                text = text[:brace] + lua.format_value(rows) + text[end:]
            except lua.LuaParseError:
                pass
    else:
        assignment = f"config.binds = {lua.format_value(rows)}\n\n"
        anchor = re.search(r"(?m)^[ \t]*return\s+config\b", text)
        if anchor:
            text = text[: anchor.start()] + assignment + text[anchor.start():]
        else:
            text = text.rstrip() + "\n\n" + assignment
    apply.write_and_reload(HYPR_USER_LUA, text)


def save_bind(data: dict, bind: dict | None = None) -> None:
    if bind and bind.get("source") == "config":
        binds = _parse_config_binds(read_text(HYPR_USER_LUA))
        entry = {
            "modifier_raw": data["modifier"],
            "key_raw": data["key"],
            "dispatcher": data["dispatcher"],
            "argument": data.get("argument", ""),
            "bind_type": data.get("bind_type", "bind"),
            "comment": data.get("comment", ""),
        }
        index = bind.get("index", len(binds))
        if index < len(binds):
            binds[index] = entry
        else:
            binds.append(entry)
        _write_config_binds(binds)
    else:
        binds = _parse_managed_binds(read_text(HYPR_USER_LUA))
        entry = {
            "modifier_raw": data["modifier"],
            "key_raw": data["key"],
            "dispatcher": data["dispatcher"],
            "argument": data.get("argument", ""),
            "bind_type": data.get("bind_type", "bind"),
            "comment": data.get("comment", ""),
        }
        if bind is not None:
            index = bind.get("index", len(binds))
            if index < len(binds):
                binds[index] = entry
            else:
                binds.append(entry)
        else:
            binds.append(entry)
        _write_managed_binds(binds)


def delete_bind(bind: dict) -> None:
    if bind.get("source") == "config":
        binds = _parse_config_binds(read_text(HYPR_USER_LUA))
        index = bind.get("index", -1)
        if 0 <= index < len(binds):
            binds.pop(index)
        _write_config_binds(binds)
    else:
        binds = _parse_managed_binds(read_text(HYPR_USER_LUA))
        index = bind.get("index", -1)
        if 0 <= index < len(binds):
            binds.pop(index)
        _write_managed_binds(binds)


# Legacy API names
def save_keybind(data: dict, line_number: int | None = None, raw_line: str | None = None):
    save_bind(data)


def delete_keybind(line_number: int, raw_line: str | None = None):
    # Legacy callers pass a line number; find the matching managed bind by raw.
    for bind in _parse_managed_binds(read_text(HYPR_USER_LUA)):
        if raw_line is None or bind.get("raw", "").strip() == raw_line.strip():
            delete_bind(bind)
            return


# ── Active binds ─────────────────────────────────────────────────────────────


def _modmask_to_combo(modmask: int) -> str:
    names = []
    if modmask & 1:
        names.append("SHIFT")
    if modmask & 4:
        names.append("CTRL")
    if modmask & 8:
        names.append("ALT")
    if modmask & 64:
        names.append("SUPER")
    return " + ".join(names)


def parse_active_binds() -> list[dict]:
    try:
        result = subprocess.run(
            ["hyprctl", "binds", "-j"], capture_output=True, text=True, timeout=3
        )
        data = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []

    binds = []
    for entry in data:
        dispatcher = str(entry.get("dispatcher", ""))
        match = re.search(r"HL\.Dispatcher\((\w+)\)", dispatcher)
        if match:
            dispatcher = match.group(1)
        combo = _modmask_to_combo(int(entry.get("modmask", 0)))
        key = str(entry.get("key", ""))
        binds.append(
            {
                "combo": f"{combo} + {key}" if combo else key,
                "dispatcher": dispatcher,
                "argument": str(entry.get("arg", "")),
                "flags": ", ".join(
                    name for name in ("locked", "mouse", "release", "repeat")
                    if entry.get(name)
                ),
            }
        )
    binds.sort(key=lambda item: item["combo"].lower())
    return binds


# ── Dialog ───────────────────────────────────────────────────────────────────


class KeybindDialog(Gtk.Dialog):
    def __init__(self, parent, bind: dict | None = None):
        title = t("Edit keybind") if bind else t("New keybind")
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(620, -1)

        self.add_button(t("Cancel"), Gtk.ResponseType.CANCEL)
        save_btn = self.add_button(t("Save"), Gtk.ResponseType.OK)
        save_btn.add_css_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        def label(text, row):
            widget = Gtk.Label(label=text)
            widget.set_halign(Gtk.Align.END)
            widget.add_css_class("dim-label")
            grid.attach(widget, 0, row, 1, 1)

        label(t("Bind type"), 0)
        self._type_combo = Gtk.ComboBoxText()
        self._type_combo.set_hexpand(True)
        for bind_type, description in BIND_TYPE_LABELS.items():
            self._type_combo.append(bind_type, f"{bind_type} — {description}")
        self._type_combo.set_active_id(bind["bind_type"] if bind else "bind")
        grid.attach(self._type_combo, 1, 0, 1, 1)

        label(t("Modifier"), 1)
        self._mod_entry = Gtk.Entry()
        self._mod_entry.set_hexpand(True)
        self._mod_entry.set_placeholder_text("SUPER, CTRL + SHIFT …")
        self._mod_entry.set_text(bind["modifier_raw"] if bind else "SUPER")
        grid.attach(self._mod_entry, 1, 1, 1, 1)

        label(t("Key"), 2)
        self._key_entry = Gtk.Entry()
        self._key_entry.set_hexpand(True)
        self._key_entry.set_placeholder_text("T, Return, F1, mouse:272 …")
        self._key_entry.set_text(bind["key_raw"] if bind else "")
        grid.attach(self._key_entry, 1, 2, 1, 1)

        label(t("Preset action"), 3)
        self._action_btn = ActionMenuButton(self._on_action_selected)
        self._action_btn.set_hexpand(True)
        self._action_btn.set_halign(Gtk.Align.START)
        grid.attach(self._action_btn, 1, 3, 1, 1)

        self._record_btn = Gtk.Button(label=t("Record shortcut…"))
        self._record_btn.connect("clicked", self._on_record_clicked)
        grid.attach(self._record_btn, 1, 4, 1, 1)

        label(t("Dispatcher"), 5)
        self._disp_combo = Gtk.ComboBoxText()
        self._disp_combo.set_hexpand(True)
        for dispatcher in DISPATCHERS:
            self._disp_combo.append(dispatcher, dispatcher)
        self._disp_combo.set_active_id(bind["dispatcher"] if bind else "exec")
        grid.attach(self._disp_combo, 1, 5, 1, 1)

        label(t("Argument"), 6)
        self._arg_entry = Gtk.Entry()
        self._arg_entry.set_hexpand(True)
        self._arg_entry.set_placeholder_text("optional — foot, 1, toggle …")
        self._arg_entry.set_text(bind["argument"] if bind else "")
        grid.attach(self._arg_entry, 1, 6, 1, 1)

        label(t("Comment"), 7)
        self._comment_entry = Gtk.Entry()
        self._comment_entry.set_hexpand(True)
        self._comment_entry.set_placeholder_text("optional")
        self._comment_entry.set_text(bind["comment"] if bind else "")
        grid.attach(self._comment_entry, 1, 7, 1, 1)

        self.get_content_area().append(grid)

    def _on_action_selected(self, action):
        self._disp_combo.set_active_id(action.dispatcher)
        if not self._disp_combo.get_active_id():
            self._disp_combo.append(action.dispatcher, action.dispatcher)
            self._disp_combo.set_active_id(action.dispatcher)
        self._arg_entry.set_text(action.argument)

    def _current_combo(self) -> str:
        mod = self._mod_entry.get_text().strip()
        key = self._key_entry.get_text().strip()
        return f"{mod} + {key}" if mod else key

    def _on_record_clicked(self, _button):
        dialog = ShortcutCaptureDialog(self._apply_combo, initial=self._current_combo())
        dialog.present(self)

    def _apply_combo(self, combo: str):
        if " + " in combo:
            mod, key = combo.rsplit(" + ", 1)
        else:
            mod, key = "", combo
        self._mod_entry.set_text(mod.strip())
        self._key_entry.set_text(key.strip())

    def get_data(self) -> dict:
        return {
            "bind_type": self._type_combo.get_active_id() or "bind",
            "modifier": self._mod_entry.get_text().strip(),
            "key": self._key_entry.get_text().strip(),
            "dispatcher": self._disp_combo.get_active_id() or "exec",
            "argument": self._arg_entry.get_text().strip(),
            "comment": self._comment_entry.get_text().strip(),
        }


# ── Page ─────────────────────────────────────────────────────────────────────


class KeybindsPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._shortcuts: list[dict] = []
        self._custom: list[dict] = []
        self._active: list[dict] = []

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        self.append(notebook)

        notebook.append_page(self._build_shortcuts_tab(), Gtk.Label(label=t("Caelestia shortcuts")))
        notebook.append_page(self._build_custom_tab(), Gtk.Label(label=t("Custom shortcuts")))
        notebook.append_page(self._build_active_tab(), Gtk.Label(label=t("Active binds")))

        self._load()

    # ── Caelestia shortcuts ───────────────────────────────────────────────

    def _build_shortcuts_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        self._shortcut_search = Gtk.SearchEntry()
        self._shortcut_search.set_hexpand(True)
        self._shortcut_search.set_placeholder_text(t("Search shortcuts…"))
        self._shortcut_search.connect("search-changed", lambda _: self._filter_shortcuts())
        bar.append(self._shortcut_search)
        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._load())
        bar.append(reload_btn)
        box.append(bar)

        note = Gtk.Label()
        note.set_markup(
            f"<small>{t('Overrides are written to')} <tt>~/.config/caelestia/hypr-vars.lua</tt>. "
            f"{t('Caelestia variables.lua stays untouched.')}</small>"
        )
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.set_halign(Gtk.Align.START)
        note.add_css_class("dim-label")
        box.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._shortcut_list = Gtk.ListBox()
        self._shortcut_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._shortcut_list.add_css_class("boxed-list")
        self._shortcut_list.set_margin_top(8)
        self._shortcut_list.set_margin_bottom(12)
        self._shortcut_list.set_margin_start(12)
        self._shortcut_list.set_margin_end(12)
        scroller.set_child(self._shortcut_list)
        box.append(scroller)
        return box

    def _filter_shortcuts(self):
        query = self._shortcut_search.get_text().lower()
        while row := self._shortcut_list.get_first_child():
            self._shortcut_list.remove(row)
        for shortcut in self._shortcuts:
            haystack = f"{shortcut['title']} {shortcut['key']} {_format_shortcut(shortcut['value'])}".lower()
            if query and query not in haystack:
                continue
            row = Adw.ActionRow(title=shortcut["title"], subtitle=shortcut["key"])
            entry = Gtk.Entry()
            entry.set_text(_format_shortcut(shortcut["value"]))
            entry.set_width_chars(22)
            entry.set_valign(Gtk.Align.CENTER)
            entry.connect("activate", self._on_shortcut_apply, shortcut, entry)
            row.add_suffix(entry)
            record_btn = Gtk.Button()
            record_btn.set_icon_name("input-keyboard-symbolic")
            record_btn.set_tooltip_text(t("Record a key combination"))
            record_btn.set_valign(Gtk.Align.CENTER)
            record_btn.connect("clicked", lambda _b, item=shortcut, field=entry: self._record_shortcut(item, field))
            row.add_suffix(record_btn)
            apply_btn = Gtk.Button()
            apply_btn.set_icon_name("object-select-symbolic")
            apply_btn.set_tooltip_text(t("Apply"))
            apply_btn.set_valign(Gtk.Align.CENTER)
            apply_btn.connect("clicked", self._on_shortcut_apply, shortcut, entry)
            row.add_suffix(apply_btn)
            if shortcut.get("overridden"):
                reset_btn = Gtk.Button()
                reset_btn.set_icon_name("edit-undo-symbolic")
                reset_btn.set_tooltip_text(t("Remove override"))
                reset_btn.set_valign(Gtk.Align.CENTER)
                reset_btn.connect("clicked", self._on_shortcut_reset, shortcut)
                row.add_suffix(reset_btn)
            self._shortcut_list.append(row)

    def _record_shortcut(self, shortcut: dict, entry: Gtk.Entry):
        dialog = ShortcutCaptureDialog(
            lambda combo: self._apply_recorded_shortcut(shortcut, entry, combo),
            initial="" if shortcut.get("is_list") else entry.get_text().strip(),
        )
        dialog.present(self.main_window)

    def _apply_recorded_shortcut(self, shortcut: dict, entry: Gtk.Entry, combo: str):
        if shortcut.get("is_list"):
            parts = [part.strip() for part in entry.get_text().split(",") if part.strip()]
            if combo not in parts:
                parts.append(combo)
            entry.set_text(", ".join(parts))
        else:
            entry.set_text(combo)

    def _on_shortcut_apply(self, _widget, shortcut: dict, entry: Gtk.Entry):
        parts = [part.strip() for part in entry.get_text().split(",") if part.strip()]
        if not parts:
            return
        value = parts[0] if len(parts) == 1 and not shortcut["is_list"] else parts
        try:
            _write_vars({shortcut["key"]: value})
            self._load()
            self.main_window.add_toast(
                Adw.Toast.new(f"{shortcut['title']}: {_format_shortcut(value)}")
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # pragma: no cover
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not save shortcut')}: {exc}"))

    def _on_shortcut_reset(self, _button, shortcut: dict):
        try:
            text = read_text(HYPR_VARS_LUA)
            new_text = lua.remove_table_values(text, [shortcut["key"]])
            if new_text != text:
                apply.write_and_reload(HYPR_VARS_LUA, new_text)
            self._load()
            self.main_window.add_toast(Adw.Toast.new(t("Override removed.")))
        except Exception as exc:  # pragma: no cover
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not reset shortcut')}: {exc}"))

    # ── Custom shortcuts ──────────────────────────────────────────────────

    def _build_custom_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        self._custom_search = Gtk.SearchEntry()
        self._custom_search.set_hexpand(True)
        self._custom_search.set_placeholder_text(t("Search custom shortcuts…"))
        self._custom_search.connect("search-changed", lambda _: self._filter_custom())
        bar.append(self._custom_search)
        add_btn = Gtk.Button(label=t("+ New"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add)
        bar.append(add_btn)
        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._load())
        bar.append(reload_btn)
        box.append(bar)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._custom_list = Gtk.ListBox()
        self._custom_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._custom_list.add_css_class("boxed-list")
        self._custom_list.set_margin_top(8)
        self._custom_list.set_margin_bottom(12)
        self._custom_list.set_margin_start(12)
        self._custom_list.set_margin_end(12)
        scroller.set_child(self._custom_list)
        box.append(scroller)
        return box

    def _filter_custom(self):
        query = self._custom_search.get_text().lower()
        while row := self._custom_list.get_first_child():
            self._custom_list.remove(row)
        for bind in self._custom:
            haystack = " ".join(
                str(bind.get(key, "")) for key in (
                    "modifier_resolved", "key_resolved", "dispatcher", "argument", "comment"
                )
            ).lower()
            if query and query not in haystack:
                continue
            mod = bind["modifier_resolved"] or bind["modifier_raw"]
            key = bind["key_resolved"] or bind["key_raw"]
            row = Adw.ActionRow(
                title=f"{mod} + {key}" if mod else key,
                subtitle=f"{bind['dispatcher']}  {bind['argument']}".strip(),
            )
            source = Gtk.Label(label=t("config.binds") if bind.get("source") == "config" else t("managed"))
            source.add_css_class("caption")
            source.add_css_class("dim-label")
            source.set_valign(Gtk.Align.CENTER)
            row.add_suffix(source)

            edit_btn = Gtk.Button()
            edit_btn.set_icon_name("document-edit-symbolic")
            edit_btn.set_valign(Gtk.Align.CENTER)
            edit_btn.set_tooltip_text(t("Edit"))
            edit_btn.connect("clicked", lambda _, item=bind: self._on_edit(item))
            row.add_suffix(edit_btn)

            delete_btn = Gtk.Button()
            delete_btn.set_icon_name("user-trash-symbolic")
            delete_btn.add_css_class("destructive-action")
            delete_btn.set_valign(Gtk.Align.CENTER)
            delete_btn.set_tooltip_text(t("Delete"))
            delete_btn.connect("clicked", lambda _, item=bind: self._on_delete(item))
            row.add_suffix(delete_btn)
            self._custom_list.append(row)

    def _on_add(self, _button):
        dialog = KeybindDialog(self.main_window)
        dialog.connect("response", self._on_dialog_response, dialog, None)
        dialog.present()

    def _on_edit(self, bind: dict):
        dialog = KeybindDialog(self.main_window, bind)
        dialog.connect("response", self._on_dialog_response, dialog, bind)
        dialog.present()

    def _on_dialog_response(self, dialog, response, dialog_obj, bind):
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        data = dialog_obj.get_data()
        if not data["key"] or not data["dispatcher"]:
            self.main_window.add_toast(Adw.Toast.new(t("Key and dispatcher are required.")))
            return
        try:
            save_bind(data, bind)
            self._load()
            self.main_window.add_toast(
                Adw.Toast.new(t("Keybind saved and Hyprland reloaded."))
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # pragma: no cover
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not save keybind')}: {exc}"))

    def _on_delete(self, bind: dict):
        dialog = Adw.MessageDialog(
            heading=t("Delete keybind?"),
            body=f"{bind['modifier_resolved']} + {bind['key_resolved']} → {bind['dispatcher']} {bind['argument']}",
        )
        dialog.set_transient_for(self.main_window)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("delete", t("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response == "delete":
                try:
                    delete_bind(bind)
                    self._load()
                    self.main_window.add_toast(Adw.Toast.new(t("Keybind deleted.")))
                except Exception as exc:  # pragma: no cover
                    self.main_window.add_toast(
                        Adw.Toast.new(f"{t('Could not delete keybind')}: {exc}")
                    )

        dialog.connect("response", on_response)
        dialog.present()

    # ── Active binds ──────────────────────────────────────────────────────

    def _build_active_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        self._active_search = Gtk.SearchEntry()
        self._active_search.set_hexpand(True)
        self._active_search.set_placeholder_text(t("Search active binds…"))
        self._active_search.connect("search-changed", lambda _: self._filter_active())
        bar.append(self._active_search)
        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._load())
        bar.append(reload_btn)
        box.append(bar)

        note = Gtk.Label(label=t("Resolved from Hyprland (hyprctl binds). Read-only."))
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.set_halign(Gtk.Align.START)
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        box.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._active_list = Gtk.ListBox()
        self._active_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._active_list.add_css_class("boxed-list")
        self._active_list.set_margin_top(8)
        self._active_list.set_margin_bottom(12)
        self._active_list.set_margin_start(12)
        self._active_list.set_margin_end(12)
        scroller.set_child(self._active_list)
        box.append(scroller)
        return box

    def _filter_active(self):
        query = self._active_search.get_text().lower()
        while row := self._active_list.get_first_child():
            self._active_list.remove(row)
        for bind in self._active:
            haystack = f"{bind['combo']} {bind['dispatcher']} {bind['argument']}".lower()
            if query and query not in haystack:
                continue
            row = Adw.ActionRow(title=bind["combo"], subtitle=f"{bind['dispatcher']}  {bind['argument']}".strip())
            if bind["flags"]:
                flag_label = Gtk.Label(label=bind["flags"])
                flag_label.add_css_class("caption")
                flag_label.add_css_class("dim-label")
                flag_label.set_valign(Gtk.Align.CENTER)
                row.add_suffix(flag_label)
            self._active_list.append(row)

    # ── Data ──────────────────────────────────────────────────────────────

    def _load(self):
        self._shortcuts = parse_caelestia_shortcuts()
        self._custom = parse_keybinds()
        self._active = parse_active_binds()
        self._filter_shortcuts()
        self._filter_custom()
        self._filter_active()
