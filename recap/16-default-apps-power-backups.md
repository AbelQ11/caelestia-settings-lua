# 16 — Default apps, Power, backup diff/delete and advanced workspace rules

Date: 2026-10-31

## Default apps page

`src/pages/default_apps.py`:

- Caelestia shell applications (`general.apps.terminal/audio/playback/explorer`)
  written to `shell.json`;
- Hyprland commands (`terminal`, `browser`, `editor`, `fileExplorer`) written as
  overrides to `hypr-vars.lua` through the validated apply helper;
- commands are shell-quoted on display and parsed with `shlex` on apply;
- one Apply covers both layers (Hyprland reload, then shell restart).

## Power page

`src/pages/power.py`:

- power profile selection via `powerprofilesctl` (detects available profiles,
  falls back to the standard three);
- battery charge, plugged state and estimated time via psutil or sysfs;
- Caelestia idle switches (`lockBeforeSleep`, `inhibitWhenAudio`,
  `inhibitWhenCharging`) written to `shell.json`;
- shortcut button to the full idle-timeout / battery-warning options on the
  Caelestia page.

## Backup improvements

`src/pages/backups.py` + `src/backup.py`:

- unified **diff** between a backup and the current file;
- delete an individual backup (with confirmation);
- **Backup now** button creates fresh backups for shell.json, hypr-user.lua,
  hypr-vars.lua, monitors.lua, execs.lua and every per-monitor shell.json;
- new `backup.delete_backup()` helper.

## Advanced workspace rules

`src/pages/workspaces.py`:

- per-workspace Advanced dialog for inner/outer gaps, layout, no-rounding,
  no-border, no-shadow and decorate;
- fields are preserved/emitted in the managed `hl.workspace_rule` block;
- parsed back from `monitors.lua` by `src/config.py`.

## Tests

- `tests/test_backup.py` — delete backup.
- UI smoke test includes Default apps and Power pages.
- Total suite: **88 tests**.

## Docs

README updated for the new pages, backup actions and advanced workspace options.
