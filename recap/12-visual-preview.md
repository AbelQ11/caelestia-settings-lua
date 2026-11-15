# 12 — Visual preview of staged UI changes

Date: 2026-10-31

## What was added

A visual preview of the Caelestia shell appearance, rendered from the **staged**
values before anything is written.

`src/preview.py`:

- reads the current colour palette from
  `~/.local/state/caelestia/scheme.json` (with a fallback palette);
- renders a mock 960×540 desktop with cairo:
  - background gradient and, when enabled, the **audio visualiser**
    (`services.visualiserBars`, spacing/rounding);
  - top bar built from `bar.entries` (logo, workspaces, spacer, active window,
    tray, clock, status icons, power);
  - workspace indicators respecting `bar.workspaces.shown` and
    `displayType` (shapes/text/icons);
  - bar clock with date/seconds toggles;
  - desktop clock with position, scale, background opacity and shadow;
  - a mock window using `appearance.rounding.scale`, `border.thickness` and
    transparency;
  - status icons from `bar.statusIcons`;
- `PreviewModel` wraps the effective/staged value map, so the preview always
  reflects what Apply would write.

## Integration

`src/pages/shell.py`:

- new **Preview** toolbar button opens the preview dialog at any time;
- **Review & apply** now shows the visual preview above the textual diff, so the
  user sees the resulting bar/clock/visualiser before confirming.

## Tests

`tests/test_preview.py`:
- hex colour parsing (`#rrggbb`, alpha, invalid values);
- `PreviewModel` value lookup;
- scheme palette fallback.

Total suite: **70 tests**.
