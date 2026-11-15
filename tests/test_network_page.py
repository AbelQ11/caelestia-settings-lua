from src.pages import network


def test_parse_device_status():
    output = "\n".join([
        "wlan0:wifi:connected:My Network",
        "eth0:ethernet:disconnected:",
        "tun0:tun:connected:Work VPN",
    ])
    devices = network.parse_device_status(output)
    assert devices[0] == {
        "device": "wlan0",
        "type": "wifi",
        "state": "connected",
        "connection": "My Network",
    }
    assert devices[1]["connection"] == ""
    assert len(devices) == 3


def test_parse_connections_with_escaped_colon():
    output = "Home\\:Office:wifi:wlan0\nWired connection 1:ethernet:eth0"
    connections = network.parse_connections(output)
    assert connections[0]["name"] == "Home:Office"
    assert connections[0]["type"] == "wifi"
    assert connections[1]["device"] == "eth0"
