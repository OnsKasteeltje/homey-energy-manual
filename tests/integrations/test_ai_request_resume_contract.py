#!/usr/bin/env python3
import importlib.util
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "services/pi/api/analysis/server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ems_ai_resume_contract", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ai = load_module()
    with tempfile.TemporaryDirectory() as temp:
        ai.JOBS_DB = str(Path(temp) / "jobs.sqlite")
        day = date(2026, 10, 4)
        request_id = "123e4567-e89b-12d3-a456-426614174000"
        question = "Waarom exporteerden we rond 14:00?"

        first = ai._job_claim(request_id, question, day)
        assert first["claimed"] is True
        assert first["status"] == "PENDING"

        duplicate = ai._job_claim(request_id, question, day)
        assert duplicate["claimed"] is False
        assert duplicate["status"] == "PENDING"

        # A legitimately long-running request must stay PENDING even beyond
        # the stale threshold while this process still owns the active call.
        with ai.sqlite3.connect(ai.JOBS_DB) as db:
            db.execute(
                """
                UPDATE analysis_jobs
                SET updated_at_utc='2026-10-04T08:00:00Z'
                WHERE request_id=?
                """,
                (request_id,),
            )
            db.commit()
        original_now = ai._job_now
        ai._job_now = lambda: ai.datetime.fromisoformat(
            "2026-10-04T08:10:00+00:00"
        )
        still_pending = ai._job_get(request_id)
        assert still_pending["status"] == "PENDING"
        duplicate_long = ai._job_claim(request_id, question, day)
        assert duplicate_long["claimed"] is False
        assert duplicate_long["status"] == "PENDING"
        ai._job_now = original_now

        response = {
            "schema": "EMS_AI_ANALYSIS_V0.4",
            "status": "OK",
            "requestId": request_id,
            "answer": "test",
        }
        ai._job_complete(request_id, response)

        stored = ai._job_get(request_id)
        assert stored["status"] == "OK"
        assert stored["response"] == response

        cached = ai._job_claim(request_id, question, day)
        assert cached["claimed"] is False
        assert cached["status"] == "OK"
        assert cached["response"] == response

        try:
            ai._job_claim(request_id, "Andere vraag", day)
        except ValueError as exc:
            assert str(exc) == "REQUEST_ID_CONFLICT"
        else:
            raise AssertionError("request-id conflict was not rejected")

        failed_id = "123e4567-e89b-12d3-a456-426614174001"
        claimed = ai._job_claim(failed_id, question, day)
        assert claimed["claimed"] is True
        ai._job_fail(failed_id, "MODEL_UNAVAILABLE")
        failed = ai._job_get(failed_id)
        assert failed["status"] == "ERROR"
        assert failed["reason"] == "MODEL_UNAVAILABLE"

        # An orphaned PENDING row from a prior process may still be reclaimed
        # after the stale threshold because no active in-process owner exists.
        orphan_id = "123e4567-e89b-12d3-a456-426614174002"
        orphan = ai._job_claim(orphan_id, question, day)
        assert orphan["claimed"] is True
        ai._job_release(orphan_id)
        with ai.sqlite3.connect(ai.JOBS_DB) as db:
            db.execute(
                """
                UPDATE analysis_jobs
                SET updated_at_utc='2026-10-04T08:00:00Z'
                WHERE request_id=?
                """,
                (orphan_id,),
            )
            db.commit()
        original_now = ai._job_now
        ai._job_now = lambda: ai.datetime.fromisoformat(
            "2026-10-04T08:10:00+00:00"
        )
        assert ai._job_get(orphan_id)["status"] == "STALE"
        reclaimed = ai._job_claim(orphan_id, question, day)
        assert reclaimed["claimed"] is True
        assert reclaimed["reclaimed"] is True
        ai._job_release(orphan_id)
        ai._job_now = original_now

    print("PASS: AI resumable request contract")


if __name__ == "__main__":
    main()
