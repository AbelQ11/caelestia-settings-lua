"""Default application commands.

Caelestia keeps its own app commands in ``shell.json`` (``general.apps.*``),
while the Hyprland keybinds and scripts use the ``terminal``, ``browser``,
``editor`` and ``fileExplorer`` variables.  This page edits both in one place.
"""

from __future__ import annotations

import shlex
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, desktop, lua, shell_config
from src.config import HYPR_VARIABLES_LUA, HYPR_VARS_LUA, read_text
from src.lang import t

SHELL_APPS = [
    ("general.apps.terminal", t("Terminal"), "foot"),
    ("general.apps.audio", t("Audio settings"), "pwvucontrol"),
    ("general.apps.playback", t("Media player"), "mpv"),
    ("general.apps.explorer", t("File manager"), "thunar"),
]

HYPR_APPS = [
    ("terminal", t("Terminal")),
    ("browser", t("Browser")),
    ("editor", t("Editor")),
    ("fileExplorer", t("File manager")),
]


def _read_hypr_vars() -> dict:
    values = {}
    for path in (HYPR_VARIABLES_LUA, HYPR_VARS_LUA):
        if path.exists():
            values.update(lua.read_table_values(read_text(path)))
    return values


class DefaultAppsPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(16)
        content.set_margin_start(12)
        content.set_margin_end(12)
        scroller.set_child(content)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=t("Default applications"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        toolbar.append(apply_btn)
        content.append(toolbar)

        shell_group = Adw.PreferencesGroup(
            title=t("Caelestia applications"),
            description=t("Used by the Caelestia shell (shell.json general.apps)."),
        )
        content.append(shell_group)
        self._shell_entries: dict[str, Gtk.Entry] = {}
        for key, label, placeholder in SHELL_APPS:
            value = shell_config.get(key, [placeholder])
            text = shlex.join([str(part) for part in value]) if isinstance(value, list) else str(value)
            row = Adw.ActionRow(title=label, subtitle=key)
            entry = Gtk.Entry()
            entry.set_text(text)
            entry.set_placeholder_text(placeholder)
            entry.set_width_chars(34)
            entry.set_valign(Gtk.Align.CENTER)
            row.add_suffix(entry)
            self._shell_entries[key] = entry
            shell_group.add(row)

        hypr_group = Adw.PreferencesGroup(
            title=t("Hyprland commands"),
            description=t("Used by keybinds and scripts (hypr-vars.lua)."),
        )
        content.append(hypr_group)
        hypr_vars = _read_hypr_vars()
        self._hypr_entries: dict[str, Gtk.Entry] = {}
        for key, label in HYPR_APPS:
            row = Adw.ActionRow(title=label, subtitle=key)
            entry = Gtk.Entry()
            entry.set_text(str(hypr_vars.get(key, "")))
            entry.set_width_chars(34)
            entry.set_valign(Gtk.Align.CENTER)
            row.add_suffix(entry)
            self._hypr_entries[key] = entry
            hypr_group.add(row)

        associations = Adw.PreferencesGroup(
            title=t("File associations"),
            description=t("GTK and XDG defaults for common file types."),
        )
        content.append(associations)
        self._assoc_combos: dict[str, Gtk.ComboBoxText] = {}
        apps = desktop.scan_desktop_files()
        self._assoc_apps = {entry["desktop_id"]: entry for entry in apps}

        association_specs = [
            ("browser", t("Web browser"), "xdg-settings", "default-web-browser", ""),
            ("image", t("Images"), "xdg-mime", "default", "image/png"),
            ("video", t("Videos"), "xdg-mime", "default", "video/mp4"),
            ("text", t("Text files"), "xdg-mime", "default", "text/plain"),
        ]
        for key, label, tool, command, mime in association_specs:
            row = Adw.ActionRow(title=label)
            combo = Gtk.ComboBoxText()
            combo.set_valign(Gtk.Align.CENTER)
            for entry in apps:
                combo.append(entry["desktop_id"], entry["name"])
            current = ""
            try:
                if tool == "xdg-settings":
                    result = subprocess.run(
                        [tool, "get", command], capture_output=True, text=True, timeout=3
                    )
                    current = result.stdout.strip()
                else:
                    result = subprocess.run(
                        [tool, "query", command, mime], capture_output=True, text=True, timeout=3
                    )
                    current = result.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                current = ""
            if current:
                if not combo.set_active_id(current):
                    combo.append(current, current)
                    combo.set_active_id(current)
            elif apps:
                combo.set_active(0)
            row.add_suffix(combo)
            associations.add(row)
            self._assoc_combos[key] = combo

        assoc_apply = Adw.ActionRow(title=t("Apply file associations"))
        assoc_btn = Gtk.Button(label=t("Apply"))
        assoc_btn.set_valign(Gtk.Align.CENTER)
        assoc_btn.connect("clicked", self._on_apply_associations)
        assoc_apply.add_suffix(assoc_btn)
        associations.add(assoc_apply)

        note = Gtk.Label(
            label=t(
                "Commands are parsed as shell arguments. Use quoting for arguments with spaces. "
                "Caelestia shell applications and Hyprland commands are independent."
            )
        )
        note.set_halign(Gtk.Align.START)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        note.set_wrap(True)
        content.append(note)

    def _on_apply_associations(self, _button):
        browser = self._assoc_combos["browser"].get_active_id()
        image = self._assoc_combos["image"].get_active_id()
        video = self._assoc_combos["video"].get_active_id()
        text = self._assoc_combos["text"].get_active_id()

        commands = []
        if browser:
            commands.append(["xdg-settings", "set", "default-web-browser", browser])
            commands.append(["xdg-mime", "default", browser, "x-scheme-handler/http"])
            commands.append(["xdg-mime", "default", browser, "x-scheme-handler/https"])
        if image:
            commands.append(["xdg-mime", "default", image, "image/png", "image/jpeg", "image/webp", "image/gif"])
        if video:
            commands.append(["xdg-mime", "default", video, "video/mp4", "video/x-matroska", "video/webm"])
        if text:
            commands.append(["xdg-mime", "default", text, "text/plain"])

        ok = True
        for command in commands:
            try:
                ok = subprocess.run(command, capture_output=True, timeout=5, check=False).returncode == 0 and ok
            except (OSError, subprocess.SubprocessError):
                ok = False
        self.main_window.add_toast(
            Adw.Toast.new(t("File associations applied.") if ok else t("Some associations could not be applied."))
        )

    def _on_apply(self, _button):
        shell_values = {}
        for key, entry in self._shell_entries.items():
            text = entry.get_text().strip()
            try:
                command = shlex.split(text)
            except ValueError as exc:
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Invalid command')} ({key}): {exc}")
                )
                return
            shell_values[key] = command or [entry.get_placeholder_text() or "foot"]

        hypr_values = {}
        for key, entry in self._hypr_entries.items():
            text = entry.get_text().strip()
            if text:
                hypr_values[key] = text

        try:
            if hypr_values:
                text = read_text(HYPR_VARS_LUA)
                if not text.strip():
                    text = "return {\n}\n"
                apply.write_and_reload(
                    HYPR_VARS_LUA, lua.set_table_values(text, hypr_values)
                )
            shell_config.set_many(shell_values)
            self.main_window.add_toast(
                Adw.Toast.new(t("Default applications applied."))
            )
        except apply.ApplyError as exc:
            self.main_window.add_toast(
                Adw.Toast.new(
                    f"{t('Hyprland rejected the change and it was rolled back')}: {exc}"
                )
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001 - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save default applications')}: {exc}")
            )
