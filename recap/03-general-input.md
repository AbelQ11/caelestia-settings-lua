# 03 — General / Input page

Date: 2026-10-30

## What changed

- Rewritten `src/pages/general.py`.
- No longer writes the Caelestia-managed `hyprland/input.lua`.
- Writes a managed `hl.config({ input = {...} })` block into the user-owned
  `~/.config/caelestia/hypr-user.lua`, which is loaded after the dotfiles files.
- Reads the effective values from `hyprctl getoption` first, with the managed block
  and legacy `input.lua` as fallbacks.

## Features

- Multi-layout support: primary layout + extra layouts (`us,fr`) and variants.
- XKB layout switch option (Alt+Shift, Ctrl+Shift, Super+Space, Caps Lock, …).
- NumLock on startup.
- Key repeat rate and delay.
- Touchpad: natural scrolling, tap-to-click, disable while typing, scroll factor.
- Gestures (3/4/5 fingers, workspace swipe) written to `hypr-vars.lua`.
- Cursor theme/size written to `hypr-vars.lua` + `hyprctl setcursor` + gsettings.
- System language (full `localectl list-locales`) and timezone (full
  `timedatectl list-timezones`) through `pkexec`.
- English keyboard layout names.

## Live apply

Each input change runs `hyprctl keyword input:<key> <value>` and then
`hyprctl reload`; the same values are persisted in `hypr-user.lua`.

## Tests

`tests/test_lua_config.py::test_input_lua_read_and_write` — reads a legacy
`input.lua`, writes the managed block, verifies `kb_layout` and
`numlock_by_default`.
