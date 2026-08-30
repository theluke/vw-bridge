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

deploy_phone_script() {
    local backend target port key script
    backend="$(env_value VW_BACKEND)"
    [[ "$backend" == "android-app" ]] || return 0
    target="$(env_value VW_ANDROID_SSH_TARGET)"
    port="$(env_value VW_ANDROID_SSH_PORT)"
    key="$(env_value VW_ANDROID_SSH_KEY)"
    script="$(env_value VW_ANDROID_SCRIPT)"
    port="${port:-8022}"
    key="${key:-$HOME/.ssh/vw-android}"
    script="${script:-/data/data/com.termux/files/home/vw_android_app.py}"
    ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
        "mkdir -p .termux/boot"
    scp -q -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -P "$port" \
        "$deploy_dir/vw_android_app.py" "$target:$script"
    scp -q -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -P "$port" \
        "$deploy_dir/scripts/android-boot.sh" "$target:.termux/boot/vw-bridge.sh"
    ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -p "$port" "$target" \
        "chmod 700 '$script' .termux/boot/vw-bridge.sh && python '$script' status" >/dev/null
}

mkdir -p "$backup_root" "$backup"
rsync -a --exclude='.git/' --exclude='.env' --exclude='venv/' "$deploy_dir/" "$backup/"
rsync -a --delete --exclude='.git/' --exclude='.env' --exclude='venv/' "$stage/" "$deploy_dir/"

if ! "$deploy_dir/venv/bin/python" -m pip uninstall -q -y weconnect weconnect-cli \
    || ! "$deploy_dir/venv/bin/python" -m pip install -q -r "$deploy_dir/requirements.txt" \
    || ! deploy_phone_script \
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

printf '%s\n' "$revision" > "$deploy_dir/.deployed-revision"
printf 'DEPLOYED_SHA=%s\n' "$revision"
curl -sS http://127.0.0.1:5000/readyz || true
REMOTE