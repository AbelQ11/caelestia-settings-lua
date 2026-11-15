# 08 — Version 2.0.0, tests, CI and documentation

Date: 2026-10-30

## Version

- `manifest.json` → `2.0.0`, English `description` key.
- `app_update.sh` now clones `AbelQ11/caelestia-settings-lua` (branch `dev`)
  instead of the old `.conf` repository.
- `main.py` window update check points at this fork's `manifest.json`.
- `Update.sh` rewritten in English and uses `caelestia update` when available.

## Optional Rust core

- `window_rules.py` and `fans.py` no longer import `caelestia_core`
  unconditionally.
- Python fallbacks exist for conflict detection and PWM conversion, so the app
  starts without the extension.
- `install.sh` still builds `caelestia_core` when Rust is available.

## Tests

Added:
- `tests/test_lua.py` — Lua parser/writer and managed blocks
- `tests/test_backup.py` — backup/atomic write/retention/restore
- `tests/test_shell_config.py` — shell.json merge and per-monitor overrides
- `tests/test_keybinds.py` — custom bind parsing and writing
- `tests/test_writers.py` — monitor/workspace/window-rule save behaviour

Updated:
- `tests/test_lua_config.py` — managed input block instead of direct `input.lua`
  writes, comment-aware rule parsing, monitor extra-field preservation.

Result: **103 tests passing** (shell settings in recap 09, health/search/undo in
recap 10, audio/Bluetooth in recap 11, visual preview in recap 12, input/theming/UI
tests in recap 13, launcher actions/interactions in recap 14, validated
writes/autostart/uninstall in recap 15, default apps/power/backups in recap 16,
animated wallpaper folder in recap 17, recording/action menu/AppImage in recap 18,
sidebar/icon/window rules in recap 19, network page in recap 20,
monitor/audio/associations/retention in recap 21, packaging in recap 22,
Bluetooth/CI/release in recap 23).

## CI

`.github/workflows/ci.yml` now installs GTK4/libadwaita typelibs and
`pytest`, then runs `python3 -m pytest tests -q` (the old `unittest discover`
did not collect the pytest-style tests).

## Documentation

- `README.md` fully rewritten for 2.0.0: features, backup policy, new pages,
  correct config paths, dependencies, architecture.
- `recap/` created with one file per modification (this folder).
