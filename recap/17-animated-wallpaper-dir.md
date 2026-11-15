# 17 — Animated wallpapers folder

Date: 2026-10-31

## What changed

The Wallpaper page now uses two locations:

- **Images/GIFs**: `paths.wallpaperDir` from `shell.json`
  (default `~/Pictures/Wallpapers`), excluding the `Animated` subfolder.
- **Videos**: `<wallpaperDir>/Animated`
  (default `~/Pictures/Wallpapers/Animated`).

Changes in `src/pages/wallpaper.py`:

- new `video_dir()` helper;
- `_scan()` accepts an `exclude` directory so images don’t include files from
  `Animated`;
- the videos tab scans `video_dir()` (mp4/webm/mkv);
- the path label follows the active tab;
- the empty-videos message points to the `Animated` folder;
- setting a video still uses Caelestia’s native `caelestia wallpaper -f`;
- thumbnails still reuse Caelestia’s video-thumbnail cache.

## Tests

`tests/test_wallpaper_paths.py`:

- `video_dir()` follows `paths.wallpaperDir`;
- images exclude `Animated`;
- videos are found in `Animated`.

Total suite: **90 tests**.

## Docs

README updated.
