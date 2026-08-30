
# VW SmartThings Bridge

A lightweight Flask-based API wrapper for the `weconnect-python` library. This bridge allows local network devices (like a SmartThings Hub) to trigger Volkswagen vehicle actions via simple HTTP GET requests.

> Operational status (2026-08-30): the bridge and Raspberry Pi are healthy, but
> VW readiness is degraded. CARIAD returns HTTP 403 without the redirect required
> by `weconnect` 0.60.11 and current upstream `main`. `/readyz` reports
> `vw_auth_unavailable` until the upstream client adopts a supported login flow.

## How it Works
The script acts as a **CLI Wrapper**. Instead of relying on the complex and sometimes unstable internal object tree of the `weconnect` library, it executes surgical `weconnect-cli` commands via Python's `subprocess` module. 

This approach was chosen because:
1. **Stability:** The CLI `set` command is more resilient to partial VW server failures (500 errors) than the full library `update()` method.
2. **Version Independence:** It avoids issues with changing library attributes across different vehicle models (e.g., Golf GTE vs ID series).
3. **Simplicity:** It translates a standard HTTP GET into a validated terminal command.

## Prerequisites
- Raspberry Pi (tested on Pi 4)
- Python 3.11+
- Volkswagen WeConnect subscription and 4-digit S-PIN.
- `weconnect-cli` installed within the local virtual environment.

## Installation

1. **Clone the repo:**
   ```bash
   git clone https://github.com/theluke/vw-bridge.git
   cd vw-bridge
   ```

2. **Setup Virtual Environment:**
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ./venv/bin/pip install weconnect-cli
   ```

3. **Configure Environment:**
   Create a `.env` file (ignored by git) with your credentials:
   ```text
   VW_USERNAME=your@email.com
   VW_PASSWORD=yourpassword
   VW_SPIN=1234
   VW_VIN=your-vin
   ```

## Usage

Start the server:
`./venv/bin/python3 main.py`

### Endpoints
- **Flash Indicators:** `GET http://<PI_IP>:5000/flash`
- **Honk & Flash:** `GET http://<PI_IP>:5000/horn`
- **Liveness:** `GET http://<PI_IP>:5000/healthz`
- **VW readiness:** `GET http://<PI_IP>:5000/readyz`

Action failures return stable error codes and request IDs. Backend tracebacks and
credentials are not returned to callers. Readiness is cached and never flashes or
honks the vehicle.

## System Integration
To run this as a background service on a Raspberry Pi:

1. Copy the service file:
   `sudo cp vw-bridge.service /etc/systemd/system/`
2. Enable and start:
   ```bash
   sudo systemctl enable vw-bridge
   sudo systemctl start vw-bridge
   ```

## Monitoring

The monitor runs on `192.168.1.110`, not the Pi, so Pi/network outages remain
observable. It checks bridge liveness, read-only VW readiness, the Pi systemd
service over SSH, and Tailscale peer state every five minutes. After three failed
runs it sends one alert through the host's existing `msmtp` configuration, then a
recovery message when all checks pass.

Configuration is stored at `/etc/vw-bridge-monitor.env`; state is private under
`/var/lib/vw-bridge-monitor`. Inspect it with:

```bash
systemctl list-timers vw-bridge-monitor.timer
journalctl -u vw-bridge-monitor.service
```

## SmartThings Agent Access

The official SmartThings CLI is installed at `~/.local/bin/smartthings`. The
workspace MCP server in `.vscode/mcp.json` uses an isolated OAuth profile and
provides read tools for locations, devices, health/history, Rules, and Scenes.
Execution tools require `confirm=true`; no delete tool is exposed. The temporary
PAT in `~/st-token.md` is bootstrap-only and must be revoked and removed after
OAuth is verified.

The API currently exposes the `Casa` location, 96 devices, and two unrelated
Scenes, but zero Rules. The SmartThings app routines controlling `Golf Flash`,
`Golf HORN`, and `query master` therefore cannot be edited through the Rules API;
diagnosis uses their device history and changes are made in the SmartThings app.

## Deployment

CI runs pytest and Ruff on every push and pull request. From a clean committed
checkout, deploy the exact revision with:

```bash
scripts/deploy.sh
```

The script preserves the Pi-only `.env` and virtualenv, backs up the previous
source, waits for `/healthz`, and rolls back if startup fails.



