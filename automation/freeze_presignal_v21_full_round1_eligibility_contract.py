#!/usr/bin/env python3
"""Freeze the revised Round 1 Episode eligibility and input-admissibility contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_population_audit"
    / "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"
)
PREVALIDATION = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7"
)
STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_contract"

GOVERNING_AUDIT_ID = "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"
PRIMARY_COUNTRY = "US"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_population_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    population_rows = read_jsonl(AUDIT_ROOT / "episode_population_manifest.jsonl")
    prevalidation_rows = {row["episode_id"]: row for row in read_jsonl(PREVALIDATION / "population_admission.jsonl")}
    omitted_rows = {row["episode_id"]: row for row in read_jsonl(AUDIT_ROOT / "omitted_episode_audit.jsonl")}
    return population_rows, prevalidation_rows, omitted_rows


def count_existing_pack_ids() -> tuple[set[str], set[str]]:
    pack_a = {row["episode_id"] for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl") if row["release_ts"].startswith("2024-05") or row["release_ts"].startswith("2024-06") or row["release_ts"].startswith("2024-07")}
    pack_e = {row["episode_id"] for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl") if row["release_ts"].startswith("2024-05") or row["release_ts"].startswith("2024-06") or row["release_ts"].startswith("2024-07")}
    return pack_a, pack_e


def candidate_status_contract() -> dict[str, Any]:
    return {
        "layer": "CalendarCandidate",
        "statuses": {
            "VALID_EVENT_CANDIDATE": "Source-relevant scheduled release row or canonical grouped release with resolved identity, in-scope country, and in-range release timestamp.",
            "DUPLICATE": "Duplicate source calendar row or duplicate canonical candidate that must remain accounted for but not double-counted.",
            "NON_EVENT": "Source row is not a genuine scheduled economic release.",
            "OUTSIDE_DATE_RANGE": "Source row is outside the authorized historical period.",
            "COUNTRY_OUT_OF_SCOPE": "Source row is outside the study country scope.",
            "EXPLICITLY_EXCLUDED_EVENT_TYPE": "Source row belongs to an event type excluded by explicit governance rather than by downstream availability.",
            "IDENTITY_UNRESOLVED": "Event membership or canonical identity is insufficiently resolved for Episode construction.",
            "RELEASE_TIME_UNRESOLVED": "Release timestamp is insufficiently resolved for deterministic cutoff construction.",
        },
        "freeze_rule": "Every source-relevant row or canonical candidate group must be accounted for before Episode admission.",
    }


def episode_eligibility_contract() -> dict[str, Any]:
    return {
        "layer": "EpisodeAdmission",
        "status_axis": {
            "ELIGIBLE": "Genuine scheduled in-scope release inside the authorized period with resolved membership, identity, release timestamp, and deterministic forecast cutoff.",
            "INELIGIBLE": "Episode candidate fails one or more minimum admission conditions.",
        },
        "required_conditions": [
            "genuine scheduled release",
            "authorized date range",
            "in-scope country and study definition",
            "resolved Episode membership",
            "resolved standalone or batch identity",
            "resolved release timestamp",
            "deterministic forecast cutoff",
            "no duplicate canonical Episode",
        ],
        "explicit_non_conditions": [
            "Attention result exists",
            "Information Requests exist",
            "Pack A is complete",
            "Pack E is complete",
            "all requested information is available",
            "all providers can execute",
            "Outcome data is available",
            "all market-data providers agree",
        ],
    }


def attention_status_contract() -> dict[str, Any]:
    return {
        "layer": "AttentionStatus",
        "statuses": {
            "ATTENTION_AVAILABLE": "Exact historical Attention lineage already exists and is reusable without reinterpretation.",
            "ATTENTION_RECONSTRUCTABLE": "Exact historical Attention is absent but Episode admission is intact and a leakage-safe reconstruction path may be attempted later.",
            "ATTENTION_UNAVAILABLE": "No safe exact or reconstructable Attention path is presently proven from frozen lineage.",
            "ATTENTION_INVALID": "Attention lineage exists but is internally contradictory or contract-invalid.",
            "ATTENTION_NOT_REQUIRED_BY_PROTOCOL": "The active protocol path does not require Attention for the relevant operation.",
        },
        "policy": [
            "Missing Attention must not change Episode eligibility.",
            "Attention availability affects downstream Pack and arm executability only.",
        ],
    }


def pack_status_contract() -> dict[str, Any]:
    return {
        "layer": "PackConstructionStatus",
        "statuses": {
            "PACK_EXISTING_EXACT": "Frozen Pack artifact already exists with exact admissible lineage.",
            "PACK_RECONSTRUCTABLE": "Required frozen Pack procedure can likely be rerun truthfully from admissible inputs without changing Episode identity.",
            "PACK_PARTIALLY_RECONSTRUCTABLE": "Some admissible inputs appear available but full Pack completion is not yet proven.",
            "PACK_UNAVAILABLE": "The Pack cannot presently be constructed from proven admissible inputs.",
            "PACK_INVALID": "Pack artifact exists but violates the frozen contract or provenance rules.",
            "PACK_NOT_REQUIRED": "The specific protocol path does not require that Pack.",
        },
        "policy": [
            "Pack success means truthful completion from admissible inputs, not perfect field completeness.",
            "Missing optional inputs become unavailable fields rather than Episode exclusions.",
        ],
    }


def input_admissibility_contract() -> dict[str, Any]:
    return {
        "layer": "InputAdmissibility",
        "statuses": {
            "PRE_CUTOFF_CONFIRMED": "Input lineage proves the value was available before the Episode forecast cutoff.",
            "POST_CUTOFF_REJECTED": "Input was published or updated after the cutoff and is individually rejected.",
            "HISTORICAL_VERSION_UNVERIFIED": "The required historical version cannot yet be proven from frozen lineage.",
            "PUBLICATION_TIME_UNVERIFIED": "Publication timing exists but cannot yet be proven to be pre-cutoff.",
            "SOURCE_UNAVAILABLE": "Input source is not presently available from authorized lineage.",
            "NOT_APPLICABLE": "The input category is not required for the current Pack or evaluation path.",
        },
        "minimum_lineage_fields": [
            "source",
            "source_record_id",
            "published_at",
            "updated_at",
            "effective_at",
            "retrieved_at",
            "forecast_cutoff",
            "historical_version_id",
            "admissibility_status",
            "reason",
        ],
        "policy": [
            "Input admissibility is evaluated per input item, not per Episode.",
            "Unsafe or unverifiable inputs become rejected or unavailable fields; they do not delete the Episode.",
        ],
    }


def runtime_status_contract() -> dict[str, Any]:
    return {
        "layer": "ForecastArmRuntimeStatus",
        "statuses": {
            "SUCCESS": "Provider arm executed and returned a terminal response.",
            "PROVIDER_REJECTED": "Provider declined the request without transport failure.",
            "TRANSPORT_FAILED": "Call failed at transport or bridge level.",
            "STATUS_UNKNOWN": "Expected arm has not yet been attempted or terminal evidence is absent.",
        },
    }


def forecast_status_contract() -> dict[str, Any]:
    return {
        "layer": "ForecastArmScientificStatus",
        "statuses": {
            "DIRECTIONAL": "Forecast contains a valid directional hypothesis.",
            "NO_SIGNAL": "Forecast abstains directionally while remaining contract-valid.",
            "INCOMPLETE": "Forecast arm did not produce a usable scientific object.",
        },
        "policy": [
            "Runtime failures, provider rejections, schema failures, NO_SIGNAL, and incorrect forecasts remain distinct states.",
        ],
    }


def outcome_status_contract() -> dict[str, Any]:
    return {
        "layer": "OutcomeStatus",
        "statuses": {
            "MULTI_SOURCE_CONFIRMED": "Primary provider and at least one independent verification provider agree within frozen tolerances.",
            "MULTI_SOURCE_CONSENSUS": "Two or more providers form a deterministic agreement cluster while another is an outlier.",
            "SINGLE_SOURCE_ONLY": "Only one valid provider observation exists; this is not independently verified.",
            "SOURCE_DISAGREEMENT": "Multiple valid providers disagree with no deterministic consensus.",
            "OUTCOME_UNAVAILABLE": "No scientifically usable target observation exists.",
        },
        "policy": [
            "Outcome availability never retroactively changes Episode eligibility.",
            "Outcome status controls only target-specific evaluation availability.",
        ],
    }


def evaluation_status_contract() -> dict[str, Any]:
    return {
        "layer": "EvaluationStatus",
        "statuses": {
            "CORRECT": "Directional forecast and verified target Outcome are both available and directionally correct.",
            "INCORRECT": "Directional forecast and verified target Outcome are both available and directionally incorrect.",
            "OUTCOME_UNAVAILABLE": "Directional forecast exists but the required target Outcome is unavailable.",
            "NOT_APPLICABLE": "Directional accuracy is not defined for NO_SIGNAL or INCOMPLETE arms.",
        },
        "policy": [
            "Directional accuracy denominator excludes NO_SIGNAL and INCOMPLETE.",
            "Outcome-unavailable forecasts remain part of operational accounting but not of the directional-accuracy denominator.",
        ],
    }


def classify_attention(row: Mapping[str, Any]) -> tuple[str, str]:
    status = row["historical_attention_status"]
    if status == "ATTENTION_LINEAGE_AVAILABLE":
        return "ATTENTION_AVAILABLE", ""
    if status == "ATTENTION_LINEAGE_MISSING":
        return "ATTENTION_RECONSTRUCTABLE", "EXACT_HISTORICAL_ATTENTION_ABSENT"
    if status == "ATTENTION_LINEAGE_MISMATCH":
        return "ATTENTION_UNAVAILABLE", "NO_EXACT_PARENT_SESSION_OR_LINEAGE_CONTRADICTION"
    return "ATTENTION_UNAVAILABLE", "UNPROVEN_ATTENTION_STATE"


def classify_pack(existing_exact: bool, prevalidation_row: Mapping[str, Any], pack_kind: str) -> tuple[str, str]:
    if existing_exact:
        return "PACK_EXISTING_EXACT", ""
    compat_status = (
        prevalidation_row["request_compatibility_status"]
        if pack_kind == "PACK_A"
        else prevalidation_row["pack_compatibility_status"]
    )
    compat_reason = (
        prevalidation_row["request_compatibility_reason"]
        if pack_kind == "PACK_A"
        else prevalidation_row["pack_compatibility_reason"]
    )
    if compat_status == "COMPATIBLE":
        return "PACK_RECONSTRUCTABLE", "EXACT_PACK_NOT_FROZEN_BUT_INPUT_PATH_COMPATIBLE"
    if compat_reason == "NO_EXACT_PARENT_SESSION":
        return "PACK_UNAVAILABLE", compat_reason
    return "PACK_PARTIALLY_RECONSTRUCTABLE", compat_reason or "PACK_STATUS_UNPROVEN"


def classify_input_admissibility(pack_status: str) -> tuple[str, str]:
    if pack_status == "PACK_EXISTING_EXACT":
        return "PRE_CUTOFF_CONFIRMED", "EXACT_FROZEN_PACK_LINEAGE"
    if pack_status == "PACK_RECONSTRUCTABLE":
        return "HISTORICAL_VERSION_UNVERIFIED", "ITEM_LEVEL_REPLAY_REQUIRED_BEFORE_USE"
    if pack_status == "PACK_UNAVAILABLE":
        return "SOURCE_UNAVAILABLE", "REQUIRED_HISTORICAL_SOURCE_PATH_NOT_PROVEN"
    return "PUBLICATION_TIME_UNVERIFIED", "PARTIAL_OR_UNPROVEN_INPUT_PATH"


def classify_episode_eligibility(row: Mapping[str, Any]) -> tuple[str, str]:
    required = [
        bool(row["episode_id"]),
        bool(row["release_ts"]),
        bool(row["forecast_cutoff_ts"]),
        row["member_event_count"] > 0,
        len(row["member_event_ids"]) == row["member_event_count"],
    ]
    if all(required):
        return "ELIGIBLE", ""
    return "INELIGIBLE", "MINIMUM_ADMISSION_FIELDS_MISSING"


def classify_forecast_arm_executability(attention_status: str, pack_a_status: str, pack_e_status: str) -> dict[str, Any]:
    exact = attention_status == "ATTENTION_AVAILABLE" and pack_a_status == "PACK_EXISTING_EXACT" and pack_e_status == "PACK_EXISTING_EXACT"
    reconstructable = attention_status in {"ATTENTION_AVAILABLE", "ATTENTION_RECONSTRUCTABLE"} and pack_a_status in {"PACK_EXISTING_EXACT", "PACK_RECONSTRUCTABLE"} and pack_e_status in {"PACK_EXISTING_EXACT", "PACK_RECONSTRUCTABLE"}
    if exact:
        return {
            "episode_execution_readiness": "FULL_SIX_ARM_EXECUTABLE_FROM_EXISTING_INPUTS",
            "currently_blocked_arm_count": 0,
            "expected_future_arm_count": 6,
        }
    if reconstructable:
        return {
            "episode_execution_readiness": "ELIGIBLE_BUT_REQUIRES_INPUT_RECONSTRUCTION",
            "currently_blocked_arm_count": 6,
            "expected_future_arm_count": 6,
        }
    return {
        "episode_execution_readiness": "ELIGIBLE_BUT_INPUTS_CURRENTLY_UNAVAILABLE",
        "currently_blocked_arm_count": 6,
        "expected_future_arm_count": 6,
    }


def classify_outcome(prevalidation_row: Mapping[str, Any]) -> tuple[str, str]:
    if prevalidation_row["legacy_outcome_status"] == "VALID":
        return "MULTI_SOURCE_CONFIRMED", "FROZEN_VERIFIED_OUTCOME_AVAILABLE"
    return "OUTCOME_UNAVAILABLE", str(prevalidation_row.get("population_exclusion_detail") or prevalidation_row.get("legacy_outcome_status") or "")


def classify_t15_evaluation(outcome_status: str) -> tuple[str, str]:
    if outcome_status == "MULTI_SOURCE_CONFIRMED":
        return "NOT_APPLICABLE", "FORECAST_NOT_RUN_IN_THIS_MOVE"
    return "OUTCOME_UNAVAILABLE", "TARGET_OUTCOME_NOT_USABLE"


def build_application_row(
    row: Mapping[str, Any],
    prevalidation_row: Mapping[str, Any],
    existing_pack_a_ids: set[str],
    existing_pack_e_ids: set[str],
) -> dict[str, Any]:
    episode_eligibility_status, episode_eligibility_reason = classify_episode_eligibility(row)
    attention_status, attention_reason = classify_attention(row)
    pack_a_status, pack_a_reason = classify_pack(row["episode_id"] in existing_pack_a_ids, prevalidation_row, "PACK_A")
    pack_e_status, pack_e_reason = classify_pack(row["episode_id"] in existing_pack_e_ids, prevalidation_row, "PACK_E")
    pack_a_input_status, pack_a_input_reason = classify_input_admissibility(pack_a_status)
    pack_e_input_status, pack_e_input_reason = classify_input_admissibility(pack_e_status)
    forecast_executability = classify_forecast_arm_executability(attention_status, pack_a_status, pack_e_status)
    outcome_status, outcome_reason = classify_outcome(prevalidation_row)
    t15_eval_status, t15_eval_reason = classify_t15_evaluation(outcome_status)
    return {
        "episode_id": row["episode_id"],
        "release_ts": row["release_ts"],
        "episode_type": row["episode_type"],
        "member_event_count": row["member_event_count"],
        "event_family": row["event_family"],
        "calendar_candidate_status": "VALID_EVENT_CANDIDATE",
        "calendar_candidate_reason": "",
        "episode_eligibility_status": episode_eligibility_status,
        "episode_eligibility_reason": episode_eligibility_reason,
        "attention_status": attention_status,
        "attention_reason": attention_reason,
        "pack_a_status": pack_a_status,
        "pack_a_reason": pack_a_reason,
        "pack_e_status": pack_e_status,
        "pack_e_reason": pack_e_reason,
        "pack_a_input_admissibility": pack_a_input_status,
        "pack_a_input_admissibility_reason": pack_a_input_reason,
        "pack_e_input_admissibility": pack_e_input_status,
        "pack_e_input_admissibility_reason": pack_e_input_reason,
        "forecast_arm_runtime_status_rule": "SUCCESS|PROVIDER_REJECTED|TRANSPORT_FAILED|STATUS_UNKNOWN",
        "forecast_arm_scientific_status_rule": "DIRECTIONAL|NO_SIGNAL|INCOMPLETE",
        "episode_execution_readiness": forecast_executability["episode_execution_readiness"],
        "currently_blocked_arm_count": forecast_executability["currently_blocked_arm_count"],
        "expected_future_arm_count": forecast_executability["expected_future_arm_count"],
        "outcome_status_t15": outcome_status,
        "outcome_status_t15_reason": outcome_reason,
        "evaluation_status_t15": t15_eval_status,
        "evaluation_status_t15_reason": t15_eval_reason,
        "legacy_population_status": prevalidation_row["population_status"],
        "legacy_population_exclusion_detail": prevalidation_row["population_exclusion_detail"],
    }


def build_state_transition_table() -> dict[str, Any]:
    return {
        "separation_rules": [
            {
                "if": "eligible Episode + missing Attention",
                "then": "Episode remains ELIGIBLE; AttentionStatus becomes ATTENTION_RECONSTRUCTABLE or ATTENTION_UNAVAILABLE",
            },
            {
                "if": "eligible Episode + incomplete Pack",
                "then": "Episode remains ELIGIBLE; PackConstructionStatus changes without retroactive Episode exclusion",
            },
            {
                "if": "valid forecast + Outcome unavailable",
                "then": "Forecast remains accounted-for; EvaluationStatus becomes OUTCOME_UNAVAILABLE",
            },
            {
                "if": "provider transport failure",
                "then": "ForecastArmRuntimeStatus=TRANSPORT_FAILED; ForecastScientificStatus is not rewritten as NO_SIGNAL",
            },
            {
                "if": "unsafe input discovered",
                "then": "InputAdmissibility rejects that input item; Pack and Episode remain separately accounted for",
            },
        ]
    }


def build_contract_markdown(summary: Mapping[str, Any]) -> str:
    return f"""# Revised Round 1 Eligibility Contract

