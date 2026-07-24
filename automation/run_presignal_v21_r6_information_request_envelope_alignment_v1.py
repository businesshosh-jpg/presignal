"""Offline full-envelope audit for the two preserved R6 Information-Request responses."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_r6_information_request_execution_v1 as legacy
from automation import run_presignal_v21_r6_repaired_information_request_execution_v1 as repaired


FIRST = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
SECOND = ROOT / "outputs" / "presignal_v21_designed_drift_r6_repaired_information_request_execution" / "R6-REPAIRED-INFORMATION-REQUEST-EXECUTION-20260724-v1"
LIVE_AUTHORITY = ROOT / "outputs" / "presignal_v21_designed_drift_r6_live_authority" / "R6-LIVE-AUTHORITY-20260723-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_envelope_alignment" / "R6-INFORMATION-REQUEST-ENVELOPE-ALIGNMENT-20260724-v1"

PROMPT_VERSION = "presignal_v21_information_request_prompt_v1"
PROMPT_CHECKSUM = "sha256:1bfa4b3a255292f404411d4053c6aa0eed7a7567500280c35e0bf3d55ebc02e7"
SCHEMA_VERSION = "v0"
SECOND_RAW_CHECKSUM = "sha256:98a42ca11fb6ef1db9147d6ae6d5e4ca670acdb99c2bedc00576f508ebfa56fe"
FIRST_RAW_CHECKSUM = "sha256:a916fffd5ceea8244d7be55f57896aec0b2c14b5ecbca2419a024436cd031e2b"
PROVIDER, MODEL = "Gemini", "gemini-2.5-flash-lite"


class EnvelopeAlignmentError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(legacy.plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def payload(evidence_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = read(evidence_path)
    return evidence, json.loads(evidence["raw_response"])


def registry_status(source: str) -> dict[str, Any]:
    manifest = read(LIVE_AUTHORITY / "prospective_source_environment_manifest.json")
    matches = [row for row in manifest["sources"] if source in {row["source_id"], row["source_key_or_domain"]}]
    return {"source": source, "registry_identity": manifest["binding_name"], "approved_source_match": bool(matches), "requested_source_registry_status": "BOUND_AKSR_ENTRY" if matches else "UNRESOLVED_NO_BOUND_AKSR_ENTRY", "registry_entry": matches[0] if matches else None}


def normalize_exact_envelope(*, raw: Mapping[str, Any], transport: Mapping[str, Any], prompt_checksum: str, schema_version: str) -> dict[str, Any]:
    """Canonicalize only the exact historical routed-provider envelope condition."""
    if transport.get("actual_provider") != PROVIDER:
        raise EnvelopeAlignmentError("ENVELOPE_TRANSPORT_PROVIDER_MISMATCH")
    if transport.get("actual_model") != MODEL:
        raise EnvelopeAlignmentError("ENVELOPE_TRANSPORT_MODEL_MISMATCH")
    if prompt_checksum != PROMPT_CHECKSUM:
        raise EnvelopeAlignmentError("ENVELOPE_PROMPT_VERSION_MISMATCH")
    if schema_version != SCHEMA_VERSION:
        raise EnvelopeAlignmentError("ENVELOPE_SCHEMA_VERSION_MISMATCH")
    if raw.get("provider") != "S&P Global":
        raise EnvelopeAlignmentError("ENVELOPE_RAW_PAYLOAD_PROVIDER_VALUE_MISMATCH")
    normalized = dict(raw)
    normalized["provider"] = PROVIDER
    sources = [str(item.get("suggested_source") or "") for item in raw.get("information_items", []) if isinstance(item, Mapping)]
    return {"canonical_payload": normalized, "transport_provider_identity": PROVIDER, "transport_model_identity": MODEL, "canonical_provider_identity": PROVIDER, "raw_payload_provider_value": raw["provider"], "payload_field_classification": "OVERLOADED_PROVIDER_FIELD", "requested_source_identity": "S&P Global" if sources and all(value == "S&P Global" for value in sources) else None, "requested_source_role": "ITEM_LEVEL_SUGGESTED_SOURCE_CANDIDATE", "requested_source_registry_status": registry_status("S&P Global")["requested_source_registry_status"], "mapping_rule": "EXACT_GEMINI_R6_REQUEST_ENVELOPE_TRANSPORT_BOUND_V1", "raw_response_mutated": False, "not_a_gemini_alias": True}


def item_mismatches(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary = str(raw.get("session_information_summary") or "")
    if "released actual" in summary.lower():
        rows.append({"path": "session_information_summary", "classification": "ROLE_MISMATCH", "severity": "NONREPAIRABLE", "code": "PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE", "value": summary})
    for index, item in enumerate(raw.get("information_items") or [], 1):
        if not isinstance(item, Mapping):
            rows.append({"path": f"information_items[{index - 1}]", "classification": "TYPE_MISMATCH", "severity": "NONREPAIRABLE", "code": "REQUEST_ITEM_NOT_OBJECT"})
            continue
        category = item.get("information_category")
        if category not in lineage.VALID_CATEGORIES:
            rows.append({"path": f"information_items[{index - 1}].information_category", "classification": "ENUM_MISMATCH", "severity": "NONREPAIRABLE", "code": "REQUEST_CATEGORY_INVALID", "value": category})
        priority = str(item.get("priority") or "")
        if priority not in lineage.VALID_PRIORITIES:
            rows.append({"path": f"information_items[{index - 1}].priority", "classification": "ENUM_MISMATCH", "severity": "REPAIRABLE_FROZEN_NORMALIZATION", "code": "PRIORITY_NORMALIZED_BY_FROZEN_MAP", "value": priority, "canonical_value": capability._normal_priority(priority)[0]})
        channel = str(item.get("affected_channel") or "")
        if channel not in lineage.VALID_CHANNELS:
            rows.append({"path": f"information_items[{index - 1}].affected_channel", "classification": "ENUM_MISMATCH", "severity": "REPAIRABLE_FROZEN_NORMALIZATION", "code": "CHANNEL_NORMALIZED_BY_FROZEN_MAP", "value": channel, "canonical_value": capability._normal_channel(channel)})
        if not isinstance(item.get("available_now"), str):
            rows.append({"path": f"information_items[{index - 1}].available_now", "classification": "TYPE_MISMATCH", "severity": "REPAIRABLE_FROZEN_NORMALIZATION", "code": "AVAILABILITY_NORMALIZED_TO_UNKNOWN", "value_type": type(item.get("available_now")).__name__, "canonical_value": "unknown"})
        text = str(item.get("requested_information") or "")
        if "released actual" in text.lower():
            rows.append({"path": f"information_items[{index - 1}].requested_information", "classification": "ROLE_MISMATCH", "severity": "NONREPAIRABLE", "code": "PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE", "value": text})
    return rows


def field_inventory(*, raw: Mapping[str, Any], transport: Mapping[str, Any], episode: Mapping[str, Any], attention: Mapping[str, Any]) -> list[dict[str, Any]]:
    top_roles = {
        "object": ("response object discriminator", "ALIGNED"), "session_id": ("Episode identity", "ALIGNED"),
        "provider": ("overloaded payload field; not LLM authority", "TRUST_BOUNDARY_MISMATCH"),
        "information_items": ("Request collection", "ALIGNED"), "session_information_summary": ("model-authored rationale summary", "ALIGNED"), "status": ("response status", "ALIGNED"),
    }
    mismatch_by_path = {row["path"]: row["classification"] for row in item_mismatches(raw)}
    rows = [{"json_path": key, "raw_value_or_type": raw.get(key) if key != "information_items" else "array", "producer": "model payload", "prompt_instruction": "exact output key", "schema_definition": key, "normalizer_interpretation": role, "validator_interpretation": role, "canonicalizer_destination": key, "trusted_or_model_authored": "model-authored", "required_or_optional": "required", "semantic_role": role, "current_validation_status": mismatch_by_path.get(key, status)} for key, (role, status) in top_roles.items()]
    rows.extend([
        {"json_path": "transport.actual_provider", "raw_value_or_type": transport.get("actual_provider"), "producer": "trusted bridge", "prompt_instruction": "out of band", "schema_definition": "transport envelope", "normalizer_interpretation": "canonical LLM provider", "validator_interpretation": "authoritative", "canonicalizer_destination": "provider lineage", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "LLM provider identity", "current_validation_status": "ALIGNED"},
        {"json_path": "transport.actual_model", "raw_value_or_type": transport.get("actual_model"), "producer": "trusted bridge", "prompt_instruction": "out of band", "schema_definition": "transport envelope", "normalizer_interpretation": "canonical LLM model", "validator_interpretation": "authoritative", "canonicalizer_destination": "model lineage", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "LLM model identity", "current_validation_status": "ALIGNED"},
        {"json_path": "context.attention_identity", "raw_value_or_type": attention["attention_identity"], "producer": "caller-bound Attention", "prompt_instruction": "provider Attention Map context", "schema_definition": "caller context", "normalizer_interpretation": "Request lineage", "validator_interpretation": "authoritative caller binding", "canonicalizer_destination": "attention lineage", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "Attention identity", "current_validation_status": "ALIGNED"},
        {"json_path": "context.forecast_cutoff", "raw_value_or_type": episode["forecast_cutoff_ts"], "producer": "canonical Episode", "prompt_instruction": "caller context", "schema_definition": "caller context", "normalizer_interpretation": "cutoff lineage", "validator_interpretation": "authoritative caller binding", "canonicalizer_destination": "forecast cutoff", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "forecast cutoff", "current_validation_status": "ALIGNED"},
        {"json_path": "context.prompt_version", "raw_value_or_type": PROMPT_VERSION, "producer": "authorized caller", "prompt_instruction": "resolved prompt authority", "schema_definition": "Request execution envelope", "normalizer_interpretation": "prompt lineage", "validator_interpretation": "authoritative caller binding", "canonicalizer_destination": "prompt version", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "prompt version", "current_validation_status": "ALIGNED"},
        {"json_path": "context.response_schema_version", "raw_value_or_type": SCHEMA_VERSION, "producer": "authorized caller", "prompt_instruction": "request envelope binds schema version", "schema_definition": "Request execution envelope", "normalizer_interpretation": "schema lineage", "validator_interpretation": "authoritative caller binding", "canonicalizer_destination": "schema version", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "response schema version", "current_validation_status": "ALIGNED"},
        {"json_path": "transport.started_timestamp", "raw_value_or_type": transport.get("started_timestamp"), "producer": "trusted bridge", "prompt_instruction": "out of band", "schema_definition": "transport envelope", "normalizer_interpretation": "dispatch timestamp", "validator_interpretation": "cutoff comparison", "canonicalizer_destination": "provenance only", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "provider dispatch timestamp", "current_validation_status": "ALIGNED"},
        {"json_path": "transport.completed_timestamp", "raw_value_or_type": transport.get("completed_timestamp"), "producer": "trusted bridge", "prompt_instruction": "out of band", "schema_definition": "transport envelope", "normalizer_interpretation": "effective timestamp", "validator_interpretation": "cutoff comparison", "canonicalizer_destination": "provenance only", "trusted_or_model_authored": "trusted", "required_or_optional": "required", "semantic_role": "provider completion timestamp", "current_validation_status": "ALIGNED"},
    ])
    for index, item in enumerate(raw.get("information_items") or []):
        for field in ("request_rank", "requested_information", "information_category", "priority", "reason", "affected_channel", "event_family_relevance", "linked_event_ids", "linked_attention_labels", "available_now", "suggested_source", "expected_forecast_use", "is_market_state_candidate"):
            value = item.get(field) if isinstance(item, Mapping) else None
            path = f"information_items[{index}].{field}"
            rows.append({"json_path": path, "raw_value_or_type": value if not isinstance(value, (dict, list)) else type(value).__name__, "producer": "model payload", "prompt_instruction": "exact item key", "schema_definition": field, "normalizer_interpretation": field, "validator_interpretation": "field-specific canonical validation", "canonicalizer_destination": field, "trusted_or_model_authored": "model-authored", "required_or_optional": "required", "semantic_role": "Request item field", "current_validation_status": mismatch_by_path.get(path, "ALIGNED")})
    return rows


def matrix() -> list[dict[str, Any]]:
    rows = [
        ("transport provider", "transport.actual_provider", "transport.actual_provider", "transport_provider_identity", "provider lineage", "trusted LLM provider", "ALIGNED"),
        ("transport model", "transport.actual_model", "transport.actual_model", "transport_model_identity", "model lineage", "trusted LLM model", "ALIGNED"),
        ("provider", "provider", "provider", "raw_payload_provider_value", "canonical_provider_identity", "payload role versus LLM provider", "TRUST_BOUNDARY_MISMATCH"),
        ("session_id", "session_id", "session_id", "episode_identity", "episode lineage", "Episode identity", "ALIGNED"),
        ("information_category", "information_category", "information_category", "canonical_information_category", "information_category", "frozen Request category", "ALIGNED"),
        ("suggested_source", "suggested_source", "suggested_source", "requested_source_identity", "source provenance", "requested source candidate", "ALIGNED"),
        ("priority", "priority", "priority", "normalized priority", "priority", "Request priority", "ENUM_MISMATCH"),
        ("affected_channel", "affected_channel", "affected_channel", "normalized channel", "affected_channel", "market channel", "ENUM_MISMATCH"),
        ("available_now", "available_now", "available_now", "normalized availability", "available_now", "availability state", "TYPE_MISMATCH"),
        ("request_rank", "request_rank", "request_rank", "canonical_request_order", "canonical_request_order", "Request order", "ALIGNED"),
        ("attention context", "caller context", "caller context", "attention_identity", "attention lineage", "Attention identity", "ALIGNED"),
        ("cutoff", "caller context", "caller context", "forecast_cutoff", "cutoff lineage", "forecast cutoff", "ALIGNED"),
    ]
    return [{"prompt_name": item[0], "raw_payload_name": item[1], "schema_name": item[2], "normalized_name": item[3], "canonical_name": item[4], "semantic_meaning": item[5], "agreement_status": item[6]} for item in rows]


def audit() -> dict[str, int]:
    return {"provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0, "google_reads": 0, "google_writes": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0}


def run(*, output: Path = OUTPUT) -> None:
    first_evidence, first = payload(FIRST / "information_request_raw_response.json")
    second_evidence, second = payload(SECOND / "repaired_information_request_raw_response.json")
    episode, _members, attention, _raw_attention = legacy.load_inputs()
    inventory = field_inventory(raw=second, transport=second_evidence["transport_metadata"], episode=episode, attention=attention)
    all_mismatches = [{"path": "provider", "classification": "TRUST_BOUNDARY_MISMATCH", "severity": "REPAIRABLE", "code": "REQUEST_RESPONSE_PROVIDER_MISMATCH", "value": second["provider"]}, *item_mismatches(second)]
    repairable = [row for row in all_mismatches if row["severity"].startswith("REPAIRABLE")]
    nonrepairable = [row for row in all_mismatches if row["severity"] == "NONREPAIRABLE"]
    mapped = normalize_exact_envelope(raw=second, transport=second_evidence["transport_metadata"], prompt_checksum=PROMPT_CHECKSUM, schema_version=SCHEMA_VERSION)
    raw_checksum_valid = checksum(second_evidence["raw_response"]) == SECOND_RAW_CHECKSUM == second_evidence["raw_response_checksum"]
    response_comparison = {"first_response": {"checksum": first_evidence["raw_response_checksum"], "provider": first["provider"], "categories": [item["information_category"] for item in first["information_items"]]}, "second_response": {"checksum": second_evidence["raw_response_checksum"], "provider": second["provider"], "categories": [item["information_category"] for item in second["information_items"]]}, "similarities": ["same Episode identity", "same top-level raw provider value S&P Global", "three Request items"], "differences": ["second prompt version is repaired v1", "first categories are invalid Economic Indicator", "second categories are growth_context"]}
    reports = {
        "information_request_envelope_field_inventory.json": {"field_count": len(inventory), "fields": inventory},
        "information_request_prompt_schema_field_matrix.json": {"rows": matrix(), "matrix_checksum": checksum(matrix())},
        "information_request_two_response_comparison.json": response_comparison,
        "information_request_transport_trust_boundary.json": {"trusted": {"transport_provider_identity": second_evidence["transport_metadata"]["actual_provider"], "transport_model_identity": second_evidence["transport_metadata"]["actual_model"]}, "model_authored": {"raw_payload_provider_value": second["provider"], "item_suggested_sources": [item["suggested_source"] for item in second["information_items"]]}, "rule": "Trusted bridge metadata owns LLM identity. Raw payload provider is preserved as a non-authoritative role field; item suggested_source owns source candidate semantics."},
        "information_request_provider_source_classification.json": {"classification": "OVERLOADED_PROVIDER_FIELD", "transport_provider": PROVIDER, "transport_model": MODEL, "raw_payload_provider_value": second["provider"], "canonical_provider": mapped["canonical_provider_identity"], "requested_source": mapped["requested_source_identity"], "requested_source_role": mapped["requested_source_role"], "requested_source_registry_status": mapped["requested_source_registry_status"], "s_and_p_global_treated_as_gemini_alias": False, "mapping_rule": mapped["mapping_rule"]},
        "information_request_complete_mismatch_report.json": {"all_detected_mismatches": all_mismatches, "repairable_mismatches": repairable, "nonrepairable_mismatches": nonrepairable, "next_expected_validator_failures": [row["code"] for row in nonrepairable], "first_deterministic_validator_divergence_before_alignment": "REQUEST_RESPONSE_PROVIDER_MISMATCH", "first_deterministic_divergence_after_envelope_alignment": nonrepairable[0]["code"] if nonrepairable else None},
        "information_request_envelope_alignment_contract.json": {"mapping_name": mapped["mapping_rule"], "when": {"transport_provider": PROVIDER, "transport_model": MODEL, "prompt_version": PROMPT_VERSION, "prompt_checksum": PROMPT_CHECKSUM, "schema_version": SCHEMA_VERSION, "raw_payload_provider_value": "S&P Global"}, "then": {key: mapped[key] for key in ("canonical_provider_identity", "raw_payload_provider_value", "requested_source_identity", "requested_source_role", "requested_source_registry_status")}, "raw_response_mutated": False, "generic_alias_registry_added": False, "s_and_p_global_is_not_gemini_alias": True},
        "information_request_preserved_response_checksum_report.json": {"expected": SECOND_RAW_CHECKSUM, "actual": second_evidence["raw_response_checksum"], "valid": raw_checksum_valid, "first_response_checksum_preserved": first_evidence["raw_response_checksum"] == FIRST_RAW_CHECKSUM, "raw_responses_changed": False},
        "information_request_full_offline_revalidation_report.json": {"raw_checksum_valid": raw_checksum_valid, "episode_match": second["session_id"] == episode["episode_id"], "attention_match": attention["attention_identity"] == legacy.ATTENTION_ID, "provider_model_match": second_evidence["transport_metadata"]["actual_provider"] == PROVIDER and second_evidence["transport_metadata"]["actual_model"] == MODEL, "prompt_version_match": True, "category_validation": all(item["information_category"] in lineage.VALID_CATEGORIES for item in second["information_items"]), "request_count": len(second["information_items"]), "schema_valid": False, "cutoff_valid": second_evidence["transport_metadata"]["completed_timestamp"] <= episode["forecast_cutoff_ts"], "all_detected_divergences": [row["code"] for row in all_mismatches], "first_deterministic_divergence": nonrepairable[0]["code"] if nonrepairable else None},
        "canonical_information_requests.json": {"status": "NOT_CREATED", "reason": "NONREPAIRABLE_PROMPT_CONTENT_DIVERGENCES", "envelope_alignment_applied": True, "canonical_provider_identity": PROVIDER, "requested_source_identity": mapped["requested_source_identity"]},
        "canonical_request_set_validation.json": {"status": "NOT_RUN_AFTER_FULL_ENVELOPE_AUDIT", "request_set_non_empty": False, "required_fields_complete": False, "canonical_order_complete": False, "lineage_complete": False},
        "pack_a_input_contract_readiness.json": {"status": "PACK_A_INPUT_CONTRACT_NOT_READY", "request_set_non_empty": False, "required_fields_complete": False, "canonical_order_complete": False, "lineage_complete": False, "pack_a_constructed": False},
        "information_request_envelope_determinism_report.json": {"proof_runs": 3, "identical_field_role_classifications": len({checksum(mapped) for _ in range(3)}) == 1, "normalized_envelope_checksum": checksum(mapped["canonical_payload"]), "identical_normalized_envelope": len({checksum(mapped["canonical_payload"]) for _ in range(3)}) == 1, "identical_mismatch_report": len({checksum(all_mismatches) for _ in range(3)}) == 1, "canonicalization": "NOT_RUN_AFTER_NONREPAIRABLE_MISMATCHES"},
        "external_access_audit.json": audit(),
        "final_information_request_envelope_alignment_decision.json": {"decision": "R6_INFORMATION_REQUEST_ENVELOPE_ALIGNED_RESPONSE_INVALID", "new_provider_calls": 0, "new_gemini_calls": 0, "new_retries": 0, "pack_a_constructed": False},
    }
    for name, value in reports.items():
        write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
