"""Wallpaper, colour scheme and desktop clock.

Caelestia 2.x handles images, GIFs and videos natively (``caelestia wallpaper
-f``), so the old ``mpvpaper`` autostart hack is gone.  The wallpaper folder is
read from ``paths.wallpaperDir`` in ``shell.json`` with ``~/Pictures/Wallpapers``
as the default.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from gi.repository import Adw, GdkPixbuf, GLib, Gtk

from src import backup, shell_config
from src.lang import t

THUMB_SIZE = 160
THUMB_CACHE = Path.home() / ".cache" / "caelestia-settings" / "thumbs"
CAELESTIA_VIDEO_THUMBS = Path.home() / ".cache" / "caelestia" / "videothumbs"
_LEGACY_MPV_PID = Path.home() / ".cache" / "caelestia-settings" / "mpvpaper.pid"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm"}
ANIMATED_DIR_NAME = "Animated"

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
CLOCK_POSITIONS = [
    ("top-right", t("Top right")),
    ("top-left", t("Top left")),
    ("bottom-right", t("Bottom right")),
    ("bottom-left", t("Bottom left")),
]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_dirs() -> None:
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)


def get_current_wallpaper() -> str:
    path = Path.home() / ".local" / "state" / "caelestia" / "wallpaper" / "path.txt"
    try:
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except OSError:
        return ""


def _state_scheme() -> dict:
    path = Path.home() / ".local" / "state" / "caelestia" / "scheme.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def video_dir() -> Path:
    """Animated wallpapers live in ``<wallpaperDir>/Animated``."""

    return shell_config.wallpaper_dir() / ANIMATED_DIR_NAME


def _scan(directory: Path, extensions: set[str], exclude: Path | None = None) -> list[Path]:
    if not directory.exists():
        return []
    files = []
    for file in directory.rglob("*"):
        if not file.is_file() or file.suffix.lower() not in extensions:
            continue
        if exclude is not None and exclude != directory:
            try:
                if file.is_relative_to(exclude):
                    continue
            except ValueError:
                pass
        files.append(file)
    return sorted(files, key=lambda path: str(path).lower())


def _djb2(text: str) -> str:
    value = 5381
    for char in text:
        value = ((value << 5) + value) + ord(char)
    return str(value & 0xFFFFFFFF)


def _thumb_path(path: Path) -> Path:
    try:
        stat = path.stat()
        return THUMB_CACHE / f"{_djb2(str(path.resolve()))}_{stat.st_size}_{int(stat.st_mtime)}.jpg"
    except OSError:
        return THUMB_CACHE / f"{_djb2(str(path))}.jpg"


def _make_image_thumb(path: Path) -> GdkPixbuf.Pixbuf | None:
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), THUMB_SIZE, THUMB_SIZE, True)
    except Exception as exc:  # noqa: BLE001 - corrupt image, just hide the thumb
        print(f"Thumbnail failed for {path.name}: {exc}")
        return None


def _make_video_thumb(path: Path) -> GdkPixbuf.Pixbuf | None:
    # Reuse Caelestia's own thumbnail cache when available.
    candidates = [
        CAELESTIA_VIDEO_THUMBS / f"{_djb2(str(path.resolve()))}.jpg",
        _thumb_path(path),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(candidate), THUMB_SIZE, THUMB_SIZE, True)
            except Exception:  # noqa: BLE001
                continue

    cache = _thumb_path(path)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "00:00:02", "-i", str(path),
                "-vframes", "1", "-vf", f"scale={THUMB_SIZE * 2}:-1", str(cache),
            ],
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ffmpeg failed for {path.name}: {exc}")
        return None
    if cache.exists():
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache), THUMB_SIZE, THUMB_SIZE, True)
        except Exception:  # noqa: BLE001
            pass
    return None


def _set_wallpaper(path: Path) -> None:
    _kill_legacy_mpvpaper()
    subprocess.Popen(["caelestia", "wallpaper", "-f", str(path)])


def _kill_legacy_mpvpaper() -> None:
    """Clean up processes left behind by the old mpvpaper implementation."""

    try:
        if _LEGACY_MPV_PID.exists():
            pid = int(_LEGACY_MPV_PID.read_text().strip())
            os.kill(pid, 15)
    except (OSError, ValueError):
        pass
    try:
        _LEGACY_MPV_PID.unlink(missing_ok=True)
    except OSError:
        pass


# ── Shared media grid ────────────────────────────────────────────────────────


class MediaGrid(Gtk.Box):
    def __init__(self, on_select_cb, empty_text: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_select = on_select_cb
        self._empty_text = empty_text

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.flow = Gtk.FlowBox()
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_max_children_per_line(20)
        self.flow.set_min_children_per_line(2)
        self.flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flow.set_row_spacing(8)
        self.flow.set_column_spacing(8)
        self.flow.set_margin_top(8)
        self.flow.set_margin_bottom(12)
        self.flow.set_margin_start(12)
        self.flow.set_margin_end(12)
        self.flow.connect("child-activated", self._on_activated)
        scroller.set_child(self.flow)

        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_size_request(-1, 48)
        self.append(self.spinner)

        self.empty_label = Gtk.Label()
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(32)
        self.empty_label.set_halign(Gtk.Align.CENTER)
        self.empty_label.set_visible(False)
        self.append(self.empty_label)

    def set_empty_text(self, text: str):
        self._empty_text = text

    def load(self, files: list[Path], current: str, thumb_fn, is_video: bool = False):
        while child := self.flow.get_first_child():
            self.flow.remove(child)
        self.empty_label.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

        def thread():
            GLib.idle_add(self._populate, files, current, thumb_fn, is_video)

        threading.Thread(target=thread, daemon=True).start()

    def _populate(self, files, current, thumb_fn, is_video):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not files:
            self.empty_label.set_label(self._empty_text)
            self.empty_label.set_visible(True)
            return

        for path in files:
            self.flow.append(MediaCard(path, current, is_video))

        threading.Thread(target=self._load_thumbs, args=(files, thumb_fn), daemon=True).start()

    def _load_thumbs(self, files, thumb_fn):
        child = self.flow.get_first_child()
        for path in files:
            if child is None:
                break
            card = child.get_child()
            if isinstance(card, MediaCard):
                pixbuf = thumb_fn(path)
                if pixbuf:
                    GLib.idle_add(card.set_thumbnail, pixbuf)
            child = child.get_next_sibling()

    def _on_activated(self, _flow, child):
        card = child.get_child()
        if isinstance(card, MediaCard):
            self._on_select(card.path)

    def mark_current(self, path: str):
        child = self.flow.get_first_child()
        while child:
            card = child.get_child()
            if isinstance(card, MediaCard):
                if str(card.path) == path:
                    card.add_css_class("suggested-action")
                else:
                    card.remove_css_class("suggested-action")
            child = child.get_next_sibling()


class MediaCard(Gtk.Box):
    def __init__(self, path: Path, current: str, is_video: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.path = path
        self.set_size_request(THUMB_SIZE, THUMB_SIZE + 30)

        is_current = str(path) == current
        self.image = Gtk.Image()
        self.image.set_pixel_size(THUMB_SIZE)
        self.image.set_from_icon_name(
            "video-x-generic-symbolic" if is_video else "image-x-generic-symbolic"
        )
        self.image.set_size_request(THUMB_SIZE, THUMB_SIZE)
        self.image.add_css_class("card")

        if is_current:
            overlay = Gtk.Overlay()
            overlay.set_child(self.image)
            check = Gtk.Image.new_from_icon_name("object-select-symbolic")
            check.set_halign(Gtk.Align.END)
            check.set_valign(Gtk.Align.END)
            check.set_margin_end(4)
            check.set_margin_bottom(4)
            overlay.add_overlay(check)
            self.append(overlay)
            self.add_css_class("suggested-action")
        else:
            self.append(self.image)

        if is_video:
            badge = Gtk.Label(label="▶ Video")
            badge.add_css_class("caption")
            badge.add_css_class("accent")
            self.append(badge)

        stem = path.stem
        name_label = Gtk.Label(label=stem[:22] + ("…" if len(stem) > 22 else ""))
        name_label.add_css_class("caption")
        name_label.set_ellipsize(3)
        self.append(name_label)

    def set_thumbnail(self, pixbuf: GdkPixbuf.Pixbuf):
        self.image.set_from_pixbuf(pixbuf)


# ── Page ─────────────────────────────────────────────────────────────────────


class WallpaperPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)

        _ensure_dirs()
        self._image_dir = shell_config.wallpaper_dir()
        self._current = get_current_wallpaper()

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_top(10)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tabs.add_css_class("linked")
        self._tab_images = Gtk.ToggleButton(label=t("Images"))
        self._tab_images.set_active(True)
        self._tab_images.connect("toggled", self._on_tab_toggle)
        tabs.append(self._tab_images)
        self._tab_videos = Gtk.ToggleButton(label=t("Videos"))
        self._tab_videos.set_group(self._tab_images)
        self._tab_videos.connect("toggled", self._on_tab_toggle)
        tabs.append(self._tab_videos)
        toolbar.append(tabs)

        self._random_btn = Gtk.Button(label=t("Random"))
        self._random_btn.set_tooltip_text(t("Set a random wallpaper from this folder"))
        self._random_btn.connect("clicked", self._on_random)
        toolbar.append(self._random_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        self._mode_btn = Gtk.ToggleButton()
        scheme = _state_scheme()
        self._scheme_mode = str(scheme.get("mode", "dark"))
        self._mode_btn.set_tooltip_text(t("Light / dark mode"))
        self._mode_btn.set_active(self._scheme_mode == "light")
        self._mode_btn.set_icon_name(
            "weather-clear-symbolic" if self._scheme_mode == "light" else "weather-clear-night-symbolic"
        )
        self._mode_btn.connect("toggled", self._on_mode_toggled)
        toolbar.append(self._mode_btn)

        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._reload())
        toolbar.append(reload_btn)
        self.append(toolbar)

        self._path_label = Gtk.Label()
        self._path_label.add_css_class("dim-label")
        self._path_label.set_halign(Gtk.Align.CENTER)
        self._path_label.set_margin_bottom(4)
        self.append(self._path_label)

        self.append(self._build_clock_group())

        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        self.append(self.banner)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.append(self._stack)

        self._image_grid = MediaGrid(
            self._on_media_selected,
            t("No images found.\nPut images in the wallpaper folder."),
        )
        self._video_grid = MediaGrid(
            self._on_media_selected,
            t("No videos found.\nCaelestia plays mp4, webm and mkv wallpapers natively."),
        )
        self._stack.add_named(self._image_grid, "images")
        self._stack.add_named(self._video_grid, "videos")

        self._update_path_label()
        self._load_images()

    # ── Scheme ────────────────────────────────────────────────────────────

    def _build_scheme_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title=t("Colour scheme"))
        group.set_margin_start(12)
        group.set_margin_end(12)
        group.set_margin_bottom(6)

        scheme = _state_scheme()
        current_name = str(scheme.get("name", "dynamic"))
        current_flavour = str(scheme.get("flavour", "default"))
        current_variant = str(scheme.get("variant", "tonalspot"))

        name_row = Adw.ActionRow(title=t("Scheme"))
        self._scheme_name = Gtk.ComboBoxText()
        self._scheme_name.set_valign(Gtk.Align.CENTER)
        for name in SCHEME_NAMES:
            self._scheme_name.append(name, name)
        if not self._scheme_name.set_active_id(current_name):
            self._scheme_name.append(current_name, current_name)
            self._scheme_name.set_active_id(current_name)
        name_row.add_suffix(self._scheme_name)
        group.add(name_row)

        flavour_row = Adw.ActionRow(title=t("Flavour"))
        self._scheme_flavour = Gtk.ComboBoxText()
        self._scheme_flavour.set_valign(Gtk.Align.CENTER)
        for flavour in SCHEME_FLAVOURS:
            self._scheme_flavour.append(flavour, flavour)
        if not self._scheme_flavour.set_active_id(current_flavour):
            self._scheme_flavour.append(current_flavour, current_flavour)
            self._scheme_flavour.set_active_id(current_flavour)
        flavour_row.add_suffix(self._scheme_flavour)
        group.add(flavour_row)

        variant_row = Adw.ActionRow(title=t("Variant"))
        self._scheme_variant = Gtk.ComboBoxText()
        self._scheme_variant.set_valign(Gtk.Align.CENTER)
        for variant in SCHEME_VARIANTS:
            self._scheme_variant.append(variant, variant)
        if not self._scheme_variant.set_active_id(current_variant):
            self._scheme_variant.append(current_variant, current_variant)
            self._scheme_variant.set_active_id(current_variant)
        variant_row.add_suffix(self._scheme_variant)
        group.add(variant_row)

        apply_row = Adw.ActionRow(title=t("Apply scheme"))
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self._on_apply_scheme)
        apply_row.add_suffix(apply_btn)
        group.add(apply_row)
        return group

    def _on_apply_scheme(self, _button):
        name = self._scheme_name.get_active_id()
        flavour = self._scheme_flavour.get_active_id()
        variant = self._scheme_variant.get_active_id()
        mode = "light" if self._mode_btn.get_active() else "dark"
        command = ["caelestia", "scheme", "set", "--notify"]
        if name:
            command += ["-n", name]
        if flavour:
            command += ["-f", flavour]
        if variant:
            command += ["-v", variant]
        command += ["-m", mode]
        try:
            subprocess.Popen(command)
            self._show_banner(t("Colour scheme updated"))
            self.main_window.add_toast(Adw.Toast.new(t("Colour scheme updated")))
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not change scheme')}: {exc}"))

    # ── Desktop clock & background ────────────────────────────────────────

    def _monitor_names(self) -> list[str]:
        try:
            result = subprocess.run(
                ["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3
            )
            return [monitor["name"] for monitor in json.loads(result.stdout)]
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return []

    def _build_clock_group(self) -> Gtk.Widget:
        expander = Adw.ExpanderRow(title=t("Background and desktop clock"))
        expander.set_subtitle(t("Wallpaper, clock position, size, colours and overlays"))

        target_row = Adw.ActionRow(title=t("Apply to"))
        self._clock_target = Gtk.ComboBoxText()
        self._clock_target.set_valign(Gtk.Align.CENTER)
        self._clock_target.append("", t("All monitors (global)"))
        for name in self._monitor_names():
            self._clock_target.append(name, f"{t('Only')} {name}")
        self._clock_target.set_active(0)
        self._clock_target.connect("changed", self._on_clock_target_changed)
        target_row.add_suffix(self._clock_target)
        expander.add_row(target_row)

        self._background_enabled = Adw.SwitchRow(title=t("Background enabled"))
        expander.add_row(self._background_enabled)
        self._wallpaper_enabled = Adw.SwitchRow(title=t("Wallpaper enabled"))
        expander.add_row(self._wallpaper_enabled)
        self._visualiser_enabled = Adw.SwitchRow(title=t("Audio visualiser"))
        expander.add_row(self._visualiser_enabled)

        self._clock_enabled = Adw.SwitchRow(title=t("Show clock"))
        expander.add_row(self._clock_enabled)

        position_row = Adw.ActionRow(title=t("Clock position"))
        self._clock_position = Gtk.ComboBoxText()
        self._clock_position.set_valign(Gtk.Align.CENTER)
        for position_id, label in CLOCK_POSITIONS:
            self._clock_position.append(position_id, label)
        position_row.add_suffix(self._clock_position)
        expander.add_row(position_row)

        self._clock_scale = Adw.SpinRow.new_with_range(0.5, 3.0, 0.05)
        self._clock_scale.set_digits(2)
        self._clock_scale.set_title(t("Clock scale"))
        expander.add_row(self._clock_scale)

        self._clock_invert = Adw.SwitchRow(title=t("Invert clock colours"))
        expander.add_row(self._clock_invert)

        self._clock_background = Adw.SwitchRow(title=t("Clock background"))
        expander.add_row(self._clock_background)

        self._clock_background_opacity = Adw.SpinRow.new_with_range(0.0, 1.0, 0.05)
        self._clock_background_opacity.set_digits(2)
        self._clock_background_opacity.set_title(t("Clock background opacity"))
        expander.add_row(self._clock_background_opacity)

        self._clock_background_blur = Adw.SwitchRow(title=t("Blur clock background"))
        expander.add_row(self._clock_background_blur)

        self._clock_shadow = Adw.SwitchRow(title=t("Clock shadow"))
        expander.add_row(self._clock_shadow)

        self._clock_shadow_opacity = Adw.SpinRow.new_with_range(0.0, 1.0, 0.05)
        self._clock_shadow_opacity.set_digits(2)
        self._clock_shadow_opacity.set_title(t("Clock shadow opacity"))
        expander.add_row(self._clock_shadow_opacity)

        self._clock_shadow_blur = Adw.SpinRow.new_with_range(0.0, 2.0, 0.05)
        self._clock_shadow_blur.set_digits(2)
        self._clock_shadow_blur.set_title(t("Clock shadow blur"))
        expander.add_row(self._clock_shadow_blur)

        apply_row = Adw.ActionRow(title=t("Apply background settings"))
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self._on_clock_apply)
        apply_row.add_suffix(apply_btn)
        expander.add_row(apply_row)

        self._clock_expander = expander
        self._load_clock_values()

        # Adw.ExpanderRow must live inside a Gtk.ListBox.
        wrapper = Gtk.ListBox()
        wrapper.set_selection_mode(Gtk.SelectionMode.NONE)
        wrapper.add_css_class("boxed-list")
        wrapper.set_margin_start(12)
        wrapper.set_margin_end(12)
        wrapper.set_margin_bottom(6)
        wrapper.append(expander)
        return wrapper

    def _clock_target_name(self) -> str | None:
        value = self._clock_target.get_active_id() if hasattr(self, "_clock_target") else ""
        return value or None

    def _load_clock_values(self):
        monitor = self._clock_target_name()
        if not hasattr(self, "_clock_enabled"):
            return
        self._clock_enabled.set_active(bool(shell_config.get("background.desktopClock.enabled", False, monitor)))
        position = str(shell_config.get("background.desktopClock.position", "bottom-right", monitor))
        if not self._clock_position.set_active_id(position):
            self._clock_position.append(position, position)
            self._clock_position.set_active_id(position)
        self._clock_scale.set_value(float(shell_config.get("background.desktopClock.scale", 1, monitor)))
        self._clock_invert.set_active(bool(shell_config.get("background.desktopClock.invertColors", False, monitor)))
        self._clock_background.set_active(
            bool(shell_config.get("background.desktopClock.background.enabled", False, monitor))
        )
        self._clock_background_opacity.set_value(
            float(shell_config.get("background.desktopClock.background.opacity", 0.7, monitor))
        )
        self._clock_background_blur.set_active(
            bool(shell_config.get("background.desktopClock.background.blur", True, monitor))
        )
        self._clock_shadow.set_active(
            bool(shell_config.get("background.desktopClock.shadow.enabled", True, monitor))
        )
        self._clock_shadow_opacity.set_value(
            float(shell_config.get("background.desktopClock.shadow.opacity", 0.7, monitor))
        )
        self._clock_shadow_blur.set_value(
            float(shell_config.get("background.desktopClock.shadow.blur", 0.4, monitor))
        )
        self._background_enabled.set_active(bool(shell_config.get("background.enabled", True, monitor)))
        self._wallpaper_enabled.set_active(
            bool(shell_config.get("background.wallpaperEnabled", True, monitor))
        )
        self._visualiser_enabled.set_active(
            bool(shell_config.get("background.visualiser.enabled", False, monitor))
        )

    def _on_clock_target_changed(self, _combo):
        self._load_clock_values()

    def _on_clock_apply(self, _button):
        monitor = self._clock_target_name()
        values = {
            "background.enabled": self._background_enabled.get_active(),
            "background.wallpaperEnabled": self._wallpaper_enabled.get_active(),
            "background.visualiser.enabled": self._visualiser_enabled.get_active(),
            "background.desktopClock.enabled": self._clock_enabled.get_active(),
            "background.desktopClock.position": self._clock_position.get_active_id() or "bottom-right",
            "background.desktopClock.scale": round(self._clock_scale.get_value(), 2),
            "background.desktopClock.invertColors": self._clock_invert.get_active(),
            "background.desktopClock.background.enabled": self._clock_background.get_active(),
            "background.desktopClock.background.opacity": round(self._clock_background_opacity.get_value(), 2),
            "background.desktopClock.background.blur": self._clock_background_blur.get_active(),
            "background.desktopClock.shadow.enabled": self._clock_shadow.get_active(),
            "background.desktopClock.shadow.opacity": round(self._clock_shadow_opacity.get_value(), 2),
            "background.desktopClock.shadow.blur": round(self._clock_shadow_blur.get_value(), 2),
        }
        try:
            shell_config.set_many(values, monitor)
            self._show_banner(t("Background settings applied"))
            self.main_window.add_toast(Adw.Toast.new(t("Background settings applied")))
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save background settings')}: {exc}")
            )

    # ── Tabs / loading ────────────────────────────────────────────────────

    def _update_path_label(self):
        current_dir = (
            video_dir()
            if self._stack.get_visible_child_name() == "videos"
            else self._image_dir
        )
        self._path_label.set_markup(
            f"<small><tt>{str(current_dir).replace(str(Path.home()), '~')}</tt></small>"
        )

    def _on_tab_toggle(self, button):
        if not button.get_active():
            return
        if button is self._tab_images:
            self._stack.set_visible_child_name("images")
            self._random_btn.set_sensitive(True)
        else:
            self._stack.set_visible_child_name("videos")
            # `caelestia wallpaper -r` only picks images.
            self._random_btn.set_sensitive(False)
        self._update_path_label()

    def _reload(self):
        self._image_dir = shell_config.wallpaper_dir()
        self._current = get_current_wallpaper()
        self._update_path_label()
        if self._stack.get_visible_child_name() == "images":
            self._load_images()
        else:
            self._load_videos()

    def _load_images(self):
        self._image_dir = shell_config.wallpaper_dir()
        self._image_grid.load(
            _scan(self._image_dir, IMAGE_EXTENSIONS, exclude=video_dir()),
            self._current,
            _make_image_thumb,
            False,
        )

    def _load_videos(self):
        animated = video_dir()
        self._video_grid.set_empty_text(
            t("No videos found.\nPut videos in the Animated folder:")
            + f"\n{str(animated).replace(str(Path.home()), '~')}"
        )
        self._video_grid.load(
            _scan(animated, VIDEO_EXTENSIONS), self._current, _make_video_thumb, True
        )

    # ── Selection ─────────────────────────────────────────────────────────

    def _on_media_selected(self, path: Path):
        try:
            _set_wallpaper(path)
            self._current = str(path)
            self._image_grid.mark_current(self._current)
            self._video_grid.mark_current(self._current)
            self._show_banner(f"{t('Wallpaper')}: {path.name}")
            self.main_window.add_toast(Adw.Toast.new(f"{t('Wallpaper')}: {path.name}"))
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not set wallpaper')}: {exc}"))

    def _on_random(self, _button):
        try:
            subprocess.Popen(["caelestia", "wallpaper", "-r", str(shell_config.wallpaper_dir())])
            self._show_banner(t("Random wallpaper set"))
            self.main_window.add_toast(Adw.Toast.new(t("Random wallpaper set")))
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not set wallpaper')}: {exc}"))

    def _on_mode_toggled(self, button):
        mode = "light" if button.get_active() else "dark"
        self._scheme_mode = mode
        button.set_icon_name(
            "weather-clear-symbolic" if mode == "light" else "weather-clear-night-symbolic"
        )
        try:
            subprocess.Popen(["caelestia", "scheme", "set", "--notify", "-m", mode])
            self._show_banner(f"{t('Colour mode')}: {mode.capitalize()}")
            self.main_window.add_toast(Adw.Toast.new(f"{t('Colour mode')}: {mode.capitalize()}"))
        except (OSError, subprocess.SubprocessError) as exc:
            self.main_window.add_toast(Adw.Toast.new(f"{t('Could not change scheme')}: {exc}"))

    def _show_banner(self, text: str):
        self.banner.set_title(text)
        self.banner.set_revealed(True)
