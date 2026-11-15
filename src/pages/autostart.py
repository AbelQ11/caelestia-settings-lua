"""Autostart entries for Caelestia/Hyprland.

Commands are written to a managed ``hl.on("hyprland.start", ...)`` block in
``hypr-user.lua``, so existing user startup handlers are left untouched.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, lua
from src.config import BLOCK_AUTOSTART, HYPR_USER_LUA, read_text
from src.lang import t


def _command_from_args(args: str) -> str:
    stripped = args.strip()
    if stripped and stripped[0] in "\"'":
        try:
            return lua._parse_string(stripped, 0)[0]
        except lua.LuaParseError:
            pass
    return stripped


def parse_commands(text: str) -> list[str]:
    body = lua.strip_managed_block(text, BLOCK_AUTOSTART)
    if not body:
        return []
    commands = []
    for call in lua.iter_calls(body, {"hl.exec_cmd"}):
        command = _command_from_args(call.args).strip()
        if command:
            commands.append(command)
    return commands


def build_block(commands: list[str]) -> str:
    lines = ['hl.on("hyprland.start", function()']
    for command in commands:
        lines.append(f"    hl.exec_cmd({lua.lua_string(command)})")
    lines.append("end)")
    return "\n".join(lines)


def write_commands(text: str, commands: list[str]) -> str:
    if commands:
        return lua.replace_managed_block(text, BLOCK_AUTOSTART, build_block(commands))
    return lua.remove_managed_block(text, BLOCK_AUTOSTART)


class AutostartPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._commands: list[str] = []

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)

        title = Gtk.Label(label=t("Autostart"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        bar.append(title)

        add_btn = Gtk.Button(label=t("+ Add"))
        add_btn.connect("clicked", lambda _b: self._edit(None))
        bar.append(add_btn)

        self.apply_btn = Gtk.Button(label=t("Apply"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.set_sensitive(False)
        self.apply_btn.connect("clicked", self._on_apply)
        bar.append(self.apply_btn)

        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _b: self._load())
        bar.append(reload_btn)
        self.append(bar)

        note = Gtk.Label(
            label=t(
                "Commands run at Hyprland startup. Existing startup handlers in "
                "hypr-user.lua are not modified."
            )
        )
        note.set_halign(Gtk.Align.START)
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        self.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_margin_top(8)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._load()

    # ── Data ──────────────────────────────────────────────────────────────

    def _load(self):
        self._commands = parse_commands(read_text(HYPR_USER_LUA))
        self.apply_btn.set_sensitive(False)
        self._render()

    def _render(self):
        while child := self.content.get_first_child():
            self.content.remove(child)

        group = Adw.PreferencesGroup(
            title=t("Startup commands"),
            description=t("Order is top to bottom."),
        )
        self.content.append(group)

        if not self._commands:
            group.add(
                Adw.ActionRow(
                    title=t("No autostart commands"),
                    subtitle=t("Use + Add to create one."),
                )
            )
            return

        for index, command in enumerate(self._commands):
            row = Adw.ActionRow(title=command)
            icon = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
            icon.set_valign(Gtk.Align.CENTER)
            row.add_prefix(icon)

            if index > 0:
                up = Gtk.Button()
                up.set_icon_name("go-up-symbolic")
                up.add_css_class("flat")
                up.set_valign(Gtk.Align.CENTER)
                up.connect("clicked", lambda _b, i=index: self._move(i, -1))
                row.add_suffix(up)
            if index < len(self._commands) - 1:
                down = Gtk.Button()
                down.set_icon_name("go-down-symbolic")
                down.add_css_class("flat")
                down.set_valign(Gtk.Align.CENTER)
                down.connect("clicked", lambda _b, i=index: self._move(i, 1))
                row.add_suffix(down)

            edit = Gtk.Button()
            edit.set_icon_name("document-edit-symbolic")
            edit.add_css_class("flat")
            edit.set_valign(Gtk.Align.CENTER)
            edit.connect("clicked", lambda _b, i=index: self._edit(i))
            row.add_suffix(edit)

            delete = Gtk.Button()
            delete.set_icon_name("user-trash-symbolic")
            delete.add_css_class("flat")
            delete.set_valign(Gtk.Align.CENTER)
            delete.connect("clicked", lambda _b, i=index: self._delete(i))
            row.add_suffix(delete)
            group.add(row)

    def _dirty(self):
        self.apply_btn.set_sensitive(True)
        self._render()

    def _move(self, index: int, delta: int):
        target = index + delta
        if 0 <= target < len(self._commands):
            self._commands[index], self._commands[target] = (
                self._commands[target],
                self._commands[index],
            )
            self._dirty()

    def _delete(self, index: int):
        if 0 <= index < len(self._commands):
            self._commands.pop(index)
            self._dirty()

    def _edit(self, index: int | None):
        current = self._commands[index] if index is not None else ""
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Edit autostart command") if index is not None else t("New autostart command"),
        )
        entry = Gtk.Entry()
        entry.set_text(current)
        entry.set_placeholder_text("caelestia shell -d")
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("save", t("Save"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(dialog_obj, response):
            if response != "save":
                return
            command = entry.get_text().strip()
            if not command:
                return
            if index is None:
                self._commands.append(command)
            else:
                self._commands[index] = command
            self._dirty()

        dialog.connect("response", on_response)
        dialog.present()

    # ── Apply ─────────────────────────────────────────────────────────────

    def _on_apply(self, _button):
        try:
            text = read_text(HYPR_USER_LUA)
            if not text.strip():
                text = "local config = {}\n\nreturn config\n"
            apply.write_and_reload(
                HYPR_USER_LUA, write_commands(text, self._commands)
            )
            self._load()
            self.main_window.add_toast(
                Adw.Toast.new(t("Autostart commands applied."))
            )
        except apply.ApplyError as exc:
            self.main_window.add_toast(
                Adw.Toast.new(
                    f"{t('Hyprland rejected the autostart change and it was rolled back')}: {exc}"
                )
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001 - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save autostart commands')}: {exc}")
            )
