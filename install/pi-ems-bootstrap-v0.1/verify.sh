#!/usr/bin/env bash
set -Eeuo pipefail
EMS_ROOT="${EMS_ROOT:-/opt/ems}"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$EMS_ROOT/compose/docker-compose.yml")
fail=0
check(){ if eval "$2" >/dev/null 2>&1; then printf "PASS  %s\n" "$1"; else printf "FAIL  %s\n" "$1"; fail=1; fi; }

check "EMS mode is SHADOW" "grep -q '^EMS_MODE=SHADOW$' '$ENV_FILE'"
check "Docker daemon active" "systemctl is-active docker"
check "PostgreSQL ready" "${COMPOSE[*]} exec -T postgres pg_isready -U ems -d ems"
check "Mosquitto running" "${COMPOSE[*]} ps --status running mosquitto | grep -q mosquitto"
check "EMS core running" "${COMPOSE[*]} ps --status running ems-core | grep -q ems-core"
check "Management API running" "${COMPOSE[*]} ps --status running management-api | grep -q management-api"
check "Management API token configured" "grep -Eq '^MANAGEMENT_API_TOKEN=.{32,}$' '$ENV_FILE'"
check "Management API localhost health" "curl -fsS http://127.0.0.1:8088/healthz | grep -q '\"write_capability\":false'"
check "Management API not exposed on all interfaces" "ss -ltn | grep ':8088 ' | grep -q '127.0.0.1:8088'"
check "No Homey token configured" "grep -q '^HOMEY_TOKEN=$' '$ENV_FILE'"
check "No Victron host configured" "grep -q '^VICTRON_HOST=$' '$ENV_FILE'"
check "DB schema installed" "${COMPOSE[*]} exec -T postgres psql -U ems -d ems -tAc \"SELECT to_regclass('public.shadow_comparisons') IS NOT NULL\" | grep -q t"
check "UFW active" "ufw status | grep -q '^Status: active'"
check "Unattended upgrades configured" "grep -q 'Unattended-Upgrade.*1' /etc/apt/apt.conf.d/20auto-upgrades"
check "Root SSH login disabled" "sshd -T | grep -q '^permitrootlogin no$'"
check "Backup timer enabled" "systemctl is-enabled ems-backup.timer"
check "Backup timer active" "systemctl is-active ems-backup.timer"
check "At least one backup exists" "find '$EMS_ROOT/backups' -mindepth 1 -maxdepth 1 -type d | grep -q ."
check "Container image lock recorded" "test -s '$EMS_ROOT/config/container-image-lock.txt'"
check "PostgreSQL has no published port" "test -z \"$(${COMPOSE[*]} port postgres 5432 2>/dev/null)\""
check "Mosquitto has no published port" "test -z \"$(${COMPOSE[*]} port mosquitto 1883 2>/dev/null)\""

if [[ $fail -eq 0 ]]; then
  echo "INSTALLATION PASS — hardened offline SHADOW baseline + read-only management API ready."
else
  echo "INSTALLATION FAIL — do not continue to Homey/Victron commissioning."
  exit 1
fi
