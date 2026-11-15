# 04 — Monitor and Workspaces pages

Date: 2026-10-30

## Monitor

- `monitors.lua` is no longer regenerated from scratch.
  Only the matching `hl.monitor({...})` calls are replaced; comments, workspace
  rules and unknown fields are preserved.
- Matches `desc:...` outputs against `hyprctl` descriptions, so bitdepth/VRR/cm
  values reach the right monitor.
- New controls: colour management preset (`cm`) and VRR. Existing `sdr_*`,
  `icc`, `reserved`, `mirror` fields are carried over untouched.
- Apply now writes the file, applies monitor keywords and calls `hyprctl reload`.
- Primary monitor still uses an `xrandr --primary` line in `execs.lua`.
- Per-monitor bar persistence uses the per-monitor `shell.json`.
- All writes are backed up.

## Workspaces

- `hl.workspace_rule` blocks are written to a managed section in `monitors.lua`;
  monitor definitions and comments are kept.
- Live apply is a proper `hyprctl reload` (the old code passed Lua source to
  `hyprctl keyword`, which never worked).
- Supports default, persistent, gaps, layout and `no_rounding` fields.
- “Any monitor” option instead of silently picking the first monitor.

## Tests

`tests/test_writers.py`:
- monitor save preserves `cm`, `sdr_*`, comments and workspace rules;
- workspace save keeps the monitor block and replaces old rules.
