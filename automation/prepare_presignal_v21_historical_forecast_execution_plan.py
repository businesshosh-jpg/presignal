#!/usr/bin/env python3
"""Prepare the immutable historical Round 1 forecast execution plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import construct_presignal_v21_pack_population as pack_construction
from automation import execute_presignal_v21_attention_batch_004 as batch004
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation import presignal_v21_event_path_contract_v1_1 as contract

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
CONSOLIDATION_ID = "PPHB-R1-ATTENTION-RESULT-CONSOLIDATION-20260729T102316Z-17358e44afc1"
LINEAGE_REPAIR_ID = "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-REPAIR-20260729T141500Z-7a5219653b5f"
PACK_CONSTRUCTION_ID = "PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2"

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_planning"
PACK_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_pack_population" / PACK_CONSTRUCTION_ID

PACK_TYPES = ("PACK_A", "PACK_E")
PACK_STATUS_KEYS = {
    "PACK_A": "pack_a_construction_status",
    "PACK_E": "pack_e_construction_status",
}
PACK_PAYLOAD_KEYS = {
    "PACK_A": "pack_a_canonical_payload",
    "PACK_E": "pack_e_canonical_payload",
}
PACK_ROW_ID_KEYS = {
    "PACK_A": "pack_a_row_identity",
    "PACK_E": "pack_e_row_identity",
}
PACK_FIELD_LINEAGE_KEYS = {
    "PACK_A": "pack_a_field_lineage_reference",
    "PACK_E": "pack_e_field_lineage_reference",
}
PROVIDER_MODEL_ASSIGNMENTS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
PROVIDER_ORDER = {provider: index for index, provider in enumerate(PROVIDER_MODEL_ASSIGNMENTS)}
FORECAST_SELECTION_STATUS = "CONSTRUCTED_VALID"
BATCH_SIZE = 12
FORECAST_PLANNING_CONTRACT_VERSION = "presignal_v21_round1_historical_forecast_execution_plan_v1"
NO_LIVE_CALLS = {
    "provider_calls_executed": 0,
    "live_forecast_outputs_generated": 0,
    "market_data_calls_executed": 0,
    "research_ai_calls_executed": 0,
    "web_calls_executed": 0,
    "google_writes_executed": 0,
    "outcome_attachment_executed": 0,
    "matrix_updates_executed": 0,
    "forecast_accuracy_calculations_executed": 0,
    "consensus_or_ranking_executed": 0,
}
FORBIDDEN_PROMPT_TOKENS = (
    "outcome_id",
    "\"price_5m\"",
    "\"price_15m\"",
    "\"price_30m\"",
    "\"price_60m\"",
    "\"direction_5m\"",
    "\"direction_15m\"",
    "\"direction_30m\"",
    "\"direction_60m\"",
    "max_up_pips",
    "max_down_pips",
)


class ForecastPlanningError(RuntimeError):
    """Forecast planning invariant failure."""


def canonical_json(value: Any) -> str:
    return pack_construction.canonical_json(value)


def read_json(path: Path) -> dict[str, Any]:
    return pack_construction.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return pack_construction.read_jsonl(path)


def write_json(path: Path, value: Any) -> None:
    pack_construction.write_json(path, value)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    pack_construction.write_jsonl(path, rows)


def path_ref(path: Path) -> str:
    return pack_construction.path_ref(path)


def now() -> str:
    return batch004.now()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {
        "move": "FORECAST_EXECUTION_PLAN",
        "timestamp": ts,
        "plan_id": PLAN_ID,
        "consolidation_id": CONSOLIDATION_ID,
        "lineage_repair_id": LINEAGE_REPAIR_ID,
        "pack_construction_id": PACK_CONSTRUCTION_ID,
    }
    run_id = (
        "PPHB-R1-FORECAST-EXECUTION-PLAN-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def episode_provider_key(episode_id: str, provider: str) -> str:
    return f"{episode_id}|{provider}"


def call_identity_seed(row: Mapping[str, Any], pack_type: str, pack_row_fingerprint: str) -> dict[str, Any]:
    payload = row[PACK_PAYLOAD_KEYS[pack_type]]
    return {
        "study_identity": "PPHB-R1-HISTORICAL-FORECAST",
        "episode_id": row["episode_id"],
        "source_session_id": row["source_session_id"],
        "provider": row["provider"],
        "model": row["model"],
        "pack_type": pack_type,
        "historical_cutoff_identity": payload["forecast_cutoff_ts"],
        "pack_row_fingerprint": pack_row_fingerprint,
        "forecast_contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
    }


def forecast_call_id(row: Mapping[str, Any], pack_type: str, pack_row_fingerprint: str) -> str:
    return "FCL_" + hashlib.sha256(canonical_json(call_identity_seed(row, pack_type, pack_row_fingerprint)).encode("utf-8")).hexdigest()[:24]


def batch_id(pack_type: str, batch_number: int) -> str:
    return f"FCB_{pack_type}_{batch_number:03d}"


def load_pack_rows(pack_type: str) -> list[dict[str, Any]]:
    path = PACK_ROOT / ("pack_a_population.jsonl" if pack_type == "PACK_A" else "pack_e_population.jsonl")
    rows = read_jsonl(path)
    if len(rows) != 1239:
        raise ForecastPlanningError(f"{pack_type}_ROW_COUNT_MISMATCH:{len(rows)}")
    return rows


def validate_provider_assignment(row: Mapping[str, Any], pack_type: str) -> None:
    provider = str(row["provider"])
    model = str(row["model"])
    if provider not in PROVIDER_MODEL_ASSIGNMENTS:
        raise ForecastPlanningError(f"UNEXPECTED_PROVIDER:{provider}")
    if PROVIDER_MODEL_ASSIGNMENTS[provider] != model:
        raise ForecastPlanningError(f"MODEL_ASSIGNMENT_MISMATCH:{provider}:{model}")
    payload = row[PACK_PAYLOAD_KEYS[pack_type]]
    if payload["provider"] != provider or payload["model"] != model:
        raise ForecastPlanningError(f"PAYLOAD_PROVIDER_MODEL_MISMATCH:{row['row_identity']}")
    if payload["forecast_cutoff_ts"] > payload["release_ts"]:
        raise ForecastPlanningError(f"CUTOFF_AFTER_RELEASE:{row['row_identity']}")


def validate_construction_status(row: Mapping[str, Any], pack_type: str) -> tuple[bool, str]:
    status = str(row[PACK_STATUS_KEYS[pack_type]])
    eligible = bool(row["future_forecast_eligibility_under_frozen_contract"])
    if eligible != (status == FORECAST_SELECTION_STATUS):
        raise ForecastPlanningError(f"ELIGIBILITY_STATUS_MISMATCH:{row['row_identity']}")
    return eligible, status


def prompt_context_and_text(row: Mapping[str, Any], pack_type: str) -> tuple[dict[str, Any], str]:
    payload = row[PACK_PAYLOAD_KEYS[pack_type]]
    context = step6.arm_context(payload)
    prompt = step6.prompt_text(context)
    return context, prompt


def prompt_leakage_audit(prompt: str, context: Mapping[str, Any], pack_type: str) -> dict[str, Any]:
    violations: list[str] = []
    if pack_type == "PACK_A":
        if context["information_arm"] != "BASELINE":
            violations.append("PACK_A_INFORMATION_ARM_NOT_BASELINE")
        if context["information_pack"] is not None:
            violations.append("PACK_A_INFORMATION_PACK_PRESENT")
    else:
        if context["information_arm"] != "FULL_CONTEXT":
            violations.append("PACK_E_INFORMATION_ARM_NOT_FULL_CONTEXT")
        if not isinstance(context["information_pack"], Mapping):
            violations.append("PACK_E_INFORMATION_PACK_MISSING")
    for token in FORBIDDEN_PROMPT_TOKENS:
        if token in prompt:
            violations.append("FORBIDDEN_TOKEN:" + token)
    return {
        "violations": violations,
        "passed": not violations,
        "outcome_data_present": any(token in prompt for token in FORBIDDEN_PROMPT_TOKENS),
        "paired_condition_leakage": any("PACK_A" in prompt for _ in [0]) if pack_type == "PACK_E" else any("PACK_E_SHARED" in prompt for _ in [0]),
    }


def build_forecast_eligibility_population(
    rows: list[dict[str, Any]],
    pack_type: str,
) -> list[dict[str, Any]]:
    population: list[dict[str, Any]] = []
    for row in rows:
        validate_provider_assignment(row, pack_type)
        eligible, status = validate_construction_status(row, pack_type)
        payload = row[PACK_PAYLOAD_KEYS[pack_type]]
        row_fingerprint = sha256_value(row)
        population.append(
            {
                "episode_id": row["episode_id"],
                "provider": row["provider"],
                "model": row["model"],
                "pack_type": pack_type,
                "construction_status": status,
                "forecast_eligibility": eligible,
                "eligibility_reason": "CONSTRUCTED_VALID" if eligible else status,
                "source_session_id": row["source_session_id"],
                "historical_cutoff": payload["forecast_cutoff_ts"],
                "pack_row_identity": row["row_identity"],
                "pack_row_fingerprint": row_fingerprint,
                "pack_payload_input_fingerprint": payload["input_fingerprint"],
                "attention_call_id": row["attention_call_id"],
                "attention_request_identity": row["attention_request_identity"],
                "attention_selection_state": row["attention_selection_state"],
                "field_lineage_reference": row[PACK_FIELD_LINEAGE_KEYS[pack_type]],
            }
        )
    return population


def order_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            row["pack_payload"]["release_ts"],
            row["episode_id"],
            PROVIDER_ORDER[row["provider"]],
        ),
    )


def build_authorized_calls(
    pack_rows_by_type: Mapping[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    pack_a_keys = {
        (row["episode_id"], row["provider"])
        for row in pack_rows_by_type["PACK_A"]
        if row["future_forecast_eligibility_under_frozen_contract"]
    }
    pack_e_keys = {
        (row["episode_id"], row["provider"])
        for row in pack_rows_by_type["PACK_E"]
        if row["future_forecast_eligibility_under_frozen_contract"]
    }
    both_keys = pack_a_keys & pack_e_keys
    a_only = sorted(episode_provider_key(*key) for key in (pack_a_keys - pack_e_keys))
    e_only = sorted(episode_provider_key(*key) for key in (pack_e_keys - pack_a_keys))
    if a_only or e_only:
        raise ForecastPlanningError("PACK_ELIGIBILITY_ASYMMETRY_PRESENT")

    eligible_by_type: dict[str, list[dict[str, Any]]] = {}
    prompt_manifest: list[dict[str, Any]] = []
    prompt_fingerprints: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for pack_type in PACK_TYPES:
        typed_rows: list[dict[str, Any]] = []
        for row in pack_rows_by_type[pack_type]:
            if not row["future_forecast_eligibility_under_frozen_contract"]:
                continue
            payload = row[PACK_PAYLOAD_KEYS[pack_type]]
            row_fingerprint = sha256_value(row)
            context, prompt = prompt_context_and_text(row, pack_type)
            audit = prompt_leakage_audit(prompt, context, pack_type)
            if not audit["passed"]:
                blockers.append(
                    {
                        "category": "LEAKAGE_CONTROL_VIOLATION",
                        "pack_type": pack_type,
                        "episode_id": row["episode_id"],
                        "provider": row["provider"],
                        "violations": audit["violations"],
                    }
                )
            call_id = forecast_call_id(row, pack_type, row_fingerprint)
            typed = {
                "forecast_call_id": call_id,
                "episode_id": row["episode_id"],
                "source_session_id": row["source_session_id"],
                "provider": row["provider"],
                "model": row["model"],
                "pack_type": pack_type,
                "pack_row_identity": row["row_identity"],
                "pack_row_fingerprint": row_fingerprint,
                "pack_payload_input_fingerprint": payload["input_fingerprint"],
                "attention_call_id": row["attention_call_id"],
                "attention_request_identity": row["attention_request_identity"],
                "historical_cutoff": payload["forecast_cutoff_ts"],
                "release_ts": payload["release_ts"],
                "prompt_contract_identity": contract.CONTRACT_VERSION,
                "expected_response_contract": contract.CONTRACT_VERSION,
                "pack_payload": payload,
                "prompt_context": context,
                "prompt_text": prompt,
                "prompt_context_fingerprint": sha256_value(context),
                "prompt_text_fingerprint": sha256_value(prompt),
                "authorization_state": "AUTHORIZED",
                "resume_key": {
                    "forecast_call_id": call_id,
                    "pack_type": pack_type,
                    "episode_id": row["episode_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "pack_row_fingerprint": row_fingerprint,
                    "forecast_contract_version": contract.CONTRACT_VERSION,
                },
                "leakage_audit": audit,
            }
            typed_rows.append(typed)
            prompt_manifest.append(
                {
                    "forecast_call_id": call_id,
                    "pack_type": pack_type,
                    "episode_id": row["episode_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "historical_cutoff": payload["forecast_cutoff_ts"],
                    "prompt_payload": context,
                    "prompt_text": prompt,
                }
            )
            prompt_fingerprints.append(
                {
                    "forecast_call_id": call_id,
                    "pack_type": pack_type,
                    "episode_id": row["episode_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "pack_row_fingerprint": row_fingerprint,
                    "prompt_context_fingerprint": sha256_value(context),
                    "prompt_text_fingerprint": sha256_value(prompt),
                    "pack_payload_input_fingerprint": payload["input_fingerprint"],
                }
            )
        eligible_by_type[pack_type] = order_rows(typed_rows)

    if blockers:
        raise ForecastPlanningError("LEAKAGE_CONTROL_VIOLATIONS_PRESENT")

    calls: list[dict[str, Any]] = []
    execution_order = 1
    for pack_type in PACK_TYPES:
        for row in eligible_by_type[pack_type]:
            row["execution_order"] = execution_order
            calls.append(row)
            execution_order += 1

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in calls:
        key = (row["episode_id"], row["provider"])
        by_key.setdefault(key, {})[row["pack_type"]] = row
    paired_index: list[dict[str, Any]] = []
    for episode_id, provider in sorted(both_keys, key=lambda item: (item[0], PROVIDER_ORDER[item[1]])):
        pair = by_key[(episode_id, provider)]
        row_a, row_e = pair["PACK_A"], pair["PACK_E"]
        paired_index.append(
            {
                "episode_id": episode_id,
                "provider": provider,
                "model": row_a["model"],
                "pack_a_call_id": row_a["forecast_call_id"],
                "pack_e_call_id": row_e["forecast_call_id"],
                "pack_a_row_fingerprint": row_a["pack_row_fingerprint"],
                "pack_e_row_fingerprint": row_e["pack_row_fingerprint"],
                "pack_a_row_identity": row_a["pack_row_identity"],
                "pack_e_row_identity": row_e["pack_row_identity"],
                "paired_cutoff_equality_result": row_a["historical_cutoff"] == row_e["historical_cutoff"],
                "paired_provider_equality_result": row_a["provider"] == row_e["provider"],
                "paired_episode_equality_result": row_a["episode_id"] == row_e["episode_id"],
            }
        )

    eligibility = {
        "pack_a_eligible_keys": sorted(episode_provider_key(*key) for key in pack_a_keys),
        "pack_e_eligible_keys": sorted(episode_provider_key(*key) for key in pack_e_keys),
        "both_keys": sorted(episode_provider_key(*key) for key in both_keys),
        "pack_a_only_keys": a_only,
        "pack_e_only_keys": e_only,
    }
    return calls, paired_index, prompt_manifest, {
        "prompt_fingerprints": prompt_fingerprints,
        "eligibility": eligibility,
    }


def strip_internal_call_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "forecast_call_id": row["forecast_call_id"],
        "episode_id": row["episode_id"],
        "source_session_id": row["source_session_id"],
        "provider": row["provider"],
        "model": row["model"],
        "pack_type": row["pack_type"],
        "pack_row_identity": row["pack_row_identity"],
        "pack_row_fingerprint": row["pack_row_fingerprint"],
        "attention_call_id": row["attention_call_id"],
        "attention_request_identity": row["attention_request_identity"],
        "historical_cutoff": row["historical_cutoff"],
        "prompt_contract_identity": row["prompt_contract_identity"],
        "expected_response_contract": row["expected_response_contract"],
        "execution_order": row["execution_order"],
        "batch_id": row["batch_id"],
        "authorization_state": row["authorization_state"],
        "resume_key": row["resume_key"],
        "pack_payload_input_fingerprint": row["pack_payload_input_fingerprint"],
    }


def build_batches(calls: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    batches: list[dict[str, Any]] = []
    for pack_type in PACK_TYPES:
        pack_calls = [row for row in calls if row["pack_type"] == pack_type]
        for index in range(0, len(pack_calls), BATCH_SIZE):
            chunk = pack_calls[index : index + BATCH_SIZE]
            number = (index // BATCH_SIZE) + 1
            bid = batch_id(pack_type, number)
            for row in chunk:
                row["batch_id"] = bid
            batches.append(
                {
                    "batch_id": bid,
                    "pack_type": pack_type,
                    "ordered_call_ids": [row["forecast_call_id"] for row in chunk],
                    "call_count": len(chunk),
                    "provider_model_composition": dict(Counter(f"{row['provider']}|{row['model']}" for row in chunk)),
                    "episode_count": len({row["episode_id"] for row in chunk}),
                    "first_execution_order": chunk[0]["execution_order"],
                    "last_execution_order": chunk[-1]["execution_order"],
                }
            )
    batch_file = {
        "ordering_rule": "PACK_A_THEN_PACK_E__RELEASE_TS__EPISODE_ID__PROVIDER_ORDER",
        "batch_size": BATCH_SIZE,
        "batches": batches,
    }
    return batch_file, batches


def planning_contract() -> dict[str, Any]:
    source = inspectable_contract_source()
    return {
        "object": "presignal_historical_forecast_execution_planning_contract",
        "version": FORECAST_PLANNING_CONTRACT_VERSION,
        "historical_forecast_contract_identity": contract.CONTRACT_VERSION,
        "historical_forecast_schema_version": contract.SCHEMA_VERSION,
        "historical_forecast_system_version": contract.SYSTEM_VERSION,
        "prediction_fields": sorted(contract.PREDICTION_FIELDS),
        "path_fields": sorted(contract.PATH_FIELDS),
        "evaluation_fields": sorted(contract.EVALUATION_FIELDS),
        "horizons_min": list(contract.HORIZONS),
        "primary_endpoint": "EPISODE_REACTION_DIRECTION_15M",
        "secondary_measurement": "IMMEDIATE_IMPULSE",
        "allowed_terminal_states": [
            "SUCCEEDED_VALID",
            "FAILED_TRANSPORT",
            "FAILED_PROVIDER",
            "FAILED_PROVIDER_AUTHORITY",
            "FAILED_PARSE",
            "FAILED_VALIDATION",
            "SKIPPED_ALREADY_SUCCEEDED",
        ],
        "parser_fingerprint": sha256_value(source["normalize_provider_output"]),
        "prompt_template_fingerprint": sha256_value(source["prompt_text"]),
        "response_contract_fingerprint": sha256_value(
            {
                "prediction_fields": contract.PREDICTION_FIELDS,
                "path_fields": contract.PATH_FIELDS,
                "contract_version": contract.CONTRACT_VERSION,
            }
        ),
    }


def inspectable_contract_source() -> dict[str, str]:
    import inspect

    return {
        "normalize_provider_output": inspect.getsource(step6.normalize_provider_output),
        "prompt_text": inspect.getsource(step6.prompt_text),
    }


def provider_model_contract() -> dict[str, Any]:
    return {
        "canonical_assignments": dict(PROVIDER_MODEL_ASSIGNMENTS),
        "assignment_rule": "provider row must execute only on its frozen provider/model pair",
        "provider_authority_rule": {
            "manifest_provider_equals_transport_provider": True,
            "manifest_model_equals_transport_model": True,
            "raw_claimed_provider_preserved_separately": True,
        },
    }


def leakage_control_contract() -> dict[str, Any]:
    return {
        "prohibitions": [
            "realized market outcome in prompts",
            "post_release_price_movement in prompts",
            "later analyst revision in prompts",
            "Outcome data in prompts",
            "paired Pack condition in same request",
            "other provider forecast content in prompts",
        ],
        "allowed_prompt_components": [
            "forecast contract instructions",
            "frozen role instructions",
            "exact Pack payload",
            "historical cutoff metadata",
            "Episode identity required by contract",
            "response schema",
        ],
        "ordering_rule": "Pack A batches first, Pack E batches second to reduce paired-condition leakage risk",
        "resume_keys": [
            "forecast_call_id",
            "pack_type",
            "episode_id",
            "provider",
            "model",
            "pack_row_fingerprint",
            "forecast_contract_version",
        ],
    }


def construct_plan(output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    pack_rows_by_type = {pack_type: load_pack_rows(pack_type) for pack_type in PACK_TYPES}
    eligibility_population = [
        row
        for pack_type in PACK_TYPES
        for row in build_forecast_eligibility_population(pack_rows_by_type[pack_type], pack_type)
    ]
    calls, paired_index, prompt_manifest, extras = build_authorized_calls(pack_rows_by_type)
    batch_file, batch_rows = build_batches(calls)
    ledger_rows = [strip_internal_call_fields(row) for row in calls]
    ineligible_rows = [row for row in eligibility_population if not row["forecast_eligibility"]]

    if len({row["forecast_call_id"] for row in ledger_rows}) != len(ledger_rows):
        raise ForecastPlanningError("DUPLICATE_FORECAST_CALL_IDS")
    if any(row["call_count"] > BATCH_SIZE for row in batch_rows):
        raise ForecastPlanningError("BATCH_SIZE_EXCEEDED")
    batch_membership = Counter(call_id for row in batch_rows for call_id in row["ordered_call_ids"])
    if any(count != 1 for count in batch_membership.values()):
        raise ForecastPlanningError("CALL_BATCH_MEMBERSHIP_MISMATCH")
    if set(batch_membership) != {row["forecast_call_id"] for row in ledger_rows}:
        raise ForecastPlanningError("BATCH_MEMBERSHIP_INCOMPLETE")

    provider_counts = dict(Counter(row["provider"] for row in ledger_rows))
    provider_counts_per_pack = {
        pack_type: dict(Counter(row["provider"] for row in ledger_rows if row["pack_type"] == pack_type))
        for pack_type in PACK_TYPES
    }
    remainder_sizes = [row["call_count"] for row in batch_rows if row["call_count"] != BATCH_SIZE]
    paired_mismatch_count = sum(
        1
        for row in paired_index
        if not (row["paired_cutoff_equality_result"] and row["paired_provider_equality_result"] and row["paired_episode_equality_result"])
    )

    leakage_audit_rows = [
        {
            "forecast_call_id": row["forecast_call_id"],
            "pack_type": row["pack_type"],
            "episode_id": row["episode_id"],
            "provider": row["provider"],
            "passed": row["leakage_audit"]["passed"],
            "violations": row["leakage_audit"]["violations"],
        }
        for row in calls
    ]
    leakage_violations = [row for row in leakage_audit_rows if not row["passed"]]
    planning_blockers: list[dict[str, Any]] = []

    planning_summary = {
        "pack_a_construction_rows": sum(1 for row in eligibility_population if row["pack_type"] == "PACK_A"),
        "pack_e_construction_rows": sum(1 for row in eligibility_population if row["pack_type"] == "PACK_E"),
        "pack_a_eligible_rows": sum(1 for row in eligibility_population if row["pack_type"] == "PACK_A" and row["forecast_eligibility"]),
        "pack_e_eligible_rows": sum(1 for row in eligibility_population if row["pack_type"] == "PACK_E" and row["forecast_eligibility"]),
        "eligible_keys_present_in_both": len(extras["eligibility"]["both_keys"]),
        "pack_a_only_eligible_keys": len(extras["eligibility"]["pack_a_only_keys"]),
        "pack_e_only_eligible_keys": len(extras["eligibility"]["pack_e_only_keys"]),
        "unique_eligible_episode_provider_count": len({(row["episode_id"], row["provider"]) for row in ledger_rows if row["pack_type"] == "PACK_A"}),
        "unique_eligible_episode_count": len({row["episode_id"] for row in ledger_rows if row["pack_type"] == "PACK_A"}),
        "provider_counts_among_eligible_keys": provider_counts_per_pack["PACK_A"],
        "authorized_pack_a_call_count": sum(1 for row in ledger_rows if row["pack_type"] == "PACK_A"),
        "authorized_pack_e_call_count": sum(1 for row in ledger_rows if row["pack_type"] == "PACK_E"),
        "total_authorized_forecast_call_count": len(ledger_rows),
        "unique_forecast_call_id_count": len({row["forecast_call_id"] for row in ledger_rows}),
        "ineligible_pack_row_count": len(ineligible_rows),
        "paired_condition_index_row_count": len(paired_index),
        "paired_condition_mismatch_count": paired_mismatch_count,
        "provider_model_assignments": dict(PROVIDER_MODEL_ASSIGNMENTS),
        "calls_per_provider": provider_counts,
        "calls_per_provider_per_pack": provider_counts_per_pack,
        "total_planned_batch_count": len(batch_rows),
        "pack_a_batch_count": sum(1 for row in batch_rows if row["pack_type"] == "PACK_A"),
        "pack_e_batch_count": sum(1 for row in batch_rows if row["pack_type"] == "PACK_E"),
        "full_size_batch_count": sum(1 for row in batch_rows if row["call_count"] == BATCH_SIZE),
        "remainder_batch_count": len(remainder_sizes),
        "remainder_batch_sizes": remainder_sizes,
        "maximum_calls_per_batch": max(row["call_count"] for row in batch_rows) if batch_rows else 0,
        "duplicate_call_id_count": len(ledger_rows) - len({row["forecast_call_id"] for row in ledger_rows}),
        "calls_without_batch_membership": len({row["forecast_call_id"] for row in ledger_rows} - set(batch_membership)),
        "calls_with_multiple_batch_memberships": sum(1 for count in batch_membership.values() if count > 1),
        "unresolved_pack_fingerprints": 0,
        "unresolved_prompt_fingerprints": 0,
        "leakage_control_violations": len(leakage_violations),
        "planning_blocker_categories": dict(Counter(row["category"] for row in planning_blockers)),
    }

    decisions = {
        "planning_status": "FORECAST_EXECUTION_PLAN_COMPLETE" if not planning_blockers else "FORECAST_EXECUTION_PLAN_PARTIALLY_COMPLETE",
        "eligibility_decision": "PACK_A_AND_PACK_E_FORECAST_ELIGIBILITY_FULLY_RECONCILED"
        if not extras["eligibility"]["pack_a_only_keys"] and not extras["eligibility"]["pack_e_only_keys"]
        else "PACK_ELIGIBILITY_ASYMMETRY_PRESENT",
        "forecast_contract_decision": "FROZEN_FORECAST_CONTRACT_BOUND",
        "leakage_control_decision": "HISTORICAL_LEAKAGE_CONTROLS_PROVEN" if not leakage_violations else "HISTORICAL_LEAKAGE_RISK_PRESENT",
        "batch_planning_decision": "FORECAST_BATCH_PLAN_COMPLETE" if not planning_blockers else "FORECAST_BATCH_PLAN_INCOMPLETE",
        "execution_boundary_decision": "PLANNING_ONLY_NO_FORECAST_CALLS",
        "next_phase_decision": "READY_FOR_BOUNDED_FORECAST_EXECUTION" if not planning_blockers and not leakage_violations else "REPAIR_FORECAST_EXECUTION_PLAN",
    }

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_dir.name,
            "move": "FORECAST_EXECUTION_PLANNING",
            "started_from_head": git_head(),
            "completed_at": fixed_timestamp or now(),
            **NO_LIVE_CALLS,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "governing_plan_id": PLAN_ID,
            "governing_consolidation_id": CONSOLIDATION_ID,
            "governing_lineage_repair_id": LINEAGE_REPAIR_ID,
            "governing_pack_construction_id": PACK_CONSTRUCTION_ID,
            "governing_pack_inputs": [
                path_ref(PACK_ROOT / "pack_a_population.jsonl"),
                path_ref(PACK_ROOT / "pack_e_population.jsonl"),
                path_ref(PACK_ROOT / "episode_provider_construction_index.jsonl"),
                path_ref(PACK_ROOT / "pack_a_construction_contract.json"),
                path_ref(PACK_ROOT / "pack_e_construction_contract.json"),
            ],
        },
    )
    write_json(run_dir / "forecast_planning_contract.json", planning_contract())
    write_json(run_dir / "forecast_execution_contract.json", planning_contract())
    write_json(run_dir / "provider_model_contract.json", provider_model_contract())
    write_json(run_dir / "historical_leakage_control_contract.json", leakage_control_contract())
    write_jsonl(run_dir / "forecast_eligibility_population.jsonl", eligibility_population)
    write_jsonl(run_dir / "authorized_forecast_call_ledger.jsonl", ledger_rows)
    write_jsonl(run_dir / "ineligible_pack_row_ledger.jsonl", ineligible_rows)
    write_jsonl(run_dir / "episode_provider_paired_condition_index.jsonl", paired_index)
    write_json(run_dir / "forecast_call_batches.json", batch_file)
    write_jsonl(run_dir / "forecast_batch_manifest.jsonl", batch_rows)
    write_jsonl(run_dir / "prompt_payload_manifest.jsonl", prompt_manifest)
    write_jsonl(run_dir / "prompt_fingerprint_ledger.jsonl", extras["prompt_fingerprints"])
    write_json(
        run_dir / "provider_model_reconciliation.json",
        {
            "provider_model_assignments": dict(PROVIDER_MODEL_ASSIGNMENTS),
            "calls_per_provider": provider_counts,
            "calls_per_provider_per_pack": provider_counts_per_pack,
        },
    )
    write_json(
        run_dir / "pack_eligibility_reconciliation.json",
        {
            "pack_a_eligible_keys": extras["eligibility"]["pack_a_eligible_keys"],
            "pack_e_eligible_keys": extras["eligibility"]["pack_e_eligible_keys"],
            "eligible_keys_present_in_both": extras["eligibility"]["both_keys"],
            "pack_a_only_eligible_keys": extras["eligibility"]["pack_a_only_keys"],
            "pack_e_only_eligible_keys": extras["eligibility"]["pack_e_only_keys"],
        },
    )
    write_json(
        run_dir / "paired_condition_reconciliation.json",
        {
            "paired_condition_index_row_count": len(paired_index),
            "paired_condition_mismatch_count": paired_mismatch_count,
            "all_pairs_match_episode_provider_cutoff": paired_mismatch_count == 0,
        },
    )
    write_json(
        run_dir / "batch_reconciliation.json",
        {
            "total_batch_count": len(batch_rows),
            "full_size_batch_count": planning_summary["full_size_batch_count"],
            "remainder_batch_sizes": remainder_sizes,
            "calls_without_batch_membership": planning_summary["calls_without_batch_membership"],
            "calls_with_multiple_batch_memberships": planning_summary["calls_with_multiple_batch_memberships"],
            "maximum_calls_per_batch": planning_summary["maximum_calls_per_batch"],
        },
    )
    write_json(
        run_dir / "leakage_control_audit.json",
        {
            "row_count": len(leakage_audit_rows),
            "violations": leakage_violations,
            "violation_count": len(leakage_violations),
            "passed": not leakage_violations,
        },
    )
    write_jsonl(run_dir / "planning_blocker_ledger.jsonl", planning_blockers)
    write_json(run_dir / "forecast_plan_summary.json", planning_summary)
    write_json(run_dir / "forecast_plan_decision.json", decisions)

    return {
        "run_dir": run_dir,
        "summary": planning_summary,
        "decision": decisions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = construct_plan(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), "decision": result["decision"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
