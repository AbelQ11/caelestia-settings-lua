"""Action picker for custom keybinds.

A searchable menu containing every installed application plus common Hyprland
and Caelestia actions.  Selecting an app creates an ``exec`` bind using
``gtk-launch`` so complex desktop entries work correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import desktop
from src.lang import t


@dataclass(frozen=True)
class Action:
    title: str
    category: str
    dispatcher: str
    argument: str
    icon: str = "application-x-executable"


def builtin_actions() -> list[Action]:
    def action(title, category, dispatcher, argument="", icon="preferences-system-symbolic"):
        return Action(title, category, dispatcher, argument, icon)

    return [
        # Caelestia globals
        action(t("Caelestia launcher"), t("Caelestia"), "global", "caelestia:launcher", "system-search-symbolic"),
        action(t("Session menu"), t("Caelestia"), "global", "caelestia:session", "system-shutdown-symbolic"),
        action(t("Sidebar"), t("Caelestia"), "global", "caelestia:sidebar", "sidebar-show-symbolic"),
        action(t("Lock screen"), t("Caelestia"), "global", "caelestia:lock", "system-lock-screen-symbolic"),
        action(t("Clear notifications"), t("Caelestia"), "global", "caelestia:clearNotifs", "preferences-system-notifications-symbolic"),
        action(t("Show all panels"), t("Caelestia"), "global", "caelestia:showall", "preferences-desktop-display-symbolic"),
        # Window
        action(t("Close window"), t("Window"), "killactive", "", "window-close-symbolic"),
        action(t("Toggle fullscreen"), t("Window"), "fullscreen", "", "view-fullscreen-symbolic"),
        action(t("Toggle floating"), t("Window"), "togglefloating", "", "window-restore-symbolic"),
        action(t("Pin window"), t("Window"), "pin", "", "view-pin-symbolic"),
        action(t("Centre window"), t("Window"), "centerwindow", "", "window-center-symbolic"),
        action(t("Toggle split"), t("Window"), "togglesplit", "", "view-dual-symbolic"),
        action(t("Swap with next window"), t("Window"), "swapnext", "", "object-flip-horizontal-symbolic"),
        action(t("Focus left"), t("Window"), "movefocus", "l", "go-previous-symbolic"),
        action(t("Focus right"), t("Window"), "movefocus", "r", "go-next-symbolic"),
        action(t("Focus up"), t("Window"), "movefocus", "u", "go-up-symbolic"),
        action(t("Focus down"), t("Window"), "movefocus", "d", "go-down-symbolic"),
        action(t("Move window left"), t("Window"), "movewindow", "l", "go-previous-symbolic"),
        action(t("Move window right"), t("Window"), "movewindow", "r", "go-next-symbolic"),
        action(t("Move window up"), t("Window"), "movewindow", "u", "go-up-symbolic"),
        action(t("Move window down"), t("Window"), "movewindow", "d", "go-down-symbolic"),
        # Workspace
        action(t("Next workspace"), t("Workspace"), "workspace", "e+1", "go-next-symbolic"),
        action(t("Previous workspace"), t("Workspace"), "workspace", "e-1", "go-previous-symbolic"),
        action(t("Move window to next workspace"), t("Workspace"), "movetoworkspace", "e+1", "go-next-symbolic"),
        action(t("Move window to previous workspace"), t("Workspace"), "movetoworkspace", "e-1", "go-previous-symbolic"),
        action(t("Toggle special workspace"), t("Workspace"), "togglespecialworkspace", "special", "view-grid-symbolic"),
        *[
            action(f"{t('Workspace')} {number}", t("Workspace"), "workspace", str(number), "view-grid-symbolic")
            for number in range(1, 6)
        ],
        # Media
        action(t("Play / pause"), t("Media"), "exec", "playerctl play-pause", "media-playback-start-symbolic"),
        action(t("Next track"), t("Media"), "exec", "playerctl next", "media-skip-forward-symbolic"),
        action(t("Previous track"), t("Media"), "exec", "playerctl previous", "media-skip-backward-symbolic"),
        action(t("Mute audio"), t("Media"), "exec", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", "audio-volume-muted-symbolic"),
        action(t("Volume up"), t("Media"), "exec", "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+", "audio-volume-high-symbolic"),
        action(t("Volume down"), t("Media"), "exec", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", "audio-volume-low-symbolic"),
        # System
        action(t("Screenshot"), t("System"), "exec", "caelestia screenshot -f", "camera-photo-symbolic"),
        action(t("Region screenshot"), t("System"), "exec", "caelestia screenshot -r", "camera-photo-symbolic"),
        action(t("Start recording"), t("System"), "exec", "caelestia record", "media-record-symbolic"),
        action(t("Record region"), t("System"), "exec", "caelestia record -r", "media-record-symbolic"),
        action(t("Sleep"), t("System"), "exec", "systemctl suspend-then-hibernate", "weather-clear-night-symbolic"),
    ]


def application_actions() -> list[Action]:
    actions = []
    for entry in desktop.scan_desktop_files():
        actions.append(
            Action(
                title=entry["name"],
                category=t("Application"),
                dispatcher="exec",
                argument=desktop.launch_command(entry),
                icon=entry.get("icon") or "application-x-executable",
            )
        )
    return actions


def all_actions() -> list[Action]:
    return application_actions() + builtin_actions()


class ActionMenuButton(Gtk.MenuButton):
    def __init__(self, on_select):
        super().__init__()
        self._on_select = on_select
        self._actions = all_actions()
        self._selected: Action | None = None
        self.set_label(t("Choose application or action"))
        self.set_icon_name("system-search-symbolic")
        self.add_css_class("flat")

        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        search = Gtk.SearchEntry()
        search.set_placeholder_text(t("Search applications and actions…"))
        search.set_margin_top(8)
        search.set_margin_bottom(6)
        search.set_margin_start(8)
        search.set_margin_end(8)
        search.connect("search-changed", lambda _e: self._populate(search.get_text()))
        box.append(search)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_width(420)
        scroller.set_min_content_height(360)
        box.append(scroller)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._list.set_margin_start(6)
        self._list.set_margin_end(6)
        self._list.set_margin_bottom(6)
        scroller.set_child(self._list)
        popover.set_child(box)
        self.set_popover(popover)
        self._search = search
        self._populate("")

    @property
    def selected(self) -> Action | None:
        return self._selected

    def _populate(self, query: str):
        while row := self._list.get_first_child():
            self._list.remove(row)
        query = query.strip().lower()
        shown = 0
        for action in self._actions:
            haystack = f"{action.title} {action.category} {action.argument}".lower()
            if query and query not in haystack:
                continue
            row = Adw.ActionRow(title=action.title, subtitle=action.category)
            icon = self._icon(action.icon)
            if icon is not None:
                row.add_prefix(icon)
            row.set_activatable(True)
            row.connect("activated", self._choose, action)
            self._list.append(row)
            shown += 1
            if shown >= 120:
                break
        if shown == 0:
            self._list.append(
                Adw.ActionRow(title=t("No matching actions"), subtitle="")
            )

    @staticmethod
    def _icon(icon: str) -> Gtk.Widget | None:
        try:
            path = Path(icon)
            if path.is_absolute() and path.exists():
                image = Gtk.Image.new_from_file(str(path))
                image.set_pixel_size(24)
                return image
        except (OSError, ValueError):
            pass
        image = Gtk.Image.new_from_icon_name(icon or "application-x-executable")
        return image

    def _choose(self, _row, action: Action):
        self._selected = action
        self.set_label(action.title)
        self.set_icon_name(action.icon)
        self.get_popover().popdown()
        self._on_select(action)
