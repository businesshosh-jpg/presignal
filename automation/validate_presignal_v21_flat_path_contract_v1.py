#!/usr/bin/env python3
"""Validate the prospective-only FLAT path-stage output contract without calls."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as frozen
from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import run_presignal_v21_single_event_path_pair_v1 as single
from automation import analyze_presignal_v21_step6_paired_batch_v1 as paired_analysis
from automation.build_presignal_v21_event_path_inputs import reject_leakage

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
SINGLE = ROOT / "outputs" / "presignal_v21_step6_single_pair" / "STEP6-SINGLE-20260719T175850564590Z"
BATCH = ROOT / "outputs" / "presignal_v21_step6_batch" / "STEP6-BATCH-f718192a7566138c3fda"
ANALYSIS = ROOT / "outputs" / "presignal_v21_step7_paired_analysis" / "STEP7-PAIRED-1dbbf399d2f73793e4f3"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_step8_r1_flat_contract_repair"
REPAIR_RUN_ID = "STEP8-R1-FLAT-" + prospective.expected_contract_fingerprint(prospective._file_json(prospective.CONTRACT_PATH)).split(":", 1)[1][:20]


class FlatContractValidationError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def tree_fingerprint(path: Path) -> str:
    records = []
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        records.append({"path": str(file_path.relative_to(path)), "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest()})
    return sha256(records)


def raw_rejection_audit() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair_dir in sorted((BATCH / "pairs").iterdir()):
        if not pair_dir.is_dir():
            continue
        pair_manifest = json.loads((pair_dir / "pair_manifest.json").read_text())
        pair_state = json.loads((pair_dir / "pair_state.json").read_text())
        for arm in ("pack_a", "pack_e"):
            raw_path = pair_dir / arm / "provider_response_raw.json"
            state = pair_state.get("arms", {}).get(arm.upper(), {})
            if not state.get("error") or not raw_path.exists():
                continue
            raw = json.loads(raw_path.read_text())
            rows.append({
                "pair_id": pair_dir.name, "arm": arm.upper(), "provider": pair_manifest.get("provider"),
                "model": pair_manifest.get("model"), "frozen_rejection_reason": state["error"],
                "raw_response_fingerprint": sha256(raw), "raw_response": raw.get("raw_output"),
            })
    return rows


def neutral_range_cases() -> list[dict[str, Any]]:
    cases = []
    for row in raw_rejection_audit():
        if row["frozen_rejection_reason"] != "PATH_NEUTRAL_PIP_RANGE":
            continue
        parsed = single.parse_provider_output(row["raw_response"])
        offending = [
            {key: stage.get(key) for key in ("horizon_min", "expected_direction", "expected_pips_min", "expected_pips_max")}
            for stage in parsed["path"]
            if stage.get("expected_direction") == "FLAT" and (stage.get("expected_pips_min") != 0 or stage.get("expected_pips_max") != 0)
        ]
        cases.append({key: value for key, value in row.items() if key != "raw_response"} | {"offending_stages": offending})
    return cases


def path_fixture(base_prediction: Mapping[str, Any], base_paths: list[Mapping[str, Any]], fixture: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prediction, paths = copy.deepcopy(dict(base_prediction)), copy.deepcopy(list(base_paths))
    path = paths[2]
    path["expected_direction"] = fixture.get("expected_direction")
    if "expected_pips_min" in fixture:
        path["expected_pips_min"] = fixture["expected_pips_min"]
    else:
        path.pop("expected_pips_min", None)
    if "expected_pips_max" in fixture:
        path["expected_pips_max"] = fixture["expected_pips_max"]
    else:
        path.pop("expected_pips_max", None)
    path["stage_fingerprint"] = frozen._fingerprint(path, "stage_fingerprint", ("run_id", "created_ts", "status", "error_message"))
    return prediction, paths


def fixture_validation() -> dict[str, Any]:
    example_dir = ROOT / "contracts" / "presignal_v21_event_path" / "examples"
    prediction = json.loads((example_dir / "valid_baseline_prediction.json").read_text())
    paths = json.loads((example_dir / "valid_prediction_path.json").read_text())
    fixtures = prospective.fixture_spec(); results = []
    for category, expected in (("valid_flat_stages", True), ("invalid_flat_stages", False)):
        for fixture in fixtures[category]:
            try:
                p, x = path_fixture(prediction, paths, fixture)
                frozen.validate_prediction_path_transaction(p, x)
                actual, error = True, None
            except Exception as exc:
                actual, error = False, str(exc)
            results.append({"category": category, "name": fixture["name"], "expected_valid": expected, "actual_valid": actual, "error": error})
    for fixture in fixtures["directional_regression_stages"]:
        try:
            p, x = path_fixture(prediction, paths, fixture)
            frozen.validate_prediction_path_transaction(p, x)
            actual, error = True, None
        except Exception as exc:
            actual, error = False, str(exc)
        results.append({"category": "directional_regression", "name": fixture["name"], "expected_valid": fixture["valid"], "actual_valid": actual, "error": error})
    if any(row["expected_valid"] != row["actual_valid"] for row in results):
        raise FlatContractValidationError("FIXTURE_VALIDATION_FAILURE")
    return {"results": results, "fingerprint": sha256(results)}


def provider_dry_run(contract_version: str = prospective.PROSPECTIVE_CONTRACT_VERSION) -> dict[str, Any]:
    inputs_a = single.read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl")
    inputs_e = single.read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl")
    by_key = {(row["episode_id"], row["provider"], row["model"]): row for row in inputs_e}
    target_providers = {
        ("Anthropic", "claude-haiku-4-5"), ("Gemini", "gemini-2.5-flash-lite"), ("OpenAI", "gpt-4o-mini-2024-07-18"),
    }
    results = []
    for provider, model in sorted(target_providers):
        candidates = [row for row in inputs_a if row["provider"] == provider and row["model"] == model]
        shapes = []
        for clustered in (False, True):
            row = next((item for item in candidates if (len(item["episode_members"]) > 1) == clustered and (item["episode_id"], provider, model) in by_key), None)
            if row is None:
                continue
            peer = by_key[(row["episode_id"], provider, model)]
            a = prospective.prospective_request(row, run_id="DRY_RUN", contract_version=contract_version)
            e = prospective.prospective_request(peer, run_id="DRY_RUN", contract_version=contract_version)
            reject_leakage(a["context"]); reject_leakage(e["context"])
            diff = single.prompt_diff(a["context"], e["context"])
            if not diff["passed"] or prospective.PROMPT_RULE not in a["prompt"] or prospective.PROMPT_RULE not in e["prompt"]:
                raise FlatContractValidationError("PROSPECTIVE_DRY_RUN_PROMPT_FAILURE")
            shapes.append({"shape": "cluster" if clustered else "standalone", "episode_id": row["episode_id"], "pack_a_prompt_fingerprint": sha256(a["prompt"]), "pack_e_prompt_fingerprint": sha256(e["prompt"]), "request_a_fingerprint": sha256(a["payload"]), "request_e_fingerprint": sha256(e["payload"]), "prompt_symmetry": diff, "serialized": True, "leakage_fields_exposed": 0})
        if not shapes:
            raise FlatContractValidationError("MISSING_PROVIDER_DRY_RUN_SOURCE:" + provider)
        results.append({"provider": provider, "model": model, "results": shapes, "provider_calls": 0})
    return {"providers": results, "provider_calls": 0, "fingerprint": sha256(results)}


def historical_verification() -> dict[str, Any]:
    before = {"single": tree_fingerprint(SINGLE), "batch": tree_fingerprint(BATCH), "analysis": tree_fingerprint(ANALYSIS)}
    manifest = json.loads((ANALYSIS / "analysis_manifest.json").read_text())
    batch_summary = json.loads((BATCH / "batch_completion_summary.json").read_text())
    single_reconstruction = single.validate_saved_run(SINGLE)
    analysis_reconstruction = paired_analysis.run(
        batch_run_id="STEP6-BATCH-f718192a7566138c3fda", verify_only=True,
    )
    if analysis_reconstruction["analysis_fingerprint"] != manifest["analysis_fingerprint"]:
        raise FlatContractValidationError("HISTORICAL_ANALYSIS_FINGERPRINT_DRIFT")
    after = {"single": tree_fingerprint(SINGLE), "batch": tree_fingerprint(BATCH), "analysis": tree_fingerprint(ANALYSIS)}
    if before != after:
        raise FlatContractValidationError("HISTORICAL_ARTIFACT_MUTATED")
    return {
        "frozen_contract_version": frozen.CONTRACT_VERSION,
        "single_run_id": json.loads((SINGLE / "run_manifest.json").read_text())["run_id"],
        "batch_run_id": json.loads((BATCH / "batch_manifest.json").read_text())["batch_run_id"],
        "analysis_run_id": manifest["analysis_run_id"],
        "historical_fingerprints_before": before, "historical_fingerprints_after": after,
        "historical_analysis_fingerprint": manifest.get("analysis_fingerprint"),
        "accepted_forecasts": batch_summary.get("accepted_forecasts"),
        "rejected_responses": len(raw_rejection_audit()),
        "single_pair_reconstruction": single_reconstruction,
        "batch_reconstruction": {"verified": True, "provider_calls": 0, "source": "read_only_episode_cluster_analysis_verifier"},
        "analysis_reconstruction": {"verified": True, "provider_calls": 0, "analysis_fingerprint": analysis_reconstruction["analysis_fingerprint"]},
        "unchanged": True,
    }


def run(
    output_dir: Path | None = None,
    *,
    contract_version: str = prospective.PROSPECTIVE_CONTRACT_VERSION,
) -> tuple[Path, dict[str, Any]]:
    output_dir = output_dir or OUTPUT_ROOT / REPAIR_RUN_ID
    historical = historical_verification()
    spec = prospective.resolve_contract(contract_version, prospective=True); fp = prospective.fingerprints()
    neutral = neutral_range_cases()
    if len(neutral) != 6:
        raise FlatContractValidationError("EXPECTED_SIX_PATH_NEUTRAL_PIP_RANGE_CASES:" + str(len(neutral)))
    root_cause = {
        "classification": "SCHEMA_DESCRIPTION_AMBIGUITY",
        "evidence": [
            "The frozen Prediction Path schema and strict validator both require FLAT [0,0].",
            "The historical provider-visible prompt only used the terse phrase 'FLAT has zero bounds' and contained no field-level FLAT example or explicit non-zero-range prohibition.",
            "All six repeated historical failures express FLAT with a non-zero range while preserving otherwise parseable stage shape.",
        ],
        "validator_change_authorized": False,
        "historical_cases": neutral,
    }
    fixtures = fixture_validation(); dry_run = provider_dry_run(contract_version)
    diff = {
        "parent_contract_version": prospective.PARENT_CONTRACT_VERSION,
        "prospective_contract_version": prospective.PROSPECTIVE_CONTRACT_VERSION,
        "scientific_changes": ["Explicit provider-visible FLAT exact-zero pip bounds and one positive JSON example."],
        "unchanged": spec["inherited_unchanged"],
        "historical_scope": "unchanged",
    }
    outputs = {
        "repair_manifest.json": {"repair_run_id": output_dir.name, "decision": "V2_1_STEP8_R1_FLAT_OUTPUT_CONTRACT_REPAIR_VALIDATED", "provider_calls": 0, "apps_script_calls": 0, "google_sheets_writes": 0, "historical_artifacts_changed": False, "prospective_contract_fingerprint": spec["contract_fingerprint"]},
        "root_cause_analysis.json": root_cause,
        "historical_contract_verification.json": historical,
        "prospective_contract_manifest.json": spec,
        "contract_diff.json": diff,
        "prompt_diff.json": {"historical_prompt_rule": "FLAT has zero bounds.", "prospective_addition": prospective.PROMPT_RULE, "only_scientific_prompt_change": "FLAT exact-zero representation"},
        "schema_diff.json": {"changed": False, "reason": "Frozen schema already states FLAT and UNCERTAIN require [0,0].", "schema_fingerprint": fp["schema_fingerprint"]},
        "validator_diff.json": {"changed": False, "reason": "Frozen validator already raises PATH_NEUTRAL_PIP_RANGE for non-zero FLAT bounds.", "validator_fingerprint": fp["validator_fingerprint"]},
        "parser_diff.json": {"changed": False, "reason": "Parser remains frozen and strict.", "parser_fingerprint": fp["parser_fingerprint"]},
        "flat_fixture_validation.json": fixtures,
        "rejected_response_fixture_audit.json": {"path_neutral_pip_range_cases": neutral, "count": len(neutral), "historical_statuses_changed": 0},
        "provider_model_dry_run.json": dry_run,
        "pack_symmetry_validation.json": {"passed": True, "permitted_differences": sorted(single.ALLOWED_PROMPT_DIFFERENCES), "provider_visible_contract_rule_identical_across_arms": True},
        "leakage_validation.json": {"passed": True, "exposed_fields": 0, "provider_calls": 0},
        "historical_reconstruction_validation.json": historical,
    }
    for name, value in outputs.items():
        write_json(output_dir / name, value)
    (output_dir / "repair_summary.md").write_text(
        "# Prospective FLAT Path-Stage Output Contract Repair\n\n"
        "The frozen validator already required FLAT bounds of exactly zero. The prospective-only repair makes that field-level rule and a positive JSON example explicit in provider-visible prompts. Historical artifacts and their rejected statuses remain unchanged.\n"
    )
    return output_dir, outputs["repair_manifest.json"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--contract-version", required=True)
    args = parser.parse_args()
    path, manifest = run(args.output_dir, contract_version=args.contract_version)
    print(json.dumps({"output_dir": str(path), **manifest}, sort_keys=True))


if __name__ == "__main__":
    main()
