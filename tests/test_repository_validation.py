import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_repository", ROOT / "scripts" / "validate_repository.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RepositoryValidationTests(unittest.TestCase):
    def test_load_json_accepts_valid_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ok.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            self.assertEqual(MODULE.load_json(path), {"ok": True})

    def test_require_rejects_missing_field(self):
        with self.assertRaises(SystemExit):
            MODULE.require({}, "missing", str, "root")

    def test_require_rejects_wrong_type(self):
        with self.assertRaises(SystemExit):
            MODULE.require({"value": "1"}, "value", int, "root")


if __name__ == "__main__":
    unittest.main()
