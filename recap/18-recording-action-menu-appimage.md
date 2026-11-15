# 18 — Direct shortcut recording, app/action menu and AppImage manager

Date: 2026-11-12

## Shortcut recording

- New `src/shortcut.py`:
  - GTK key-name → Hyprland key-name normalization;
  - modifier ordering;
  - mouse buttons mapped to `mouse:272`…`mouse:276`;
  - `ShortcutCaptureDialog`: press a combination (or click a mouse button),
    live preview, Clear/Use/Cancel.
- Caelestia shortcut rows now have a **Record** button; list-valued shortcuts
  append the new combo, single values are replaced.
- The custom keybind dialog now opens the capture dialog instead of the old
  inline recording toggle.

## App/action menu for custom keybinds

New `src/action_menu.py`:

- searchable menu with **every installed desktop application**;
- choosing an app generates `exec` + `gtk-launch <desktop-id>`;
- built-in actions:
  - Caelestia: launcher, session, sidebar, lock, clear notifications, show panels;
  - window: close, fullscreen, floating, pin, centre, split, swap, focus/move in
    four directions;
  - workspace: next/previous, move window next/previous, toggle special, 1–5;
  - media: play/pause, next/previous, mute, volume up/down;
  - system: screenshot, region screenshot, record, region record, sleep.
- The existing dispatcher/argument fields remain for advanced users.

## AppImage manager

New `src/desktop.py` + `src/pages/applications.py`:

- pick an `.AppImage`;
- name, icon, categories, terminal, copy-to-`~/Applications`, FUSE-less
  `--appimage-extract-and-run` options;
- makes the file executable;
- writes `~/.local/share/applications/caelestia-appimage-<slug>.desktop` with
  `X-Caelestia-Settings-Managed=true`;
- validates with `desktop-file-validate` when available and runs
  `update-desktop-database`;
- lists/removes only entries created by the app, optionally deleting the copied
  AppImage;
- Caelestia’s launcher reads these entries through Quickshell `DesktopEntries`.

## Tests

- `tests/test_shortcut.py` — key names, modifiers, mouse buttons.
- `tests/test_desktop.py` — AppImage install/copy/remove, desktop entry content,
  extract-and-run.
- UI interaction tests for the action menu, keybind dialog and capture dialog.
- UI smoke test includes the Applications page.
- Total suite: **98 tests**.

## Docs

README updated for recording, the action menu and AppImage integration.
