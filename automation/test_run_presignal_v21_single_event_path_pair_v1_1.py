#!/usr/bin/env python3
"""Narrow unit tests for the single historical Event-Path pair runner."""
from __future__ import annotations

import copy
import unittest

from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


def input_row(*, arm: str, episode_id: str = "EP_BATCH_alpha", members: int = 2) -> dict:
    episode_members = [
        {"event_id": f"EV_{index}", "indicator_name": f"Indicator {index}", "structural_component_role": "STRUCTURAL_PRIMARY" if index == 0 else "STRUCTURAL_SECONDARY"}
        for index in range(members)
    ]
    attention = [
        {
            "event_id": member["event_id"], "indicator_name": member["indicator_name"], "attention_label": "PRIMARY_DRIVER" if index == 0 else "SECONDARY_DRIVER",
            "attention_rank": index + 1, "attention_reason": f"reason {index}", "expected_market_channel": "rates" if index == 0 else "risk",
            "driver_role": "driver", "confidence": 0.7, "attention_run_id": "ATTN_1", "session_id": "SES_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18",
            "forecast_cutoff_ts": "2024-01-01T00:00:00Z", "status": "parsed",
        }
        for index, member in enumerate(episode_members)
    ]
    return {
        "episode_id": episode_id, "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "SES_1", "country": "US",
        "release_ts": "2024-01-01T00:05:00Z", "forecast_cutoff_ts": "2024-01-01T00:00:00Z", "episode_members": episode_members,
        "structural_component_roles": [{"event_id": member["event_id"], "component_role": member["structural_component_role"]} for member in episode_members],
        "provider_attention_map": attention, "provider_episode_selection": "FORECAST", "information_requests": [{"information_key": "rates", "reason": "context"}],
        "information_arm": arm, "shared_market_state_pack": None if arm == "PACK_A" else {"items": [{"information_key": "rates", "value": "frozen"}]},
        "pack_id": "PACK_A_NO_SHARED_MARKET_STATE_PACK" if arm == "PACK_A" else "PACK_E_FROZEN", "pack_fingerprint": None if arm == "PACK_A" else "sha256:packe",
        "input_fingerprint": "sha256:" + arm,
    }


def response() -> dict:
    return {
        "no_signal_flag": False, "no_signal_reason": None, "confidence": 0.61,
        "immediate_impulse_direction": "UP", "immediate_impulse_peak_pips_min": 2.0,
        "immediate_impulse_peak_pips_max": 6.0, "immediate_impulse_confidence": 0.58,
        "immediate_impulse_window_seconds": 120, "early_reaction_5m_direction": "UP",
        "expected_reversal_flag": True, "expected_reversal_horizon_min": 30, "expected_path_summary": "initial rise then reversal",
        "information_used": ["rates"], "missing_information": [], "invalidation_condition": "material surprise differs",
        "path": [
            {"horizon_min": 5, "expected_direction": "UP", "expected_pips_min": 1.0, "expected_pips_max": 5.0, "stage_confidence": 0.6, "continuation_probability": 0.6, "reversal_probability": 0.1, "stage_reason": "initial", "invalidation_condition": "surprise"},
            {"horizon_min": 15, "expected_direction": "UP", "expected_pips_min": 1.0, "expected_pips_max": 6.0, "stage_confidence": 0.6, "continuation_probability": 0.5, "reversal_probability": 0.2, "stage_reason": "follow through", "invalidation_condition": "surprise"},
            {"horizon_min": 30, "expected_direction": "DOWN", "expected_pips_min": 1.0, "expected_pips_max": 7.0, "stage_confidence": 0.5, "continuation_probability": 0.3, "reversal_probability": 0.6, "stage_reason": "reversal", "invalidation_condition": "surprise"},
            {"horizon_min": 60, "expected_direction": "DOWN", "expected_pips_min": 1.0, "expected_pips_max": 7.0, "stage_confidence": 0.5, "continuation_probability": 0.3, "reversal_probability": 0.6, "stage_reason": "settle", "invalidation_condition": "surprise"},
        ],
    }


