"""Visual preview for Caelestia shell changes.

Renders a mock desktop from the *staged* shell values: bar entries, workspaces,
clock, desktop clock, audio visualiser, rounding/spacing/transparency and the
current colour scheme.  Used by the Caelestia page before applying changes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.lang import t

SCHEME_STATE = Path.home() / ".local" / "state" / "caelestia" / "scheme.json"

_W, _H = 960, 540


def read_scheme_colours() -> dict[str, str]:
    try:
        data = json.loads(SCHEME_STATE.read_text(encoding="utf-8"))
        colours = data.get("colours")
        if isinstance(colours, dict):
            return {key: str(value) for key, value in colours.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "background": "131411",
        "surface": "1f201d",
        "surfaceContainer": "292a27",
        "primary": "b7cea2",
        "onSurface": "e4e2dd",
        "onSurfaceVariant": "c5c8bc",
        "outline": "8e9287",
        "secondary": "c1cab5",
    }


def _rgb(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    value = (value or "").strip().lstrip("#")
    if len(value) == 8:
        value = value[:6]
    try:
        return (
            int(value[0:2], 16) / 255,
            int(value[2:4], 16) / 255,
            int(value[4:6], 16) / 255,
            alpha,
        )
    except (ValueError, IndexError):
        return (0.5, 0.5, 0.5, alpha)


def _rounded(cr: cairo.Context, x, y, w, h, radius):
    radius = max(0, min(radius, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + w - radius, y + h - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + h - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()


@dataclass
class PreviewModel:
    values: dict = field(default_factory=dict)
    colours: dict = field(default_factory=read_scheme_colours)

    def get(self, path: str, default=None):
        return self.values.get(path, default)


class DesktopPreview(Gtk.DrawingArea):
    def __init__(self, model: PreviewModel):
        super().__init__()
        self.model = model
        self.set_content_height(300)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_model(self, model: PreviewModel):
        self.model = model
        self.queue_draw()

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw(self, _area, cr: cairo.Context, width: int, height: int):
        model = self.model
        colours = model.colours
        cr.save()
        cr.scale(width / _W, height / _H)

        # Background
        gradient = cairo.LinearGradient(0, 0, _W, _H)
        gradient.add_color_stop_rgb(0, *_rgb(colours.get("background", "131411"))[:3])
        gradient.add_color_stop_rgb(1, *_rgb(colours.get("surfaceContainer", "292a27"))[:3])
        cr.set_source(gradient)
        cr.rectangle(0, 0, _W, _H)
        cr.fill()

        self._draw_visualiser(cr, model, colours)
        self._draw_desktop_clock(cr, model, colours)
        self._draw_window(cr, model, colours)
        self._draw_bar(cr, model, colours)
        cr.restore()

    def _alpha(self, model: PreviewModel, base: float = 1.0) -> float:
        transparency = model.get("appearance.transparency.enabled", False)
        if not transparency:
            return base
        return max(0.25, min(base, float(model.get("appearance.transparency.base", 0.85))))

    def _draw_visualiser(self, cr, model, colours):
        if not model.get("background.visualiser.enabled", False):
            return
        bars = max(1, min(int(model.get("services.visualiserBars", 60)), 80))
        spacing = max(0.0, float(model.get("background.visualiser.spacing", 1)))
        rounding = float(model.get("background.visualiser.rounding", 1))
        total_width = 720
        bar_width = max(2.0, (total_width - spacing * (bars - 1)) / bars)
        x0 = (_W - total_width) / 2
        base_y = _H - 36
        cr.set_source_rgba(*_rgb(colours.get("primary", "b7cea2"), 0.55))
        for index in range(bars):
            height = 18 + abs(math.sin(index * 0.55)) * 70 + abs(math.sin(index * 0.17)) * 22
            x = x0 + index * (bar_width + spacing)
            y = base_y - height
            radius = min(rounding * 2, bar_width / 2)
            _rounded(cr, x, y, bar_width, height, radius)
            cr.fill()

    def _draw_desktop_clock(self, cr, model, colours):
        if not model.get("background.desktopClock.enabled", False):
            return
        position = str(model.get("background.desktopClock.position", "bottom-right"))
        scale = float(model.get("background.desktopClock.scale", 1))
        font = str(model.get("appearance.font.clock", "Sans")) or "Sans"
        size = 34 * max(0.5, scale)
        cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(size)
        text = "12:34"
        ext = cr.text_extents(text)
        pad = 28
        if position.endswith("left"):
            x = pad
        else:
            x = _W - pad - ext.width
        if position.startswith("top"):
            y = pad + ext.height
        else:
            y = _H - pad - ext.height

        bg = model.get("background.desktopClock.background.enabled", False)
        if bg:
            opacity = float(model.get("background.desktopClock.background.opacity", 0.7))
            margin = 16
            _rounded(
                cr,
                x - margin,
                y - ext.height - margin + 6,
                ext.width + margin * 2,
                ext.height + margin * 2,
                18 * scale,
            )
            cr.set_source_rgba(*_rgb(colours.get("surfaceContainer", "292a27"), opacity))
            cr.fill()

        if model.get("background.desktopClock.shadow.enabled", True):
            opacity = float(model.get("background.desktopClock.shadow.opacity", 0.7))
            for offset in (6, 4, 2):
                cr.set_source_rgba(0, 0, 0, opacity / (offset + 2))
                cr.move_to(x + offset, y + offset)
                cr.show_text(text)

        if model.get("background.desktopClock.invertColors", False):
            colour = colours.get("background", "131411")
        else:
            colour = colours.get("onSurface", "e4e2dd")
        cr.set_source_rgb(*_rgb(colour)[:3])
        cr.move_to(x, y)
        cr.show_text(text)

    def _draw_window(self, cr, model, colours):
        rounding = 18 * float(model.get("appearance.rounding.scale", 1))
        border = max(1, int(model.get("border.thickness", 2)))
        x, y, w, h = 260, 120, 440, 250
        _rounded(cr, x, y, w, h, rounding)

        alpha = self._alpha(model, 1.0)
        cr.set_source_rgba(*_rgb(colours.get("surfaceContainer", "292a27"), alpha))
        cr.fill_preserve()
        cr.set_line_width(border)
        cr.set_source_rgba(*_rgb(colours.get("primary", "b7cea2"), 0.9))
        cr.stroke()

        # Fake window content
        cr.set_source_rgba(*_rgb(colours.get("onSurface", "e4e2dd"), 0.85))
        cr.select_font_face(
            str(model.get("appearance.font.body.medium.family", "Sans")) or "Sans",
            cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD,
        )
        cr.set_font_size(16)
        cr.move_to(x + 20, y + 34)
        cr.show_text("Caelestia Settings")

        cr.set_source_rgba(*_rgb(colours.get("onSurfaceVariant", "c5c8bc"), 0.5))
        for index in range(4):
            bar_y = y + 62 + index * 26
            _rounded(cr, x + 20, bar_y, w * (0.72 - index * 0.08), 8, 4)
            cr.fill()

    def _draw_bar(self, cr, model, colours):
        if not model.get("bar.persistent", True) and not model.get("bar.showOnHover", True):
            return
        margin = 14
        height = 38
        rounding = max(6, 18 * float(model.get("appearance.rounding.scale", 1)))
        _rounded(cr, margin, margin, _W - margin * 2, height, rounding)
        alpha = self._alpha(model, 0.96) if model.get("bar.persistent", True) else 0.5
        cr.set_source_rgba(*_rgb(colours.get("surfaceContainer", "292a27"), alpha))
        cr.fill()
        cr.set_line_width(1)
        cr.set_source_rgba(*_rgb(colours.get("outline", "8e9287"), 0.35))
        cr.stroke()

        entries = model.get("bar.entries", [])
        if not isinstance(entries, list) or not entries:
            entries = [
                {"id": "logo", "enabled": True},
                {"id": "workspaces", "enabled": True},
                {"id": "spacer", "enabled": True},
                {"id": "activeWindow", "enabled": True},
                {"id": "clock", "enabled": True},
                {"id": "statusIcons", "enabled": True},
            ]

        x = margin + 14
        y = margin + height / 2
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("enabled", True):
                continue
            item = entry.get("id", "")
            if item == "spacer":
                x += 26
            elif item == "logo":
                cr.set_source_rgba(*_rgb(colours.get("primary", "b7cea2"), 0.9))
                cr.arc(x + 10, y, 9, 0, 2 * math.pi)
                cr.fill()
                x += 32
            elif item == "workspaces":
                x = self._draw_workspaces(cr, model, colours, x, y)
            elif item == "activeWindow":
                _rounded(cr, x, y - 10, 150, 20, 7)
                cr.set_source_rgba(*_rgb(colours.get("surface", "1f201d"), 0.7))
                cr.fill()
                cr.set_source_rgba(*_rgb(colours.get("onSurface", "e4e2dd"), 0.8))
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(11)
                cr.move_to(x + 10, y + 4)
                cr.show_text("Browser")
                x += 162
            elif item == "tray":
                for offset in range(3):
                    cr.set_source_rgba(*_rgb(colours.get("onSurfaceVariant", "c5c8bc"), 0.8))
                    cr.arc(x + offset * 14, y, 4, 0, 2 * math.pi)
                    cr.fill()
                x += 46
            elif item == "clock":
                x = self._draw_bar_clock(cr, model, colours, x, y)
            elif item == "statusIcons":
                x = self._draw_status_icons(cr, model, colours, x, y)
            elif item == "power":
                cr.set_source_rgba(*_rgb(colours.get("primary", "b7cea2"), 0.9))
                cr.arc(x + 9, y, 8, 0, 2 * math.pi)
                cr.fill()
                x += 30
            else:
                x += 10

    def _draw_workspaces(self, cr, model, colours, x, y):
        shown = max(1, min(int(model.get("bar.workspaces.shown", 5)), 10))
        display = str(model.get("bar.workspaces.displayType", "shapes"))
        active = int(model.get("bar.workspaces.activeIndicator", True))
        for index in range(shown):
            is_active = index == active
            if display == "text":
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(12)
                cr.set_source_rgba(
                    *_rgb(
                        colours.get("onSurface" if is_active else "onSurfaceVariant", "e4e2dd"),
                        0.95 if is_active else 0.55,
                    )
                )
                cr.move_to(x, y + 4)
                cr.show_text(str(index + 1))
                x += 18
            else:
                width = 18 if display == "icons" else 14
                _rounded(cr, x, y - 4, width, 8, 4)
                if is_active:
                    cr.set_source_rgba(*_rgb(colours.get("primary", "b7cea2"), 0.95))
                else:
                    cr.set_source_rgba(*_rgb(colours.get("onSurfaceVariant", "c5c8bc"), 0.45))
                cr.fill()
                x += width + 6
        return x + 12

    def _draw_bar_clock(self, cr, model, colours, x, y):
        family = str(model.get("appearance.font.clock", "Sans")) or "Sans"
        cr.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.set_source_rgba(*_rgb(colours.get("onSurface", "e4e2dd"), 0.95))
        text = "12:34"
        if model.get("bar.clock.showDate", False):
            text += "  31 Oct"
        cr.move_to(x, y + 4)
        cr.show_text(text)
        ext = cr.text_extents(text)
        return x + ext.width + 20

    def _draw_status_icons(self, cr, model, colours, x, y):
        icons = model.get("bar.statusIcons", [])
        enabled = [
            icon.get("id", "")
            for icon in icons
            if isinstance(icon, dict) and icon.get("enabled", False)
        ] if isinstance(icons, list) else []
        for icon in enabled[:6]:
            cr.set_source_rgba(*_rgb(colours.get("onSurfaceVariant", "c5c8bc"), 0.85))
            cr.arc(x + 6, y, 5, 0, 2 * math.pi)
            cr.fill()
            x += 16
        return x + 10


def build_preview_box(model: PreviewModel, diff_text: str | None = None) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_size_request(760, -1)
    preview = DesktopPreview(model)
    preview.set_size_request(760, 300)
    box.append(preview)

    hint = Gtk.Label(label=t("Preview uses the staged values above. Nothing is applied yet."))
    hint.add_css_class("caption")
    hint.add_css_class("dim-label")
    hint.set_halign(Gtk.Align.START)
    box.append(hint)

    if diff_text is not None:
        buffer = Gtk.TextBuffer()
        buffer.set_text(diff_text)
        view = Gtk.TextView(buffer=buffer)
        view.set_editable(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(220)
        scroller.set_child(view)
        box.append(scroller)
    return box


def show_preview(parent, model: PreviewModel):
    dialog = Adw.MessageDialog(
        transient_for=parent,
        heading=t("Preview"),
        body=t("Visual preview of the staged Caelestia appearance."),
    )
    dialog.set_extra_child(build_preview_box(model))
    dialog.add_response("close", t("Close"))
    dialog.present()
