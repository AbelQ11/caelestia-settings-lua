"""Backup and atomic-write helpers.

Every write the app performs to a user configuration file goes through
:func:`atomic_write_text`.  The contract is deliberately strict:

* a timestamped copy is created **before** the file is replaced;
* the new content is written to a temporary file in the same directory and
  moved into place with :func:`os.replace` (atomic on POSIX);
* if the backup cannot be created the write is refused, so we never mutate a
  file we could not restore.

Backups live under ``~/.config/caelestia-settings/backups`` mirroring the
original path, e.g.::

    ~/.config/caelestia-settings/backups/dot-config-caelestia/hypr-user.lua.20261030_214512_123.bak

A convenience copy next to the source file (``<name>.bak``) is kept as well,
so a user can recover with a file manager without digging through the backup
folder.  The last :data:`RETENTION` timestamped backups per file are kept.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "caelestia-settings"
BACKUP_DIR = CONFIG_DIR / "backups"

#: How many timestamped backups to keep per source file.
RETENTION = 50
SETTINGS_FILE = CONFIG_DIR / "settings.json"

_TIMESTAMP_RE = re.compile(r"^(?P<name>.+)\.(?P<stamp>\d{8}_\d{6}(?:_\d{3})?)\.bak$")


class BackupError(RuntimeError):
    """Raised when a backup is required but could not be created."""


@dataclass(frozen=True)
class BackupEntry:
    backup: Path
    target: Path
    timestamp: datetime

    @property
    def size(self) -> int:
        try:
            return self.backup.stat().st_size
        except OSError:
            return 0


def get_retention() -> int:
    try:
        import json

        if SETTINGS_FILE.exists():
            value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("backup_retention")
            if isinstance(value, int) and value > 0:
                return value
    except (OSError, ValueError, TypeError):
        pass
    return RETENTION


def set_retention(value: int) -> None:
    import json

    value = max(1, min(int(value), 1000))
    data = {}
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
    except (OSError, ValueError):
        data = {}
    data["backup_retention"] = value
    atomic_write_text(SETTINGS_FILE, json.dumps(data, indent=2) + "\n")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _relative_to_home(path: Path) -> Path:
    try:
        return path.resolve().relative_to(HOME.resolve())
    except ValueError:
        # Files outside $HOME (unusual, but possible) still get a stable slot.
        return Path("external") / path.name


def _backup_dir_for(path: Path) -> Path:
    return BACKUP_DIR / _relative_to_home(Path(path)).parent


def backup_path_for(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    return _backup_dir_for(path) / f"{path.name}.{_timestamp()}.bak"


def create_backup(path: Path, *, required: bool = True) -> Path | None:
    """Copy ``path`` to the backup store and to ``<path>.bak``.

    Returns the timestamped backup path, or ``None`` when the source does not
    exist (nothing to back up).  Raises :class:`BackupError` when the copy
    fails and ``required`` is true.
    """

    path = Path(path)
    # Resolve symlinks so we update the target instead of replacing the link
    # (dotfile managers commonly symlink ~/.config files).
    if path.is_symlink():
        path = path.resolve()
    if not path.exists():
        return None

    dest = backup_path_for(path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        # Sidecar copy for quick manual recovery.
        shutil.copy2(path, path.with_name(f"{path.name}.bak"))
    except OSError as exc:
        if required:
            raise BackupError(f"Could not back up {path}: {exc}") from exc
        return None

    _prune(path)
    return dest


def _prune(path: Path) -> None:
    directory = _backup_dir_for(path)
    prefix = f"{path.name}."
    try:
        candidates = sorted(
            p for p in directory.iterdir() if p.name.startswith(prefix) and p.name.endswith(".bak")
        )
    except OSError:
        return
    for old in candidates[:-get_retention()]:
        try:
            old.unlink()
        except OSError:
            pass


def atomic_write_text(path: Path, content: str, *, backup: bool = True) -> Path | None:
    """Atomically replace ``path`` with ``content`` after creating a backup.

    Returns the backup path (or ``None`` when there was no previous file).
    The backup is made *before* the temporary file is created, so a failure
    while writing leaves both the original and its backup intact.
    """

    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    backup_path = create_backup(path, required=True) if backup else None

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            try:
                shutil.copymode(path, tmp_name)
            except OSError:
                pass
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return backup_path


def atomic_write_bytes(path: Path, content: bytes, *, backup: bool = True) -> Path | None:
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    backup_path = create_backup(path, required=True) if backup else None

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            try:
                shutil.copymode(path, tmp_name)
            except OSError:
                pass
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return backup_path


def decode_backup_path(backup: Path) -> tuple[Path, datetime] | None:
    """Turn a backup path back into ``(original target, timestamp)``."""

    backup = Path(backup)
    match = _TIMESTAMP_RE.match(backup.name)
    if not match:
        return None
    raw_stamp = match.group("stamp")
    fmt = "%Y%m%d_%H%M%S_%f" if raw_stamp.count("_") == 2 else "%Y%m%d_%H%M%S"
    try:
        stamp = datetime.strptime(raw_stamp, fmt)
    except ValueError:
        return None
    try:
        relative = backup.parent.relative_to(BACKUP_DIR)
    except ValueError:
        return None
    if relative.parts and relative.parts[0] == "external":
        return None
    return HOME / relative / match.group("name"), stamp


def list_backups() -> list[BackupEntry]:
    """All timestamped backups, newest first."""

    if not BACKUP_DIR.exists():
        return []
    entries: list[BackupEntry] = []
    for candidate in BACKUP_DIR.rglob("*.bak"):
        decoded = decode_backup_path(candidate)
        if decoded is None:
            continue
        target, stamp = decoded
        entries.append(BackupEntry(backup=candidate, target=target, timestamp=stamp))
    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
    return entries


def delete_backup(backup: Path) -> bool:
    """Delete one timestamped backup file. Returns ``True`` if it existed."""

    backup = Path(backup)
    try:
        backup.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise BackupError(f"Could not delete {backup}: {exc}") from exc


def restore_backup(backup: Path, target: Path | None = None) -> Path:
    """Restore ``backup`` over its target, backing up the current file first."""

    backup = Path(backup)
    if not backup.exists():
        raise BackupError(f"Backup not found: {backup}")

    if target is None:
        decoded = decode_backup_path(backup)
        if decoded is None:
            raise BackupError(f"Cannot determine the target of {backup}")
        target = decoded[0]

    data = backup.read_bytes()
    atomic_write_bytes(target, data, backup=True)
    return target
