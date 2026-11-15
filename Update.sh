#!/usr/bin/env bash
# Caelestia Settings — system update helper
set -e

echo "### UPDATE ###"
echo ">>> [1/2] Updating system and Caelestia dots..."
if command -v caelestia >/dev/null 2>&1; then
    caelestia update
elif command -v yay >/dev/null 2>&1; then
    yay -Syu
else
    sudo pacman -Syu
fi

echo ">>> [2/2] Restarting audio services..."
systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service

if [[ "$1" == "-r" ]]; then
    echo "!!! Reboot in 15 seconds !!!"
    sleep 15
    sudo reboot
fi
