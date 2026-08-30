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

mkdir -p "$backup_root" "$backup"
rsync -a --exclude='.git/' --exclude='.env' --exclude='venv/' "$deploy_dir/" "$backup/"
rsync -a --delete --exclude='.git/' --exclude='.env' --exclude='venv/' "$stage/" "$deploy_dir/"

if ! "$deploy_dir/venv/bin/python" -m pip install -q -r "$deploy_dir/requirements.txt" \
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