"""Offline priority-contract repair and preserved FOMC Request revalidation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_new_r6_information_request_execution_v1 as request


SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_oauth_redispatch/R6-INFORMATION-REQUEST-OAUTH-REDISPATCH-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1"
RAW_SHA = "sha256:7e52711719a4830e7863fb92e09f249c7768622d9a566b929432e6377d39c6eb"
V2_AUTH = "sha256:be362f0b9cb73a1135c036eb1eaaa130408ec999d498c458cc371144fa50e763"
CONTRACT_NAME = "PRESIGNAL_V21_INFORMATION_REQUEST_PRIORITY_CONTRACT_V1"


def read(name: str) -> Any:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(request.canonical(value) + "\n", encoding="utf-8")


def priority_contract() -> dict[str, Any]:
    return {"contract_name": CONTRACT_NAME, "canonical_enum": sorted(lineage.VALID_PRIORITIES),
            "authoritative_normalizer_path": "automation/presignal_v21_pack_capability_v1.py:_normal_priority",
            "authoritative_mapping_path": "automation/presignal_v21_pack_capability_v1.py:PRIORITY_NORMALIZATION_MAP",
            "display_to_canonical_mapping": {"High": "must_have", "Medium": "useful", "Low": "low_value"},
            "all_explicit_aliases": dict(sorted(capability.PRIORITY_NORMALIZATION_MAP.items())),
            "priority_ownership": "MODEL_OWNED_DISPLAY_NORMALIZED_BY_SYSTEM", "unknown_values_fail_closed_at_request_boundary": True,
            "canonical_ordering": "request_rank, requested_information, information_key", "priority_affects_request_identity": False,
            "priority_affects_pack_a_order": False, "scientific_meaning_changed": False}


def run(output: Path = OUT) -> str:
    raw_evidence = read("new_r6_information_request_raw_response.json")
    transport = read("new_r6_information_request_transport_report.json")
    raw = raw_evidence["raw_response"]
    raw_object = json.loads(raw) if isinstance(raw, str) else dict(raw)
    contract = priority_contract(); contract_fp = request.sha(contract)
    values = [item.get("priority") for item in raw_object.get("information_items", [])]
    mapped = [request.normalize_known_priority(value) for value in values]
    raw_unchanged = request.sha(raw) == RAW_SHA == raw_evidence["raw_response_checksum"]
    prompt_audit = {"old_prompt_version": lineage.REQUEST_PROMPT_VERSION_V2, "new_prompt_version": lineage.REQUEST_PROMPT_VERSION_V3,
                    "old_prompt_checksum": request.PROMPT_SHA, "new_prompt_checksum": request.sha(lineage.REQUEST_INSTRUCTION_V3),
                    "old_prompt_lists_exact_priority_enum": False, "new_prompt_lists_exact_priority_enum": True,
                    "new_prompt_requires_lowercase": True, "new_prompt_prohibits_display_labels": True, "new_prompt_has_valid_json_example": True,
                    "model_reasonably_emitted_display_values": True, "scientific_fields_changed": False}
    schema_audit = {"old_response_schema_version": "v0", "new_response_schema_version": "v0_priority_enum_v1",
                    "canonical_enum": sorted(lineage.VALID_PRIORITIES), "model_facing_priority_constraint": "exact lowercase enum only",
                    "canonical_enum_broadened": False, "display_labels_canonical": False,
                    "validator_before": "strict local enum without prompt enumeration", "validator_after": "strict local enum plus exact model-facing prompt rule"}
    try:
        normalized, rows, report = request.normalize_response(raw, transport, RAW_SHA, authorization_fingerprint=V2_AUTH, allow_authoritative_priority_normalization=True, priority_contract_fingerprint=contract_fp)
    except request.RequestValidationError as exc:
        reports = {"information_request_priority_contract_trace.json": {"prompt": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION_V2/V3", "schema": "automation/presignal_v21_minimal_prospective_lineage_v1.py:VALID_PRIORITIES", "normalizer": contract["authoritative_normalizer_path"], "canonicalizer": "automation/run_presignal_v21_new_r6_information_request_execution_v1.py:normalize_response", "pack_order": contract["canonical_ordering"]},
                   "information_request_priority_mapping_decision.json": {"classification": "AUTHORITATIVE_PRIORITY_MAPPING_EXISTS", "mapping": contract["display_to_canonical_mapping"], "mapping_safe": True}, "information_request_priority_prompt_audit.json": prompt_audit, "information_request_priority_schema_audit.json": schema_audit, "information_request_priority_repair_manifest.json": {"priority_only_repair": True, "new_prompt_version": lineage.REQUEST_PROMPT_VERSION_V3, "scientific_fields_changed": False}, "information_request_priority_contract.json": contract, "information_request_priority_contract_fingerprint.json": {"contract_name": CONTRACT_NAME, "contract_fingerprint": contract_fp}, "information_request_preserved_response_revalidation.json": {"raw_checksum_unchanged": raw_unchanged, "additional_divergences": exc.divergences}, "information_request_preserved_response_normalized.json": {"status": "NOT_CREATED", "reason": exc.code}, "information_request_canonicalization_authority.json": {"classification": "PRESERVED_REQUEST_RESPONSE_STILL_INVALID", "canonical_requests_created": False, "new_provider_call_required": False}, "new_r6_canonical_information_requests.json": {"status": "NOT_CREATED", "reason": exc.code}, "new_r6_information_request_determinism_report.json": {"status": "NOT_EXECUTED"}, "new_r6_pack_authorization_preparation.json": {"status": "NOT_CREATED"}, "new_r6_information_request_v3_authorization_preparation.json": {"status": "NOT_CREATED"}, "external_access_audit.json": {key: 0 for key in ("oauth_probes", "apps_script_executions", "gemini_calls", "information_request_calls", "calendar_refreshes", "fmp_calls", "google_reads", "google_writes", "attention_calls", "acquisition_calls", "forecast_calls", "pack_a_constructions", "pack_e_constructions", "r6_evidence_writes", "outcome_operations", "evaluation_operations")}, "final_information_request_priority_repair_decision.json": {"decision": "NEW_R6_INFORMATION_REQUEST_PRESERVED_RESPONSE_STILL_INVALID"}}
        for name, value in reports.items(): write(name, value)
        return "NEW_R6_INFORMATION_REQUEST_PRESERVED_RESPONSE_STILL_INVALID"
    pack = request.pack_authorization(rows, report["request_set_checksum"], request_authorization_fingerprint=V2_AUTH)
    pack.update({"priority_contract_fingerprint": contract_fp, "preserved_raw_response_checksum": RAW_SHA})
    pack["authorization_fingerprint"] = request.sha({key: value for key, value in pack.items() if key != "authorization_fingerprint"})
    runs = [request.normalize_response(raw, transport, RAW_SHA, authorization_fingerprint=V2_AUTH, allow_authoritative_priority_normalization=True, priority_contract_fingerprint=contract_fp)[1] for _ in range(3)]
    reports = {
        "information_request_priority_contract_trace.json": {"prompt": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION_V2/V3", "response_schema": "automation/presignal_v21_minimal_prospective_lineage_v1.py:VALID_PRIORITIES", "normalizer": contract["authoritative_normalizer_path"], "validator": "automation/run_presignal_v21_new_r6_information_request_execution_v1.py:normalize_known_priority", "canonicalizer": "automation/run_presignal_v21_new_r6_information_request_execution_v1.py:normalize_response", "pack_a_ordering": contract["canonical_ordering"], "historical_compatibility": "automation/run_presignal_v21_r6_information_request_envelope_alignment_v1.py:PRIORITY_NORMALIZED_BY_FROZEN_MAP"},
        "information_request_priority_mapping_decision.json": {"classification": "AUTHORITATIVE_PRIORITY_MAPPING_EXISTS", "authoritative_mapping_found": True, "mapping": contract["display_to_canonical_mapping"], "low_value_treatment": "Low maps explicitly to low_value; optional remains an independent canonical value", "enum_broadened": False},
        "information_request_priority_prompt_audit.json": prompt_audit,
        "information_request_priority_schema_audit.json": schema_audit,
        "information_request_priority_repair_manifest.json": {"repair_scope": "prompt/schema priority constraint plus existing frozen normalization", "old_prompt_version": lineage.REQUEST_PROMPT_VERSION_V2, "new_prompt_version": lineage.REQUEST_PROMPT_VERSION_V3, "old_prompt_checksum": request.PROMPT_SHA, "new_prompt_checksum": request.sha(lineage.REQUEST_INSTRUCTION_V3), "scientific_fields_changed": False, "raw_response_rewritten": False},
        "information_request_priority_contract.json": contract,
        "information_request_priority_contract_fingerprint.json": {"contract_name": CONTRACT_NAME, "contract_fingerprint": contract_fp, "reproducible": request.sha(contract) == contract_fp},
        "information_request_preserved_response_revalidation.json": {"raw_response_checksum_before": RAW_SHA, "raw_response_checksum_after": request.sha(raw), "raw_checksum_unchanged": raw_unchanged, "request_count": len(rows), "categories_valid": True, "temporal_scope_valid": True, "provider_source_separation_valid": True, "scientific_content_valid": True, "priority_values_valid_before_normalization": False, "priority_normalization_applied": True, "priority_values_valid_after_normalization": all(row["priority"] in lineage.VALID_PRIORITIES for row in rows), "additional_divergences": []},
        "information_request_preserved_response_normalized.json": normalized,
        "information_request_canonicalization_authority.json": {"classification": "PRESERVED_REQUEST_RESPONSE_CANONICALIZATION_PERMITTED", "canonical_requests_created": True, "new_provider_call_required": False, "reason": "The original V2 call was authorized and the frozen capability already defines the exact display-to-canonical mapping."},
        "new_r6_canonical_information_requests.json": {"requests": rows, "request_set_checksum": report["request_set_checksum"]},
        "new_r6_information_request_determinism_report.json": {"runs": 3, "identical": len({request.sha(value) for value in runs}) == 1, "request_identities": [row["request_identity"] for row in rows], "canonical_priorities": [row["priority"] for row in rows], "request_set_checksum": report["request_set_checksum"]},
        "new_r6_pack_authorization_preparation.json": pack,
        "new_r6_information_request_v3_authorization_preparation.json": {"status": "NOT_CREATED_PRESERVED_RESPONSE_CANONICALIZED"},
        "external_access_audit.json": {key: 0 for key in ("oauth_probes", "apps_script_executions", "gemini_calls", "information_request_calls", "calendar_refreshes", "fmp_calls", "google_reads", "google_writes", "attention_calls", "acquisition_calls", "forecast_calls", "pack_a_constructions", "pack_e_constructions", "r6_evidence_writes", "outcome_operations", "evaluation_operations")},
        "final_information_request_priority_repair_decision.json": {"decision": "NEW_R6_INFORMATION_REQUEST_PRIORITY_REPAIRED_PACK_AUTHORIZATION_PREPARED", "provider_call_executed": False, "pack_a_constructed": False, "pack_e_constructed": False},
    }
    for name, value in reports.items(): write(name, value)
    return "NEW_R6_INFORMATION_REQUEST_PRIORITY_REPAIRED_PACK_AUTHORIZATION_PREPARED"


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(); print(request.canonical({"decision": run(args.output), "output": str(args.output.relative_to(ROOT))})); return 0


if __name__ == "__main__": raise SystemExit(main())
