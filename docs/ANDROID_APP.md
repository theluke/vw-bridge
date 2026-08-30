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
- Termux from F-Droid with OpenSSH, Python, and Android platform tools
- Wireless debugging paired locally from Termux to Android ADB
- Pi key `/home/luca/.ssh/vw-android`
- Phone script `/data/data/com.termux/files/home/vw_android_app.py`
- Boot recovery script `~/.termux/boot/vw-bridge.sh`

The phone has no LAN path from the wired hosts because the access point isolates
clients. SSH uses the private Tailscale network. ADB stays entirely inside the
phone at `127.0.0.1:<wireless-debugging-port>`.

## Production environment

```text
VW_BACKEND=android-app
VW_ANDROID_SSH_TARGET=u0_a332@100.88.221.13
VW_ANDROID_SSH_PORT=8022
VW_ANDROID_SSH_KEY=/home/luca/.ssh/vw-android
VW_ANDROID_SCRIPT=/data/data/com.termux/files/home/vw_android_app.py
```

The standard deploy script copies the committed phone script over SSH and runs
only its non-actuating `status` command before restarting the bridge.
Set `VW_COMMAND_TIMEOUT=90`; the official app can take about one minute to
complete a command, including SSH and UI preparation overhead.

## Phone requirements

1. Keep the phone powered and physically secured.
2. Keep Tailscale, Termux SSH, and Wireless debugging enabled.
3. Keep the official Volkswagen app logged in.
4. Use no secure screen lock, because unattended UI automation cannot enter a
   PIN. The bridge wakes the screen and dismisses a swipe keyguard.
5. Exclude Tailscale, Termux, and the Volkswagen app from battery optimization.
6. Disable Samsung automatic restart. A reboot stops Termux SSH and rotates the
   local Wireless-debugging command port. Termux:Boot starts SSH and scans local
   listening ports until the paired ADB service reconnects. Android still needs
   to be unlocked once after a reboot before the app can operate normally.

## Readiness and monitoring

`/readyz` runs `python vw_android_app.py status` through Pi-to-phone SSH. Status
requires all of the following without sending a vehicle command:

- ADB reports the phone as `device`.
- The Volkswagen app launches while logged in.
- The command details page is reachable.
- Both `turnSignals` and `hornAndTurnSignals` resources are present.

The existing off-device monitor checks `/readyz` every five minutes and alerts
after the configured failure threshold.

## Recovery after reboot or port rotation

1. Open Termux and run `sshd`.
2. Enable Android Wireless debugging.
3. In Termux, pair once if required:

   ```bash
   adb pair 127.0.0.1:<pairing-port> <six-digit-code>
   ```

4. Read the main Wireless debugging `IP address & port`, then run:

   ```bash
   adb connect 127.0.0.1:<command-port>
   adb devices -l
   ```

5. If the command port changed, set `VW_ANDROID_ADB_SERIAL` before running the
   phone script or update its configured default and redeploy.
6. Verify from the Pi with status only:

   ```bash
   ssh -i ~/.ssh/vw-android -p 8022 u0_a332@100.88.221.13 \
     python /data/data/com.termux/files/home/vw_android_app.py status
   ```

Never use `/horn` as a diagnostic probe. Use `/readyz`; test horn only during an
appropriate daytime window with the vehicle observable.