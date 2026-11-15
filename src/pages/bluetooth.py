"""Bluetooth devices and adapter control via bluetoothctl."""

from __future__ import annotations

import threading

from gi.repository import Adw, GLib, Gtk

from src import bluetooth
from src.lang import t


class BluetoothPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._loading = False

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        title = Gtk.Label(label=t("Bluetooth"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)

        self.spinner = Gtk.Spinner()
        toolbar.append(self.spinner)

        self.scan_btn = Gtk.Button(label=t("Scan"))
        self.scan_btn.add_css_class("suggested-action")
        self.scan_btn.connect("clicked", self._on_scan)
        toolbar.append(self.scan_btn)

        refresh = Gtk.Button()
        refresh.set_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text(t("Reload"))
        refresh.connect("clicked", lambda _b: self._load())
        toolbar.append(refresh)
        self.append(toolbar)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content.set_margin_top(4)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._load()

    # ── Loading ───────────────────────────────────────────────────────────

    def _load(self):
        while child := self.content.get_first_child():
            self.content.remove(child)

        if not bluetooth.has_adapter():
            status = Adw.StatusPage()
            status.set_icon_name("bluetooth-disabled-symbolic")
            status.set_title(t("No Bluetooth adapter"))
            status.set_description(
                t("bluetoothctl could not find an adapter. Check that BlueZ is installed "
                  "and the service is running.")
            )
            status.set_vexpand(True)
            self.content.append(status)
            self.scan_btn.set_sensitive(False)
            return

        self.scan_btn.set_sensitive(True)
        controller = bluetooth.controller()

        adapter_group = Adw.PreferencesGroup(title=t("Adapter"))
        self.content.append(adapter_group)

        self._loading = True
        power_row = Adw.SwitchRow(
            title=t("Bluetooth"),
            subtitle=(controller.get("name") or controller.get("alias") or t("Adapter")),
        )
        power_row.set_active(controller.get("powered") == "yes")
        power_row.connect("notify::active", self._on_power)
        adapter_group.add(power_row)
        self._loading = False

        if controller.get("discovering") == "yes":
            discovering = Adw.ActionRow(title=t("Discovering…"), subtitle=t("Scan in progress"))
            adapter_group.add(discovering)

        known = bluetooth.devices()
        entries = []
        for device in known:
            info = bluetooth.device_info(device["mac"])
            device.update(
                {
                    "connected": info.get("connected") == "yes",
                    "paired": info.get("paired") == "yes",
                    "trusted": info.get("trusted") == "yes",
                    "name": info.get("alias") or info.get("name") or device["name"],
                    "icon": info.get("icon", ""),
                }
            )
            entries.append(device)

        entries.sort(
            key=lambda item: (
                0 if item.get("connected") else 1 if item.get("paired") else 2,
                (item.get("name") or "").lower(),
            )
        )

        group = Adw.PreferencesGroup(
            title=t("Devices"),
            description=t("Pair, connect, trust or remove Bluetooth devices."),
        )
        self.content.append(group)
        if not entries:
            group.add(
                Adw.ActionRow(
                    title=t("No devices"),
                    subtitle=t("Use Scan to look for nearby devices."),
                )
            )
        for device in entries:
            group.add(self._device_row(device))

    def _device_row(self, device: dict) -> Adw.ActionRow:
        status = []
        if device.get("connected"):
            status.append(t("Connected"))
        if device.get("paired"):
            status.append(t("Paired"))
        if device.get("trusted"):
            status.append(t("Trusted"))
        if not status:
            status.append(t("Available"))

        row = Adw.ActionRow(
            title=device.get("name") or device["mac"],
            subtitle=f"{device['mac']}  ·  {' · '.join(status)}",
        )
        icon = Gtk.Image.new_from_icon_name(
            "bluetooth-active-symbolic" if device.get("connected") else "bluetooth-symbolic"
        )
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        if device.get("connected"):
            disconnect = Gtk.Button(label=t("Disconnect"))
            disconnect.set_valign(Gtk.Align.CENTER)
            disconnect.connect("clicked", self._on_disconnect, device)
            row.add_suffix(disconnect)
        elif device.get("paired"):
            connect = Gtk.Button(label=t("Connect"))
            connect.add_css_class("suggested-action")
            connect.set_valign(Gtk.Align.CENTER)
            connect.connect("clicked", self._on_connect, device)
            row.add_suffix(connect)
        else:
            pair = Gtk.Button(label=t("Pair"))
            pair.add_css_class("suggested-action")
            pair.set_valign(Gtk.Align.CENTER)
            pair.connect("clicked", self._on_pair, device)
            row.add_suffix(pair)

        trust = Gtk.Button()
        trust.set_icon_name("security-high-symbolic")
        trust.add_css_class("flat")
        trust.set_tooltip_text(t("Trusted") if device.get("trusted") else t("Trust this device"))
        if device.get("trusted"):
            trust.add_css_class("accent")
        trust.set_valign(Gtk.Align.CENTER)
        trust.connect("clicked", self._on_trust, device)
        row.add_suffix(trust)

        remove = Gtk.Button()
        remove.set_icon_name("user-trash-symbolic")
        remove.add_css_class("flat")
        remove.set_tooltip_text(t("Remove device"))
        remove.set_valign(Gtk.Align.CENTER)
        remove.connect("clicked", self._on_remove, device)
        row.add_suffix(remove)
        return row

    # ── Actions ───────────────────────────────────────────────────────────

    def _toast(self, message: str):
        self.main_window.add_toast(Adw.Toast.new(message))

    def _on_power(self, row, _param):
        if self._loading:
            return
        if bluetooth.set_powered(row.get_active()):
            self._toast(t("Bluetooth enabled.") if row.get_active() else t("Bluetooth disabled."))
        else:
            self._toast(t("Could not change Bluetooth power."))
        GLib.timeout_add(400, self._load)

    def _on_scan(self, _button):
        self.scan_btn.set_sensitive(False)
        self.spinner.start()

        def worker():
            bluetooth.scan(8)
            GLib.idle_add(self._scan_done)

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self):
        self.spinner.stop()
        self.scan_btn.set_sensitive(True)
        self._load()
        self._toast(t("Bluetooth scan finished."))

    def _run_action(self, action, device, success_message):
        if action(device["mac"]):
            self._toast(success_message)
        else:
            self._toast(t("Bluetooth operation failed."))
        GLib.timeout_add(400, self._load)

    def _on_connect(self, _button, device):
        self._run_action(bluetooth.connect, device, f"{t('Connected to')} {device['name']}")

    def _on_disconnect(self, _button, device):
        self._run_action(
            bluetooth.disconnect, device, f"{t('Disconnected from')} {device['name']}"
        )

    def _on_pair(self, _button, device):
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Pair device"),
            body=device["name"],
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text(t("PIN or passkey (optional)"))
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("pair", t("Pair"))
        dialog.set_response_appearance("pair", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("pair")

        def on_response(dialog_obj, response):
            if response != "pair":
                return
            pin = entry.get_text().strip()
            self._toast(f"{t('Pairing with')} {device['name']}…")

            def worker():
                ok, output = bluetooth.pair_with_agent(device["mac"], pin)
                GLib.idle_add(self._pair_finished, device, ok, output)

            threading.Thread(target=worker, daemon=True).start()

        dialog.connect("response", on_response)
        dialog.present()

    def _pair_finished(self, device, ok, output):
        if ok:
            self._toast(f"{t('Paired with')} {device['name']}")
            bluetooth.set_trusted(device["mac"], True)
        else:
            detail = output.splitlines()[-1] if output else t("unknown error")
            self._toast(f"{t('Pairing failed')}: {detail}")
        self._load()
        return False

    def _on_trust(self, _button, device):
        trusted = not device.get("trusted")
        if bluetooth.set_trusted(device["mac"], trusted):
            self._toast(
                f"{t('Trusted')} {device['name']}" if trusted else f"{t('Untrusted')} {device['name']}"
            )
        else:
            self._toast(t("Could not change trust state."))
        GLib.timeout_add(300, self._load)

    def _on_remove(self, _button, device):
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Remove device?"),
            body=f"{device['name']}\n{device['mac']}",
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("remove", t("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "remove":
                return
            if bluetooth.remove(device["mac"]):
                self._toast(t("Device removed."))
            else:
                self._toast(t("Could not remove the device."))
            GLib.timeout_add(300, self._load)

        dialog.connect("response", on_response)
        dialog.present()
