"""General input, region and language settings.

Input overrides are written to a managed ``hl.config`` block in
``~/.config/caelestia/hypr-user.lua`` (the user-owned file Caelestia loads
last), never to the dotfiles-managed ``hyprland/input.lua``.  Gestures and
cursor values are overrides in ``hypr-vars.lua``.  Every write creates a
timestamped backup (see :mod:`src.backup`).
"""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import apply, backup, lua
from src.config import (
    BLOCK_INPUT,
    HYPR_INPUT_LUA,
    HYPR_USER_LUA,
    HYPR_VARIABLES_LUA,
    HYPR_VARS_LUA,
    read_text,
    hyprctl_config_errors,
    reload_hyprland,
    reload_hyprland_checked,
)
from src.lang import t

# (xkb code, English display name)
KEYBOARD_LAYOUTS = [
    ("ad", "Andorran"), ("af", "Afghan"), ("al", "Albanian"), ("am", "Armenian"),
    ("ara", "Arabic"), ("at", "Austrian"), ("au", "Australian"), ("az", "Azerbaijani"),
    ("ba", "Bosnian"), ("bd", "Bengali"), ("be", "Belgian"), ("bg", "Bulgarian"),
    ("br", "Brazilian"), ("brai", "Braille"), ("bt", "Bhutanese"), ("bw", "Botswana"),
    ("by", "Belarusian"), ("ca", "Canadian"), ("cd", "Congolese (DR)"), ("ch", "Swiss"),
    ("cm", "Cameroonian"), ("cn", "Chinese"), ("cz", "Czech"), ("de", "German"),
    ("dk", "Danish"), ("ee", "Estonian"), ("epo", "Esperanto"), ("es", "Spanish"),
    ("et", "Ethiopian"), ("eu", "Basque"), ("fi", "Finnish"), ("fo", "Faroese"),
    ("fr", "French"), ("gb", "English (UK)"), ("ge", "Georgian"), ("gh", "Ghanaian"),
    ("gn", "Guinean"), ("gr", "Greek"), ("hr", "Croatian"), ("hu", "Hungarian"),
    ("ie", "Irish"), ("il", "Hebrew"), ("in", "Indian"), ("iq", "Iraqi"),
    ("ir", "Persian"), ("is", "Icelandic"), ("it", "Italian"), ("jp", "Japanese"),
    ("ke", "Kenyan"), ("kg", "Kyrgyz"), ("kh", "Khmer"), ("kr", "Korean"),
    ("kz", "Kazakh"), ("la", "Lao"), ("latam", "Latin American"), ("lk", "Sinhala"),
    ("lt", "Lithuanian"), ("lv", "Latvian"), ("ma", "Moroccan"), ("mao", "Maori"),
    ("md", "Moldavian"), ("me", "Montenegrin"), ("mk", "Macedonian"), ("ml", "Mali"),
    ("mm", "Myanmar"), ("mn", "Mongolian"), ("mt", "Maltese"), ("mv", "Dhivehi"),
    ("my", "Malay"), ("ng", "Nigerian"), ("nl", "Dutch"), ("no", "Norwegian"),
    ("np", "Nepali"), ("ph", "Filipino"), ("pk", "Pakistani"), ("pl", "Polish"),
    ("pt", "Portuguese"), ("ro", "Romanian"), ("rs", "Serbian"), ("ru", "Russian"),
    ("se", "Swedish"), ("si", "Slovenian"), ("sk", "Slovak"), ("sn", "Senegalese"),
    ("sy", "Syrian"), ("tg", "Togo"), ("th", "Thai"), ("tj", "Tajik"),
    ("tm", "Turkmen"), ("tr", "Turkish"), ("tw", "Taiwanese"), ("tz", "Tanzanian"),
    ("ua", "Ukrainian"), ("us", "English (US)"), ("uz", "Uzbek"), ("vn", "Vietnamese"),
    ("za", "South African"),
]

