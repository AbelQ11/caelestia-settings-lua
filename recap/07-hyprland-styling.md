# 07 — Hyprland styling page

Date: 2026-10-30

## New page: `src/pages/hyprland.py`

Caelestia exposes its Hyprland look through `variables.lua`
(`local vars = require("variables")` in every `hyprland/*.lua` file).

The page edits **overrides only**, stored in the user-owned
`~/.config/caelestia/hypr-vars.lua`. `variables.lua` is never modified, so
Caelestia updates keep working.

## Sections

- **Gaps** — workspace, inner, outer, single-window outer gaps
- **Windows** — opacity, rounding, border size, active/inactive border colours
- **Blur** — enabled, special workspaces, popups, input methods, xray, size, passes
- **Shadows** — enabled, range, render power, colour
- **Gestures** — gesture fingers, workspace swipe fingers, extra gesture fingers
  (touchpad options live on the General page to avoid two competing writers)
- **Cursor** — theme and size
- **Volume and sleep** — volume step, maximum volume, sleep command

## Behaviour

- Defaults are read from `variables.lua`; overrides from `hypr-vars.lua`.
- On **Apply**, a value equal to the Caelestia default is removed from the
  override file instead of being written redundantly.
- **Reset to Caelestia defaults** removes every override owned by this page,
  leaving unrelated user variables (`terminal`, keybind overrides, …) intact.
- Every apply is backed up and followed by `hyprctl reload`.

## Notes

- Colour fields show the raw Caelestia expression (e.g.
  `"rgba(" .. scheme.primary .. "e6)"`). Entering a plain value creates an
  override.
- The page is read/write through `src/lua.py`, so comments and unrelated
  variables in `hypr-vars.lua` are preserved.
