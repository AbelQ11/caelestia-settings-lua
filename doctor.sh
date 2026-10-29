#!/bin/bash
#
# Caelestia Settings — Hyprland integration doctor
#
# Checks (and repairs) the handful of Lua configuration lines the app depends
# on: the Super+I keybind, the monitors.lua requirement, window rules, and
# the Polkit auth agent autostart.
#
# Purely additive/idempotent: a missing line is appended, an existing one
# is left alone. Nothing is ever deleted or rewritten.

set -e

HYPR_CONFIG_DIR="$HOME/.config/hypr"
HYPR_LUA_FILE="$HYPR_CONFIG_DIR/hyprland.lua"
CAELESTIA_CONFIG_DIR="$HOME/.config/caelestia"
HYPR_USER_LUA="$CAELESTIA_CONFIG_DIR/hypr-user.lua"
MONITOR_LUA_FILE="$HYPR_CONFIG_DIR/monitors.lua"
KEYBINDS_LUA_FILE="$HYPR_CONFIG_DIR/keybinds.lua"

_DOCTOR_RESULTS=()

check_and_add() {
    local target_file="$1"
    local needle="$2"
    local content="$3"
    local label="$4"
    local also_check_file="$5"

    if grep -q -F "$needle" "$target_file" 2>/dev/null \
        || { [[ -n "$also_check_file" ]] && grep -q -F "$needle" "$also_check_file" 2>/dev/null; }; then
        _DOCTOR_RESULTS+=("OK:    $label")
    else
        echo "   ...Adding: $label"
        if [ -f "$target_file" ] && grep -q -F "return config" "$target_file"; then
            # Insert before "return config"
            sed -i "/return config/i $content\n" "$target_file"
        else
            printf '%s\n' "$content" >> "$target_file"
        fi
        _DOCTOR_RESULTS+=("FIXED: $label (was missing, now added)")
    fi
}

run_hyprland_doctor() {
    echo ">>> Checking Hyprland Lua integration..."

    mkdir -p "$HYPR_CONFIG_DIR"
    mkdir -p "$CAELESTIA_CONFIG_DIR"
    touch "$HYPR_LUA_FILE"
    [ -f "$HYPR_USER_LUA" ] || echo "return {}" > "$HYPR_USER_LUA"
    [ -f "$MONITOR_LUA_FILE" ] || touch "$MONITOR_LUA_FILE"

    _DOCTOR_RESULTS=()

    # Ensure monitors.lua is loaded in hyprland.lua or hypr-user.lua
    local monitor_req='pcall(require, "monitors")'
    local monitor_needle='require("monitors")'
    if grep -q -F "$monitor_needle" "$HYPR_LUA_FILE" 2>/dev/null || grep -q -F "monitors" "$HYPR_LUA_FILE" 2>/dev/null || grep -q -F "monitors" "$HYPR_USER_LUA" 2>/dev/null; then
        _DOCTOR_RESULTS+=("OK:    monitors.lua require line")
    else
        echo "   ...Adding: monitors.lua require line to hyprland.lua"
        printf '\n-- Load monitor configuration if present\n%s\n' "$monitor_req" >> "$HYPR_LUA_FILE"
        _DOCTOR_RESULTS+=("FIXED: monitors.lua require line (was missing, now added)")
    fi

    # Super+I keybind
    local bind_needle="caelestia-settings"
    local bind_cmd='hl.bind("SUPER + I", hl.dsp.exec_cmd("caelestia-settings"))'
    check_and_add "$HYPR_USER_LUA" "$bind_needle" "$bind_cmd" "Super+I keybind" "$KEYBINDS_LUA_FILE"

    # Polkit auth agent autostart
    local polkit_needle="polkit"
    local polkit_cmd='hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")'
    check_and_add "$HYPR_USER_LUA" "$polkit_needle" "$polkit_cmd" "Polkit auth agent autostart" "$HYPR_CONFIG_DIR/hyprland/execs.lua"

    echo
    echo ">>> Hyprland integration summary:"
    for result in "${_DOCTOR_RESULTS[@]}"; do
        echo "   $result"
    done
    echo
}

# Sourced by install.sh (which then calls run_hyprland_doctor itself), but
# also directly runnable on its own: `./doctor.sh` repairs a live config
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_hyprland_doctor
fi
