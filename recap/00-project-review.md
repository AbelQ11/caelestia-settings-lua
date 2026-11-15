# 00 — Project review (before changes)

Date: 2026-10-30

## Context

Caelestia and Hyprland moved to Lua (Hyprland 0.55+). The fork had a partial
migration commit, but several pages still targeted files that are not loaded,
or rewrote Caelestia-managed files.

## Findings

| Area | Problem |
|------|---------|
| Keybinds | Read/wrote `~/.config/hypr/keybinds.lua`, which is only a comment stub. Real binds are generated from `variables.lua` into `hyprland/keybinds.lua`. |
| General | Wrote the dotfiles-managed `hyprland/input.lua`; collapsed multi-layout `us,fr` to one layout; German layout names. |
| Wallpaper | Default folder `~/Bilder/Wallpapers`; `mpvpaper` integration obsolete (Caelestia 2.x plays videos natively); clock options incomplete. |
| Monitor | Regenerated `monitors.lua` from scratch and dropped `cm`, `sdr_*`, `vrr`, `mirror`, `reserved`; `desc:` names did not match `hyprctl` names. |
| Workspaces | Sent Lua source to `hyprctl keyword workspace` (invalid). |
| Window rules | Hard `import caelestia_core`; German marker; limited match types. |
| Shell config | Only `bar.persistent` and four clock keys exposed. |
| Language | German i18n plus hard-coded German strings in several pages. |
| Self-update | `app_update.sh` pointed at the original `.conf` repository. |

## Environment

- Hyprland 0.57.0, caelestia-shell 2.5.0, caelestia-cli 1.1.3
- Python 3.14, GTK4 + libadwaita
- `caelestia_core` was not built in the dev environment (now optional)
