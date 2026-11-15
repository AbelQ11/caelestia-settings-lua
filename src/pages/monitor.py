import json
import subprocess
from pathlib import Path

import cairo

from src import apply, backup, kanshi, lua, shell_config
from src.config import (
    HYPR_EXECS_LUA,
    HYPR_HYPRLAND_DIR,
    HYPR_MONITORS_LUA,
    read_text,
    hyprctl_config_errors,
    reload_hyprland,
    reload_hyprland_checked,
    restart_caelestia,
    write_text,
)
from src.lang import t
from gi.repository import Gtk, Adw, GLib

# ── Constants ─────────────────────────────────────────────────────────────────

ROTATION_OPTIONS = [
    ("0",   t("Normal (0°)")),
    ("1",   t("90° right")),
    ("2",   "180°"),
    ("3",   t("270° right / 90° left")),
]

BITDEPTH_OPTIONS = [
    ("",   t("Standard (8 bit)")),
    ("8",  "8 bit"),
    ("10", t("10 bit (HDR)")),
]

COLOUR_MANAGEMENT_OPTIONS = [
    ("", "Automatic"),
    ("srgb", "sRGB"),
    ("wide", "Wide colour gamut"),
    ("edid", "EDID"),
    ("hdr", "HDR"),
    ("dcip3", "DCI-P3"),
]

# Colours for monitor rectangles (index → RGBA)
MONITOR_COLORS = [
    (0.27, 0.52, 0.93, 1.0),   # Blue
    (0.20, 0.78, 0.56, 1.0),   # Green
    (0.93, 0.47, 0.27, 1.0),   # Orange
    (0.73, 0.40, 0.93, 1.0),   # Purple
    (0.93, 0.27, 0.47, 1.0),   # Red
]

CANVAS_H = 220   # Preview canvas height in pixels

# Scales that commonly keep an integer logical resolution.  Hyprland rounds
# unsupported fractional scales, so the UI only offers valid values.
COMMON_SCALES = [0.5, 0.75, 1.0, 1.1, 1.2, 1.25, 1.333, 1.4, 1.5, 1.6,
                 1.666, 1.75, 1.8, 2.0, 2.25, 2.5, 3.0, 4.0]


def valid_scales(width: int, height: int) -> list[float]:
    result = []
    for scale in COMMON_SCALES:
        logical_w = width / scale
        logical_h = height / scale
        if abs(logical_w - round(logical_w)) < 1e-6 and abs(logical_h - round(logical_h)) < 1e-6:
            result.append(round(scale, 3))
    return sorted(set(result))


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _monitor_file() -> Path:
    for candidate in (HYPR_MONITORS_LUA, HYPR_HYPRLAND_DIR / "monitors.lua"):
        if candidate.exists():
            return candidate
    return HYPR_MONITORS_LUA


def _parse_monitor_blocks() -> list[dict]:
    """All ``hl.monitor`` tables in the active monitor file."""

    target = _monitor_file()
    text = read_text(target)
    blocks: list[dict] = []
    if not text:
        return blocks
    for call in lua.iter_calls(text, {"hl.monitor"}):
        if isinstance(call.table, dict):
            blocks.append(call.table)
    return blocks


def _matches_live(block: dict, live: dict) -> bool:
    output = str(block.get("output", "")).strip()
    name = str(live.get("name", ""))
    if output == name:
        return True
    if output.startswith("desc:"):
        wanted = output[len("desc:"):].strip().lower()
        return wanted == str(live.get("description", "")).strip().lower()
    return False


def _get_live_monitors() -> list[dict]:
    """Current monitors from hyprctl, enriched with fields from monitors.lua."""

    try:
        res = subprocess.run(
            ["hyprctl", "monitors", "all", "-j"],
            capture_output=True, text=True, check=True, timeout=3,
        )
        monitors = json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"hyprctl error: {exc}")
        return []

    for monitor in monitors:
        monitor.setdefault("description", "")
        for block in _parse_monitor_blocks():
            if not _matches_live(block, monitor):
                continue
            monitor["_file_output"] = block.get("output", monitor.get("name", ""))
            monitor["_file_fields"] = block
            monitor["bitdepth"] = str(block.get("bitdepth", ""))
            monitor["cm"] = str(block.get("cm", ""))
            monitor["mirror"] = str(block.get("mirror", ""))
            monitor["icc"] = str(block.get("icc", ""))
            monitor["sdrbrightness"] = block.get("sdrbrightness", 1)
            monitor["sdrsaturation"] = block.get("sdrsaturation", 1)
            monitor["sdr_min_luminance"] = block.get("sdr_min_luminance", 0.2)
            monitor["sdr_max_luminance"] = block.get("sdr_max_luminance", 80)
            monitor["min_luminance"] = block.get("min_luminance", 0)
            monitor["max_luminance"] = block.get("max_luminance", 0)
            monitor["max_avg_luminance"] = block.get("max_avg_luminance", 0)
            if "vrr" in block:
                monitor["vrr"] = block["vrr"]
            break
    return monitors


