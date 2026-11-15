import json
import threading
import urllib.error
import urllib.request
from gi.repository import Gtk, Adw, GLib
from src.pages.home import HomePage
from src.pages.general import GeneralPage
from src.pages.input_devices import InputDevicesPage
from src.pages.applications import ApplicationsPage
from src.pages.default_apps import DefaultAppsPage
from src.pages.theming import ThemingPage
from src.pages.monitor import MonitorPage
from src.pages.network import NetworkPage
from src.pages.power import PowerPage
from src.pages.audio import AudioPage
from src.pages.autostart import AutostartPage
from src.pages.bluetooth import BluetoothPage
from src.pages.wifi import WifiPage
from src.pages.updates import UpdatePage
from src.pages.about import AboutPage
from src.pages.fans import FansPage
from src.pages.window_rules import WindowRulesPage
from src.pages.keybinds import KeybindsPage
from src.pages.wallpaper import WallpaperPage
from src.pages.workspaces import WorkspacesPage
from src.pages.hyprland import HyprlandPage
from src.pages.shell import ShellPage
from src.pages.health import HealthPage
from src.pages.backups import BackupsPage
from src.search import SearchDialog
from src.lang import t

# Source of truth for "is a newer version out": the manifest on this fork.
MANIFEST_URL = "https://raw.githubusercontent.com/AbelQ11/caelestia-settings-lua/dev/manifest.json"


