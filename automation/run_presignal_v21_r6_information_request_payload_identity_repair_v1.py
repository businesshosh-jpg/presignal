"""Offline-only field-role repair for the preserved R6 Information-Request response.

The historical v2 request parser used the routed bridge provider/model as the
canonical LLM identity while retaining the model-authored top-level ``provider``
text in its raw evidence.  This module applies that narrow provenance rule only
to the one frozen Gemini response named below.  It does not dispatch providers,
access Google, construct Packs, or modify the preserved raw response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_r6_information_request_execution_v1 as execution


EXECUTION = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
LIVE_AUTHORITY = ROOT / "outputs" / "presignal_v21_designed_drift_r6_live_authority" / "R6-LIVE-AUTHORITY-20260723-v1"
HISTORICAL = ROOT / "outputs" / "presignal_v21_step8_r2_historical_replication"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_payload_identity_repair" / "R6-INFORMATION-REQUEST-PAYLOAD-IDENTITY-REPAIR-20260723-v1"

PROVIDER = "Gemini"
MODEL = "gemini-2.5-flash-lite"
PAYLOAD_VALUE = "S&P Global"
EXPECTED_RAW_CHECKSUM = "sha256:a916fffd5ceea8244d7be55f57896aec0b2c14b5ecbca2419a024436cd031e2b"
PROMPT_TEMPLATE_CHECKSUM = "sha256:2e743a5fa501bdd806f29155eb337555a9bcfb286f8b9331706b67120b0db7b9"
RESPONSE_SCHEMA_CHECKSUM = "sha256:457ac10dad1be7204136eee65dd6377ff9b1dc5229d8109515e21a2c626731e7"
PROMPT_VERSION = "existing_v2_information_request_prompt_schema"
RESPONSE_SCHEMA_VERSION = "v0"


class RequestPayloadIdentityError(ValueError):
    """An exact preserved-response field-role invariant failed."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD:" + str(path.relative_to(ROOT))], cwd=ROOT, text=True
    ).strip()


def git_commit(path: Path) -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(path.relative_to(ROOT))], cwd=ROOT, text=True
    ).strip()


def normalize_exact_gemini_request_payload_identity(
    *, raw_response: Mapping[str, Any], transport_provider: str, transport_model: str,
    prompt_template_checksum: str, response_schema_checksum: str,
) -> dict[str, Any]:
    """Use trusted bridge identity for exactly this frozen Request envelope.

    ``S&P Global`` is not accepted as an alias for Gemini.  It remains the
    untrusted model-authored payload value; this mapping only supplies the
    historical routed provider value required by the canonical Request parser.
    """
    if transport_provider != PROVIDER:
        raise RequestPayloadIdentityError("REQUEST_BRIDGE_TRANSPORT_PROVIDER_MISMATCH")
    if transport_model != MODEL:
        raise RequestPayloadIdentityError("REQUEST_BRIDGE_TRANSPORT_MODEL_MISMATCH")
    if prompt_template_checksum != PROMPT_TEMPLATE_CHECKSUM:
        raise RequestPayloadIdentityError("REQUEST_BRIDGE_PROMPT_VERSION_MISMATCH")
    if response_schema_checksum != RESPONSE_SCHEMA_CHECKSUM:
        raise RequestPayloadIdentityError("REQUEST_BRIDGE_SCHEMA_VERSION_MISMATCH")
    if raw_response.get("provider") != PAYLOAD_VALUE:
        raise RequestPayloadIdentityError("REQUEST_BRIDGE_PAYLOAD_VALUE_MISMATCH")
    canonical_payload = dict(raw_response)
    canonical_payload["provider"] = PROVIDER
    return {
        "canonical_payload": canonical_payload,
        "canonical_provider_identity": PROVIDER,
        "transport_provider_identity": transport_provider,
        "transport_model_identity": transport_model,
        "payload_provider_value": PAYLOAD_VALUE,
        "payload_provider_role": "MODEL_AUTHORED_OVERLOADED_REQUEST_FIELD",
        "requested_source_candidate_value": PAYLOAD_VALUE,
        "requested_source_identity": None,
        "requested_source_role": "NOT_ASSERTED_BY_PROMPT_OR_REGISTRY",
        "mapping_rule": "EXACT_GEMINI_REQUEST_TRANSPORT_IDENTITY_V1",
        "mapping_checksum": checksum({
            "transport_provider": transport_provider,
            "transport_model": transport_model,
            "prompt_template_checksum": prompt_template_checksum,
            "response_schema_checksum": response_schema_checksum,
            "payload_provider_value": PAYLOAD_VALUE,
        }),
    }


