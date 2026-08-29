#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }
EMS_ROOT="${EMS_ROOT:-/opt/ems}"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
BACKUP_ROOT="$EMS_ROOT/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_ROOT/$STAMP"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$EMS_ROOT/compose/docker-compose.yml")

install -d -m 0700 "$DEST"

"${COMPOSE[@]}" exec -T postgres pg_dump -U ems -d ems -Fc > "$DEST/ems-postgres.dump"
cp -a "$EMS_ROOT/config" "$DEST/config" 2>/dev/null || true
install -m 0600 "$ENV_FILE" "$DEST/ems.env"
git -C "$EMS_ROOT/repo/homey-energy-manual" rev-parse HEAD > "$DEST/git-commit.txt"
docker compose version > "$DEST/docker-compose-version.txt"
docker version --format '{{.Server.Version}}' > "$DEST/docker-engine-version.txt"
"${COMPOSE[@]}" images --format json > "$DEST/container-images.json" 2>/dev/null || "${COMPOSE[@]}" images > "$DEST/container-images.txt"

sha256sum "$DEST"/* > "$DEST/SHA256SUMS" 2>/dev/null || true
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
chmod -R go-rwx "$DEST"
echo "Backup created: $DEST"
