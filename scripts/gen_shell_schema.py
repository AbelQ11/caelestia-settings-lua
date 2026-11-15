#!/usr/bin/env python3
"""Generate ``src/data/shell_schema.json`` from the upstream Caelestia shell.

The Caelestia shell documents every ``shell.json`` option in the "Example
config" block of its README.  That block is the authoritative list of defaults
for a given release.  This script extracts it, adds the enum values from the
installed QML type information (or a built-in fallback), records which options
are global-only (per the upstream README), and writes the result next to the
app so the settings UI can be built without network access.

Usage::

    python scripts/gen_shell_schema.py --tag v2.5.0
    python scripts/gen_shell_schema.py --readme path/to/README.md

Re-run it when updating Caelestia.  Unknown keys already present in a user's
``shell.json`` are preserved by the app; only the defaults/schema come from
here.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

REPO = "caelestia-dots/shell"
DEFAULT_TAG = "v2.5.0"
OUT_PATH = Path(__file__).resolve().parents[1] / "src" / "data" / "shell_schema.json"
QMLTYPES = Path("/usr/lib/qt6/qml/Caelestia/Config/caelestia-config.qmltypes")

# Options that the shell only reads from the global shell.json (upstream README).
GLOBAL_ONLY = [
    "appearance.anim.",
    "appearance.transparency.",
    "bar.tray.hiddenIcons",
    "bar.tray.iconSubs",
    "bar.workspaces.ignoredTags",
    "bar.workspaces.specialWorkspaceIcons",
    "bar.workspaces.windowIcons",
    "bar.workspaces.workspaceIcons",
    "dashboard.mediaUpdateInterval",
    "dashboard.resourceUpdateInterval",
    "general.apps.",
    "general.battery.",
    "general.idle.",
    "general.logo",
    "launcher.actionPrefix",
    "launcher.actions",
    "launcher.enableDangerousActions",
    "launcher.favouriteApps",
    "launcher.hiddenApps",
    "launcher.specialPrefix",
    "launcher.useFuzzy.",
    "launcher.vimKeybinds",
    "lock.enableFprint",
    "lock.enableHowdy",
    "lock.maxFprintTries",
    "lock.maxHowdyTries",
    "lock.triggerHowdyOnWake",
    "nexus.networkRescanInterval",
    "notifs.actionOnClick",
    "notifs.defaultExpireTimeout",
    "notifs.expire",
    "notifs.fullscreen",
    "notifs.fullscreenExpireTimeout",
    "paths.lyricsDir",
    "paths.wallpaperDir",
    "services.audioIncrement",
    "services.brightnessIncrement",
    "services.clockFormat",
    "services.dataUnits",
    "services.defaultPlayer",
    "services.gpuType",
    "services.lyricsBackend",
    "services.maxVolume",
    "services.playerAliases",
    "services.sensorUnits",
    "services.smartScheme",
    "services.visualiserBars",
    "services.weatherLocation",
    "services.weatherUnits",
    "utilities.toasts.",
    "utilities.vpn.",
]

# Empty lists cannot be typed from their default alone.
EMPTY_LIST_KINDS = {
    "bar.excludedScreens": "strlist",
    "bar.tray.hiddenIcons": "strlist",
    "bar.tray.iconSubs": "objlist",
    "bar.workspaces.workspaceIcons": "objlist",
    "launcher.favouriteApps": "strlist",
    "launcher.hiddenApps": "strlist",
    "utilities.vpn.providers": "objlist",
}

# String options whose value is one of a fixed set.
ENUM_PATHS = {
    "bar.workspaces.capitalisation": "BarWorkspaceCapitalisation",
    "bar.workspaces.displayType": "BarWorkspaceDisplay",
    "bar.workspaces.specialDisplayType": "BarWorkspaceDisplay",
    "services.clockFormat": "ClockFormat",
    "services.dataUnits": "DataUnit",
    "services.gpuType": "GpuType",
    "services.lyricsBackend": "LyricsBackend",
    "services.sensorUnits": "TemperatureUnit",
    "services.weatherUnits": "TemperatureUnit",
    "notifs.fullscreen": "NotifsFullscreen",
    "utilities.toasts.fullscreen": "NotifsFullscreen",
}

FALLBACK_ENUMS = {
    "BarWorkspaceCapitalisation": ["Preserve", "Upper", "Lower"],
    "BarWorkspaceDisplay": ["Shapes", "Text", "Icons"],
    "ClockFormat": ["Auto", "TwelveHour", "TwentyFourHour"],
    "DataUnit": ["Binary", "Decimal"],
    "GpuType": ["Auto", "Nvidia", "Generic", "None"],
    "LyricsBackend": ["Auto", "Local", "LRCLIB", "NetEase"],
    "NotifsFullscreen": ["On", "Off"],
    "TemperatureUnit": ["Auto", "Celsius", "Fahrenheit", "Kelvin"],
}


def fetch_readme(tag: str) -> str:
    url = f"https://raw.githubusercontent.com/{REPO}/{tag}/README.md"
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def extract_defaults(readme: str) -> dict:
    start = readme.index("<details><summary>Example config</summary>")
    fence = readme.index("```json", start)
    end = readme.index("```", fence + 7)
    return json.loads(readme[fence + 7:end].strip())


def read_enums() -> dict[str, list[str]]:
    if not QMLTYPES.exists():
        return dict(FALLBACK_ENUMS)
    text = QMLTYPES.read_text(encoding="utf-8", errors="replace")
    enums = dict(FALLBACK_ENUMS)
    for component in re.split(r"\n    Component \{", text):
        for match in re.finditer(
            r'Enum \{\s*\n\s*name: "(\w+)".*?values: \[(.*?)\]', component, re.S
        ):
            values = re.findall(r'"([^"]+)"', match.group(2))
            if values:
                enums[match.group(1)] = values
    return enums


def infer_kind(path: str, value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "enum" if path in ENUM_PATHS else "str"
    if isinstance(value, list):
        if not value:
            return EMPTY_LIST_KINDS.get(path, "strlist")
        return "objlist" if any(isinstance(item, dict) for item in value) else "strlist"
    return "str"


def flatten(value: dict, prefix: str = "") -> dict[str, str]:
    result = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict) and item:
            result.update(flatten(item, path))
        else:
            result[path] = infer_kind(path, item)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--readme", type=Path)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    if args.readme:
        readme = args.readme.read_text(encoding="utf-8")
        source = str(args.readme)
    else:
        readme = fetch_readme(args.tag)
        source = f"https://github.com/{REPO}/blob/{args.tag}/README.md"

    defaults = extract_defaults(readme)
    enums = read_enums()
    kinds = flatten(defaults)

    schema = {
        "source": source,
        "tag": args.tag,
        "defaults": defaults,
        "kinds": kinds,
        "enums": enums,
        "enum_paths": {path: name for path, name in ENUM_PATHS.items() if path in kinds},
        "global_only": GLOBAL_ONLY,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(kinds)} options, {len(enums)} enums)")


if __name__ == "__main__":
    main()
