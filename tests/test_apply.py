import pytest

from src import apply, backup, config


@pytest.fixture()
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "HOME", tmp_path)
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "reload_hyprland", lambda: True)
    return tmp_path


def test_write_and_reload_rolls_back_new_errors(sandbox, monkeypatch):
    target = sandbox / "hypr-user.lua"
    target.write_text("old\n")
    errors = iter(["", "line 1: bad option"])
    monkeypatch.setattr(config, "hyprctl_config_errors", lambda: next(errors))

    with pytest.raises(apply.ApplyError):
        apply.write_and_reload(target, "new\n")

    assert target.read_text() == "old\n"


def test_write_and_reload_accepts_clean_reload(sandbox, monkeypatch):
    target = sandbox / "hypr-user.lua"
    target.write_text("old\n")
    errors = iter(["", ""])
    monkeypatch.setattr(config, "hyprctl_config_errors", lambda: next(errors))

    backup_path = apply.write_and_reload(target, "new\n")

    assert target.read_text() == "new\n"
    assert backup_path is not None
    assert backup_path.read_text() == "old\n"


def test_write_and_reload_ignores_preexisting_errors(sandbox, monkeypatch):
    target = sandbox / "hypr-user.lua"
    target.write_text("old\n")
    errors = iter(["existing error", "existing error"])
    monkeypatch.setattr(config, "hyprctl_config_errors", lambda: next(errors))

    apply.write_and_reload(target, "new\n")

    assert target.read_text() == "new\n"


def test_write_without_reload(sandbox, monkeypatch):
    target = sandbox / "hypr-user.lua"
    target.write_text("old\n")

    def fail():
        raise AssertionError("should not check errors")

    monkeypatch.setattr(config, "hyprctl_config_errors", fail)

    apply.write_and_reload(target, "new\n", reload=False)
    assert target.read_text() == "new\n"
