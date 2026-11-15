"""Small BlueZ wrapper around ``bluetoothctl``.

Kept separate from the page so parsing is unit-testable and all subprocess
interaction lives in one place.
"""

from __future__ import annotations

import queue
import re
import subprocess
import threading
import time

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean(output: str) -> str:
    return _ANSI_RE.sub("", output or "")


def run(args: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["bluetoothctl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0, _clean(result.stdout + result.stderr)
    except FileNotFoundError:
        return False, "bluetoothctl is not installed"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def parse_devices(output: str) -> list[dict]:
    devices = []
    for line in _clean(output).splitlines():
        line = line.strip()
        if not line.startswith("Device "):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            continue
        mac = parts[1]
        name = parts[2] if len(parts) > 2 else mac
        devices.append({"mac": mac, "name": name})
    return devices


def parse_info(output: str) -> dict:
    fields: dict[str, str] = {}
    for line in _clean(output).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in ("name", "alias", "connected", "paired", "trusted", "icon", "address"):
            fields[key] = value.strip()
    return fields


def parse_controller(output: str) -> dict:
    fields: dict[str, str] = {}
    for line in _clean(output).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in ("powered", "discovering", "pairable", "discoverable", "name", "alias"):
            fields[key] = value.strip()
    return fields


def has_adapter() -> bool:
    ok, output = run(["list"])
    return ok and "Controller" in output


def controller() -> dict:
    ok, output = run(["show"])
    return parse_controller(output) if ok else {}


def powered() -> bool:
    return controller().get("powered") == "yes"


def set_powered(enabled: bool) -> bool:
    ok, _ = run(["power", "on" if enabled else "off"])
    return ok


def devices() -> list[dict]:
    ok, output = run(["devices"])
    return parse_devices(output) if ok else []


def device_info(mac: str) -> dict:
    ok, output = run(["info", mac])
    return parse_info(output) if ok else {}


def scan(timeout: int = 8) -> bool:
    ok, _ = run(["--timeout", str(timeout), "scan", "on"], timeout=timeout + 4)
    return ok


def connect(mac: str) -> bool:
    ok, _ = run(["connect", mac], timeout=20)
    return ok


def disconnect(mac: str) -> bool:
    ok, _ = run(["disconnect", mac], timeout=10)
    return ok


def agent_response(line: str, pin: str = "") -> str | None:
    """Return the bluetoothctl response for an agent prompt, if any."""

    lower = line.lower()
    if "request pin code" in lower or "request passkey" in lower:
        return pin or "0000"
    if (
        "confirm passkey" in lower
        or "authorize service" in lower
        or "accept pairing" in lower
    ):
        return "yes"
    return None


def pair_with_agent(mac: str, pin: str = "", timeout: int = 40) -> tuple[bool, str]:
    """Pair using an interactive KeyboardDisplay agent.

    Handles PIN/passkey requests and confirmation prompts.  Returns
    ``(success, last_lines)``.
    """

    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        return False, str(exc)

    lines: queue.Queue[str] = queue.Queue()

    def reader():
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.put(_clean(line.rstrip()))

    threading.Thread(target=reader, daemon=True).start()

    def send(command: str):
        if proc.stdin is not None:
            try:
                proc.stdin.write(command + "\n")
                proc.stdin.flush()
            except (OSError, ValueError):
                pass

    send("agent KeyboardDisplay")
    send("default-agent")
    send(f"pair {mac}")

    deadline = time.monotonic() + timeout
    success = False
    messages: list[str] = []
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        messages.append(line)
        response = agent_response(line, pin)
        if response is not None:
            send(response)
        lower = line.lower()
        if "pairing successful" in lower:
            success = True
            break
        if (
            "failed to pair" in lower
            or "authentication failed" in lower
            or "not available" in lower
        ):
            break

    send("quit")
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    return success, "\n".join(messages[-8:])


def pair(mac: str) -> bool:
    ok, _ = run(["pair", mac], timeout=25)
    return ok


def set_trusted(mac: str, trusted: bool) -> bool:
    ok, _ = run(["trust" if trusted else "untrust", mac])
    return ok


def remove(mac: str) -> bool:
    ok, _ = run(["remove", mac], timeout=15)
    return ok
