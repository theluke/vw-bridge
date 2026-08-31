#!/usr/bin/env bash
set -euo pipefail

target="${VW_DEPLOY_TARGET:-luca@192.168.1.50}"
deploy_dir="${VW_DEPLOY_DIR:-/home/luca/scripts/vw-bridge}"
revision="$(git rev-parse HEAD)"
stage="/tmp/vw-bridge-${revision}"
archive="$(mktemp --suffix=.tar)"
worktree="$(mktemp -d)"

cleanup() {
    rm -f "$archive"
    rm -rf "$worktree"
    ssh -o BatchMode=yes "$target" "rm -rf '$stage'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

git archive --format=tar --output="$archive" "$revision"

ssh -o BatchMode=yes "$target" "rm -rf '$stage' && mkdir -p '$stage'"
tar -xf "$archive" -C "$worktree"
rsync -a "$worktree/" "$target:$stage/"

ssh -o BatchMode=yes "$target" "bash -s" -- "$stage" "$deploy_dir" "$revision" <<'REMOTE'
set -euo pipefail
stage="$1"
deploy_dir="$2"
revision="$3"
backup_root="$HOME/vw-bridge-deploy-backups"
backup="$backup_root/$(date +%Y%m%dT%H%M%S)-$revision"

env_value() {
    sed -n "s/^$1=//p" "$deploy_dir/.env" | tail -n 1
}

deploy_android_script() {
    local adb_path backend boot_recovery key port python_path script target
    backend="$(env_value VW_BACKEND)"
    [[ "$backend" == "android-app" ]] || return 0
    target="$(env_value VW_ANDROID_SSH_TARGET)"
    port="$(env_value VW_ANDROID_SSH_PORT)"
    key="$(env_value VW_ANDROID_SSH_KEY)"
    script="$(env_value VW_ANDROID_SCRIPT)"
    python_path="$(env_value VW_ANDROID_PYTHON)"
    adb_path="$(env_value VW_ANDROID_ADB_PATH)"
    boot_recovery="$(env_value VW_ANDROID_BOOT_RECOVERY)"
    port="${port:-8022}"
    key="${key:-$HOME/.ssh/vw-android}"
    script="${script:-/data/data/com.termux/files/home/vw_android_app.py}"
    python_path="${python_path:-python}"
    adb_path="${adb_path:-adb}"
    boot_recovery="${boot_recovery:-true}"
    ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
        "mkdir -p '$(dirname "$script")'"
    scp -O -q -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -P "$port" \
        "$deploy_dir/vw_android_app.py" "$target:$script"
    if [[ "$boot_recovery" == "true" ]]; then
        ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
            "mkdir -p .termux/boot"
        scp -O -q -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -P "$port" \
            "$deploy_dir/scripts/android-boot.sh" "$target:.termux/boot/vw-bridge.sh"
        ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
            "chmod 700 .termux/boot/vw-bridge.sh"
    else
        scp -O -q -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -P "$port" \
            "$deploy_dir/scripts/router-adb.sh" "$target:$(dirname "$script")/router-adb.sh"
        ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
            "chmod 700 '$(dirname "$script")/router-adb.sh'"
    fi
    ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
        "chmod 700 '$script' && env VW_ANDROID_ADB_PATH='$adb_path' '$python_path' '$script' status" >/dev/null
}

mkdir -p "$backup_root" "$backup"
rsync -a --exclude='.git/' --exclude='.env' --exclude='venv/' "$deploy_dir/" "$backup/"
rsync -a --delete --exclude='.git/' --exclude='.env' --exclude='venv/' "$stage/" "$deploy_dir/"
printf '%s\n' "$revision" > "$deploy_dir/.deployed-revision"

if ! "$deploy_dir/venv/bin/python" -m pip uninstall -q -y weconnect weconnect-cli \
    || ! "$deploy_dir/venv/bin/python" -m pip install -q -r "$deploy_dir/requirements.txt" \
    || ! deploy_android_script \
    || ! sudo install -m 0644 "$deploy_dir/vw-bridge.service" /etc/systemd/system/vw-bridge.service \
    || ! sudo systemctl daemon-reload \
    || ! sudo systemctl restart vw-bridge \
    || ! curl --retry 10 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:5000/healthz >/dev/null; then
    rsync -a --delete --exclude='.git/' --exclude='.env' --exclude='venv/' "$backup/" "$deploy_dir/"
    sudo systemctl daemon-reload
    sudo systemctl restart vw-bridge
    echo "Deployment failed; restored $backup" >&2
    exit 1
fi

printf 'DEPLOYED_SHA=%s\n' "$revision"
curl -sS http://127.0.0.1:5000/readyz || true
REMOTE