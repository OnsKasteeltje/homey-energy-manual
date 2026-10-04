#!/usr/bin/env bash
set -euo pipefail

REPO=/home/jeroen/ems/repo/homey-energy-manual
SYSTEMD=/etc/systemd/system

TIMERS=(
  ems-heating-preheat-shadow.timer
  ems-flex-priority-shadow.timer
  ems-heating-preheat-progression-shadow.timer
  ems-heating-control-gate-shadow.timer
  ems-heating-homey-shadow-publish.timer
)

declare -A WAS_ACTIVE
declare -A WAS_ENABLED

echo "=== HEATING SHADOW CADENCE INSTALL ==="

for timer in "${TIMERS[@]}"; do
  WAS_ACTIVE["$timer"]="$(systemctl is-active "$timer" 2>/dev/null || true)"
  WAS_ENABLED["$timer"]="$(systemctl is-enabled "$timer" 2>/dev/null || true)"
  echo "$timer active=${WAS_ACTIVE[$timer]} enabled=${WAS_ENABLED[$timer]}"
done

echo
echo "=== INSTALL TIMER UNITS ==="
for timer in "${TIMERS[@]}"; do
  sudo install -m 0644 "$REPO/deploy/systemd/$timer" "$SYSTEMD/$timer"
done
sudo systemctl daemon-reload

echo
echo "=== VERIFY INSTALLED CONTRACT ==="
grep -q '^OnCalendar=\*-\*-\* \*:04/5:00$' "$SYSTEMD/ems-heating-preheat-shadow.timer"
grep -q '^AccuracySec=1s$' "$SYSTEMD/ems-heating-preheat-shadow.timer"

grep -q '^OnCalendar=\*-\*-\* \*:\*:10$' "$SYSTEMD/ems-flex-priority-shadow.timer"
grep -q '^AccuracySec=1s$' "$SYSTEMD/ems-flex-priority-shadow.timer"
if grep -q '^OnUnitActiveSec=' "$SYSTEMD/ems-flex-priority-shadow.timer"; then
  echo "ERROR: relative Flex scheduling is still present"
  exit 1
fi

grep -q '^OnCalendar=\*-\*-\* \*:\*:20$' "$SYSTEMD/ems-heating-preheat-progression-shadow.timer"
grep -q '^AccuracySec=1s$' "$SYSTEMD/ems-heating-preheat-progression-shadow.timer"

grep -q '^OnCalendar=\*-\*-\* \*:\*:30$' "$SYSTEMD/ems-heating-control-gate-shadow.timer"
grep -q '^AccuracySec=1s$' "$SYSTEMD/ems-heating-control-gate-shadow.timer"

grep -q '^OnCalendar=\*-\*-\* \*:\*:35$' "$SYSTEMD/ems-heating-homey-shadow-publish.timer"
grep -q '^AccuracySec=1s$' "$SYSTEMD/ems-heating-homey-shadow-publish.timer"

echo "PASS: installed timer definitions match deterministic cadence"

echo
echo "=== RESTART ONLY TIMERS THAT WERE ACTIVE ==="
for timer in "${TIMERS[@]}"; do
  if [[ "${WAS_ACTIVE[$timer]}" == "active" ]]; then
    sudo systemctl restart "$timer"
    echo "restarted $timer"
  else
    echo "left inactive: $timer"
  fi
done

echo
echo "=== PRESERVE ENABLED STATE ==="
for timer in "${TIMERS[@]}"; do
  now_enabled="$(systemctl is-enabled "$timer" 2>/dev/null || true)"
  if [[ "$now_enabled" != "${WAS_ENABLED[$timer]}" ]]; then
    echo "ERROR: enabled state changed for $timer: ${WAS_ENABLED[$timer]} -> $now_enabled"
    exit 1
  fi
done
echo "PASS: enabled/disabled states preserved"

echo
echo "=== NEXT ELAPSE ==="
systemctl list-timers --all --no-pager | grep -E   'ems-heating-preheat-shadow|ems-flex-priority-shadow|ems-heating-preheat-progression-shadow|ems-heating-control-gate-shadow|ems-heating-homey-shadow-publish'

echo
echo "PASS: Heating SHADOW cadence installed"
echo "Expected minute order: V0.3(if due) :00 -> Flex :10 -> V0.4 :20 -> V0.5 :30 -> Publish :35"
echo "NOTE: no Homey/device command was issued by this installer"
