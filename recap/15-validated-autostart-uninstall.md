# 15 — Validated writes, autostart, uninstall cleanup and optional Rust

Date: 2026-10-31

## Validated writes with rollback

New `src/apply.py`:

- reads `hyprctl configerrors` before a write;
- writes atomically (backup first);
- reloads Hyprland and compares the errors;
- if the change introduced **new** errors, restores the backup, reloads again
  and raises `ApplyError`;
- pre-existing errors do not trigger a rollback.

Used by all Hyprland-writing pages:

- General input block
- Hyprland styling (`hypr-vars.lua`)
- Keybinds (managed and `config.binds`, plus override resets)
- Window rules
- Workspaces
- Monitor configuration
- Input devices
- Autostart

`src/config.py` gained `hyprctl_config_errors()` and
`reload_hyprland_checked()`.

## Autostart page

`src/pages/autostart.py`:

- manages commands in a managed `hl.on("hyprland.start", ...)` block in
  `hypr-user.lua`;
- add, edit, delete and reorder;
- existing startup handlers are untouched;
- validated reload with rollback.

## Uninstall cleanup

`uninstall.sh` now removes every managed block it wrote:

- `input`
- `custom keybinds`
- `window rules`
- `input devices`
- `autostart`
- workspace rules in `monitors.lua`

Each removal is backed up. It deliberately leaves `shell.json`, per-monitor
overrides, `hypr-vars.lua`, monitor definitions and the primary-monitor line,
since those may contain manual settings.

## Optional Rust

`install.sh` no longer installs the Rust toolchain and no longer fails when Rust
or the crate is missing:

- skips `caelestia_core` with a message when `cargo`/`rustc` are absent;
- continues if the wheel build fails;
- the Python fallbacks are always available.

## Tests

- `tests/test_apply.py` — rollback on new errors, clean reload, pre-existing
  errors, reload disabled.
- `tests/test_autostart.py` — parsing and writing the managed autostart block.
- UI smoke test now includes the Autostart page.
- Interaction test applies autostart commands.

Total suite: **87 tests**.

## Docs

README updated for the Autostart page, validated reload/rollback, uninstall
cleanup and optional Rust.
