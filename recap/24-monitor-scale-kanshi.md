# 24 — Fix monitor scale (Kanshi override and valid scale choices)

Date: 2026-11-15

## Root cause

The Monitor page wrote the new scale into `monitors.lua`, but **Kanshi is
running** and applies its own profile:

```
output "eDP-1" ... scale 1.25
```

Kanshi re-applies that profile on output events/reload, so changing the scale
in the app was immediately reverted to 1.25 on the laptop panel.

A second issue was that arbitrary fractional scales were offered even when
Hyprland/Kanshi round them to a value that keeps an integer logical resolution
(e.g. 2560×1600 at 1.5 becomes 1.6).

## Fixes

- New `src/kanshi.py`:
  - detects Kanshi and its config;
  - rewrites `output` lines for every profile with the current enabled state,
    mode, position and scale (lines that disable an output are left alone);
  - preserves unknown output options (e.g. `transform`);
  - backs up the Kanshi config and calls `kanshictl reload`.
- `MonitorPage` now:
  - updates the Kanshi config after saving `monitors.lua`;
  - reloads Kanshi after reloading Hyprland;
  - shows a caption when Kanshi is running.
- Scale is now a combo of **valid scales** for the monitor resolution
  (`valid_scales()` in `src/pages/monitor.py`), so the selected value is one
  Hyprland can apply exactly. The current value is always included.
- Health check reports whether Kanshi is managing outputs.

## Tests

- `tests/test_kanshi.py` — profile rewriting, unknown-option preservation,
  disabled outputs.
- `tests/test_monitor_scales.py` — valid scale sets for 2560×1600 and 1920×1080.

Total suite after this change: **108 tests** (110 after recap 25).
