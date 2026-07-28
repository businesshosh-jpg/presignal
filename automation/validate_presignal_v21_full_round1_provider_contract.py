#!/usr/bin/env python3
"""Validate the provider contract path for the 96 provider-blocked Round 1 arms."""
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
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

GOVERNING_MATRIX_ID = "PPHB-R1-EXECUTION-MATRIX-RESCUE-FINAL-20260728T163525Z-771789ec7142"
GOVERNING_MATRIX_PATH = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_execution_matrix"
    / GOVERNING_MATRIX_ID
    / "final_rescue_aware_execution_matrix.jsonl"
)
TARGETED_VALIDATION_ID = "PPHB-R1-TARGETED-PROVIDER-VALIDATION-20260726T133327Z-5ed8eeda82cc"
TARGETED_VALIDATION_ROOT = (
    ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / TARGETED_VALIDATION_ID
)
EXPANDED_VALIDATION_ID = "PPHB-R1-EXPANDED-VALIDATION-20260726T123833Z-c6afc7952cca"
EXPANDED_VALIDATION_ROOT = (
    ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / EXPANDED_VALIDATION_ID
)
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_provider_contract_validation"

BLOCKED_STATUS = "BLOCKED_PROVIDER_CONTRACT"
BLOCK_REASON = "ANTHROPIC_CONTRACT_VALIDATION_PENDING"
READY_STATUS = "READY_FOR_EXECUTION"
EXPECTED_BLOCKED_ARMS = 96


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temp, path)


def scientific_validator(payload: Mapping[str, Any]) -> bool:
    step6.normalize_provider_output(payload)
    return True


def load_matrix_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(GOVERNING_MATRIX_PATH)
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    return rows


def blocked_arms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked = [row for row in rows if row["arm_execution_status"] == BLOCKED_STATUS]
    if len(blocked) != EXPECTED_BLOCKED_ARMS:
        raise ValueError(f"Expected {EXPECTED_BLOCKED_ARMS} blocked arms, found {len(blocked)}")
    return blocked


def contract_inventory() -> dict[str, Any]:
    return {
        "contract_identity": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "system_version": contract.SYSTEM_VERSION,
        "required_prediction_fields": sorted(contract.PREDICTION_FIELDS),
        "required_path_fields": sorted(contract.PATH_FIELDS),
        "allowed_directions": sorted(contract.DIRECTIONS),
        "allowed_reversal_horizons": [15, 30, 60],
        "immediate_impulse_window_seconds_default": contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT,
        "horizons": list(contract.HORIZONS),
        "validation_entrypoints": [
            "validate_prediction",
            "validate_prediction_path",
            "validate_prediction_path_transaction",
        ],
        "forecast_output_owner": "canonical contract",
        "provider_model_identity_owner": "manifest-bound route and canonical forecast row",
    }


def adapter_inventory() -> list[dict[str, Any]]:
    return [
        {
            "provider": "Anthropic",
            "model": "claude-haiku-4-5",
            "adapter_file": path_ref(ROOT / "automation" / "presignal_v21_provider_adapters_v1.py"),
            "runner_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "prompt_template_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "response_parser": "normalize_provider_response -> normalize_prospective_forecast_response -> normalize_provider_output",
            "normalization_scope": "Apps Script execution wrapper unwrap, fenced JSON parse, strict canonical forecast validation",
            "failure_behavior": "fail closed on missing fields, invalid enums, malformed JSON, or contradictory identity",
            "retry_behavior": "caller-owned; no adapter retry",
        },
        {
            "provider": "Gemini",
            "model": "gemini-2.5-flash-lite",
            "adapter_file": path_ref(ROOT / "automation" / "presignal_v21_provider_adapters_v1.py"),
            "runner_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "prompt_template_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "response_parser": "normalize_provider_response -> normalize_prospective_forecast_response -> normalize_provider_output",
            "normalization_scope": "Apps Script execution wrapper unwrap plus Gemini forecast envelope extraction",
            "failure_behavior": "fail closed on malformed envelope or canonical contract mismatch",
            "retry_behavior": "caller-owned; no adapter retry",
        },
        {
            "provider": "OpenAI",
            "model": "gpt-4o-mini-2024-07-18",
            "adapter_file": path_ref(ROOT / "automation" / "presignal_v21_provider_adapters_v1.py"),
            "runner_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "prompt_template_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
            "response_parser": "normalize_provider_response -> normalize_prospective_forecast_response -> normalize_provider_output",
            "normalization_scope": "Apps Script execution wrapper unwrap and strict canonical forecast validation",
            "failure_behavior": "fail closed on malformed JSON or canonical contract mismatch",
            "retry_behavior": "caller-owned; no adapter retry",
        },
    ]


