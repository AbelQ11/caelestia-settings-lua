# 13 — Per-device input, Theming, visual toggle editors and UI smoke tests

Date: 2026-10-31

## Per-device input settings

`src/devices.py` + `src/pages/input_devices.py`:

- lists every device from `hyprctl devices -j` (keyboards, mice, touchpads,
  touchscreens, tablets);
- writes managed `hl.device({ name = ..., ... })` overrides into
  `hypr-user.lua` under `-- BEGIN Caelestia Settings: input devices`;
- reads current Hyprland global input defaults with `hyprctl getoption` and only
  writes values that differ;
- fields:
  - keyboard: layout, variant, options, model, repeat rate/delay, NumLock,
    resolve binds by symbol, keybinds;
  - mouse: sensitivity, acceleration profile, natural scroll, scroll factor,
    left-handed, middle-button emulation, scroll method, clickfinger;
  - touchpad: tap-to-click, tap-and-drag, tap button map, disable while typing,
    scroll factor, left-handed, drag lock, clickfinger;
  - touchscreen/tablet: enabled, transform, left-handed;
- per-device reset, one backup per apply, `hyprctl reload`;
- manually written `hl.device` calls outside the managed block are preserved.

## Theming

`src/pages/theming.py`:

- Caelestia scheme name, flavour, variant and mode (apply/random via CLI);
- live palette swatches from `scheme.json` with click-to-copy hex values;
- GTK theme, icon theme and GTK colour-scheme selection via `gsettings`;
- the old duplicate scheme block was removed from the Wallpaper page.

## Visual bar/status/quick-toggle editors

`src/pages/shell.py` now renders:

- `bar.entries`
- `bar.statusIcons`
- `utilities.quickToggles`

as expandable lists with switches and up/down reordering instead of raw JSON.
All other object lists keep the validated JSON editor.

## UI smoke tests

`tests/test_ui_smoke.py` constructs every page once under a real GTK/Adwaita
application and asserts they are widgets. It is skipped automatically when no
display is available; run with `xvfb-run -a python -m pytest tests` on a headless
machine.

## Tests

Total suite: **76 tests** (including the UI smoke test and device filters).

## Docs

README updated with Input devices, Theming, visual toggle editors, UI test and
the new modules.
