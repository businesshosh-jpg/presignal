"""Offline checks for Slice 003 reconciliation and Slice 004 preparation."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
MANIFEST_DIR = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-004-20260803T090000Z-527470dac479af672166"
EVAL_DIR = BASE / "PPHB-R1-OUTCOME-EVALUATION-SLICE-003-PAIRED-EXCLUSION-20260803T081500Z-1a04811ea2b95396242c-v2"


def read(name: str) -> dict:
    return json.loads((MANIFEST_DIR / name).read_text())


def test_slice_003_denominator_reconciliation_is_append_only() -> None:
    path = BASE / "PPHB-R1-SLICE-003-T15-DENOMINATOR-RECONCILIATION-20260803T090000Z" / "denominator_reconciliation.json"
    value = json.loads(path.read_text())
    assert value["decision"] == "SLICE_003_T15_DENOMINATORS_CONFIRMED"
    assert value["affected_forecast"]["forecast_call_id"] == "FCL_cb40905e9d82b875db434ffd"
    assert value["pack_denominators"]["PACK_E"]["denominator"] == 15
    assert value["common_pair_comparison"]["t15_common_scoreable_pairs"] == 15
    assert value["metrics_not_recalculated"] is True


def test_slice_004_population_and_ceilings_are_frozen() -> None:
    manifest = read("slice_004_manifest.json")
    auth = read("proposed_end_to_end_authorization_inputs.json")
    assert manifest["manifest_fingerprint"] == "sha256:527470dac479af672166e861dc39b33873264fc4fc734208cb370ccd2ce593a5"
    assert manifest["episode_count"] == 12
    assert manifest["authorized_forecast_population"] == {
        "valid_forecasts": 48,
        "pack_a": 24,
        "pack_e": 24,
        "complete_pack_a_e_pairs": 24,
        "pack_a_only": 0,
        "pack_e_only": 0,
        "unpaired": 0,
    }
    assert len(read("population_proof.json")["distinct_utc_release_days"]) == 8
    assert auth["authorization_status"] == "PROPOSED_NOT_ACTIVE"
    assert auth["max_apps_script_reads"] == 8
    assert auth["max_market_data_provider_attempts"] == 12
    assert auth["max_total_external_requests"] == 20
    assert auth["max_google_writes"] == 0
    assert auth["max_attachment_records"] == 12
    assert auth["evaluation_authorized"] is False


def test_slice_004_excludes_prior_and_unavailable_episodes() -> None:
    manifest = read("slice_004_manifest.json")
    proof = read("population_proof.json")
    selected = {row["episode_id"] for row in manifest["episode_manifest"]}
    assert "EP_EVENT_82563db31e94ae9d1799" not in selected
    assert "EP_EVENT_4b80366594480b554889" not in selected
    assert "EP_EVENT_aa41226bcb8107901555" not in selected
    assert proof["accepted_unavailable_exclusions"][0]["reason"] == "ACCEPTED_OUTCOME_UNAVAILABLE"


def test_slice_003_evaluation_artifact_was_not_rerun() -> None:
    decision = json.loads((EVAL_DIR / "evaluation_decision.json").read_text())
    assert decision["decision"] == "OUTCOME_SLICE_003_MINIMAL_EVALUATION_COMPLETE"
    assert decision["external_requests"] == 0
