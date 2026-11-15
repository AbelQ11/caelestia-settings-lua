# 21 — Monitor HDR, per-app audio, file associations and backup retention

Date: 2026-11-12

## Monitor colour / HDR controls

`src/pages/monitor.py`:

- ICC profile path (`icc`);
- mirror output (`mirror`);
- SDR brightness and saturation;
- expandable HDR/luminance section:
  - SDR min/max luminance,
  - min/max luminance,
  - max average luminance;
- values are read back from `monitors.lua` and written into `hl.monitor`;
- fields the UI does not edit are still preserved.

## Per-application audio

`src/pages/audio.py`:

- new Applications group using `pactl -f json list sink-inputs`;
- one row per playing stream with volume slider and mute switch;
- `pactl set-sink-input-volume` / `set-sink-input-mute`;
- pure `parse_sink_inputs()` parser tested.

## File associations

`src/pages/default_apps.py`:

- browser, images, video and text associations;
- reads current values with `xdg-settings`/`xdg-mime`;
- applies with `xdg-settings set default-web-browser` and `xdg-mime default`.

## Backup retention

`src/backup.py` + `src/pages/backups.py`:

- retention is stored in `~/.config/caelestia-settings/settings.json`;
- configurable from the Backups toolbar (1–500, default 50);
- pruning uses the configured value;
- `get_retention()` / `set_retention()` helpers tested.

## Tests

- audio `parse_sink_inputs`;
- backup retention get/set.

Total suite: **102 tests**.

## Docs

README updated.
