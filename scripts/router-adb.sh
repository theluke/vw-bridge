#!/bin/sh
set -eu

root=/opt/alpine-adb
resolved_root="$(readlink -f "$root")"

grep -qs " $resolved_root/dev " /proc/mounts || mount -o bind /dev "$root/dev"
grep -qs " $resolved_root/proc " /proc/mounts || mount -t proc proc "$root/proc"

if [ "${1:-}" = "devices" ]; then
	output="$(busybox chroot "$root" /usr/bin/adb "$@")"
	if ! printf '%s\n' "$output" | grep -Eq '[[:space:]]device([[:space:]]|$)'; then
		busybox chroot "$root" /usr/bin/adb kill-server >/dev/null 2>&1 || true
		busybox chroot "$root" /usr/bin/adb start-server >/dev/null
		output="$(busybox chroot "$root" /usr/bin/adb "$@")"
	fi
	printf '%s\n' "$output"
	exit 0
fi

exec busybox chroot "$root" /usr/bin/adb "$@"