class CandidateSelectionTests(unittest.TestCase):
    def test_multimember_and_variation_preference_is_deterministic(self) -> None:
        a_one, e_one = input_row(arm="PACK_A", episode_id="EP_EVENT_z", members=1), input_row(arm="PACK_E", episode_id="EP_EVENT_z", members=1)
        a_two, e_two = input_row(arm="PACK_A", episode_id="EP_BATCH_b", members=2), input_row(arm="PACK_E", episode_id="EP_BATCH_b", members=2)
        outcomes = [{"episode_id": "EP_EVENT_z", "status": "VALID"}, {"episode_id": "EP_BATCH_b", "status": "VALID"}]
        assessed, eligible = step6.eligible_candidates([a_one, a_two], [e_one, e_two], outcomes)
        self.assertEqual(len(assessed), 2)
        self.assertEqual(eligible[0]["episode_id"], "EP_BATCH_b")
        self.assertEqual(eligible, step6.eligible_candidates([a_two, a_one], [e_two, e_one], outcomes)[1])

    def test_attention_omission_is_not_eligible(self) -> None:
        row_a, row_e = input_row(arm="PACK_A"), input_row(arm="PACK_E")
        row_a["provider_attention_map"] = row_a["provider_attention_map"][:1]
        _, eligible = step6.eligible_candidates([row_a], [row_e], [{"episode_id": row_a["episode_id"], "status": "VALID"}])
        self.assertEqual(eligible, [])

    def test_watch_episode_is_not_a_directional_forecast_candidate(self) -> None:
        row_a, row_e = input_row(arm="PACK_A"), input_row(arm="PACK_E")
        row_a["provider_episode_selection"] = "WATCH"
        _, eligible = step6.eligible_candidates([row_a], [row_e], [{"episode_id": row_a["episode_id"], "status": "VALID"}])
        self.assertEqual(eligible, [])


class PromptAndParsingTests(unittest.TestCase):
    def test_only_pack_fields_differ(self) -> None:
        context_a = step6.arm_context(input_row(arm="PACK_A"))
        context_e = step6.arm_context(input_row(arm="PACK_E"))
        diff = step6.prompt_diff(context_a, context_e)
        self.assertTrue(diff["passed"])
        self.assertEqual(set(diff["differences"]), step6.ALLOWED_PROMPT_DIFFERENCES)

    def test_prompt_diff_rejects_non_pack_change(self) -> None:
        left, right = step6.arm_context(input_row(arm="PACK_A")), step6.arm_context(input_row(arm="PACK_E"))
        right["episode"]["country"] = "JP"
        self.assertFalse(step6.prompt_diff(left, right)["passed"])

    def test_malformed_horizons_are_rejected(self) -> None:
        bad = response(); bad["path"] = bad["path"][:3]
        with self.assertRaisesRegex(step6.Step6Error, "PATH_COUNT"):
            step6.parse_provider_output(bad)

    def test_existing_response_contract_envelope_is_transport_normalized(self) -> None:
        parsed = step6.parse_provider_output({"forecast": response(), "response_contract": {"version": "transport"}})
        self.assertEqual(parsed, response())

    def test_known_transport_metadata_is_not_scientific_response_content(self) -> None:
        wrapped = response()
        wrapped.update({"object": "presignal_event_path_contract_v1_forecast", "schema_version": "2.1.0", "response_contract": "presignal_event_path_contract_v1"})
        self.assertEqual(step6.parse_provider_output(wrapped), response())

    def test_contract_predictions_and_paths_are_constructed(self) -> None:
        row = input_row(arm="PACK_A")
        prediction, paths = step6.response_to_contract(response(), row, run_id="RUN", created_ts="2024-01-01T00:00:01Z", raw_output=response(), bridge_result={"prompt_tokens": 1, "completion_tokens": 2, "latency_ms": 3})
        self.assertEqual(prediction["information_arm"], "BASELINE")
        self.assertEqual([row["horizon_min"] for row in paths], [5, 15, 30, 60])

    def test_attention_scope_preserves_structural_neutrality(self) -> None:
        result = step6.attention_adequacy(input_row(arm="PACK_A"))
        self.assertEqual(result["decision"], "ADEQUATE")
        self.assertTrue(result["dominant_member_identifiable"])
        self.assertFalse(result["would_episode_attention_field_materially_change_task"])


if __name__ == "__main__":
    unittest.main()
