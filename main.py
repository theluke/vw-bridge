import logging
import os
import subprocess
import time
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

VW_USERNAME = os.getenv("VW_USERNAME", "")
VW_PASSWORD = os.getenv("VW_PASSWORD", "")
VW_SPIN = os.getenv("VW_SPIN", "")
VW_VIN = os.getenv("VW_VIN", "WVWZZZAUZLW802874")
VW_CLI_PATH = os.getenv(
    "VW_CLI_PATH", "/home/luca/scripts/vw-bridge/venv/bin/weconnect-cli"
)
VW_COMMAND_TIMEOUT = int(os.getenv("VW_COMMAND_TIMEOUT", "60"))
VW_READY_CACHE_SECONDS = int(os.getenv("VW_READY_CACHE_SECONDS", "300"))

app = Flask(__name__)
_readiness_cache = {"checked_at": 0.0, "payload": None}


def _base_command():
    return [
        VW_CLI_PATH,
        "--username",
        VW_USERNAME,
        "--password",
        VW_PASSWORD,
        "--spin",
        VW_SPIN,
    ]


def _run_cli(arguments, timeout=VW_COMMAND_TIMEOUT):
    return subprocess.run(
        _base_command() + arguments,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _classify_failure(output):
    lowered = output.lower()
    if "tokenexpirederror" in lowered or "keyerror: 'location'" in lowered:
        return "vw_auth_unavailable"
    if "too many requests" in lowered or "429" in lowered:
        return "vw_rate_limited"
    if "timed out" in lowered or "timeout" in lowered:
        return "vw_timeout"
    return "vw_command_failed"


def _configuration_error():
    if not (VW_USERNAME and VW_PASSWORD and VW_SPIN):
        return "vw_credentials_missing"
    if not os.path.isfile(VW_CLI_PATH) or not os.access(VW_CLI_PATH, os.X_OK):
        return "vw_cli_unavailable"
    return None


def check_readiness(force=False):
    now = time.monotonic()
    cached_payload = _readiness_cache["payload"]
    if (
        not force
        and cached_payload is not None
        and now - _readiness_cache["checked_at"] < VW_READY_CACHE_SECONDS
    ):
        return {**cached_payload, "cached": True}

    error_code = _configuration_error()
    if error_code is None:
        try:
            result = _run_cli(["get", "/vehicles"], timeout=min(VW_COMMAND_TIMEOUT, 30))
            if result.returncode != 0:
                error_code = _classify_failure(result.stderr or result.stdout)
            elif VW_VIN not in result.stdout:
                error_code = "vw_vehicle_unavailable"
        except subprocess.TimeoutExpired:
            error_code = "vw_timeout"
        except OSError:
            error_code = "vw_cli_unavailable"

    payload = {
        "status": "ready" if error_code is None else "degraded",
        "ready": error_code is None,
        "error_code": error_code,
        "cached": False,
    }
    _readiness_cache.update({"checked_at": now, "payload": payload})
    return payload


def run_vw_command(action_type):
    attempt_id = str(uuid.uuid4())
    error_code = _configuration_error()
    if error_code is not None:
        return {"status": "error", "error_code": error_code, "attempt_id": attempt_id}, 503

    logger.info("Executing VW action=%s attempt=%s", action_type, attempt_id)
    try:
        result = _run_cli(
            ["set", f"/vehicles/{VW_VIN}/controls/honkAndFlash", action_type]
        )
    except subprocess.TimeoutExpired:
        error_code = "vw_timeout"
    except OSError:
        error_code = "vw_cli_unavailable"
    else:
        if result.returncode == 0:
            _readiness_cache["checked_at"] = 0.0
            logger.info("VW action succeeded action=%s attempt=%s", action_type, attempt_id)
            return {"status": "success", "action": action_type, "attempt_id": attempt_id}, 200
        error_code = _classify_failure(result.stderr or result.stdout)

    logger.error(
        "VW action failed action=%s attempt=%s error_code=%s",
        action_type,
        attempt_id,
        error_code,
    )
    status_code = 429 if error_code == "vw_rate_limited" else 503
    return {
        "status": "error",
        "action": action_type,
        "error_code": error_code,
        "attempt_id": attempt_id,
    }, status_code


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@app.get("/readyz")
def readyz():
    payload = check_readiness()
    return jsonify(payload), 200 if payload["ready"] else 503


@app.get("/horn")
def trigger_horn():
    payload, status_code = run_vw_command("honkandflash")
    return jsonify(payload), status_code


@app.get("/flash")
def trigger_flash():
    payload, status_code = run_vw_command("flash")
    return jsonify(payload), status_code


if __name__ == "__main__":
    app.run(
        host=os.getenv("VW_BRIDGE_HOST", "0.0.0.0"),
        port=int(os.getenv("VW_BRIDGE_PORT", "5000")),
    )