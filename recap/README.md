# Recap

One file per modification, newest last.

| File | Summary |
|------|---------|
| [00-project-review.md](00-project-review.md) | Audit of the Lua migration and the bugs found |
| [01-backup-and-english.md](01-backup-and-english.md) | Backup-before-every-write system, Backups page, English-only UI |
| [02-lua-config-core.md](02-lua-config-core.md) | `src/lua.py`, `src/config.py` rewrite, `src/shell_config.py` |
| [03-general-input.md](03-general-input.md) | General page: multi-layout input, touchpad, gestures, cursor, region |
| [04-monitor-workspaces.md](04-monitor-workspaces.md) | Monitor field preservation, workspace live-apply fix |
| [05-keybinds-window-rules.md](05-keybinds-window-rules.md) | Keybind sources/recorder, window-rule managed block |
| [06-wallpaper-scheme.md](06-wallpaper-scheme.md) | Correct wallpaper dir, native video support, scheme and clock options |
| [07-hyprland-styling.md](07-hyprland-styling.md) | New Hyprland styling page (hypr-vars overrides) |
| [08-release-docs.md](08-release-docs.md) | Version 2.0.0, tests, CI, README |
| [09-shell-settings.md](09-shell-settings.md) | Schema-driven editor for all 279 Caelestia shell options |
| [10-health-search-undo.md](10-health-search-undo.md) | Health checks, global search, review before apply, undo |
| [11-audio-bluetooth.md](11-audio-bluetooth.md) | Expanded audio page and new Bluetooth page |
| [12-visual-preview.md](12-visual-preview.md) | Visual preview of staged UI changes (bar, clock, visualiser) |
| [13-input-theming-tests.md](13-input-theming-tests.md) | Per-device input, Theming page, visual toggle editors, UI smoke tests |
| [14-launcher-actions-tests.md](14-launcher-actions-tests.md) | Visual launcher-actions editor and interaction tests |
| [15-validated-autostart-uninstall.md](15-validated-autostart-uninstall.md) | Validated writes/rollback, Autostart page, uninstall cleanup, optional Rust |
| [16-default-apps-power-backups.md](16-default-apps-power-backups.md) | Default apps, Power, backup diff/delete/backup-now, advanced workspace rules |
| [17-animated-wallpaper-dir.md](17-animated-wallpaper-dir.md) | Videos read from `~/Pictures/Wallpapers/Animated` |
| [18-recording-action-menu-appimage.md](18-recording-action-menu-appimage.md) | Key/mouse recording, app/action menu, AppImage manager |
| [19-sidebar-icon-window-rules.md](19-sidebar-icon-window-rules.md) | Grouped sidebar, app icon, advanced window rules |
| [20-network-page.md](20-network-page.md) | General Network page (devices, connections, VPN, IPv4) |
| [21-monitor-audio-associations-retention.md](21-monitor-audio-associations-retention.md) | Monitor HDR/ICC/mirror, per-app audio, file associations, retention |
| [22-packaging.md](22-packaging.md) | App icon and PKGBUILD packaging |
| [23-bluetooth-ci-release.md](23-bluetooth-ci-release.md) | Bluetooth agent, xvfb/shellcheck CI, tagged releases |
| [24-monitor-scale-kanshi.md](24-monitor-scale-kanshi.md) | Kanshi-aware monitor scale and valid scale choices |
| [25-monitor-settings-panel.md](25-monitor-settings-panel.md) | Fix monitor settings panel crash and layout-safe Kanshi sync |

## Invariant

Every write performed by the app or by `install.sh` / `uninstall.sh` /
`doctor.sh` creates a timestamped backup first. The shared implementation lives in
`src/backup.py` and refuses to write if the backup cannot be created.
