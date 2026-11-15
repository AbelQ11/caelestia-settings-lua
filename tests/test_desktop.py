from pathlib import Path

from src import backup, desktop


def _setup(monkeypatch, tmp_path):
    apps = tmp_path / "applications"
    appimages = tmp_path / "Applications"
    monkeypatch.setattr(desktop, "USER_APP_DIR", apps)
    monkeypatch.setattr(desktop, "APPIMAGE_DIR", appimages)
    monkeypatch.setattr(desktop, "update_database", lambda: None)
    monkeypatch.setattr(backup, "HOME", tmp_path)
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    return apps, appimages


def test_install_and_remove_appimage(monkeypatch, tmp_path):
    apps, appimages = _setup(monkeypatch, tmp_path)
    source = tmp_path / "My App.AppImage"
    source.write_bytes(b"fake appimage")

    desktop_path, _errors = desktop.install_appimage(
        source,
        name="My App",
        categories="Utility;Development;",
        copy_to_applications=True,
    )

    assert apps.exists()
    copied = appimages / source.name
    assert copied.exists()
    assert copied.stat().st_mode & 0o111
    assert desktop_path.exists()
    content = desktop_path.read_text()
    assert "Name=My App" in content
    assert "X-Caelestia-Settings-Managed=true" in content
    assert f'Exec="{copied}" %U' in content
    assert "Categories=Utility;Development;" in content

    entries = desktop.managed_entries()
    assert len(entries) == 1
    assert entries[0]["name"] == "My App"
    assert entries[0]["appimage"] == str(copied)

    assert desktop.remove_entry(entries[0], delete_appimage=True) is True
    assert not desktop_path.exists()
    assert not copied.exists()
    assert desktop.managed_entries() == []


def test_install_appimage_keeps_original(monkeypatch, tmp_path):
    apps, appimages = _setup(monkeypatch, tmp_path)
    source = tmp_path / "Tool.AppImage"
    source.write_bytes(b"fake")

    desktop_path, _errors = desktop.install_appimage(
        source, name="Tool", copy_to_applications=False
    )
    assert apps.exists()
    content = desktop_path.read_text()
    assert f'Exec="{source}" %U' in content
    assert not appimages.exists()


def test_build_desktop_entry_extract_and_run():
    content = desktop.build_desktop_entry(
        name="Demo",
        exec_path=Path("/tmp/Demo.AppImage"),
        extract_and_run=True,
    )
    assert "--appimage-extract-and-run" in content
    assert "Categories=Utility;" in content
