# 19 — Grouped sidebar, app icon and advanced window rules

Date: 2026-10-31

## KDE-style grouped sidebar

`src/window.py` replaces the flat `Gtk.StackSidebar` with a grouped
navigation list:

- System: Home, General, Input devices, Default apps, Applications
- Caelestia: Caelestia, Theming, Wallpaper, Hyprland, Autostart
- Desktop: Monitor, Workspaces, Window Rules, Keybinds
- Hardware: Wi-Fi, Bluetooth, Audio, Fans, Power
- Maintenance: Updates, Backups, Health, About

The list stays in sync with `Gtk.Stack` when navigation comes from the Home
quick actions, global search or code, and keeps a scrollable 214 px sidebar.

## App icon

- Added `assets/caelestia-settings.svg`.
- `install.sh` copies it to
  `~/.local/share/icons/hicolor/scalable/apps/` and sets `Icon=caelestia-settings`
  in the desktop entry.
- `uninstall.sh` removes the icon and refreshes the icon cache.

## Advanced window rules

`src/pages/window_rules.py` now has an Advanced dialog per application:

- fullscreen mode, idle inhibit;
- pin, stay-focused, centre, no-animations, no-blur;
- opacity, size, move and tags.

The managed `hl.window_rule` generator emits those fields, existing advanced
rules are imported from `rules.lua`/`hypr-user.lua`, and the conflict checker
still works. Rows with only advanced settings are no longer skipped on save.

## Tests

- UI smoke + interaction tests still pass.
- **98 tests** total.

## Docs

README updated for advanced window rules, the icon install and the grouped
sidebar.
