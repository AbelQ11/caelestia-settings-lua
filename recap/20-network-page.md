# 20 — General Network page

Date: 2026-11-12

## New page

`src/pages/network.py` (sidebar → Hardware → Network):

- **Devices**: every NetworkManager device with type/state/active connection;
  connect or disconnect directly.
- **Saved connections**: activate, deactivate and delete connections
  (Ethernet, Wi-Fi, VPN, tunnels, …).
- **IPv4 editor**: automatic (DHCP) or manual addresses/gateway/DNS via
  `nmcli connection modify` + `connection up`.
- **Import VPN**: `.ovpn`/`.conf` through
  `nmcli connection import type openvpn file`.
- Missing `nmcli` shows a clear “NetworkManager is not available” state.
- Wi-Fi scanning/passwords stay on the Wi-Fi page.

## Parsing

`src/pages/network.py` includes pure terse-output parsers:

- `parse_device_status()` — handles `:` escaping in connection names;
- `parse_connections()`.

## Integration

- Added to the grouped sidebar under **Hardware** and to global search.
- UI smoke test constructs the page.

## Tests

`tests/test_network_page.py` covers device and connection parsing (including
escaped colons).

Total suite: **100 tests**.
