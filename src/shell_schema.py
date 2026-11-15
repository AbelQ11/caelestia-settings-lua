"""Caelestia ``shell.json`` schema and labels.

The defaults are generated from the upstream shell README by
``scripts/gen_shell_schema.py`` and committed as ``src/data/shell_schema.json``.
This module turns that tree into a flat, UI-friendly option list.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("data") / "shell_schema.json"

SECTION_META: dict[str, tuple[str, str, str]] = {
    "general": (
        "General",
        "Shell behaviour, logo, default applications, idle and battery settings.",
        "preferences-system-symbolic",
    ),
    "appearance": (
        "Appearance",
        "Scaling, fonts, rounding, spacing, padding, animations and transparency.",
        "applications-graphics-symbolic",
    ),
    "background": (
        "Background",
        "Wallpaper, desktop clock and audio visualiser.",
        "preferences-desktop-wallpaper-symbolic",
    ),
    "bar": (
        "Bar",
        "Top bar layout, workspaces, clock, tray, status icons and popouts.",
        "preferences-desktop-display-symbolic",
    ),
    "border": (
        "Borders",
        "Hyprland border integration for the shell panels.",
        "preferences-desktop-theme-symbolic",
    ),
    "dashboard": (
        "Dashboard",
        "Dashboard visibility and performance widgets.",
        "speedometer-symbolic",
    ),
    "launcher": (
        "Launcher",
        "Launcher behaviour, actions, favourites and fuzzy search.",
        "system-search-symbolic",
    ),
    "lock": (
        "Lock screen",
        "Lock screen background, logo, fingerprint, Howdy and session controls.",
        "system-lock-screen-symbolic",
    ),
    "nexus": (
        "Control centre",
        "Caelestia Nexus settings (wallpaper grid, network scanning).",
        "preferences-system-network-symbolic",
    ),
    "notifs": (
        "Notifications",
        "Expiry, fullscreen behaviour, grouping and interaction.",
        "preferences-system-notifications-symbolic",
    ),
    "osd": (
        "On-screen display",
        "Volume, brightness and microphone OSDs.",
        "video-display-symbolic",
    ),
    "services": (
        "Services",
        "Weather, units, clock format, media player, lyrics and volume steps.",
        "applications-system-symbolic",
    ),
    "session": (
        "Session",
        "Logout, shutdown, reboot and hibernate behaviour.",
        "system-shutdown-symbolic",
    ),
    "sidebar": (
        "Sidebar",
        "Sidebar visibility, hover behaviour and drag threshold.",
        "sidebar-show-symbolic",
    ),
    "utilities": (
        "Utilities",
        "Toasts, utility cards, quick toggles and VPN.",
        "applications-utilities-symbolic",
    ),
    "paths": (
        "Paths",
        "Wallpaper folder, lyrics folder and GIF/profile images.",
        "folder-symbolic",
    ),
}

SECTION_ORDER = [
    "general", "appearance", "background", "bar", "border", "dashboard",
    "launcher", "lock", "nexus", "notifs", "osd", "services", "session",
    "sidebar", "utilities", "paths",
]

SUBGROUP_TITLES = {
    "appearance.font": "Fonts",
    "appearance.font.headline": "Headline font",
    "appearance.font.title": "Title font",
    "appearance.font.body": "Body font",
    "appearance.font.label": "Label font",
    "appearance.font.mono": "Monospace font",
    "appearance.font.icon": "Icon font",
    "appearance.anim": "Animations",
    "appearance.anim.durations": "Animation durations",
    "appearance.anim.curves": "Animation curves",
    "appearance.transparency": "Transparency",
    "appearance.rounding": "Rounding",
    "appearance.spacing": "Spacing",
    "appearance.padding": "Padding",
    "background.desktopClock": "Desktop clock",
    "background.visualiser": "Audio visualiser",
    "bar.workspaces": "Workspaces",
    "bar.activeWindow": "Active window",
    "bar.statusIcons": "Status icons",
    "bar.entries": "Bar entries",
    "bar.tray": "System tray",
    "bar.clock": "Clock",
    "bar.popouts": "Popouts",
    "bar.scrollActions": "Scroll actions",
    "general.apps": "Default applications",
    "general.idle": "Idle",
    "general.battery": "Battery",
    "launcher.useFuzzy": "Fuzzy search",
    "session.commands": "Commands",
    "session.icons": "Icons",
    "utilities.toasts": "Toasts",
    "utilities.cards": "Utility cards",
    "utilities.vpn": "VPN",
    "utilities.quickToggles": "Quick toggles",
}

LABEL_OVERRIDES = {
    "enabled": "Shell enabled",
    "appearance.deformScale": "Deformation scale",
    "appearance.font.clock": "Clock font",
    "appearance.font.workspaces": "Workspaces font",
    "appearance.transparency.base": "Base transparency",
    "appearance.transparency.layers": "Layer transparency",
    "background.wallpaperEnabled": "Wallpaper enabled",
    "bar.excludedScreens": "Excluded screens",
    "bar.statusIcons": "Status icons",
    "bar.entries": "Bar entries",
    "general.logo": "Logo",
    "general.mediaGifSpeedAdjustment": "Media GIF speed",
    "general.sessionGifSpeed": "Session GIF speed",
    "general.apps.terminal": "Terminal",
    "general.apps.audio": "Audio settings",
    "general.apps.playback": "Media player",
    "general.apps.explorer": "File manager",
    "general.idle.lockBeforeSleep": "Lock before sleep",
    "general.idle.inhibitWhenAudio": "Inhibit idle when audio plays",
    "general.idle.inhibitWhenCharging": "Inhibit idle while charging",
    "general.battery.criticalLevel": "Critical battery level",
    "general.battery.warnLevels": "Battery warning levels",
    "general.idle.timeouts": "Idle timeouts",
    "launcher.specialPrefix": "Special command prefix",
    "launcher.actionPrefix": "Action prefix",
    "launcher.enableDangerousActions": "Enable dangerous actions",
    "launcher.maxShown": "Maximum results",
    "launcher.maxWallpapers": "Maximum wallpapers",
    "launcher.favouriteApps": "Favourite apps",
    "launcher.hiddenApps": "Hidden apps",
    "launcher.actions": "Launcher actions",
    "launcher.vimKeybinds": "Vim keybinds",
    "lock.enableFprint": "Fingerprint unlock",
    "lock.maxFprintTries": "Fingerprint attempts",
    "lock.enableHowdy": "Howdy face unlock",
    "lock.maxHowdyTries": "Howdy attempts",
    "lock.triggerHowdyOnWake": "Trigger Howdy on wake",
    "lock.useWallpaper": "Use wallpaper on lock screen",
    "lock.recolourLogo": "Recolour logo",
    "lock.hideNotifs": "Hide notifications",
    "notifs.defaultExpireTimeout": "Default timeout (ms)",
    "notifs.fullscreenExpireTimeout": "Fullscreen timeout (ms)",
    "notifs.clearThreshold": "Clear threshold",
    "notifs.expandThreshold": "Expand threshold",
    "notifs.groupPreviewNum": "Group preview count",
    "notifs.openExpanded": "Open expanded",
    "notifs.actionOnClick": "Action on click",
    "osd.hideDelay": "Hide delay (ms)",
    "services.weatherLocation": "Weather location",
    "services.weatherUnits": "Weather units",
    "services.sensorUnits": "Sensor units",
    "services.dataUnits": "Data units",
    "services.clockFormat": "Clock format",
    "services.gpuType": "GPU type",
    "services.visualiserBars": "Visualiser bars",
    "services.audioIncrement": "Audio step",
    "services.brightnessIncrement": "Brightness step",
    "services.maxVolume": "Maximum volume",
    "services.smartScheme": "Smart scheme",
    "services.defaultPlayer": "Default player",
    "services.playerAliases": "Player aliases",
    "services.lyricsBackend": "Lyrics backend",
    "session.commands.logout": "Logout command",
    "session.commands.shutdown": "Shutdown command",
    "session.commands.hibernate": "Hibernate command",
    "session.commands.reboot": "Reboot command",
    "sidebar.minHoverThreshold": "Minimum hover threshold",
    "utilities.maxToasts": "Maximum toasts",
    "utilities.toasts.fullscreen": "Toasts over fullscreen",
    "utilities.vpn.selectedProvider": "Selected VPN provider",
    "paths.wallpaperDir": "Wallpaper directory",
    "paths.lyricsDir": "Lyrics directory",
    "paths.sessionGif": "Session GIF",
    "paths.mediaGif": "Media GIF",
    "paths.noNotifsPic": "No notifications image",
    "paths.lockNoNotifsPic": "Lock no notifications image",
    "nexus.wallpapersPerRow": "Wallpapers per row",
    "nexus.maxNetworksShown": "Maximum networks shown",
    "nexus.networkRescanInterval": "Network rescan interval (ms)",
    "dashboard.mediaUpdateInterval": "Media update interval (ms)",
    "dashboard.resourceUpdateInterval": "Resource update interval (ms)",
    "bar.workspaces.ignoredTags": "Ignored tags",
    "bar.workspaces.specialWorkspaceIcons": "Special workspace icons",
    "bar.workspaces.workspaceIcons": "Workspace icons",
    "bar.workspaces.windowIcons": "Window icons",
    "bar.workspaces.label": "Inactive label",
    "bar.workspaces.occupiedLabel": "Occupied label",
    "bar.workspaces.activeLabel": "Active label",
    "bar.workspaces.capitalisation": "Capitalisation",
    "bar.workspaces.displayType": "Display type",
    "bar.workspaces.specialDisplayType": "Special display type",
    "bar.workspaces.maxWindowIcons": "Maximum window icons",
    "bar.workspaces.activeTrail": "Active trail",
    "bar.workspaces.perMonitor": "Per monitor",
    "bar.workspaces.showWindowsOnSpecialWorkspaces": "Windows on special workspaces",
    "bar.tray.hiddenIcons": "Hidden tray icons",
    "bar.tray.iconSubs": "Tray icon substitutions",
    "bar.tray.recolour": "Recolour tray icons",
    "bar.activeWindow.showOnHover": "Show on hover",
    "bar.showOnHover": "Show on hover",
    "bar.dragThreshold": "Drag threshold",
    "bar.clock.showSeconds": "Show seconds",
    "bar.clock.showDate": "Show date",
    "bar.clock.showIcon": "Show icon",
    "bar.clock.background": "Clock background",
    "border.minThickness": "Minimum thickness",
    "border.clampedThickness": "Clamped thickness",
    "appearance.transparency.enabled": "Transparency enabled",
    "appearance.font.scale": "Font scale",
    "appearance.rounding.scale": "Rounding scale",
    "appearance.spacing.scale": "Spacing scale",
    "appearance.padding.scale": "Padding scale",
    "appearance.anim.durations.scale": "Duration scale",
    "appearance.font.headline.family": "Family",
    "appearance.font.title.family": "Family",
    "appearance.font.body.family": "Family",
    "appearance.font.label.family": "Family",
    "appearance.font.mono.family": "Family",
    "appearance.font.icon.family": "Family",
}

_ACRONYMS = {
    "api": "API", "cpu": "CPU", "dnd": "DND", "fps": "FPS", "gif": "GIF",
    "gpu": "GPU", "hdr": "HDR", "id": "ID", "kb": "Keyboard", "osd": "OSD",
    "pfp": "Profile picture", "ui": "UI", "url": "URL", "vpn": "VPN",
    "vrr": "VRR", "ws": "Workspace",
}


@dataclass(frozen=True)
class Option:
    path: str
    kind: str
    default: Any
    section: str
    subgroup: str | None
    label: str
    enum: str | None = None
    global_only: bool = False


def _humanize(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").strip()
    words = []
    for word in text.split():
        words.append(_ACRONYMS.get(word.lower(), word))
    result = " ".join(words)
    if not result:
        return text
    return result[0].upper() + result[1:]


def _split_path(path: str) -> list[str]:
    return path.split(".")


def _section(path: str) -> str:
    first = _split_path(path)[0]
    return "general" if first == "enabled" else first


LIST_GROUPS = {
    "bar.entries",
    "bar.statusIcons",
    "bar.excludedScreens",
    "launcher.actions",
    "launcher.favouriteApps",
    "launcher.hiddenApps",
}


def _subgroup(path: str) -> str | None:
    parts = _split_path(path)
    if parts[0] == "enabled":
        return None
    if path in LIST_GROUPS:
        return parts[-1]
    if len(parts) <= 2:
        return None
    # Keep the font families/animation groups separate for readability.
    if parts[0] == "appearance" and parts[1] in ("font", "anim"):
        if parts[1] == "anim" and len(parts) > 3:
            return "anim.durations"
        if parts[1] == "font" and len(parts) > 3:
            return f"font.{parts[2]}"
        return parts[1]
    return parts[1]


def _label(path: str) -> str:
    if path in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[path]
    parts = _split_path(path)
    if parts[0] == "enabled":
        return "Shell enabled"
    group = _subgroup(path)
    if group is None:
        return _humanize(parts[-1])
    group_parts = group.split(".")
    consumed = 1 + len(group_parts)
    tail = parts[consumed:]
    if not tail:
        return _humanize(group_parts[-1])
    return " · ".join(_humanize(part) for part in tail)


def group_title(section: str, subgroup: str | None) -> str:
    if subgroup is None:
        return SECTION_META.get(section, (section.title(), "", ""))[0]
    key = f"{section}.{subgroup}"
    if key in SUBGROUP_TITLES:
        return SUBGROUP_TITLES[key]
    return _humanize(subgroup.split(".")[-1])


def section_meta(section: str) -> tuple[str, str, str]:
    return SECTION_META.get(section, (section.title(), "", "preferences-system-symbolic"))


@lru_cache(maxsize=1)
def _load() -> dict:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def source_tag() -> str:
    return _load().get("tag", "?")


def defaults() -> dict:
    return _load()["defaults"]


def enums() -> dict[str, list[str]]:
    return _load()["enums"]


def enum_paths() -> dict[str, str]:
    return _load()["enum_paths"]


def global_only_prefixes() -> list[str]:
    return _load()["global_only"]


def is_global_only(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in global_only_prefixes())


def default_value(path: str) -> Any:
    node: Any = defaults()
    for part in _split_path(path):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@lru_cache(maxsize=1)
def options() -> tuple[Option, ...]:
    kinds = _load()["kinds"]
    enum_paths_map = enum_paths()
    result = []
    for path, kind in kinds.items():
        enum_name = enum_paths_map.get(path)
        result.append(
            Option(
                path=path,
                kind=kind,
                default=default_value(path),
                section=_section(path),
                subgroup=_subgroup(path),
                label=_label(path),
                enum=enum_name,
                global_only=is_global_only(path),
            )
        )
    result.sort(key=lambda option: (SECTION_ORDER.index(option.section) if option.section in SECTION_ORDER else 99,
                                    option.subgroup or "", option.label.lower()))
    return tuple(result)


def option_map() -> dict[str, Option]:
    return {option.path: option for option in options()}


def sections() -> list[str]:
    present = {option.section for option in options()}
    return [section for section in SECTION_ORDER if section in present]


def options_for_section(section: str) -> list[Option]:
    return [option for option in options() if option.section == section]
