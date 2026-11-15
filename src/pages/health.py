"""Health check page.

Surfaces the state of the app, Caelestia, Hyprland, dependencies, wallpaper
daemons, unknown shell.json keys and backups, with explicit repair actions.
"""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import backup, health
from src.lang import t

_STATUS_ICONS = {
    "ok": "emblem-ok-symbolic",
    "info": "dialog-information-symbolic",
    "warning": "dialog-warning-symbolic",
    "error": "dialog-error-symbolic",
}


class HealthPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)

        title = Gtk.Label(label=t("Health check"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        bar.append(title)

        refresh = Gtk.Button(label=t("Re-check"))
        refresh.connect("clicked", lambda _b: self.refresh())
        bar.append(refresh)

        restart = Gtk.Button(label=t("Restart Caelestia shell"))
        restart.connect("clicked", self._on_restart_shell)
        bar.append(restart)

        reload_btn = Gtk.Button(label=t("Reload Hyprland"))
        reload_btn.connect("clicked", self._on_reload_hyprland)
        bar.append(reload_btn)
        self.append(bar)

        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        self.append(self.banner)

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

        self.refresh()

    # ── Rendering ─────────────────────────────────────────────────────────

    def refresh(self):
        while child := self.content.get_first_child():
            self.content.remove(child)

        results = health.run_all()
        errors = sum(1 for result in results if result.status == "error")
        warnings = sum(1 for result in results if result.status == "warning")

        if errors:
            self.banner.set_title(
                f"{errors} error(s), {warnings} warning(s) — see details below."
            )
            self.banner.set_revealed(True)
        elif warnings:
            self.banner.set_title(f"{warnings} warning(s) — see details below.")
            self.banner.set_revealed(True)
        else:
            self.banner.set_title(t("All checks passed."))
            self.banner.set_revealed(True)

        app_checks = [r for r in results if r.key in ("app_version", "shell_version")]
        config_checks = [
            r for r in results
            if r.key in ("hyprland_errors", "unknown_keys", "backups")
            or r.key.startswith("json")
        ]
        wallpaper_checks = [r for r in results if r.key == "wallpaper"]
        dependency_checks = [r for r in results if r.key.startswith("dep:")]

        self.content.append(
            self._group(t("Application"), app_checks, icon="applications-system-symbolic")
        )
        self.content.append(
            self._group(t("Configuration"), config_checks, icon="preferences-system-symbolic")
        )
        self.content.append(
            self._group(t("Wallpaper"), wallpaper_checks, icon="preferences-desktop-wallpaper-symbolic")
        )

        dependency_group = self._group(
            t("Dependencies"), dependency_checks, icon="package-x-generic-symbolic"
        )
        self.content.append(dependency_group)

        footer = Gtk.Label()
        footer.set_markup(
            f"<small>{t('Every repair action creates a timestamped backup first.')} "
            f"{t('Backups')}: <tt>{str(backup.BACKUP_DIR).replace(str(health.HOME), '~')}</tt></small>"
        )
        footer.add_css_class("dim-label")
        footer.set_halign(Gtk.Align.START)
        self.content.append(footer)

    def _group(self, title: str, checks: list[health.CheckResult], icon: str) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title)
        if not checks:
            group.add(Adw.ActionRow(title=t("No checks"), subtitle=""))
            return group
        for check in checks:
            group.add(self._check_row(check))
        return group

    def _check_row(self, check: health.CheckResult) -> Adw.ActionRow:
        row = Adw.ActionRow(title=check.title, subtitle=check.detail)
        try:
            row.set_subtitle_lines(0)
        except (AttributeError, TypeError):
            pass

        icon = Gtk.Image.new_from_icon_name(_STATUS_ICONS.get(check.status, "dialog-information-symbolic"))
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        if check.key == "unknown_keys" and check.status == "warning":
            button = Gtk.Button(label=t("Clean…"))
            button.add_css_class("destructive-action")
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", self._on_clean_unknown, check)
            row.add_suffix(button)
        elif check.key == "wallpaper":
            reapply = Gtk.Button(label=t("Reapply wallpaper"))
            reapply.set_valign(Gtk.Align.CENTER)
            reapply.connect("clicked", self._on_reapply)
            row.add_suffix(reapply)

            if check.data.get("hyprpaper") and check.data.get("shell"):
                disable = Gtk.Button(label=t("Disable hyprpaper"))
                disable.add_css_class("destructive-action")
                disable.set_valign(Gtk.Align.CENTER)
                disable.connect("clicked", self._on_disable_hyprpaper)
                row.add_suffix(disable)
        elif check.key == "hyprland_errors" and check.status == "error":
            reload_btn = Gtk.Button(label=t("Reload"))
            reload_btn.set_valign(Gtk.Align.CENTER)
            reload_btn.connect("clicked", self._on_reload_hyprland)
            row.add_suffix(reload_btn)
        elif check.key == "backups":
            open_btn = Gtk.Button(label=t("Open folder"))
            open_btn.set_valign(Gtk.Align.CENTER)
            open_btn.connect("clicked", self._on_open_backups)
            row.add_suffix(open_btn)
        return row

    # ── Actions ───────────────────────────────────────────────────────────

    def _toast(self, message: str):
        self.main_window.add_toast(Adw.Toast.new(message))

    def _on_restart_shell(self, _button):
        if health.restart_shell():
            self._toast(t("Restarting the Caelestia shell…"))
        else:
            self._toast(t("Could not restart the Caelestia shell."))

    def _on_reload_hyprland(self, _button):
        if health.reload_hypr():
            self._toast(t("Hyprland reloaded."))
        else:
            self._toast(t("Could not reload Hyprland."))

    def _on_reapply(self, _button):
        if health.reapply_wallpaper():
            self._toast(t("Reapplying the wallpaper…"))
            self.refresh()
        else:
            self._toast(t("Could not reapply the wallpaper."))

    def _on_disable_hyprpaper(self, _button):
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Disable hyprpaper?"),
            body=t(
                "hyprpaper will be stopped and its autostart line in hypr-user.lua "
                "will be commented out. A backup is created first. Caelestia's shell "
                "wallpaper will handle the monitors."
            ),
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("disable", t("Disable"))
        dialog.set_response_appearance("disable", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "disable":
                return
            try:
                edited, stopped = health.disable_hyprpaper()
                parts = []
                if edited:
                    parts.append(t("autostart commented out"))
                if stopped:
                    parts.append(t("running process stopped"))
                self._toast(
                    t("hyprpaper disabled") + (f" ({', '.join(parts)})" if parts else "")
                )
                self.refresh()
            except backup.BackupError as exc:
                self._toast(str(exc))
            except Exception as exc:  # noqa: BLE001 - defensive UI path
                self._toast(f"{t('Could not disable hyprpaper')}: {exc}")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_clean_unknown(self, _button, check: health.CheckResult):
        unknown = check.data.get("unknown", {})
        total = sum(len(paths) for paths in unknown.values())
        if not total:
            return
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Remove unknown settings?"),
            body=(
                t("This removes {count} key(s) that the installed Caelestia shell "
                  "does not recognise. A backup is created first.").format(count=total)
            ),
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("remove", t("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "remove":
                return
            try:
                removed = health.remove_unknown_keys(unknown)
                self._toast(f"{t('Removed')} {removed} {t('unknown key(s).')}")
                self.refresh()
            except backup.BackupError as exc:
                self._toast(str(exc))
            except Exception as exc:  # noqa: BLE001
                self._toast(f"{t('Could not remove unknown keys')}: {exc}")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_open_backups(self, _button):
        try:
            subprocess.Popen(["xdg-open", str(backup.BACKUP_DIR)])
        except (OSError, subprocess.SubprocessError) as exc:
            self._toast(f"{t('Could not open the backup folder')}: {exc}")
