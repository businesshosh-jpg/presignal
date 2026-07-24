import unittest

from automation import presignal_v21_calendar_idempotency_replay_v1 as replay
from automation import run_presignal_v21_calendar_idempotency_replay_v1 as runner


class CalendarIdempotencyReplayTest(unittest.TestCase):
    def test_identical_replay_is_duplicate_free_and_corrected_content_updates(self):
        proof = replay.offline_replay_proof()
        self.assertTrue(proof["passed"])
        self.assertEqual(proof["second_identical_invocation"]["unchanged"], 2)
        self.assertEqual(proof["second_identical_invocation"]["duplicate_canonical_rows"], 0)
        self.assertEqual(proof["corrected_content_replay"]["updated"], 1)


    def test_preexisting_duplicate_lookup_key_fails_closed(self):
        row = {"country": "US", "indicator_name": "PMI", "release_ts": "2026-07-27T13:45:00Z"}
        with self.assertRaisesRegex(replay.CalendarReplayProofError, "PREEXISTING_DUPLICATE_UPSERT_KEY"):
            replay.simulate_apps_script_upsert([row, dict(row)], [])


    def test_capture_redacts_secret_like_fields(self):
        captured = replay.capture_calendar_adapter_response(
            {"ok": True, "response": {"access_token": "secret", "response": {"result": {"fetched": 1}}}, "result": {"fetched": 1}},
            window={"start_utc": "2026-07-24T00:00:00Z", "end_utc": "2026-07-31T00:00:00Z"},
        )
        self.assertNotIn('"access_token":"secret"', replay.canonical(captured))
        self.assertIn('"access_token":"REDACTED"', replay.canonical(captured))
        self.assertEqual(captured["execution_status"], "EXECUTION_COMPLETED_WITH_PAYLOAD")

    def test_legacy_leading_event_column_is_ignored_without_changing_values(self):
        shifted = {header: value for header, value in zip(runner.EVENT_HEADERS, ["", "econ_event", "US", "PMI", "Manufacturing", "Medium", "single", "event-1", "", "2026-07-27T13:45:00Z", "FMP"])}
        shifted["source_row"] = 10
        repaired = runner.realign_captured_rows([shifted])[0]
        self.assertEqual(repaired["object"], "econ_event")
        self.assertEqual(repaired["country"], "US")
        self.assertEqual(repaired["indicator_name"], "PMI")
        self.assertEqual(repaired["release_ts"], "2026-07-27T13:45:00Z")
        self.assertEqual(repaired["source_cal"], "FMP")