Decision: `REVISED_ELIGIBILITY_CONTRACT_FROZEN`

## Frozen Principle

Episode admission is determined by event reality, canonical membership, release timestamp, and deterministic cutoff safety. Attention, Pack completeness, provider execution, Outcome availability, and evaluation status are downstream layers and must not retroactively erase an admitted Episode.

## Population Result

- Candidate Episodes: `{summary['candidate_episode_count']}`
- Eligible Episodes under revised contract: `{summary['eligible_episode_count']}`
- Ineligible Episodes under revised contract: `{summary['ineligible_episode_count']}`
- Exact historical Attention: `{summary['attention_exact_count']}`
- Reconstructable Attention: `{summary['attention_reconstructable_count']}`
- Unavailable Attention: `{summary['attention_unavailable_count']}`

## Key Separation

- Missing Attention does not make an Episode ineligible.
- Missing or reconstructable Pack inputs do not make an Episode ineligible.
- Outcome unavailability does not make an Episode ineligible.
- Runtime failure, NO_SIGNAL, and incorrect direction remain separate accounting states.

## Special Case

`EP_EVENT_757e72165d3ec05306a6` is eligible under the revised contract, with exact Attention and exact Pack lineage already present, but `OUTCOME_UNAVAILABLE` at the T+15 layer. It remains in the forecast population and is excluded only from target-specific evaluation denominators requiring that Outcome.
"""


def freeze_contract(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    population_rows, prevalidation_rows, _omitted_rows = load_population_inputs()
    existing_pack_a_ids, existing_pack_e_ids = count_existing_pack_ids()
    contract_timestamp = fixed_timestamp or now()
    seed = {
        "audit": GOVERNING_AUDIT_ID,
        "timestamp": contract_timestamp,
        "population_fingerprint": fingerprint(population_rows),
    }
    run_id = f"PPHB-R1-ELIGIBILITY-CONTRACT-{contract_timestamp.replace(':', '').replace('-', '')}-{hashlib.sha256(canonical_json(seed).encode()).hexdigest()[:12]}"
    run_dir = output_root / run_id

    application_rows = [
        build_application_row(row, prevalidation_rows[row["episode_id"]], existing_pack_a_ids, existing_pack_e_ids)
        for row in population_rows
    ]
    application_rows.sort(key=lambda row: (row["release_ts"], row["episode_id"]))

    eligible_rows = [row for row in application_rows if row["episode_eligibility_status"] == "ELIGIBLE"]
    ineligible_rows = [row for row in application_rows if row["episode_eligibility_status"] != "ELIGIBLE"]

    counts = {
        "candidate_episode_count": len(application_rows),
        "eligible_episode_count": len(eligible_rows),
        "ineligible_episode_count": len(ineligible_rows),
        "attention_exact_count": sum(row["attention_status"] == "ATTENTION_AVAILABLE" for row in eligible_rows),
        "attention_reconstructable_count": sum(row["attention_status"] == "ATTENTION_RECONSTRUCTABLE" for row in eligible_rows),
        "attention_unavailable_count": sum(row["attention_status"] == "ATTENTION_UNAVAILABLE" for row in eligible_rows),
        "pack_a_exact_count": sum(row["pack_a_status"] == "PACK_EXISTING_EXACT" for row in eligible_rows),
        "pack_a_reconstructable_count": sum(row["pack_a_status"] == "PACK_RECONSTRUCTABLE" for row in eligible_rows),
        "pack_a_unavailable_count": sum(row["pack_a_status"] == "PACK_UNAVAILABLE" for row in eligible_rows),
        "pack_e_exact_count": sum(row["pack_e_status"] == "PACK_EXISTING_EXACT" for row in eligible_rows),
        "pack_e_reconstructable_count": sum(row["pack_e_status"] == "PACK_RECONSTRUCTABLE" for row in eligible_rows),
        "pack_e_unavailable_count": sum(row["pack_e_status"] == "PACK_UNAVAILABLE" for row in eligible_rows),
        "eligible_currently_blocked_from_one_or_more_forecast_arms": sum(row["currently_blocked_arm_count"] > 0 for row in eligible_rows),
        "outcome_unavailable_count": sum(row["outcome_status_t15"] == "OUTCOME_UNAVAILABLE" for row in eligible_rows),
    }

    if counts["candidate_episode_count"] != 462:
        raise RuntimeError("CANDIDATE_EPISODE_COUNT_UNEXPECTED")
    if counts["eligible_episode_count"] + counts["ineligible_episode_count"] != 462:
        raise RuntimeError("EPISODE_ELIGIBILITY_RECONCILIATION_FAILED")

    population_result = (
        "374_EPISODE_ELIGIBLE_POPULATION_CONFIRMED"
        if counts["eligible_episode_count"] == 374
        else "ELIGIBLE_POPULATION_REVISED_BY_CONTRACT_APPLICATION"
    )
    attention_decision = "ATTENTION_SEPARATED_FROM_EPISODE_ELIGIBILITY"
    outcome_decision = "OUTCOME_SEPARATED_FROM_EPISODE_ELIGIBILITY"
    implementation_readiness = "READY_FOR_NARROW_ELIGIBILITY_IMPLEMENTATION"
    contract_status = "REVISED_ELIGIBILITY_CONTRACT_FROZEN"

    special_case = next(row for row in application_rows if row["episode_id"] == "EP_EVENT_757e72165d3ec05306a6")
    special_case_review = {
        "episode_id": special_case["episode_id"],
        "release_ts": special_case["release_ts"],
        "revised_episode_eligibility_status": special_case["episode_eligibility_status"],
        "revised_forecast_population_status": "FORECAST_POPULATION_ELIGIBLE",
        "attention_status": special_case["attention_status"],
        "pack_a_status": special_case["pack_a_status"],
        "pack_e_status": special_case["pack_e_status"],
        "outcome_status_t15": special_case["outcome_status_t15"],
        "evaluation_status_t15": special_case["evaluation_status_t15"],
        "legacy_population_status": special_case["legacy_population_status"],
        "legacy_population_exclusion_detail": special_case["legacy_population_exclusion_detail"],
        "decision": "Outcome unavailability no longer controls Episode admission under the revised contract.",
    }

    provider_arm_projection = {
        "expected_future_matrix": [
            "Gemini x Pack A",
            "Gemini x Pack E",
            "OpenAI x Pack A",
            "OpenAI x Pack E",
            "Anthropic x Pack A",
            "Anthropic x Pack E",
        ],
        "eligible_episode_count": counts["eligible_episode_count"],
        "projected_total_provider_arms": counts["eligible_episode_count"] * 6,
        "eligible_currently_blocked_from_one_or_more_forecast_arms": counts["eligible_currently_blocked_from_one_or_more_forecast_arms"],
    }

    population_reconciliation_summary = {
        "candidate_episode_count": counts["candidate_episode_count"],
        "eligible_episode_count": counts["eligible_episode_count"],
        "ineligible_episode_count": counts["ineligible_episode_count"],
        "legacy_prevalidation_eligible_episode_count": 374,
        "legacy_prevalidation_outcome_unavailable_count": 15,
        "legacy_prevalidation_lineage_unsafe_count": 73,
        "revised_from_legacy_delta": counts["eligible_episode_count"] - 374,
        "attention_counts": {
            "exact": counts["attention_exact_count"],
            "reconstructable": counts["attention_reconstructable_count"],
            "unavailable": counts["attention_unavailable_count"],
        },
        "pack_a_counts": {
            "exact": counts["pack_a_exact_count"],
            "reconstructable": counts["pack_a_reconstructable_count"],
            "unavailable": counts["pack_a_unavailable_count"],
        },
        "pack_e_counts": {
            "exact": counts["pack_e_exact_count"],
            "reconstructable": counts["pack_e_reconstructable_count"],
            "unavailable": counts["pack_e_unavailable_count"],
        },
    }

    contract_json = {
        "governing_audit_id": GOVERNING_AUDIT_ID,
        "contract_status": contract_status,
        "population_result": population_result,
        "attention_decision": attention_decision,
        "outcome_decision": outcome_decision,
        "implementation_readiness_status": implementation_readiness,
        "layers": [
            "CalendarCandidate",
            "EpisodeAdmission",
            "AttentionStatus",
            "PackConstructionStatus",
            "InputAdmissibility",
            "ForecastArmRuntimeStatus",
            "ForecastArmScientificStatus",
            "OutcomeStatus",
            "EvaluationStatus",
        ],
        "principle": "Later-layer failures must not retroactively erase valid earlier-layer objects.",
        "summary_counts": counts,
    }

    contract_decision = {
        "contract_status": contract_status,
        "population_result": population_result,
        "attention_decision": attention_decision,
        "outcome_decision": outcome_decision,
        "implementation_readiness_status": implementation_readiness,
        "audit_fingerprint": fingerprint(
            {
                "contract_json": contract_json,
                "population_reconciliation_summary": population_reconciliation_summary,
                "special_case_review": special_case_review,
            }
        ),
        "external_calls": {
            "provider": 0,
            "market_data": 0,
            "google_writes": 0,
        },
    }

    previous_47 = [row for row in application_rows if row["attention_status"] == "ATTENTION_AVAILABLE" and row["pack_a_status"] == "PACK_EXISTING_EXACT" and row["pack_e_status"] == "PACK_EXISTING_EXACT" and row["outcome_status_t15"] == "MULTI_SOURCE_CONFIRMED"]
    previous_47.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    if len(previous_47) != 47:
        raise RuntimeError(f"PREVIOUS_47_CONTRACT_APPLICATION_COUNT_UNEXPECTED:{len(previous_47)}")

    contract_md = build_contract_markdown(counts)
    state_table = build_state_transition_table()

    run_manifest = {
        "run_id": run_id,
        "generated_at": contract_timestamp,
        "source_commit": git_head(),
        "governing_audit_id": GOVERNING_AUDIT_ID,
        "input_artifacts": [
            path_ref(AUDIT_ROOT / "episode_population_manifest.jsonl"),
            path_ref(PREVALIDATION / "population_admission.jsonl"),
            path_ref(STEP5 / "event_path_forecast_inputs_pack_a.jsonl"),
            path_ref(STEP5 / "event_path_forecast_inputs_pack_e.jsonl"),
        ],
        "notes": [
            "No provider calls",
            "No market-data calls",
            "No Google workbook writes",
            "No prior evidence modification",
        ],
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "eligibility_contract.json", contract_json)
    (run_dir / "eligibility_contract.md").write_text(contract_md)
    write_json(run_dir / "state_transition_table.json", state_table)
    write_json(run_dir / "candidate_status_contract.json", candidate_status_contract())
    write_json(run_dir / "episode_eligibility_contract.json", episode_eligibility_contract())
    write_json(run_dir / "attention_status_contract.json", attention_status_contract())
    write_json(run_dir / "pack_status_contract.json", pack_status_contract())
    write_json(run_dir / "input_admissibility_contract.json", input_admissibility_contract())
    write_json(run_dir / "runtime_status_contract.json", runtime_status_contract())
    write_json(run_dir / "forecast_status_contract.json", forecast_status_contract())
    write_json(run_dir / "outcome_status_contract.json", outcome_status_contract())
    write_json(run_dir / "evaluation_status_contract.json", evaluation_status_contract())
    write_jsonl(run_dir / "full_population_contract_application.jsonl", application_rows)
    write_json(run_dir / "population_reconciliation_summary.json", population_reconciliation_summary)
    write_jsonl(run_dir / "previous_47_contract_application.jsonl", previous_47)
    write_json(run_dir / "outcome_unavailable_case_review.json", special_case_review)
    write_json(run_dir / "provider_arm_projection.json", provider_arm_projection)
    write_json(run_dir / "contract_decision.json", contract_decision)

    return {
        "run_id": run_id,
        "run_dir": path_ref(run_dir),
        "contract_status": contract_status,
        "population_result": population_result,
        "attention_decision": attention_decision,
        "outcome_decision": outcome_decision,
        "implementation_readiness_status": implementation_readiness,
        **counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    result = freeze_contract(output_root=args.output_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
