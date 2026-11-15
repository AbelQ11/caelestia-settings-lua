# 23 — Bluetooth agent, CI and release automation

Date: 2026-11-12

## Bluetooth pairing agent

`src/bluetooth.py`:

- `agent_response()` handles PIN, passkey, confirm-passkey and authorize prompts;
- `pair_with_agent()` drives an interactive `bluetoothctl` `KeyboardDisplay`
  agent, sends the PIN/passkey/yes, waits for success, and returns diagnostics.

`src/pages/bluetooth.py`:

- Pair now opens a dialog with an optional PIN/passkey;
- pairing runs in a background thread;
- on success the device is trusted and the list refreshes;
- failures show the last agent line.

## CI

`.github/workflows/ci.yml`:

- all application jobs run inside `archlinux:latest` containers, matching the
  supported distribution;
- installs Arch packages (`python-gobject`, `gtk4`, `libadwaita`,
  `gobject-introspection`, `libnm`, `xorg-server-xvfb`, `dbus`, …);
- runs the full pytest suite under `dbus-run-session -- xvfb-run -a`, so the
  UI smoke/interaction tests actually run in CI;
- new `lint-shell` job running `shellcheck --severity=error` on all shell
  scripts;
- Rust jobs use Arch `rustup` with the `rustfmt`/`clippy` components.

## Release automation

- `app_update.sh` asks the GitHub API for the latest release tag, clones that
  tag with `--depth 1`, and falls back to `dev` only if no release exists.
  `CAELESTIA_SETTINGS_BRANCH` can override it.
- New `.github/workflows/release.yml` triggers on `v*` tags:
  - builds `caelestia-settings-lua-<tag>.tar.gz` with `git archive`;
  - writes `checksums.txt` (SHA-256);
  - creates the GitHub release with notes and both files.

## GTK deprecation cleanup

- `Gtk.Picture.set_pixbuf` replaced with `Gdk.Texture` + `set_paintable`.
- Remaining `Gtk.ComboBoxText`/`Gtk.Dialog` deprecations are limited to
  existing widgets and are non-fatal; a future mechanical migration to
  `Gtk.DropDown`/`Adw.Dialog` can remove them.

## Tests

- Bluetooth agent prompt tests added.
- **103 tests** total.

## Docs

README updated for the Bluetooth agent, CI and release workflow.