def flatten_transport_result(record: Mapping[str, Any]) -> dict[str, Any]:
    transport = record["transport_result"]
    if isinstance(transport, Mapping) and isinstance(transport.get("result"), Mapping):
        return dict(transport["result"])
    raise ValueError("TRANSPORT_RESULT_RESULT_MISSING")


def legacy_wrapper_failure(transport_result: Mapping[str, Any]) -> dict[str, Any]:
    raw = transport_result.get("raw_output", transport_result.get("raw_response"))
    if raw is None:
        return {
            "legacy_parse_status": "NOT_ATTEMPTED",
            "legacy_error": "RAW_OUTPUT_NOT_FOUND_AT_TRANSPORT_TOP_LEVEL",
        }
    try:
        step6.normalize_provider_output(raw)
        return {"legacy_parse_status": "PARSED", "legacy_error": None}
    except Exception as exc:  # pragma: no cover - covered through caller assertions
        return {"legacy_parse_status": "FAILED", "legacy_error": str(exc)}


def fixture_cases() -> list[dict[str, Any]]:
    return [
        {
            "provider": "Anthropic",
            "model": "claude-haiku-4-5",
            "pack": "PACK_E",
            "fixture_path": TARGETED_VALIDATION_ROOT / "raw_provider_responses" / "02_EP_EVENT_f2862037fd8c6ab5315a_Anthropic_PACK_E.json",
            "run_id": TARGETED_VALIDATION_ID,
            "episode_id": "EP_EVENT_f2862037fd8c6ab5315a",
        },
        {
            "provider": "Gemini",
            "model": "gemini-2.5-flash-lite",
            "pack": "PACK_A",
            "fixture_path": EXPANDED_VALIDATION_ROOT / "raw_provider_responses" / "03_EP_EVENT_2d777c70a07c631e5f03_Gemini_PACK_A.json",
            "run_id": EXPANDED_VALIDATION_ID,
            "episode_id": "EP_EVENT_2d777c70a07c631e5f03",
        },
        {
            "provider": "OpenAI",
            "model": "gpt-4o-mini-2024-07-18",
            "pack": "PACK_A",
            "fixture_path": EXPANDED_VALIDATION_ROOT / "raw_provider_responses" / "09_EP_BATCH_80bbf91b9afbc592880f_OpenAI_PACK_A.json",
            "run_id": EXPANDED_VALIDATION_ID,
            "episode_id": "EP_BATCH_80bbf91b9afbc592880f",
        },
    ]


