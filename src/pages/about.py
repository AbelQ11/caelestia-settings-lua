import json
import os
import shutil
import subprocess
from pathlib import Path

from gi.repository import Adw, Gtk

from src.config import APP_DATA_DIR
from src.lang import t


def _terminal_command(script: str, pid: str) -> list[str]:
    """Build a terminal command, trying the common Wayland terminals."""

    for terminal in ("xdg-terminal-exec", "foot", "kitty", "alacritty", "wezterm"):
        if shutil.which(terminal):
            if terminal == "xdg-terminal-exec":
                return [terminal, script, pid]
            if terminal == "wezterm":
                return [terminal, "start", "--", script, pid]
            return [terminal, "-e", script, pid]
    return [script, pid]

class AboutPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.win = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = APP_DATA_DIR / "manifest.json"
        if not manifest_path.exists():
            manifest_path = repo_root / "manifest.json"
        self.update_script = APP_DATA_DIR / "app_update.sh"
        if not self.update_script.exists():
            self.update_script = repo_root / "app_update.sh"
        self.uninstall_script = APP_DATA_DIR / "uninstall.sh"
        if not self.uninstall_script.exists():
            self.uninstall_script = repo_root / "uninstall.sh"

        info = {
            "name": "Caelestia Settings",
            "version": "?",
            "author": "?",
            "description": t("Manifest missing"),
        }

        try:
            if manifest_path.exists():
                with manifest_path.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                    info.update(data)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not read manifest: {exc}")

        # Exposed so MainWindow's background update check can compare against
        # it without re-reading/re-parsing manifest.json itself.
        self.local_version = info["version"]

        # Info Group
        info_group = Adw.PreferencesGroup()
        self.append(info_group)
        
        info_group.add(Adw.ActionRow(title=t("Version"), subtitle=info["version"]))
        info_group.add(Adw.ActionRow(title=t("Author"), subtitle=info["author"]))
        info_group.add(
            Adw.ActionRow(title=t("Description"), subtitle=info.get("description", ""))
        )

        # App Mgmt Group
        update_group = Adw.PreferencesGroup(title=t("App Management"))
        self.append(update_group)

        update_row = Adw.ActionRow(title=t("Update App"), subtitle=t("Downloads latest version..."))
        update_btn = Gtk.Button(label=t("Check for Updates"))
        update_btn.add_css_class("suggested-action")
        update_btn.connect("clicked", self.on_update_clicked)
        
        update_row.add_suffix(update_btn)
        update_group.add(update_row)

        uninstall_row = Adw.ActionRow(title=t("Uninstall App"), subtitle=t("Removes the app and its Hyprland integration..."))
        uninstall_btn = Gtk.Button(label=t("Uninstall"))
        uninstall_btn.add_css_class("destructive-action")
        uninstall_btn.connect("clicked", self.on_uninstall_clicked)

        uninstall_row.add_suffix(uninstall_btn)
        update_group.add(uninstall_row)

    def on_update_clicked(self, button):
        if not self.update_script.exists():
            print(f"ERR: Script missing: {self.update_script}")
            return

        my_pid = str(os.getpid())
        print(f"Starting the update process (PID: {my_pid})…")

        try:
            subprocess.Popen(_terminal_command(str(self.update_script), my_pid))
        except Exception as exc:  # noqa: BLE001
            print(f"Could not start the updater: {exc}")

    def on_uninstall_clicked(self, button):
        if not self.uninstall_script.exists():
            print(f"ERR: Script missing: {self.uninstall_script}")
            return

        # uninstall.sh still asks for confirmation in the terminal, so a
        # mis-click can be aborted. The app itself quits immediately.
        my_pid = str(os.getpid())
        print(f"Starting the uninstall process (PID: {my_pid})…")

        try:
            subprocess.Popen(_terminal_command(str(self.uninstall_script), my_pid))
        except Exception as exc:  # noqa: BLE001
            print(f"Could not start the uninstaller: {exc}")

        self.win.get_application().quit()