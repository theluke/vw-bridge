#!/bin/sh
set -eu

version="${ALPINE_VERSION:-3.22.1}"
branch="${ALPINE_BRANCH:-v3.22}"
root=/opt/alpine-adb
resolved_root="$(readlink -f "$root")"
archive="alpine-minirootfs-$version-aarch64.tar.gz"
base="https://dl-cdn.alpinelinux.org/alpine/$branch/releases/aarch64"

if [ ! -f "$root/etc/alpine-release" ]; then
    cd /tmp
    wget -q "$base/$archive"
    wget -q "$base/$archive.sha256"
    sha256sum -c "$archive.sha256"
    mkdir -p "$root"
    tar -xzf "$archive" -C "$root"
    rm -f "$archive" "$archive.sha256"
fi

cp /etc/resolv.conf "$root/etc/resolv.conf"
grep -qs " $resolved_root/dev " /proc/mounts || mount -o bind /dev "$root/dev"
grep -qs " $resolved_root/proc " /proc/mounts || mount -t proc proc "$root/proc"
grep -q "/community$" "$root/etc/apk/repositories" || \
    echo "https://dl-cdn.alpinelinux.org/alpine/$branch/community" >> "$root/etc/apk/repositories"

busybox chroot "$root" /sbin/apk update
busybox chroot "$root" /sbin/apk add android-tools