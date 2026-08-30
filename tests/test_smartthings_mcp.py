import subprocess
from unittest.mock import patch

import pytest

import smartthings_mcp


def test_read_tool_uses_json_cli():
    completed = subprocess.CompletedProcess([], 0, '[{"name":"Casa"}]', "")

    with patch.object(smartthings_mcp.subprocess, "run", return_value=completed) as run:
        result = smartthings_mcp.list_locations()

    assert result == [{"name": "Casa"}]
    assert run.call_args.args[0][-1] == "--json"


def test_execute_rule_requires_confirmation():
    with pytest.raises(PermissionError, match="confirm=true"):
        smartthings_mcp.execute_rule("83bc847f-1d42-486a-bbf9-505883a418e6")


def test_execute_device_command_validates_payload_before_cli():
    with patch.object(smartthings_mcp.subprocess, "run") as run, pytest.raises(
        ValueError, match="exactly one command"
    ):
        smartthings_mcp.execute_device_command(
            "3a528f45-0939-4e26-a88c-27c3c3e28ca8", "{}", confirm=True
        )

    run.assert_not_called()


def test_execute_device_command_translates_cli_syntax():
    completed = subprocess.CompletedProcess([], 0, "", "")

    with patch.object(
        smartthings_mcp.subprocess, "run", return_value=completed
    ) as run:
        result = smartthings_mcp.execute_device_command(
            "3a528f45-0939-4e26-a88c-27c3c3e28ca8",
            '[{"component":"main","capability":"switch","command":"on"}]',
            confirm=True,
        )

    assert "switch:on" in run.call_args.args[0]
    assert "--json" not in run.call_args.args[0]
    assert result == {"status": "accepted"}


def test_cli_errors_do_not_expose_stderr():
    completed = subprocess.CompletedProcess([], 1, "", "token=secret")

    with patch.object(
        smartthings_mcp.subprocess, "run", return_value=completed
    ), pytest.raises(RuntimeError, match="request failed") as error:
        smartthings_mcp.list_locations()

    assert "secret" not in str(error.value)