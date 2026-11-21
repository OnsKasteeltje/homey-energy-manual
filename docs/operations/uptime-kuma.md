# Uptime Kuma — Pi-monitoring (opt-in)

**Status: source-only, not yet deployed.** Existing Kuma container was upgraded
from 2.5.3 to 2.5.12 on 21 November 2026 and subsequently reported healthy.
It has a persistent Docker volume and five previously inventoried monitors:
Homey, Internet – Cloudflare, EMS website, Homey Cloud and EMS Status API.
Their post-upgrade statuses still need dashboard confirmation. Notifications
remain deliberately disabled.

The old container \`uptime-kuma-v253\` and a pre-upgrade volume backup
were preserved. Do not delete either until independently approved.

## First addition: EMS – Forecastketen

This design adds **one** Push monitor, not a second scheduler or Homey poller.

- Canonical source: read-only \`/usr/local/bin/ems-health\` JSON
  (\`EMS_PI_HEALTH_V0.1\`), interpreted locally by
  \`services/pi/health/push_kuma_forecast.py\`.
- Every 5 minutes it checks \`emsFunctions.forecastChain.status\`,
  \`emsData.dynamicPlan.status\`, and \`emsData.wwPlan.status\`.
- All three must be \`OK\` to send \`up\`; otherwise send \`down\` with a
  bounded reason code. The aggregate global EMS health may separately show
  recovered incidents or unrelated degradation.
- If the publisher or Pi stops, Kuma's missing-heartbeat detection applies.
  This single-host installation cannot notify anyone while the Pi is offline.
- No appliance API calls, Homey traffic, planner/actuator writes, extra data
  publishers, public network endpoints or notifications are introduced.
- The push token lives in a root-owned 0600 file on the Pi and is never
  committed or printed. Only the local HTTP loopback endpoint is permitted.

On 21 November 2026, the 20:18 forecast failed due to a 10-second Homey
Logic timeout in the WW-input fetcher. The 20:33 forecast run succeeded.
This is why a successful Kuma website probe is not equivalent to process
health and why a historical failure should not permanently degrade a
recovered forecast.

## Controlled commissioning — after PR review and merge

These are **future operator steps**. The existing Pi deploy must not
automatically enable this optional monitor.

1. Verify the Pi checkout matches the accepted Git revision.
2. In Kuma, create a **Push** monitor named **EMS – Forecastketen**.
   Set the heartbeat interval to **600 seconds** (Pi publishes every
   300 seconds); choose the retry policy deliberately. Do not add
   notification destinations or enable notifications.
3. Copy the generated Push URL privately. Replace only its hostname
   with \`127.0.0.1\`; retain its port \`3001\` and unique token.
   The desired form is \`http://127.0.0.1:3001/api/push/TOKEN\`.
4. Install the versioned script and units in the agreed Pi runtime locations,
   then install the secret file as root with 0600 permissions:

\`\`\`bash
sudo install -D -m 0644 services/pi/health/push_kuma_forecast.py \
  /home/jeroen/ems/runtime/health/push_kuma_forecast.py
sudo install -m 0644 deploy/systemd/ems-kuma-forecast-push.service \
  /etc/systemd/system/ems-kuma-forecast-push.service
sudo install -m 0644 deploy/systemd/ems-kuma-forecast-push.timer \
  /etc/systemd/system/ems-kuma-forecast-push.timer
sudo install -d -m 0700 /etc/ems
sudo install -m 0600 /dev/null /etc/ems/kuma-forecast.env
# Edit the root-owned file securely. Its content must be:
# KUMA_PUSH_URL="http://127.0.0.1:3001/api/push/<PRIVATE_TOKEN>"
sudo systemctl daemon-reload
sudo systemctl enable --now ems-kuma-forecast-push.timer
\`\`\`

Do not enable the timer until the real private push URL is installed. Never
paste that URL into public GitHub, chat, or debugging output. Review the
existing runtime structure and drift guard before copying deployment files.

## Validation (no failure injection on the production EMS)

\`\`\`bash
python3 -m unittest discover -s tests/health -v
systemctl status ems-kuma-forecast-push.timer --no-pager
journalctl -u ems-kuma-forecast-push.service -n 20 --no-pager
/usr/local/bin/ems-health
\`\`\`

Require successful first push, a fresh **UP** in Kuma when all three fields
are \`OK\`, and confirm the five original monitors remain intact. A missing
heartbeat and an explicit \`down\` are separate diagnosis cases: first
check the local canonical health, then publisher journal, then Kuma history.
Verify DOWN mapping with offline mock tests, not induced production faults.

## Stop and recovery

\`\`\`bash
sudo systemctl disable --now ems-kuma-forecast-push.timer
\`\`\`

Pause the newly added Push monitor in Kuma while disabled. Do not touch the
original monitors, database, volume, Homey flows or forecast timer. Retain
the backup and do not remove the secret until a deliberate secret-retirement
decision. An optional monitoring deployment never proves itself healthy from
GitHub source alone; require Pi and Kuma runtime readback.

## Future candidates, separately validated

P1 freshness, AlphaESS read-only Modbus, Victron phase quality, Quatt,
Honeywell, EV control evidence and Pi hardware can be considered in later
changes using existing canonical evidence. Do not add separate Homey polling.
