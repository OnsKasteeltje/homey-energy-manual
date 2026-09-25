import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).parents[3] / "services/pi/integrations/github/ev/fetch_deadline_command.py"
spec = importlib.util.spec_from_file_location("deadline_command", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

VALID = {
    "schema": 2,
    "requestId": "req-1",
    "requestedAt": "2026-09-20T06:05:04.734Z",
    "source": "website",
    "active": True,
    "deadline": "2026-09-20T09:00",
    "currentSoc": 88,
    "targetSoc": 95,
    "calibrationKWhPerPercent": 0.62,
    "goalKWh": 3.85,
    "maxA": 8,
}


class TestDeadlineCommandIngress(unittest.TestCase):
    def test_amsterdam_local_deadline_is_valid(self):
        self.assertEqual(m.validate(dict(VALID)), VALID)

    def test_invalid_command_rejected(self):
        bad = dict(VALID, maxA=20)
        with self.assertRaisesRegex(ValueError, "MAX_A_INVALID"):
            m.validate(bad)

    def test_duplicate_request_id_preserves_runtime_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command.json"
            path.write_text(json.dumps(VALID) + "\n")
            before = path.read_bytes()
            with patch.object(m, "fetch", return_value=dict(VALID)):
                status, _ = m.sync(path)
            self.assertEqual(status, "UNCHANGED")
            self.assertEqual(path.read_bytes(), before)

    def test_new_request_is_atomically_published(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command.json"
            path.write_text(json.dumps(VALID) + "\n")
            new = dict(VALID, requestId="req-2")
            with patch.object(m, "fetch", return_value=new):
                status, _ = m.sync(path)
            self.assertEqual(status, "UPDATED")
            self.assertEqual(json.loads(path.read_text())["requestId"], "req-2")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_fetch_failure_preserves_last_valid_command(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command.json"
            path.write_text(json.dumps(VALID) + "\n")
            before = path.read_bytes()
            with patch.object(m, "fetch", side_effect=OSError("network down")):
                with self.assertRaises(OSError):
                    m.sync(path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