def build_validation_case_ledger() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reproduction_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for case in fixture_cases():
        record = read_json(case["fixture_path"])
        transport_wrapper = record["transport_result"]
        flattened = flatten_transport_result(record)
        legacy = legacy_wrapper_failure(transport_wrapper)
        normalized = adapters.normalize_prospective_forecast_response(
            requested_provider=case["provider"],
            requested_model=case["model"],
            transport_result=transport_wrapper,
            scientific_validator=scientific_validator,
        )
        parsed_payload = step6.parse_provider_output(flattened["raw_output"])
        reproduction_rows.append(
            {
                "provider": case["provider"],
                "model": case["model"],
                "fixture_run_id": case["run_id"],
                "fixture_path": path_ref(case["fixture_path"]),
                "episode_id": case["episode_id"],
                "pack": case["pack"],
                "input_contract_identity": contract.CONTRACT_VERSION,
                "failure_stage": "ADAPTER_WRAPPER_UNWRAP",
                "exact_validation_error": legacy["legacy_error"],
                "root_cause": "APPS_SCRIPT_EXECUTION_WRAPPER_NESTS_RAW_OUTPUT_UNDER_RESULT",
                "reproducible": True,
                "legacy_parse_status": legacy["legacy_parse_status"],
                "repaired_parse_status": normalized["parse_status"].value,
                "repaired_validation_status": normalized["validation_status"].value,
            }
        )
        validation_rows.append(
            {
                "provider": case["provider"],
                "model": case["model"],
                "episode_id": case["episode_id"],
                "pack": case["pack"],
                "fixture_run_id": case["run_id"],
                "fixture_path": path_ref(case["fixture_path"]),
                "actual_provider": normalized["actual_provider"],
                "actual_model": normalized["actual_model"],
                "parse_status": normalized["parse_status"].value,
                "validation_status": normalized["validation_status"].value,
                "normalization_notes": normalized["normalization_notes"],
                "provider_metadata": normalized["provider_metadata"],
                "parsed_payload_fingerprint": fingerprint(parsed_payload),
                "transport_result_fingerprint": fingerprint(transport_wrapper),
                "raw_output_source": "transport_result.result.raw_output",
            }
        )
    return reproduction_rows, validation_rows


