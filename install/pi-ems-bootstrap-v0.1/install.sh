#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Run with sudo: sudo ./install.sh"; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config/install.conf"

echo "[1/8] Host checks"
grep -qi "Raspberry Pi" /proc/device-tree/model 2>/dev/null || echo "WARNING: Raspberry Pi model not detected."
. /etc/os-release
[[ "${ID:-}" == "debian" || "${ID_LIKE:-}" == *debian* ]] || { echo "Unsupported OS: ${PRETTY_NAME:-unknown}"; exit 1; }
dpkg --print-architecture | grep -Eq 'arm64|aarch64' || { echo "64-bit ARM OS required."; exit 1; }

echo "[2/8] Packages"
apt-get update
apt-get install -y ca-certificates curl git unzip openssl

echo "[3/8] Docker"
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

echo "[4/8] EMS directories"
install -d -m 0755 "$EMS_ROOT"/{repo,compose,config,backups,data,bootstrap}
install -d -m 0700 "$EMS_ROOT/secrets"
cp -a "$SCRIPT_DIR/." "$EMS_ROOT/bootstrap/"
cp "$SCRIPT_DIR/docker/docker-compose.yml" "$EMS_ROOT/compose/docker-compose.yml"
cp "$SCRIPT_DIR/docker/mosquitto.conf" "$EMS_ROOT/compose/mosquitto.conf"

echo "[5/8] Repository"
REPO_DIR="$EMS_ROOT/repo/homey-energy-manual"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone --branch "$EMS_BRANCH" --single-branch "$EMS_REPO" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin "$EMS_BRANCH"
  git -C "$REPO_DIR" checkout "$EMS_BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$EMS_BRANCH"
fi

echo "[6/8] SHADOW environment"
ENV_FILE="$EMS_ROOT/secrets/ems.env"
if [[ ! -f "$ENV_FILE" ]]; then
  DBPASS="$(openssl rand -hex 24)"
  cat > "$ENV_FILE" <<EOF
EMS_MODE=SHADOW
TZ=$TZ
POSTGRES_PASSWORD=$DBPASS
EMS_REPO_DIR=$REPO_DIR
HOMEY_BASE_URL=
HOMEY_TOKEN=
VICTRON_HOST=
EOF
  chmod 0600 "$ENV_FILE"
fi
grep -q '^EMS_MODE=SHADOW$' "$ENV_FILE" || { echo "Refusing install: EMS_MODE must be SHADOW"; exit 1; }

COMPOSE="docker compose --env-file $ENV_FILE -f $EMS_ROOT/compose/docker-compose.yml"

echo "[7/8] Infrastructure + migration"
$COMPOSE up -d postgres mosquitto
for i in {1..30}; do
  if $COMPOSE exec -T postgres pg_isready -U ems -d ems >/dev/null 2>&1; then break; fi
  sleep 2
done
$COMPOSE exec -T postgres pg_isready -U ems -d ems >/dev/null
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U ems -d ems < "$SCRIPT_DIR/migrations/001_bootstrap.sql"

echo "[8/8] Build/start EMS core in SHADOW"
$COMPOSE up -d --build ems-core
echo
 echo "Bootstrap complete. Running verification..."
"$EMS_ROOT/bootstrap/verify.sh"
