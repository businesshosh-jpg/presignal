"""Offline regression checks for the Slice 003 autonomous completion boundary."""
from __future__ import annotations

import json
from pathlib import Path

from automation import evaluate_presignal_v21_outcome_slice_001 as evaluator
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
RAW = BASE / "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3" / "raw_provider_outputs.jsonl"
RECOVERED = {
    "FCL_215cbe7ebee83be08888dbc5",
    "FCL_49308d97ec550f9587f1a571",
    "FCL_eb02f508140281ab6020b46b",
}


def test_preserved_raw_recovery_is_strict_and_scoped() -> None:
    rows = [json.loads(line) for line in RAW.read_text().splitlines()]
    selected = {row["forecast_call_id"]: row for row in rows if row["forecast_call_id"] in RECOVERED}
    assert set(selected) == RECOVERED
    for row in selected.values():
        normalized, audit = step6.normalize_provider_output(row["raw_provider_output"])
        assert normalized["no_signal_flag"] is False
        assert len(normalized["path"]) == 4
        assert audit["path_boundary_repair"]["status"] == "NO_REPAIR_POSITION"


def test_slice_003_evaluation_artifact_is_authorized_population() -> None:
    run = BASE / "PPHB-R1-OUTCOME-EVALUATION-SLICE-003-PAIRED-EXCLUSION-20260803T081500Z-1a04811ea2b95396242c-v2"
    manifest = json.loads((run / "run_manifest.json").read_text())
    decision = json.loads((run / "evaluation_decision.json").read_text())
    assert manifest["external_requests"] == 0
    assert manifest["google_writes"] == 0
    assert manifest["forecast_count"] == 32
    assert manifest["episode_pair_groups"] == 10
    assert manifest["provider_model_pair_rows"] == 16
    assert decision["decision"] == "OUTCOME_SLICE_003_MINIMAL_EVALUATION_COMPLETE"
    assert decision["composite_score"] == "NOT_CALCULATED_NOT_AUTHORIZED"


def test_paired_difference_fails_closed_for_ineligible_values() -> None:
    assert evaluator.paired_difference(None, 1.0) is None
    assert evaluator.paired_difference(1.0, None) is None
    assert evaluator.paired_difference(1.0, 0.25) == 0.75
