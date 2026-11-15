from src import devices


def test_parse_devices_categorises_touchpads():
    payload = {
        "keyboards": [{"name": "kbd", "address": "0x1"}],
        "mice": [
            {"name": "mouse", "address": "0x2"},
            {"name": "ven_06cb-touchpad", "address": "0x3"},
        ],
        "touch": [{"name": "touchscreen", "address": "0x4"}],
        "tablets": [],
    }
    parsed = devices.parse_devices(payload)
    kinds = {device.name: device.kind for device in parsed}
    assert kinds["kbd"] == "keyboard"
    assert kinds["mouse"] == "pointer"
    assert kinds["ven_06cb-touchpad"] == "touchpad"
    assert kinds["touchscreen"] == "touch"


def test_overrides_roundtrip():
    text = "local config = {}\n\nreturn config\n"
    overrides = {
        "mouse": {"name": "mouse", "sensitivity": 0.5, "tap_to_click": True},
        "kbd": {"name": "kbd", "kb_layout": "fr"},
    }
    written = devices.write_overrides(text, overrides)
    assert "BEGIN Caelestia Settings: input devices" in written
    assert written.index("BEGIN Caelestia Settings") < written.index("return config")

    parsed = devices.parse_overrides(written)
    assert parsed["mouse"]["sensitivity"] == 0.5
    assert parsed["mouse"]["tap_to_click"] is True
    assert parsed["kbd"]["kb_layout"] == "fr"


def test_write_overrides_removes_empty_block():
    text = (
        "local config = {}\n\n"
        "-- BEGIN Caelestia Settings: input devices\n"
        'hl.device({ name = "x", sensitivity = 0.2 })\n'
        "-- END Caelestia Settings: input devices\n\n"
        "return config\n"
    )
    cleaned = devices.write_overrides(text, {})
    assert "input devices" not in cleaned
    assert cleaned.strip().startswith("local config")


def test_system_device_filter():
    assert devices.is_system_device("video-bus")
    assert devices.is_system_device("power-button")
    assert devices.is_system_device("rustdesk-uinput-keyboard")
    assert not devices.is_system_device("razer-razer-blackwidow-elite")
    assert not devices.is_system_device("ven_06cb-touchpad")


def test_defaults_exist_for_every_field():
    for fields in devices.FIELDS.values():
        for key, _label, kind, _min, _max, _step, _option, _enum in fields:
            value = devices.default_for(key, kind)
            assert value is not None
