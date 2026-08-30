import subprocess
from unittest.mock import patch

import main


def setup_function():
    main._readiness_cache.update({"checked_at": 0.0, "payload": None})


def test_healthz_is_liveness_only():
    response = main.app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readyz_redacts_vw_authentication_failure():
    failure = subprocess.CompletedProcess(
        [], 1, "", "TokenExpiredError\nKeyError: 'location'"
    )

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=failure
    ):
        response = main.app.test_client().get("/readyz")

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "vw_auth_unavailable"
    assert "KeyError" not in response.get_data(as_text=True)


def test_readyz_caches_successful_probe():
    success = subprocess.CompletedProcess([], 0, main.VW_VIN, "")

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=success
    ) as run_cli:
        first = main.app.test_client().get("/readyz")
        second = main.app.test_client().get("/readyz")

    assert first.status_code == 200
    assert first.get_json()["cached"] is False
    assert second.get_json()["cached"] is True
    run_cli.assert_called_once()


def test_action_returns_stable_error_without_backend_output():
    failure = subprocess.CompletedProcess([], 1, "", "password=secret traceback")

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=failure
    ):
        response = main.app.test_client().get("/flash")

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "vw_command_failed"
    assert "secret" not in response.get_data(as_text=True)