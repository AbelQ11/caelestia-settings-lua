# 01 — Backup system and English-only UI

Date: 2026-10-30

## Backup system (`src/backup.py`) — new

Every write to a user file now goes through one helper:

- `create_backup()` copies the file to
  `~/.config/caelestia-settings/backups/<mirrored path>/<file>.<timestamp>.bak`
  and to `<file>.bak` next to the source;
- `atomic_write_text()` / `atomic_write_bytes()` create the backup **first**, write
  to a temporary file in the same directory, `fsync`, then `os.replace()`;
- if the backup fails, the write is refused (`BackupError`);
- retention: last 50 backups per file;
- symlinked config files are resolved before writing, so dotfile-managed links are
  preserved rather than replaced by a regular file (the shell scripts use
  `sed --follow-symlinks` for the same reason).

`src/config.py` exposes `write_text()` which always uses the backup helper.
`src/shell_config.py`, Lua writers, monitor/workspace/rule/keybind writers and the
app's own JSON caches all use it.

The shell scripts also back up before editing: `doctor.sh`, `install.sh` and
`uninstall.sh` define `backup_file()` which writes both a timestamped sidecar and a
copy in the same `~/.config/caelestia-settings/backups/` store.

Added `Backups` page (`src/pages/backups.py`): list, preview and restore backups.
A restore backs up the current file first, so it is undoable.

## English-only

- `src/lang.py` is now an identity `t()`; the German translation table and locale
  detection were removed.
- Hard-coded German strings and comments were translated in General, Monitor,
  Workspaces, Wallpaper, Window Rules, Keybinds, Updates, About and Window.
- `manifest.json` uses `description` instead of `beschreibung`; `about.py` reads it.
- Legacy German managed markers are still recognised so old user files keep working.

## Tests

- `tests/test_backup.py` — backup creation, atomic write, refusal without backup,
  retention, restore-is-backed-up.
- `tests/test_shell_config.py` — every `set_many()` produces a backup.
