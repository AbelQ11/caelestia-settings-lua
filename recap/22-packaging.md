# 22 — Packaging and app icon

Date: 2026-11-12

## App icon

- `assets/caelestia-settings.svg` (rounded dark tile with a sprocket/circle).
- `install.sh` installs it to
  `~/.local/share/icons/hicolor/scalable/apps/caelestia-settings.svg` and uses
  `Icon=caelestia-settings` in the desktop entry.
- `uninstall.sh` removes the icon and refreshes the icon cache.

## PKGBUILD

`packaging/` contains:

- `PKGBUILD` — git package that installs the app to
  `/usr/lib/caelestia-settings`, plus `/usr/bin/caelestia-settings`;
- `caelestia-settings` launcher;
- `caelestia-settings.desktop`.

Dependencies and optional dependencies are declared (Rust remains optional).

## Docs

README installation section updated with `makepkg -si`.
