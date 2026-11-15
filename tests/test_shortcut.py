import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from src import shortcut


def test_key_name_normalization():
    assert shortcut.key_name("space") == "Space"
    assert shortcut.key_name("Return") == "Return"
    assert shortcut.key_name("Prior") == "Page_Up"
    assert shortcut.key_name("BackSpace") == "BackSpace"
    assert shortcut.key_name("a") == "A"
    assert shortcut.key_name("minus") == "Minus"
    assert shortcut.key_name("Shift_L") is None
    assert shortcut.key_name("ISO_Level3_Shift") is None


def test_modifiers_and_combo():
    state = (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.SUPER_MASK
    )
    assert shortcut.modifier_names(state) == ["CTRL", "SHIFT", "SUPER"]
    assert shortcut.combo_from_state("t", state) == "CTRL + SHIFT + SUPER + T"


def test_mouse_buttons():
    assert shortcut.mouse_combo(1) == "mouse:272"
    assert shortcut.mouse_combo(3) == "mouse:273"
    assert shortcut.mouse_combo(8) == "mouse:275"
    assert shortcut.mouse_combo(99) is None
