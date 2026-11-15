from types import SimpleNamespace

from src import kanshi


def _model(name, **kwargs):
    data = {
        "name": name,
        "resolution": "2560x1600",
        "hz": "240.000",
        "x": 0,
        "y": 0,
        "scale": 1.5,
        "disabled": False,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_update_kanshi_profiles():
    text = """# Profile 1
profile dual-extend {
    output "HDMI-A-1" enable mode preferred position 0,0
    output "eDP-1" enable mode 2560x1600@240Hz position 0,0 scale 1.25
}

profile internal-only {
    output "eDP-1" enable mode 2560x1600@240Hz position 0,0 scale 1.25
    output "HDMI-A-1" disable
}
"""
    models = [
        _model("eDP-1", scale=1.5),
        _model("HDMI-A-1", resolution="1920x1080", hz="60", scale=1),
    ]
    updated = kanshi.update_text(text, models)
    assert "# Profile 1" in updated
    assert 'output "eDP-1" enable mode 2560x1600@240Hz position 0,0 scale 1.5' in updated
    assert 'output "HDMI-A-1" enable mode 1920x1080@60Hz position 0,0 scale 1' in updated


def test_update_preserves_unknown_output_options():
    text = """profile test {
    output "eDP-1" enable mode preferred position 0,0 scale 1.25 transform 1
}
"""
    updated = kanshi.update_text(text, [_model("eDP-1", scale=1.25)])
    assert "transform 1" in updated
    assert "mode 2560x1600@240Hz" in updated
    assert "scale 1.25" in updated


def test_update_disabled_output():
    text = """profile test {
    output "eDP-1" enable mode 2560x1600@240Hz position 0,0 scale 1.25
}
"""
    updated = kanshi.update_text(text, [_model("eDP-1", disabled=True)])
    assert 'output "eDP-1" disable' in updated
    assert "scale" not in updated
