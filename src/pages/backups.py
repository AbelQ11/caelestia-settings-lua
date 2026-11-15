"""Backup browser and restore page.

Every configuration write creates a timestamped backup (see :mod:`src.backup`).
This page lists those backups, grouped by the file they belong to, and lets the
user restore one.  Restoring also backs up the current file first, so a restore
is itself undoable.
"""

from __future__ import annotations

import difflib
from collections import defaultdict

from gi.repository import Adw, Gtk

from src import backup
from src.config import (
    HOME,
    HYPR_EXECS_LUA,
    HYPR_MONITORS_LUA,
    HYPR_USER_LUA,
    HYPR_VARS_LUA,
    MONITOR_SHELL_DIR,
    SHELL_JSON,
    read_text,
    reload_hyprland,
    restart_caelestia,
)
from src.lang import t


def _short_path(path) -> str:
    try:
        return str(path).replace(str(HOME), "~")
    except Exception:  # noqa: BLE001
        return str(path)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


class BackupsPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        title = Gtk.Label(label=t("Configuration backups"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)

        backup_btn = Gtk.Button(label=t("Backup now"))
        backup_btn.add_css_class("suggested-action")
        backup_btn.connect("clicked", self._on_backup_now)
        toolbar.append(backup_btn)

        refresh_btn = Gtk.Button(label=t("Refresh"))
        refresh_btn.connect("clicked", lambda _: self._load())
        toolbar.append(refresh_btn)

        open_btn = Gtk.Button(label=t("Open backup folder"))
        open_btn.connect("clicked", self._on_open_folder)
        toolbar.append(open_btn)

        keep_label = Gtk.Label(label=t("Keep per file"))
        keep_label.add_css_class("caption")
        keep_label.add_css_class("dim-label")
        toolbar.append(keep_label)
        self.retention_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.retention_spin.set_value(backup.get_retention())
        self.retention_spin.set_valign(Gtk.Align.CENTER)
        self.retention_spin.connect("value-changed", self._on_retention_changed)
        toolbar.append(self.retention_spin)
        self.append(toolbar)

        note = Gtk.Label()
        note.set_markup(
            f"<small>{t('Backups are created before every write. Retention is configurable above. Backups live in')} "
            f"<tt>{_short_path(backup.BACKUP_DIR)}</tt>.</small>"
        )
        note.set_halign(Gtk.Align.START)
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.add_css_class("dim-label")
        self.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content.set_margin_top(8)
        self._content.set_margin_bottom(12)
        self._content.set_margin_start(12)
        self._content.set_margin_end(12)
        scroller.set_child(self._content)

        self._load()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self):
        while child := self._content.get_first_child():
            self._content.remove(child)

        entries = backup.list_backups()
        if not entries:
            status = Adw.StatusPage()
            status.set_icon_name("document-save-symbolic")
            status.set_title(t("No backups yet"))
            status.set_description(
                t("A backup is created automatically the first time you change a setting.")
            )
            self._content.append(status)
            return

        grouped = defaultdict(list)
        for entry in entries:
            grouped[entry.target].append(entry)

        for target, items in sorted(grouped.items(), key=lambda item: str(item[0])):
            group = Adw.PreferencesGroup(title=_short_path(target))
            for entry in items[:20]:
                row = Adw.ActionRow(
                    title=entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    subtitle=f"{_format_size(entry.size)}  ·  {entry.backup.name}",
                )
                preview = Gtk.Button(label=t("Preview"))
                preview.set_valign(Gtk.Align.CENTER)
                preview.connect("clicked", self._on_preview, entry)
                row.add_suffix(preview)

                diff = Gtk.Button(label=t("Diff"))
                diff.set_valign(Gtk.Align.CENTER)
                diff.connect("clicked", self._on_diff, entry)
                row.add_suffix(diff)

                restore = Gtk.Button(label=t("Restore"))
                restore.add_css_class("suggested-action")
                restore.set_valign(Gtk.Align.CENTER)
                restore.connect("clicked", self._on_restore, entry)
                row.add_suffix(restore)

                delete = Gtk.Button()
                delete.set_icon_name("user-trash-symbolic")
                delete.add_css_class("flat")
                delete.set_valign(Gtk.Align.CENTER)
                delete.set_tooltip_text(t("Delete this backup"))
                delete.connect("clicked", self._on_delete, entry)
                row.add_suffix(delete)
                group.add(row)
            self._content.append(group)

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_open_folder(self, _button):
        try:
            import subprocess

            subprocess.Popen(["xdg-open", str(backup.BACKUP_DIR)])
        except Exception as exc:  # noqa: BLE001
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not open folder')}: {exc}"))

    def _on_retention_changed(self, spin):
        backup.set_retention(int(spin.get_value()))

    def _on_backup_now(self, _button):
        paths = [
            SHELL_JSON,
            HYPR_USER_LUA,
            HYPR_VARS_LUA,
            HYPR_MONITORS_LUA,
            HYPR_EXECS_LUA,
        ]
        if MONITOR_SHELL_DIR.exists():
            paths.extend(sorted(MONITOR_SHELL_DIR.glob("*/shell.json")))
        created = 0
        try:
            for path in paths:
                if path.exists() and backup.create_backup(path) is not None:
                    created += 1
            self.main_window.add_toast(
                Adw.Toast.new(f"{created} {t('backup(s) created.')}")
            )
            self._load()
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))

    def _on_diff(self, _button, entry: backup.BackupEntry):
        old_text = read_text(entry.backup)
        new_text = read_text(entry.target)
        diff = list(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile=f"{_short_path(entry.backup)}",
                tofile=f"{_short_path(entry.target)} (current)",
                lineterm="",
            )
        )
        text = "\n".join(diff) if diff else t("No differences.")
        dialog = Adw.MessageDialog(
            heading=t("Backup diff"),
            body=f"{_short_path(entry.target)}\n{entry.timestamp}",
        )
        dialog.set_transient_for(self.main_window)
        dialog.add_response("close", t("Close"))
        buffer = Gtk.TextBuffer()
        buffer.set_text(text)
        view = Gtk.TextView(buffer=buffer)
        view.set_editable(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(420)
        scroller.set_min_content_width(760)
        scroller.set_child(view)
        dialog.set_extra_child(scroller)
        dialog.present()

    def _on_delete(self, _button, entry: backup.BackupEntry):
        dialog = Adw.MessageDialog(
            heading=t("Delete this backup?"),
            body=f"{_short_path(entry.target)}\n{entry.timestamp}",
        )
        dialog.set_transient_for(self.main_window)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("delete", t("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "delete":
                return
            try:
                backup.delete_backup(entry.backup)
                self.main_window.add_toast(Adw.Toast.new(t("Backup deleted.")))
                self._load()
            except backup.BackupError as exc:
                self.main_window.add_toast(Adw.Toast.new(str(exc)))

        dialog.connect("response", on_response)
        dialog.present()

    def _on_preview(self, _button, entry: backup.BackupEntry):
        dialog = Adw.MessageDialog(
            heading=t("Backup preview"),
            body=f"{_short_path(entry.target)}\n{entry.timestamp}",
        )
        dialog.set_transient_for(self.main_window)
        dialog.add_response("close", t("Close"))

        text = read_text(entry.backup)
        if len(text) > 12000:
            text = text[:12000] + "\n…"

        buffer = Gtk.TextBuffer()
        buffer.set_text(text)
        view = Gtk.TextView(buffer=buffer)
        view.set_editable(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(360)
        scroller.set_min_content_width(640)
        scroller.set_child(view)
        dialog.set_extra_child(scroller)
        dialog.present()

    def _on_restore(self, _button, entry: backup.BackupEntry):
        dialog = Adw.MessageDialog(
            heading=t("Restore this backup?"),
            body=f"{_short_path(entry.target)}\n{entry.timestamp}",
        )
        dialog.set_transient_for(self.main_window)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("restore", t("Restore"))
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog_obj, response):
            if response != "restore":
                return
            try:
                target = backup.restore_backup(entry.backup)
                if "caelestia" in str(target):
                    restart_caelestia()
                if "hypr" in str(target):
                    reload_hyprland()
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Restored')} {_short_path(target)}")
                )
                self._load()
            except backup.BackupError as exc:
                self.main_window.add_toast(Adw.Toast.new(str(exc)))
            except Exception as exc:  # noqa: BLE001
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Could not restore backup')}: {exc}")
                )

        dialog.connect("response", on_response)
        dialog.present()
