#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="/var/www/ems-frontend-v2"

if [[ ! -f "$ROOT/frontend/live/index.html" ]]; then
  echo "Frontend V2 source missing" >&2
  exit 1
fi

sudo install -d -o root -g root -m 0755 "$TARGET"
sudo rsync -a --delete --chmod=D755,F644 "$ROOT/frontend/" "$TARGET/"
sudo chown -R root:root "$TARGET"
sudo install -D -m 0644 "$ROOT/deploy/caddy/ems-frontend-v2.Caddyfile" /etc/caddy/Caddyfile

echo "Staged Frontend V2 in $TARGET"
echo "Installed Caddy config. Validate with: sudo caddy validate --config /etc/caddy/Caddyfile"
echo "This script does not install, enable, or restart Caddy and does not configure Tailscale Serve."
