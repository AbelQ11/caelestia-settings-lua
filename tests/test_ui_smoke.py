"""Lightweight UI smoke test: construct every page once.

Skipped automatically when no display is available (for example a bare CI
runner without Xvfb).  Run with ``xvfb-run -a python -m pytest tests`` to
exercise it in CI.
"""

from types import SimpleNamespace

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from src.pages.about import AboutPage  # noqa: E402
from src.pages.applications import ApplicationsPage  # noqa: E402
from src.pages.audio import AudioPage  # noqa: E402
from src.pages.autostart import AutostartPage  # noqa: E402
from src.pages.backups import BackupsPage  # noqa: E402
from src.pages.bluetooth import BluetoothPage  # noqa: E402
from src.pages.default_apps import DefaultAppsPage  # noqa: E402
from src.pages.fans import FansPage  # noqa: E402
from src.pages.general import GeneralPage  # noqa: E402
from src.pages.health import HealthPage  # noqa: E402
from src.pages.home import HomePage  # noqa: E402
from src.pages.hyprland import HyprlandPage  # noqa: E402
from src.pages.input_devices import InputDevicesPage  # noqa: E402
from src.pages.keybinds import KeybindsPage  # noqa: E402
from src.pages.monitor import MonitorPage  # noqa: E402
from src.pages.network import NetworkPage  # noqa: E402
from src.pages.power import PowerPage  # noqa: E402
from src.pages.shell import ShellPage  # noqa: E402
from src.pages.theming import ThemingPage  # noqa: E402
from src.pages.updates import UpdatePage  # noqa: E402
from src.pages.wallpaper import WallpaperPage  # noqa: E402
from src.pages.wifi import WifiPage  # noqa: E402
from src.pages.window_rules import WindowRulesPage  # noqa: E402
from src.pages.workspaces import WorkspacesPage  # noqa: E402

PAGE_CLASSES = [
    HomePage,
    GeneralPage,
    InputDevicesPage,
    DefaultAppsPage,
    ApplicationsPage,
    ShellPage,
    ThemingPage,
    WallpaperPage,
    HyprlandPage,
    AutostartPage,
    WorkspacesPage,
    MonitorPage,
    NetworkPage,
    WifiPage,
    BluetoothPage,
    AudioPage,
    WindowRulesPage,
    KeybindsPage,
    FansPage,
    PowerPage,
    UpdatePage,
    BackupsPage,
    HealthPage,
    AboutPage,
]


class FakeMain:
    def __init__(self):
        self.about_page = SimpleNamespace(local_version="2.0.0")
        self.toasts = []
        self.stack = None

    def add_toast(self, toast):
        self.toasts.append(toast)


@pytest.mark.skipif(Gdk.Display.get_default() is None, reason="no display available")
def test_pages_construct():
    app = Adw.Application(application_id="org.caelestia.settings.uitest")
    app.register(None)
    main = FakeMain()

    for page_class in PAGE_CLASSES:
        page = page_class(main)
        assert isinstance(page, Gtk.Widget), page_class.__name__
        page.unparent()

    app.quit()
