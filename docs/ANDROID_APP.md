# Official Android app fallback

## Purpose

Volkswagen requires mobile app attestation for command-capable authentication.
The bridge therefore drives the authenticated official Volkswagen app on a
dedicated Samsung A22 rather than extracting tokens or bypassing attestation.

The two actions are deliberately separate:

- `/flash` taps the app resource `turnSignals`.
- `/horn` taps the app resource `hornAndTurnSignals`.

The phone script accepts only `status`, `flash`, and `horn`. Tests assert that
each action taps its own resource. The first lights-only action was physically
verified on 2026-08-30. Horn was not invoked because testing occurred late at
night; it remains available for the existing SmartThings routine.

## Components

- Samsung A22, Android 13, official package `com.volkswagen.weconnect`
- Tailscale address `100.88.221.13`
- ASUSWRT-Merlin router at `192.168.1.1:2223`, with Entware on USB storage
- Router package `python3` and a minimal Alpine runtime with ADB 35
- A data-capable USB connection from the phone to the router
- Pi key `/home/luca/.ssh/vw-router`
- Router script `/opt/share/vw-bridge/vw_android_app.py`
- Termux, Tailscale, and Wireless debugging as a fallback recovery path

The production path is Pi to router over SSH, then router to phone over USB ADB.
The same USB composite connection keeps Samsung USB tethering available as the
router's secondary WAN; Merlin remains configured as `wan usb` in failover mode.
USB ADB does not rotate ports and is available after reboot without a lockscreen
swipe. The phone's Tailscale and Termux services are not in the command path.

Install the router runtime from a checked-out repository, then permanently
approve its fingerprint on the phone:

```bash
ssh -p 2223 admin@192.168.1.1 '/opt/bin/opkg update && /opt/bin/opkg install python3'
ssh -p 2223 admin@192.168.1.1 'sh -s' < scripts/install-router-adb.sh
```

The installer verifies Alpine's published SHA-256 checksum and installs current
`android-tools` in `/opt/alpine-adb`. Entware ADB 1.0.32 must not be used: its
authorization is session-only on Android 13. The deployed `router-adb.sh`
wrapper restores the chroot's `/dev` and `/proc` mounts after router reboot.

## Production environment

```text
VW_BACKEND=android-app
VW_ANDROID_SSH_TARGET=admin@192.168.1.1
VW_ANDROID_SSH_PORT=2223
VW_ANDROID_SSH_KEY=/home/luca/.ssh/vw-router
VW_ANDROID_SCRIPT=/opt/share/vw-bridge/vw_android_app.py
VW_ANDROID_PYTHON=/opt/bin/python3
VW_ANDROID_ADB_PATH=/opt/share/vw-bridge/router-adb.sh
VW_ANDROID_BOOT_RECOVERY=false
```

The standard deploy script copies the committed automation script to the router
using Merlin-compatible legacy SCP and runs only its non-actuating `status`
command before restarting the bridge.
Set `VW_COMMAND_TIMEOUT=90`; the official app can take about one minute to
complete a command, including SSH and UI preparation overhead.

## Phone requirements

1. Keep the phone powered and physically secured.
2. Keep USB debugging enabled and permanently authorize the router's ADB key.
3. Keep the official Volkswagen app logged in.
4. Set **Screen lock type** to **None**, not Swipe. Unattended UI automation
   cannot enter a PIN, and Android may not start ADB before a swipe keyguard is
   dismissed.
5. Exclude Tailscale, Termux, and the Volkswagen app from battery optimization.
6. Keep USB tethering enabled for the router's WAN failover. USB debugging and
   tethering coexist on the Samsung composite USB device.

For fallback access, Tailscale is configured as Android's always-on VPN and
Termux plus Termux:Boot are battery-unrestricted and never sleeping. Samsung
resets fixed `adb tcpip 5555` mode during reboot, and Wireless debugging may not
start automatically, so neither is used for unattended production commands.

## Readiness and monitoring

`/readyz` runs `python vw_android_app.py status` through Pi-to-phone SSH. Status
requires all of the following without sending a vehicle command:

- ADB reports the phone as `device`.
- The Volkswagen app launches while logged in.
- The command details page is reachable.
- Both `turnSignals` and `hornAndTurnSignals` resources are present.

The existing off-device monitor checks `/readyz` every five minutes and alerts
after the configured failure threshold.

## Recovery after reboot

1. Check that the phone is connected to the ASUS router by a data-capable cable
   and that USB tethering remains enabled.
2. On the router, verify
   `/opt/share/vw-bridge/router-adb.sh devices -l` lists the Samsung as `device`.
3. If it is `unauthorized`, accept the phone prompt with **Always allow from
   this computer**. If absent, verify Developer options > USB debugging.
4. Use Termux/Tailscale only if the USB path is unavailable. Open Termux and run
   `sshd`, then inspect `~/android-boot.log`.
5. Enable Android Wireless debugging if fallback ADB is required.
6. In Termux, pair once if required:

   ```bash
   adb pair 127.0.0.1:<pairing-port> <six-digit-code>
   ```

7. Read the main Wireless debugging `IP address & port`, then run:

   ```bash
   adb connect 127.0.0.1:<command-port>
   adb devices -l
   ```

8. If the command port changed, set `VW_ANDROID_ADB_SERIAL` before running the
   phone script or update its configured default and redeploy.
9. Verify the production path from the Pi with status only:

   ```bash
    ssh -i ~/.ssh/vw-router -p 2223 admin@192.168.1.1 \
      env VW_ANDROID_ADB_PATH=/opt/share/vw-bridge/router-adb.sh /opt/bin/python3 \
       /opt/share/vw-bridge/vw_android_app.py status
   ```

Never use `/horn` as a diagnostic probe. Use `/readyz`; test horn only during an
appropriate daytime window with the vehicle observable.