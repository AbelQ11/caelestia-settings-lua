"""Audio output and input settings.

Uses PipeWire/PulseAudio's ``pactl`` CLI (with ``pamixer`` still accepted as a
fallback for volume when present).  Both the default output and the default
input are configurable, including mute and volume.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from gi.repository import Adw, Gtk

from src.lang import t

_TEST_SOUNDS = [
    Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/bell.oga"),
]


def _run(command: list[str], timeout: int = 3) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def parse_devices(output: str) -> dict[str, str]:
    """Parse ``pactl list sinks/sources`` into ``{name: description}``."""

    devices: dict[str, str] = {}
    current = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("Description:") and current:
            devices[current] = line.split(":", 1)[1].strip()
            current = None
    return devices


def parse_volume(output: str) -> int:
    match = re.search(r"(\d+)%", output)
    return int(match.group(1)) if match else 0


def parse_mute(output: str) -> bool:
    return "yes" in output.lower()


def _list_devices(kind: str) -> dict[str, str]:
    code, output = _run(["pactl", "list", kind])
    return parse_devices(output) if code == 0 else {}


def _default_device(kind: str) -> str:
    code, output = _run(["pactl", f"get-default-{kind}"])
    return output.strip() if code == 0 else ""


def _volume(kind: str) -> int:
    code, output = _run(
        ["pactl", f"get-{kind}-volume", f"@DEFAULT_{kind.upper()}@"]
    )
    return parse_volume(output) if code == 0 else 0


def _mute(kind: str) -> bool:
    code, output = _run(
        ["pactl", f"get-{kind}-mute", f"@DEFAULT_{kind.upper()}@"]
    )
    return parse_mute(output) if code == 0 else False


def parse_sink_inputs(payload: str) -> list[dict]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        properties = item.get("properties") or {}
        name = (
            properties.get("application.name")
            or properties.get("media.name")
            or properties.get("application.process.binary")
            or f"Sink input {item.get('index', '?')}"
        )
        result.append(
            {
                "index": int(item.get("index", 0)),
                "name": str(name),
                "sink": int(item.get("sink", 0)),
                "mute": bool(item.get("mute", False)),
            }
        )
    return result


def list_sink_inputs() -> list[dict]:
    code, output = _run(["pactl", "-f", "json", "list", "sink-inputs"])
    return parse_sink_inputs(output) if code == 0 else []


def sink_input_volume(index: int) -> int:
    code, output = _run(["pactl", "get-sink-input-volume", str(index)])
    return parse_volume(output) if code == 0 else 0


def sink_input_mute(index: int) -> bool:
    code, output = _run(["pactl", "get-sink-input-mute", str(index)])
    return parse_mute(output) if code == 0 else False


class AudioPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._loading = False

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        scroller.set_child(content)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        heading = Gtk.Label(label=t("Audio"))
        heading.add_css_class("heading")
        heading.set_hexpand(True)
        heading.set_halign(Gtk.Align.START)
        toolbar.append(heading)
        refresh = Gtk.Button()
        refresh.set_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text(t("Reload"))
        refresh.connect("clicked", lambda _b: self.load())
        toolbar.append(refresh)
        content.append(toolbar)

        # ── Output ────────────────────────────────────────────────────────
        output = Adw.PreferencesGroup(title=t("Output"))
        content.append(output)

        self.output_device = Adw.ActionRow(title=t("Output device"))
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_valign(Gtk.Align.CENTER)
        self.output_combo.connect("changed", self._on_output_device)
        self.output_device.add_suffix(self.output_combo)
        output.add(self.output_device)

        self.output_volume_row = Adw.ActionRow(title=t("Volume"))
        self.output_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.output_volume.set_draw_value(True)
        self.output_volume.set_size_request(220, -1)
        self.output_volume.set_valign(Gtk.Align.CENTER)
        self.output_volume.connect("value-changed", self._on_output_volume)
        self.output_volume_row.add_suffix(self.output_volume)
        output.add(self.output_volume_row)

        self.output_mute = Adw.SwitchRow(title=t("Mute output"))
        self.output_mute.connect("notify::active", self._on_output_mute)
        output.add(self.output_mute)

        test_row = Adw.ActionRow(title=t("Test output"), subtitle=t("Play a short test sound"))
        test = Gtk.Button(label=t("Play"))
        test.set_valign(Gtk.Align.CENTER)
        test.connect("clicked", self._on_test)
        test_row.add_suffix(test)
        output.add(test_row)

        # ── Input ─────────────────────────────────────────────────────────
        microphone = Adw.PreferencesGroup(title=t("Input"))
        content.append(microphone)

        self.input_device = Adw.ActionRow(title=t("Input device"))
        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.set_valign(Gtk.Align.CENTER)
        self.input_combo.connect("changed", self._on_input_device)
        self.input_device.add_suffix(self.input_combo)
        microphone.add(self.input_device)

        self.input_volume_row = Adw.ActionRow(title=t("Volume"))
        self.input_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.input_volume.set_draw_value(True)
        self.input_volume.set_size_request(220, -1)
        self.input_volume.set_valign(Gtk.Align.CENTER)
        self.input_volume.connect("value-changed", self._on_input_volume)
        self.input_volume_row.add_suffix(self.input_volume)
        microphone.add(self.input_volume_row)

        self.input_mute = Adw.SwitchRow(title=t("Mute input"))
        self.input_mute.connect("notify::active", self._on_input_mute)
        microphone.add(self.input_mute)

        self._apps_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self._apps_wrapper)
        self._build_apps()

        self.load()

    # ── Loading ───────────────────────────────────────────────────────────

    def load(self):
        self._loading = True
        try:
            sinks = _list_devices("sinks")
            sources = _list_devices("sources")
            default_sink = _default_device("sink")
            default_source = _default_device("source")

            self.output_combo.remove_all()
            for name, description in sinks.items():
                self.output_combo.append(name, description or name)
            if default_sink:
                if not self.output_combo.set_active_id(default_sink):
                    self.output_combo.append(default_sink, default_sink)
                    self.output_combo.set_active_id(default_sink)
            elif sinks:
                self.output_combo.set_active(0)

            self.input_combo.remove_all()
            for name, description in sources.items():
                self.input_combo.append(name, description or name)
            if default_source:
                if not self.input_combo.set_active_id(default_source):
                    self.input_combo.append(default_source, default_source)
                    self.input_combo.set_active_id(default_source)
            elif sources:
                self.input_combo.set_active(0)

            self.output_volume.set_value(_volume("sink"))
            self.output_mute.set_active(_mute("sink"))
            self.input_volume.set_value(_volume("source"))
            self.input_mute.set_active(_mute("source"))
            self._refresh_apps()
        finally:
            self._loading = False

    # ── Per-application volume ────────────────────────────────────────────

    def _build_apps(self):
        self._apps_group = Adw.PreferencesGroup(
            title=t("Applications"),
            description=t("Volume for apps currently playing audio."),
        )
        self._apps_wrapper.append(self._apps_group)

    def _refresh_apps(self):
        if self._apps_group.get_first_child() is not None:
            # Adw.PreferencesGroup has no remove(); replace it.
            self._apps_wrapper.remove(self._apps_group)
            self._build_apps()
        inputs = list_sink_inputs()
        if not inputs:
            self._apps_group.add(
                Adw.ActionRow(
                    title=t("No applications playing audio"),
                    subtitle=t("Start playback to control app volumes here."),
                )
            )
            return
        for item in inputs:
            index = item["index"]
            row = Adw.ActionRow(
                title=item["name"],
                subtitle=f"Sink input {index}  ·  sink {item['sink']}",
            )
            volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            volume.set_draw_value(True)
            volume.set_size_request(160, -1)
            volume.set_valign(Gtk.Align.CENTER)
            volume.set_value(sink_input_volume(index))
            volume.connect(
                "value-changed",
                lambda scale, idx=index: self._set_app_volume(idx, scale),
            )
            row.add_suffix(volume)

            mute = Gtk.Switch()
            mute.set_valign(Gtk.Align.CENTER)
            mute.set_active(sink_input_mute(index))
            mute.connect(
                "notify::active",
                lambda switch, _p, idx=index: _run(
                    ["pactl", "set-sink-input-mute", str(idx), "1" if switch.get_active() else "0"]
                ),
            )
            row.add_suffix(mute)
            self._apps_group.add(row)

    def _set_app_volume(self, index: int, scale):
        if self._loading:
            return
        _run(
            ["pactl", "set-sink-input-volume", str(index), f"{int(scale.get_value())}%"]
        )

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _on_output_device(self, combo):
        if self._loading:
            return
        name = combo.get_active_id()
        if name:
            _run(["pactl", "set-default-sink", name])
            self.load()

    def _on_input_device(self, combo):
        if self._loading:
            return
        name = combo.get_active_id()
        if name:
            _run(["pactl", "set-default-source", name])
            self.load()

    def _on_output_volume(self, scale):
        if self._loading:
            return
        _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(scale.get_value())}%"])

    def _on_input_volume(self, scale):
        if self._loading:
            return
        _run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{int(scale.get_value())}%"])

    def _on_output_mute(self, row, _param):
        if self._loading:
            return
        _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if row.get_active() else "0"])

    def _on_input_mute(self, row, _param):
        if self._loading:
            return
        _run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if row.get_active() else "0"])

    def _on_test(self, _button):
        sound = next((path for path in _TEST_SOUNDS if path.exists()), None)
        if sound is None:
            self.main_window.add_toast(Adw.Toast.new(t("No test sound found.")))
            return
        try:
            subprocess.Popen(["paplay", str(sound)])
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not play test sound')}: {exc}")
            )
