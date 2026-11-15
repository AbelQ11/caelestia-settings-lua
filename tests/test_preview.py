from src import preview


def test_rgb_parsing():
    assert preview._rgb("ff0000") == (1.0, 0.0, 0.0, 1.0)
    assert preview._rgb("00ff0080", 0.5) == (0.0, 1.0, 0.0, 0.5)
    assert preview._rgb("bad", 0.25) == (0.5, 0.5, 0.5, 0.25)


def test_preview_model_values():
    model = preview.PreviewModel({"bar.persistent": False}, {"primary": "ffffff"})
    assert model.get("bar.persistent") is False
    assert model.get("missing", 42) == 42


def test_scheme_colours_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(preview, "SCHEME_STATE", tmp_path / "missing.json")
    colours = preview.read_scheme_colours()
    assert "background" in colours
    assert "primary" in colours
