import json
from pathlib import Path

import pytest

from src import backup, shell_config


@pytest.fixture()
def shell_env(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    shell_json = home / ".config" / "caelestia" / "shell.json"
    monitors_dir = home / ".config" / "caelestia" / "monitors"
    monkeypatch.setattr(shell_config, "SHELL_JSON", shell_json)
    monkeypatch.setattr(shell_config, "MONITOR_SHELL_DIR", monitors_dir)
    monkeypatch.setattr(shell_config, "restart_caelestia", lambda: True)
    monkeypatch.setattr(backup, "HOME", home)
    monkeypatch.setattr(backup, "BACKUP_DIR", home / ".config" / "caelestia-settings" / "backups")
    return {"home": home, "shell": shell_json, "monitors": monitors_dir}


def test_global_and_per_monitor_merge(shell_env):
    shell_config.set_many(
        {
            "bar.persistent": True,
            "background.desktopClock.enabled": True,
            "background.desktopClock.scale": 1.0,
        }
    )
    shell_config.set_many({"bar.persistent": False}, monitor="DP-1")

    assert shell_config.get("bar.persistent") is True
    assert shell_config.get("bar.persistent", monitor="DP-1") is False
    assert shell_config.get("background.desktopClock.enabled", monitor="DP-1") is True

    data = json.loads(shell_env["shell"].read_text())
    assert data["bar"]["persistent"] is True
    global_monitor = shell_env["monitors"] / "DP-1" / "shell.json"
    assert json.loads(global_monitor.read_text())["bar"]["persistent"] is False


def test_delete_value(shell_env):
    shell_config.set_many({"bar.persistent": False})
    assert shell_config.delete_value("bar.persistent") is True
    assert shell_config.get("bar.persistent") is True  # falls back to the default


def test_wallpaper_dir_from_config(shell_env, monkeypatch):
    monkeypatch.setattr(shell_config, "_pictures_dir", lambda: Path("/home/user/Pictures"))
    assert shell_config.wallpaper_dir() == Path("/home/user/Pictures/Wallpapers")

    shell_config.set_many({"paths.wallpaperDir": "~/Walls"})
    assert shell_config.wallpaper_dir() == Path.home() / "Walls"


def test_every_write_creates_a_backup(shell_env):
    shell_config.set_many({"bar.persistent": False})
    shell_config.set_many({"bar.persistent": True})
    entries = backup.list_backups()
    assert any(entry.target == shell_env["shell"] for entry in entries)


def test_apply_changes_and_reset_prunes_empty_dicts(shell_env):
    changed = shell_config.apply_changes(
        {
            "background.desktopClock.enabled": True,
            "background.desktopClock.shadow.enabled": False,
            "bar.workspaces.shown": 7,
        },
        restart=False,
    )
    assert changed is True
    assert shell_config.get("background.desktopClock.enabled") is True
    assert shell_config.get("background.desktopClock.shadow.enabled") is False

    changed = shell_config.apply_changes(
        {},
        {"background.desktopClock.shadow.enabled", "bar.workspaces.shown"},
        restart=False,
    )
    assert changed is True
    data = json.loads(shell_env["shell"].read_text())
    assert "bar" not in data
    assert "shadow" not in data["background"]["desktopClock"]
    assert data["background"]["desktopClock"]["enabled"] is True

    assert shell_config.apply_changes({}, {"missing.path"}, restart=False) is False


def test_apply_changes_tracked_returns_backup(shell_env):
    shell_env["shell"].parent.mkdir(parents=True)
    shell_env["shell"].write_text("{}\n")
    changed, backups = shell_config.apply_changes_tracked(
        {"bar.persistent": False}, restart=False
    )
    assert changed is True
    assert shell_env["shell"] in backups
    backup_path = backups[shell_env["shell"]]
    assert backup_path.exists()
    assert json.loads(backup_path.read_text()) == {}

    changed, backups = shell_config.apply_changes_tracked({}, restart=False)
    assert changed is False
    assert backups == {}

