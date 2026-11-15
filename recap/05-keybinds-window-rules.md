# 05 — Keybinds and Window Rules

Date: 2026-10-30

## Keybinds — rewritten

The old page wrote to `~/.config/hypr/keybinds.lua`, which nothing loads.
The new page has three tabs:

1. **Caelestia shortcuts**
   - Reads `variables.lua` defaults and `hypr-vars.lua` overrides.
   - All `kb*` variables (terminal, browser, workspaces, window actions, media, …)
     are editable.
   - Only overrides are written to `hypr-vars.lua`; `variables.lua` is untouched.
   - “Remove override” restores the Caelestia default.
2. **Custom shortcuts**
   - Reads `config.binds` from `hypr-user.lua` and the managed `hl.bind` block.
   - Add/edit/delete works for both sources; managed binds are written to a marked
     block before `return config`.
3. **Active binds**
   - Read-only list from `hyprctl binds -j`, with decoded modifier masks.

Other additions:
- Key recorder: press the shortcut in the dialog to fill modifier/key.
- Search and filters.
- Every save reloads Hyprland and creates a backup.

## Window Rules

- Removed the unconditional `import caelestia_core` (the Rust core is optional;
  Python conflict detection is used when it is absent).
- Rules are written to a managed `-- BEGIN Caelestia Settings: window rules`
  block in `hypr-user.lua`; legacy German blocks are cleaned up automatically.
- New match types: `class`, `initial_class`, `title`, `initial_title`.
- Hand-written rules remain visible and are not duplicated.
- Backups and English messages throughout.

## Tests

- `tests/test_keybinds.py` — managed binds, `config.binds`, flags roundtrip,
  backup-aware writer.
- `tests/test_writers.py::test_window_rules_save_uses_managed_block` — managed
  block placement, legacy marker cleanup.
