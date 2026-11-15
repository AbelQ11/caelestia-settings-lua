# 14 — Visual launcher actions and interaction tests

Date: 2026-10-31

## Visual launcher-actions editor

`src/pages/shell.py` renders `launcher.actions` as a proper editor instead of JSON:

- list of actions with icon, name, description and command
- add / edit / delete
- reorder with up/down buttons
- edit dialog: name, icon, description, command (shell-quoted and parsed with
  `shlex`), enabled and dangerous switches
- unknown keys on existing actions are preserved
- all changes are staged until the normal Review & apply flow

## Interaction tests

`tests/test_ui_interactions.py` (skipped automatically without a display):

- **ShellPage apply/undo**: stages a value, builds the plan, applies it, verifies
  the written `shell.json`, then undoes the last apply and verifies the original.
- **InputDevicesPage apply**: writes a managed `hl.device` block with a changed
  sensitivity and verifies the generated Lua.
- **SearchDialog**: filters for “gpu” and navigates to the matching shell option.

Together with `tests/test_ui_smoke.py` (constructs every page), this covers the
main interaction paths without touching real user configuration.

## Tests

Total suite: **79 tests**.

## Docs

README updated (launcher-action editor, roadmap).
