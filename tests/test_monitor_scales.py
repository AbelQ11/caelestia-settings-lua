from src.pages.monitor import valid_scales


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
