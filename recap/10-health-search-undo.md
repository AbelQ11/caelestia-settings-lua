# 10 — Health check, global search, change review and undo

Date: 2026-10-31

## Health check (`src/health.py`, `src/pages/health.py`)

New **Health** page in the sidebar. Checks:

- repository vs installed application version (catches a stale
  `~/.local/share/caelestia-settings` copy and tells the user to run `./install.sh`);
- installed `caelestia-shell` version vs the bundled schema tag;
- `hyprctl configerrors`;
- validity of the global and per-monitor `shell.json` files;
- unknown/outdated `shell.json` keys;
- wallpaper state and daemon conflict:
  - `hyprpaper` + Caelestia shell both running (the cause of one monitor going black),
  - missing wallpaper file,
  - shell not running;
- required/optional dependency executables;
- backup count and newest backup.

Repair actions (all backed up first):

- **Reapply wallpaper** (`caelestia wallpaper -f` / `-r`)
- **Disable hyprpaper** — comments out `hl.exec_cmd("hyprpaper")` in
  `hypr-user.lua`, stops the running process and restarts the shell
- **Clean unknown keys** — removes unknown keys from global and per-monitor
  `shell.json` in one pass
- **Restart Caelestia shell**
- **Reload Hyprland**
- **Open backup folder**

## Global search (`src/search.py`, `src/window.py`)

- `Ctrl+F` / `Ctrl+K` or the header search button opens a command-palette dialog.
- Searches all pages and every Caelestia shell option (label, path, section, group).
- Selecting a page navigates to it; selecting a shell option opens the Caelestia
  page with its search pre-filled.
- Row activation and Enter (first result) both navigate.

## Change review and undo (`src/pages/shell.py`, `src/shell_config.py`)

- The Caelestia page’s Apply button now opens **Review changes** with a diff of
  every pending global/per-monitor change before writing.
- `shell_config.apply_changes_tracked()` returns `{target: backup}`; the page
  keeps the mapping for the session.
- New **Undo last apply** button restores those backups (the restore itself is
  backed up) and restarts the shell.
- `apply_changes()` remains a boolean wrapper for existing callers/tests.

## Tests

- `tests/test_health.py` — version helpers, leaf-path collection, unknown-key
  detection, hyprpaper disable, unknown-key removal, wallpaper conflict/missing file.
- `tests/test_shell_config.py` — tracked apply returns a backup and skips no-op writes.

Total suite: **63 tests**.

## Docs

README updated with the Health page, global search, review/undo, shortcuts and
the new modules.
