from src import bluetooth
from src.pages import audio


def test_audio_parse_devices():
    output = """
Sink #0
    Name: alsa_output.pci-0000_00_1f.3.analog-stereo
    Description: Built-in Audio Analog Stereo
Sink #1
    Name: bluez_output.AC_12_2F_00_00_01.1
    Description: WH-1000XM4
"""
    devices = audio.parse_devices(output)
    assert devices["alsa_output.pci-0000_00_1f.3.analog-stereo"] == "Built-in Audio Analog Stereo"
    assert devices["bluez_output.AC_12_2F_00_00_01.1"] == "WH-1000XM4"


def test_audio_parse_volume_and_mute():
    assert audio.parse_volume("Volume: front-left: 32768 /  50% / -18.06 dB") == 50
    assert audio.parse_volume("Volume: mono: 65536 / 100% / 0.00 dB") == 100
    assert audio.parse_mute("Mute: yes") is True
    assert audio.parse_mute("Mute: no") is False


def test_audio_parse_sink_inputs():
    payload = """[
        {"index": 12, "sink": 2, "mute": false,
         "properties": {"application.name": "Firefox"}},
        {"index": 13, "sink": 2, "mute": true,
         "properties": {"media.name": "Video"}}
    ]"""
    inputs = audio.parse_sink_inputs(payload)
    assert inputs == [
        {"index": 12, "name": "Firefox", "sink": 2, "mute": False},
        {"index": 13, "name": "Video", "sink": 2, "mute": True},
    ]
    assert audio.parse_sink_inputs("not json") == []


def test_bluetooth_parse_devices():
    output = """
Device AA:BB:CC:DD:EE:FF WH-1000XM4
Device 11:22:33:44:55:66 MX Master 3
"""
    devices = bluetooth.parse_devices(output)
    assert devices == [
        {"mac": "AA:BB:CC:DD:EE:FF", "name": "WH-1000XM4"},
        {"mac": "11:22:33:44:55:66", "name": "MX Master 3"},
    ]


def test_bluetooth_agent_responses():
    assert bluetooth.agent_response("[agent] Request PIN code") == "0000"
    assert bluetooth.agent_response("[agent] Request passkey", "123456") == "123456"
    assert bluetooth.agent_response("[agent] Confirm passkey 123456") == "yes"
    assert bluetooth.agent_response("[agent] Authorize service") == "yes"
    assert bluetooth.agent_response("Pairing successful") is None


def test_bluetooth_parse_info_and_controller():
    info = bluetooth.parse_info(
        """
Device AA:BB:CC:DD:EE:FF
  Name: WH-1000XM4
  Alias: Headphones
  Connected: yes
  Paired: yes
  Trusted: no
  Icon: audio-card
"""
    )
    assert info["name"] == "WH-1000XM4"
    assert info["alias"] == "Headphones"
    assert info["connected"] == "yes"

    controller = bluetooth.parse_controller(
        """
Controller AA:BB:CC:DD:EE:FF
  Powered: yes
  Discovering: no
  Pairable: yes
"""
    )
    assert controller["powered"] == "yes"
    assert controller["discovering"] == "no"
