"""Interaction tests for key pages (require a display, skipped otherwise)."""

from types import SimpleNamespace

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk  # noqa: E402

from src import backup, devices, shell_config, shell_schema  # noqa: E402
from src.action_menu import ActionMenuButton, builtin_actions  # noqa: E402
from src.pages import autostart, input_devices  # noqa: E402
from src.pages.keybinds import KeybindDialog  # noqa: E402
from src.pages.shell import ShellPage  # noqa: E402
from src.search import SearchDialog  # noqa: E402
from src.shortcut import ShortcutCaptureDialog  # noqa: E402

pytestmark = pytest.mark.skipif(
    Gdk.Display.get_default() is None, reason="no display available"
)


class FakeMain:
    def __init__(self):
        self.about_page = SimpleNamespace(local_version="2.0.0")
        self.stack = SimpleNamespace(set_visible_child_name=lambda _name: None)
        self.toasts = []

    def add_toast(self, toast):
        self.toasts.append(toast)


@pytest.fixture(scope="module")
def app():
    application = Adw.Application(application_id="org.caelestia.settings.interactions")
    application.register(None)
    return application


def _isolate(monkeypatch, tmp_path):
    shell_json = tmp_path / "shell.json"
    monitors = tmp_path / "monitors"
    monkeypatch.setattr(shell_config, "SHELL_JSON", shell_json)
    monkeypatch.setattr(shell_config, "MONITOR_SHELL_DIR", monitors)
    monkeypatch.setattr(shell_config, "restart_caelestia", lambda: True)
    monkeypatch.setattr("src.pages.shell.restart_caelestia", lambda: True)
    monkeypatch.setattr(backup, "HOME", tmp_path)
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    return shell_json


def test_shell_apply_and_undo(app, monkeypatch, tmp_path):
    shell_json = _isolate(monkeypatch, tmp_path)
    shell_json.write_text('{"bar": {"persistent": false}}\n')

    page = ShellPage(FakeMain())
    option = next(
        item for item in shell_schema.options() if item.path == "bar.workspaces.shown"
    )
    page._stage(option, 9)

    plan = page._build_plan()
    assert plan
    assert plan[0]["changes"]["bar.workspaces.shown"] == 9

    page._apply_plan(plan)
    assert '"shown": 9' in shell_json.read_text()
    assert page._last_apply

    page._on_undo_last_apply(None)
    assert shell_json.read_text().strip() == '{"bar": {"persistent": false}}'


def test_input_devices_apply(app, monkeypatch, tmp_path):
    user_lua = tmp_path / "hypr-user.lua"
    user_lua.write_text("local config = {}\n\nreturn config\n")
    monkeypatch.setattr(input_devices, "HYPR_USER_LUA", user_lua)
    monkeypatch.setattr(
        input_devices.apply, "write_and_reload", lambda path, text, **kwargs: path.write_text(text)
    )
    monkeypatch.setattr(
        input_devices.devices,
        "list_devices",
        lambda: [devices.Device("mouse", "pointer", "0x1")],
    )
    monkeypatch.setattr(input_devices.devices, "global_defaults", lambda: {})
    monkeypatch.setattr(input_devices.devices, "load_overrides", lambda: {})

    page = input_devices.InputDevicesPage(FakeMain())
    page._values["mouse"]["sensitivity"] = 0.5
    page._on_apply(None)

    text = user_lua.read_text()
    assert "BEGIN Caelestia Settings: input devices" in text
    assert 'name = "mouse"' in text
    assert "sensitivity = 0.5" in text


def test_autostart_apply(app, monkeypatch, tmp_path):
    user_lua = tmp_path / "hypr-user.lua"
    user_lua.write_text("local config = {}\n\nreturn config\n")
    monkeypatch.setattr(autostart, "HYPR_USER_LUA", user_lua)
    monkeypatch.setattr(
        autostart.apply, "write_and_reload", lambda path, text, **kwargs: path.write_text(text)
    )

    page = autostart.AutostartPage(FakeMain())
    page._commands = ["caelestia shell -d", "hyprpaper"]
    page._on_apply(None)

    text = user_lua.read_text()
    assert "BEGIN Caelestia Settings: autostart" in text
    assert 'hl.exec_cmd("caelestia shell -d")' in text
    assert 'hl.exec_cmd("hyprpaper")' in text
    assert text.index("BEGIN Caelestia Settings") < text.index("return config")


def test_keybind_action_menu_and_recorder(app):
    selected = []
    button = ActionMenuButton(selected.append)
    action = builtin_actions()[0]
    button._choose(None, action)
    assert selected == [action]
    assert button.selected == action

    dialog = KeybindDialog(None)
    dialog._on_action_selected(action)
    assert dialog._disp_combo.get_active_id() == action.dispatcher
    assert dialog._arg_entry.get_text() == action.argument

    dialog._apply_combo("CTRL + SHIFT + T")
    data = dialog.get_data()
    assert data["modifier"] == "CTRL + SHIFT"
    assert data["key"] == "T"


def test_shortcut_capture_dialog(app):
    captured = []
    dialog = ShortcutCaptureDialog(captured.append)

    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    state = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SUPER_MASK
    dialog._on_key(None, Gdk.KEY_t, 0, state)
    dialog._on_use_clicked(None)
    assert captured == ["CTRL + SUPER + T"]


def test_search_dialog_filters_and_navigates(app, monkeypatch):
    monkeypatch.setattr(SearchDialog, "close", lambda self: None)
    seen = []
    dialog = SearchDialog(lambda page, query: seen.append((page, query)))
    dialog._entry.set_text("gpu")
    dialog._populate()

    assert ("shell", "services.gpuType") in dialog._results
    dialog._on_activated(None, "shell", "services.gpuType")
    assert seen == [("shell", "services.gpuType")]
