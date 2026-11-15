# 06 — Wallpaper, colour scheme and desktop clock

Date: 2026-10-30

## Wallpaper

- The folder now comes from `paths.wallpaperDir` in `shell.json`
  (`src.shell_config.wallpaper_dir()`), defaulting to the XDG Pictures dir +
  `Wallpapers` (i.e. `~/Pictures/Wallpapers`).
- Removed the old `~/Bilder/Wallpapers` path.
- Removed the `mpvpaper` autostart hack. Caelestia plays mp4/webm/mkv natively, so
  images, GIFs and videos all use `caelestia wallpaper -f <path>`.
- Video thumbnails reuse Caelestia's cache (`~/.cache/caelestia/videothumbs`),
  with an ffmpeg fallback.
- Random wallpaper uses `caelestia wallpaper -r <dir>`.
- Legacy `mpvpaper` processes from older versions are terminated.

## Colour scheme

- Scheme name, flavour, variant and light/dark mode controls.
- Applied with `caelestia scheme set`.
- Existing mode is read from `~/.local/state/caelestia/scheme.json`.

## Background and desktop clock

All values are read from and written to `shell.json`:

- `background.enabled`, `background.wallpaperEnabled`,
  `background.visualiser.enabled`
- `background.desktopClock.enabled`
- `background.desktopClock.position`
- `background.desktopClock.scale`
- `background.desktopClock.invertColors`
- `background.desktopClock.background.enabled/opacity/blur`
- `background.desktopClock.shadow.enabled/opacity/blur`

A scope selector writes either to the global `shell.json` or to
`~/.config/caelestia/monitors/<name>/shell.json`. All clock values are applied in
one pass (one backup, one shell restart).

The clock expander is wrapped in a `Gtk.ListBox`, as required by
`Adw.ExpanderRow`.
