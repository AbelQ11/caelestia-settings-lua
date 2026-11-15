import json

import pytest

from src import backup, health, shell_config


@pytest.fixture()
def shell_env(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    shell_json = home / ".config" / "caelestia" / "shell.json"
    monitors = home / ".config" / "caelestia" / "monitors"
    monkeypatch.setattr(shell_config, "SHELL_JSON", shell_json)
    monkeypatch.setattr(shell_config, "MONITOR_SHELL_DIR", monitors)
    monkeypatch.setattr("src.health.MONITOR_SHELL_DIR", monitors)
    monkeypatch.setattr(backup, "HOME", home)
    monkeypatch.setattr(backup, "BACKUP_DIR", home / ".config" / "caelestia-settings" / "backups")
    return {"home": home, "shell": shell_json, "monitors": monitors}


def test_version_helpers():
    assert health._version("v2.5.0") == (2, 5, 0)
    assert health._version("caelestia-shell 2.5.0") == (2, 5, 0)
    assert health._same_version("2.5.0", "v2.5.0") is True
    assert health._same_version("2.5.0", "2.6.0") is False


def test_collect_leaf_paths():
    data = {
        "bar": {"persistent": True, "workspaces": {"shown": 5}},
        "paths": {"wallpaperDir": ""},
        "enabled": True,
    }
    assert set(health.collect_leaf_paths(data)) == {
        "bar.persistent",
        "bar.workspaces.shown",
        "paths.wallpaperDir",
        "enabled",
    }


def test_unknown_shell_keys(shell_env):
    shell_env["shell"].parent.mkdir(parents=True)
    shell_env["shell"].write_text(
        json.dumps(
            {
                "bar": {"persistent": False, "notARealOption": 1},
                "services": {"useFahrenheit": True},
            }
        )
    )
    monitor = shell_env["monitors"] / "DP-1" / "shell.json"
    monitor.parent.mkdir(parents=True)
    monitor.write_text(json.dumps({"background": {"desktopClock": {"nope": 1}}}))

    unknown = health.unknown_shell_keys()
    assert "bar.notARealOption" in unknown[""]
    assert "services.useFahrenheit" in unknown[""]
    assert unknown["DP-1"] == ["background.desktopClock.nope"]


def test_unknown_keys_check_status(shell_env):
    shell_env["shell"].parent.mkdir(parents=True)
    shell_env["shell"].write_text(json.dumps({"bar": {"persistent": False}}))
    result = health.unknown_keys_check()
    assert result.status == "ok"

    shell_env["shell"].write_text(json.dumps({"bar": {"persistent": False, "bad": True}}))
    result = health.unknown_keys_check()
    assert result.status == "warning"


def test_disable_hyprpaper_comments_autostart(monkeypatch, tmp_path):
    user_lua = tmp_path / "hypr-user.lua"
    user_lua.write_text(
        'hl.on("hyprland.start", function()\n'
        '    hl.exec_cmd("hyprpaper")\n'
        "end)\n"
    )
    monkeypatch.setattr(health, "HYPR_USER_LUA", user_lua)
    monkeypatch.setattr(health, "write_text", lambda p, t: p.write_text(t))
    monkeypatch.setattr(health, "restart_caelestia", lambda: True)

    class Result:
        returncode = 0

    monkeypatch.setattr(health.subprocess, "run", lambda *a, **k: Result())

    edited, stopped = health.disable_hyprpaper()
    assert edited is True
    assert stopped is True
    text = user_lua.read_text()
    assert '--     hl.exec_cmd("hyprpaper")' in text
    assert "disabled by Caelestia Settings" in text


def test_remove_unknown_keys(monkeypatch):
    calls = []
    monkeypatch.setattr(
        health.shell_config,
        "apply_changes_tracked",
        lambda changes, resets, monitor=None, restart=True: (
            calls.append((changes, set(resets), monitor)) or (True, {})
        ),
    )
    monkeypatch.setattr(health, "restart_caelestia", lambda: True)

    removed = health.remove_unknown_keys({"": ["services.useFahrenheit"], "DP-1": ["bar.bad"]})
    assert removed == 2
    assert calls[0][0] == {}
    assert calls[0][1] == {"services.useFahrenheit"}
    assert calls[0][2] is None
    assert calls[1][2] == "DP-1"


def test_wallpaper_conflict(monkeypatch, tmp_path):
    state = tmp_path / "path.txt"
    wallpaper = tmp_path / "wall.jpg"
    wallpaper.write_bytes(b"x")
    state.write_text(str(wallpaper))
    monkeypatch.setattr(health, "_WALLPAPER_STATE", state)
    monkeypatch.setattr(health, "_pgrep", lambda pattern, exact=False: True)

    result = health.wallpaper_check()
    assert result.status == "warning"
    assert "hyprpaper" in result.detail.lower()


def test_wallpaper_missing_file(monkeypatch, tmp_path):
    state = tmp_path / "path.txt"
    state.write_text(str(tmp_path / "gone.jpg"))
    monkeypatch.setattr(health, "_WALLPAPER_STATE", state)
    monkeypatch.setattr(health, "_pgrep", lambda pattern, exact=False: False)

    result = health.wallpaper_check()
    assert result.status == "error"
