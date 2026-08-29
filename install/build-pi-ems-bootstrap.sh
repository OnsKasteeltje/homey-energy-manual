#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="$ROOT/install/pi-ems-bootstrap-v0.1"
OUT_DIR="${1:-$ROOT/dist}"
ZIP="$OUT_DIR/pi-ems-bootstrap-v0.1.zip"
SHA="$ZIP.sha256"

mkdir -p "$OUT_DIR"
rm -f "$ZIP" "$SHA"
(
  cd "$ROOT/install"
  zip -r -X "$ZIP" pi-ems-bootstrap-v0.1 >/dev/null
)
sha256sum "$ZIP" > "$SHA"
echo "Created: $ZIP"
echo "Checksum: $SHA"
