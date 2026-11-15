# Caelestia Settings

> A native GTK4/Libadwaita control center for [Caelestia](https://github.com/caelestia-dots/caelestia) on **Hyprland 0.55+ with Lua configuration**.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Arch%20Linux-1793d1)
![License](https://img.shields.io/badge/license-MIT-green)
![Language](https://img.shields.io/badge/i18n-English-orange)

---

## Overview

This is the maintained Lua fork of [caelestia-settings](https://github.com/Jojo252511/caelestia-settings).
The original app edited `.conf` files and stopped working when Caelestia and Hyprland moved to
Lua (`hypr-user.lua`, `hypr-vars.lua`, `monitors.lua`, `keybinds.lua`, `variables.lua`).

Version **2.0.0** is a full Lua rewrite of the backend:

- every write targets the correct Lua file and the correct layer
  (user overrides are never written into dotfiles-managed files);
- **a timestamped backup is created before every write** — no exceptions;
- the whole app is **English-only** (the German i18n layer and all hard-coded German strings are gone);
- the new **Hyprland** page exposes Caelestia's styling variables (gaps, borders, opacity, blur, shadows, cursor);
- the new **Backups** page lets you inspect and restore any automatic backup.

---

## Features

### Home
- System overview: current wallpaper thumbnail, monitors, Wi-Fi, keyboard layout, CPU/GPU temperatures
- Quick actions for Wallpaper, Monitor, Wi-Fi, Keybinds and Updates

### General
- Multi-layout keyboard configuration (`kb_layout`, variants, XKB options)
- NumLock, key repeat rate/delay
- Touchpad: natural scrolling, tap-to-click, disable-while-typing, scroll factor
- Gestures: gesture fingers and workspace swipe fingers
- Cursor theme and size
- System language and timezone (authenticated with Polkit)
- Input overrides are written as a managed `hl.config` block in `~/.config/caelestia/hypr-user.lua`

### Input devices (new)
Per-device Hyprland settings written as managed `hl.device` overrides in
`hypr-user.lua`:
- keyboards: layout, variant, options, model, repeat rate/delay, NumLock, keybinds
- mice: sensitivity, acceleration profile, natural scroll, scroll factor,
  left-handed, middle-button emulation, scroll method, clickfinger
- touchpads: tap-to-click, tap-and-drag, tap button map, disable while typing,
  scroll factor, drag lock
- touchscreens and tablets: enabled, transform, left-handed
- only values that differ from the global input defaults are written
- per-device reset, one backup per apply, `hyprctl reload`

### Theming (new)
- Caelestia scheme name, flavour, variant and light/dark mode
- random scheme
- live palette preview with click-to-copy hex swatches
- GTK theme, icon theme and GTK colour-scheme selection via `gsettings`

### Caelestia (shell settings)
A complete, schema-driven editor for **all 279 `shell.json` options** of
caelestia-shell 2.5.0:
- searchable section sidebar (General, Appearance, Background, Bar, Borders,
  Dashboard, Launcher, Lock, Control centre, Notifications, OSD, Services,
  Session, Sidebar, Utilities, Paths)
- global and **per-monitor** scope; upstream global-only options are disabled
  in monitor scope
- native widgets: switches, sliders/spin buttons, text fields, enum combos,
  string-list editors and a validated JSON editor for list-of-object options
  (bar entries, status icons, quick toggles, launcher actions, idle timeouts,
  battery levels, player aliases, …)
- staged changes with a single Apply (one backup and one shell restart)
- **visual preview** of the staged appearance before applying (bar layout,
  workspaces, bar clock, desktop clock, rounding/spacing/transparency and the
  audio visualiser mock)
- per-row reset and “Reset section” remove overrides so Caelestia defaults
  come back
- visual editors for `bar.entries`, `bar.statusIcons` and `utilities.quickToggles`
  (toggle + reorder) and for `launcher.actions` (name, icon, description,
  command, enabled, dangerous, reorder/delete) instead of raw JSON
- defaults and enum values generated from the pinned upstream release with
  `scripts/gen_shell_schema.py`

### Wallpaper
- Reads `paths.wallpaperDir` from `shell.json` (default `~/Pictures/Wallpapers`)
- Images/GIFs from the wallpaper folder
- **Animated videos** (mp4/webm/mkv) from `<wallpaperDir>/Animated`
  (e.g. `~/Pictures/Wallpapers/Animated`), using Caelestia's native wallpaper engine
- The images tab excludes the `Animated` folder automatically
- Reuses Caelestia's video thumbnail cache
- Random wallpaper from the configured folder
- Colour scheme: name, flavour, variant and light/dark mode
- Background and desktop clock: enabled, position, scale, inverted colours, clock background
  (enabled/opacity/blur), shadow (enabled/opacity/blur), audio visualiser
- Global or **per-monitor** background overrides

### Hyprland (new)
Caelestia's styling variables, edited as overrides in `hypr-vars.lua`:
- gaps (workspace, inner, outer, single window)
- window opacity, rounding, border size and border colours
- blur (enabled, special workspaces, popups, input methods, xray, size, passes)
- shadows (enabled, range, render power, colour)
- gesture finger variables
- cursor theme/size, volume step/max and sleep command
- “Reset to Caelestia defaults” removes every override written by the page

### Applications (new)
- Add `.AppImage` files as launcher entries
- Name, icon, categories, terminal mode, FUSE-less `--appimage-extract-and-run`
- Copy to `~/Applications` or keep the original path
- Writes `~/.local/share/applications/*.desktop` and refreshes the desktop database
- Lists and removes only entries created by Caelestia Settings (marker key)

### Default apps (new)
- Caelestia shell applications (`general.apps.terminal/audio/playback/explorer`)
- Hyprland commands (`terminal`, `browser`, `editor`, `fileExplorer` in `hypr-vars.lua`)
- XDG/GTK file associations for browser, images, video and text
- shell-quoted command parsing, one apply for both layers

### Autostart (new)
- Manage commands executed at Hyprland startup
- Written to a managed `hl.on("hyprland.start", ...)` block in `hypr-user.lua`
- Existing startup handlers are preserved
- Add, edit, delete and reorder commands; validated reload with rollback

### Monitor
- Drag-and-drop monitor arrangement
- Resolution, refresh rate, rotation, scale and bit depth (8/10-bit)
- Scale choices are limited to values Hyprland can apply exactly; when Kanshi
  is running, its profiles are updated and reloaded too
- Colour management preset, VRR, ICC profile and mirror output
- SDR brightness/saturation and HDR min/max luminance controls
- Primary monitor (`xrandr --primary` in `execs.lua`)
- Per-monitor taskbar persistence
- **Preserves every field the app does not edit** (`reserved`, `sdr_eotf`, …)
- Matches `desc:` output names from `monitors.lua` with `hyprctl` names

### Power (new)
- Power profile selection via `powerprofilesctl` (performance / balanced / power-saver)
- Battery charge, plugged state and estimated time
- Caelestia idle behaviour: lock before sleep, inhibit while audio plays or charging
- Link to the full idle-timeout and battery-warning options on the Caelestia page

### Workspaces
- Rules grouped by monitor
- Default and persistent workspace toggles
- Advanced dialog: inner/outer gaps, layout, no-rounding, no-border, no-shadow, decorate
- Written as `hl.workspace_rule` blocks in `monitors.lua` and applied with `hyprctl reload`

### Keybinds
Three independent tabs, because Caelestia generates its shortcuts from variables:
- **Caelestia shortcuts** — edit `kb*` variables; overrides go to `hypr-vars.lua`
- **Custom shortcuts** — edit `config.binds` or the managed `hl.bind` block in `hypr-user.lua`
- **Active binds** — the resolved list from `hyprctl binds -j` (read-only)
- Search, add/edit/delete, reset overrides
- **Direct key recording** for Caelestia shortcuts and custom binds: press the keys
  (modifiers + key, or mouse buttons) instead of typing them
- **Preset action menu** with every installed desktop application plus Caelestia,
  window, workspace, media and system actions — choose “Steam” and the bind is
  generated automatically with `gtk-launch`

### Window Rules
- App scanner (`.desktop` files)
- Match by `class`, `initial_class`, `title` or `initial_title`
- Workspace assignment (including special workspaces), float behaviour
- Advanced dialog: fullscreen, pin, stay-focused, centre, no-anim, no-blur,
  idle inhibit, opacity, size, move and tags
- Conflict detection before saving
- Managed block in `hypr-user.lua`; hand-written rules are preserved and shown separately

### Network (new)
- Device list with connect/disconnect (Ethernet, Wi-Fi, VPN, tunnels)
- Saved connections: activate, deactivate, delete
- IPv4 editor: DHCP or manual address/gateway/DNS
- VPN import from `.ovpn`/`.conf`
- Wi-Fi scanning and passwords remain on the Wi-Fi page

### Wi-Fi, Bluetooth, Audio, Fans, Updates
- Wi-Fi scan/connect/disconnect via NetworkManager
- **Bluetooth**: adapter power, scan, pair (with PIN/passkey agent), connect/disconnect, trust and remove
- **Audio**: output/input devices, per-application volumes, mute switches and a test sound
- CPU/GPU temperatures and fan control
- System update UI with live progress, optional reboot and `caelestia update` support

### Backups
- Every automatic backup, grouped by source file
- Preview a backup or show a **unified diff** against the current file
- One-click restore (the current file is backed up first, so restores are undoable)
- Delete individual backups
- **Backup now** for shell.json, hypr-user.lua, hypr-vars.lua, monitors.lua, execs.lua
  and per-monitor shell.json
- Configurable retention (default 50 backups per file)

### Health check (new)
A diagnostics page that reports and can repair:
- repository vs installed app version (detects the stale `caelestia-settings` copy)
- installed caelestia-shell version vs bundled schema
- `hyprctl configerrors`
- invalid `shell.json` files
- unknown/outdated `shell.json` keys with a one-click clean-up
- **wallpaper daemon conflicts** (`hyprpaper` + Caelestia shell), missing wallpaper files,
  and whether the shell is running — with *Reapply wallpaper*, *Disable hyprpaper*,
  *Restart Caelestia shell* and *Reload Hyprland* actions
- required/optional dependencies
- backup count and newest backup

### Search, review and undo (new)
- **Global search**: `Ctrl+F` (or the header search button) searches every page and all
  Caelestia shell options; selecting a result navigates to it
- **Review changes**: Apply on the Caelestia page opens a diff **and a visual preview**
  of every pending change before anything is written
- **Undo last apply**: restores the backups created by the previous apply (current session)

### About
- Version, author, description
- App self-update from this fork
- Uninstall integration

---

## Backup policy (guaranteed)

Every modification goes through `src/backup.py`:

1. The current file is copied to a timestamped backup **before** any change.
2. The new content is written to a temporary file and moved into place atomically.
3. If the backup cannot be created, the write is refused.
4. A convenience copy is also written next to the source as `<file>.bak`.

Backup location:

```
~/.config/caelestia-settings/backups/<mirrored-path>/<file>.<YYYYmmdd_HHMMSS_mmm>.bak
```

Example:

```
~/.config/caelestia-settings/backups/dot-config-caelestia/hypr-user.lua.20261030_214512_123.bak
```

The last 50 backups per file are kept. `install.sh`, `uninstall.sh` and `doctor.sh` also back up
the Hyprland files they touch.

---

## Installation

### Dependencies

```bash
sudo pacman -S --needed \
  python-gobject libadwaita python-cairo python-psutil \
  pamixer networkmanager git ffmpeg
```

For the optional Rust extension (`caelestia_core`, used for conflict detection and PWM maths):

```bash
rustup component add clippy rust-analyzer   # development only
```

The app runs without the Rust extension: all parsers are implemented in Python and every Rust
feature has a fallback.

### Install

```bash
git clone https://github.com/AbelQ11/caelestia-settings-lua.git
cd caelestia-settings-lua
./install.sh
```

The installer:
- copies the app to `~/.local/share/caelestia-settings/`;
- builds and installs `caelestia_core` if Rust is available;
- creates `~/.local/bin/caelestia-settings`;
- installs the app icon and adds a `.desktop` entry;
- adds the `Super + I` keybind and the Polkit agent autostart to `~/.config/caelestia/hypr-user.lua`
  (with a backup).

### Uninstall

```bash
./uninstall.sh
```

Removes the app, launcher, `.desktop` entry, keybind, integration lines and every
managed block it wrote (input overrides, custom keybinds, window rules, input
devices, autostart and workspace rules). Asks before deleting
`~/.config/caelestia-settings/` (which contains your backups).

It deliberately leaves `shell.json`, per-monitor overrides, `hypr-vars.lua`,
monitor definitions and the primary-monitor line, because those may contain
settings you made yourself.

### Package (Arch)

A PKGBUILD for a local package is included:

```bash
cd packaging
makepkg -si
```

It installs the app under `/usr/lib/caelestia-settings`, the
`caelestia-settings` command, the desktop entry and the icon.

### Run without installing

```bash
python main.py
```

`caelestia_core` is optional. If you want the Rust extension:

```bash
cd rust/caelestia-py
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install maturin && maturin develop
```

---

## Keyboard shortcut

| Shortcut | Action |
|----------|--------|
| `Super + I` | Open Caelestia Settings |
| `Ctrl + F` / `Ctrl + K` | Search every page and setting |

The bind lives in `~/.config/caelestia/hypr-user.lua`:

```lua
hl.bind("SUPER + I", hl.dsp.exec_cmd("caelestia-settings"))
```

---

## File overview

```
caelestia-settings-lua/
├── main.py                     # App entry point
├── install.sh / uninstall.sh   # Installer / uninstaller
├── app_update.sh               # Self-updater (About page)
├── doctor.sh                   # Hyprland integration check/repair
├── manifest.json               # Version 2.0.0
├── assets/                     # App icon
├── packaging/                  # PKGBUILD, launcher and desktop entry
├── ruff.toml                   # Python lint config
├── scripts/
│   └── gen_shell_schema.py     # Regenerate the shell schema for a new release
├── rust/                       # Optional Rust core + PyO3 bindings
├── recap/                      # Change log, one file per modification
├── tests/                      # pytest suite (Lua, backups, schema, writers, Wi-Fi)
└── src/
    ├── backup.py               # Backup + atomic write (used by every write)
    ├── lua.py                  # Lua table reader/writer + managed blocks
    ├── config.py               # Paths, Lua parsing, reload helpers
    ├── shell_config.py         # shell.json global + per-monitor merge
    ├── shell_schema.py         # Flat option list, labels, defaults, enums
    ├── health.py               # Diagnostics and repair actions
    ├── search.py               # Global search dialog (Ctrl+F)
    ├── bluetooth.py            # BlueZ/bluetoothctl helpers
    ├── desktop.py              # Desktop entries and AppImage integration
    ├── shortcut.py             # Key/mouse capture helpers and dialog
    ├── action_menu.py          # Searchable app/action picker for keybinds
    ├── devices.py              # Per-device input model and Lua overrides
    ├── preview.py              # Visual preview of staged shell changes
    ├── data/
    │   └── shell_schema.json   # Generated caelestia-shell defaults + schema
    ├── lang.py                 # English UI strings
    ├── network.py              # NetworkManager helpers
    ├── window.py               # Main window / sidebar / search
    └── pages/
        ├── home.py             # Overview
        ├── general.py          # Input, gestures, cursor, region
        ├── input_devices.py    # Per-device input settings
        ├── default_apps.py     # Caelestia and Hyprland app commands
        ├── applications.py     # AppImage/launcher entry manager
        ├── shell.py            # All Caelestia shell options
        ├── theming.py          # Scheme, palette and GTK appearance
        ├── wallpaper.py        # Wallpaper, scheme, desktop clock
        ├── hyprland.py         # Hyprland styling variables
        ├── autostart.py        # Startup command manager
        ├── monitor.py          # Monitor canvas and settings
        ├── power.py            # Power profiles, battery and idle settings
        ├── network.py          # Devices, connections, VPN, IPv4
        ├── workspaces.py       # Workspace rules
        ├── keybinds.py         # Variables, custom binds, active binds
        ├── window_rules.py     # App rules
        ├── wifi.py / bluetooth.py / audio.py / fans.py / updates.py
        ├── backups.py          # Backup browser and restore
        ├── health.py           # Health check page
        └── about.py
```

---

## Configuration files

| File | What the app writes |
|------|---------------------|
| `~/.config/caelestia/hypr-user.lua` | managed `hl.config` input block, custom `hl.bind` block, managed window-rule block |
| `~/.config/caelestia/hypr-vars.lua` | keybind overrides, gesture/cursor values, Hyprland styling overrides |
| `~/.config/caelestia/shell.json` | any global Caelestia shell option (279 options), background/clock/wallpaper path |
| `~/.config/caelestia/monitors/<name>/shell.json` | per-monitor overrides for every supported option |
| `~/.config/hypr/monitors.lua` | `hl.monitor` definitions and `hl.workspace_rule` blocks |
| `~/.config/hypr/hyprland/execs.lua` | primary-monitor `xrandr` line |
| `~/.config/kanshi/config` | monitor scale/mode/position/enable in Kanshi profiles |
| `~/.config/caelestia-settings/*.json` | app caches |
| `~/.config/caelestia-settings/backups/` | automatic timestamped backups |

**Never written:** `variables.lua`, `hyprland/*.lua` (other than the primary-monitor line),
`hyprland/keybinds.lua`, `hyprland/rules.lua`. These are Caelestia-managed and are only read.

---

## Architecture

- **Python 3.12+/GTK4/Libadwaita** — UI and all file operations.
- **`src/lua.py`** — dependency-free Lua reader/writer: balanced tables, function calls,
  managed blocks, line-preserving value updates. No Lua interpreter is executed.
- **`src/backup.py`** — the single write path; every save is backed up and atomic.
- **`src/shell_schema.py` + `src/data/shell_schema.json`** — the full Caelestia
  option tree, generated from the pinned upstream release. Regenerate after a
  Caelestia update with:
  ```bash
  python scripts/gen_shell_schema.py --tag vX.Y.Z
  ```
- **Rust `caelestia_core` (optional)** — PyO3 bindings for monitor/rule parsing, conflict detection
  and PWM conversion. Pure Python fallbacks exist for all of it.

---

## Language

The app is English-only. `src/lang.py` keeps a tiny `t()` indirection so a translation layer can be
reintroduced later without touching every page.

---

## CI

`.github/workflows/ci.yml` runs the application jobs inside **Arch Linux
containers** (`archlinux:latest`), matching the supported distribution:

- `ruff check` with Arch's Python/ruff
- `pytest` under `xvfb`/`dbus` (includes the UI smoke/interaction tests)
- `shellcheck --severity=error` for the shell scripts
- `cargo fmt --check`, `cargo clippy --workspace --all-targets`, `cargo test --workspace`
  via rustup
- `gitleaks` secret scan (on the GitHub runner)

---

## Requirements

- Arch Linux (or an Arch-based distribution)
- Hyprland 0.55+ with Lua config (`hl.*` API)
- [Caelestia](https://github.com/caelestia-dots/caelestia) dots and `caelestia-shell` 2.x
- Python 3.12+, `python-gobject`, `libadwaita`, `python-cairo`, `python-psutil`
- `pamixer`/`pactl` (audio), `nmcli` (Wi-Fi), `bluetoothctl`/BlueZ (Bluetooth),
  `ffmpeg` (video thumbnails)
- Optional: Rust toolchain (for `caelestia_core`), `python-nvidia-ml-py` (GPU fan control)
- Optional: `yay`/`paru` (package updates; `caelestia update` is preferred when available)

---

## What's new in 2.0.0

- Complete Lua backend rewrite for Hyprland 0.55+ / Caelestia 2.x
- **Backup before every write** + atomic replacement + restore UI
- Full English translation (German i18n removed)
- New Hyprland styling page
- New Backups page
- Complete schema-driven Caelestia page covering all 279 shell options,
  with global/per-monitor scope, search, staged Apply and reset
- Health check page with wallpaper-daemon detection, config-error reporting,
  unknown-key cleanup and dependency checks
- Global search (`Ctrl+F`), change review before apply and undo-last-apply
- New Bluetooth page and expanded Audio page (input, mute, device selection, test sound)
- Visual preview of staged Caelestia UI changes (including the audio visualiser)
  shown in the review dialog and via the Preview button
- Per-device input settings, a Theming page (palette/GTK) and visual
  bar/status-icon/quick-toggle editors
- UI smoke test that constructs every page
- Autostart command manager, validated reload with automatic rollback, uninstall
  cleanup of all managed blocks, and an optional-Rust installer
- Default apps and Power pages, advanced workspace rules, backup diff/delete/backup-now
- Direct key/mouse recording for every shortcut and a searchable app/action menu
- AppImage manager for Caelestia’s launcher
- KDE-style grouped sidebar, app icon and advanced window-rule editor
- General Network page: devices, connections, VPN import and IPv4 editing
- Monitor HDR/ICC/mirror controls, per-app audio, file associations and
  configurable backup retention
- Kanshi-aware monitor scaling (Kanshi was overriding the app's scale), with
  layout-safe profile syncing and a regression test for the monitor panel
- Bluetooth pairing agent, xvfb/shellcheck CI and tagged releases with checksums
- Keybinds now edit `variables.lua` overrides, `config.binds` and managed `hl.bind` entries,
  with a key recorder and a live `hyprctl binds` view
- Monitor save preserves all untouched fields and `desc:` outputs
- Workspaces are applied with `hyprctl reload` instead of invalid `hyprctl keyword`
- Wallpaper page uses Caelestia's native image/GIF/video handling (no `mpvpaper`)
- Correct `~/Pictures/Wallpapers` default and per-monitor clock/background overrides
- Optional Rust core (the app runs without it)

## Roadmap

- [x] Lua configuration support
- [x] Backup + restore system
- [x] Hyprland styling page
- [x] Keybind recorder
- [x] Per-monitor shell overrides
- [x] Full schema-driven pages for every Caelestia shell option
- [x] Health check, global search, change review and undo
- [x] Audio input, Bluetooth page
- [x] Visual preview of staged UI changes (bar/workspaces/clock/visualiser)
- [x] Per-device input settings page
- [x] Theming / palette / GTK appearance page
- [x] Visual bar entries, status icons, quick toggles and launcher-action editors
- [x] UI smoke test for every page
- [x] Interaction tests for apply/undo, input devices and global search
- [x] Autostart manager and validated reload with rollback
- [x] Default apps page, Power page, advanced workspace rules
- [x] Backup diff, delete and backup-now
- [x] Direct key/mouse shortcut recording and app action menu
- [x] AppImage launcher integration
- [x] Grouped sidebar, app icon, advanced window rules
- [x] General Network page (Ethernet/VPN/connections/IPv4)
- [x] Monitor HDR/ICC/mirror, per-app audio, file associations, backup retention
- [x] App icon and PKGBUILD packaging
- [x] Kanshi-aware monitor scaling and valid scale choices
- [x] Bluetooth pairing agent (PIN/passkey)
- [x] CI with xvfb UI tests and shellcheck
- [x] Release-tag updater and GitHub release workflow with checksums
- [ ] Automated interaction tests for the remaining dialogs

---

## Author

**Jojo252511** — [GitHub](https://github.com/Jojo252511) — [Ko-fi](https://ko-fi.com/jojo2511)

Lua fork maintained by **AbelQ11**.

Made for the [Caelestia](https://github.com/caelestia-dots/caelestia) ecosystem.
