# Private Caddy ingress and reboot resilience

`ems-frontend-v2.Caddyfile` binds the private website to the Pi Tailnet
address (`100.127.130.0`), not to LAN or wildcard interfaces.

The canonical systemd retry override is stored at
`deploy/systemd-dropins/caddy.service.d/10-tailscale-retry.conf`.
This file matches the drop-in first installed on the Pi on 16 October 2026.
After an unplanned shutdown, systemd may start Caddy before Tailscale has
assigned the IP. `After=tailscaled.service` orders daemon startup, while
`Restart=on-failure` and `RestartSec=10s` retry the bind until the address
is present. No new listener or other network exposure is introduced.

The official `scripts/deploy_ems_pi.sh` backs up the existing host override,
installs the versioned file into
`/etc/systemd/system/caddy.service.d/10-tailscale-retry.conf`, and runs
`systemctl daemon-reload` **without restarting the running Caddy service**.
`scripts/ems_pi_drift_check.sh` compares the host override to this Git file.
The main Caddyfile is managed separately; this addition does not install or
change it.

Read-only verification after deployment:

```bash
systemctl show caddy -p Restart -p RestartUSec -p After
systemctl is-active caddy
curl --noproxy "*" -sS --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://100.127.130.0/live/
```

If Caddy is failed after Tailscale is reachable, run
`sudo systemctl reset-failed caddy && sudo systemctl restart caddy`.
Do not change Homey, the planner or the website APIs to resolve this
bind-ordering issue.