def _parse_conf_extras() -> dict:
    """Compatibility helper: map file output names to their extras."""

    result = {}
    for block in _parse_monitor_blocks():
        output = block.get("output")
        if output:
            result[output] = {
                "bitdepth": str(block.get("bitdepth", "")),
                "cm": str(block.get("cm", "")),
                "mirror": str(block.get("mirror", "")),
                "vrr": block.get("vrr"),
            }
    return result


_parse_lua_extras = _parse_conf_extras


def _apply_to_hyprland(monitors: list[dict]):
    """Apply monitor changes by reloading Hyprland after the file is written."""

    for monitor in monitors:
        try:
            subprocess.run(
                ["hyprctl", "keyword", "monitor", _build_monitor_keyword(monitor)],
                capture_output=True, timeout=3, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"hyprctl monitor error: {exc}")


def _build_monitor_lua(m) -> str:
    output = getattr(m, "file_output", "") or m.name
    fields: dict = {"output": output}

    if getattr(m, "disabled", False):
        fields["disabled"] = True
    else:
        res_hz = f"{m.resolution}@{m.hz}" if getattr(m, "hz", None) else m.resolution
        fields["mode"] = res_hz
        fields["position"] = f"{int(m.x)}x{int(m.y)}"
        try:
            fields["scale"] = float(m.scale)
        except (TypeError, ValueError):
            fields["scale"] = m.scale
        if getattr(m, "bitdepth", ""):
            bitdepth = str(m.bitdepth)
            fields["bitdepth"] = int(bitdepth) if bitdepth.isdigit() else bitdepth
        if getattr(m, "transform", "") not in ("", "0", 0):
            fields["transform"] = int(m.transform)
        if getattr(m, "cm", ""):
            fields["cm"] = m.cm
        if getattr(m, "vrr", None) not in (None, False):
            fields["vrr"] = m.vrr
        if getattr(m, "mirror", ""):
            fields["mirror"] = m.mirror
        if getattr(m, "icc", ""):
            fields["icc"] = m.icc
        for key, default in (
            ("sdrbrightness", 1),
            ("sdrsaturation", 1),
            ("sdr_min_luminance", 0.2),
            ("sdr_max_luminance", 80),
            ("min_luminance", 0),
            ("max_luminance", 0),
            ("max_avg_luminance", 0),
        ):
            value = getattr(m, key, default)
            try:
                if float(value) != float(default):
                    fields[key] = value
            except (TypeError, ValueError):
                pass

    # Preserve every field the UI does not edit (reserved, eotf, ...).
    if not getattr(m, "disabled", False):
        for key, value in getattr(m, "extra_fields", {}).items():
            fields.setdefault(key, value)

    return f"hl.monitor({lua.format_value(fields)})"


def _save_monitors_conf(monitors: list):
    """Rewrite only the ``hl.monitor`` tables, preserving everything else."""

    target = _monitor_file()
    text = read_text(target)
    calls = lua.iter_calls(text, {"hl.monitor"}) if text else []

    replacements: list[tuple[int, int, str]] = []
    used_calls: set[int] = set()
    matched: set[int] = set()
    for monitor in monitors:
        match_index = None
        for index, call in enumerate(calls):
            if index in used_calls or not isinstance(call.table, dict):
                continue
            block = call.table
            output = str(block.get("output", ""))
            if output and (
                output == getattr(monitor, "file_output", "")
                or output == monitor.name
                or (output.startswith("desc:") and output[5:].strip().lower() == monitor.description.strip().lower())
            ):
                match_index = index
                break
        new_block = _build_monitor_lua(monitor)
        if match_index is not None:
            used_calls.add(match_index)
            matched.add(id(monitor))
            call = calls[match_index]
            replacements.append((call.start, call.end, new_block))

    new_text = text
    for start, end, rendered in sorted(replacements, key=lambda item: item[0], reverse=True):
        new_text = new_text[:start] + rendered + new_text[end:]

    missing = [m for m in monitors if id(m) not in matched]
    if missing:
        appended = "\n\n".join(_build_monitor_lua(m) for m in missing)
        new_text = new_text.rstrip() + "\n\n" + appended + "\n"

    if not new_text.strip():
        new_text = "\n\n".join(_build_monitor_lua(m) for m in monitors) + "\n"

    return backup.atomic_write_text(target, new_text)


_save_monitors_lua = _save_monitors_conf


# ── execs.lua Helpers ────────────────────────────────────────────────────────

def _get_primary_monitor() -> str:
    """Read the current primary monitor from ``execs.lua``."""

    execs = HYPR_EXECS_LUA
    if not execs.exists():
        return ""
    for line in read_text(execs).splitlines():
        line = line.strip()
        if "xrandr" in line and "--primary" in line and "--output" in line:
            parts = line.split()
            try:
                idx = parts.index("--output")
                return parts[idx + 1].strip('"\'')
            except (ValueError, IndexError):
                pass
    return ""


