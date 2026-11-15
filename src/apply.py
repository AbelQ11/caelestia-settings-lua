"""Write-and-reload with validation and automatic rollback.

Hyprland can accept a syntactically valid Lua file but still report config
errors after a reload.  This helper compares the errors before and after the
change; if the change introduced new errors, the previous file is restored and
the reload is repeated.
"""

from __future__ import annotations

from pathlib import Path

from src import backup, config


class ApplyError(RuntimeError):
    """Raised when a write produced new Hyprland configuration errors."""

    def __init__(self, errors: str):
        super().__init__(errors)
        self.errors = errors


def write_and_reload(path: Path, text: str, *, reload: bool = True) -> Path | None:
    """Atomically write ``text`` to ``path``, reload and roll back on new errors.

    Returns the backup path (``None`` when the file did not exist before).
    Raises :class:`ApplyError` after restoring the previous content.
    """

    path = Path(path)
    existed = path.exists()
    before_errors = config.hyprctl_config_errors() if reload else ""
    backup_path = backup.atomic_write_text(path, text)

    if not reload:
        return backup_path

    _ok, after_errors = config.reload_hyprland_checked()
    if after_errors and after_errors != before_errors:
        if backup_path is not None:
            backup.restore_backup(backup_path, path)
        elif not existed:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        config.reload_hyprland()
        raise ApplyError(after_errors)

    return backup_path
