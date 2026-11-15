"""Shortcut capture helpers.

Turns GTK key events into Hyprland combo strings and provides a modal capture
dialog used by the keybind editor.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from src.lang import t

MODIFIERS = [
    ("CTRL", Gdk.ModifierType.CONTROL_MASK),
    ("ALT", Gdk.ModifierType.ALT_MASK),
    ("SHIFT", Gdk.ModifierType.SHIFT_MASK),
    ("SUPER", Gdk.ModifierType.SUPER_MASK),
]

KEY_NAMES = {
    "space": "Space",
    "Return": "Return",
    "BackSpace": "BackSpace",
    "Escape": "Escape",
    "Tab": "Tab",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "Page_Up",
    "Next": "Page_Down",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
    "Print": "Print",
    "Menu": "Menu",
    "minus": "Minus",
    "equal": "Equal",
    "comma": "Comma",
    "period": "Period",
    "slash": "Slash",
    "backslash": "Backslash",
    "semicolon": "Semicolon",
    "apostrophe": "Apostrophe",
    "grave": "Grave",
    "bracketleft": "BracketLeft",
    "bracketright": "BracketRight",
    "KP_Enter": "KP_Enter",
    "KP_Delete": "KP_Delete",
}

MODIFIER_KEYS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Super_L", "Super_R", "Meta_L", "Meta_R", "Hyper_L", "Hyper_R",
    "Caps_Lock", "Num_Lock", "ISO_Level3_Shift", "ISO_Level5_Shift",
}

MOUSE_BUTTONS = {
    1: "mouse:272",
    2: "mouse:274",
    3: "mouse:273",
    8: "mouse:275",
    9: "mouse:276",
}


def modifier_names(state) -> list[str]:
    return [name for name, mask in MODIFIERS if state & mask]


def key_name(keyval_name: str) -> str | None:
    if not keyval_name or keyval_name in MODIFIER_KEYS:
        return None
    if keyval_name in KEY_NAMES:
        return KEY_NAMES[keyval_name]
    if len(keyval_name) == 1:
        return keyval_name.upper()
    if keyval_name.startswith("KP_"):
        return keyval_name
    return keyval_name


def combo_from_state(keyval_name: str, state) -> str | None:
    key = key_name(keyval_name)
    if key is None:
        return None
    mods = modifier_names(state)
    return " + ".join(mods + [key])


def mouse_combo(button: int) -> str | None:
    return MOUSE_BUTTONS.get(button)


class ShortcutCaptureDialog(Adw.Dialog):
    """Modal shortcut recorder with live preview and mouse-button support."""

    def __init__(self, on_use, initial: str = ""):
        super().__init__()
        self._on_use = on_use
        self._combo = initial
        self._mods: list[str] = []
        self.set_content_width(520)
        self.set_content_height(430)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self.set_child(box)

        title = Gtk.Label(label=t("Record shortcut"))
        title.add_css_class("title-2")
        box.append(title)

        hint = Gtk.Label(
            label=t("Press a key combination. Modifier-only presses are ignored.")
        )
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        box.append(hint)

        self._preview = Gtk.Label(label=initial or t("Waiting for input…"))
        self._preview.add_css_class("title-1")
        self._preview.set_wrap(True)
        if initial:
            self._preview.add_css_class("accent")
        box.append(self._preview)

        mouse_frame = Gtk.Frame()
        mouse_frame.set_tooltip_text(t("Click here to record a mouse button"))
        mouse_label = Gtk.Label(
            label=t("Click here for a mouse button (left, middle, right, side)")
        )
        mouse_label.add_css_class("dim-label")
        mouse_label.set_margin_top(18)
        mouse_label.set_margin_bottom(18)
        mouse_frame.set_child(mouse_label)
        box.append(mouse_frame)

        click = Gtk.GestureClick()
        click.connect("released", self._on_mouse)
        mouse_frame.add_controller(click)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label=t("Cancel"))
        cancel.connect("clicked", lambda _b: self.close())
        buttons.append(cancel)
        clear = Gtk.Button(label=t("Clear"))
        clear.connect("clicked", self._on_clear)
        buttons.append(clear)
        self._use_btn = Gtk.Button(label=t("Use shortcut"))
        self._use_btn.add_css_class("suggested-action")
        self._use_btn.set_sensitive(bool(initial))
        self._use_btn.connect("clicked", self._on_use_clicked)
        buttons.append(self._use_btn)
        box.append(buttons)

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self._on_key)
        self.add_controller(controller)

    def _set_preview(self, text: str):
        self._preview.set_text(text or t("Waiting for input…"))
        self._use_btn.set_sensitive(bool(self._combo))

    def _on_key(self, controller, keyval, keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        if name == "Escape":
            self.close()
            return True
        mods = modifier_names(state)
        key = key_name(name)
        if key is None:
            self._mods = mods
            self._set_preview(" + ".join(mods + ["…"]) if mods else t("Waiting for input…"))
            return True
        self._combo = " + ".join(mods + [key])
        self._set_preview(self._combo)
        return True

    def _on_mouse(self, gesture, n_press, x, y):
        combo = mouse_combo(gesture.get_current_button())
        if combo is None:
            return
        mods = modifier_names(gesture.get_current_event_state())
        self._combo = " + ".join(mods + [combo])
        self._set_preview(self._combo)

    def _on_clear(self, _button):
        self._combo = ""
        self._set_preview("")

    def _on_use_clicked(self, _button):
        if not self._combo:
            return
        self._on_use(self._combo)
        self.close()
