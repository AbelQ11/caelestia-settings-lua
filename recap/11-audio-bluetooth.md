# 11 — Expanded Audio and new Bluetooth page

Date: 2026-10-31

## Audio (`src/pages/audio.py`)

The page now covers input as well as output, using `pactl` (PipeWire/PulseAudio):

- **Output**: default sink selection, volume, mute, test sound
- **Input**: default source selection, volume, mute
- Device lists are parsed from `pactl list sinks` / `pactl list sources`
  (`Name:` + `Description:`), so descriptions are shown instead of raw device IDs.
- Volume is parsed from `pactl get-*-volume`; mute from `pactl get-*-mute`.
- Test sound uses `paplay` with the freedesktop sounds.
- Pure parsing helpers (`parse_devices`, `parse_volume`, `parse_mute`) are tested.

## Bluetooth (`src/bluetooth.py`, `src/pages/bluetooth.py`)

New **Bluetooth** page and wrapper around `bluetoothctl`:

- adapter detection and power switch
- scan (8-second `bluetoothctl --timeout` scan in a background thread)
- device list with connected/paired/trusted status
- pair, connect, disconnect, trust/untrust and remove
- confirmation before removing a device
- clear "No Bluetooth adapter" state when BlueZ/`bluetoothctl` is unavailable

Pure parsers (`parse_devices`, `parse_info`, `parse_controller`) are unit-testable.

## Integration

- New page added to the main sidebar and to global search (`Ctrl+F`).
- Audio and Bluetooth entries added to the Health check dependency list
  (`pactl`, `pamixer`, `paplay`, `bluetoothctl`).
- README updated.

## Tests

- `tests/test_audio_bluetooth.py` — audio device/volume/mute parsing,
  Bluetooth device/info/controller parsing.

Total suite: **67 tests**.
