import json
import os
import subprocess
import uuid

from mcp.server.fastmcp import FastMCP

SMARTTHINGS_CLI = os.getenv("SMARTTHINGS_CLI", "/home/luca/.local/bin/smartthings")
CLI_TIMEOUT = int(os.getenv("SMARTTHINGS_CLI_TIMEOUT", "45"))

mcp = FastMCP("SmartThings")


def _validate_id(value, name):
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{name} must be a UUID") from error


def _run_cli(*arguments, json_output=True):
    command = [SMARTTHINGS_CLI, *arguments]
    if json_output:
        command.append("--json")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("SmartThings CLI request failed")
    if not json_output:
        return {"status": "accepted"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("SmartThings CLI returned invalid JSON") from error


def _require_confirmation(confirm):
    if confirm is not True:
        raise PermissionError("This operation requires confirm=true")


@mcp.tool()
def list_locations():
    """List SmartThings locations."""
    return _run_cli("locations")


@mcp.tool()
def list_devices():
    """List SmartThings devices available to the authorized account."""
    return _run_cli("devices")


@mcp.tool()
def get_device_status(device_id: str):
    """Read all current capability values for a SmartThings device."""
    return _run_cli("devices:status", _validate_id(device_id, "device_id"))


@mcp.tool()
def get_device_health(device_id: str):
    """Read the SmartThings health state for a device."""
    return _run_cli("devices:health", _validate_id(device_id, "device_id"))


@mcp.tool()
def get_device_history(device_id: str):
    """Read recent SmartThings history for a device."""
    return _run_cli("devices:history", _validate_id(device_id, "device_id"))


@mcp.tool()
def list_rules():
    """List SmartThings Rules visible to the authorized CLI integration."""
    return _run_cli("rules")


@mcp.tool()
def list_scenes():
    """List SmartThings Scenes visible to the authorized CLI integration."""
    return _run_cli("scenes")


@mcp.tool()
def execute_rule(rule_id: str, confirm: bool = False):
    """Execute a Rule only after the user explicitly confirms the operation."""
    _require_confirmation(confirm)
    return _run_cli(
        "rules:execute", _validate_id(rule_id, "rule_id"), json_output=False
    )


@mcp.tool()
def execute_scene(scene_id: str, confirm: bool = False):
    """Execute a Scene only after the user explicitly confirms the operation."""
    _require_confirmation(confirm)
    return _run_cli(
        "scenes:execute", _validate_id(scene_id, "scene_id"), json_output=False
    )


@mcp.tool()
def execute_device_command(device_id: str, command_json: str, confirm: bool = False):
    """Execute a validated device command only after explicit user confirmation."""
    _require_confirmation(confirm)
    device_id = _validate_id(device_id, "device_id")
    try:
        command = json.loads(command_json)
    except json.JSONDecodeError as error:
        raise ValueError("command_json must be valid JSON") from error
    if not isinstance(command, list) or len(command) != 1:
        raise ValueError("command_json must contain exactly one command")
    item = command[0]
    if not isinstance(item, dict) or not all(item.get(key) for key in ("capability", "command")):
        raise ValueError("command requires capability and command")
    component = item.get("component", "main")
    prefix = "" if component == "main" else f"{component}:"
    command_spec = f"{prefix}{item['capability']}:{item['command']}"
    arguments = item.get("arguments", [])
    if arguments:
        if not isinstance(arguments, list):
            raise ValueError("command arguments must be a list")
        rendered = ",".join(json.dumps(argument) for argument in arguments)
        command_spec += f"({rendered})"
    return _run_cli(
        "devices:commands", device_id, command_spec, json_output=False
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")