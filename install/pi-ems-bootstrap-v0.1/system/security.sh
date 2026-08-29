#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }

apt-get install -y unattended-upgrades ufw

cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Conservative SSH hardening: do not change authentication method during bootstrap.
install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/90-ems-hardening.conf <<'EOF'
PermitRootLogin no
X11Forwarding no
MaxAuthTries 5
LoginGraceTime 30
EOF
sshd -t
systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true

# Keep SSH reachable before enabling a default-deny host firewall.
SSH_PORT="$(sshd -T 2>/dev/null | awk '$1=="port" {print $2; exit}')"
SSH_PORT="${SSH_PORT:-22}"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment 'SSH'
ufw --force enable

echo "Host hardening applied: unattended security upgrades, conservative SSH policy, UFW default-deny incoming."
