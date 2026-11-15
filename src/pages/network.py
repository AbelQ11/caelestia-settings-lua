"""General NetworkManager page: devices, connections, VPN import and IPv4."""

from __future__ import annotations

import shutil
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.lang import t


def _run(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["nmcli", *args], capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", "nmcli is not installed"
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)


def _split_terse(line: str) -> list[str]:
    fields = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def parse_device_status(output: str) -> list[dict]:
    devices = []
    for line in output.splitlines():
        fields = _split_terse(line)
        if len(fields) < 4:
            continue
        devices.append(
            {
                "device": fields[0],
                "type": fields[1],
                "state": fields[2],
                "connection": fields[3],
            }
        )
    return devices


def parse_connections(output: str) -> list[dict]:
    connections = []
    for line in output.splitlines():
        fields = _split_terse(line)
        if len(fields) < 2:
            continue
        connections.append(
            {
                "name": fields[0],
                "type": fields[1],
                "device": fields[2] if len(fields) > 2 else "",
            }
        )
    return connections


def list_devices() -> list[dict]:
    code, output, _ = _run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    return parse_device_status(output) if code == 0 else []


def list_connections() -> list[dict]:
    code, output, _ = _run(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show"])
    return parse_connections(output) if code == 0 else []


def ipv4_settings(name: str) -> dict:
    code, output, _ = _run(
        ["-g", "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns", "connection", "show", name]
    )
    if code != 0:
        return {"method": "", "addresses": "", "gateway": "", "dns": ""}
    values = output.splitlines() + [""] * 4
    return {
        "method": values[0],
        "addresses": values[1],
        "gateway": values[2],
        "dns": values[3],
    }


def apply_ipv4(name: str, method: str, addresses: str, gateway: str, dns: str) -> bool:
    args = ["connection", "modify", name, "ipv4.method", method]
    args += ["ipv4.addresses", addresses if method == "manual" else ""]
    args += ["ipv4.gateway", gateway if method == "manual" else ""]
    args += ["ipv4.dns", dns if method == "manual" else ""]
    code, _, _ = _run(args, timeout=20)
    if code != 0:
        return False
    _run(["connection", "up", name], timeout=30)
    return True


class NetworkPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        title = Gtk.Label(label=t("Network"))
        title.add_css_class("heading")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)

        import_btn = Gtk.Button(label=t("+ Import VPN"))
        import_btn.connect("clicked", self._on_import_vpn)
        toolbar.append(import_btn)

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
        self.content.set_margin_top(8)
        self.content.set_margin_bottom(16)
        self.content.set_margin_start(12)
        self.content.set_margin_end(12)
        scroller.set_child(self.content)

        self._load()

    def _load(self):
        while child := self.content.get_first_child():
            self.content.remove(child)

        if shutil.which("nmcli") is None:
            status = Adw.StatusPage()
            status.set_icon_name("network-offline-symbolic")
            status.set_title(t("NetworkManager is not available"))
            status.set_description(t("Install NetworkManager and the nmcli tool."))
            self.content.append(status)
            return

        device_group = Adw.PreferencesGroup(title=t("Devices"))
        self.content.append(device_group)
        devices = list_devices()
        if not devices:
            device_group.add(Adw.ActionRow(title=t("No network devices found")))
        for device in devices:
            row = Adw.ActionRow(
                title=device["device"],
                subtitle=f"{device['type']}  ·  {device['state']}"
                + (f"  ·  {device['connection']}" if device["connection"] else ""),
            )
            if device["state"] == "connected":
                btn = Gtk.Button(label=t("Disconnect"))
                btn.set_valign(Gtk.Align.CENTER)
                btn.connect("clicked", self._on_device_action, device["device"], "disconnect")
            else:
                btn = Gtk.Button(label=t("Connect"))
                btn.add_css_class("suggested-action")
                btn.set_valign(Gtk.Align.CENTER)
                btn.connect("clicked", self._on_device_action, device["device"], "connect")
            row.add_suffix(btn)
            device_group.add(row)

        connection_group = Adw.PreferencesGroup(
            title=t("Saved connections"),
            description=t("Connect, edit IPv4 or remove a connection."),
        )
        self.content.append(connection_group)
        connections = list_connections()
        if not connections:
            connection_group.add(Adw.ActionRow(title=t("No saved connections")))
        for connection in connections:
            name = connection["name"]
            row = Adw.ActionRow(
                title=name,
                subtitle=f"{connection['type']}"
                + (f"  ·  {connection['device']}" if connection["device"] else ""),
            )
            activate = Gtk.Button(label=t("Activate"))
            activate.set_valign(Gtk.Align.CENTER)
            activate.connect("clicked", self._on_connection_action, name, "up")
            row.add_suffix(activate)

            deactivate = Gtk.Button(label=t("Deactivate"))
            deactivate.set_valign(Gtk.Align.CENTER)
            deactivate.connect("clicked", self._on_connection_action, name, "down")
            row.add_suffix(deactivate)

            ipv4 = Gtk.Button(label=t("IPv4"))
            ipv4.set_valign(Gtk.Align.CENTER)
            ipv4.connect("clicked", self._edit_ipv4, name)
            row.add_suffix(ipv4)

            delete = Gtk.Button()
            delete.set_icon_name("user-trash-symbolic")
            delete.add_css_class("flat")
            delete.set_valign(Gtk.Align.CENTER)
            delete.connect("clicked", self._delete_connection, name)
            row.add_suffix(delete)
            connection_group.add(row)

        note = Gtk.Label(
            label=t("Wi-Fi scanning and passwords are on the Wi-Fi page.")
        )
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        note.set_halign(Gtk.Align.START)
        self.content.append(note)

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_device_action(self, _button, device: str, action: str):
        code, _, error = _run(["device", action, device])
        if code == 0:
            self.main_window.add_toast(
                Adw.Toast.new(f"{device}: {t('Done') if action == 'connect' else t('Disconnected')}")
            )
            self._load()
        else:
            self.main_window.add_toast(Adw.Toast.new(error or t("Network operation failed")))

    def _on_connection_action(self, _button, name: str, action: str):
        code, _, error = _run(["connection", action, name], timeout=30)
        if code == 0:
            self.main_window.add_toast(
                Adw.Toast.new(f"{name}: {t('Activated') if action == 'up' else t('Deactivated')}")
            )
            self._load()
        else:
            self.main_window.add_toast(Adw.Toast.new(error or t("Network operation failed")))

    def _delete_connection(self, _button, name: str):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=t("Delete this connection?"),
            body=name,
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("delete", t("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog_obj, response):
            if response != "delete":
                return
            code, _, error = _run(["connection", "delete", name])
            if code == 0:
                self.main_window.add_toast(Adw.Toast.new(t("Connection deleted.")))
                self._load()
            else:
                self.main_window.add_toast(Adw.Toast.new(error or t("Could not delete the connection.")))

        dialog.connect("response", on_response)
        dialog.present()

    def _edit_ipv4(self, _button, name: str):
        settings = ipv4_settings(name)
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=t("IPv4 settings"),
            body=name,
        )
        box = Gtk.ListBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")

        method_row = Adw.ActionRow(title=t("Method"))
        method = Gtk.ComboBoxText()
        method.set_valign(Gtk.Align.CENTER)
        method.append("auto", t("Automatic (DHCP)"))
        method.append("manual", t("Manual"))
        current_method = settings.get("method") or "auto"
        if not method.set_active_id(current_method):
            method.set_active_id("auto")
        method_row.add_suffix(method)
        box.append(method_row)

        addresses = Adw.EntryRow(title=t("Addresses (CIDR, comma separated)"))
        addresses.set_text(settings.get("addresses", ""))
        box.append(addresses)

        gateway = Adw.EntryRow(title=t("Gateway"))
        gateway.set_text(settings.get("gateway", ""))
        box.append(gateway)

        dns = Adw.EntryRow(title=t("DNS servers (comma separated)"))
        dns.set_text(settings.get("dns", ""))
        box.append(dns)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("apply", t("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog_obj, response):
            if response != "apply":
                return
            if apply_ipv4(
                name,
                method.get_active_id() or "auto",
                addresses.get_text().strip(),
                gateway.get_text().strip(),
                dns.get_text().strip(),
            ):
                self.main_window.add_toast(Adw.Toast.new(t("IPv4 settings applied.")))
                self._load()
            else:
                self.main_window.add_toast(Adw.Toast.new(t("Could not apply IPv4 settings.")))

        dialog.connect("response", on_response)
        dialog.present()

    def _on_import_vpn(self, _button):
        chooser = Gtk.FileChooserNative.new(
            t("Import VPN configuration"),
            self.get_root(),
            Gtk.FileChooserAction.OPEN,
            t("Import"),
            t("Cancel"),
        )
        vpn_filter = Gtk.FileFilter()
        vpn_filter.set_name(t("VPN configurations"))
        vpn_filter.add_pattern("*.ovpn")
        vpn_filter.add_pattern("*.conf")
        chooser.add_filter(vpn_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name(t("All files"))
        all_filter.add_pattern("*")
        chooser.add_filter(all_filter)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file is not None and file.get_path():
                    code, output, error = _run(
                        ["connection", "import", "type", "openvpn", "file", file.get_path()],
                        timeout=30,
                    )
                    if code == 0:
                        self.main_window.add_toast(
                            Adw.Toast.new(t("VPN configuration imported."))
                        )
                        self._load()
                    else:
                        self.main_window.add_toast(
                            Adw.Toast.new(error or t("Could not import the VPN."))
                        )
            dialog.destroy()

        chooser.connect("response", on_response)
        chooser.show()
