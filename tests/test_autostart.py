from src.pages.autostart import build_block, parse_commands, write_commands


def test_parse_autostart_commands():
    text = (
        "local config = {}\n\n"
        "-- BEGIN Caelestia Settings: autostart\n"
        'hl.on("hyprland.start", function()\n'
        '    hl.exec_cmd("caelestia shell -d")\n'
        '    hl.exec_cmd("hyprpaper")\n'
        "end)\n"
        "-- END Caelestia Settings: autostart\n\n"
        "return config\n"
    )
    assert parse_commands(text) == ["caelestia shell -d", "hyprpaper"]


def test_write_autostart_roundtrip():
    text = "local config = {}\n\nreturn config\n"
    written = write_commands(text, ["foot --server", "nm-applet"])
    assert 'hl.exec_cmd("foot --server")' in written
    assert 'hl.exec_cmd("nm-applet")' in written
    assert written.index("BEGIN Caelestia Settings: autostart") < written.index("return config")
    assert parse_commands(written) == ["foot --server", "nm-applet"]


def test_remove_autostart_block():
    text = (
        "local config = {}\n\n"
        "-- BEGIN Caelestia Settings: autostart\n"
        + build_block(["one"])
        + "\n-- END Caelestia Settings: autostart\n\nreturn config\n"
    )
    written = write_commands(text, [])
    assert "BEGIN Caelestia Settings: autostart" not in written
    assert written.strip().startswith("local config")
    assert "hl.exec_cmd" not in written
