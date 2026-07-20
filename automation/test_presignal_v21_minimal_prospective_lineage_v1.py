from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_prospective_shadow_v1 as shadow
from automation import presignal_v21_prospective_flat_contract_v1 as prospective


STUDY = "PSS_8a6e8ca69c195cf9defc"
RUN = "P12-COLLECT-ffd55626bc1a886c2e19"
CUTOFF = "2030-01-01T12:00:00Z"
SESSION = {"session_id": "PROS_TEST_SESSION", "country": "US", "session_window_name": "test", "session_start_ts": "2030-01-01T11:00:00Z", "session_end_ts": "2030-01-01T13:00:00Z"}
MEMBERS = [{"event_id": "EV_TEST_A", "indicator_name": "Test A", "release_ts": "2030-01-01T12:05:00Z", "member_order": 1}, {"event_id": "EV_TEST_B", "indicator_name": "Test B", "release_ts": "2030-01-01T12:05:00Z", "member_order": 2}]


def dispatcher(request):
    payload = json.loads(request["prompt"]["user"])
    if payload["object"] == "presignal_v2_market_session_attention_task":
        raw = {"object": "session_attention_map", "session_id": SESSION["session_id"], "provider": request["provider"], "status": "ok", "attention_items": [{"event_id": row["event_id"], "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST", "attention_rank": index + 1, "attention_reason": "test", "expected_market_channel": "treasury_yields", "driver_role": "primary" if index == 0 else "watch", "confidence": 0.7} for index, row in enumerate(payload["events"])]}
    else:
        raw = {"object": "session_information_requirements", "session_id": SESSION["session_id"], "provider": request["provider"], "status": "ok", "information_items": [{"request_rank": 1, "requested_information": "US 2Y yield", "information_category": "treasury_yields", "priority": "must_have", "reason": "test", "affected_channel": "treasury_yields", "event_family_relevance": "session", "linked_event_ids": ["EV_TEST_A"], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "unknown", "suggested_source": "approved", "expected_forecast_use": "context", "is_market_state_candidate": True}]}
    return {"status": "ok", "actual_provider": request["provider"], "actual_model": request["model"], "raw_output": json.dumps(raw), "completed_timestamp": "2030-01-01T11:59:00Z"}


class MinimalProspectiveLineageTests(unittest.TestCase):
    def attention(self, provider="OpenAI", model="gpt-4o-mini-2024-07-18"):
        return lineage.build_prospective_attention(study_id=STUDY, collection_run_id=RUN, session_snapshot=SESSION, member_rows=MEMBERS, provider=provider, model=model, information_cutoff_ts=CUTOFF, attention_run_id="PATTN_" + provider, stage_generated_ts="2030-01-01T11:55:00Z", dispatcher=dispatcher)

    def test_exact_provider_models_and_attention_raw_lineage_are_preserved(self):
        for provider, model in lineage.APPROVED_MODELS.items():
            result = self.attention(provider, model)
            self.assertEqual(result["status"], "parsed")
            self.assertEqual(len(result["rows"]), 2)
            self.assertTrue(all(row["provider"] == provider and row["model"] == model and row["raw_output"] for row in result["rows"]))
        with self.assertRaisesRegex(lineage.MinimalProspectiveLineageError, "EXACT_PROVIDER_MODEL_REQUIRED"):
            self.attention("OpenAI", "gpt-new")

    def test_requests_bind_to_new_attention_and_pack_e_is_shared(self):
        requests = {}
        for provider, model in lineage.APPROVED_MODELS.items():
            attention = self.attention(provider, model)
            request = lineage.build_prospective_requests(study_id=STUDY, collection_run_id=RUN, session_snapshot=SESSION, member_rows=MEMBERS, attention_result=attention, provider=provider, model=model, information_cutoff_ts=CUTOFF, request_run_id="PREQ_" + provider, stage_generated_ts="2030-01-01T11:57:00Z", dispatcher=dispatcher)
            self.assertEqual(request["status"], "parsed")
            self.assertEqual(request["rows"][0]["attention_run_id"], attention["rows"][0]["attention_run_id"])
            requests[provider] = request["rows"]
        packs = lineage.build_prospective_packs(study_id=STUDY, collection_run_id=RUN, session_id=SESSION["session_id"], information_cutoff_ts=CUTOFF, pack_freeze_id="PPACK_TEST", requests_by_provider=requests, shared_pack_items=[{"information_key": "rates", "value": "cutoff", "source_timestamp": "2030-01-01T11:58:00Z"}], pack_generated_ts="2030-01-01T11:59:00Z")
        self.assertEqual(packs["status"], "FROZEN")
        self.assertEqual(len({packs["pack_e"]["pack_fingerprint"] for _ in requests}), 1)
        self.assertEqual(len({value["pack_fingerprint"] for value in packs["pack_a_by_provider"].values()}), 3)

    def test_cutoff_and_forbidden_fields_fail_closed(self):
        with self.assertRaisesRegex(lineage.MinimalProspectiveLineageError, "POST_CUTOFF_PACK_ITEM"):
            lineage.build_prospective_packs(study_id=STUDY, collection_run_id=RUN, session_id=SESSION["session_id"], information_cutoff_ts=CUTOFF, pack_freeze_id="P", requests_by_provider={"OpenAI": [{"status": "parsed", "session_id": SESSION["session_id"], "information_cutoff_ts": CUTOFF, "request_identity": "x"}]}, shared_pack_items=[{"source_timestamp": "2030-01-01T12:00:01Z"}], pack_generated_ts="2030-01-01T11:59:00Z")
        bad = copy.deepcopy(SESSION); bad["released_value"] = 1
        with self.assertRaisesRegex(lineage.MinimalProspectiveLineageError, "FORBIDDEN_PROSPECTIVE_FIELD"):
            lineage.build_prospective_attention(study_id=STUDY, collection_run_id=RUN, session_snapshot=bad, member_rows=MEMBERS, provider="OpenAI", model="gpt-4o-mini-2024-07-18", information_cutoff_ts=CUTOFF, attention_run_id="x", stage_generated_ts="2030-01-01T11:55:00Z")

    def test_dry_run_is_call_free_and_does_not_create_scientific_output(self):
        result = lineage.build_prospective_attention(study_id=STUDY, collection_run_id=RUN, session_snapshot=SESSION, member_rows=MEMBERS, provider="OpenAI", model="gpt-4o-mini-2024-07-18", information_cutoff_ts=CUTOFF, attention_run_id="x", stage_generated_ts="2030-01-01T11:55:00Z")
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["rows"], [])

    def test_same_p12_run_resumes_append_only_without_live_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            p12 = Path(directory) / "P12-COLLECT-ffd55626bc1a886c2e19"; p12.mkdir()
            for filename in ("collection_manifest.json", "collection_status.json", "p12_checkpoint_assessment.json", "blocker_resolution.json", "resume_transition.json", "live_lineage_capability.json"):
                (p12 / filename).write_text(json.dumps({"original": filename}))
            result = shadow.resume_minimal_p12(p12_dir=p12, repair_dir=Path(directory) / "repair", contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION)
            self.assertEqual(result["status"], "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS")
            self.assertTrue((p12 / "collection_manifest_r2.json").exists())
            self.assertEqual(json.loads((p12 / "collection_status.json").read_text())["admitted_episodes"], 0)
            self.assertEqual(result["external_calls"], 0)


if __name__ == "__main__":
    unittest.main()
