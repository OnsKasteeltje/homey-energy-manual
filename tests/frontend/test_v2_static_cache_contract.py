#!/usr/bin/env python3
"""Static contract for deterministic Frontend V2 asset delivery."""
from pathlib import Path

caddy = Path("deploy/caddy/ems-frontend-v2.Caddyfile").read_text()

assert 'handle /web/* {' in caddy
assert 'reverse_proxy 127.0.0.1:3200' in caddy

static_handle = caddy.split('handle /web/* {', 1)[1].split('handle {', 1)[1].split('}', 1)[0]
assert 'header Cache-Control "no-store"' in static_handle
assert 'file_server' in static_handle

print("PASS: Frontend V2 static assets are served no-store")
