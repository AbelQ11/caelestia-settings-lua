# 09 — Full Caelestia shell settings (schema-driven)

Date: 2026-10-30

## Goal

Expose every option in `~/.config/caelestia/shell.json` (caelestia-shell 2.5.0)
instead of only the handful of options used by the Wallpaper and Monitor pages.

## Schema generation

- New `scripts/gen_shell_schema.py` fetches the official “Example config” from
  the upstream README for a pinned tag (`v2.5.0`), extracts all defaults, reads
  enum values from `caelestia-config.qmltypes` (with a built-in fallback), and
  records the upstream per-monitor “ignored options” list.
- Generated `src/data/shell_schema.json`:
  - **279 options** across 16 sections;
  - default values, inferred widget kinds, enum mappings, global-only prefixes;
  - regeneration command documented in the README.
- New `src/shell_schema.py` flattens the tree into `Option` records with
  human-readable section/group/label names, enum values and global-only flags.

## New page: `src/pages/shell.py` ("Caelestia")

- Section sidebar: General, Appearance, Background, Bar, Borders, Dashboard,
  Launcher, Lock, Control centre, Notifications, OSD, Services, Session,
  Sidebar, Utilities, Paths.
- Search across labels, paths, sections and groups.
- Global / per-monitor scope. Options the shell only reads globally are
  disabled in monitor scope.
- Widgets:
  - switches for booleans;
  - spin buttons with sensible ranges for integers/floats;
  - entries for strings;
  - combo boxes for enums (`clockFormat`, units, workspace display,
    notification fullscreen, …);
  - expandable editors for string lists (apps, ignored tags, commands, …);
  - validated JSON editor for list-of-object values (bar entries, status icons,
    quick toggles, launcher actions, idle timeouts, battery warnings, player
    aliases, workspace/window icons, VPN providers).
- Staged changes: nothing is written until **Apply**; all affected values are
  written in one pass, with one backup per file and one shell restart.
- Values equal to the default (global scope) or to the global value (monitor
  scope) are removed rather than written, keeping `shell.json` minimal.
- Per-row reset and “Reset section” remove overrides; empty nested objects are
  pruned automatically.
- Row reset buttons only appear for keys actually overridden in the current
  scope.

## `shell_config.py`

- `apply_changes()` writes staged changes and resets for one scope in a single
  atomic, backed-up operation.
- `set_many()` accepts `restart=False`, and `save_global()`/`save_monitor()`
  gained restart flags so a page can batch updates.
- Deleting a dotted key now prunes empty parent objects.

## Tests

- `tests/test_shell_schema.py` — option count, defaults, enums, global-only
  prefixes, labels.
- `tests/test_shell_config.py` — `apply_changes`, reset pruning, backups.
- Sandbox test of `ShellPage` staging/apply/reset across global and per-monitor
  scopes.

Total suite: **54 tests**.
