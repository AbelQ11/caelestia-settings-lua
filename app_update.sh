#!/bin/bash
# Caelestia Settings — App Updater
set -e

# First argument is the PID of the running Python app
APP_PID=$1

# --- CONFIGURATION ---
GIT_REPO_URL="https://github.com/AbelQ11/caelestia-settings-lua.git"
GIT_BRANCH="${CAELESTIA_SETTINGS_BRANCH:-}"
TEMP_DIR="/tmp/caelestia-settings-update"
API_URL="https://api.github.com/repos/AbelQ11/caelestia-settings-lua/releases/latest"

if [ -z "$GIT_BRANCH" ]; then
    GIT_BRANCH=$(python3 - "$API_URL" <<'PY' 2>/dev/null || true
import json
import sys
import urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=8) as response:
        print(json.load(response).get("tag_name", ""))
except Exception:
    pass
PY
)
fi
if [ -z "$GIT_BRANCH" ]; then
    GIT_BRANCH="dev"
    echo "No release tag found; falling back to the dev branch."
fi

echo "#######################################"
echo "###   Caelestia App Updater         ###"
echo "#######################################"
echo

# --- STEP 0: Stop the running app ---
if [ -n "$APP_PID" ]; then
    echo ">>> Stopping running app (PID: $APP_PID) for a clean update..."
    kill "$APP_PID" 2>/dev/null || true
    sleep 1
    echo "   ...App stopped."
    echo
fi

echo ">>> [1/3] Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo ">>> [2/3] Downloading latest version from Git..."
echo "Repo: $GIT_REPO_URL (tag/branch: $GIT_BRANCH)"
if git clone --depth 1 --branch "$GIT_BRANCH" --single-branch "$GIT_REPO_URL" "$TEMP_DIR"; then
    echo "   ...Download successful."
else
    echo
    echo "ERROR: Git clone failed."
    echo "Please check your internet connection or GitHub server status."
    echo "Press Enter to exit."
    read
    exit 1
fi

echo ">>> [3/3] Running installer for the new version..."
echo
cd "$TEMP_DIR"

# install.sh sources doctor.sh and runs the Hyprland integration checks
# itself, so no separate doctor.sh call is needed here.
if [ -f "install.sh" ]; then
    chmod +x install.sh
    ./install.sh
else
    echo "ERROR: 'install.sh' not found in the downloaded repository!"
    echo "Press Enter to exit."
    read
    exit 1
fi

echo
echo "#######################################"
echo "   Update completed successfully!"
echo "#######################################"
echo "You can now restart the app."
echo
echo "Press Enter to close."
read