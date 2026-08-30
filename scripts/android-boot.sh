#!/data/data/com.termux/files/usr/bin/bash

set -u

log="$HOME/android-boot.log"
exec >>"$log" 2>&1
printf '%s starting Android bridge recovery\n' "$(date -Iseconds)"

termux-wake-lock || true
sshd
adb start-server

for attempt in $(seq 1 30); do
    while read -r port; do
        adb connect "127.0.0.1:$port" >/dev/null 2>&1 || true
        if adb devices | grep -Eq "^127\.0\.0\.1:$port[[:space:]]+device$"; then
            printf '%s connected local ADB on port %s\n' "$(date -Iseconds)" "$port"
            exit 0
        fi
    done < <(python - <<'PY'
import concurrent.futures
import socket


def is_open(port):
    sock = socket.socket()
    sock.settimeout(0.05)
    try:
        return port if sock.connect_ex(("127.0.0.1", port)) == 0 else None
    finally:
        sock.close()


with concurrent.futures.ThreadPoolExecutor(max_workers=128) as executor:
    for port in executor.map(is_open, range(30000, 50001)):
        if port is not None:
            print(port)
PY
    )
    sleep 2
done

printf '%s local ADB recovery failed\n' "$(date -Iseconds)"
exit 1