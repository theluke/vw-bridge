#!/bin/sh
set -eu

root=/opt/alpine-adb
resolved_root="$(readlink -f "$root")"

grep -qs " $resolved_root/dev " /proc/mounts || mount -o bind /dev "$root/dev"
grep -qs " $resolved_root/proc " /proc/mounts || mount -t proc proc "$root/proc"

exec busybox chroot "$root" /usr/bin/adb "$@"