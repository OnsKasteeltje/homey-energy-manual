#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Run with sudo: sudo ./install.sh"; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config/install.conf"

echo "[1/11] Host checks"
grep -qi "Raspberry Pi" /proc/device-tree/model 2>/dev/null || echo "WARNING: Raspberry Pi model not detected."
. /etc/os-release
[[ "${ID:-}" == "debian" || "${ID_LIKE:-}" == *debian* ]] || { echo "Unsupported OS: ${PRETTY_NAME:-unknown}"; exit 1; }
dpkg --print-architecture | grep -Eq 'arm64|aarch64' || { echo "64-bit ARM OS required."; exit 1; }

echo "[2/11] Base packages and OS update"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
apt-get install -y ca-certificates curl git unzip openssl

echo "[3/11] Docker"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

echo "[4/11] EMS directories"
install -d -m 0755 "$EMS_ROOT"/{repo,compose,config,bootstrap}
install -d -m 0700 "$EMS_ROOT"/{secrets,backups,data}
cp -a "$SCRIPT_DIR/." "$EMS_ROOT/bootstrap/"
cp "$SCRIPT_DIR/docker/docker-compose.yml" "$EMS_ROOT/compose/docker-compose.yml"
cp "$SCRIPT_DIR/docker/mosquitto.conf" "$EMS_ROOT/compose/mosquitto.conf"
chmod +x "$EMS_ROOT/bootstrap/install.sh" "$EMS_ROOT/bootstrap/verify.sh" "$EMS_ROOT/bootstrap/system/"*.sh

echo "[5/11] Repository"
REPO_DIR="$EMS_ROOT/repo/homey-energy-manual"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone --branch "$EMS_BRANCH" --single-branch "$EMS_REPO" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin "$EMS_BRANCH"
  git -C "$REPO_DIR" checkout "$EMS_BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$EMS_BRANCH"
fi

echo "[6/11] SHADOW environment"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
if [[ ! -f "$ENV_FILE" ]]; then
  DBPASS="$(openssl rand -hex 24)"
  APITOKEN="$(openssl rand -hex 32)"
  cat > "$ENV_FILE" <<EOF
EMS_MODE=SHADOW
TZ=$TZ
POSTGRES_PASSWORD=$DBPASS
EMS_REPO_DIR=$REPO_DIR
MANAGEMENT_API_TOKEN=$APITOKEN
HOMEY_BASE_URL=
HOMEY_TOKEN=
VICTRON_HOST=
EOF
  chmod 0600 "$ENV_FILE"
fi
grep -q '^EMS_MODE=SHADOW$' "$ENV_FILE" || { echo "Refusing install: EMS_MODE must be SHADOW"; exit 1; }
grep -Eq '^MANAGEMENT_API_TOKEN=.{32,}$' "$ENV_FILE" || { echo "Refusing install: management API token missing/too short"; exit 1; }

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$EMS_ROOT/compose/docker-compose.yml")

echo "[7/11] Resolve and record container images"
"$EMS_ROOT/bootstrap/system/capture-image-lock.sh"

echo "[8/11] Infrastructure + migration"
"${COMPOSE[@]}" up -d postgres mosquitto
for i in {1..30}; do
  if "${COMPOSE[@]}" exec -T postgres pg_isready -U ems -d ems >/dev/null 2>&1; then break; fi
  sleep 2
done
"${COMPOSE[@]}" exec -T postgres pg_isready -U ems -d ems >/dev/null
"${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U ems -d ems < "$SCRIPT_DIR/migrations/001_bootstrap.sql"

echo "[9/11] Build/start EMS core + read-only management API in SHADOW"
"${COMPOSE[@]}" up -d --build ems-core management-api

echo "[10/11] Host hardening + backup timer"
"$EMS_ROOT/bootstrap/system/security.sh"
install -m 0644 "$EMS_ROOT/bootstrap/system/ems-backup.service" /etc/systemd/system/ems-backup.service
install -m 0644 "$EMS_ROOT/bootstrap/system/ems-backup.timer" /etc/systemd/system/ems-backup.timer
systemctl daemon-reload
systemctl enable --now ems-backup.timer
"$EMS_ROOT/bootstrap/system/backup.sh"

echo "[11/11] Verification"
"$EMS_ROOT/bootstrap/verify.sh"
