import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ADB_PATH = os.getenv("VW_ANDROID_ADB_PATH", "adb")
ADB_SERIAL = os.getenv("VW_ANDROID_ADB_SERIAL", "")
APP_ACTIVITY = "com.volkswagen.weconnect/.SingleActivity"
HOME_CONTROL = "Horn and Turn Signals. Open details"
TURN_SIGNALS_ID = "turnSignals"
HORN_ID = "hornAndTurnSignals"
BOUNDS_PATTERN = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


class AutomationError(RuntimeError):
    pass


def _adb_serial():
    if ADB_SERIAL:
        return ADB_SERIAL
    result = subprocess.run(
        [ADB_PATH, "devices"], capture_output=True, text=True, timeout=10, check=False
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2 and fields[1] == "device":
                return fields[0]
    raise AutomationError("adb_unavailable")


def _adb(*arguments, timeout=20):
    result = subprocess.run(
        [ADB_PATH, "-s", _adb_serial(), *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise AutomationError("adb_command_failed")
    return result.stdout


def _dump_ui():
    output = _adb("exec-out", "uiautomator", "dump", "/dev/tty")
    start = output.find("<?xml")
    end = output.rfind("</hierarchy>")
    if start < 0 or end < 0:
        raise AutomationError("ui_unavailable")
    try:
        return ET.fromstring(output[start : end + len("</hierarchy>")])
    except ET.ParseError as error:
        raise AutomationError("ui_unavailable") from error


def _find(root, attribute, value):
    return next((node for node in root.iter() if node.get(attribute) == value), None)


def _tap(node):
    match = BOUNDS_PATTERN.fullmatch(node.get("bounds", ""))
    if match is None:
        raise AutomationError("ui_control_unavailable")
    left, top, right, bottom = (int(value) for value in match.groups())
    _adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))


def _wait_for_controls(timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            root = _dump_ui()
        except AutomationError as error:
            if str(error) not in ("adb_command_failed", "ui_unavailable"):
                raise
            time.sleep(1)
            continue
        turn_signals = _find(root, "resource-id", TURN_SIGNALS_ID)
        horn = _find(root, "resource-id", HORN_ID)
        if turn_signals is not None and horn is not None:
            return root, {"flash": turn_signals, "horn": horn}

        home_control = _find(root, "content-desc", HOME_CONTROL)
        if home_control is not None:
            _tap(home_control)
        time.sleep(1)
    raise AutomationError("vw_app_not_ready")


def _prepare_app():
    if _adb("get-state").strip() != "device":
        raise AutomationError("adb_unavailable")
    _adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    _adb("shell", "wm", "dismiss-keyguard")
    _adb("shell", "cmd", "statusbar", "collapse")
    _adb("shell", "am", "force-stop", "com.volkswagen.weconnect")
    _adb("shell", "am", "start", "-n", APP_ACTIVITY)
    time.sleep(1)
    return _wait_for_controls()


def status():
    _prepare_app()
    return {"status": "ready", "backend": "android-app", "horn_enabled": True}


def run_action(action):
    _, controls = _prepare_app()
    _tap(controls[action])
    time.sleep(1)

    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        root = _dump_ui()
        control_id = TURN_SIGNALS_ID if action == "flash" else HORN_ID
        control = _find(root, "resource-id", control_id)
        if control is None:
            raise AutomationError("vw_app_not_ready")
        if not any(node.get("class") == "android.widget.ProgressBar" for node in control.iter()):
            return {"status": "success", "action": action, "backend": "android-app"}
        time.sleep(2)
    raise AutomationError("vw_command_timeout")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "flash", "horn"))
    action = parser.parse_args().action
    with open(os.path.expanduser("~/.vw-android.lock"), "w", encoding="ascii") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            payload = status() if action == "status" else run_action(action)
        except (AutomationError, subprocess.TimeoutExpired) as error:
            error_code = str(error) if isinstance(error, AutomationError) else "vw_command_timeout"
            print(json.dumps({"status": "error", "error_code": error_code}))
            return 1
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())