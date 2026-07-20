#!/usr/bin/env python3
"""Build the read-only PreSignal v2.1 Step 9 promotion decision.

This is an evidence gate. It verifies frozen historical artifacts and the
prospective-only FLAT contract, then writes an authorization for future shadow
collection. It has no provider, acquisition, workbook, or production path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import analyze_presignal_v21_step6_paired_batch_v1 as paired_analysis
from automation import presignal_v21_prospective_flat_contract_v1 as prospective

TAG = "presignal-v2.1-event-path-contract-v1-frozen"
TAG_TARGET = "e8cd4f3fa2f3d7c1b2e624e32f1aea0a6c9866c0"
BATCH_RUN_ID = "STEP6-BATCH-f718192a7566138c3fda"
ANALYSIS_RUN_ID = "STEP7-PAIRED-1dbbf399d2f73793e4f3"
REPAIR_RUN_ID = "STEP8-R1-FLAT-a40c0ee570cde5c1e52e"
BATCH = ROOT / "outputs" / "presignal_v21_step6_batch" / BATCH_RUN_ID
ANALYSIS = ROOT / "outputs" / "presignal_v21_step7_paired_analysis" / ANALYSIS_RUN_ID
REPAIR = ROOT / "outputs" / "presignal_v21_step8_r1_flat_contract_repair" / REPAIR_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_step9_promotion_decision"
DECISION = "V2_1_STEP9_PROMOTION_DEFERRED_PROSPECTIVE_SHADOW_AUTHORIZED"


class PromotionDecisionError(RuntimeError):
    """Frozen evidence cannot support a Step 9 decision."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def tree_fingerprint(path: Path) -> str:
    records = [
        {"path": str(item.relative_to(path)), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
        for item in sorted(path.rglob("*")) if item.is_file()
    ]
    return sha256(records)


def tag_target() -> str:
    return subprocess.check_output(["git", "rev-parse", TAG + "^{}"], cwd=ROOT, text=True).strip()


def verify_evidence() -> dict[str, Any]:
    if tag_target() != TAG_TARGET:
        raise PromotionDecisionError("FROZEN_CONTRACT_TAG_TARGET")
    batch_before, analysis_before, repair_before = tree_fingerprint(BATCH), tree_fingerprint(ANALYSIS), tree_fingerprint(REPAIR)
    batch_summary = read_json(BATCH / "batch_completion_summary.json")
    analysis_manifest = read_json(ANALYSIS / "analysis_manifest.json")
    repair_manifest = read_json(REPAIR / "repair_manifest.json")
    historical = paired_analysis.run(batch_run_id=BATCH_RUN_ID, verify_only=True)
    spec = prospective.contract_spec()
    if historical["analysis_run_id"] != ANALYSIS_RUN_ID or historical["analysis_fingerprint"] != analysis_manifest["analysis_fingerprint"]:
        raise PromotionDecisionError("HISTORICAL_ANALYSIS_FINGERPRINT")
    if historical["interpretation"]["evidence_classification"] != "INDETERMINATE_DUE_TO_MISSINGNESS_OR_SMALL_SAMPLE":
        raise PromotionDecisionError("HISTORICAL_INTERPRETATION_CHANGED")
    if repair_manifest.get("decision") != "V2_1_STEP8_R1_FLAT_OUTPUT_CONTRACT_REPAIR_VALIDATED":
        raise PromotionDecisionError("PROSPECTIVE_REPAIR_NOT_VALIDATED")
    if spec["contract_fingerprint"] != repair_manifest.get("prospective_contract_fingerprint"):
        raise PromotionDecisionError("PROSPECTIVE_CONTRACT_FINGERPRINT")
    batch_after, analysis_after, repair_after = tree_fingerprint(BATCH), tree_fingerprint(ANALYSIS), tree_fingerprint(REPAIR)
    if (batch_before, analysis_before, repair_before) != (batch_after, analysis_after, repair_after):
        raise PromotionDecisionError("FROZEN_EVIDENCE_MUTATED")
    return {
        "frozen_contract_tag": TAG,
        "frozen_contract_tag_target": TAG_TARGET,
        "historical_batch_run_id": BATCH_RUN_ID,
        "historical_batch_fingerprint": batch_after,
        "historical_analysis_run_id": ANALYSIS_RUN_ID,
        "historical_analysis_fingerprint": historical["analysis_fingerprint"],
        "prospective_repair_run_id": REPAIR_RUN_ID,
        "prospective_contract_version": spec["contract_version"],
        "prospective_contract_fingerprint": spec["contract_fingerprint"],
        "accepted_forecasts": batch_summary["accepted_forecasts"],
        "rejected_responses": len(historical["rejected"]),
        "complete_paired_observations": len(historical["complete_rows"]),
        "unique_complete_episodes": historical["cluster"]["unique_episode_clusters"],
        "historical_trees_unchanged": True,
        "historical": historical,
    }


def prospective_population_plan() -> dict[str, Any]:
    return {
        "unit_of_collection": "unique Event Episode",
        "providers_per_episode": 3,
        "planned_providers_models": [
            {"provider": "Anthropic", "model": "claude-haiku-4-5"},
            {"provider": "Gemini", "model": "gemini-2.5-flash-lite"},
            {"provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18"},
        ],
        "initial_operational_checkpoint_unique_episodes": 12,
        "minimum_interpretable_unique_episodes": 40,
        "target_unique_episodes": 60,
        "maximum_bounded_unique_episodes": 80,
        "expected_provider_episode_pairs_at_target": 180,
        "expected_forecast_arms_at_target": 360,
        "maximum_forecast_arms": 480,
        "checkpoint_policy": [
            "At 12 unique Episodes, verify operational completion, leakage, exact model identity, and contract adherence only.",
            "At 40 unique Episodes, perform one preregistered adequacy and missingness review without prompt or eligibility optimization.",
            "Continue toward 60 unique Episodes if controls hold; stop at 80 until a new explicit decision review.",
        ],
        "prohibited_checkpoint_actions": ["prompt optimization based on accuracy", "arm rebalancing based on outcomes", "provider/model substitution", "main-path promotion"],
    }


def assessments(evidence: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    historical = evidence["historical"]
    primary, cluster, bounds, attention = historical["primary"], historical["cluster"], historical["bounds"], historical["attention"]
    return {
        "scientific": {
            "status": "VALID_FOR_PROSPECTIVE_SHADOW_REPLICATION",
            "finding": "Frozen artifacts validate Predictions, Prediction Paths, deterministic Outcome attachment, 5/15/30/60 evaluation, reconstruction, and leakage-safe paired comparison.",
        },
        "comparative": {
            "status": "NO_PACK_SUPERIORITY_SUPPORTED",
            "pack_a_accuracy": primary["pack_a_accuracy"], "pack_e_accuracy": primary["pack_e_accuracy"],
            "paired_difference_pack_a_minus_pack_e": primary["paired_risk_difference_pack_a_minus_pack_e"],
            "exact_mcnemar_p_value": primary["exact_mcnemar_two_sided_p_value"],
            "episode_cluster_permutation_p_value": cluster["two_sided_p_value"],
        },
        "population": {
            "status": "INSUFFICIENT_FOR_MAIN_PATH_PROMOTION",
            "unique_complete_episodes": cluster["unique_episode_clusters"],
            "complete_pairs": primary["pair_count"],
            "limitations": ["Episode-clustered provider rows", "seven incomplete pairs", "limited Event-type diversity", "wide paired uncertainty"],
        },
        "operational": {
            "status": "SUFFICIENT_FOR_BOUNDED_PROSPECTIVE_SHADOW",
            "controls": ["exact provider/model control", "Pack A/E prompt symmetry", "restart and duplicate-call controls", "deterministic reconstruction", "zero leakage", "validated prospective FLAT repair"],
        },
        "attention": {
            "status": "SUFFICIENT_WITH_MONITORING",
            "completed_pairs_reviewed": attention["completed_pairs_reviewed"],
            "adequate": attention["attention_scope_adequate"],
            "extension_candidates": attention["extension_candidates"],
            "policy": "Reuse the existing member-level Attention infrastructure for new sessions; retain per-pair adequacy monitoring and do not reuse historical Attention answers.",
        },
        "missingness": {
            "status": "MATERIAL_LIMITATION",
            "complete_case_difference": bounds["complete_case_observed_difference"],
            "worst_case_pack_a_difference": bounds["worst_case_pack_a_difference"],
            "best_case_pack_a_difference": bounds["best_case_pack_a_difference"],
            "effect_sign_survives_bounds": bounds["effect_sign_survives_bounds"],
        },
    }


def artifacts(evidence: Mapping[str, Any]) -> dict[str, Any]:
    plan = prospective_population_plan(); assessment = assessments(evidence)
    authorization = {
        "authorized": True,
        "scope": "Post-Step-9 Prospective Shadow Replication",
        "contract_version": evidence["prospective_contract_version"],
        "required_controls": [
            "New v2 Attention Map for each new session using existing infrastructure.",
            "New Information Requests and shared Pack A/E inputs for each new session.",
            "Same provider/model within each Pack A/E pair; identical prompts except arm and pack content.",
            "Forecast 5/15/30/60-minute paths and preserve 15-minute direction correctness as primary endpoint.",
            "Freeze both forecasts before release; attach deterministic Outcome only after release.",
            "Preserve provider disagreement, rejected responses, and no-trading shadow-only status.",
        ],
        "explicitly_not_authorized": ["provider execution in this decision task", "production routing", "automatic trading", "historical artifact revision", "direct Session Forecast retirement", "v3.0 transition"],
    }
    endpoint = {
        "primary_endpoint": "15-minute direction correctness",
        "primary_comparison": "paired Pack A minus Pack E within provider + model + Episode identity",
        "primary_cluster": "Episode",
        "secondary_endpoints": ["5-minute direction correctness", "30-minute direction correctness", "60-minute direction correctness", "numeric path score", "reversal/path validity", "completion rate", "Attention scope adequacy"],
        "missingness_policy": "Preserve rejected responses, arm/provider completion, contract failure category, prompt length, Pack sizes, and execution order. Do not impute rejected forecasts or treat them as incorrect unless a future preregistered rule requires it.",
    }
    criteria = {
        "scientific": ["At least the bounded target of unique Episodes, with useful paired and Episode-cluster-aware uncertainty.", "No material arm-dependent missingness and no single provider or Episode driving the result.", "Coherent horizon/path evidence and acceptable Attention adequacy."],
        "operational": ["Acceptable paired completion", "controlled call usage", "zero leakage", "no model substitution", "deterministic reconstruction", "stable Outcome attachment", "no recurring output-contract defect"],
        "governance": ["Historical and prospective samples remain separate", "shadow outputs remain non-production", "a new explicit Step 9 review is required", "no automatic v3.0 naming or migration"],
        "automatic_promotion": False,
    }
    roadmap = {
        "Step 1": "COMPLETE", "Step 2": "COMPLETE", "Step 3": "COMPLETE", "Step 4": "COMPLETE",
        "Step 5": "COMPLETE", "Step 6": "COMPLETE", "Step 7": "COMPLETE", "Step 8A": "COMPLETE",
        "Step 8B": "COMPLETE", "Step 8-R1": "COMPLETE", "Step 9": "COMPLETE",
        "next_authorized_work": "Post-Step-9 Prospective Shadow Replication",
        "historical_name_mapping": "historical batch execution = Step 8A; historical paired analysis = Step 8B",
    }
    promotion = {
        "decision": DECISION,
        "main_path_promotion": "DEFERRED",
        "direct_session_forecasting": "RETAIN_ACTIVE",
        "shadow_only_operation": "CONTINUES",
        "prospective_shadow_replication": "AUTHORIZED",
        "attention_redesign": "NOT_REQUIRED",
        "v3_status": "NOT_AUTHORIZED",
        "rationale": "The architecture and controls are valid, but comparative historical evidence is indeterminate under Episode clustering and missingness bounds.",
    }
    return {
        "roadmap_status.json": roadmap,
        "scientific_validity_assessment.json": assessment["scientific"],
        "comparative_evidence_assessment.json": assessment["comparative"],
        "population_sufficiency_assessment.json": assessment["population"],
        "operational_stability_assessment.json": assessment["operational"],
        "attention_scope_assessment.json": assessment["attention"],
        "promotion_decision.json": promotion,
        "prospective_shadow_authorization.json": authorization,
        "prospective_population_plan.json": plan,
        "prospective_endpoint_preregistration.json": endpoint,
        "future_promotion_criteria.json": criteria,
        "direct_session_forecast_status.json": {"status": "RETAIN_ACTIVE", "future_shadow_mode": "research-only sidecar beside direct Session Forecasting; production remains unchanged."},
        "v3_status.json": {"status": "NOT_AUTHORIZED", "reason": "v3.0 requires later prospective evidence and a new explicit decision."},
        "risk_and_limitations.json": {"risks": assessment["population"]["limitations"] + ["Historical missingness bounds cross zero."], "mitigation": "bounded paired prospective collection with Episode clustering and preserved failure records."},
        "next_task_authorization.json": {"authorized": True, "task": "Implement and prepare the bounded Post-Step-9 prospective Event-Path shadow collection using the repaired contract, without starting provider execution."},
    }


def run(output_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    before = {"batch": tree_fingerprint(BATCH), "analysis": tree_fingerprint(ANALYSIS), "repair": tree_fingerprint(REPAIR)}
    evidence = verify_evidence()
    run_id = "STEP9-PROMOTION-" + sha256({key: value for key, value in evidence.items() if key != "historical"}).split(":", 1)[1][:20]
    destination = output_dir or OUTPUT_ROOT / run_id
    content = artifacts(evidence)
    decision_fingerprint = sha256({"evidence": {key: value for key, value in evidence.items() if key != "historical"}, "decision": content["promotion_decision.json"], "authorization": content["prospective_shadow_authorization.json"], "plan": content["prospective_population_plan.json"]})
    manifest = {"decision_run_id": run_id, "decision": DECISION, "decision_fingerprint": decision_fingerprint, "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0}, "workbook_changes": 0, "production_changes": 0, "historical_artifacts_changed": False}
    historical_verification = {key: value for key, value in evidence.items() if key != "historical"} | {"historical_summary": {"primary": evidence["historical"]["primary"], "cluster": evidence["historical"]["cluster"], "bounds": evidence["historical"]["bounds"], "attention": evidence["historical"]["attention"]}}
    for name, value in {"step9_manifest.json": manifest, "historical_evidence_verification.json": historical_verification, "prospective_contract_verification.json": prospective.contract_spec(), **content}.items():
        write_json(destination / name, value)
    (destination / "step9_summary.md").write_text(
        "# PreSignal v2.1 Step 9 Promotion Decision\n\n"
        "`V2_1_STEP9_PROMOTION_DEFERRED_PROSPECTIVE_SHADOW_AUTHORIZED`\n\n"
        "The Event-Path architecture is valid for a bounded prospective shadow replication, but the frozen historical Pack A/E comparison remains indeterminate. Direct Session Forecasting remains active; v3.0 is not authorized.\n"
    )
    after = {"batch": tree_fingerprint(BATCH), "analysis": tree_fingerprint(ANALYSIS), "repair": tree_fingerprint(REPAIR)}
    if before != after:
        raise PromotionDecisionError("FROZEN_EVIDENCE_MUTATED")
    return destination, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    destination, manifest = run(args.output_dir)
    print(json.dumps({"output_dir": str(destination), **manifest}, sort_keys=True))


if __name__ == "__main__":
    main()
