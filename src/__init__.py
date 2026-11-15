"""Caelestia Settings package.

GTK/Adwaita versions are pinned here so every submodule (and the test suite)
imports the same toolkit before any ``gi.repository`` import happens.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