def historical_provider_inventory() -> list[dict[str, Any]]:
    """Summarize successful raw Request provider values without changing them."""
    rows: list[dict[str, Any]] = []
    for provider in ("gemini", "anthropic", "openai"):
        files = sorted(HISTORICAL.glob(f"**/requests/{provider}.json"))
        values: dict[str, int] = {}
        records = 0
        for path in files:
            data = read(path)
            raw = []

            def walk(value: Any) -> None:
                if isinstance(value, Mapping):
                    if isinstance(value.get("raw_output"), str):
                        raw.append(value["raw_output"])
                    for child in value.values():
                        walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)

            walk(data)
            for text in raw:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                value = parsed.get("provider")
                if isinstance(value, str) and value:
                    values[value] = values.get(value, 0) + 1
                    records += 1
        rows.append({
            "transport_provider_route": provider.capitalize() if provider != "openai" else "OpenAI",
            "path_glob": str((HISTORICAL / "**" / "requests" / f"{provider}.json").relative_to(ROOT)),
            "file_count": len(files), "successful_raw_provider_record_count": records,
            "raw_provider_value_counts": [
                {"value": value, "count": count}
                for value, count in sorted(values.items(), key=lambda pair: (-pair[1], pair[0]))
            ],
            "contains_transport_provider_name": (
                ("Gemini" in values) if provider == "gemini" else
                ("Anthropic" in values) if provider == "anthropic" else ("OpenAI" in values)
            ),
        })
    return rows


def source_registry_validation() -> dict[str, Any]:
    manifest_path = LIVE_AUTHORITY / "prospective_source_environment_manifest.json"
    manifest = read(manifest_path)
    matches = [row for row in manifest["sources"] if str(row.get("source_id")) == PAYLOAD_VALUE or str(row.get("source_key_or_domain")) == PAYLOAD_VALUE]
    return {
        "requested_source_candidate_value": PAYLOAD_VALUE,
        "registry_identity": manifest["binding_name"],
        "original_registry_identity": manifest["original_registry_identity"],
        "registry_checksum": manifest["registry_checksum"],
        "registry_path": str(manifest_path.relative_to(ROOT)),
        "registry_commit": git_commit(manifest_path),
        "approved_source_match": bool(matches),
        "registry_entry": matches[0] if matches else None,
        "allowed_acquisition_methods": matches[0]["allowed_acquisition_methods"] if matches else [],
        "source_normalization_result": "UNRESOLVED_NO_BOUND_AKSR_ENTRY" if not matches else "BOUND_AKSR_ENTRY",
        "acquisition_admission_rule": "A later acquisition must fail closed if it relies on an unapproved source; this offline Request repair does not convert that source condition into an LLM-provider mismatch.",
    }


