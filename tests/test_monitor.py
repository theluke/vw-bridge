from pathlib import Path
from unittest.mock import patch

import monitor


def healthy_results():
    return [monitor.CheckResult("bridge", True, "ok")]


def failed_results():
    return [monitor.CheckResult("bridge", False, "HTTP 503")]


def test_incident_alerts_after_threshold_then_recovers():
    state = monitor.load_state(Path("missing-state"))

    notification, _ = monitor.update_incident(state, failed_results(), 2, 60, 100)
    assert notification is None
    notification, _ = monitor.update_incident(state, failed_results(), 2, 60, 101)
    assert notification == "failure"
    notification, _ = monitor.update_incident(state, failed_results(), 2, 60, 120)
    assert notification is None
    notification, _ = monitor.update_incident(state, healthy_results(), 2, 60, 121)
    assert notification == "recovery"


def test_state_is_written_with_private_permissions(tmp_path):
    state_path = tmp_path / "state.json"

    monitor.save_state(state_path, {"incident_open": False})

    assert state_path.stat().st_mode & 0o777 == 0o600


def test_tailscale_requires_named_peer_online():
    completed = type(
        "Result",
        (),
        {"stdout": '{"Peer":{"id":{"HostName":"raspi-dns","Online":false}}}'},
    )()

    with patch.object(monitor.subprocess, "run", return_value=completed):
        result = monitor.check_tailscale("raspi-dns")

    assert result == monitor.CheckResult("tailscale", False, "peer_offline")


def test_readiness_check_allows_android_probe_to_finish():
    with patch.object(
        monitor, "check_http", return_value=healthy_results()[0]
    ) as check_http, patch.object(
        monitor, "check_service", return_value=healthy_results()[0]
    ), patch.object(monitor, "check_tailscale", return_value=healthy_results()[0]):
        monitor.run_checks("http://bridge", "bridge", "tailscale", readiness_timeout=45)

    assert check_http.call_args_list[0].args == (
        "bridge_liveness",
        "http://bridge/healthz",
    )
    assert check_http.call_args_list[1].args == (
        "vw_readiness",
        "http://bridge/readyz",
    )
    assert check_http.call_args_list[1].kwargs == {"timeout": 45}