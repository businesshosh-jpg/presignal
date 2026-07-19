#!/usr/bin/env python3
"""Tests for the narrow v2-to-v2.1 Episode input compatibility adapter."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_event_path_inputs as inputs


def episode(event_id="event-1", release="2024-05-01T07:30:00Z"):
    return {"episode_id":"EP_EVENT_TEST","country":"US","release_ts":release,"member_event_ids":[event_id],"member_indicator_names":["Test Event"]}


def session(event_id="event-1"):
    return {"session_id":"US|2024-05-01|CUSTOM_CONFIG_WINDOW","country":"US","session_start_ts":"2024-05-01T07:30:00Z","session_end_ts":"2024-05-01T18:30:00Z","forecast_cutoff":"2024-05-01T07:20:00Z","event_id":event_id}


class EventPathInputTests(unittest.TestCase):
    def test_attention_label_mapping_and_cluster_precedence(self):
        expected={"PRIMARY_DRIVER":"FORECAST","SECONDARY_DRIVER":"WATCH","WATCHLIST":"WATCH","CONTEXT_ONLY":"WATCH","IGNORE":"IGNORE","NO_SIGNAL":"NO_SIGNAL"}
        for label, status in expected.items(): self.assertEqual(inputs.select_status([label]), status)
        self.assertEqual(inputs.select_status(["SECONDARY_DRIVER","IGNORE"]),"WATCH")
        self.assertEqual(inputs.select_status(["PRIMARY_DRIVER","NO_SIGNAL"]),"FORECAST")
        self.assertEqual(inputs.select_status([]),"UNAVAILABLE")

    def test_exact_parent_session_rejects_date_only_nearest_and_multiple(self):
        member={"event_id":"event-1","release_ts":"2024-05-01T07:30:00Z","session_id":session()["session_id"]}
        state={"sessions":[session()],"members_by_session":{session()["session_id"]:[member]}}
        self.assertEqual(inputs.parent_session(episode(),state),(session()["session_id"],None))
        self.assertEqual(inputs.parent_session(episode(release="2024-05-01T07:31:00Z"),state),(None,"NO_EXACT_PARENT_SESSION"))
        state["sessions"].append({**session(),"session_id":"US|2024-05-01|SECOND"})
        state["members_by_session"]["US|2024-05-01|SECOND"]=[{**member,"session_id":"US|2024-05-01|SECOND"}]
        self.assertEqual(inputs.parent_session(episode(),state),(None,"MULTIPLE_PARENT_SESSIONS"))

    def test_cutoff_and_leakage_are_fail_closed(self):
        pack={"forecast_cutoff":"2024-05-01T07:20:00Z","items":[{"forecast_cutoff":"2024-05-01T07:20:00Z","source_timestamp":"2024-05-01T07:19:00Z","historical_availability_timestamp":"2024-05-01T07:20:00Z"}]}
        self.assertIsNone(inputs.validate_cutoff_and_pack(session(),pack,"2024-05-01T07:30:00Z"))
        self.assertEqual(inputs.validate_cutoff_and_pack(session(),{**pack,"items":[{**pack["items"][0],"source_timestamp":"2024-05-01T07:21:00Z"}]},"2024-05-01T07:30:00Z"),"POST_CUTOFF_SOURCE")
        with self.assertRaisesRegex(inputs.CompatibilityError,"FORBIDDEN_LEAKAGE_FIELD:outcome_id"):
            inputs.reject_leakage({"outcome_id":"OUT_test"})
        with self.assertRaisesRegex(inputs.CompatibilityError,"FORBIDDEN_LEAKAGE_FIELD:released_value"):
            inputs.reject_leakage({"released_value":1})

    def test_structural_roles_are_neutral_metadata(self):
        member=inputs.structural_members(episode(),{"EP_EVENT_TEST":[{"event_id":"event-1","component_role":"PRIMARY_COMPONENT"}]})[0]
        self.assertEqual(member["structural_component_role"],"PRIMARY_COMPONENT")
        self.assertNotIn("causal",member)
        self.assertNotIn("provider_selection",member)

    def test_historical_attention_gap_is_explicit_and_deterministic(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first=inputs.run("compatibility",Path(first_dir))
            second=inputs.run("compatibility",Path(second_dir))
            self.assertFalse(first["attention_export_available"])
            self.assertEqual(first["counts"]["fully_step_6_ready_episodes"],0)
            self.assertEqual(first["unavailable_by_reason"]["ATTENTION_MAP_MISSING"],1316)
            self.assertEqual(first["pack_a_input_fingerprint"],second["pack_a_input_fingerprint"])
            self.assertEqual(first["pack_e_input_fingerprint"],second["pack_e_input_fingerprint"])
            self.assertEqual((Path(first_dir)/"event_path_forecast_inputs_pack_a.jsonl").read_text(),"")
            ledger=[json.loads(line) for line in (Path(first_dir)/"compatibility_unavailable_ledger.jsonl").read_text().splitlines()]
            self.assertEqual(len({row["episode_id"] for row in ledger}),1682)

    def test_prospective_interface_is_pure_and_no_duplicate_transport(self):
        result=inputs.adapt_prospective_outputs(episodes=[episode()],attention_records=[{}],request_records=[{}],shared_pack_records=[{}],provider_models={"Mock":"mock"})
        self.assertEqual(result["external_calls"],0)
        source=Path(inputs.__file__).read_text()
        self.assertNotIn("google_clients",source)
        self.assertNotIn("run_script_function",source)


if __name__ == "__main__": unittest.main()
