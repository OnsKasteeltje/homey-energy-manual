import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_energy_contract.py"
SPEC = importlib.util.spec_from_file_location("sync_energy_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SyncEnergyContractTests(unittest.TestCase):
    def write_docs(
        self,
        root: Path,
        runtime_version: str,
        canonical_version: str,
        runtime_publisher: str = "EM2_PUBLISHER_V1.0.11",
        canonical_publisher: str | None = None,
    ):
        canonical_publisher = canonical_publisher or runtime_publisher
        runtime = {
            "meta": {
                "schema_version": runtime_version,
                "publisher_version": runtime_publisher,
            }
        }
        schema = {
            "x-frontend-compatible-major": "2",
            "x-frontend-compatible-schema-versions": ["2.10", canonical_version],
            "properties": {
                "meta": {
                    "properties": {
                        "schema_version": {"const": canonical_version},
                        "publisher_version": {"const": canonical_publisher},
                    }
                }
            },
        }
        runtime_path = root / "runtime.json"
        schema_path = root / "schema.json"
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        return runtime_path, schema_path

    def test_forward_minor_is_synchronized(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(Path(tmp), "2.13", "2.12")
            self.assertTrue(MODULE.sync_contract(runtime_path, schema_path))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["properties"]["meta"]["properties"]["schema_version"]["const"],
                "2.13",
            )
            self.assertIn("2.13", schema["x-frontend-compatible-schema-versions"])

    def test_forward_publisher_is_synchronized(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(
                Path(tmp),
                "2.12",
                "2.12",
                runtime_publisher="EM2_PUBLISHER_V1.0.12",
                canonical_publisher="EM2_PUBLISHER_V1.0.11",
            )
            self.assertTrue(MODULE.sync_contract(runtime_path, schema_path))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["properties"]["meta"]["properties"]["publisher_version"]["const"],
                "EM2_PUBLISHER_V1.0.12",
            )

    def test_schema_and_publisher_can_advance_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(
                Path(tmp),
                "2.13",
                "2.12",
                runtime_publisher="EM2_PUBLISHER_V1.1.0",
                canonical_publisher="EM2_PUBLISHER_V1.0.11",
            )
            self.assertTrue(MODULE.sync_contract(runtime_path, schema_path))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            meta = schema["properties"]["meta"]["properties"]
            self.assertEqual(meta["schema_version"]["const"], "2.13")
            self.assertEqual(meta["publisher_version"]["const"], "EM2_PUBLISHER_V1.1.0")

    def test_equal_contract_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(Path(tmp), "2.12", "2.12")
            before = schema_path.read_text(encoding="utf-8")
            self.assertFalse(MODULE.sync_contract(runtime_path, schema_path))
            self.assertEqual(schema_path.read_text(encoding="utf-8"), before)

    def test_major_schema_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(Path(tmp), "3.0", "2.12")
            with self.assertRaises(SystemExit):
                MODULE.sync_contract(runtime_path, schema_path)

    def test_schema_rollback_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(Path(tmp), "2.11", "2.12")
            with self.assertRaises(SystemExit):
                MODULE.sync_contract(runtime_path, schema_path)

    def test_publisher_rollback_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(
                Path(tmp),
                "2.12",
                "2.12",
                runtime_publisher="EM2_PUBLISHER_V1.0.10",
                canonical_publisher="EM2_PUBLISHER_V1.0.11",
            )
            with self.assertRaises(SystemExit):
                MODULE.sync_contract(runtime_path, schema_path)

    def test_publisher_family_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_path, schema_path = self.write_docs(
                Path(tmp),
                "2.12",
                "2.12",
                runtime_publisher="OTHER_PUBLISHER_V1.0.12",
                canonical_publisher="EM2_PUBLISHER_V1.0.11",
            )
            with self.assertRaises(SystemExit):
                MODULE.sync_contract(runtime_path, schema_path)


if __name__ == "__main__":
    unittest.main()
