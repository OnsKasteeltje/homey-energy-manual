#!/usr/bin/env python3
"""Offline, standalone contract checks for the local Pi deadline command ingress."""
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "tesla_command_ingest", ROOT / "services/pi/api/status/tesla_command_ingest.py"
)
ingress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingress)
BSPEC = importlib.util.spec_from_file_location(
    "ev_deadline_builder", ROOT / "services/pi/state/ev/deadline/build_deadline_state.py"
)
builder = importlib.util.module_from_spec(BSPEC)
BSPEC.loader.exec_module(builder)

NOW = datetime(2026, 10, 9, 10, 20, tzinfo=timezone.utc)
INTENT = dict(active=True, deadline="2026-10-09T13:00", currentSoc=90,
              targetSoc=100, maxA=10)


class Validation(unittest.TestCase):
    def test_deadline_browser_timezone_is_not_reinterpreted(self):
        state_js=(ROOT / "frontend/settings/state/settings-state.js").read_text()
        ctrl_js=(ROOT / "frontend/settings/control/tesla-deadline.js").read_text()
        self.assertIn('if(/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$/.test(v))return v;', state_js)
        self.assertNotIn('new Date(v.deadline)', ctrl_js)
        self.assertIn('browser time zones can differ', ctrl_js)

    def test_one_tailnet_website_listener(self):
        cfg=(ROOT / "deploy/caddy/ems-frontend-v2.Caddyfile").read_text()
        self.assertIn("http://100.127.130.0 {", cfg)
        self.assertIn("    bind 100.127.130.0", cfg)
        self.assertNotIn("http://192.168.1.42", cfg)
        self.assertNotIn("bind 192.168.1.42", cfg)
        self.assertNotIn("0.0.0.0", cfg)
        self.assertIn("reverse_proxy 127.0.0.1:3200", cfg)
        self.assertIn("reverse_proxy 127.0.0.1:3100", cfg)

    def test_valid_intent(self):
        d = ingress.validate_intent(INTENT, NOW)
        self.assertEqual((d["goalKWh"], d["maxA"]), (6.2, 10))

    def test_zero_soc(self):
        d = dict(INTENT, currentSoc=0)
        self.assertEqual(ingress.validate_intent(d, NOW)["goalKWh"], 62.0)

    def test_cancel_without_soc_or_deadline(self):
        d = ingress.validate_intent({"active": False}, NOW)
        self.assertEqual(d["goalKWh"], 0.0)
        self.assertEqual(d["deadline"], "")

    def test_expired_deadline_denied(self):
        with self.assertRaisesRegex(ValueError, "DEADLINE_NOT_IN_FUTURE"):
            ingress.validate_intent(dict(INTENT, deadline="2026-10-09T12:00"), NOW)

    def test_soc_equal_denied(self):
        with self.assertRaisesRegex(ValueError, "TARGET_SOC_INVALID"):
            ingress.validate_intent(dict(INTENT, targetSoc=90), NOW)

    def test_invalid_max_a_denied(self):
        for amps in (0, 5, 17, 8.2, True):
            with self.subTest(amps=amps), self.assertRaises(ValueError):
                ingress.validate_intent(dict(INTENT, maxA=amps), NOW)

    def test_too_small_goal_denied(self):
        with self.assertRaisesRegex(ValueError, "GOAL_KWH_INVALID"):
            ingress.validate_intent(dict(INTENT, currentSoc=99), NOW)

    def test_command_identity(self):
        cmd = ingress.build_command(ingress.validate_intent(INTENT, NOW),
                                    "2fbf070c-4a28-4505-a66d-6ee1a086386e", NOW)
        self.assertEqual(cmd["schema"], 2)
        self.assertEqual(cmd["goalKWh"], 6.2)
        self.assertEqual(cmd["calibrationKWhPerPercent"], 0.62)
        self.assertEqual(cmd["source"], "website")
        self.assertEqual(cmd["maxA"], 10)

    def test_atomic_write_and_read(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "command.json"
            ingress.persist_atomic({"schema": 2, "requestId": "r1"}, p)
            self.assertEqual(json.loads(p.read_text())["requestId"], "r1")

    def test_derived_builder_accepts_cancel(self):
        command = ingress.build_command(ingress.validate_intent({"active": False}, NOW),
                                       "2fbf070c-4a28-4505-a66d-6ee1a086386e", NOW)
        state = builder.build(command, {"tesla":{}, "meta":{}}, {}, NOW)
        self.assertEqual(state["status"], "INACTIVE")
        self.assertIsNone(state["deadlineAt"])
        self.assertEqual(state["remainingKWh"], 0.0)


class Handler(unittest.TestCase):
    def future(self):
        return dict(INTENT, deadline=(datetime.now(ingress.LOCAL_TZ) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"))

    def handler(self, obj, peer="127.0.0.1", pin="long-secret"):
        data = json.dumps(obj).encode()
        h = SimpleNamespace(
            client_address=(peer, 123),
            headers={"Content-Type":"application/json",
                     "Content-Length":str(len(data)),
                     "X-Tesla-Control-Pin":pin,
                     "Origin":"http://100.127.130.0"},
            rfile=io.BytesIO(data))
        return h

    def collect(self, handler, previous=None):
        result = []
        with patch.object(ingress, "_pin_ready", return_value="long-secret"), \
             patch.object(ingress, "_previous", return_value=previous or {}), \
             patch.object(ingress, "persist_atomic") as persist, \
             patch.object(ingress.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as runner:
            ingress.handle_tesla_command(handler,
                lambda h, status, body: result.append((status, body)))
            return result, persist.call_count, runner.call_count

    def test_reject_non_loopback(self):
        result, writes, runs = self.collect(self.handler(self.future(),peer="192.168.1.50"))
        self.assertEqual((result[0][0], writes, runs), (403,0,0))

    def test_reject_wrong_pin(self):
        result, writes, runs = self.collect(self.handler({**INTENT},pin="bad"))
        self.assertEqual((result[0][0], writes, runs), (401,0,0))

    def test_missing_idempotency_key(self):
        result, writes, runs = self.collect(self.handler(self.future()))
        self.assertEqual((result[0][0], writes, runs), (400,0,0))

    def test_accept_and_immediate_derive(self):
        req=dict(self.future(),clientRequestId="a900fe6c-6552-40ba-9be4-c74445ef795e")
        result,writes,runs=self.collect(self.handler(req))
        self.assertEqual((result[0][0],writes,runs),(200,1,1))
        self.assertEqual(result[0][1]["derivedState"],"UPDATED")

    def test_retry_is_idempotent(self):
        req=dict(self.future(),clientRequestId="a900fe6c-6552-40ba-9be4-c74445ef795e")
        old=ingress.build_command(ingress.validate_intent(req,NOW),
                                  req["clientRequestId"], NOW)
        result,writes,runs=self.collect(self.handler(req), old)
        self.assertEqual((result[0][0],writes,runs),(200,0,0))
        self.assertTrue(result[0][1]["duplicate"])

    def test_idempotency_conflict_is_rejected(self):
        req=dict(self.future(),currentSoc=80,clientRequestId="a900fe6c-6552-40ba-9be4-c74445ef795e")
        old=ingress.build_command(ingress.validate_intent(dict(req,currentSoc=90),NOW),
                                  req["clientRequestId"], NOW)
        result,writes,runs=self.collect(self.handler(req),old)
        self.assertEqual((result[0][0],writes,runs),(409,0,0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
