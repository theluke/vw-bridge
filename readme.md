
# VW SmartThings Bridge

A lightweight Flask API wrapper for
[CarConnectivity](https://github.com/tillsteinbach/CarConnectivity). The bridge
allows local network devices such as a SmartThings Hub to trigger Volkswagen
vehicle actions through simple HTTP GET requests.

> Operational status (2026-08-30): the bridge and Raspberry Pi are healthy and
> the code uses CarConnectivity 0.11.10 with Volkswagen connector 0.10.6. VW
> readiness remains degraded because CARIAD returns HTTP 403 before credentials
> are submitted. See [CarConnectivity migration](docs/CARCONNECTIVITY.md).

## How it Works
The script invokes `carconnectivity-cli` and checks the Volkswagen connector's
advertised writable resources before reporting ready. VW credentials and S-PIN
are passed through an anonymous in-memory file descriptor. They do not appear in
process arguments or a second plaintext configuration file. Token and cache
files remain private under the service working directory (`UMask=0077`).

## Prerequisites
- Raspberry Pi (tested on Pi 4)
- Python 3.11+
- Volkswagen account and 4-digit S-PIN.
- CarConnectivity CLI and Volkswagen connector from `requirements.txt`.

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

The production command mappings are:

```text
/flash -> /garage/<VIN>/commands/honk-flash = flash
/horn  -> /garage/<VIN>/commands/honk-flash = honk-and-flash
```

The honk command has not been live-tested by policy. `/readyz` runs only
`list --setters` and requires this command path to be advertised.

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



