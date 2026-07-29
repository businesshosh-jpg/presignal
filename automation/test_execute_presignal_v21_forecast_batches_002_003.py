from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import execute_presignal_v21_forecast_batch_001 as batch001
from automation import execute_presignal_v21_forecast_batches_002_003 as coordinator
from automation.test_execute_presignal_v21_forecast_batch_001 import valid_raw_output


def fake_preflight() -> dict[str, object]:
    return {
        "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
        "token_path_external": True,
        "authentication_method": "test",
        "scope_names": [],
        "scope_verification_result": "PASSED",
        "read_only_preflight_result": "PASSED",
        "resource_identity_result": "PASSED",
        "google_writes": 0,
    }


def fake_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
        "classification": {"category": "READY"},
        "elapsed_ms": 10,
        "result": {
            "status": "ok",
            "actual_provider": payload["provider"],
            "actual_model": payload["model"],
            "raw_output": valid_raw_output(),
            "prompt_tokens": 111,
            "completion_tokens": 222,
            "latency_ms": 333,
            "completed_timestamp": "2026-07-29T13:30:00Z",
        },
    }


class ForecastBatches002003Test(unittest.TestCase):
    def test_only_batches_002_and_003_are_authorized(self) -> None:
        bundles = coordinator.validate_authorized_batches()
        self.assertEqual([bundle["frozen_batch_id"] for bundle in bundles], ["FCB_PACK_A_002", "FCB_PACK_A_003"])
        self.assertEqual([bundle["user_batch_label"] for bundle in bundles], ["FORECAST_BATCH_002", "FORECAST_BATCH_003"])
        self.assertTrue(all(bundle["pack_type"] == "PACK_A" for bundle in bundles))
        ids_002 = {row["call"]["forecast_call_id"] for row in bundles[0]["bundles"]}
        ids_003 = {row["call"]["forecast_call_id"] for row in bundles[1]["bundles"]}
        ids_001 = {row["call"]["forecast_call_id"] for row in batch001.verified_batch_bundle()["bundles"]}
        self.assertEqual(len(ids_002), 12)
        self.assertEqual(len(ids_003), 12)
        self.assertTrue(ids_001.isdisjoint(ids_002))
        self.assertTrue(ids_001.isdisjoint(ids_003))
        self.assertTrue(ids_002.isdisjoint(ids_003))

    def test_generic_batch_executor_resolves_second_batch_fingerprints(self) -> None:
        bundle = batch001.verified_batch_bundle(user_batch_label="FORECAST_BATCH_002", frozen_batch_id="FCB_PACK_A_002")
        self.assertEqual(bundle["pack_type"], "PACK_A")
        self.assertEqual(len(bundle["bundles"]), 12)
        for row in bundle["bundles"]:
            self.assertEqual(row["call"]["pack_row_fingerprint"], batch001.sha256_value(row["pack_row"]))
            self.assertEqual(
                row["prompt_fingerprint"]["prompt_text_fingerprint"],
                batch001.sha256_value(row["prompt_row"]["prompt_text"]),
            )

    def test_batch_003_waits_for_batch_002_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = coordinator.execute_move(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T13:31:00Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=fake_dispatch,
            )
            self.assertEqual(result["continuation_gate"], "PROCEED_TO_FORECAST_BATCH_003")
            self.assertIsNotNone(result["batch_003"])
            batch_002_started = batch001.read_jsonl(result["batch_002"]["run_dir"] / "operation_journal.jsonl")[0]
            batch_003_started = batch001.read_jsonl(result["batch_003"]["run_dir"] / "operation_journal.jsonl")[0]
            self.assertEqual(batch_002_started["event"], "CALL_STARTED")
            self.assertEqual(batch_003_started["event"], "CALL_STARTED")
            self.assertEqual(result["move_reconciliation"]["total_attempted_calls"], 24)
            self.assertEqual(result["move_reconciliation"]["total_valid_calls"], 24)

    def test_shared_batch_002_failure_blocks_batch_003(self) -> None:
        def failing_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            if payload["provider"] == "Anthropic":
                return {
                    "ok": True,
                    "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
                    "classification": {"category": "READY"},
                    "elapsed_ms": 10,
                    "result": {
                        "status": "ok",
                        "actual_provider": "OpenAI",
                        "actual_model": payload["model"],
                        "raw_output": valid_raw_output(),
                        "prompt_tokens": 111,
                        "completion_tokens": 222,
                        "latency_ms": 333,
                        "completed_timestamp": "2026-07-29T13:30:00Z",
                    },
                }
            return fake_dispatch(_service, _script_id, payload)

        with tempfile.TemporaryDirectory() as tmp:
            result = coordinator.execute_move(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T13:31:00Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=failing_dispatch,
            )
            self.assertEqual(result["continuation_gate"], "STOP_BEFORE_FORECAST_BATCH_003_SHARED_FAILURE")
            self.assertIsNone(result["batch_003"])
            self.assertEqual(result["move_decision"]["move_status"], "FORECAST_BATCHES_002_003_STOPPED_AFTER_BATCH_002")


if __name__ == "__main__":
    unittest.main()
