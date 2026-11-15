# 02 — Lua configuration core

Date: 2026-10-30

## New module: `src/lua.py`

Dependency-free Lua reader/writer (no Lua interpreter is executed):

- `parse_table()` — tables, nested tables, arrays, booleans, numbers, strings,
  comments and raw expressions (e.g. `"rgba(" .. scheme.primary .. "e6)"`);
- `iter_calls()` — `hl.monitor({...})`, `hl.workspace_rule({...})`,
  `hl.window_rule({...})`, `hl.bind(...)`, `hl.config({...})`;
- `replace_managed_block()` / `remove_managed_block()` / `strip_managed_block()` —
  marker-guarded sections (`-- BEGIN Caelestia Settings: <id>`);
- `set_table_values()` / `remove_table_values()` / `read_table_values()` —
  line-preserving updates to `return { ... }` variable tables;
- `format_value()` / `format_key()` — renders Lua, including bracket keys such as
  `["tap-to-click"]`.

## `src/config.py` rewritten

- Correct paths for Hyprland 0.55+ / Caelestia 2.x.
- `parse_monitors_conf()` returns monitors and workspace rules, including extra
  monitor fields (`cm`, `bitdepth`, `vrr`, `mirror`) and special workspaces.
- `parse_rules_conf()` reads `rules.lua` + `hypr-user.lua`, understands multiline
  `hl.window_rule` tables, `match` tables, managed blocks and legacy markers.
- `reload_hyprland()` and `restart_caelestia()` helpers.
- Rust `caelestia_core` is now optional.

## `src/shell_config.py` — new

- Global + per-monitor `shell.json` deep merge.
- Dotted get/set/delete and `set_many()` (one backup + one shell restart).
- Wallpaper directory resolution (`paths.wallpaperDir`, XDG pictures dir,
  `~/Pictures/Wallpapers` fallback).

## Tests

- `tests/test_lua.py` — nested tables, arrays, comment skipping, managed blocks,
  value roundtrip, bracket keys.
- `tests/test_shell_config.py` — merge, delete, wallpaper path, backups.