def _set_primary_monitor(name: str):
    """Write the ``xrandr --primary`` line in ``execs.lua`` (with backup)."""

    execs = HYPR_EXECS_LUA
    execs.parent.mkdir(parents=True, exist_ok=True)
    new_line = f'    hl.exec_cmd("xrandr --output {name} --primary")'

    if execs.exists():
        lines = read_text(execs).splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if "xrandr" in line and "--primary" in line and "--output" in line:
                lines[i] = new_line
                replaced = True
                break
        if not replaced:
            inserted = False
            for i, line in enumerate(lines):
                if 'hl.on("hyprland.start"' in line:
                    lines.insert(i + 1, new_line)
                    inserted = True
                    break
            if not inserted:
                lines.append(new_line)
        write_text(execs, "\n".join(lines) + "\n")
    else:
        write_text(execs, f'hl.on("hyprland.start", function()\n{new_line}\nend)\n')

    try:
        subprocess.run(
            ["xrandr", "--output", name, "--primary"],
            timeout=3, capture_output=True, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"xrandr error: {exc}")


# ── shell.json Helpers ───────────────────────────────────────────────────────

def _get_bar_persistent(monitor_name: str) -> bool:
    """Whether the bar stays visible on this monitor (per-monitor override)."""

    value = shell_config.read_monitor(monitor_name).get("bar", {}).get("persistent")
    if value is None:
        return bool(shell_config.get("bar.persistent", True))
    return bool(value)


def _set_bar_persistent(monitor_name: str, persistent: bool, *, restart: bool = True):
    """Write ``bar.persistent`` to the monitor's shell.json override."""

    try:
        shell_config.set_monitor_value(
            monitor_name, "bar.persistent", persistent, restart=restart
        )
    except backup.BackupError as exc:
        print(f"Could not back up shell.json: {exc}")
        raise
    except Exception as exc:  # pragma: no cover - defensive UI path
        print(f"Could not write shell.json: {exc}")


def _build_monitor_keyword(m) -> str:
    """
    Baut den Hyprland monitor-Keyword-String aus einem MonitorModel.
    DP-1,2560x1440@179.95,0x0,1,bitdepth,10,transform,3
    """
    if m.disabled:
        return f"{m.name},disable"

    res_hz = f"{m.resolution}@{m.hz}" if m.hz else m.resolution
    pos    = f"{int(m.x)}x{int(m.y)}"
    parts  = [m.name, res_hz, pos, str(m.scale)]

    if m.bitdepth:
        parts += ["bitdepth", m.bitdepth]

    if m.transform and m.transform != "0":
        parts += ["transform", m.transform]

    return ",".join(parts)


def _parse_mode(mode_str: str) -> tuple[str, str]:
    """'2560x1440@179.950Hz' → ('2560x1440', '179.950')"""
    if "@" in mode_str:
        res, hz = mode_str.split("@", 1)
        hz = hz.replace("Hz", "").strip()
        try:
            hz = f"{float(hz):.3f}"   # normalisieren auf 3 Dezimalstellen
        except ValueError:
            pass
        return res, hz
    return mode_str, ""


# ── Monitor-Datenmodell ───────────────────────────────────────────────────────

class MonitorModel:
    """Editable monitor state."""

    def __init__(self, data: dict):
        self.name        = data["name"]
        self.description = data.get("description", self.name)
        self.x           = float(data.get("x", 0))
        self.y           = float(data.get("y", 0))
        self.width       = int(data.get("width", 1920))
        self.height      = int(data.get("height", 1080))
        self.scale       = float(data.get("scale", 1.0))
        self.transform   = str(int(data.get("transform", 0)))
        self.disabled    = data.get("disabled", False)

        # Active resolution + refresh rate
        self.resolution  = f"{self.width}x{self.height}"
        self.hz          = f"{round(data.get('refreshRate', 60), 3):.3f}"

        # Fields preserved from monitors.lua
        self.bitdepth = str(data.get("bitdepth", ""))
        self.cm = str(data.get("cm", ""))
        self.vrr = data.get("vrr")
        self.mirror = str(data.get("mirror", ""))
        self.icc = str(data.get("icc", ""))
        self.sdrbrightness = data.get("sdrbrightness", 1)
        self.sdrsaturation = data.get("sdrsaturation", 1)
        self.sdr_min_luminance = data.get("sdr_min_luminance", 0.2)
        self.sdr_max_luminance = data.get("sdr_max_luminance", 80)
        self.min_luminance = data.get("min_luminance", 0)
        self.max_luminance = data.get("max_luminance", 0)
        self.max_avg_luminance = data.get("max_avg_luminance", 0)
        self.file_output = str(data.get("_file_output", self.name))
        self.extra_fields = dict(data.get("_file_fields") or {})

        # Set separately by the page
        self.primary = False
        self.bar_persistent = True

        # All available modes
        self.available_modes: list[str] = data.get("availableModes", [])
        if not self.available_modes:
            self.available_modes = [f"{self.resolution}@{self.hz}Hz"]

        # Deduplicated resolutions + refresh rates per resolution
        self._res_map: dict[str, list[str]] = {}
        for mode in self.available_modes:
            r, h = _parse_mode(mode)
            self._res_map.setdefault(r, []).append(h)

    @property
    def logical_w(self) -> float:
        """Logical width; hyprctl already swaps width/height on rotated outputs."""
        return self.width / self.scale

    @property
    def logical_h(self) -> float:
        return self.height / self.scale

    def resolutions(self) -> list[str]:
        return sorted(self._res_map.keys(),
                      key=lambda r: int(r.split("x")[0]), reverse=True)

    def hz_for_resolution(self, res: str) -> list[str]:
        return sorted(self._res_map.get(res, []),
                      key=lambda h: float(h) if h else 0, reverse=True)

    def to_save_dict(self) -> dict:
        return {
            "name":       self.name,
            "resolution": self.resolution,
            "hz":         self.hz,
            "x":          self.x,
            "y":          self.y,
            "scale":      self.scale,
            "transform":  self.transform,
            "bitdepth":   self.bitdepth,
        }


