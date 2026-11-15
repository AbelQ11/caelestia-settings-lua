import pytest

from src import backup


@pytest.fixture()
def fake_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(backup, "HOME", home)
    monkeypatch.setattr(backup, "BACKUP_DIR", home / ".config" / "caelestia-settings" / "backups")
    return home


def test_backup_and_atomic_write(fake_home):
    target = fake_home / ".config" / "caelestia" / "hypr-user.lua"
    target.parent.mkdir(parents=True)
    target.write_text("old\n")

    backup_path = backup.atomic_write_text(target, "new\n")

    assert target.read_text() == "new\n"
    assert backup_path is not None and backup_path.exists()
    assert backup_path.read_text() == "old\n"
    assert target.with_name("hypr-user.lua.bak").read_text() == "old\n"

    entries = backup.list_backups()
    assert len(entries) == 1
    assert entries[0].target == target
    assert entries[0].backup == backup_path


def test_symlinked_config_keeps_the_link(fake_home):
    real = fake_home / "dotfiles" / "hypr-user.lua"
    real.parent.mkdir()
    real.write_text("old\n")
    link = fake_home / ".config" / "caelestia" / "hypr-user.lua"
    link.parent.mkdir(parents=True)
    link.symlink_to(real)

    backup.atomic_write_text(link, "new\n")

    assert link.is_symlink()
    assert real.read_text() == "new\n"


def test_no_backup_is_refused(fake_home, monkeypatch):
    target = fake_home / "config.lua"
    target.write_text("original\n")

    def fail(_path, required=True):
        raise backup.BackupError("no backup")

    monkeypatch.setattr(backup, "create_backup", fail)
    with pytest.raises(backup.BackupError):
        backup.atomic_write_text(target, "changed\n")

    assert target.read_text() == "original\n"


def test_retention_keeps_newest(fake_home, monkeypatch):
    target = fake_home / "config.lua"
    target.write_text("v0\n")
    monkeypatch.setattr(backup, "RETENTION", 3)

    counter = {"value": 0}

    def timestamp():
        counter["value"] += 1
        return f"20260101_00000{counter['value']}_000"

    monkeypatch.setattr(backup, "_timestamp", timestamp)
    for index in range(5):
        backup.create_backup(target)
        target.write_text(f"v{index + 1}\n")

    entries = backup.list_backups()
    assert len(entries) == 3


def test_retention_setting(fake_home, monkeypatch):
    monkeypatch.setattr(backup, "SETTINGS_FILE", fake_home / ".config" / "caelestia-settings" / "settings.json")
    assert backup.get_retention() == backup.RETENTION
    backup.set_retention(12)
    assert backup.get_retention() == 12
    backup.set_retention(0)
    assert backup.get_retention() == 1


def test_delete_backup(fake_home):
    target = fake_home / "config.lua"
    target.write_text("old\n")
    path = backup.create_backup(target)
    assert path is not None
    assert backup.delete_backup(path) is True
    assert not path.exists()
    assert backup.delete_backup(path) is False


def test_restore_is_also_backed_up(fake_home, monkeypatch):
    counter = {"value": 0}

    def timestamp():
        counter["value"] += 1
        return f"20260101_00000{counter['value']}_000"

    monkeypatch.setattr(backup, "_timestamp", timestamp)
    target = fake_home / "config.lua"
    target.write_text("first\n")
    backup_path = backup.create_backup(target)

    target.write_text("second\n")
    restored = backup.restore_backup(backup_path)

    assert restored == target
    assert target.read_text() == "first\n"
    # The restore backed up "second" before overwriting it.
    newest = backup.list_backups()[0]
    assert newest.backup.read_text() == "second\n"
