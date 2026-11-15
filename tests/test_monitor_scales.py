import pytest

from src.pages.monitor import MonitorModel, MonitorSettingsPanel, valid_scales


def test_valid_scales_for_laptop_panel():
    scales = valid_scales(2560, 1600)
    assert 1.25 in scales
    assert 1.6 in scales
    assert 2.0 in scales
    # 1.5 would produce a non-integer logical resolution (1706.67 x 1066.67).
    assert 1.5 not in scales


def test_valid_scales_for_1080p():
    scales = valid_scales(1920, 1080)
    assert 1.0 in scales
    assert 1.2 in scales
    assert 1.5 in scales
    assert 1.6 in scales


def _display_available() -> bool:
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gdk

    return Gdk.Display.get_default() is not None


@pytest.mark.skipif(not _display_available(), reason="no display available")
def test_settings_panel_loads_every_field():
    """Regression: ``load()`` must not reference widgets missing from ``__init__``."""

    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    app = Adw.Application(application_id="org.caelestia.settings.scaletest")
    app.register(None)

    model = MonitorModel(
        {
            "name": "eDP-1",
            "description": "Test panel",
            "width": 2560,
            "height": 1600,
            "scale": 1.25,
            "refreshRate": 240,
            "availableModes": ["2560x1600@240.00Hz"],
        }
    )

    panel = MonitorSettingsPanel()
    panel.load(model)

    assert panel._scale_combo.get_active_id() == "1.250"
    for scale in valid_scales(2560, 1600):
        assert panel._scale_combo.set_active_id(f"{scale:.3f}")
        assert model.scale == scale

    panel.unparent()
    app.quit()
