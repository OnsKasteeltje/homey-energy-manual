#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jeroen/ems/repo/homey-energy-manual"
SCRIPT_DIR="$ROOT_DIR/scripts/pi/connectlife"
PYTHON_BIN="/home/jeroen/ems/tools/connectlife-probe/.venv/bin/python"
STATE_DIR="/home/jeroen/ems/runtime/state"
ENV_DIR="/etc/ems"
ENV_FILE="$ENV_DIR/connectlife.env"
SERVICE_SRC="$SCRIPT_DIR/ems-connectlife-oven.service"
SERVICE_DST="/etc/systemd/system/ems-connectlife-oven.service"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ConnectLife Python venv niet gevonden: $PYTHON_BIN" >&2
  exit 2
fi

if ! "$PYTHON_BIN" -c 'import connectlife' >/dev/null 2>&1; then
  echo "Python package 'connectlife' ontbreekt in $PYTHON_BIN" >&2
  exit 2
fi

if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "Systemd unit ontbreekt: $SERVICE_SRC" >&2
  exit 2
fi

read -r -p "ConnectLife e-mail: " CL_USER
read -r -s -p "ConnectLife wachtwoord: " CL_PASS
echo

if [[ -z "$CL_USER" || -z "$CL_PASS" ]]; then
  echo "E-mail of wachtwoord ontbreekt." >&2
  exit 2
fi

escape_systemd_env() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '"%s"' "$value"
}

tmp_env=$(mktemp)
trap 'rm -f "$tmp_env"' EXIT
chmod 600 "$tmp_env"
{
  printf 'CONNECTLIFE_USERNAME='
  escape_systemd_env "$CL_USER"
  printf '\nCONNECTLIFE_PASSWORD='
  escape_systemd_env "$CL_PASS"
  printf '\n'
} > "$tmp_env"

unset CL_PASS

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

sudo install -d -m 700 -o root -g root "$ENV_DIR"
sudo install -m 600 -o root -g root "$tmp_env" "$ENV_FILE"
sudo install -m 644 -o root -g root "$SERVICE_SRC" "$SERVICE_DST"

sudo systemctl daemon-reload
sudo systemctl enable --now ems-connectlife-oven.service

echo
echo "=== SERVICE ==="
sudo systemctl status ems-connectlife-oven.service --no-pager -l

echo
echo "=== STATE ==="
sleep 2
if [[ -f "$STATE_DIR/oven-state.json" ]]; then
  cat "$STATE_DIR/oven-state.json"
else
  echo "Nog geen statefile; controleer journalctl -u ems-connectlife-oven.service"
fi
