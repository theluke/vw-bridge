import subprocess
import xml.etree.ElementTree as ET
from unittest.mock import patch

import vw_android_app

DETAILS_XML = """
<hierarchy>
  <node resource-id="hornAndTurnSignals" bounds="[112,1580][968,1715]" />
  <node resource-id="turnSignals" bounds="[112,1750][968,1885]" />
</hierarchy>
"""


def test_status_requires_both_command_rows():
    root = ET.fromstring(DETAILS_XML)

    controls = {"horn": root[0], "flash": root[1]}
    with patch.object(vw_android_app, "_prepare_app", return_value=(root, controls)):
        payload = vw_android_app.status()

    assert payload == {
        "status": "ready",
        "backend": "android-app",
        "horn_enabled": True,
    }


def test_flash_taps_only_turn_signals_node():
    root = ET.fromstring(DETAILS_XML)
    turn_signals = root[1]

    with patch.object(
        vw_android_app,
        "_prepare_app",
        return_value=(root, {"horn": root[0], "flash": turn_signals}),
    ), patch.object(vw_android_app, "_dump_ui", return_value=root), patch.object(
        vw_android_app, "_tap"
    ) as tap, patch.object(vw_android_app.time, "sleep"):
        payload = vw_android_app.run_action("flash")

    assert payload["action"] == "flash"
    tap.assert_called_once_with(turn_signals)


def test_horn_taps_only_horn_and_turn_signals_node():
    root = ET.fromstring(DETAILS_XML)
    horn = root[0]

    with patch.object(
        vw_android_app,
        "_prepare_app",
        return_value=(root, {"horn": horn, "flash": root[1]}),
    ), patch.object(vw_android_app, "_dump_ui", return_value=root), patch.object(
        vw_android_app, "_tap"
    ) as tap, patch.object(vw_android_app.time, "sleep"):
        payload = vw_android_app.run_action("horn")

    assert payload["action"] == "horn"
    tap.assert_called_once_with(horn)


def test_tap_uses_center_of_accessibility_bounds():
    node = ET.fromstring('<node bounds="[112,1750][968,1885]" />')

    with patch.object(vw_android_app, "_adb") as adb:
        vw_android_app._tap(node)

    adb.assert_called_once_with("shell", "input", "tap", "540", "1817")


def test_adb_serial_uses_connected_device():
    devices = subprocess.CompletedProcess(
        [], 0, "List of devices attached\n127.0.0.1:45678\tdevice\n", ""
    )

    with patch.object(vw_android_app, "ADB_SERIAL", ""), patch.object(
        vw_android_app, "ADB_PATH", "/opt/bin/adb"
    ), patch.object(
        vw_android_app.subprocess, "run", return_value=devices
    ) as run:
        assert vw_android_app._adb_serial() == "127.0.0.1:45678"
        assert run.call_args.args[0] == ["/opt/bin/adb", "devices"]


def test_wait_for_controls_retries_transient_ui_failure():
    root = ET.fromstring(DETAILS_XML)

    with patch.object(
        vw_android_app,
        "_dump_ui",
        side_effect=[vw_android_app.AutomationError("ui_unavailable"), root],
    ), patch.object(vw_android_app.time, "sleep"):
        _, controls = vw_android_app._wait_for_controls()

    assert controls["flash"] is root[1]
    assert controls["horn"] is root[0]