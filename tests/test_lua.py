from src import lua


def test_parse_nested_table():
    text = 'hl.monitor({ output = "eDP-1", scale = 1.25, touchpad = { tap = true } })'
    calls = lua.iter_calls(text, {"hl.monitor"})
    assert len(calls) == 1
    table = calls[0].table
    assert table["output"] == "eDP-1"
    assert table["scale"] == 1.25
    assert table["touchpad"] == {"tap": True}


def test_parse_array_table():
    text = 'config.binds = { { "SUPER", "K", "exec", "cmd" }, { "ALT", "T" } }'
    values, _ = lua.parse_table(text, text.index("{"))
    assert values == [["SUPER", "K", "exec", "cmd"], ["ALT", "T"]]


def test_iter_calls_skips_commented_lines():
    text = """
hl.bind("SUPER + T", hl.dsp.exec_cmd("foot"))
-- hl.bind("SUPER + X", hl.dsp.exec_cmd("rm -rf /"))
"""
    calls = lua.iter_calls(text, {"hl.bind"})
    assert len(calls) == 1
    assert "SUPER + T" in calls[0].args


def test_read_values_and_update_roundtrip():
    text = """local scheme = require("scheme.current")

return {
    terminal = "foot",
    windowOpacity = 0.9,
    shadowColour = "rgba(" .. scheme.inversePrimary .. "10)",
}
"""
    values = lua.read_table_values(text)
    assert values["terminal"] == "foot"
    assert values["windowOpacity"] == 0.9
    assert values["shadowColour"].startswith('"rgba("')

    updated = lua.set_table_values(text, {"terminal": "kitty", "browser": "firefox"})
    assert 'terminal = "kitty"' in updated
    assert 'browser = "firefox"' in updated
    # Untouched concatenated expression survives.
    assert "scheme.inversePrimary" in updated

    removed = lua.remove_table_values(updated, ["browser"])
    assert "browser" not in removed
    assert 'terminal = "kitty"' in removed


def test_managed_block_replace_and_remove():
    text = "local config = {}\n\nreturn config\n"
    block = lua.replace_managed_block(text, "window rules", 'hl.window_rule({ match = { class = "x" }, float = true })')
    assert "BEGIN Caelestia Settings: window rules" in block
    assert block.index("BEGIN Caelestia Settings") < block.index("return config")

    replaced = lua.replace_managed_block(block, "window rules", 'hl.window_rule({ match = { class = "y" } })')
    assert 'class = "x"' not in replaced
    assert 'class = "y"' in replaced
    assert replaced.count("BEGIN Caelestia Settings: window rules") == 1

    removed = lua.remove_managed_block(replaced, "window rules")
    assert "Caelestia Settings" not in removed
    assert removed.strip() == "local config = {}\n\nreturn config"


def test_managed_block_inserts_before_plain_return():
    text = "return {}\n"
    block = lua.replace_managed_block(text, "input", 'hl.config({ input = { kb_layout = "us" } })')
    assert block.index("BEGIN Caelestia Settings") < block.index("return {}")


def test_format_key_with_dash():
    rendered = lua.format_value({"tap-to-click": True})
    assert '["tap-to-click"] = true' in rendered
