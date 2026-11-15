# 25 — Fix the monitor settings panel and make Kanshi sync layout-safe

Date: 2026-11-15

## Root cause

Selecting a monitor on the Monitor page raised

```
AttributeError: 'MonitorSettingsPanel' object has no attribute '_icc_row'
```

`MonitorSettingsPanel.load()` already loaded the ICC profile, mirror output,
SDR brightness/saturation and HDR luminance values, but `__init__` never
created those widgets. The exception aborted `load()`, so the Scale combo was
never populated and the monitor could not be configured at all.

## Fixes

- `MonitorSettingsPanel.__init__` now creates every widget `load()` uses:
  - **ICC profile** (`Adw.EntryRow`, `hl.monitor icc`)
  - **Mirror output** (`Adw.EntryRow`, `hl.monitor mirror`)
  - **SDR brightness** (`0.10 – 10.00`)
  - **SDR saturation** (`0.00 – 2.00`)
  - **SDR min / max luminance**
  - **HDR min / max / max-average luminance**
  All of them are wired to `_on_icc_changed`, `_on_mirror_changed` or
  `_on_luminance_changed`, so they are written to `monitors.lua` on Apply.
- Selecting a different resolution refreshes both the refresh-rate list and
  the valid-scale list.
- Kanshi synchronisation is now **layout-safe** (`src/kanshi.py`): only output
  lines that are currently `enable`d are rewritten, and outputs disabled in
  the app are skipped. Layout-only profiles such as `external-only`
  (`output "eDP-1" disable`) are no longer silently rewritten to enable the
  panel.

## Tests

- `tests/test_monitor_scales.py::test_settings_panel_loads_every_field` — a
  regression test that loads a synthetic model into the real panel and walks
  every valid scale, so a missing widget can never break `load()` again.
- `tests/test_kanshi.py` — disabled outputs stay disabled, enabled outputs get
  the new mode/position/scale.

Total suite: **110 tests**.

## Verified live

Selecting `1.6` for `eDP-1` in the panel and pressing Apply produced:

- `~/.config/hypr/monitors.lua` with `scale = 1.6`
- `~/.config/kanshi/config` with `scale 1.6` in the active profiles
- `hyprctl monitors` reporting `eDP-1 scale 1.6`

Restoring the original files returned the panel to `1.25`.