def _parse_version(version: str) -> tuple:
    """Turns "1.2.10" into (1, 2, 10) for numeric comparison.

    Plain string comparison would rank "1.10.0" below "1.9.0". Returns an
    empty tuple for anything that isn't dot-separated integers, which always
    compares as "not newer" against a real version.
    """
    try:
        return tuple(int(part) for part in version.split("."))
    except (ValueError, AttributeError):
        return ()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.set_title(t("Caelestia Settings"))
        self.set_default_size(1100, 840)

        # --- ToastOverlay als Haupt-Container ---
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(root)

        header = Adw.HeaderBar()
        root.append(header)

        # --- BUTTONS ---
        self.update_btn = Gtk.Button(label=t("Update App"))
        self.update_btn.add_css_class("suggested-action")
        self.update_btn.set_visible(False)
        self.update_btn.connect("clicked", self.on_update_app)
        header.pack_end(self.update_btn)

        self.search_btn = Gtk.Button()
        self.search_btn.set_icon_name("system-search-symbolic")
        self.search_btn.set_tooltip_text(t("Search settings (Ctrl+F)"))
        self.search_btn.connect("clicked", lambda _b: self.open_search())
        header.pack_end(self.search_btn)
        self._install_shortcuts()

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_vexpand(True)
        root.append(main_box)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        self._nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(self._nav_box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        main_box.append(self.stack)

        # Pages that need a stable reference for navigation/search.
        self.mon_page = MonitorPage(self)
        self.about_page = AboutPage(self)
        self.shell_page = ShellPage(self)
        self.health_page = HealthPage(self)

        # ── Fill the stack ──────────────────────────────────────────────────
        # HomePage reads about_page.local_version, so it is built after it.
        self.stack.add_titled(HomePage(self),          "home",    t("Home"))
        self.stack.add_titled(GeneralPage(self),      "gen",     t("General"))
        self.stack.add_titled(InputDevicesPage(self), "input",   t("Input devices"))
        self.stack.add_titled(DefaultAppsPage(self),  "apps",    t("Default apps"))
        self.stack.add_titled(ApplicationsPage(self), "applications", t("Applications"))
        self.stack.add_titled(self.shell_page,        "shell",   t("Caelestia"))
        self.stack.add_titled(ThemingPage(self),      "theme",   t("Theming"))
        self.stack.add_titled(WallpaperPage(self),     "wall",    t("Wallpaper"))
        self.stack.add_titled(HyprlandPage(self),      "hypr",    t("Hyprland"))
        self.stack.add_titled(AutostartPage(self),     "autostart", t("Autostart"))
        self.stack.add_titled(WorkspacesPage(self),   "ws",      t("Workspaces"))
        self.stack.add_titled(self.mon_page,           "mon",     t("Monitor"))
        self.stack.add_titled(NetworkPage(self),       "network", t("Network"))
        self.stack.add_titled(WifiPage(self),          "wifi",    t("Wi-Fi"))
        self.stack.add_titled(BluetoothPage(self),     "bluetooth", t("Bluetooth"))
        self.stack.add_titled(AudioPage(self),         "audio",   t("Audio"))
        self.stack.add_titled(WindowRulesPage(self),   "rules",   t("Window Rules"))
        self.stack.add_titled(KeybindsPage(self),      "keys",    t("Keybinds"))
        self.stack.add_titled(FansPage(self),          "fans",    t("Fans"))
        self.stack.add_titled(PowerPage(self),         "power",   t("Power"))
        self.stack.add_titled(UpdatePage(self),        "upd",     t("Updates"))
        self.stack.add_titled(BackupsPage(self),       "backups", t("Backups"))
        self.stack.add_titled(self.health_page,        "health",  t("Health"))
        self.stack.add_titled(self.about_page,         "about",   t("About"))
        # ───────────────────────────────────────────────────────────────────

        self._build_sidebar()
        self.stack.set_visible_child_name("home")

        threading.Thread(target=self._check_for_update, daemon=True).start()

    def add_toast(self, toast):
        self.toast_overlay.add_toast(toast)

    # ── Global search / navigation ───────────────────────────────────────

    def _install_shortcuts(self):
        controller = Gtk.ShortcutController()
        for accel in ("<Control>f", "<Control>k"):
            controller.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(accel),
                    Gtk.CallbackAction.new(self._on_search_shortcut),
                )
            )
        self.add_controller(controller)

    def _build_sidebar(self):
        self._nav_sync = False
        self._nav_rows: dict[str, Gtk.ListBoxRow] = {}

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_size_request(214, -1)
        self._nav_box.append(scroller)

        nav = Gtk.ListBox()
        nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        nav.add_css_class("navigation-sidebar")
        nav.set_margin_top(6)
        nav.set_margin_bottom(6)
        nav.set_margin_start(6)
        nav.set_margin_end(6)
        nav.connect("row-selected", self._on_nav_row_selected)
        scroller.set_child(nav)
        self._nav_list = nav

        groups = [
            (t("System"), [
                ("home", t("Home"), "go-home-symbolic"),
                ("gen", t("General"), "preferences-system-symbolic"),
                ("input", t("Input devices"), "input-keyboard-symbolic"),
                ("apps", t("Default apps"), "application-x-executable-symbolic"),
                ("applications", t("Applications"), "applications-system-symbolic"),
            ]),
            (t("Caelestia"), [
                ("shell", t("Caelestia"), "preferences-desktop-symbolic"),
                ("theme", t("Theming"), "applications-graphics-symbolic"),
                ("wall", t("Wallpaper"), "preferences-desktop-wallpaper-symbolic"),
                ("hypr", t("Hyprland"), "applications-graphics-symbolic"),
                ("autostart", t("Autostart"), "application-x-executable-symbolic"),
            ]),
            (t("Desktop"), [
                ("mon", t("Monitor"), "video-display-symbolic"),
                ("ws", t("Workspaces"), "preferences-desktop-display-symbolic"),
                ("rules", t("Window Rules"), "preferences-system-windows-symbolic"),
                ("keys", t("Keybinds"), "preferences-desktop-keyboard-symbolic"),
            ]),
            (t("Hardware"), [
                ("network", t("Network"), "network-wired-symbolic"),
                ("wifi", t("Wi-Fi"), "network-wireless-symbolic"),
                ("bluetooth", t("Bluetooth"), "bluetooth-symbolic"),
                ("audio", t("Audio"), "audio-volume-high-symbolic"),
                ("fans", t("Fans"), "sensors-applet-symbolic"),
                ("power", t("Power"), "battery-good-symbolic"),
            ]),
            (t("Maintenance"), [
                ("upd", t("Updates"), "software-update-available-symbolic"),
                ("backups", t("Backups"), "document-save-symbolic"),
                ("health", t("Health"), "dialog-information-symbolic"),
                ("about", t("About"), "help-about-symbolic"),
            ]),
        ]

        for title, entries in groups:
            header = Gtk.ListBoxRow()
            header.set_selectable(False)
            header.set_activatable(False)
            label = Gtk.Label(label=title)
            label.add_css_class("caption")
            label.add_css_class("dim-label")
            label.set_halign(Gtk.Align.START)
            label.set_margin_top(12)
            label.set_margin_bottom(2)
            label.set_margin_start(10)
            header.set_child(label)
            nav.append(header)

            for name, page_title, icon_name in entries:
                row = Gtk.ListBoxRow()
                row.set_tooltip_text(page_title)
                row._page = name  # type: ignore[attr-defined]
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                box.set_margin_top(7)
                box.set_margin_bottom(7)
                box.set_margin_start(10)
                box.set_margin_end(10)
                image = Gtk.Image.new_from_icon_name(icon_name)
                box.append(image)
                page_label = Gtk.Label(label=page_title)
                page_label.set_halign(Gtk.Align.START)
                page_label.set_hexpand(True)
                box.append(page_label)
                row.set_child(box)
                nav.append(row)
                self._nav_rows[name] = row

        self.stack.connect("notify::visible-child", self._on_visible_child_changed)

    def _on_nav_row_selected(self, _nav, row):
        if self._nav_sync or row is None:
            return
        page = getattr(row, "_page", None)
        if page:
            self.stack.set_visible_child_name(page)

    def _on_visible_child_changed(self, _stack, _param):
        page = self.stack.get_visible_child_name()
        if page and page in self._nav_rows:
            self._nav_sync = True
            self._nav_list.select_row(self._nav_rows[page])
            self._nav_sync = False

    def _on_search_shortcut(self, *_args) -> bool:
        self.open_search()
        return True

    def open_search(self):
        dialog = SearchDialog(self.navigate_to)
        self._search_dialog = dialog  # keep a reference while it is open
        dialog.present(self)

    def navigate_to(self, page: str, query: str | None = None):
        self.stack.set_visible_child_name(page)
        if page == "shell":
            self.shell_page.set_search(query or "")
        elif query:
            # Unknown page with a query: fall back to the shell search.
            self.stack.set_visible_child_name("shell")
            self.shell_page.set_search(query)

    def _check_for_update(self):
        try:
            with urllib.request.urlopen(MANIFEST_URL, timeout=5) as resp:
                remote_manifest = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return  # No network, GitHub unreachable, etc. — check silently fails.

        remote_version = _parse_version(remote_manifest.get("version", ""))
        local_version = _parse_version(self.about_page.local_version)
        if remote_version > local_version:
            GLib.idle_add(self.update_btn.set_visible, True)

    def on_update_app(self, btn):
        # The header button is just a shortcut to the same update flow the
        # About page offers — no separate implementation to keep in sync.
        self.about_page.on_update_clicked(btn)