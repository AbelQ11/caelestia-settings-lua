"""Global settings search (Ctrl+F).

A small command-palette style dialog that searches page names and every
Caelestia shell option.  Selecting a result navigates to the page (and, for
shell options, pre-fills the Caelestia page search).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import shell_schema
from src.lang import t

PAGES = [
    ("home", t("Home"), t("Overview of the system"), "go-home-symbolic"),
    ("gen", t("General"), t("Keyboard, touchpad, gestures, cursor, language and timezone"), "preferences-system-symbolic"),
    ("input", t("Input devices"), t("Per-device keyboard, mouse, touchpad and tablet settings"), "input-keyboard-symbolic"),
    ("apps", t("Default apps"), t("Caelestia and Hyprland application commands"), "application-x-executable-symbolic"),
    ("applications", t("Applications"), t("Add AppImages and manage launcher entries"), "application-x-executable-symbolic"),
    ("shell", t("Caelestia"), t("All 279 Caelestia shell options"), "preferences-desktop-symbolic"),
    ("theme", t("Theming"), t("Colour scheme, palette and GTK appearance"), "applications-graphics-symbolic"),
    ("wall", t("Wallpaper"), t("Wallpaper and desktop clock"), "preferences-desktop-wallpaper-symbolic"),
    ("hypr", t("Hyprland"), t("Gaps, borders, opacity, blur, shadows and cursor"), "applications-graphics-symbolic"),
    ("autostart", t("Autostart"), t("Commands run at Hyprland startup"), "application-x-executable-symbolic"),
    ("ws", t("Workspaces"), t("Workspace rules and monitor assignment"), "preferences-desktop-display-symbolic"),
    ("mon", t("Monitor"), t("Monitor layout, resolution and scaling"), "video-display-symbolic"),
    ("network", t("Network"), t("Devices, connections, VPN and IPv4"), "network-wired-symbolic"),
    ("wifi", t("Wi-Fi"), t("Wi-Fi networks"), "network-wireless-symbolic"),
    ("bluetooth", t("Bluetooth"), t("Bluetooth adapter, pairing and devices"), "bluetooth-symbolic"),
    ("audio", t("Audio"), t("Audio output, input, volume and mute"), "audio-volume-high-symbolic"),
    ("rules", t("Window Rules"), t("App workspace and floating rules"), "preferences-system-windows-symbolic"),
    ("keys", t("Keybinds"), t("Caelestia shortcuts, custom binds and active binds"), "preferences-desktop-keyboard-symbolic"),
    ("fans", t("Fans"), t("Fan speeds and temperatures"), "sensors-applet-symbolic"),
    ("power", t("Power"), t("Power profiles, battery and idle behaviour"), "battery-good-symbolic"),
    ("upd", t("Updates"), t("System updates"), "software-update-available-symbolic"),
    ("backups", t("Backups"), t("Restore configuration backups"), "document-save-symbolic"),
    ("health", t("Health"), t("Diagnostics, dependencies and wallpaper daemons"), "dialog-information-symbolic"),
    ("about", t("About"), t("Version, author and uninstall"), "help-about-symbolic"),
]


class SearchDialog(Adw.Dialog):
    def __init__(self, on_navigate):
        super().__init__()
        self._on_navigate = on_navigate
        self._results: list[tuple[str, str | None]] = []
        self.set_content_width(700)
        self.set_content_height(560)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(box)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text(t("Search settings and Caelestia options…"))
        self._entry.set_margin_top(12)
        self._entry.set_margin_bottom(8)
        self._entry.set_margin_start(12)
        self._entry.set_margin_end(12)
        self._entry.connect("search-changed", lambda _e: self._populate())
        self._entry.connect("activate", lambda _e: self._activate_first())
        box.append(self._entry)

        self._count = Gtk.Label()
        self._count.add_css_class("caption")
        self._count.add_css_class("dim-label")
        self._count.set_halign(Gtk.Align.START)
        self._count.set_margin_start(14)
        self._count.set_margin_bottom(6)
        box.append(self._count)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box.append(scroller)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._list.set_margin_start(12)
        self._list.set_margin_end(12)
        self._list.set_margin_bottom(12)
        scroller.set_child(self._list)

        self._populate()
        self._entry.grab_focus()

    def _populate(self):
        while row := self._list.get_first_child():
            self._list.remove(row)
        self._results.clear()

        query = self._entry.get_text().strip().lower()
        entries: list[tuple[str, str, str, str | None, str]] = []
        for page, title, description, icon in PAGES:
            haystack = f"{title} {description}".lower()
            if not query or query in haystack:
                entries.append((page, title, description, None, icon))

        if query:
            for option in shell_schema.options():
                section = shell_schema.section_meta(option.section)[0]
                group = shell_schema.group_title(option.section, option.subgroup)
                haystack = f"{option.label} {option.path} {section} {group}".lower()
                if query not in haystack:
                    continue
                title = f"{section} · {option.label}"
                subtitle = f"{option.path}  ·  {group}"
                entries.append(("shell", title, subtitle, option.path, "preferences-system-symbolic"))
            entries = entries[:60]
        self._count.set_text(
            f"{len(entries)} {t('result(s)')}"
            if entries
            else t("No matching settings")
        )

        for page, title, subtitle, query_text, icon in entries:
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            image = Gtk.Image.new_from_icon_name(icon)
            image.set_valign(Gtk.Align.CENTER)
            row.add_prefix(image)
            row.set_activatable(True)
            row.connect("activated", self._on_activated, page, query_text)
            self._list.append(row)
            self._results.append((page, query_text))

    def _on_activated(self, _row, page: str, query_text: str | None):
        self.close()
        self._on_navigate(page, query_text)

    def _activate_first(self):
        if self._results:
            page, query_text = self._results[0]
            self.close()
            self._on_navigate(page, query_text)