# ── Canvas ────────────────────────────────────────────────────────────────────

class MonitorCanvas(Gtk.DrawingArea):
    """
    Zeichnet alle Monitore als Rechtecke.
    Click → select a monitor.
    Drag → move a monitor (snaps to neighbours).
    """

    def __init__(self, on_select_cb):
        super().__init__()
        self.on_select_cb = on_select_cb
        self.monitors: list[MonitorModel] = []
        self.selected: MonitorModel | None = None
        self._drag_mon: MonitorModel | None = None
        self._drag_off_x = 0.0
        self._drag_off_y = 0.0

        self.set_vexpand(False)
        self.set_hexpand(True)
        self.set_content_height(CANVAS_H)
        self.set_draw_func(self._draw)

        # Gestures
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_press)
        self.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin",  self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end",    self._on_drag_end)
        self.add_controller(drag)

    # ── Koordinaten-Umrechnung ────────────────────────────────────────────

    def _canvas_rect(self, m: MonitorModel, scale: float, ox: float, oy: float):
        """Return (cx, cy, cw, ch) in canvas pixels."""
        cw = max(m.logical_w * scale, 40)
        ch = max(m.logical_h * scale, 30)
        cx = ox + m.x * scale
        cy = oy + m.y * scale
        return cx, cy, cw, ch

    def _view_scale_offset(self) -> tuple[float, float, float]:
        """Scale factor and offset so that every monitor fits."""
        if not self.monitors:
            return 0.1, 20, 20

        active = [m for m in self.monitors if not m.disabled]
        if not active:
            return 0.1, 20, 20

        min_x = min(m.x for m in active)
        min_y = min(m.y for m in active)
        max_x = max(m.x + m.logical_w for m in active)
        max_y = max(m.y + m.logical_h for m in active)

        w = self.get_width()
        h = self.get_height()
        pad = 32

        sw = (w - 2 * pad) / max(max_x - min_x, 1)
        sh = (h - 2 * pad) / max(max_y - min_y, 1)
        s  = min(sw, sh, 0.18)   # max 0.18 px/logical-px

        ox = pad - min_x * s + (w - 2*pad - (max_x-min_x)*s) / 2
        oy = pad - min_y * s + (h - 2*pad - (max_y-min_y)*s) / 2
        return s, ox, oy

    # ── Zeichnen ──────────────────────────────────────────────────────────

    def _draw(self, area, cr, w, h):
        s, ox, oy = self._view_scale_offset()

        # Background
        cr.set_source_rgba(0.12, 0.12, 0.12, 1)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Grid
        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.set_line_width(1)
        step = 40
        for gx in range(0, w, step):
            cr.move_to(gx, 0); cr.line_to(gx, h)
        for gy in range(0, h, step):
            cr.move_to(0, gy); cr.line_to(w, gy)
        cr.stroke()

        for i, m in enumerate(self.monitors):
            if m.disabled:
                continue
            cx, cy, cw, ch = self._canvas_rect(m, s, ox, oy)
            r, g, b, a = MONITOR_COLORS[i % len(MONITOR_COLORS)]
            selected = (m is self.selected)

            # Shadow
            cr.set_source_rgba(0, 0, 0, 0.4)
            cr.rectangle(cx + 4, cy + 4, cw, ch)
            cr.fill()

            # Fill
            alpha = 1.0 if selected else 0.75
            cr.set_source_rgba(r * 0.6, g * 0.6, b * 0.6, alpha)
            cr.rectangle(cx, cy, cw, ch)
            cr.fill()

            # Border
            lw = 3 if selected else 1.5
            cr.set_line_width(lw)
            cr.set_source_rgba(r, g, b, 1.0)
            cr.rectangle(cx, cy, cw, ch)
            cr.stroke()

            # Name
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD if selected else cairo.FONT_WEIGHT_NORMAL)
            font_size = max(min(cw / 6, 16), 9)
            cr.set_font_size(font_size)
            ext = cr.text_extents(m.name)
            cr.move_to(cx + cw/2 - ext.width/2, cy + ch/2 - 2)
            cr.show_text(m.name)

            # Resolution
            res_str = f"{m.resolution}@{float(m.hz):.0f}Hz"
            cr.set_font_size(max(font_size * 0.7, 7))
            cr.set_source_rgba(1, 1, 1, 0.7)
            ext2 = cr.text_extents(res_str)
            if ext2.width < cw - 8:
                cr.move_to(cx + cw/2 - ext2.width/2, cy + ch/2 + font_size)
                cr.show_text(res_str)

            # Redation indicator
            if m.transform != "0":
                deg = {"1": "90°", "2": "180°", "3": "270°"}.get(m.transform, "")
                cr.set_font_size(max(font_size * 0.65, 7))
                cr.set_source_rgba(1, 1, 0.4, 0.9)
                cr.move_to(cx + 4, cy + 14)
                cr.show_text(f"↻ {deg}")

    # ── Interaktion ───────────────────────────────────────────────────────

    def _mon_at(self, px, py) -> MonitorModel | None:
        s, ox, oy = self._view_scale_offset()
        for m in reversed(self.monitors):
            if m.disabled: continue
            cx, cy, cw, ch = self._canvas_rect(m, s, ox, oy)
            if cx <= px <= cx+cw and cy <= py <= cy+ch:
                return m
        return None

    def _on_press(self, gesture, n, px, py):
        m = self._mon_at(px, py)
        self.selected = m
        self.queue_draw()
        self.on_select_cb(m)

    def _on_drag_begin(self, gesture, sx, sy):
        self._drag_mon = self._mon_at(sx, sy)
        if self._drag_mon:
            s, ox, oy = self._view_scale_offset()
            self._drag_off_x = (sx - ox) / s - self._drag_mon.x
            self._drag_off_y = (sy - oy) / s - self._drag_mon.y

    def _on_drag_update(self, gesture, dx, dy):
        if not self._drag_mon: return
        sx, sy = gesture.get_start_point()[1], gesture.get_start_point()[2]
        px, py = sx + dx, sy + dy
        s, ox, oy = self._view_scale_offset()
        new_x = (px - ox) / s - self._drag_off_x
        new_y = (py - oy) / s - self._drag_off_y
        self._drag_mon.x = round(new_x)
        self._drag_mon.y = round(new_y)
        self.queue_draw()

    def _on_drag_end(self, gesture, dx, dy):
        if self._drag_mon:
            self._snap(self._drag_mon)
            self.queue_draw()
        self._drag_mon = None

    def _snap(self, m: MonitorModel, threshold: float = 30):
        """Rastet Monitor an benachbarten Monitoren ein."""
        for other in self.monitors:
            if other is m or other.disabled:
                continue
            # Horizontal
            for mx in [m.x, m.x + m.logical_w]:
                for ox_ in [other.x, other.x + other.logical_w]:
                    if abs(mx - ox_) < threshold:
                        m.x += ox_ - mx
            # Vertikal
            for my in [m.y, m.y + m.logical_h]:
                for oy_ in [other.y, other.y + other.logical_h]:
                    if abs(my - oy_) < threshold:
                        m.y += oy_ - my


