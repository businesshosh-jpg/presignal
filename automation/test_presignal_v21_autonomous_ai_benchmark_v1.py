"""Focused offline checks for the frozen native-v2 reconciliation path."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import automation.presignal_v21_autonomous_ai_benchmark_v1 as benchmark
from automation.run_presignal_v21_single_event_path_pair_v1 import parse_provider_output, response_to_contract


class NativeV2ReconciliationTests(unittest.TestCase):
    def test_v2_prompt_keeps_numeric_confidence_contract(self):
        episode = benchmark.resolve_source()["sample"][0]["episode"]
        prompt = benchmark._native_prompt_v2(episode)
        self.assertIn("JSON number from 0.0 to 1.0 inclusive", prompt)
        self.assertIn("Never use Low/Medium/High", prompt)

    def test_every_frozen_episode_has_one_durable_response_and_terminal_record(self):
        records = benchmark._ledger_records_for_v2()
        self.assertEqual(len(records), benchmark.SAMPLE_SIZE)
        terminals = {"FORECAST_ACCEPTED", "NATIVE_AI_FORECAST_SCHEMA_REJECTED"}
        for episode_id, rows in records.items():
            response = [row for row in rows if row.get("state") == "RESPONSE_RECEIVED"]
            terminal = [row for row in rows if row.get("state") in terminals]
            self.assertEqual(len(response), 1, episode_id)
            self.assertTrue(Path(response[0]["raw_response_path"]).is_file(), episode_id)
            self.assertEqual(len(terminal), 1, episode_id)

    def test_valid_response_remains_parseable_without_normalization(self):
        records = benchmark._ledger_records_for_v2()
        accepted = next(rows for rows in records.values() if any(row.get("state") == "FORECAST_ACCEPTED" for row in rows))
        response_record = next(row for row in accepted if row.get("state") == "RESPONSE_RECEIVED")
        raw = json.loads(Path(response_record["raw_response_path"]).read_text())["provider_response"]["raw_output"]
        self.assertIsInstance(parse_provider_output(raw), dict)

    def test_flat_nonzero_range_remains_unrecoverable(self):
        records = benchmark._ledger_records_for_v2()
        rejected = next(rows for rows in records.values() if any(row.get("state") == "NATIVE_AI_FORECAST_SCHEMA_REJECTED" for row in rows))
        response_record = next(row for row in rejected if row.get("state") == "RESPONSE_RECEIVED")
        raw = json.loads(Path(response_record["raw_response_path"]).read_text())["provider_response"]
        response = parse_provider_output(raw["raw_output"])
        episode_id = response_record["episode_id"]
        episode = next(item["episode"] for item in benchmark.resolve_source()["sample"] if item["episode"]["episode_id"] == episode_id)
        input_row = {"information_arm": "PACK_A", "episode_id": episode_id, "source_session_id": episode["session_id"], "provider": "Gemini", "model": "gemini-2.5-flash-lite", "forecast_cutoff_ts": episode["forecast_cutoff_ts"], "episode_members": episode["episode_members"], "pack_id": "NATIVE_AI_NO_RESEARCH_V2", "pack_fingerprint": None}
        with self.assertRaisesRegex(Exception, "PATH_NEUTRAL_PIP_RANGE"):
            response_to_contract(response, input_row, run_id=benchmark.NATIVE_RUN_ID, created_ts=benchmark.now(), raw_output=raw["raw_output"], bridge_result=raw)

    def test_v3_prompt_requires_flat_zero_zero_net_pips(self):
        episode = benchmark.resolve_source()["sample"][0]["episode"]
        prompt = benchmark._native_prompt_v3(episode)
        benchmark._validate_v3_prompt(prompt)
        self.assertIn("both be numeric zero", prompt)
        self.assertIn("not intrahorizon volatility", prompt)

    def test_v3_call_identity_differs_from_v2(self):
        episode = benchmark.resolve_source()["sample"][0]["episode"]
        base = benchmark.NATIVE_RUN_ID + episode["episode_id"] + benchmark.fingerprint(episode)
        v2 = "NATIVEV2_" + __import__("hashlib").sha256((base + benchmark.NATIVE_PROMPT_V2).encode()).hexdigest()[:24]
        v3 = "NATIVEV3_" + __import__("hashlib").sha256((base + benchmark.NATIVE_PROMPT_V3).encode()).hexdigest()[:24]
        self.assertNotEqual(v2, v3)

    def test_v3_authorization_is_exactly_the_four_prior_flat_rejections(self):
        audit = json.loads((benchmark.NATIVE_ARTIFACT / "native_ai_v2_reconciliation.json").read_text())["audit"]
        authorized = [row["episode_id"] for row in audit if row["terminal_state"] == "NATIVE_AI_FORECAST_SCHEMA_REJECTED" and row["parser_rejection_reason"] == "PATH_NEUTRAL_PIP_RANGE"]
        self.assertEqual(len(authorized), 4)
        self.assertNotIn("EP_EVENT_2de77b689facc34d5811", authorized)


if __name__ == "__main__":
    unittest.main()