LAYOUT_OPTIONS = [
    ("", "None"),
    ("grp:alt_shift_toggle", "Alt + Shift"),
    ("grp:ctrl_shift_toggle", "Ctrl + Shift"),
    ("grp:win_space_toggle", "Super + Space"),
    ("grp:caps_toggle", "Caps Lock"),
    ("grp:alt_caps_toggle", "Alt + Caps Lock"),
    ("grp_led:scroll", "Scroll Lock LED"),
    ("compose:ralt", "Compose key (right Alt)"),
]

GESTURE_FINGERS = [("3", "3 fingers"), ("4", "4 fingers"), ("5", "5 fingers")]


def _layout_label(code: str) -> str:
    for xkb_code, label in KEYBOARD_LAYOUTS:
        if xkb_code == code:
            return f"{label}  ({xkb_code})"
    return code


def _hypr_getoption(name: str) -> str | None:
    try:
        result = subprocess.run(
            ["hyprctl", "getoption", name], capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    first = result.stdout.splitlines()[0].strip() if result.stdout else ""
    if ":" in first:
        return first.split(":", 1)[1].strip()
    return first or None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _read_managed_input() -> dict:
    """Read the ``input`` table from our managed block in hypr-user.lua."""

    text = read_text(HYPR_USER_LUA)
    body = lua.strip_managed_block(text, BLOCK_INPUT)
    if body:
        for call in lua.iter_calls(body, {"hl.config"}):
            if isinstance(call.table, dict):
                value = call.table.get("input")
                if isinstance(value, dict):
                    return value
    # Legacy fallback: read the dotfiles-managed input.lua (read-only).
    legacy = read_text(HYPR_INPUT_LUA)
    if legacy:
        for call in lua.iter_calls(legacy, {"hl.config"}):
            if isinstance(call.table, dict):
                value = call.table.get("input")
                if isinstance(value, dict):
                    return value
    return {}


def read_input_conf() -> dict:
    """Return the effective input settings as plain values."""

    managed = _read_managed_input()
    layout = _hypr_getoption("input:kb_layout")
    variant = _hypr_getoption("input:kb_variant")
    options = _hypr_getoption("input:kb_options")
    numlock = _hypr_getoption("input:numlock_by_default")
    repeat_rate = _hypr_getoption("input:repeat_rate")
    repeat_delay = _hypr_getoption("input:repeat_delay")

    layouts = (layout or str(managed.get("kb_layout", "us"))).replace(" ", "")
    variants = (variant or str(managed.get("kb_variant", ""))).replace(" ", "")

    touchpad = managed.get("touchpad") if isinstance(managed.get("touchpad"), dict) else {}
    return {
        "kb_layout": layouts,
        "primary_layout": layouts.split(",")[0] if layouts else "us",
        "extra_layouts": ",".join(layouts.split(",")[1:]) if "," in layouts else "",
        "kb_variant": variants or "",
        "kb_options": options or str(managed.get("kb_options", "")),
        "numlock_by_default": "true" if _as_bool(numlock, bool(managed.get("numlock_by_default", False))) else "false",
        "repeat_rate": str(_as_int(repeat_rate, _as_int(str(managed.get("repeat_rate", 40)), 40))),
        "repeat_delay": str(_as_int(repeat_delay, _as_int(str(managed.get("repeat_delay", 250)), 250))),
        "natural_scroll": _as_bool(_hypr_getoption("input:touchpad:natural_scroll"), bool(touchpad.get("natural_scroll", False))),
        "tap_to_click": _as_bool(_hypr_getoption("input:touchpad:tap-to-click"), bool(touchpad.get("tap-to-click", False))),
        "disable_while_typing": _as_bool(
            _hypr_getoption("input:touchpad:disable_while_typing"),
            bool(touchpad.get("disable_while_typing", True)),
        ),
        "scroll_factor": str(
            _as_float(_hypr_getoption("input:touchpad:scroll_factor"), _as_float(str(touchpad.get("scroll_factor", 0.3)), 0.3))
        ),
    }


read_input_lua = read_input_conf


def _read_vars() -> dict:
    """Caelestia defaults from variables.lua, then user overrides."""

    result: dict = {}
    for path in (HYPR_VARIABLES_LUA, HYPR_VARS_LUA):
        if not path.exists():
            continue
        result.update(lua.read_table_values(read_text(path)))
    return result


def _write_vars(updates: dict) -> None:
    text = read_text(HYPR_VARS_LUA)
    if not text.strip():
        text = "return {\n}\n"
    new_text = lua.set_table_values(text, updates)
    apply.write_and_reload(HYPR_VARS_LUA, new_text)


def _write_input_block(values: dict) -> str:
    text = read_text(HYPR_USER_LUA)
    if not text.strip():
        text = "local config = {}\n\nreturn config\n"

    body = lua.strip_managed_block(text, BLOCK_INPUT)
    existing_input: dict = {}
    existing_cursor: dict = {}
    if body:
        for call in lua.iter_calls(body, {"hl.config"}):
            if isinstance(call.table, dict):
                if isinstance(call.table.get("input"), dict):
                    existing_input = dict(call.table["input"])
                if isinstance(call.table.get("cursor"), dict):
                    existing_cursor = dict(call.table["cursor"])

    touchpad = dict(existing_input.get("touchpad") or {})
    touchpad.update(
        {
            "natural_scroll": values["natural_scroll"],
            "tap-to-click": values["tap_to_click"],
            "disable_while_typing": values["disable_while_typing"],
            "scroll_factor": values["scroll_factor"],
        }
    )

    input_table = dict(existing_input)
    input_table.update(
        {
            "kb_layout": values["kb_layout"],
            "kb_variant": values["kb_variant"],
            "kb_options": values["kb_options"],
            "numlock_by_default": values["numlock_by_default"] == "true",
            "repeat_rate": values["repeat_rate_int"],
            "repeat_delay": values["repeat_delay_int"],
            "touchpad": touchpad,
        }
    )

    config_table: dict = {"input": input_table}
    if existing_cursor:
        config_table["cursor"] = existing_cursor

    block_body = f"hl.config({lua.format_value(config_table)})"
    return lua.replace_managed_block(text, BLOCK_INPUT, block_body)


def _apply_live_input(values: dict) -> None:
    keywords = {
        "input:kb_layout": values["kb_layout"],
        "input:kb_variant": values["kb_variant"],
        "input:kb_options": values["kb_options"],
        "input:numlock_by_default": values["numlock_by_default"],
        "input:repeat_rate": values["repeat_rate"],
        "input:repeat_delay": values["repeat_delay"],
        "input:touchpad:natural_scroll": "true" if values["natural_scroll"] else "false",
        "input:touchpad:tap-to-click": "true" if values["tap_to_click"] else "false",
        "input:touchpad:disable_while_typing": "true" if values["disable_while_typing"] else "false",
        "input:touchpad:scroll_factor": values["scroll_factor"],
    }
    for name, value in keywords.items():
        try:
            subprocess.run(
                ["hyprctl", "keyword", name, str(value)],
                capture_output=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass


def _list_locales() -> list[str]:
    fallback = [
        "en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8", "es_ES.UTF-8",
        "it_IT.UTF-8", "nl_NL.UTF-8", "pl_PL.UTF-8", "pt_PT.UTF-8", "ru_RU.UTF-8",
    ]
    try:
        result = subprocess.run(
            ["localectl", "list-locales"], capture_output=True, text=True, timeout=5
        )
        locales = [line.strip() for line in result.stdout.splitlines() if line.strip().endswith("UTF-8")]
        return locales or fallback
    except (OSError, subprocess.SubprocessError):
        return fallback


def _list_timezones() -> list[str]:
    try:
        result = subprocess.run(
            ["timedatectl", "list-timezones"], capture_output=True, text=True, timeout=5
        )
        zones = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return zones or ["UTC"]
    except (OSError, subprocess.SubprocessError):
        return ["UTC"]


class GeneralPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._loading = True

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

        # ── Keyboard ──────────────────────────────────────────────────────
        keyboard = Adw.PreferencesGroup(
            title=t("Keyboard"),
            description=t("Applies immediately and is saved to hypr-user.lua."),
        )
        content.append(keyboard)

        layout_row = Adw.ActionRow(
            title=t("Keyboard layout"),
            subtitle=t("Primary layout; extra layouts are selected with the layout option."),
        )
        self.layout_combo = Gtk.ComboBoxText()
        self.layout_combo.set_valign(Gtk.Align.CENTER)
        for code, label in KEYBOARD_LAYOUTS:
            self.layout_combo.append(code, f"{label}  ({code})")
        layout_row.add_suffix(self.layout_combo)
        keyboard.add(layout_row)

        self.extra_layout_row = Adw.EntryRow(title=t("Additional layouts (comma separated)"))
        self.extra_layout_row.set_show_apply_button(True)
        keyboard.add(self.extra_layout_row)

        self.variant_row = Adw.EntryRow(title=t("Layout variants (comma separated)"))
        self.variant_row.set_show_apply_button(True)
        keyboard.add(self.variant_row)

        options_row = Adw.ActionRow(title=t("Layout switch option"), subtitle="XKB group option")
        self.options_combo = Gtk.ComboBoxText()
        self.options_combo.set_valign(Gtk.Align.CENTER)
        for option, label in LAYOUT_OPTIONS:
            self.options_combo.append(option, label)
        options_row.add_suffix(self.options_combo)
        keyboard.add(options_row)

        self.numlock_row = Adw.SwitchRow(
            title=t("NumLock on startup"),
            subtitle="input:numlock_by_default",
        )
        keyboard.add(self.numlock_row)

        self.repeat_rate_row = Adw.SpinRow.new_with_range(10, 100, 1)
        self.repeat_rate_row.set_title(t("Key repeat rate"))
        self.repeat_rate_row.set_subtitle(t("Keys per second"))
        keyboard.add(self.repeat_rate_row)

        self.repeat_delay_row = Adw.SpinRow.new_with_range(100, 1000, 10)
        self.repeat_delay_row.set_title(t("Key repeat delay"))
        self.repeat_delay_row.set_subtitle(t("Milliseconds before repeating"))
        keyboard.add(self.repeat_delay_row)

        # ── Touchpad ──────────────────────────────────────────────────────
        touchpad = Adw.PreferencesGroup(title=t("Touchpad"))
        content.append(touchpad)

        self.natural_scroll_row = Adw.SwitchRow(title=t("Natural scrolling"))
        touchpad.add(self.natural_scroll_row)

        self.tap_click_row = Adw.SwitchRow(title=t("Tap to click"))
        touchpad.add(self.tap_click_row)

        self.disable_typing_row = Adw.SwitchRow(title=t("Disable while typing"))
        touchpad.add(self.disable_typing_row)

        self.scroll_factor_row = Adw.SpinRow.new_with_range(0.1, 3.0, 0.1)
        self.scroll_factor_row.set_digits(2)
        self.scroll_factor_row.set_title(t("Scroll factor"))
        touchpad.add(self.scroll_factor_row)

        # ── Gestures ──────────────────────────────────────────────────────
        gestures = Adw.PreferencesGroup(
            title=t("Gestures"),
            description=t("Stored as overrides in hypr-vars.lua."),
        )
        content.append(gestures)

        gesture_row = Adw.ActionRow(title=t("Gesture fingers"))
        self.gesture_combo = Gtk.ComboBoxText()
        self.gesture_combo.set_valign(Gtk.Align.CENTER)
        for fingers, label in GESTURE_FINGERS:
            self.gesture_combo.append(fingers, label)
        gesture_row.add_suffix(self.gesture_combo)
        gestures.add(gesture_row)

        swipe_row = Adw.ActionRow(title=t("Workspace swipe fingers"))
        self.swipe_combo = Gtk.ComboBoxText()
        self.swipe_combo.set_valign(Gtk.Align.CENTER)
        for fingers, label in GESTURE_FINGERS:
            self.swipe_combo.append(fingers, label)
        swipe_row.add_suffix(self.swipe_combo)
        gestures.add(swipe_row)

        # ── Cursor ────────────────────────────────────────────────────────
        cursor = Adw.PreferencesGroup(
            title=t("Cursor"),
            description=t("Stored as overrides in hypr-vars.lua and applied live."),
        )
        content.append(cursor)

        self.cursor_theme_row = Adw.EntryRow(title=t("Cursor theme"))
        self.cursor_theme_row.set_show_apply_button(True)
        cursor.add(self.cursor_theme_row)

        self.cursor_size_row = Adw.SpinRow.new_with_range(16, 96, 1)
        self.cursor_size_row.set_title(t("Cursor size"))
        cursor.add(self.cursor_size_row)

        # ── Region & language ─────────────────────────────────────────────
        region = Adw.PreferencesGroup(
            title=t("Region and language"),
            description=t("System-wide settings; changing them requires authentication."),
        )
        content.append(region)

        self.locale_row = Adw.ActionRow(title=t("System language"), subtitle=t("Requires password"))
        self.locale_combo = Gtk.ComboBoxText()
        self.locale_combo.set_valign(Gtk.Align.CENTER)
        for locale in _list_locales():
            self.locale_combo.append(locale, locale)
        self.locale_row.add_suffix(self.locale_combo)
        region.add(self.locale_row)

        self.timezone_row = Adw.ActionRow(title=t("Timezone"), subtitle=t("Requires password"))
        self.timezone_combo = Gtk.ComboBoxText()
        self.timezone_combo.set_valign(Gtk.Align.CENTER)
        for zone in _list_timezones():
            self.timezone_combo.append(zone, zone)
        self.timezone_row.add_suffix(self.timezone_combo)
        region.add(self.timezone_row)

        # Initial state
        self._load_all()
        self._loading = False

        self.layout_combo.connect("changed", self._on_layout_changed)
        self.extra_layout_row.connect("apply", self._on_layout_changed)
        self.variant_row.connect("apply", self._on_layout_changed)
        self.options_combo.connect("changed", self._on_layout_changed)
        self.numlock_row.connect("notify::active", self._on_switch_changed)
        self.repeat_rate_row.connect("notify::value", self._on_switch_changed)
        self.repeat_delay_row.connect("notify::value", self._on_switch_changed)
        self.natural_scroll_row.connect("notify::active", self._on_switch_changed)
        self.tap_click_row.connect("notify::active", self._on_switch_changed)
        self.disable_typing_row.connect("notify::active", self._on_switch_changed)
        self.scroll_factor_row.connect("notify::value", self._on_switch_changed)
        self.gesture_combo.connect("changed", self._on_gesture_changed)
        self.swipe_combo.connect("changed", self._on_gesture_changed)
        self.cursor_theme_row.connect("apply", self._on_cursor_changed)
        self.cursor_size_row.connect("notify::value", self._on_cursor_changed)
        self.locale_combo.connect("changed", self._on_locale_changed)
        self.timezone_combo.connect("changed", self._on_timezone_changed)

    # ── Loading ───────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        conf = read_input_conf()
        primary = conf["primary_layout"]
        if not self.layout_combo.set_active_id(primary):
            self.layout_combo.append(primary, _layout_label(primary))
            self.layout_combo.set_active_id(primary)
        self.extra_layout_row.set_text(conf["extra_layouts"])
        self.variant_row.set_text(conf["kb_variant"])
        if not self.options_combo.set_active_id(conf["kb_options"]):
            self.options_combo.append(conf["kb_options"], conf["kb_options"] or t("None"))
            self.options_combo.set_active_id(conf["kb_options"])
        self.numlock_row.set_active(conf["numlock_by_default"] == "true")
        self.repeat_rate_row.set_value(_as_int(conf["repeat_rate"], 40))
        self.repeat_delay_row.set_value(_as_int(conf["repeat_delay"], 250))
        self.natural_scroll_row.set_active(conf["natural_scroll"])
        self.tap_click_row.set_active(conf["tap_to_click"])
        self.disable_typing_row.set_active(conf["disable_while_typing"])
        self.scroll_factor_row.set_value(_as_float(conf["scroll_factor"], 0.3))

        variables = _read_vars()
        for combo, key in ((self.gesture_combo, "gestureFingers"), (self.swipe_combo, "workspaceSwipeFingers")):
            value = str(variables.get(key, "3"))
            if not combo.set_active_id(value):
                combo.set_active_id("3")
        self.cursor_theme_row.set_text(str(variables.get("cursorTheme", "sweet-cursors")))
        self.cursor_size_row.set_value(_as_int(str(variables.get("cursorSize", 24)), 24))

        self._load_locale()
        self._load_timezone()

    def _load_locale(self) -> None:
        try:
            result = subprocess.run(["localectl", "status"], capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                if "LANG=" in line:
                    locale = line.split("LANG=", 1)[1].strip()
                    if not self.locale_combo.set_active_id(locale):
                        self.locale_combo.append(locale, locale)
                        self.locale_combo.set_active_id(locale)
                    return
        except (OSError, subprocess.SubprocessError):
            pass

    def _load_timezone(self) -> None:
        try:
            result = subprocess.run(
                ["timedatectl", "show", "-p", "Timezone", "--value"],
                capture_output=True, text=True, timeout=3,
            )
            zone = result.stdout.strip()
            if zone:
                if not self.timezone_combo.set_active_id(zone):
                    self.timezone_combo.append(zone, zone)
                    self.timezone_combo.set_active_id(zone)
        except (OSError, subprocess.SubprocessError):
            pass

    # ── Saving ────────────────────────────────────────────────────────────

    def _values(self) -> dict:
        primary = self.layout_combo.get_active_id() or "us"
        extra = self.extra_layout_row.get_text().strip().replace(" ", "")
        layouts = ",".join(part for part in [primary, extra] if part)
        return {
            "kb_layout": layouts,
            "kb_variant": self.variant_row.get_text().strip().replace(" ", ""),
            "kb_options": self.options_combo.get_active_id() or "",
            "numlock_by_default": "true" if self.numlock_row.get_active() else "false",
            "repeat_rate": str(int(self.repeat_rate_row.get_value())),
            "repeat_delay": str(int(self.repeat_delay_row.get_value())),
            "repeat_rate_int": int(self.repeat_rate_row.get_value()),
            "repeat_delay_int": int(self.repeat_delay_row.get_value()),
            "natural_scroll": self.natural_scroll_row.get_active(),
            "tap_to_click": self.tap_click_row.get_active(),
            "disable_while_typing": self.disable_typing_row.get_active(),
            "scroll_factor": round(self.scroll_factor_row.get_value(), 2),
        }

    def _on_layout_changed(self, *_args) -> None:
        if self._loading:
            return
        self._save_input()

    def _on_switch_changed(self, *_args) -> None:
        if self._loading:
            return
        self._save_input()

    def _save_input(self) -> None:
        values = self._values()
        try:
            new_text = _write_input_block(values)
            before = hyprctl_config_errors()
            backup_path = backup.atomic_write_text(HYPR_USER_LUA, new_text)
            _apply_live_input(values)
            _ok, errors = reload_hyprland_checked()
            if errors and errors != before:
                if backup_path is not None:
                    backup.restore_backup(backup_path, HYPR_USER_LUA)
                reload_hyprland()
                raise apply.ApplyError(errors)
            self.show_toast(t("Keyboard and touchpad settings applied."))
        except apply.ApplyError as exc:
            self.show_toast(f"{t('Hyprland rejected the input settings and they were rolled back')}: {exc}")
        except backup.BackupError as exc:
            self.show_toast(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.show_toast(f"{t('Could not save input settings')}: {exc}")

    def _on_gesture_changed(self, *_args) -> None:
        if self._loading:
            return
        updates = {
            "gestureFingers": int(self.gesture_combo.get_active_id() or 3),
            "workspaceSwipeFingers": int(self.swipe_combo.get_active_id() or 3),
        }
        try:
            _write_vars(updates)
            self.show_toast(t("Gesture settings applied."))
        except Exception as exc:  # pragma: no cover
            self.show_toast(f"{t('Could not save gesture settings')}: {exc}")

    def _on_cursor_changed(self, *_args) -> None:
        if self._loading:
            return
        theme = self.cursor_theme_row.get_text().strip()
        size = int(self.cursor_size_row.get_value())
        try:
            _write_vars({"cursorTheme": theme, "cursorSize": size})
            subprocess.run(["hyprctl", "setcursor", theme, str(size)], capture_output=True, timeout=2, check=False)
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", theme],
                capture_output=True, timeout=2, check=False,
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", str(size)],
                capture_output=True, timeout=2, check=False,
            )
            self.show_toast(t("Cursor settings applied."))
        except Exception as exc:  # pragma: no cover
            self.show_toast(f"{t('Could not save cursor settings')}: {exc}")

    # ── Region ────────────────────────────────────────────────────────────

    def _on_locale_changed(self, combo) -> None:
        if self._loading:
            return
        locale = combo.get_active_id()
        if not locale:
            return
        try:
            subprocess.run(
                ["pkexec", "localectl", "set-locale", f"LANG={locale}"],
                check=True, timeout=30,
            )
            self.show_toast(t("Language set successfully (reboot needed)."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Language change cancelled."))
            self._load_locale()
        except (OSError, subprocess.SubprocessError) as exc:
            self.show_toast(f"{t('Could not change language')}: {exc}")
            self._load_locale()

    def _on_timezone_changed(self, combo) -> None:
        if self._loading:
            return
        zone = combo.get_active_id()
        if not zone:
            return
        try:
            subprocess.run(
                ["pkexec", "timedatectl", "set-timezone", zone],
                check=True, timeout=30,
            )
            self.show_toast(t("Timezone set successfully."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Timezone change cancelled."))
            self._load_timezone()
        except (OSError, subprocess.SubprocessError) as exc:
            self.show_toast(f"{t('Could not change timezone')}: {exc}")
            self._load_timezone()

    # ── Helpers ───────────────────────────────────────────────────────────

    def show_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        if hasattr(self.main_window, "add_toast"):
            self.main_window.add_toast(toast)


# Legacy helper kept for tests and external callers.
def _write_input_lua_key(key: str, value: str) -> None:
    values = read_input_conf()
    values.update({
        "kb_layout": values["kb_layout"],
        "kb_variant": values["kb_variant"],
        "kb_options": values["kb_options"],
        "numlock_by_default": values["numlock_by_default"],
        "repeat_rate": values["repeat_rate"],
        "repeat_delay": values["repeat_delay"],
        "repeat_rate_int": _as_int(values["repeat_rate"], 40),
        "repeat_delay_int": _as_int(values["repeat_delay"], 250),
        "natural_scroll": values["natural_scroll"],
        "tap_to_click": values["tap_to_click"],
        "disable_while_typing": values["disable_while_typing"],
        "scroll_factor": _as_float(values["scroll_factor"], 0.3),
    })
    if key == "kb_layout":
        values["kb_layout"] = value
    elif key == "numlock_by_default":
        values["numlock_by_default"] = "true" if str(value).lower() == "true" else "false"
    apply.write_and_reload(HYPR_USER_LUA, _write_input_block(values))


_write_input_conf_key = _write_input_lua_key