# ── Settings panel ──────────────────────────────────────────────────────────

class MonitorSettingsPanel(Gtk.Box):
    """Settings for the selected monitor."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._monitor: MonitorModel | None = None
        self._loading = False
        self._on_primary_exclusive_cb = None

        self._placeholder = Adw.StatusPage()
        self._placeholder.set_icon_name("video-display-symbolic")
        self._placeholder.set_title(t("No monitor selected"))
        self._placeholder.set_description(t("Click on a monitor in the preview."))
        self._placeholder.set_vexpand(True)
        self.append(self._placeholder)

        self._panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._panel.set_vexpand(True)
        self._panel.set_visible(False)
        self.append(self._panel)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._panel.append(scroller)

        self._group = Adw.PreferencesGroup()
        self._group.set_margin_top(8)
        self._group.set_margin_bottom(12)
        self._group.set_margin_start(12)
        self._group.set_margin_end(12)
        scroller.set_child(self._group)

        # ── Resolution ──
        res_row = Adw.ActionRow(title=t("Resolution"))
        self._res_combo = Gtk.ComboBoxText()
        self._res_combo.set_valign(Gtk.Align.CENTER)
        self._res_combo.connect("changed", self._on_res_changed)
        res_row.add_suffix(self._res_combo)
        self._group.add(res_row)

        # ── Refresh rate ──
        hz_row = Adw.ActionRow(title=t("Refresh rate"))
        self._hz_combo = Gtk.ComboBoxText()
        self._hz_combo.set_valign(Gtk.Align.CENTER)
        self._hz_combo.connect("changed", self._on_hz_changed)
        hz_row.add_suffix(self._hz_combo)
        self._group.add(hz_row)

        # ── Rotation ──
        rot_row = Adw.ActionRow(title=t("Rotation"))
        self._rot_combo = Gtk.ComboBoxText()
        self._rot_combo.set_valign(Gtk.Align.CENTER)
        for r_id, r_lbl in ROTATION_OPTIONS:
            self._rot_combo.append(r_id, r_lbl)
        self._rot_combo.connect("changed", self._on_rot_changed)
        rot_row.add_suffix(self._rot_combo)
        self._group.add(rot_row)

        # ── Bit depth ──
        bd_row = Adw.ActionRow(title=t("Bit depth"))
        self._bd_combo = Gtk.ComboBoxText()
        self._bd_combo.set_valign(Gtk.Align.CENTER)
        for b_id, b_lbl in BITDEPTH_OPTIONS:
            self._bd_combo.append(b_id, b_lbl)
        self._bd_combo.connect("changed", self._on_bd_changed)
        bd_row.add_suffix(self._bd_combo)
        self._group.add(bd_row)

        # ── Colour management ──
        cm_row = Adw.ActionRow(title=t("Colour management"), subtitle="hl.monitor cm")
        self._cm_combo = Gtk.ComboBoxText()
        self._cm_combo.set_valign(Gtk.Align.CENTER)
        for cm_id, cm_label in COLOUR_MANAGEMENT_OPTIONS:
            self._cm_combo.append(cm_id, cm_label)
        self._cm_combo.connect("changed", self._on_cm_changed)
        cm_row.add_suffix(self._cm_combo)
        self._group.add(cm_row)

        # ── Variable refresh rate ──
        self._vrr_row = Adw.SwitchRow(title=t("Variable refresh rate (VRR)"))
        self._vrr_row.connect("notify::active", self._on_vrr_changed)
        self._group.add(self._vrr_row)

        # ── ICC profile ──
        self._icc_row = Adw.EntryRow(title=t("ICC profile"))
        self._icc_row.set_show_apply_button(False)
        self._icc_row.connect("changed", self._on_icc_changed)
        self._group.add(self._icc_row)

        # ── Mirror output ──
        self._mirror_row = Adw.EntryRow(title=t("Mirror output"))
        self._mirror_row.set_show_apply_button(False)
        self._mirror_row.set_tooltip_text(
            t("Name of the output to mirror, e.g. HDMI-A-1.")
        )
        self._mirror_row.connect("changed", self._on_mirror_changed)
        self._group.add(self._mirror_row)

        # ── SDR brightness / saturation ──
        sdr_brightness_row = Adw.ActionRow(
            title=t("SDR brightness"), subtitle="hl.monitor sdrbrightness"
        )
        self._sdr_brightness = Gtk.SpinButton.new_with_range(0.1, 10.0, 0.05)
        self._sdr_brightness.set_digits(2)
        self._sdr_brightness.set_valign(Gtk.Align.CENTER)
        self._sdr_brightness.connect("value-changed", self._on_luminance_changed)
        sdr_brightness_row.add_suffix(self._sdr_brightness)
        self._group.add(sdr_brightness_row)

        sdr_saturation_row = Adw.ActionRow(
            title=t("SDR saturation"), subtitle="hl.monitor sdrsaturation"
        )
        self._sdr_saturation = Gtk.SpinButton.new_with_range(0.0, 2.0, 0.05)
        self._sdr_saturation.set_digits(2)
        self._sdr_saturation.set_valign(Gtk.Align.CENTER)
        self._sdr_saturation.connect("value-changed", self._on_luminance_changed)
        sdr_saturation_row.add_suffix(self._sdr_saturation)
        self._group.add(sdr_saturation_row)

        sdr_min_row = Adw.ActionRow(
            title=t("SDR min luminance"), subtitle="hl.monitor sdr_min_luminance"
        )
        self._sdr_min = Gtk.SpinButton.new_with_range(0.0, 100.0, 0.01)
        self._sdr_min.set_digits(2)
        self._sdr_min.set_valign(Gtk.Align.CENTER)
        self._sdr_min.connect("value-changed", self._on_luminance_changed)
        sdr_min_row.add_suffix(self._sdr_min)
        self._group.add(sdr_min_row)

        sdr_max_row = Adw.ActionRow(
            title=t("SDR max luminance"), subtitle="hl.monitor sdr_max_luminance"
        )
        self._sdr_max = Gtk.SpinButton.new_with_range(0.0, 10000.0, 10.0)
        self._sdr_max.set_digits(0)
        self._sdr_max.set_valign(Gtk.Align.CENTER)
        self._sdr_max.connect("value-changed", self._on_luminance_changed)
        sdr_max_row.add_suffix(self._sdr_max)
        self._group.add(sdr_max_row)

        # ── HDR luminance ──
        min_luminance_row = Adw.ActionRow(
            title=t("Minimum luminance"), subtitle="hl.monitor min_luminance"
        )
        self._min_luminance = Gtk.SpinButton.new_with_range(0.0, 10000.0, 0.01)
        self._min_luminance.set_digits(2)
        self._min_luminance.set_valign(Gtk.Align.CENTER)
        self._min_luminance.connect("value-changed", self._on_luminance_changed)
        min_luminance_row.add_suffix(self._min_luminance)
        self._group.add(min_luminance_row)

        max_luminance_row = Adw.ActionRow(
            title=t("Maximum luminance"), subtitle="hl.monitor max_luminance"
        )
        self._max_luminance = Gtk.SpinButton.new_with_range(0.0, 10000.0, 10.0)
        self._max_luminance.set_digits(0)
        self._max_luminance.set_valign(Gtk.Align.CENTER)
        self._max_luminance.connect("value-changed", self._on_luminance_changed)
        max_luminance_row.add_suffix(self._max_luminance)
        self._group.add(max_luminance_row)

        max_avg_row = Adw.ActionRow(
            title=t("Maximum average luminance"),
            subtitle="hl.monitor max_avg_luminance",
        )
        self._max_avg_luminance = Gtk.SpinButton.new_with_range(0.0, 10000.0, 10.0)
        self._max_avg_luminance.set_digits(0)
        self._max_avg_luminance.set_valign(Gtk.Align.CENTER)
        self._max_avg_luminance.connect("value-changed", self._on_luminance_changed)
        max_avg_row.add_suffix(self._max_avg_luminance)
        self._group.add(max_avg_row)

        # ── Scaling ──
        scale_row = Adw.ActionRow(title=t("Scale"))
        self._scale_combo = Gtk.ComboBoxText()
        self._scale_combo.set_valign(Gtk.Align.CENTER)
        self._scale_combo.connect("changed", self._on_scale_changed)
        scale_row.add_suffix(self._scale_combo)
        self._group.add(scale_row)

        # ── Enabled ──
        self._enabled_row = Adw.SwitchRow(title=t("Monitor enabled"))
        self._enabled_row.connect("notify::active", self._on_enabled_changed)
        self._group.add(self._enabled_row)

        # ── Primary monitor ──
        self._primary_row = Adw.SwitchRow(
            title=t("Primary monitor"),
            subtitle=t("xrandr --primary (for X11 apps and tray)")
        )
        self._primary_row.connect("notify::active", self._on_primary_changed)
        self._group.add(self._primary_row)

        # ── Taskbar ──
        self._bar_row = Adw.SwitchRow(
            title=t("Always show taskbar"),
            subtitle="shell.json: bar.persistent"
        )
        self._bar_row.connect("notify::active", self._on_bar_changed)
        self._group.add(self._bar_row)

    def load(self, m: MonitorModel | None):
        self._monitor = m
        self._loading = True

        if m is None:
            self._placeholder.set_visible(True)
            self._panel.set_visible(False)
            self._loading = False
            return

        self._placeholder.set_visible(False)
        self._panel.set_visible(True)
        self._group.set_title(f"{m.name}  –  {m.description}")

        # Resolutionen laden
        self._res_combo.remove_all()
        for r in m.resolutions():
            self._res_combo.append(r, r)
        self._res_combo.set_active_id(m.resolution)

        # Load refresh rates, normalized to 3 decimals for stable comparison
        self._reload_hz(m.resolution)
        hz_norm = f"{float(m.hz):.3f}" if m.hz else ""
        if not self._hz_combo.set_active_id(hz_norm):
            # Fallback: ersten Eintrag nehmen
            self._hz_combo.set_active(0)
            first = self._hz_combo.get_active_id()
            if first:
                m.hz = first

        self._rot_combo.set_active_id(m.transform or "0")
        self._bd_combo.set_active_id(m.bitdepth if m.bitdepth else "")
        if not self._cm_combo.set_active_id(m.cm or ""):
            self._cm_combo.set_active_id("")
        self._vrr_row.set_active(bool(m.vrr))
        self._icc_row.set_text(m.icc)
        self._mirror_row.set_text(m.mirror)
        self._sdr_brightness.set_value(float(m.sdrbrightness or 1))
        self._sdr_saturation.set_value(float(m.sdrsaturation or 1))
        self._sdr_min.set_value(float(m.sdr_min_luminance or 0))
        self._sdr_max.set_value(float(m.sdr_max_luminance or 0))
        self._min_luminance.set_value(float(m.min_luminance or 0))
        self._max_luminance.set_value(float(m.max_luminance or 0))
        self._max_avg_luminance.set_value(float(m.max_avg_luminance or 0))
        self._reload_scales(m)
        self._enabled_row.set_active(not m.disabled)
        self._primary_row.set_active(m.primary)
        self._bar_row.set_active(m.bar_persistent)

        self._loading = False

    def _reload_hz(self, resolution: str):
        self._hz_combo.remove_all()
        if not self._monitor: return
        for h in self._monitor.hz_for_resolution(resolution):
            # IDs are always 3-decimal strings for stable comparison
            h_norm = f"{float(h):.3f}"
            self._hz_combo.append(h_norm, f"{float(h):.2f} Hz")

    def _on_res_changed(self, combo):
        if self._loading or not self._monitor: return
        res = combo.get_active_id()
        if not res: return
        self._monitor.resolution = res
        w, h = res.split("x")
        self._monitor.width  = int(w)
        self._monitor.height = int(h)
        self._loading = True
        self._reload_hz(res)
        self._reload_scales(self._monitor)
        # Default to the highest refresh rate
        hz_list = self._monitor.hz_for_resolution(res)
        if hz_list:
            self._hz_combo.set_active_id(hz_list[0])
            self._monitor.hz = hz_list[0]
        self._loading = False

    def _on_hz_changed(self, combo):
        if self._loading or not self._monitor: return
        hz = combo.get_active_id()
        if hz: self._monitor.hz = hz

    def _on_rot_changed(self, combo):
        if self._loading or not self._monitor: return
        t = combo.get_active_id()
        if t is not None: self._monitor.transform = t

    def _on_bd_changed(self, combo):
        if self._loading or not self._monitor: return
        bd = combo.get_active_id()
        if bd is not None: self._monitor.bitdepth = bd

    def _on_cm_changed(self, combo):
        if self._loading or not self._monitor: return
        cm = combo.get_active_id()
        if cm is not None: self._monitor.cm = cm

    def _on_vrr_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.vrr = row.get_active()

    def _on_icc_changed(self, row):
        if self._loading or not self._monitor: return
        self._monitor.icc = row.get_text().strip()

    def _on_mirror_changed(self, row):
        if self._loading or not self._monitor: return
        self._monitor.mirror = row.get_text().strip()

    def _on_luminance_changed(self, *_):
        if self._loading or not self._monitor: return
        self._monitor.sdrbrightness = round(self._sdr_brightness.get_value(), 2)
        self._monitor.sdrsaturation = round(self._sdr_saturation.get_value(), 2)
        self._monitor.sdr_min_luminance = round(self._sdr_min.get_value(), 2)
        self._monitor.sdr_max_luminance = int(self._sdr_max.get_value())
        self._monitor.min_luminance = round(self._min_luminance.get_value(), 2)
        self._monitor.max_luminance = int(self._max_luminance.get_value())
        self._monitor.max_avg_luminance = int(self._max_avg_luminance.get_value())

    def _reload_scales(self, m: MonitorModel):
        self._scale_combo.remove_all()
        width, height = m.width, m.height
        for scale in valid_scales(width, height):
            logical_w = int(round(width / scale))
            logical_h = int(round(height / scale))
            self._scale_combo.append(
                f"{scale:.3f}", f"{scale:g}   ({logical_w}×{logical_h})"
            )
        current = f"{m.scale:.3f}"
        if not self._scale_combo.set_active_id(current):
            self._scale_combo.append(current, f"{m.scale:g}   ({t('current')})")
            self._scale_combo.set_active_id(current)

    def _on_scale_changed(self, combo):
        if self._loading or not self._monitor:
            return
        value = combo.get_active_id()
        if value:
            self._monitor.scale = float(value)

    def _on_enabled_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.disabled = not row.get_active()

    def _on_bar_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.bar_persistent = row.get_active()

    def _on_primary_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.primary = row.get_active()
        # Only one monitor can be primary
        if row.get_active():
            # Propagated to MonitorPage via callback
            if hasattr(self, "_on_primary_exclusive_cb") and self._on_primary_exclusive_cb:
                self._on_primary_exclusive_cb(self._monitor)


# ── Haupt-Seite ───────────────────────────────────────────────────────────────

class MonitorPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self._monitors: list[MonitorModel] = []

        # ── Canvas ──
        canvas_frame = Gtk.Frame()
        canvas_frame.set_margin_top(12)
        canvas_frame.set_margin_start(12)
        canvas_frame.set_margin_end(12)
        self._canvas = MonitorCanvas(self._on_monitor_selected)
        canvas_frame.set_child(self._canvas)
        self.append(canvas_frame)

        # Canvas hint
        hint_text = t("Click to select  •  Drag to move")
        if kanshi.is_running():
            hint_text += "  ·  " + t("Kanshi is running; changes are synced to its profiles.")
        hint = Gtk.Label(label=hint_text)
        hint.add_css_class("caption")
        hint.set_margin_top(4)
        hint.set_margin_bottom(8)
        self.append(hint)

        # ── Separator ──
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Settings panel ──
        self._settings_panel = MonitorSettingsPanel()
        self._settings_panel._on_primary_exclusive_cb = self._on_primary_exclusive
        self.append(self._settings_panel)

        # ── Buttons ──
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(12)
        btn_box.set_margin_end(12)

        reload_btn = Gtk.Button(label=t("Reload"))
        reload_btn.connect("clicked", lambda _: self.load_monitors())
        btn_box.append(reload_btn)

        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        btn_box.append(apply_btn)

        self.append(btn_box)

        self.load_monitors()

    def load_monitors(self):
        raw = _get_live_monitors()
        self._monitors = [MonitorModel(m) for m in raw]

        # Mark the primary monitor from execs.lua
        primary_name = _get_primary_monitor()
        for m in self._monitors:
            m.primary = (m.name == primary_name)
            m.bar_persistent = _get_bar_persistent(m.name)

        self._canvas.monitors = self._monitors
        self._canvas.selected = None
        self._canvas.queue_draw()
        self._settings_panel.load(None)

    def _on_monitor_selected(self, m: MonitorModel | None):
        self._settings_panel.load(m)
        self._canvas.queue_draw()

    def _on_primary_exclusive(self, primary_mon: MonitorModel):
        """Ensure only one monitor is marked primary."""
        for m in self._monitors:
            if m is not primary_mon:
                m.primary = False

    def _on_apply(self, _btn):
        try:
            before = hyprctl_config_errors()
            backup_path = _save_monitors_conf(self._monitors)
            try:
                kanshi.update_config(self._monitors)
            except Exception as exc:  # noqa: BLE001 - Kanshi is optional
                print(f"Could not update Kanshi config: {exc}")
            _apply_to_hyprland(self._monitors)
            _ok, errors = reload_hyprland_checked()
            if errors and errors != before:
                if backup_path is not None:
                    backup.restore_backup(backup_path, _monitor_file())
                reload_hyprland()
                raise apply.ApplyError(errors)
            kanshi.reload()
            for monitor in self._monitors:
                if monitor.primary:
                    _set_primary_monitor(monitor.name)
                _set_bar_persistent(monitor.name, monitor.bar_persistent, restart=False)
            restart_caelestia()
            GLib.timeout_add(600, self.load_monitors)
            self.main_window.add_toast(
                Adw.Toast.new(t("Monitor configuration saved and applied."))
            )
        except apply.ApplyError as exc:
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Hyprland rejected the monitor configuration and it was rolled back')}: {exc}")
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save monitor configuration')}: {exc}")
            )

    # Compatibility helper
    def get_all_widget_settings(self):
        return {}