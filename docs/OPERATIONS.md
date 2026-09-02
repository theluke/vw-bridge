# Production operations

## Topology

```text
SmartThings routine
  -> Raspberry Pi 192.168.1.50:5000
  -> SSH admin@192.168.1.1:2223
  -> ASUSWRT-Merlin router
  -> modern ADB 35.0.2 in /opt/alpine-adb
  -> USB Samsung A22
  -> official Volkswagen app
  -> vehicle
```

The Samsung USB composite connection provides both ADB and router WAN failover.
The router is configured as `wans_dualwan=wan usb`, `wans_mode=fb`, with `usb0`
as the USB modem. Do not replace USB mode with charge-only or file-transfer-only
mode.

## Fixed identities and paths

- Production bridge host: `luca@192.168.1.50`
- Router SSH: `admin@192.168.1.1:2223`
- Pi router key: `/home/luca/.ssh/vw-router`
- Router automation: `/opt/share/vw-bridge/vw_android_app.py`
- Router ADB wrapper: `/opt/share/vw-bridge/router-adb.sh`
- Router Python: `/opt/bin/python3`
- Alpine ADB root: `/opt/alpine-adb`
- Phone: Samsung A22, Android 13, serial `R9AT207QMYD`
- Volkswagen app: `com.volkswagen.weconnect`
- Phone fallback Tailscale IP: `100.88.221.13`
- Phone fallback SSH: `u0_a332@100.88.221.13:8022`

## SmartThings controls

- `Golf Flash`: `3a528f45-0939-4e26-a88c-27c3c3e28ca8`
- `Golf HORN`: `74ff6a7e-dafb-4eb6-a688-63ba4e850532`

Both are `virtual-switch-mirror` devices. The routines turn their switch back
off after execution. Confirm the label and current state before sending any
command. Never use the horn as a diagnostic probe.

## Safe checks

These checks do not actuate the vehicle:

```bash
ssh luca@192.168.1.50 'curl -sS http://127.0.0.1:5000/readyz'

ssh -p 2223 admin@192.168.1.1 \
  '/opt/share/vw-bridge/router-adb.sh devices -l'

ssh -p 2223 admin@192.168.1.1 \
  'env VW_ANDROID_ADB_PATH=/opt/share/vw-bridge/router-adb.sh \
  /opt/bin/python3 /opt/share/vw-bridge/vw_android_app.py status'
```

Expected results are HTTP 200 with `"ready":true`, an ADB device state of
`device`, and app status `"status":"ready"`.

Each status or action preparation force-stops and relaunches the Volkswagen app
before locating controls. This recovers stale connection-error screens without
triggering flash or horn. The monitor gives `/readyz` 45 seconds to complete;
override this only with `VW_MONITOR_READY_TIMEOUT` on the monitoring host.

## Reboot recovery

The phone screen-lock type must be **None**, USB debugging must remain enabled,
and the router fingerprint must be permanently authorized. After phone reboot,
the ADB wrapper restarts the daemon once if Samsung re-enumerates USB without
appearing in the existing daemon. No unlock or fingerprint prompt is expected.

If readiness is degraded:

1. Verify the cable and that `lsusb` on the router shows Samsung `04e8:6864`.
2. Run `router-adb.sh devices -l`; `unauthorized` requires physical approval.
3. Verify `nvram get usb_modem_act_dev` is `usb0` and do not alter dual-WAN.
4. Run the status-only automation command above.
5. Use Termux/Tailscale fallback only if USB access is unavailable.

Entware ADB 1.0.32 is incompatible with persistent Android 13 authorization.
Use the checked, Alpine-hosted ADB 35 runtime installed by
`scripts/install-router-adb.sh`.

## Deployment and validation

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check main.py monitor.py smartthings_mcp.py vw_android_app.py tests
bash -n scripts/deploy.sh scripts/android-boot.sh
sh -n scripts/router-adb.sh scripts/install-router-adb.sh
scripts/deploy.sh
```

Deployment copies the exact committed revision to the Pi and router, runs
non-actuating status first, restarts `vw-bridge.service`, and checks liveness.
The deployed SHA is stored at
`/home/luca/scripts/vw-bridge/.deployed-revision` on the Pi.

## Known command caveat

The official app can physically complete an action before its progress UI
settles. A verified SmartThings flash on 2026-08-31 worked physically and reset
its virtual switch, but the bridge returned `vw_timeout` after about 52 seconds.
Treat timeout as indeterminate and inspect the vehicle/routine state. Never
automatically retry flash or horn after a timeout.