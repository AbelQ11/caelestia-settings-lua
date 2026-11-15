from src.pages import keybinds


def test_parse_managed_binds():
    text = """local config = {}

return config
"""
    text = keybinds.lua.replace_managed_block(
        text,
        keybinds.BLOCK_KEYBINDS,
        '\n'.join([
            'hl.bind("SUPER + T", hl.dsp.exec_cmd("foot"))',
            'hl.bind("SUPER + Q", hl.dsp.exec_cmd("killactive"), { repeating = true })',
            'hl.bind("SUPER + F", hl.dsp.global("caelestia:lock"), { locked = true })',
        ]),
    )

    binds = keybinds._parse_managed_binds(text)
    assert len(binds) == 3
    assert binds[0]["key_raw"] == "T"
    assert binds[0]["dispatcher"] == "exec"
    assert binds[0]["argument"] == "foot"
    assert binds[0]["bind_type"] == "bind"
    assert binds[1]["bind_type"] == "binde"
    assert binds[2]["bind_type"] == "bindl"


def test_config_binds_and_caelestia_variables(monkeypatch, tmp_path):
    user_lua = tmp_path / "hypr-user.lua"
    user_lua.write_text(
        """local config = {}

config.binds = {
    { "SUPER", "K", "exec", "hyprctl switchkblayout current next" },
}

return config
"""
    )
    monkeypatch.setattr(keybinds, "HYPR_USER_LUA", user_lua)

    binds = keybinds.parse_keybinds()
    assert len(binds) == 1
    assert binds[0]["source"] == "config"
    assert binds[0]["argument"] == "hyprctl switchkblayout current next"


def test_write_managed_binds_uses_backup(monkeypatch, tmp_path):
    user_lua = tmp_path / "hypr-user.lua"
    user_lua.write_text("local config = {}\n\nreturn config\n")
    monkeypatch.setattr(keybinds, "HYPR_USER_LUA", user_lua)
    monkeypatch.setattr(
        keybinds.apply, "write_and_reload", lambda path, text, **kwargs: path.write_text(text)
    )

    keybinds._write_managed_binds([
        {
            "modifier_raw": "SUPER",
            "key_raw": "T",
            "dispatcher": "exec",
            "argument": "foot",
            "bind_type": "bind",
        }
    ])

    written = user_lua.read_text()
    assert 'hl.bind("SUPER + T", hl.dsp.exec_cmd("foot"))' in written
    assert "BEGIN Caelestia Settings: custom keybinds" in written
    assert written.index("BEGIN Caelestia Settings") < written.index("return config")


def test_type_and_flags_roundtrip():
    for bind_type in ("bind", "binde", "bindl", "bindle", "bindr", "bindm"):
        flags = keybinds._type_to_flags(bind_type)
        assert keybinds._flags_to_type(flags) == bind_type
