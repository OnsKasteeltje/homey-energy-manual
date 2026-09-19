from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INGEST = ROOT / "services/pi/integrations/homey/ingress/state_ingest.py"


def test_state_ingest_declares_explicit_compatible_schema_versions():
    text = INGEST.read_text(encoding="utf-8")

    assert 'COMPATIBLE_SCHEMA_VERSIONS = {"2.12", "2.13"}' in text
    assert 'meta.get("schema_version") not in COMPATIBLE_SCHEMA_VERSIONS' in text
    assert 'EXPECTED_SCHEMA_VERSION = "2.12"' not in text
