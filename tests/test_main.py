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
        [], 1, "", "Authorization URL could not be fetched due to WeConnect failure"
    )

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=failure
    ):
        response = main.app.test_client().get("/readyz")

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "vw_auth_unavailable"
    assert "Authorization URL" not in response.get_data(as_text=True)


def test_readyz_caches_successful_probe():
    setter = f"/garage/{main.VW_VIN}/commands/honk-flash"
    success = subprocess.CompletedProcess([], 0, setter, "")

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


def test_flash_uses_carconnectivity_lights_only_command():
    success = subprocess.CompletedProcess([], 0, "", "")

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=success
    ) as run_cli:
        response = main.app.test_client().get("/flash")

    assert response.status_code == 200
    run_cli.assert_called_once_with(
        ["set", f"/garage/{main.VW_VIN}/commands/honk-flash", "flash"]
    )


def test_horn_uses_combined_command():
    success = subprocess.CompletedProcess([], 0, "", "")

    with patch.object(main, "_configuration_error", return_value=None), patch.object(
        main, "_run_cli", return_value=success
    ) as run_cli:
        response = main.app.test_client().get("/horn")

    assert response.status_code == 200
    run_cli.assert_called_once_with(
        ["set", f"/garage/{main.VW_VIN}/commands/honk-flash", "honk-and-flash"]
    )


def test_cli_command_does_not_expose_credentials():
    command = main._base_command("/proc/self/fd/7")

    assert main.VW_USERNAME not in command
    assert main.VW_PASSWORD not in command
    assert main.VW_SPIN not in command
    assert command[-1] == "/proc/self/fd/7"


def test_android_readyz_checks_phone_status():
    success = subprocess.CompletedProcess(
        [], 0, '{"status": "ready", "backend": "android-app"}', ""
    )

    with patch.object(main, "VW_BACKEND", "android-app"), patch.object(
        main, "_configuration_error", return_value=None
    ), patch.object(main, "_run_android", return_value=success) as run_android:
        response = main.app.test_client().get("/readyz")

    assert response.status_code == 200
    run_android.assert_called_once_with("status", timeout=30)


def test_android_flash_uses_lights_only_action():
    success = subprocess.CompletedProcess([], 0, '{"status": "success"}', "")

    with patch.object(main, "VW_BACKEND", "android-app"), patch.object(
        main, "_configuration_error", return_value=None
    ), patch.object(main, "_run_android", return_value=success) as run_android:
        response = main.app.test_client().get("/flash")

    assert response.status_code == 200
    run_android.assert_called_once_with("flash")


def test_android_horn_uses_separate_remote_action():
    success = subprocess.CompletedProcess([], 0, '{"status": "success"}', "")

    with patch.object(main, "VW_BACKEND", "android-app"), patch.object(
        main, "_configuration_error", return_value=None
    ), patch.object(main, "_run_android", return_value=success) as run_android:
        response = main.app.test_client().get("/horn")

    assert response.status_code == 200
    run_android.assert_called_once_with("horn")