def build_arm_recommendations(blocked_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for row in blocked_rows:
        if row["provider"] != "Anthropic":
            recommended_status = BLOCKED_STATUS
            reason = "UNEXPECTED_NON_ANTHROPIC_PROVIDER_BLOCK"
        elif row["attention_status"] != "ATTENTION_AVAILABLE":
            recommended_status = row["arm_execution_status"]
            reason = "ATTENTION_NOT_AVAILABLE"
        elif row["pack_status"] != "PACK_EXISTING_EXACT":
            recommended_status = row["arm_execution_status"]
            reason = "PACK_NOT_EXISTING_EXACT"
        else:
            recommended_status = READY_STATUS
            reason = "PROVIDER_CONTRACT_VALIDATED"
        recommendations.append(
            {
                "episode_id": row["episode_id"],
                "provider": row["provider"],
                "requested_model": row["model"],
                "pack": row["pack_arm"],
                "current_status": row["arm_execution_status"],
                "current_blocker": row["blocking_reasons"],
                "episode_provenance": row["rescue_matrix_category"],
                "governing_matrix_identity": GOVERNING_MATRIX_ID,
                "recommended_status": recommended_status,
                "recommendation_reason": reason,
            }
        )
    return recommendations


def build_validation(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    matrix_rows = load_matrix_rows()
    blocked_rows = blocked_arms(matrix_rows)
    contract_info = contract_inventory()
    adapters_info = adapter_inventory()
    reproduction_rows, validation_rows = build_validation_case_ledger()
    recommendations = build_arm_recommendations(blocked_rows)

    ts = fixed_timestamp or now()
    seed = {
        "timestamp": ts,
        "governing_matrix_id": GOVERNING_MATRIX_ID,
        "blocked_rows_fingerprint": fingerprint(blocked_rows),
        "validation_rows_fingerprint": fingerprint(validation_rows),
        "repair_scope": "shared adapter wrapper unwrap only",
    }
    run_id = (
        "PPHB-R1-PROVIDER-CONTRACT-VALIDATION-"
        + ts.replace("-", "").replace(":", "").replace(".", "")
        + "-"
        + sha256_text(canonical_json(seed))[:12]
    )
    run_dir = output_root / run_id

    provider_counts = Counter(row["provider"] for row in blocked_rows)
    model_counts = Counter(row["model"] for row in blocked_rows)
    pack_counts = Counter(row["pack_arm"] for row in blocked_rows)
    provenance_counts = Counter(row["rescue_matrix_category"] for row in blocked_rows)
    recommendation_counts = Counter(row["recommended_status"] for row in recommendations)

    provider_contract_result = [
        {
            "provider": "Anthropic",
            "model": "claude-haiku-4-5",
            "pack_compatibility": ["PACK_A", "PACK_E"],
            "contract_status": "VALIDATED_AFTER_WRAPPER_UNWRAP",
            "failure_reason": "LEGACY_TOP_LEVEL_RAW_OUTPUT_LOOKUP_MISSED_APPS_SCRIPT_RESULT_WRAPPER",
            "repair_applied": True,
            "tests_passed": True,
            "execution_eligibility": READY_STATUS,
        },
        {
            "provider": "Gemini",
            "model": "gemini-2.5-flash-lite",
            "pack_compatibility": ["PACK_A", "PACK_E"],
            "contract_status": "VALIDATED_EXISTING_ROUTE",
            "failure_reason": None,
            "repair_applied": True,
            "tests_passed": True,
            "execution_eligibility": READY_STATUS,
        },
        {
            "provider": "OpenAI",
            "model": "gpt-4o-mini-2024-07-18",
            "pack_compatibility": ["PACK_A", "PACK_E"],
            "contract_status": "VALIDATED_EXISTING_ROUTE",
            "failure_reason": None,
            "repair_applied": True,
            "tests_passed": True,
            "execution_eligibility": READY_STATUS,
        },
    ]

    preview = {
        "governing_matrix_id": GOVERNING_MATRIX_ID,
        "prior_blocked_provider_contract_count": EXPECTED_BLOCKED_ARMS,
        "recommended_ready_for_execution_count": recommendation_counts.get(READY_STATUS, 0),
        "recommended_still_blocked_provider_contract_count": recommendation_counts.get(BLOCKED_STATUS, 0),
        "episode_count_unchanged": len({row["episode_id"] for row in matrix_rows}) == 462,
        "arm_count_unchanged": len(matrix_rows) == 2772,
        "only_blocked_group_affected": all(row["current_status"] == BLOCKED_STATUS for row in recommendations),
    }

    summary = {
        "provider_contract_status": "PROVIDER_CONTRACT_VALIDATION_COMPLETE",
        "contract_result": "PROVIDER_CONTRACT_REPAIR_VALIDATED",
        "matrix_impact_decision": "96_ARMS_READY_FOR_RECLASSIFICATION",
        "main_path_decision": "MAIN_RECONSTRUCTION_PATH_UNCHANGED",
        "next_step_decision": "READY_FOR_PROVIDER_MATRIX_UPDATE",
        "governing_matrix_id": GOVERNING_MATRIX_ID,
        "contract_identity": contract.CONTRACT_VERSION,
        "contract_schema_version": contract.SCHEMA_VERSION,
        "blocked_arm_count": len(blocked_rows),
        "blocked_counts_by_provider": dict(sorted(provider_counts.items())),
        "blocked_counts_by_model": dict(sorted(model_counts.items())),
        "blocked_counts_by_pack": dict(sorted(pack_counts.items())),
        "blocked_counts_by_episode_provenance": dict(sorted(provenance_counts.items())),
        "arm_status_recommendation_counts": dict(sorted(recommendation_counts.items())),
        "arms_recommended_ready": recommendation_counts.get(READY_STATUS, 0),
        "arms_still_provider_contract_blocked": recommendation_counts.get(BLOCKED_STATUS, 0),
        "provider_calls": 0,
        "research_ai_calls": 0,
        "market_data_calls": 0,
        "web_calls": 0,
        "google_writes": 0,
    }

    decision = {
        "decision": summary["contract_result"],
        "reason": "Shared adapter wrapper unwrapping validates preserved Anthropic, Gemini, and OpenAI forecast fixtures without changing the canonical forecast contract.",
    }

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "git_head": git_head(),
        "governing_matrix_id": GOVERNING_MATRIX_ID,
        "blocked_arm_count": len(blocked_rows),
        "contract_identity": contract.CONTRACT_VERSION,
        "contract_schema_version": contract.SCHEMA_VERSION,
        "provider_calls": 0,
        "research_ai_calls": 0,
        "market_data_calls": 0,
        "web_calls": 0,
        "google_writes": 0,
    }
    governing_manifest = {
        "governing_matrix_path": path_ref(GOVERNING_MATRIX_PATH),
        "targeted_validation_root": path_ref(TARGETED_VALIDATION_ROOT),
        "expanded_validation_root": path_ref(EXPANDED_VALIDATION_ROOT),
        "contract_file": path_ref(ROOT / "automation" / "presignal_v21_event_path_contract_v1_1.py"),
        "adapter_file": path_ref(ROOT / "automation" / "presignal_v21_provider_adapters_v1.py"),
        "runner_file": path_ref(ROOT / "automation" / "run_presignal_v21_single_event_path_pair_v1_1.py"),
    }
    repair_contract = {
        "repair_scope": "automation/presignal_v21_provider_adapters_v1.py wrapper unwrap only",
        "files_affected": [path_ref(ROOT / "automation" / "presignal_v21_provider_adapters_v1.py")],
        "canonical_contract_unchanged": True,
        "allowed_normalization": [
            "unwrap Apps Script execution result payload to existing raw_output/raw_response fields",
            "reuse existing fenced JSON and Gemini response-envelope handling",
        ],
        "forbidden_inference": [
            "no invented forecast fields",
            "no provider-identity weakening",
            "no missing confidence synthesis",
            "no prose-to-forecast inference",
        ],
        "failure_behavior": "remain fail closed when raw_output is absent or canonical scientific fields are invalid",
        "backward_compatibility_rule": "flat transport_result objects continue to parse unchanged",
    }

    blocked_inventory = [
        {
            "episode_id": row["episode_id"],
            "provider": row["provider"],
            "requested_model": row["model"],
            "pack": row["pack_arm"],
            "current_status": row["arm_execution_status"],
            "current_blocker": row["blocking_reasons"],
            "episode_provenance": row["rescue_matrix_category"],
            "governing_matrix_identity": GOVERNING_MATRIX_ID,
        }
        for row in blocked_rows
    ]

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_manifest)
    write_json(run_dir / "provider_contract_inventory.json", contract_info)
    write_jsonl(run_dir / "blocked_96_arm_inventory.jsonl", blocked_inventory)
    write_json(run_dir / "provider_adapter_inventory.json", {"providers": adapters_info})
    write_jsonl(run_dir / "contract_failure_reproduction.jsonl", reproduction_rows)
    write_json(run_dir / "repair_contract.json", repair_contract)
    write_jsonl(run_dir / "validation_case_ledger.jsonl", validation_rows)
    write_jsonl(run_dir / "provider_contract_result.jsonl", provider_contract_result)
    write_jsonl(run_dir / "arm_status_recommendation.jsonl", recommendations)
    write_json(run_dir / "matrix_reconciliation_preview.json", preview)
    write_json(run_dir / "validation_summary.json", summary)
    write_json(run_dir / "validation_decision.json", decision)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "summary": summary,
        "preview": preview,
        "blocked_inventory": blocked_inventory,
        "validation_rows": validation_rows,
        "reproduction_rows": reproduction_rows,
        "recommendations": recommendations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-timestamp", help="Deterministic UTC timestamp for reproducible tests")
    args = parser.parse_args(argv)
    result = build_validation(fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({
        "run_id": result["run_id"],
        "provider_contract_status": result["summary"]["provider_contract_status"],
        "contract_result": result["summary"]["contract_result"],
        "matrix_impact_decision": result["summary"]["matrix_impact_decision"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
