from src import shell_schema


def test_schema_has_every_option():
    options = shell_schema.options()
    assert len(options) == 279
    assert len(shell_schema.sections()) == 16
    assert {option.kind for option in options} >= {
        "bool", "int", "float", "str", "enum", "strlist", "objlist"
    }


def test_defaults_and_enums():
    assert shell_schema.default_value("bar.persistent") is True
    assert shell_schema.default_value("background.desktopClock.enabled") is False
    option = shell_schema.option_map()["bar.workspaces.displayType"]
    assert option.enum == "BarWorkspaceDisplay"
    assert shell_schema.enums()["BarWorkspaceDisplay"] == ["Shapes", "Text", "Icons"]


def test_global_only_prefixes():
    assert shell_schema.is_global_only("services.clockFormat") is True
    assert shell_schema.is_global_only("paths.wallpaperDir") is True
    assert shell_schema.is_global_only("bar.persistent") is False
    assert shell_schema.is_global_only("background.desktopClock.enabled") is False


def test_labels_are_readable():
    options = shell_schema.option_map()
    assert options["bar.workspaces.displayType"].label == "Display type"
    assert options["general.apps.terminal"].label == "Terminal"
    assert options["services.gpuType"].label == "GPU type"
    assert options["paths.wallpaperDir"].label == "Wallpaper directory"
    assert options["enabled"].label == "Shell enabled"
