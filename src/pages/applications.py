"""Applications page: AppImage integration and managed desktop entries."""

from __future__ import annotations

import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import desktop
from src.lang import t


class ApplicationsPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        title = Gtk.Label(label=t("Applications"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)

        add_btn = Gtk.Button(label=t("+ Add AppImage"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_appimage)
        toolbar.append(add_btn)

        refresh = Gtk.Button()
        refresh.set_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text(t("Reload"))
        refresh.connect("clicked", lambda _b: self._load())
        toolbar.append(refresh)
        self.append(toolbar)

        note = Gtk.Label(
            label=t(
                "AppImages are added as .desktop entries in ~/.local/share/applications, "
                "so Caelestia's launcher and other application menus can find them."
            )
        )
        note.set_halign(Gtk.Align.START)
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        note.set_wrap(True)
        self.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.set_margin_top(8)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._load()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self):
        while child := self.content.get_first_child():
            self.content.remove(child)

        entries = desktop.managed_entries()
        group = Adw.PreferencesGroup(
            title=t("AppImages added by Caelestia Settings"),
            description=t("Entries created by this page."),
        )
        self.content.append(group)

        if not entries:
            group.add(
                Adw.ActionRow(
                    title=t("No AppImages added yet"),
                    subtitle=t("Use “+ Add AppImage” to create a launcher entry."),
                )
            )
            return

        for entry in entries:
            row = Adw.ActionRow(
                title=entry["name"],
                subtitle=entry.get("appimage") or entry["exec"],
            )
            icon = self._icon(entry.get("icon", ""))
            if icon is not None:
                row.add_prefix(icon)

            open_btn = Gtk.Button()
            open_btn.set_icon_name("folder-open-symbolic")
            open_btn.add_css_class("flat")
            open_btn.set_valign(Gtk.Align.CENTER)
            open_btn.set_tooltip_text(t("Open containing folder"))
            open_btn.connect("clicked", self._on_open_folder, entry)
            row.add_suffix(open_btn)

            remove = Gtk.Button()
            remove.set_icon_name("user-trash-symbolic")
            remove.add_css_class("flat")
            remove.set_valign(Gtk.Align.CENTER)
            remove.set_tooltip_text(t("Remove launcher entry"))
            remove.connect("clicked", self._on_remove, entry)
            row.add_suffix(remove)
            group.add(row)

    @staticmethod
    def _icon(icon: str) -> Gtk.Widget | None:
        try:
            path = Path(icon)
            if path.is_absolute() and path.exists():
                image = Gtk.Image.new_from_file(str(path))
                image.set_pixel_size(32)
                return image
        except (OSError, ValueError):
            pass
        image = Gtk.Image.new_from_icon_name(icon or "application-x-executable")
        image.set_pixel_size(32)
        return image

    # ── Add AppImage ──────────────────────────────────────────────────────

    def _on_add_appimage(self, _button):
        chooser = Gtk.FileChooserNative.new(
            t("Select AppImage"),
            self.get_root(),
            Gtk.FileChooserAction.OPEN,
            t("Select"),
            t("Cancel"),
        )
        appimage_filter = Gtk.FileFilter()
        appimage_filter.set_name("AppImage")
        appimage_filter.add_pattern("*.AppImage")
        appimage_filter.add_pattern("*.appimage")
        chooser.add_filter(appimage_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name(t("All files"))
        all_filter.add_pattern("*")
        chooser.add_filter(all_filter)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file is not None and file.get_path():
                    self._show_appimage_form(Path(file.get_path()))
            dialog.destroy()

        chooser.connect("response", on_response)
        chooser.show()

    def _show_appimage_form(self, path: Path):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=t("Add AppImage"),
            body=str(path),
        )

        box = Gtk.ListBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")

        name = Adw.EntryRow(title=t("Name"))
        name.set_text(path.stem)
        box.append(name)

        icon = Adw.EntryRow(title=t("Icon (optional path or theme name)"))
        icon.set_text("")
        box.append(icon)

        categories = Adw.EntryRow(title=t("Categories"))
        categories.set_text("Utility;")
        box.append(categories)

        terminal = Adw.SwitchRow(title=t("Run in terminal"))
        box.append(terminal)

        copy = Adw.SwitchRow(title=t("Copy to ~/Applications"))
        copy.set_subtitle(t("Recommended; keeps the launcher entry stable"))
        copy.set_active(True)
        box.append(copy)

        extract = Adw.SwitchRow(title=t("Use --appimage-extract-and-run"))
        extract.set_subtitle(t("For systems where FUSE is unavailable"))
        box.append(extract)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("add", t("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog_obj, response):
            if response != "add":
                return
            try:
                desktop_path, errors = desktop.install_appimage(
                    path,
                    name=name.get_text().strip() or path.stem,
                    icon=icon.get_text().strip(),
                    categories=categories.get_text().strip(),
                    terminal=terminal.get_active(),
                    copy_to_applications=copy.get_active(),
                    extract_and_run=extract.get_active(),
                )
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Added')} {desktop_path.name}")
                )
                if errors:
                    self.main_window.add_toast(
                        Adw.Toast.new(f"{t('Desktop file warning')}: {errors[:200]}")
                    )
                self._load()
            except Exception as exc:  # noqa: BLE001 - defensive UI path
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Could not add the AppImage')}: {exc}")
                )

        dialog.connect("response", on_response)
        dialog.present()

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_open_folder(self, _button, entry: dict):
        try:
            folder = Path(entry["path"]).parent
            subprocess.Popen(["xdg-open", str(folder)])
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not open the folder')}: {exc}")
            )

    def _on_remove(self, _button, entry: dict):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=t("Remove launcher entry?"),
            body=entry["name"],
        )
        delete_appimage = Gtk.CheckButton(label=t("Also delete the copied AppImage"))
        appimage = entry.get("appimage", "")
        delete_appimage.set_sensitive(
            bool(appimage) and Path(appimage).is_relative_to(desktop.APPIMAGE_DIR)
        )
        delete_appimage.set_margin_top(8)
        dialog.set_extra_child(delete_appimage)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("remove", t("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "remove":
                return
            try:
                if desktop.remove_entry(
                    entry, delete_appimage=delete_appimage.get_active()
                ):
                    self.main_window.add_toast(Adw.Toast.new(t("Launcher entry removed.")))
                    self._load()
            except Exception as exc:  # noqa: BLE001
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Could not remove the entry')}: {exc}")
                )

        dialog.connect("response", on_response)
        dialog.present()
