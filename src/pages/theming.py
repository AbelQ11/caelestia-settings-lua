"""Theming: colour scheme, palette preview and GTK appearance."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from src.lang import t
from src.preview import read_scheme_colours

SCHEME_STATE = Path.home() / ".local" / "state" / "caelestia" / "scheme.json"

SCHEME_NAMES = [
    "dynamic", "caelestia", "catppuccin", "darkgreen", "dracula", "everblush",
    "everforest", "gruvbox", "nord", "oldworld", "onedark", "rosepine",
    "shadotheme", "solarized", "tokyonight",
]
SCHEME_VARIANTS = [
    "tonalspot", "vibrant", "expressive", "fidelity", "fruitsalad",
    "monochrome", "neutral", "rainbow", "content",
]
SCHEME_FLAVOURS = [
    "default", "main", "moon", "dawn", "latte", "frappe", "macchiato", "mocha",
    "hard", "medium", "soft",
]
PALETTE_KEYS = [
    "primary", "onPrimary", "secondary", "tertiary", "error",
    "background", "surface", "surfaceContainer", "surfaceContainerHigh",
    "onSurface", "onSurfaceVariant", "outline", "inversePrimary",
    "term0", "term1", "term2", "term3", "term4", "term5", "term6", "term7",
]
ICON_DIRS = [Path("/usr/share/icons"), Path.home() / ".icons", Path.home() / ".local/share/icons"]
THEME_DIRS = [Path("/usr/share/themes"), Path.home() / ".themes", Path.home() / ".local/share/themes"]


def _rgb_hex(value: str) -> tuple[float, float, float]:
    value = str(value or "808080").lstrip("#")
    if len(value) == 8:
        value = value[:6]
    try:
        return (
            int(value[0:2], 16) / 255,
            int(value[2:4], 16) / 255,
            int(value[4:6], 16) / 255,
        )
    except (ValueError, IndexError):
        return (0.5, 0.5, 0.5)


def _gsettings_get(key: str) -> str:
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", key],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _gsettings_set(key: str, value: str) -> bool:
    try:
        return subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", key, value],
            capture_output=True, timeout=3, check=False,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _list_names(directories: list[Path]) -> list[str]:
    names = set()
    for directory in directories:
        try:
            for entry in directory.iterdir():
                if entry.is_dir():
                    names.add(entry.name)
        except OSError:
            continue
    return sorted(names, key=str.lower)


class ColourSwatch(Gtk.Box):
    def __init__(self, name: str, value: str, on_copy):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_size_request(92, -1)
        self._value = value

        area = Gtk.DrawingArea()
        area.set_content_width(84)
        area.set_content_height(38)
        area.set_draw_func(self._draw, value)
        area.set_tooltip_text(f"{name}: #{value}")
        self.append(area)

        label = Gtk.Label(label=name)
        label.add_css_class("caption")
        label.set_ellipsize(3)
        self.append(label)

        click = Gtk.GestureClick()
        click.connect("released", lambda _g, _n, _x, _y: on_copy(value))
        area.add_controller(click)

    def _draw(self, _area, cr, width, height, value):
        red, green, blue = _rgb_hex(value)
        radius = 10
        cr.new_sub_path()
        cr.arc(width - radius, radius, radius, -3.14159 / 2, 0)
        cr.arc(width - radius, height - radius, radius, 0, 3.14159 / 2)
        cr.arc(radius, height - radius, radius, 3.14159 / 2, 3.14159)
        cr.arc(radius, radius, radius, 3.14159, 3 * 3.14159 / 2)
        cr.close_path()
        cr.set_source_rgb(red, green, blue)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.set_line_width(1)
        cr.stroke()


class ThemingPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.set_margin_top(12)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._build_scheme()
        self._build_palette()
        self._build_gtk()

    # ── Caelestia scheme ──────────────────────────────────────────────────

    def _scheme_state(self) -> dict:
        try:
            if SCHEME_STATE.exists():
                data = json.loads(SCHEME_STATE.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _build_scheme(self):
        state = self._scheme_state()
        group = Adw.PreferencesGroup(
            title=t("Caelestia colour scheme"),
            description=t("Applied with caelestia scheme set. Colours update immediately."),
        )
        self.content.append(group)

        name_row = Adw.ActionRow(title=t("Scheme"))
        self._name = Gtk.ComboBoxText()
        self._name.set_valign(Gtk.Align.CENTER)
        for name in SCHEME_NAMES:
            self._name.append(name, name)
        current = str(state.get("name", "dynamic"))
        if not self._name.set_active_id(current):
            self._name.append(current, current)
            self._name.set_active_id(current)
        name_row.add_suffix(self._name)
        group.add(name_row)

        flavour_row = Adw.ActionRow(title=t("Flavour"))
        self._flavour = Gtk.ComboBoxText()
        self._flavour.set_valign(Gtk.Align.CENTER)
        for flavour in SCHEME_FLAVOURS:
            self._flavour.append(flavour, flavour)
        current = str(state.get("flavour", "default"))
        if not self._flavour.set_active_id(current):
            self._flavour.append(current, current)
            self._flavour.set_active_id(current)
        flavour_row.add_suffix(self._flavour)
        group.add(flavour_row)

        variant_row = Adw.ActionRow(title=t("Variant"))
        self._variant = Gtk.ComboBoxText()
        self._variant.set_valign(Gtk.Align.CENTER)
        for variant in SCHEME_VARIANTS:
            self._variant.append(variant, variant)
        current = str(state.get("variant", "tonalspot"))
        if not self._variant.set_active_id(current):
            self._variant.append(current, current)
            self._variant.set_active_id(current)
        variant_row.add_suffix(self._variant)
        group.add(variant_row)

        mode_row = Adw.ActionRow(title=t("Mode"))
        self._mode = Gtk.ComboBoxText()
        self._mode.set_valign(Gtk.Align.CENTER)
        self._mode.append("dark", t("Dark"))
        self._mode.append("light", t("Light"))
        self._mode.set_active_id(str(state.get("mode", "dark")))
        mode_row.add_suffix(self._mode)
        group.add(mode_row)

        actions = Adw.ActionRow(title=t("Apply scheme"))
        random_btn = Gtk.Button(label=t("Random"))
        random_btn.set_valign(Gtk.Align.CENTER)
        random_btn.connect("clicked", self._on_random_scheme)
        actions.add_suffix(random_btn)
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self._on_apply_scheme)
        actions.add_suffix(apply_btn)
        group.add(actions)

    def _on_apply_scheme(self, _button):
        command = ["caelestia", "scheme", "set", "--notify"]
        if self._name.get_active_id():
            command += ["-n", self._name.get_active_id()]
        if self._flavour.get_active_id():
            command += ["-f", self._flavour.get_active_id()]
        if self._variant.get_active_id():
            command += ["-v", self._variant.get_active_id()]
        if self._mode.get_active_id():
            command += ["-m", self._mode.get_active_id()]
        try:
            subprocess.Popen(command)
            self.main_window.add_toast(Adw.Toast.new(t("Colour scheme applied.")))
            from gi.repository import GLib

            GLib.timeout_add(500, self._refresh_palette)
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not apply the scheme')}: {exc}")
            )

    def _on_random_scheme(self, _button):
        try:
            subprocess.Popen(["caelestia", "scheme", "set", "--notify", "-r"])
            self.main_window.add_toast(Adw.Toast.new(t("Random colour scheme applied.")))
            from gi.repository import GLib

            GLib.timeout_add(500, self._refresh_palette)
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not apply the scheme')}: {exc}")
            )

    # ── Palette ───────────────────────────────────────────────────────────

    def _build_palette(self):
        self._palette_group = Adw.PreferencesGroup(
            title=t("Palette"),
            description=t("Click a swatch to copy its hex value."),
        )
        self.content.append(self._palette_group)
        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_max_children_per_line(10)
        self._flow.set_min_children_per_line(4)
        self._flow.set_row_spacing(8)
        self._flow.set_column_spacing(8)
        row = Adw.PreferencesRow()
        row.set_child(self._flow)
        self._palette_group.add(row)
        self._refresh_palette()

    def _refresh_palette(self):
        while child := self._flow.get_first_child():
            self._flow.remove(child)
        colours = read_scheme_colours()
        for key in PALETTE_KEYS:
            value = colours.get(key)
            if value:
                self._flow.append(ColourSwatch(key, value, self._copy))
        return False

    def _copy(self, value: str):
        try:
            display = Gdk.Display.get_default()
            if display is not None:
                display.get_clipboard().set(f"#{value.lstrip('#')}")
                self.main_window.add_toast(Adw.Toast.new(f"#{value.lstrip('#')} {t('copied')}"))
        except Exception:  # noqa: BLE001 - clipboard backend may be unavailable
            pass

    # ── GTK appearance ────────────────────────────────────────────────────

    def _build_gtk(self):
        group = Adw.PreferencesGroup(
            title=t("GTK appearance"),
            description=t("Used by GTK applications. Applied with gsettings."),
        )
        self.content.append(group)

        theme_row = Adw.ActionRow(title=t("GTK theme"))
        self._gtk_theme = Gtk.ComboBoxText()
        self._gtk_theme.set_valign(Gtk.Align.CENTER)
        for name in _list_names(THEME_DIRS):
            self._gtk_theme.append(name, name)
        current = _gsettings_get("gtk-theme")
        if current:
            if not self._gtk_theme.set_active_id(current):
                self._gtk_theme.append(current, current)
                self._gtk_theme.set_active_id(current)
        theme_row.add_suffix(self._gtk_theme)
        group.add(theme_row)

        icon_row = Adw.ActionRow(title=t("Icon theme"))
        self._icon_theme = Gtk.ComboBoxText()
        self._icon_theme.set_valign(Gtk.Align.CENTER)
        for name in _list_names(ICON_DIRS):
            self._icon_theme.append(name, name)
        current = _gsettings_get("icon-theme")
        if current:
            if not self._icon_theme.set_active_id(current):
                self._icon_theme.append(current, current)
                self._icon_theme.set_active_id(current)
        icon_row.add_suffix(self._icon_theme)
        group.add(icon_row)

        scheme_row = Adw.ActionRow(title=t("GTK colour scheme"))
        self._gtk_scheme = Gtk.ComboBoxText()
        self._gtk_scheme.set_valign(Gtk.Align.CENTER)
        self._gtk_scheme.append("default", t("Default"))
        self._gtk_scheme.append("prefer-dark", t("Prefer dark"))
        self._gtk_scheme.append("prefer-light", t("Prefer light"))
        current = _gsettings_get("color-scheme") or "default"
        if not self._gtk_scheme.set_active_id(current):
            self._gtk_scheme.append(current, current)
            self._gtk_scheme.set_active_id(current)
        scheme_row.add_suffix(self._gtk_scheme)
        group.add(scheme_row)

        apply_row = Adw.ActionRow(title=t("Apply GTK settings"))
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self._on_apply_gtk)
        apply_row.add_suffix(apply_btn)
        group.add(apply_row)

    def _on_apply_gtk(self, _button):
        ok = True
        values = [
            ("gtk-theme", self._gtk_theme.get_active_id()),
            ("icon-theme", self._icon_theme.get_active_id()),
            ("color-scheme", self._gtk_scheme.get_active_id()),
        ]
        for key, value in values:
            if value:
                ok = _gsettings_set(key, value) and ok
        self.main_window.add_toast(
            Adw.Toast.new(t("GTK appearance applied.") if ok else t("Some GTK settings could not be applied."))
        )
