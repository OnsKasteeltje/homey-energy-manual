#!/usr/bin/env bash
set -Eeuo pipefail
EMS_ROOT="${EMS_ROOT:-/opt/ems}"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
COMPOSE="docker compose --env-file $ENV_FILE -f $EMS_ROOT/compose/docker-compose.yml"
fail=0
check(){ if eval "$2" >/dev/null 2>&1; then printf "PASS  %s\n" "$1"; else printf "FAIL  %s\n" "$1"; fail=1; fi; }

check "EMS mode is SHADOW" "grep -q '^EMS_MODE=SHADOW$' '$ENV_FILE'"
check "Docker daemon active" "systemctl is-active docker"
check "PostgreSQL ready" "$COMPOSE exec -T postgres pg_isready -U ems -d ems"
check "Mosquitto running" "$COMPOSE ps --status running mosquitto | grep -q mosquitto"
check "EMS core running" "$COMPOSE ps --status running ems-core | grep -q ems-core"
check "No Homey token configured" "grep -q '^HOMEY_TOKEN=$' '$ENV_FILE'"
check "No Victron host configured" "grep -q '^VICTRON_HOST=$' '$ENV_FILE'"
check "DB schema installed" "$COMPOSE exec -T postgres psql -U ems -d ems -tAc \"SELECT to_regclass('public.shadow_comparisons') IS NOT NULL\" | grep -q t"

if [[ $fail -eq 0 ]]; then
  echo "INSTALLATION PASS — offline SHADOW baseline ready."
else
  echo "INSTALLATION FAIL — do not continue to Homey/Victron commissioning."
  exit 1
fi
