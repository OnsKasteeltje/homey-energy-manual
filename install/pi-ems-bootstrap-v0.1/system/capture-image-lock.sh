#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }
EMS_ROOT="${EMS_ROOT:-/opt/ems}"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$EMS_ROOT/compose/docker-compose.yml")
LOCK="$EMS_ROOT/config/container-image-lock.txt"

"${COMPOSE[@]}" pull postgres mosquitto
{
  echo "# Resolved at bootstrap; promote these RepoDigests into the release package before production freeze."
  echo "resolved_at_utc=$(date -u +%FT%TZ)"
  for image in postgres:16-alpine eclipse-mosquitto:2; do
    digest="$(docker image inspect "$image" --format '{{join .RepoDigests ","}}')"
    printf '%s=%s\n' "$image" "$digest"
  done
} > "$LOCK"
chmod 0644 "$LOCK"
cat "$LOCK"
