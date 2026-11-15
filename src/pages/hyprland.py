"""Hyprland look-and-feel (Caelestia variables).

Caelestia exposes its Hyprland styling through ``variables.lua``
(``local vars = require("variables")`` in every ``hyprland/*.lua`` file).
This page edits *overrides* only: values are stored in the user-owned
``~/.config/caelestia/hypr-vars.lua``, which Caelestia merges over its
defaults at startup.  ``variables.lua`` itself is never touched, so dotfiles
updates keep working.

A value equal to the Caelestia default removes the override instead of
writing a redundant copy.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, lua
from src.config import HYPR_VARIABLES_LUA, HYPR_VARS_LUA, read_text
from src.lang import t

# (key, label, kind, min, max, step)
# kind: bool | int | float | str
SECTIONS: list[tuple[str, str, list[tuple]]] = [
    (
        t("Gaps"),
        t("Spacing between windows and the screen edge."),
        [
            ("workspaceGaps", t("Workspace gaps"), "int", 0, 100, 1),
            ("windowGapsIn", t("Inner gaps"), "int", 0, 100, 1),
            ("windowGapsOut", t("Outer gaps"), "int", 0, 100, 1),
            ("singleWindowGapsOut", t("Single window outer gaps"), "int", 0, 100, 1),
        ],
    ),
    (
        t("Windows"),
        t("Opacity, rounding and border size."),
        [
            ("windowOpacity", t("Window opacity"), "float", 0.0, 1.0, 0.01),
            ("windowRounding", t("Window rounding"), "int", 0, 50, 1),
            ("windowBorderSize", t("Border size"), "int", 0, 10, 1),
            ("activeWindowBorderColour", t("Active border colour"), "str",),
            ("inactiveWindowBorderColour", t("Inactive border colour"), "str",),
        ],
    ),
    (
        t("Blur"),
        t("Blur is disabled automatically in game mode."),
        [
            ("blurEnabled", t("Enable blur"), "bool"),
            ("blurSpecialWs", t("Blur special workspaces"), "bool"),
            ("blurPopups", t("Blur popups"), "bool"),
            ("blurInputMethods", t("Blur input methods"), "bool"),
            ("blurXray", t("X-ray blur"), "bool"),
            ("blurSize", t("Blur size"), "int", 1, 32, 1),
            ("blurPasses", t("Blur passes"), "int", 1, 8, 1),
        ],
    ),
    (
        t("Shadows"),
        t("Drop shadows behind windows."),
        [
            ("shadowEnabled", t("Enable shadows"), "bool"),
            ("shadowRange", t("Shadow range"), "int", 0, 60, 1),
            ("shadowRenderPower", t("Shadow render power"), "int", 1, 8, 1),
            ("shadowColour", t("Shadow colour"), "str"),
        ],
    ),
    (
        t("Gestures"),
        t("Touchpad options are on the General page."),
        [
            ("gestureFingers", t("Gesture fingers"), "int", 3, 5, 1),
            ("workspaceSwipeFingers", t("Workspace swipe fingers"), "int", 3, 5, 1),
            ("gestureFingersMore", t("Extra gesture fingers"), "int", 3, 5, 1),
        ],
    ),
    (
        t("Cursor"),
        t("Cursor theme and size."),
        [
            ("cursorTheme", t("Cursor theme"), "str"),
            ("cursorSize", t("Cursor size"), "int", 16, 96, 1),
        ],
    ),
    (
        t("Volume and sleep"),
        t("Volume steps and the sleep command."),
        [
            ("volumeStep", t("Volume step (%)"), "int", 1, 50, 1),
            ("volumeMax", t("Maximum volume (%)"), "int", 1, 150, 1),
            ("sleepGestureCmd", t("Sleep command"), "str"),
        ],
    ),
]

SPEC_KEYS = {spec[0] for _title, _description, specs in SECTIONS for spec in specs}


def _read_defaults() -> dict:
    return lua.read_table_values(read_text(HYPR_VARIABLES_LUA)) if HYPR_VARIABLES_LUA.exists() else {}


def _read_overrides() -> dict:
    return lua.read_table_values(read_text(HYPR_VARS_LUA)) if HYPR_VARS_LUA.exists() else {}


class HyprlandPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._widgets: dict[str, tuple[str, Gtk.Widget]] = {}
        self._is_loading = True

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

        header = Adw.PreferencesGroup(
            title=t("Hyprland appearance"),
            description=t(
                "Only values that differ from Caelestia's defaults are written, "
                "as overrides in ~/.config/caelestia/hypr-vars.lua."
            ),
        )
        content.append(header)

        for title, description, specs in SECTIONS:
            group = Adw.PreferencesGroup(title=title, description=description)
            content.append(group)
            for spec in specs:
                self._add_widget(group, spec)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        actions.set_margin_top(4)

        reset_btn = Gtk.Button(label=t("Reset to Caelestia defaults"))
        reset_btn.connect("clicked", self._on_reset)
        actions.append(reset_btn)

        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        actions.append(apply_btn)
        content.append(actions)

        self._load_values()
        self._is_loading = False

    # ── Widgets ───────────────────────────────────────────────────────────

    def _add_widget(self, group: Adw.PreferencesGroup, spec: tuple) -> None:
        key, label = spec[0], spec[1]
        kind = spec[2]
        if kind == "bool":
            row = Adw.SwitchRow(title=label, subtitle=key)
            group.add(row)
        elif kind in ("int", "float"):
            _key, _label, _kind, minimum, maximum, step = spec
            row = Adw.SpinRow.new_with_range(minimum, maximum, step)
            row.set_title(label)
            row.set_subtitle(key)
            if kind == "float":
                row.set_digits(2)
            group.add(row)
        else:
            row = Adw.EntryRow(title=label)
            row.set_tooltip_text(key)
            group.add(row)
        self._widgets[key] = (kind, row)

    def _load_values(self) -> None:
        values = {**_read_defaults(), **_read_overrides()}
        overrides = _read_overrides()
        for key, (kind, row) in self._widgets.items():
            value = values.get(key)
            if value is None:
                continue
            if kind == "bool":
                row.set_active(bool(value))
            elif kind == "int":
                try:
                    row.set_value(int(float(str(value))))
                except (TypeError, ValueError):
                    pass
            elif kind == "float":
                try:
                    row.set_value(float(str(value)))
                except (TypeError, ValueError):
                    pass
            else:
                row.set_text(str(value))
                if key in overrides:
                    row.set_tooltip_text(f"{key} — {t('overridden')}")

    def _collect(self) -> dict:
        values: dict = {}
        for key, (kind, row) in self._widgets.items():
            if kind == "bool":
                values[key] = row.get_active()
            elif kind == "int":
                values[key] = int(row.get_value())
            elif kind == "float":
                values[key] = round(row.get_value(), 2)
            else:
                values[key] = row.get_text().strip()
        return values

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_apply(self, _button):
        defaults = _read_defaults()
        overrides = _read_overrides()
        values = self._collect()

        updates: dict = {}
        removals: list[str] = []
        for key, value in values.items():
            default = defaults.get(key)
            if default is not None and str(default) == str(value):
                if key in overrides:
                    removals.append(key)
            else:
                updates[key] = value

        try:
            text = read_text(HYPR_VARS_LUA)
            if not text.strip():
                text = "return {\n}\n"
            if updates:
                text = lua.set_table_values(text, updates)
            if removals:
                text = lua.remove_table_values(text, removals)
            apply.write_and_reload(HYPR_VARS_LUA, text)
            self._load_values()
            self.main_window.add_toast(
                Adw.Toast.new(t("Hyprland appearance applied."))
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save Hyprland appearance')}: {exc}")
            )

    def _on_reset(self, _button):
        try:
            text = read_text(HYPR_VARS_LUA)
            new_text = lua.remove_table_values(text, SPEC_KEYS)
            if new_text != text:
                apply.write_and_reload(HYPR_VARS_LUA, new_text)
            self._load_values()
            self.main_window.add_toast(
                Adw.Toast.new(t("Caelestia defaults restored."))
            )
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not reset appearance')}: {exc}")
            )
