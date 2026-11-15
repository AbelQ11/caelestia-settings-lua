"""Per-device input settings (keyboard, mouse, touchpad, tablet, touch)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, devices
from src.config import HYPR_USER_LUA, read_text
from src.lang import t

KIND_TITLES = {
    "keyboard": t("Keyboards"),
    "pointer": t("Mice"),
    "touchpad": t("Touchpads"),
    "touch": t("Touchscreens"),
    "tablet": t("Tablets"),
}

KIND_ICONS = {
    "keyboard": "input-keyboard-symbolic",
    "pointer": "input-mouse-symbolic",
    "touchpad": "input-touchpad-symbolic",
    "touch": "input-touchscreen-symbolic",
    "tablet": "input-tablet-symbolic",
}


class InputDevicesPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._values: dict[str, dict] = {}
        self._overrides: dict[str, dict] = {}
        self._defaults: dict = {}
        self._kinds: dict[str, str] = {}
        self._reset: set[str] = set()
        self._loading = True

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)

        title = Gtk.Label(label=t("Input devices"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        bar.append(title)

        self.show_system = Gtk.ToggleButton()
        self.show_system.set_icon_name("utilities-system-monitor-symbolic")
        self.show_system.set_tooltip_text(t("Show virtual/system devices"))
        self.show_system.connect("toggled", lambda _b: self._load())
        bar.append(self.show_system)

        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _b: self._load())
        bar.append(reload_btn)

        self.apply_btn = Gtk.Button(label=t("Apply"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.set_sensitive(False)
        self.apply_btn.connect("clicked", self._on_apply)
        bar.append(self.apply_btn)
        self.append(bar)

        note = Gtk.Label(
            label=t(
                "Only values that differ from the global Hyprland input defaults are written. "
                "Overrides live in hypr-user.lua and every apply creates a backup."
            )
        )
        note.set_halign(Gtk.Align.START)
        note.set_margin_start(12)
        note.set_margin_end(12)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        self.append(note)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.set_margin_top(8)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._load()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self):
        self._loading = True
        while child := self.content.get_first_child():
            self.content.remove(child)

        self._overrides = devices.load_overrides()
        self._defaults = devices.global_defaults()
        all_devices = devices.list_devices()
        device_list = [
            device for device in all_devices
            if self.show_system.get_active() or not devices.is_system_device(device.name)
        ]
        self._values = {}
        self._kinds = {device.name: device.kind for device in all_devices}

        if not device_list:
            status = Adw.StatusPage()
            status.set_icon_name("input-keyboard-symbolic")
            if all_devices:
                status.set_title(t("Only system devices found"))
                status.set_description(
                    t("Enable “Show virtual/system devices” to configure power buttons, "
                      "video buses and other internal devices.")
                )
            else:
                status.set_title(t("No input devices found"))
                status.set_description(t("Is Hyprland running? hyprctl returned no devices."))
            self.content.append(status)
            self._loading = False
            self.apply_btn.set_sensitive(False)
            return

        by_kind: dict[str, list[devices.Device]] = {}
        for device in device_list:
            by_kind.setdefault(device.kind, []).append(device)

        for kind in ("keyboard", "pointer", "touchpad", "touch", "tablet"):
            entries = by_kind.get(kind, [])
            if not entries:
                continue
            group = Adw.PreferencesGroup(title=KIND_TITLES.get(kind, kind.title()))
            self.content.append(group)
            for device in sorted(entries, key=lambda item: item.name.lower()):
                group.add(self._device_expander(device))

        self._loading = False
        self._update_apply()

    def _device_expander(self, device: devices.Device) -> Gtk.Widget:
        override = {} if device.name in self._reset else self._overrides.get(device.name, {})
        values: dict = {}
        for key, _label, kind, _min, _max, _step, _option, _enum in devices.FIELDS[device.kind]:
            if key in override:
                values[key] = override[key]
            elif key in self._defaults:
                values[key] = self._defaults[key]
            else:
                values[key] = devices.default_for(key, kind)
        self._values[device.name] = values

        overridden = len(override)
        expander = Adw.ExpanderRow(
            title=device.name,
            subtitle=f"{device.kind} · {device.address or device.description} · "
            f"{overridden} {t('override(s)')}",
        )
        icon = Gtk.Image.new_from_icon_name(KIND_ICONS.get(device.kind, "input-keyboard-symbolic"))
        icon.set_valign(Gtk.Align.CENTER)
        expander.add_prefix(icon)

        reset = Gtk.Button()
        reset.set_icon_name("edit-undo-symbolic")
        reset.add_css_class("flat")
        reset.set_tooltip_text(t("Reset this device to the global defaults"))
        reset.set_valign(Gtk.Align.CENTER)
        reset.connect("clicked", lambda _b, name=device.name: self._reset_device(name))
        expander.add_suffix(reset)

        for key, label, kind, minimum, maximum, step, _option, enum_values in devices.FIELDS[device.kind]:
            row = self._field_row(
                device.name, key, label, kind, minimum, maximum, step, enum_values, values
            )
            expander.add_row(row)
        return expander

    def _field_row(self, device_name, key, label, kind, minimum, maximum, step, enum_values, values):
        subtitle = key
        if kind == "bool":
            row = Adw.SwitchRow(title=label, subtitle=subtitle)
            row.set_active(bool(values.get(key, False)))
            row.connect(
                "notify::active",
                lambda r, _p: self._set(device_name, key, r.get_active()),
            )
            return row

        if kind in ("int", "float"):
            row = Adw.SpinRow.new_with_range(minimum, maximum, step)
            row.set_title(label)
            row.set_subtitle(subtitle)
            if kind == "float":
                row.set_digits(2)
            try:
                row.set_value(float(values.get(key, minimum)))
            except (TypeError, ValueError):
                row.set_value(minimum)
            row.connect(
                "notify::value",
                lambda r, _p: self._set(
                    device_name, key, round(r.get_value(), 2) if kind == "float" else int(r.get_value())
                ),
            )
            return row

        row = Adw.ActionRow(title=label, subtitle=subtitle)
        if kind == "enum":
            combo = Gtk.ComboBoxText()
            combo.set_valign(Gtk.Align.CENTER)
            for enum_value in enum_values:
                combo.append(enum_value, enum_value)
            current = str(values.get(key, ""))
            if not combo.set_active_id(current):
                combo.append(current, current or t("Default"))
                combo.set_active_id(current)
            combo.connect("changed", lambda c: self._set(device_name, key, c.get_active_id() or ""))
            row.add_suffix(combo)
        else:
            entry = Gtk.Entry()
            entry.set_text(str(values.get(key, "")))
            entry.set_width_chars(26)
            entry.set_valign(Gtk.Align.CENTER)
            entry.connect("changed", lambda e: self._set(device_name, key, e.get_text()))
            row.add_suffix(entry)
        return row

    # ── State ─────────────────────────────────────────────────────────────

    def _set(self, device_name: str, key: str, value):
        if self._loading:
            return
        self._values.setdefault(device_name, {})[key] = value
        self._update_apply()

    def _update_apply(self):
        dirty = bool(self._reset)
        if not dirty:
            for values in self._values.values():
                for key, value in values.items():
                    if value != self._defaults.get(key, devices.default_for(key, "str")):
                        dirty = True
                        break
                if dirty:
                    break
        self.apply_btn.set_sensitive(dirty)

    def _reset_device(self, name: str):
        kind = self._kinds.get(name)
        if kind is None:
            return
        self._reset.add(name)
        self._values[name] = {
            key: self._defaults.get(key, devices.default_for(key, field_kind))
            for key, _label, field_kind, _min, _max, _step, _option, _enum in devices.FIELDS[kind]
        }
        self.apply_btn.set_sensitive(True)
        self._load()

    # ── Apply ─────────────────────────────────────────────────────────────

    def _on_apply(self, _button):
        overrides: dict[str, dict] = {}
        for name, values in self._values.items():
            entry = {}
            for key, value in values.items():
                default = self._defaults.get(key, devices.default_for(key, "str"))
                if value != default:
                    entry[key] = value
            if entry:
                overrides[name] = entry

        try:
            text = read_text(HYPR_USER_LUA)
            if not text.strip():
                text = "local config = {}\n\nreturn config\n"
            apply.write_and_reload(HYPR_USER_LUA, devices.write_overrides(text, overrides))
            self._reset.clear()
            self._load()
            self.main_window.add_toast(
                Adw.Toast.new(
                    t("Input device settings applied.")
                    if overrides
                    else t("Input device overrides removed.")
                )
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001 - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save input device settings')}: {exc}")
            )