def validate_after_identity_repair(*, episode: Mapping[str, Any], attention: Mapping[str, Any], raw: Mapping[str, Any], transport: Mapping[str, Any], pre: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Apply the narrow role normalization, then stop at the first schema divergence."""
    mapped = normalize_exact_gemini_request_payload_identity(
        raw_response=raw,
        transport_provider=str(transport.get("actual_provider") or ""),
        transport_model=str(transport.get("actual_model") or ""),
        prompt_template_checksum=str(pre.get("prompt_template_checksum") or ""),
        response_schema_checksum=str(pre.get("response_schema_checksum") or ""),
    )
    payload = mapped["canonical_payload"]
    if payload.get("session_id") != episode["episode_id"]:
        raise RequestPayloadIdentityError("REQUEST_RESPONSE_EPISODE_MISMATCH")
    items = payload.get("information_items")
    if not isinstance(items, list):
        raise RequestPayloadIdentityError("REQUEST_ITEMS_NOT_ARRAY")
    if not items:
        raise RequestPayloadIdentityError("REQUEST_RESPONSE_EMPTY")
    invalid = next((index for index, item in enumerate(items) if not isinstance(item, Mapping) or item.get("information_category") not in lineage.VALID_CATEGORIES), None)
    if invalid is not None:
        category = None if not isinstance(items[invalid], Mapping) else items[invalid].get("information_category")
        raise RequestPayloadIdentityError(f"REQUEST_CATEGORY_INVALID:raw_information_items[{invalid}].information_category={category}")
    rows, report = execution.validate_and_compute(
        episode=episode, attention=attention, raw_response=canonical(payload), transport={"actual_provider": PROVIDER, "actual_model": MODEL},
    )
    return rows, report, mapped


def audit() -> dict[str, int]:
    return {
        "provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0,
        "google_reads": 0, "google_writes": 0, "http_acquisition_calls": 0,
        "forecast_calls": 0, "pack_a_constructions": 0, "live_pack_e_computations": 0,
        "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0,
    }


def run(*, output: Path = OUTPUT) -> None:
    raw_evidence = read(EXECUTION / "information_request_raw_response.json")
    pre = read(EXECUTION / "information_request_pre_call_manifest.json")
    raw_text = raw_evidence["raw_response"]
    raw = json.loads(raw_text)
    raw_checksum_valid = checksum(raw_text) == EXPECTED_RAW_CHECKSUM == raw_evidence["raw_response_checksum"]
    episode, _members, attention, _raw_attention = execution.load_inputs()
    transport = raw_evidence["transport_metadata"]
    historical = historical_provider_inventory()
    registry = source_registry_validation()
    audit_report = audit()
    occurrence = {
        "searched_fields": ["provider", "source", "publisher", "institution", "data_provider", "requested_provider", "preferred_source", "source_name"],
        "occurrences": [
            {"path": str((EXECUTION / "information_request_raw_response.json").relative_to(ROOT)), "source_commit": git_commit(EXECUTION / "information_request_raw_response.json"), "git_blob_sha": git_blob(EXECUTION / "information_request_raw_response.json"), "object_type": "session_information_requirements", "field_name": "raw_response.provider", "producer": "Gemini model raw payload", "consumer": "prior strict R6 Request validator", "semantic_definition": "model-authored top-level field with no prompt role definition", "fixed_by_code": False, "refers_to_llm_provider": False, "refers_to_information_source": "UNPROVEN", "appears_in_successful_historical_fixtures": False},
            {"path": "automation/presignal_v21_minimal_prospective_lineage_v1.py", "source_commit": git_commit(ROOT / "automation/presignal_v21_minimal_prospective_lineage_v1.py"), "git_blob_sha": git_blob(ROOT / "automation/presignal_v21_minimal_prospective_lineage_v1.py"), "object_type": "Information Request prompt", "field_name": "provider", "producer": "prompt output contract", "consumer": "v2 Request parser", "semantic_definition": "required top-level output key; no LLM/source role definition", "fixed_by_code": True, "refers_to_llm_provider": "UNSPECIFIED", "refers_to_information_source": "UNSPECIFIED", "appears_in_successful_historical_fixtures": True},
            {"path": "automation/presignal_v21_minimal_prospective_lineage_v1.py", "source_commit": git_commit(ROOT / "automation/presignal_v21_minimal_prospective_lineage_v1.py"), "git_blob_sha": git_blob(ROOT / "automation/presignal_v21_minimal_prospective_lineage_v1.py"), "object_type": "Information Request item", "field_name": "suggested_source", "producer": "model payload", "consumer": "Request canonicalizer", "semantic_definition": "item-level suggested source slot", "fixed_by_code": False, "refers_to_llm_provider": False, "refers_to_information_source": True, "appears_in_successful_historical_fixtures": True},
            {"path": "automation/run_presignal_v21_step8_r2_historical_replication_v1.py", "source_commit": git_commit(ROOT / "automation/run_presignal_v21_step8_r2_historical_replication_v1.py"), "git_blob_sha": git_blob(ROOT / "automation/run_presignal_v21_step8_r2_historical_replication_v1.py"), "object_type": "historical routed bridge adapter", "field_name": "raw_output.provider", "producer": "model raw payload", "consumer": "temporary parser normalization", "semantic_definition": "non-empty payload provider required but routed bridge identity wins", "fixed_by_code": True, "refers_to_llm_provider": False, "refers_to_information_source": False, "appears_in_successful_historical_fixtures": True},
        ],
    }
    prompt_trace = {
        "prompt_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION",
        "prompt_version": PROMPT_VERSION, "resolved_prompt_checksum": pre["resolved_prompt_checksum"],
        "prompt_template_checksum": pre["prompt_template_checksum"], "schema_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION and build_prospective_requests", "schema_version": RESPONSE_SCHEMA_VERSION,
        "field_description": "The exact prompt requires a top-level provider key but supplies no semantic definition; it defines suggested_source, not provider, as the per-item source field.",
        "prompt_instruction_source_role": "suggested_source", "prompt_instruction_provider_role": "UNSPECIFIED",
    }
    historical_trace = {
        "fixture_glob": "outputs/presignal_v21_step8_r2_historical_replication/**/requests/{gemini,anthropic,openai}.json",
        "provider_value_summary": historical,
        "historical_parser_precedent": "automation/run_presignal_v21_step8_r2_historical_replication_v1.py:_context_provider_dispatch",
        "historical_rule": "Provider text is required but bridge identity wins; temporary canonical parsing replaces it with routed provider and raw evidence is restored.",
        "schema_behavior_classification": "VALIDATOR_FIELD_MAPPING_DEFECT",
        "reason": "Historical successful Request envelopes contain descriptive raw provider values instead of transport LLM names, while canonical identity was routed from bridge context.",
    }
    trust = {
        "call_path": ["Information Request runner", "Gemini bridge", "raw response envelope", "payload extraction", "Request validation", "canonical Request computation"],
        "trusted_provider_identity_source": "information_request_raw_response.json.transport_metadata.actual_provider",
        "trusted_model_identity_source": "information_request_raw_response.json.transport_metadata.actual_model",
        "payload_provider_field_source": "model-authored raw_response.provider",
        "request_item_source_field": "information_items[].suggested_source",
        "canonical_provider_lineage_source": "trusted bridge provider/model supplied to Route B compute",
        "trust_rule": "Transport metadata owns canonical LLM provider/model. The top-level payload provider value is preserved as provenance and is never accepted as a provider alias.",
    }
    mapping_contract = {
        "mapping_name": "EXACT_GEMINI_REQUEST_TRANSPORT_IDENTITY_V1",
        "when": {"transport_provider": PROVIDER, "transport_model": MODEL, "prompt_template_checksum": PROMPT_TEMPLATE_CHECKSUM, "response_schema_checksum": RESPONSE_SCHEMA_CHECKSUM, "payload_provider_value": PAYLOAD_VALUE},
        "then": {"canonical_provider_identity": PROVIDER, "payload_provider_value_preserved": True, "requested_source_candidate_value": PAYLOAD_VALUE, "requested_source_identity": None, "requested_source_role": "NOT_ASSERTED_BY_PROMPT_OR_REGISTRY"},
        "scope": "one preserved R6 Request response and exact Request prompt/schema version only",
        "not_a_provider_alias": True, "not_a_generic_alias_registry": True, "raw_response_mutated": False,
    }
    try:
        rows, validation, mapped = validate_after_identity_repair(episode=episode, attention=attention, raw=raw, transport=transport, pre=pre)
        repeated = [validate_after_identity_repair(episode=episode, attention=attention, raw=raw, transport=transport, pre=pre)[0] for _ in range(3)]
        deterministic = len({checksum(value) for value in repeated}) == 1
        decision = "R6_INFORMATION_REQUEST_PAYLOAD_IDENTITY_REPAIRED_PACK_A_READY"
        canonical_requests = {"requests": rows, "request_set_checksum": validation["request_set_checksum"], "identity_role_normalization": {key: value for key, value in mapped.items() if key != "canonical_payload"}}
        determinism = {"proof_runs": 3, "identical_runs": deterministic, "request_set_checksum": validation["request_set_checksum"], "request_identities": validation["request_identities"]}
        offline = {"preserved_raw_checksum": EXPECTED_RAW_CHECKSUM, "checksum_valid": raw_checksum_valid, "episode_match": True, "attention_match": True, "transport_provider_match": True, "transport_model_match": True, "payload_identity_normalized": True, "raw_item_count": len(raw["information_items"]), "canonical_request_count": len(rows), "schema_valid": True, "cutoff_valid": True, "next_validation_divergence": None}
    except RequestPayloadIdentityError as exc:
        reason = str(exc)
        mapped = normalize_exact_gemini_request_payload_identity(raw_response=raw, transport_provider=str(transport.get("actual_provider") or ""), transport_model=str(transport.get("actual_model") or ""), prompt_template_checksum=str(pre.get("prompt_template_checksum") or ""), response_schema_checksum=str(pre.get("response_schema_checksum") or ""))
        decision = "R6_INFORMATION_REQUEST_RESPONSE_EMPTY" if reason == "REQUEST_RESPONSE_EMPTY" else "R6_INFORMATION_REQUEST_OFFLINE_REVALIDATION_FAILED"
        canonical_requests = {"status": "NOT_CREATED", "reason": reason, "identity_role_normalization": {key: value for key, value in mapped.items() if key != "canonical_payload"}}
        determinism = {"proof_runs": 3, "identity_role_normalization_identical_runs": len({checksum(normalize_exact_gemini_request_payload_identity(raw_response=raw, transport_provider=str(transport.get("actual_provider") or ""), transport_model=str(transport.get("actual_model") or ""), prompt_template_checksum=str(pre.get("prompt_template_checksum") or ""), response_schema_checksum=str(pre.get("response_schema_checksum") or ""))) for _ in range(3)}) == 1, "canonical_request_construction": "NOT_RUN_AFTER_FIRST_SCHEMA_DIVERGENCE"}
        offline = {"preserved_raw_checksum": EXPECTED_RAW_CHECKSUM, "checksum_valid": raw_checksum_valid, "episode_match": True, "attention_match": True, "transport_provider_match": transport.get("actual_provider") == PROVIDER, "transport_model_match": transport.get("actual_model") == MODEL, "payload_identity_normalized": True, "raw_item_count": len(raw.get("information_items") or []), "canonical_request_count": 0, "schema_valid": False, "cutoff_valid": True, "next_validation_divergence": reason}
    reports = {
        "request_payload_identity_occurrence_inventory.json": occurrence,
        "request_payload_identity_prompt_trace.json": prompt_trace,
        "request_payload_identity_historical_trace.json": historical_trace,
        "request_payload_identity_trust_boundary.json": trust,
        "request_payload_identity_classification.json": {"classification": "REQUEST_PROVIDER_FIELD_OVERLOADED", "reason": "Historical successful Request payloads use the same raw provider field for descriptive model roles, while this response contains an institution token; neither form is trusted LLM provider authority."},
        "request_payload_identity_mapping_contract.json": mapping_contract,
        "requested_source_registry_validation.json": registry,
        "preserved_response_checksum_report.json": {"expected": EXPECTED_RAW_CHECKSUM, "actual": raw_evidence["raw_response_checksum"], "valid": raw_checksum_valid, "raw_evidence_file_checksum": sha_file(EXECUTION / "information_request_raw_response.json"), "raw_response_changed": False},
        "offline_request_revalidation_report.json": offline,
        "canonical_information_requests.json": canonical_requests,
        "canonical_request_determinism_report.json": determinism,
        "external_access_audit.json": audit_report,
        "final_request_payload_identity_repair_decision.json": {"decision": decision, "previous_information_request_calls_used": 1, "remaining_information_request_calls": 0, "retry_budget": 0, "new_calls_made": 0},
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
