import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _now():
    return datetime.now(timezone.utc).isoformat()


def check_http(name, url):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.load(response)
        if response.status == 200:
            return CheckResult(name, True, payload.get("status", "ok"))
        return CheckResult(name, False, f"HTTP {response.status}")
    except urllib.error.HTTPError as error:
        try:
            payload = json.load(error)
            detail = payload.get("error_code") or f"HTTP {error.code}"
        except (ValueError, AttributeError):
            detail = f"HTTP {error.code}"
        return CheckResult(name, False, detail)
    except (OSError, ValueError) as error:
        return CheckResult(name, False, type(error).__name__)


def check_service(ssh_host):
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                ssh_host,
                "systemctl is-active vw-bridge",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return CheckResult("bridge_service", False, type(error).__name__)
    state = result.stdout.strip() or "ssh_failed"
    return CheckResult("bridge_service", result.returncode == 0 and state == "active", state)


def check_tailscale(hostname):
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return CheckResult("tailscale", False, type(error).__name__)

    peers = payload.get("Peer", {}).values()
    matches = [peer for peer in peers if peer.get("HostName") == hostname]
    if not matches:
        return CheckResult("tailscale", False, "peer_missing")
    if not any(peer.get("Online") for peer in matches):
        return CheckResult("tailscale", False, "peer_offline")
    return CheckResult("tailscale", True, "online")


def run_checks(base_url, ssh_host, tailscale_hostname):
    base_url = base_url.rstrip("/")
    return [
        check_http("bridge_liveness", base_url + "/healthz"),
        check_http("vw_readiness", base_url + "/readyz"),
        check_service(ssh_host),
        check_tailscale(tailscale_hostname),
    ]


def load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "consecutive_failures": 0,
            "incident_open": False,
            "last_alert_epoch": 0,
            "last_success": None,
        }


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def send_alert(subject, body, recipient, sender, msmtp_path):
    message = EmailMessage()
    message["To"] = recipient
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(body)
    subprocess.run(
        [msmtp_path, "--read-envelope-from", recipient],
        input=message.as_bytes(),
        capture_output=True,
        timeout=30,
        check=True,
    )


def update_incident(state, results, threshold, reminder_seconds, now_epoch):
    failed = [result for result in results if not result.ok]
    notification = None
    if failed:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= threshold:
            if not state["incident_open"]:
                state["incident_open"] = True
                notification = "failure"
            elif now_epoch - state["last_alert_epoch"] >= reminder_seconds:
                notification = "reminder"
    else:
        state["consecutive_failures"] = 0
        state["last_success"] = _now()
        if state["incident_open"]:
            state["incident_open"] = False
            notification = "recovery"
    if notification:
        state["last_alert_epoch"] = now_epoch
    return notification, failed


def main():
    base_url = os.getenv("VW_MONITOR_URL", "http://192.168.1.50:5000")
    ssh_host = os.getenv("VW_MONITOR_SSH_HOST", "luca@192.168.1.50")
    tailscale_hostname = os.getenv("VW_MONITOR_TAILSCALE_HOST", "raspi-dns")
    state_path = Path(os.getenv("VW_MONITOR_STATE", "/var/lib/vw-bridge-monitor/state.json"))
    threshold = int(os.getenv("VW_MONITOR_FAILURE_THRESHOLD", "3"))
    reminder_seconds = int(os.getenv("VW_MONITOR_REMINDER_SECONDS", "21600"))
    recipient = os.getenv("ALERT_EMAIL_TO", "")
    sender = os.getenv("ALERT_EMAIL_FROM", recipient)
    msmtp_path = os.getenv("MSMTP_PATH", "/usr/bin/msmtp")

    results = run_checks(base_url, ssh_host, tailscale_hostname)
    state = load_state(state_path)
    notification, _ = update_incident(
        state, results, threshold, reminder_seconds, int(time.time())
    )
    state["checked_at"] = _now()
    state["checks"] = [asdict(result) for result in results]

    if notification and recipient:
        details = "\n".join(
            f"{result.name}: {'OK' if result.ok else result.detail}" for result in results
        )
        subject = f"[VW bridge] {notification} on raspi-dns"
        send_alert(subject, details, recipient, sender, msmtp_path)
    save_state(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())