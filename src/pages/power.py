"""Power profiles, battery status and Caelestia idle behaviour."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from gi.repository import Adw, Gtk

from src import backup, shell_config
from src.lang import t


def _run(command: list[str], timeout: int = 3) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


def available_profiles() -> list[str]:
    if not shutil.which("powerprofilesctl"):
        return []
    code, output, _ = _run(["powerprofilesctl", "list"])
    profiles = []
    if code == 0:
        for line in output.splitlines():
            match = re.match(r"^\s*\*?\s*([a-z0-9-]+):\s*$", line)
            if match:
                profiles.append(match.group(1))
    return profiles or ["performance", "balanced", "power-saver"]


def current_profile() -> str:
    if not shutil.which("powerprofilesctl"):
        return ""
    code, output, _ = _run(["powerprofilesctl", "get"])
    return output if code == 0 else ""


def set_profile(profile: str) -> bool:
    if not shutil.which("powerprofilesctl"):
        return False
    return _run(["powerprofilesctl", "set", profile])[0] == 0


def battery_status() -> dict | None:
    try:
        import psutil

        battery = psutil.sensors_battery()
        if battery is not None:
            seconds = battery.secsleft
            if seconds is None or seconds < 0:
                seconds = None
            return {
                "percent": round(battery.percent),
                "plugged": bool(battery.power_plugged),
                "seconds": seconds,
            }
    except Exception:  # noqa: BLE001 - psutil may be missing or fail
        pass

    for directory in Path("/sys/class/power_supply").glob("BAT*"):
        try:
            percent = int((directory / "capacity").read_text().strip())
            status = (directory / "status").read_text().strip().lower()
            return {
                "percent": percent,
                "plugged": status in ("charging", "full"),
                "seconds": None,
            }
        except (OSError, ValueError):
            continue
    return None


def _format_seconds(seconds: int | None) -> str:
    if seconds is None:
        return t("Unknown")
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours} h {minutes} min"


class PowerPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._loading = False

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.set_margin_top(12)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=t("Power management"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)
        refresh = Gtk.Button()
        refresh.set_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text(t("Reload"))
        refresh.connect("clicked", lambda _b: self._load())
        toolbar.append(refresh)
        self.content.append(toolbar)

        self._build_profile()
        self._build_battery()
        self._build_idle()
        self._load()

    # ── Profile ───────────────────────────────────────────────────────────

    def _build_profile(self):
        self._profile_group = Adw.PreferencesGroup(
            title=t("Power profile"),
            description=t("Managed by power-profiles-daemon."),
        )
        self.content.append(self._profile_group)
        self._profile_row = Adw.ActionRow(title=t("Profile"))
        self._profile_combo = Gtk.ComboBoxText()
        self._profile_combo.set_valign(Gtk.Align.CENTER)
        self._profile_combo.connect("changed", self._on_profile_changed)
        self._profile_row.add_suffix(self._profile_combo)
        self._profile_group.add(self._profile_row)

    def _on_profile_changed(self, combo):
        if self._loading:
            return
        profile = combo.get_active_id()
        if not profile:
            return
        if set_profile(profile):
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Power profile set to')} {profile}")
            )
        else:
            self.main_window.add_toast(
                Adw.Toast.new(t("Could not change the power profile."))
            )

    # ── Battery ───────────────────────────────────────────────────────────

    def _build_battery(self):
        self._battery_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.append(self._battery_wrapper)
        self._refresh_battery()

    def _refresh_battery(self):
        while child := self._battery_wrapper.get_first_child():
            self._battery_wrapper.remove(child)
        group = Adw.PreferencesGroup(title=t("Battery"))
        self._battery_wrapper.append(group)
        battery = battery_status()
        if battery is None:
            group.add(
                Adw.ActionRow(
                    title=t("No battery detected"),
                    subtitle=t("This system does not expose a battery."),
                )
            )
            return
        percent = battery["percent"]
        group.add(
            Adw.ActionRow(
                title=t("Charge"),
                subtitle=f"{percent} %"
                + (f"  ·  {t('plugged in')}" if battery["plugged"] else ""),
            )
        )
        group.add(
            Adw.ActionRow(
                title=t("Estimated time"),
                subtitle=_format_seconds(battery["seconds"]),
            )
        )

    # ── Idle ──────────────────────────────────────────────────────────────

    def _build_idle(self):
        group = Adw.PreferencesGroup(
            title=t("Idle and sleep"),
            description=t("Stored in shell.json. Timeouts are on the Caelestia page."),
        )
        self.content.append(group)

        self._lock_before_sleep = Adw.SwitchRow(title=t("Lock before sleep"))
        group.add(self._lock_before_sleep)

        self._inhibit_audio = Adw.SwitchRow(title=t("Inhibit idle while audio plays"))
        group.add(self._inhibit_audio)

        self._inhibit_charging = Adw.SwitchRow(title=t("Inhibit idle while charging"))
        group.add(self._inhibit_charging)

        apply_row = Adw.ActionRow(title=t("Apply idle settings"))
        open_btn = Gtk.Button(label=t("Caelestia idle options"))
        open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.connect("clicked", self._open_caelestia)
        apply_row.add_suffix(open_btn)
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", self._on_apply_idle)
        apply_row.add_suffix(apply_btn)
        group.add(apply_row)

    def _open_caelestia(self, _button):
        try:
            self.main_window.stack.set_visible_child_name("shell")
        except AttributeError:
            pass

    def _on_apply_idle(self, _button):
        try:
            shell_config.set_many(
                {
                    "general.idle.lockBeforeSleep": self._lock_before_sleep.get_active(),
                    "general.idle.inhibitWhenAudio": self._inhibit_audio.get_active(),
                    "general.idle.inhibitWhenCharging": self._inhibit_charging.get_active(),
                }
            )
            self.main_window.add_toast(Adw.Toast.new(t("Idle settings applied.")))
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001 - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save idle settings')}: {exc}")
            )

    # ── Load ──────────────────────────────────────────────────────────────

    def _load(self):
        self._loading = True
        profiles = available_profiles()
        self._profile_combo.remove_all()
        self._profile_group.set_description(
            t("Managed by power-profiles-daemon.") if profiles else
            t("powerprofilesctl is not installed; power profiles are unavailable.")
        )
        for profile in profiles:
            self._profile_combo.append(profile, profile)
        current = current_profile()
        if current:
            self._profile_combo.set_active_id(current)
        elif profiles:
            self._profile_combo.set_active(0)
        self._profile_row.set_sensitive(bool(profiles))

        self._lock_before_sleep.set_active(
            bool(shell_config.get("general.idle.lockBeforeSleep", True))
        )
        self._inhibit_audio.set_active(
            bool(shell_config.get("general.idle.inhibitWhenAudio", True))
        )
        self._inhibit_charging.set_active(
            bool(shell_config.get("general.idle.inhibitWhenCharging", False))
        )
        self._refresh_battery()
        self._loading = False
