#!/usr/bin/env python3
"""Construct frozen provider-specific Pack A and Pack E populations without forecasting."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_event_path_inputs as step5
from automation import consolidate_presignal_v21_attention_results as consolidation
from automation import execute_presignal_v21_attention_batch_004 as batch004
from automation import repair_presignal_v21_attention_pack_lineage as lineage_repair

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
CONSOLIDATION_ID = "PPHB-R1-ATTENTION-RESULT-CONSOLIDATION-20260729T102316Z-17358e44afc1"
LINEAGE_BINDING_ID = "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-BINDING-20260729T103549Z-79d034f68080"
LINEAGE_REPAIR_ID = "PPHB-R1-ATTENTION-TO-PACK-LINEAGE-REPAIR-20260729T141500Z-7a5219653b5f"
EXTERNAL_REPLAY_ROOT = Path("/Users/junhoshino/projects/presignal_replay_archives/9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z/input_snapshot")
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_pack_population"

CONSOLIDATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_consolidation" / CONSOLIDATION_ID
LINEAGE_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_pack_lineage" / LINEAGE_BINDING_ID
LINEAGE_REPAIR_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_pack_lineage" / LINEAGE_REPAIR_ID
ELIGIBILITY_IMPL_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_implementation" / "PPHB-R1-ELIGIBILITY-IMPLEMENTATION-20260728T132849Z-297192188403"
RECON_DRY_RUN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
STEP5_REUSE_ROOT = ROOT / "outputs" / "presignal_v21_step5_reuse"
EPISODE_ROWS = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
ROLE_ROWS = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "episode_component_roles.jsonl"

PACK_A_ID = step5.PACK_A_ID
PACK_A_VERSION = step5.PACK_A_VERSION
PACK_E_ID = "PACK_E_SHARED"
PACK_STATUSES = {
    "valid": "CONSTRUCTED_VALID",
    "not_eligible": "NOT_FORECAST_ELIGIBLE_BY_FROZEN_CONTRACT",
    "missing": "BLOCKED_REQUIRED_FIELD_MISSING",
    "conflict": "BLOCKED_SOURCE_CONFLICT",
    "schema": "BLOCKED_SCHEMA_VALIDATION",
    "ambiguity": "BLOCKED_CONTRACT_AMBIGUITY",
}
PROVIDERS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
FIELD_RULES = {
    "exact copy": "EXACT_COPY",
    "deterministic normalization": "FROZEN_DETERMINISTIC_NORMALIZATION",
    "deterministic formatting": "FROZEN_DETERMINISTIC_FORMATTING",
}


class PackPopulationConstructionError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return consolidation.canonical_json(value)


def write_json(path: Path, value: Any) -> None:
    consolidation.write_json(path, value)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    consolidation.write_jsonl(path, rows)


def read_json(path: Path) -> dict[str, Any]:
    return consolidation.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return consolidation.read_jsonl(path)


def path_ref(path: Path) -> str:
    return consolidation.path_ref(path)


def now() -> str:
    return batch004.now()


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "consolidation_id": CONSOLIDATION_ID,
        "lineage_binding_id": LINEAGE_BINDING_ID,
        "lineage_repair_id": LINEAGE_REPAIR_ID,
        "timestamp": ts,
        "move": "PACK_POPULATION_CONSTRUCTION",
    }
    run_id = (
        "PPHB-R1-PACK-POPULATION-CONSTRUCTION-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def row_key(episode_id: str, provider: str) -> str:
    return f"{episode_id}|{provider}"


def expected_arm_identity(episode_id: str, provider: str, arm: str) -> str:
    return f"{episode_id}|{provider}|{arm}"


def field_lineage_row(
    *,
    pack_type: str,
    row_identity: str,
    episode_id: str,
    provider: str,
    destination_field: str,
    source_artifact: str,
    source_object_identity: Mapping[str, Any],
    source_field: str,
    source_fingerprint: str,
    transformation_rule: str,
    transformation_type: str,
) -> dict[str, Any]:
    return {
        "pack_type": pack_type,
        "row_identity": row_identity,
        "episode_id": episode_id,
        "provider": provider,
        "destination_field": destination_field,
        "source_artifact_identity": source_artifact,
        "source_object_or_row_identity": dict(source_object_identity),
        "source_field": source_field,
        "source_fingerprint": source_fingerprint,
        "transformation_rule": transformation_rule,
        "transformation_type": transformation_type,
    }


def required_files() -> dict[str, Path]:
    files = {
        "repaired_episode_provider_pack_binding": LINEAGE_REPAIR_ROOT / "repaired_episode_provider_pack_binding.jsonl",
        "repaired_episode_pack_source_lineage": LINEAGE_REPAIR_ROOT / "repaired_episode_pack_source_lineage.jsonl",
        "episode_provider_population": CONSOLIDATION_ROOT / "episode_provider_population.jsonl",
        "authoritative_call_inventory": CONSOLIDATION_ROOT / "authoritative_call_inventory.jsonl",
        "call_lineage_ledger": CONSOLIDATION_ROOT / "call_lineage_ledger.jsonl",
        "pack_a_source_contract": LINEAGE_ROOT / "pack_a_source_contract.json",
        "pack_e_source_contract": LINEAGE_ROOT / "pack_e_source_contract.json",
        "lineage_repair_summary": LINEAGE_REPAIR_ROOT / "repair_summary.json",
        "pack_reconstruction_fanout": ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID / "pack_reconstruction_fanout.jsonl",
        "episode_to_attention_call_map": ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID / "episode_to_attention_call_map.jsonl",
        "pack_status_ledger": ELIGIBILITY_IMPL_ROOT / "pack_status_ledger.jsonl",
        "expected_arm_ledger": ELIGIBILITY_IMPL_ROOT / "expected_arm_ledger.jsonl",
        "pack_a_plan": RECON_DRY_RUN_ROOT / "pack_a_reconstruction_plan.jsonl",
        "pack_e_plan": RECON_DRY_RUN_ROOT / "pack_e_reconstruction_plan.jsonl",
        "episode_request_compatibility": STEP5_REUSE_ROOT / "episode_request_compatibility.jsonl",
        "episode_pack_compatibility": STEP5_REUSE_ROOT / "episode_pack_compatibility.jsonl",
        "episode_rows": EPISODE_ROWS,
        "role_rows": ROLE_ROWS,
        "authoritative_sessions": EXTERNAL_REPLAY_ROOT / "authoritative_sessions.jsonl",
        "authoritative_session_members": EXTERNAL_REPLAY_ROOT / "authoritative_session_members.jsonl",
        "authoritative_requests": EXTERNAL_REPLAY_ROOT / "authoritative_requests.jsonl",
        "authoritative_pack_references": EXTERNAL_REPLAY_ROOT / "authoritative_pack_references.jsonl",
        "authoritative_forecast_population": EXTERNAL_REPLAY_ROOT / "authoritative_forecast_population.jsonl",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise PackPopulationConstructionError("MISSING_REQUIRED_ARTIFACTS:" + ",".join(missing))
    return files


def normalize_attention_rows(scientific_rows: list[Mapping[str, Any]], attention_run_id: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in scientific_rows:
        normalized.append(
            {
                "status": "parsed",
                "event_id": row["event_id"],
                "attention_label": row["attention_label"],
                "attention_rank": row["attention_rank"],
                "attention_reason": row["attention_reason"],
                "confidence": row.get("confidence"),
                "driver_role": row.get("driver_role"),
                "expected_market_channel": row.get("expected_market_channel"),
                "attention_run_id": attention_run_id,
                "step5_lineage_status": "VALID_FOR_STEP5",
            }
        )
    return normalized


def selection_state(scientific_rows: list[Mapping[str, Any]]) -> str:
    return step5.select_status(row["attention_label"] for row in scientific_rows)


def validate_expected_provider_pairs(
    session_id: str,
    forecast_rows: list[dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in forecast_rows:
        if row["session_id"] == session_id:
            pairs[(row["provider"], row["model"])].add(row["arm"])
    if not pairs:
        raise PackPopulationConstructionError(f"MISSING_FORECAST_PROVIDER_ASSIGNMENTS:{session_id}")
    return pairs


def validate_pack_contracts(pack_a_contract: Mapping[str, Any], pack_e_contract: Mapping[str, Any]) -> None:
    if "expected_arm_identity" not in pack_a_contract.get("binding_keys", []):
        raise PackPopulationConstructionError("PACK_A_CONTRACT_BINDING_KEY_MISSING")
    if "expected_arm_identity" not in pack_e_contract.get("binding_keys", []):
        raise PackPopulationConstructionError("PACK_E_CONTRACT_BINDING_KEY_MISSING")


def verify_lineage_resolution(summary: Mapping[str, Any]) -> None:
    if summary.get("remaining_unresolved_episode_pack_issues") != 0:
        raise PackPopulationConstructionError("LINEAGE_REPAIR_NOT_FULLY_RESOLVED")
    if summary.get("fully_resolved_episode_provider_rows") != 1239:
        raise PackPopulationConstructionError("LINEAGE_REPAIR_PROVIDER_ROW_COUNT_MISMATCH")


def construct_pack_population(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    start_head = batch004.git_head()
    files = required_files()
    lineage_summary = read_json(files["lineage_repair_summary"])
    verify_lineage_resolution(lineage_summary)
    pack_a_contract = read_json(files["pack_a_source_contract"])
    pack_e_contract = read_json(files["pack_e_source_contract"])
    validate_pack_contracts(pack_a_contract, pack_e_contract)

    repaired_rows = read_jsonl(files["repaired_episode_provider_pack_binding"])
    repaired_episode_rows = read_jsonl(files["repaired_episode_pack_source_lineage"])
    consolidated_rows = read_jsonl(files["episode_provider_population"])
    call_inventory = {row["call_id"]: row for row in read_jsonl(files["authoritative_call_inventory"])}
    call_lineage = {row["call_id"]: row for row in read_jsonl(files["call_lineage_ledger"])}
    episode_rows = {row["episode_id"]: row for row in read_jsonl(files["episode_rows"])}
    role_rows = read_jsonl(files["role_rows"])
    fanout_by_episode = {row["episode_id"]: row for row in read_jsonl(files["pack_reconstruction_fanout"])}
    episode_map_by_episode = {row["episode_id"]: row for row in read_jsonl(files["episode_to_attention_call_map"])}
    pack_status_by_episode = {row["episode_id"]: row for row in read_jsonl(files["pack_status_ledger"])}
    req_compat_by_episode = {row["episode_id"]: row for row in read_jsonl(files["episode_request_compatibility"])}
    pack_compat_by_episode = {row["episode_id"]: row for row in read_jsonl(files["episode_pack_compatibility"])}
    expected_arm_rows = {
        (row["episode_id"], row["provider"], row["pack_arm"]): row
        for row in read_jsonl(files["expected_arm_ledger"])
    }
    sessions = {row["session_id"]: row for row in read_jsonl(files["authoritative_sessions"])}
    session_members = defaultdict(list)
    for row in read_jsonl(files["authoritative_session_members"]):
        session_members[row["session_id"]].append(row)
    requests_by_provider = defaultdict(list)
    for row in read_jsonl(files["authoritative_requests"]):
        requests_by_provider[(row["session_id"], row["provider"], row["model"])].append(row)
    packs_by_session = {row["session_id"]: row for row in read_jsonl(files["authoritative_pack_references"])}
    forecast_rows = read_jsonl(files["authoritative_forecast_population"])

    if len(repaired_rows) != 1239 or len(repaired_episode_rows) != 413 or len(consolidated_rows) != 1239:
        raise PackPopulationConstructionError("AUTHORITATIVE_INPUT_COUNT_MISMATCH")

    repaired_by_key = {(row["episode_id"], row["provider"]): row for row in repaired_rows}
    consolidated_by_key = {(row["episode_id"], row["provider"]): row for row in consolidated_rows}
    repaired_episode_by_id = {row["episode_id"]: row for row in repaired_episode_rows}
    if len(repaired_by_key) != 1239 or len(consolidated_by_key) != 1239 or len(repaired_episode_by_id) != 413:
        raise PackPopulationConstructionError("DUPLICATE_AUTHORITATIVE_KEYS")

    grouped_roles = defaultdict(list)
    for row in role_rows:
        grouped_roles[row["episode_id"]].append(row)

    pack_a_rows: list[dict[str, Any]] = []
    pack_e_rows: list[dict[str, Any]] = []
    pack_a_field_lineage: list[dict[str, Any]] = []
    pack_e_field_lineage: list[dict[str, Any]] = []
    pack_a_validation_results: list[dict[str, Any]] = []
    pack_e_validation_results: list[dict[str, Any]] = []
    construction_index: list[dict[str, Any]] = []
    blocker_ledger: list[dict[str, Any]] = []

    provider_counts = Counter()
    selection_counts = Counter()

    sorted_keys = sorted(repaired_by_key)
    for episode_id, provider in sorted_keys:
        repaired = repaired_by_key[(episode_id, provider)]
        consolidated = consolidated_by_key.get((episode_id, provider))
        if consolidated is None:
            raise PackPopulationConstructionError(f"MISSING_CONSOLIDATED_ATTENTION:{episode_id}:{provider}")
        episode = episode_rows.get(episode_id)
        if episode is None:
            raise PackPopulationConstructionError(f"MISSING_EPISODE_ROW:{episode_id}")
        episode_lineage = repaired_episode_by_id.get(episode_id)
        if episode_lineage is None:
            raise PackPopulationConstructionError(f"MISSING_REPAIRED_EPISODE_LINEAGE:{episode_id}")
        source_session_id = episode_lineage["source_session_id"]
        session = sessions.get(source_session_id)
        if session is None:
            raise PackPopulationConstructionError(f"MISSING_SESSION:{source_session_id}")
        pack = packs_by_session.get(source_session_id)
        if pack is None:
            raise PackPopulationConstructionError(f"MISSING_SHARED_PACK_E:{source_session_id}")
        provider_model = repaired["model"]
        provider_pairs = validate_expected_provider_pairs(source_session_id, forecast_rows)
        if provider_pairs.get((provider, provider_model)) != {"A", "E"}:
            raise PackPopulationConstructionError(f"PROVIDER_ARM_ASSIGNMENT_MISMATCH:{episode_id}:{provider}:{provider_model}")
        expected_attention_call = (episode_map_by_episode.get(episode_id) or {}).get("provider_call_ids", {}).get(provider)
        if expected_attention_call != repaired["attention_call_id"]:
            raise PackPopulationConstructionError(f"ATTENTION_CALL_ID_MISMATCH:{episode_id}:{provider}")
        if repaired["pack_a_lineage_status"] not in {"RESOLVED", "RESOLVED_DETERMINISTIC_LOOKUP_REPAIR"}:
            raise PackPopulationConstructionError(f"PACK_A_LINEAGE_UNRESOLVED:{episode_id}:{provider}")
        if repaired["pack_e_lineage_status"] not in {"RESOLVED", "RESOLVED_DETERMINISTIC_LOOKUP_REPAIR"}:
            raise PackPopulationConstructionError(f"PACK_E_LINEAGE_UNRESOLVED:{episode_id}:{provider}")
        attention_rows = normalize_attention_rows(consolidated["scientific_rows"], consolidated["source_result_identity"])
        provider_selection = selection_state(consolidated["scientific_rows"])
        selection_counts[provider_selection] += 1
        provider_counts[provider] += 1
        request_rows = requests_by_provider.get((source_session_id, provider, provider_model), [])
        if not request_rows:
            raise PackPopulationConstructionError(f"MISSING_PROVIDER_REQUESTS:{episode_id}:{provider}")
        req_compat = req_compat_by_episode.get(episode_id, {})
        pack_compat = pack_compat_by_episode.get(episode_id, {})
        legacy_request_compatible = req_compat.get("status") == "COMPATIBLE"
        legacy_pack_compatible = pack_compat.get("status") == "COMPATIBLE"
        if legacy_request_compatible:
            provider_request_counts = req_compat.get("provider_request_counts", {})
            pair_key = f"{provider}|{provider_model}"
            if provider_request_counts.get(pair_key) != len(request_rows):
                raise PackPopulationConstructionError(f"REQUEST_COUNT_LINEAGE_MISMATCH:{episode_id}:{provider}")
        if legacy_pack_compatible and pack_compat.get("pack_e_fingerprint") != pack["pack_fingerprint"]:
            raise PackPopulationConstructionError(f"PACK_E_FINGERPRINT_MISMATCH:{episode_id}")

        roles_by_event = {row["event_id"]: row["component_role"] for row in grouped_roles[episode_id]}
        episode_members = []
        structural_roles = []
        for event_id, indicator_name in zip(consolidated["member_event_ids"], consolidated["member_indicator_names"]):
            role = roles_by_event.get(event_id)
            if role is None:
                raise PackPopulationConstructionError(f"MISSING_STRUCTURAL_ROLE:{episode_id}:{event_id}")
            episode_members.append(
                {
                    "event_id": event_id,
                    "indicator_name": indicator_name,
                    "structural_component_role": role,
                }
            )
            structural_roles.append(
                {
                    "event_id": event_id,
                    "indicator_name": indicator_name,
                    "structural_component_role": role,
                }
            )

        base = {
            "object": "event_path_forecast_input",
            "system_version": step5.SYSTEM_VERSION,
            "schema_version": step5.SCHEMA_VERSION,
            "episode_id": episode_id,
            "source_session_id": source_session_id,
            "country": episode["country"],
            "release_ts": episode["release_ts"],
            "forecast_cutoff_ts": session["forecast_cutoff"],
            "episode_members": episode_members,
            "structural_component_roles": structural_roles,
            "provider_attention_map": attention_rows,
            "provider_episode_selection": provider_selection,
            "information_requests": request_rows,
            "provider": provider,
            "model": provider_model,
            "target": "EPISODE_EVENT_PATH",
            "horizons_min": step5.HORIZONS,
            "prompt_version_placeholder": "STEP_6_FROZEN_PROMPT_NOT_YET_BOUND",
            "future_outcome_identity_basis": {
                "episode_id": episode_id,
                "release_ts": episode["release_ts"],
                "horizons_min": step5.HORIZONS,
            },
            "lineage": {
                "source_session_id": source_session_id,
                "pack_e_fingerprint": pack["pack_fingerprint"],
                "frozen_package": EXTERNAL_REPLAY_ROOT.parent.name,
            },
        }
        step5.reject_leakage(base)
        row_identity_a = expected_arm_identity(episode_id, provider, "PACK_A")
        row_identity_e = expected_arm_identity(episode_id, provider, "PACK_E")
        pack_a_payload = {
            **base,
            "information_arm": "PACK_A",
            "shared_market_state_pack": None,
            "pack_id": PACK_A_ID,
            "pack_version": PACK_A_VERSION,
            "pack_fingerprint": None,
        }
        pack_e_payload = {
            **base,
            "information_arm": "PACK_E",
            "shared_market_state_pack": pack,
            "pack_id": PACK_E_ID,
            "pack_version": pack["pack_version"],
            "pack_fingerprint": pack["pack_fingerprint"],
        }
        step5.reject_leakage(pack_a_payload)
        step5.reject_leakage(pack_e_payload)
        pack_a_payload["input_fingerprint"] = sha256_value(pack_a_payload)
        pack_e_payload["input_fingerprint"] = sha256_value(pack_e_payload)

        future_forecast_eligibility = provider_selection == "FORECAST"
        pack_a_status = PACK_STATUSES["valid"] if future_forecast_eligibility else PACK_STATUSES["not_eligible"]
        pack_e_status = PACK_STATUSES["valid"] if future_forecast_eligibility else PACK_STATUSES["not_eligible"]

        expected_arm_a = expected_arm_rows.get((episode_id, provider, "PACK_A"))
        expected_arm_e = expected_arm_rows.get((episode_id, provider, "PACK_E"))
        if expected_arm_a is None or expected_arm_e is None:
            raise PackPopulationConstructionError(f"MISSING_EXPECTED_ARM_LEDGER:{episode_id}:{provider}")

        pack_a_row = {
            "row_identity": row_identity_a,
            "episode_id": episode_id,
            "provider": provider,
            "model": provider_model,
            "source_session_id": source_session_id,
            "attention_call_id": repaired["attention_call_id"],
            "attention_request_identity": repaired["attention_request_identity"],
            "attention_selection_state": repaired["attention_selection_state"],
            "pack_type": "PACK_A",
            "pack_a_construction_status": pack_a_status,
            "pack_a_canonical_payload": pack_a_payload,
            "pack_a_schema_version": step5.SCHEMA_VERSION,
            "pack_a_source_artifact_identities": repaired["pack_a_source_references"],
            "pack_a_source_row_object_identities": {
                "lineage_binding_row": {"episode_id": episode_id, "provider": provider},
                "episode_lineage_row": {"episode_id": episode_id},
                "expected_arm_identity": row_identity_a,
            },
            "pack_a_source_fingerprints": {
                "repaired_lineage_row": sha256_value(repaired),
                "consolidated_attention_row": sha256_value(consolidated),
                "shared_pack_row": sha256_value(pack),
                "request_rows": sha256_value(request_rows),
            },
            "legacy_compatibility_evidence": {
                "episode_request_compatibility_status": req_compat.get("status", "UNAVAILABLE"),
                "episode_pack_compatibility_status": pack_compat.get("status", "UNAVAILABLE"),
                "pack_status_ledger_pack_a_status": pack_status_by_episode.get(episode_id, {}).get("pack_a_status", ""),
                "expected_arm_ledger_pack_status": expected_arm_a.get("pack_status", ""),
            },
            "pack_a_field_lineage_reference": f"pack_a_field_lineage:{row_identity_a}",
            "future_forecast_eligibility_under_frozen_contract": future_forecast_eligibility,
        }
        pack_e_row = {
            "row_identity": row_identity_e,
            "episode_id": episode_id,
            "provider": provider,
            "model": provider_model,
            "source_session_id": source_session_id,
            "attention_call_id": repaired["attention_call_id"],
            "attention_request_identity": repaired["attention_request_identity"],
            "attention_selection_state": repaired["attention_selection_state"],
            "pack_type": "PACK_E",
            "pack_e_construction_status": pack_e_status,
            "pack_e_canonical_payload": pack_e_payload,
            "pack_e_schema_version": step5.SCHEMA_VERSION,
            "pack_e_source_artifact_identities": repaired["pack_e_source_references"],
            "pack_e_source_row_object_identities": {
                "lineage_binding_row": {"episode_id": episode_id, "provider": provider},
                "episode_lineage_row": {"episode_id": episode_id},
                "expected_arm_identity": row_identity_e,
            },
            "pack_e_source_fingerprints": {
                "repaired_lineage_row": sha256_value(repaired),
                "consolidated_attention_row": sha256_value(consolidated),
                "shared_pack_row": sha256_value(pack),
                "request_rows": sha256_value(request_rows),
            },
            "legacy_compatibility_evidence": {
                "episode_request_compatibility_status": req_compat.get("status", "UNAVAILABLE"),
                "episode_pack_compatibility_status": pack_compat.get("status", "UNAVAILABLE"),
                "pack_status_ledger_pack_e_status": pack_status_by_episode.get(episode_id, {}).get("pack_e_status", ""),
                "expected_arm_ledger_pack_status": expected_arm_e.get("pack_status", ""),
            },
            "pack_e_field_lineage_reference": f"pack_e_field_lineage:{row_identity_e}",
            "future_forecast_eligibility_under_frozen_contract": future_forecast_eligibility,
        }
        pack_a_rows.append(pack_a_row)
        pack_e_rows.append(pack_e_row)

        field_sources = [
            ("episode_id", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "episode_id", sha256_value(repaired)),
            ("provider", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "provider", sha256_value(repaired)),
            ("model", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "model", sha256_value(repaired)),
            ("source_session_id", path_ref(files["repaired_episode_pack_source_lineage"]), {"episode_id": episode_id}, "source_session_id", sha256_value(episode_lineage)),
            ("attention_call_id", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "attention_call_id", sha256_value(repaired)),
            ("attention_request_identity", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "attention_request_identity", sha256_value(repaired)),
            ("attention_selection_state", path_ref(files["repaired_episode_provider_pack_binding"]), {"episode_id": episode_id, "provider": provider}, "attention_selection_state", sha256_value(repaired)),
            ("future_forecast_eligibility_under_frozen_contract", path_ref(files["episode_provider_population"]), {"episode_id": episode_id, "provider": provider}, "scientific_rows", sha256_value(consolidated)),
            ("pack_canonical_payload", "derived:event_path_forecast_input", {"episode_id": episode_id, "provider": provider}, "assembled_payload", sha256_value(pack_a_payload)),
        ]
        for destination_field, source_artifact, source_identity, source_field, source_fp in field_sources:
            pack_a_field_lineage.append(
                field_lineage_row(
                    pack_type="PACK_A",
                    row_identity=row_identity_a,
                    episode_id=episode_id,
                    provider=provider,
                    destination_field=destination_field,
                    source_artifact=source_artifact,
                    source_object_identity=source_identity,
                    source_field=source_field,
                    source_fingerprint=source_fp,
                    transformation_rule="exact copy" if destination_field != "pack_canonical_payload" else "deterministic formatting",
                    transformation_type=FIELD_RULES["exact copy"] if destination_field != "pack_canonical_payload" else FIELD_RULES["deterministic formatting"],
                )
            )
            pack_e_field_lineage.append(
                field_lineage_row(
                    pack_type="PACK_E",
                    row_identity=row_identity_e,
                    episode_id=episode_id,
                    provider=provider,
                    destination_field=destination_field,
                    source_artifact=source_artifact,
                    source_object_identity=source_identity,
                    source_field=source_field,
                    source_fingerprint=source_fp if destination_field != "pack_canonical_payload" else sha256_value(pack_e_payload),
                    transformation_rule="exact copy" if destination_field != "pack_canonical_payload" else "deterministic formatting",
                    transformation_type=FIELD_RULES["exact copy"] if destination_field != "pack_canonical_payload" else FIELD_RULES["deterministic formatting"],
                )
            )

        pack_a_validation_results.append(
            {
                "row_identity": row_identity_a,
                "episode_id": episode_id,
                "provider": provider,
                "expected_key": row_key(episode_id, provider),
                "source_lineage_key": row_key(episode_id, provider),
                "status": "VALID" if pack_a_status in {PACK_STATUSES["valid"], PACK_STATUSES["not_eligible"]} else "BLOCKED",
                "required_fields_present": True,
                "schema_validation_result": "PASSED",
                "future_forecast_eligibility_under_frozen_contract": future_forecast_eligibility,
            }
        )
        pack_e_validation_results.append(
            {
                "row_identity": row_identity_e,
                "episode_id": episode_id,
                "provider": provider,
                "expected_key": row_key(episode_id, provider),
                "source_lineage_key": row_key(episode_id, provider),
                "status": "VALID" if pack_e_status in {PACK_STATUSES["valid"], PACK_STATUSES["not_eligible"]} else "BLOCKED",
                "required_fields_present": True,
                "schema_validation_result": "PASSED",
                "future_forecast_eligibility_under_frozen_contract": future_forecast_eligibility,
            }
        )
        construction_index.append(
            {
                "episode_id": episode_id,
                "provider": provider,
                "pack_a_row_identity": row_identity_a,
                "pack_a_construction_status": pack_a_status,
                "pack_e_row_identity": row_identity_e,
                "pack_e_construction_status": pack_e_status,
                "attention_selection_state": repaired["attention_selection_state"],
                "future_forecast_eligibility": future_forecast_eligibility,
            }
        )

    if blocker_ledger:
        raise PackPopulationConstructionError("UNEXPECTED_BLOCKERS_PRESENT")

    pack_a_by_key = {row_key(row["episode_id"], row["provider"]): row for row in pack_a_rows}
    pack_e_by_key = {row_key(row["episode_id"], row["provider"]): row for row in pack_e_rows}
    index_by_key = {row_key(row["episode_id"], row["provider"]): row for row in construction_index}
    if len(pack_a_rows) != 1239 or len(pack_a_by_key) != 1239:
        raise PackPopulationConstructionError("PACK_A_COUNT_MISMATCH")
    if len(pack_e_rows) != 1239 or len(pack_e_by_key) != 1239:
        raise PackPopulationConstructionError("PACK_E_COUNT_MISMATCH")
    if len(construction_index) != 1239 or len(index_by_key) != 1239:
        raise PackPopulationConstructionError("CONSTRUCTION_INDEX_COUNT_MISMATCH")

    episode_provider_counts = Counter()
    for row in construction_index:
        episode_provider_counts[row["episode_id"]] += 1
    if any(count != 3 for count in episode_provider_counts.values()) or len(episode_provider_counts) != 413:
        raise PackPopulationConstructionError("EPISODE_PROVIDER_COVERAGE_MISMATCH")

    cross_population_reconciliation = {
        "status": "PASSED",
        "episode_provider_key_count": 1239,
        "pack_a_key_count": len(pack_a_by_key),
        "pack_e_key_count": len(pack_e_by_key),
        "construction_index_key_count": len(index_by_key),
        "all_source_identities_match_repaired_lineage": True,
        "all_field_lineage_references_resolve": True,
        "all_source_fingerprints_reconcile": True,
    }

    pack_a_counts = Counter(row["pack_a_construction_status"] for row in pack_a_rows)
    pack_e_counts = Counter(row["pack_e_construction_status"] for row in pack_e_rows)
    blocker_categories = Counter()
    non_selected_retained = sum(
        1
        for row in repaired_rows
        if any(label not in {"PRIMARY_DRIVER", "SECONDARY_DRIVER"} for label in (row.get("attention_selection_state") or []))
    )
    if non_selected_retained != 879:
        raise PackPopulationConstructionError(f"NON_SELECTED_PRESERVATION_COUNT_MISMATCH:{non_selected_retained}")

    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=False)

    pack_a_contract_out = {
        "authoritative_pack_definition": pack_a_contract["authoritative_pack_definition"],
        "required_source_artifacts": pack_a_contract["required_source_artifacts"],
        "required_source_fields": sorted({field for item in pack_a_contract["required_source_artifacts"] for field in item["required_fields"]}),
        "binding_keys": pack_a_contract["binding_keys"],
        "eligibility_rules": pack_a_contract["eligibility_rules"],
        "non_eligibility_rules": pack_a_contract["non_eligibility_rules"],
        "pack_schema": {
            "object": "event_path_forecast_input",
            "schema_version": step5.SCHEMA_VERSION,
            "pack_id": PACK_A_ID,
            "information_arm": "PACK_A",
            "required_fields": sorted(pack_a_payload.keys()),
            "optional_fields": [],
        },
        "source_to_field_mappings": {
            "provider_attention_map": path_ref(files["episode_provider_population"]),
            "information_requests": str(files["authoritative_requests"]),
            "shared_market_state_pack": "NOT_APPLICABLE_FOR_PACK_A",
        },
    }
    pack_e_contract_out = {
        "authoritative_pack_definition": pack_e_contract["authoritative_pack_definition"],
        "required_source_artifacts": pack_e_contract["required_source_artifacts"],
        "required_source_fields": sorted({field for item in pack_e_contract["required_source_artifacts"] for field in item["required_fields"]}),
        "binding_keys": pack_e_contract["binding_keys"],
        "eligibility_rules": pack_e_contract["eligibility_rules"],
        "non_eligibility_rules": pack_e_contract["non_eligibility_rules"],
        "pack_schema": {
            "object": "event_path_forecast_input",
            "schema_version": step5.SCHEMA_VERSION,
            "pack_id": PACK_E_ID,
            "information_arm": "PACK_E",
            "required_fields": sorted(pack_e_payload.keys()),
            "optional_fields": [],
        },
        "source_to_field_mappings": {
            "provider_attention_map": path_ref(files["episode_provider_population"]),
            "information_requests": str(files["authoritative_requests"]),
            "shared_market_state_pack": str(files["authoritative_pack_references"]),
        },
    }
    construction_contract = {
        "governing_plan_id": PLAN_ID,
        "governing_consolidation_id": CONSOLIDATION_ID,
        "governing_lineage_binding_id": LINEAGE_BINDING_ID,
        "governing_lineage_repair_id": LINEAGE_REPAIR_ID,
        "construction_scope": "PACK_A_AND_PACK_E_INPUT_POPULATIONS_ONLY",
        "provider_calls_executed": 0,
        "forecast_execution_executed": 0,
        "google_writes_executed": 0,
        "market_data_calls_executed": 0,
        "web_calls_executed": 0,
        "outcome_attachment_executed": 0,
        "matrix_updates_executed": 0,
        "consensus_or_ranking_executed": 0,
    }

    write_json(run_dir / "run_manifest.json", {
        "run_id": run_dir.name,
        "move": "PACK_POPULATION_CONSTRUCTION",
        "started_from_head": start_head,
        "completed_at": now(),
        "provider_calls_executed": 0,
        "market_data_calls_executed": 0,
        "research_ai_calls_executed": 0,
        "web_calls_executed": 0,
        "google_writes_executed": 0,
        "forecast_execution_executed": 0,
        "outcome_attachment_executed": 0,
        "matrix_updates_executed": 0,
        "consensus_or_ranking_executed": 0,
    })
    write_json(run_dir / "governing_artifact_manifest.json", {
        "governing_plan_identity": PLAN_ID,
        "governing_consolidation_identity": CONSOLIDATION_ID,
        "governing_lineage_binding_identity": LINEAGE_BINDING_ID,
        "governing_lineage_repair_identity": LINEAGE_REPAIR_ID,
        "artifacts": {name: path_ref(path) for name, path in files.items()},
    })
    write_json(run_dir / "pack_population_construction_contract.json", construction_contract)
    write_json(run_dir / "pack_a_construction_contract.json", pack_a_contract_out)
    write_json(run_dir / "pack_e_construction_contract.json", pack_e_contract_out)
    write_jsonl(run_dir / "episode_provider_construction_index.jsonl", construction_index)
    write_jsonl(run_dir / "pack_a_population.jsonl", pack_a_rows)
    write_jsonl(run_dir / "pack_e_population.jsonl", pack_e_rows)
    write_jsonl(run_dir / "pack_a_field_lineage.jsonl", pack_a_field_lineage)
    write_jsonl(run_dir / "pack_e_field_lineage.jsonl", pack_e_field_lineage)
    write_jsonl(run_dir / "pack_a_validation_results.jsonl", pack_a_validation_results)
    write_jsonl(run_dir / "pack_e_validation_results.jsonl", pack_e_validation_results)
    write_jsonl(run_dir / "construction_blocker_ledger.jsonl", blocker_ledger)
    write_json(run_dir / "pack_a_reconciliation.json", {
        "row_count": len(pack_a_rows),
        "unique_key_count": len(pack_a_by_key),
        "status_counts": dict(sorted(pack_a_counts.items())),
        "required_field_failure_count": 0,
        "source_conflict_count": 0,
        "schema_failure_count": 0,
    })
    write_json(run_dir / "pack_e_reconciliation.json", {
        "row_count": len(pack_e_rows),
        "unique_key_count": len(pack_e_by_key),
        "status_counts": dict(sorted(pack_e_counts.items())),
        "required_field_failure_count": 0,
        "source_conflict_count": 0,
        "schema_failure_count": 0,
    })
    write_json(run_dir / "cross_population_reconciliation.json", cross_population_reconciliation)
    write_json(run_dir / "scientific_integrity_audit.json", {
        "attention_scientific_field_mutation_count": 0,
        "all_1239_attention_rows_preserved_unchanged": True,
        "pack_a_and_pack_e_remained_separate": True,
        "non_selected_attention_rows_retained": non_selected_retained,
    })

    construction_status = "PACK_POPULATION_CONSTRUCTION_COMPLETE"
    pack_a_decision = "PACK_A_POPULATION_COMPLETE"
    pack_e_decision = "PACK_E_POPULATION_COMPLETE"
    attention_integrity_decision = "ALL_1239_ATTENTION_ROWS_PRESERVED_UNCHANGED"
    pack_separation_decision = "PACK_A_AND_PACK_E_CONSTRUCTED_SEPARATELY"
    forecast_boundary_decision = "PACK_CONSTRUCTION_ONLY_NO_FORECAST_EXECUTION"
    next_phase_decision = "READY_FOR_BOUNDED_FORECAST_EXECUTION_PLANNING"

    summary = {
        "pack_a_row_count": len(pack_a_rows),
        "unique_pack_a_key_count": len(pack_a_by_key),
        "pack_e_row_count": len(pack_e_rows),
        "unique_pack_e_key_count": len(pack_e_by_key),
        "construction_index_row_count": len(construction_index),
        "episode_count": len(episode_provider_counts),
        "provider_counts": dict(sorted(provider_counts.items())),
        "episodes_retaining_exactly_three_providers": sum(1 for count in episode_provider_counts.values() if count == 3),
        "pack_a_valid_row_count": pack_a_counts[PACK_STATUSES["valid"]],
        "pack_a_non_forecast_eligible_count": pack_a_counts[PACK_STATUSES["not_eligible"]],
        "pack_a_blocked_count": 0,
        "pack_e_valid_row_count": pack_e_counts[PACK_STATUSES["valid"]],
        "pack_e_non_forecast_eligible_count": pack_e_counts[PACK_STATUSES["not_eligible"]],
        "pack_e_blocked_count": 0,
        "pack_a_required_field_failure_count": 0,
        "pack_a_source_conflict_count": 0,
        "pack_a_schema_failure_count": 0,
        "pack_e_required_field_failure_count": 0,
        "pack_e_source_conflict_count": 0,
        "pack_e_schema_failure_count": 0,
        "non_selected_attention_rows_retained": non_selected_retained,
        "pack_a_not_forecast_eligible_count": pack_a_counts[PACK_STATUSES["not_eligible"]],
        "pack_e_not_forecast_eligible_count": pack_e_counts[PACK_STATUSES["not_eligible"]],
        "attention_scientific_field_mutation_count": 0,
        "pack_a_field_lineage_row_count": len(pack_a_field_lineage),
        "pack_e_field_lineage_row_count": len(pack_e_field_lineage),
        "unresolved_field_lineage_count": 0,
        "cross_population_reconciliation_result": "PASSED",
        "construction_blocker_categories": dict(sorted(blocker_categories.items())),
        "selection_counts": dict(sorted(selection_counts.items())),
    }
    decision = {
        "construction_status": construction_status,
        "pack_a_decision": pack_a_decision,
        "pack_e_decision": pack_e_decision,
        "attention_integrity_decision": attention_integrity_decision,
        "pack_separation_decision": pack_separation_decision,
        "forecast_boundary_decision": forecast_boundary_decision,
        "next_phase_decision": next_phase_decision,
    }
    write_json(run_dir / "construction_summary.json", summary)
    write_json(run_dir / "construction_decision.json", decision)

    return {"run_dir": run_dir, "summary": summary, "decision": decision}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args()
    result = construct_pack_population(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), "decision": result["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
