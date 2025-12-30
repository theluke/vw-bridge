
# VW SmartThings Bridge

A lightweight Flask-based API wrapper for the `weconnect-python` library. This bridge allows local network devices (like a SmartThings Hub) to trigger Volkswagen vehicle actions via simple HTTP GET requests.

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
   ./venv/bin/pip install flask weconnect[vimpl] weconnect-cli python-dotenv
   ```

3. **Configure Environment:**
   Create a `.env` file (ignored by git) with your credentials:
   ```text
   VW_USERNAME=your@email.com
   VW_PASSWORD=yourpassword
   VW_SPIN=1234
   ```

## Usage

Start the server:
`./venv/bin/python3 main.py`

### Endpoints
- **Flash Indicators:** `GET http://<PI_IP>:5000/flash`
- **Honk & Flash:** `GET http://<PI_IP>:5000/horn`

## System Integration
To run this as a background service on a Raspberry Pi:

1. Copy the service file:
   `sudo cp vw-bridge.service /etc/systemd/system/`
2. Enable and start:
   ```bash
   sudo systemctl enable vw-bridge
   sudo systemctl start vw-bridge
   ```
