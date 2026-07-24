"""Execute exactly one authorized R6 Information-Request call using the aligned prompt."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_information_request_prompt_schema_alignment_v1 as alignment
from automation import run_presignal_v21_r6_information_request_execution_v1 as legacy
from automation import run_presignal_v21_r6_native_attention_execution_v1 as attention_execution


OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_repaired_information_request_execution" / "R6-REPAIRED-INFORMATION-REQUEST-EXECUTION-20260724-v1"
ALIGNMENT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_prompt_schema_alignment" / "INFORMATION-REQUEST-PROMPT-SCHEMA-ALIGNMENT-20260723-v1"
AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_REPAIRED_INFORMATION_REQUEST_CALL_AUTHORIZATION_V1"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
R6_V3 = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
SELECTION = "sha256:73e8fe3f89126d9129ef6bcbbaeedeaf79d9f148d367248f9dcc778b307827e1"
ALIGNMENT_FINGERPRINT = "sha256:7ee8ca2ee7d59a79d99919c3a401e19be7b2e9b2aa48f1304ed8211cf2aa59fe"
PROMPT_CHECKSUM = "sha256:1bfa4b3a255292f404411d4053c6aa0eed7a7567500280c35e0bf3d55ebc02e7"
CATEGORY_ENUM_CHECKSUM = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52"
PROVIDER, MODEL, RESPONSE_SCHEMA_VERSION = "Gemini", "gemini-2.5-flash-lite", "v0"


class RepairedRequestExecutionError(ValueError):
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def authorization_manifest(*, episode: Mapping[str, Any], attention: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "authorization_name": AUTHORIZATION_NAME, "schema_version": "1",
        "route_b_freeze_fingerprint": ROUTE_B_FREEZE, "r6_authorization_v3_fingerprint": R6_V3,
        "episode_selection_authorization_fingerprint": SELECTION,
        "episode_identity": episode["episode_id"], "episode_checksum": attention_execution.EXPECTED_EPISODE_CHECKSUM,
        "attention_identity": attention["attention_identity"], "attention_content_checksum": legacy.ATTENTION_CONTENT,
        "attention_provenance_checksum": legacy.ATTENTION_PROVENANCE, "attention_lineage_checksum": legacy.ATTENTION_LINEAGE,
        "prompt_schema_alignment_fingerprint": ALIGNMENT_FINGERPRINT, "prompt_version": lineage.REQUEST_PROMPT_VERSION,
        "prompt_template_checksum": PROMPT_CHECKSUM, "category_enum_checksum": CATEGORY_ENUM_CHECKSUM,
        "response_schema_version": RESPONSE_SCHEMA_VERSION, "provider": PROVIDER, "model": MODEL,
        "information_request_call_budget": 1, "retry_count": 0,
        "prohibitions": {"attention_calls": 0, "forecast_calls": 0, "acquisition_calls": 0, "google_reads": 0, "google_writes": 0, "pack_a_constructions": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "failure_stop_policy": ["authorization_mismatch", "cutoff_closed", "provider_model_mismatch", "invalid_category", "request_response_invalid", "request_response_empty", "canonicalization_failed", "no_retry"],
    }


def validate_bindings(*, episode: Mapping[str, Any], attention: Mapping[str, Any], pre: Mapping[str, Any]) -> dict[str, Any]:
    alignment_fp = read(ALIGNMENT / "information_request_prompt_schema_alignment_fingerprint.json")
    alignment_manifest = read(ALIGNMENT / "information_request_prompt_schema_alignment_manifest.json")
    checks = {
        "route_b_freeze_valid": ROUTE_B_FREEZE == legacy.ROUTE_B_FREEZE,
        "r6_authorization_v3_valid": R6_V3 == legacy.R6_V3,
        "episode_selection_authorization_valid": SELECTION == legacy.SELECTION_FINGERPRINT,
        "episode_checksum_valid": attention_execution.EXPECTED_EPISODE_CHECKSUM == "sha256:64cca8b9d148fe795ef154273be8b12f0f405ee09e1308c5dfc1d246933a77f1",
        "attention_identity_valid": attention["attention_identity"] == legacy.ATTENTION_ID,
        "attention_checksums_valid": legacy.checksum(attention) == legacy.ATTENTION_CONTENT and attention["provenance_checksum"] == legacy.ATTENTION_PROVENANCE and attention["lineage_checksum"] == legacy.ATTENTION_LINEAGE,
        "attention_state_valid": attention["selection_state"] == "SELECTED_FOR_INFORMATION_REQUESTS" and attention["acceptance_state"] == "ACCEPTED",
        "alignment_fingerprint_valid": alignment_fp["alignment_fingerprint"] == ALIGNMENT_FINGERPRINT and alignment_manifest["alignment_name"] == alignment.ALIGNMENT_NAME,
        "prompt_version_valid": lineage.REQUEST_PROMPT_VERSION == "presignal_v21_information_request_prompt_v1" == legacy.PROMPT_VERSION,
        "prompt_template_checksum_valid": checksum(lineage.REQUEST_INSTRUCTION) == PROMPT_CHECKSUM == pre["prompt_template_checksum"],
        "category_enum_checksum_valid": checksum(sorted(lineage.VALID_CATEGORIES)) == CATEGORY_ENUM_CHECKSUM,
        "response_schema_version_valid": RESPONSE_SCHEMA_VERSION == alignment_manifest["response_schema_version"],
        "response_schema_checksum_valid": pre["response_schema_checksum"] == checksum({"object": "session_information_requirements", "schema_version": RESPONSE_SCHEMA_VERSION, "categories": sorted(lineage.VALID_CATEGORIES), "priorities": sorted(lineage.VALID_PRIORITIES), "channels": sorted(lineage.VALID_CHANNELS)}),
        "provider_model_valid": PROVIDER == legacy.PROVIDER and MODEL == legacy.MODEL,
        "call_budget_valid": True, "retry_count_valid": True,
        "episode_identity": episode["episode_id"], "attention_identity": attention["attention_identity"],
    }
    if not all(value for key, value in checks.items() if key.endswith("_valid")):
        raise RepairedRequestExecutionError("R6_REPAIRED_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH")
    return checks


def audit() -> dict[str, int]:
    return {
        "gemini_repaired_information_request_calls": 0, "gemini_attention_calls": 0, "other_provider_calls": 0,
        "forecast_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0,
        "pack_a_constructions": 0, "pack_e_computations": 0, "google_reads": 0, "google_writes": 0,
        "apps_script_executions": 0, "r6_evidence_writes": 0, "historical_mutations": 0,
        "outcome_operations": 0, "evaluation_operations": 0,
    }


def normalize_and_validate(*, episode: Mapping[str, Any], attention: Mapping[str, Any], raw_response: Any, transport: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, report = legacy.validate_and_compute(episode=episode, attention=attention, raw_response=raw_response, transport=transport)
    parsed = json.loads(raw_response) if isinstance(raw_response, str) else dict(raw_response)
    report.update({
        "prompt_version_match": True, "raw_categories": [item.get("information_category") for item in parsed["information_items"]],
        "canonical_categories": [row["information_category"] for row in rows],
        "requested_sources": [row.get("suggested_source") for row in rows],
        "raw_response_checksum": checksum(raw_response),
    })
    return rows, report


def not_executed_reports(*, authorization: Mapping[str, Any], authorization_fingerprint: str, validation: Mapping[str, Any], cutoff: Mapping[str, Any], decision: str, audit_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "repaired_information_request_call_authorization.json": authorization,
        "repaired_information_request_call_authorization_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fingerprint, "reproducible": checksum(authorization) == authorization_fingerprint},
        "repaired_information_request_authorization_validation.json": validation,
        "repaired_information_request_cutoff_revalidation.json": cutoff,
        **{name: {"status": "NOT_EXECUTED", "reason": decision} for name in ("repaired_information_request_pre_call_manifest.json", "repaired_information_request_provider_request.json", "repaired_information_request_raw_response.json", "repaired_information_request_normalized_response.json", "canonical_information_requests.json", "canonical_request_validation_report.json", "canonical_request_determinism_report.json")},
        "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0},
        "external_access_audit.json": audit_report,
        "final_repaired_information_request_decision.json": {"decision": decision, "call_attempted": False, "call_count": 0},
    }


def run(*, output: Path = OUTPUT, dispatch: bool = False, at_utc: str | None = None) -> int:
    state = audit()
    try:
        episode, members, attention, raw_attention = legacy.load_inputs()
        now = at_utc or utc_now()
        pre = legacy.build_pre_call(episode=episode, members=members, attention=attention, raw_attention=raw_attention, at_utc=now)
        validation = validate_bindings(episode=episode, attention=attention, pre=pre)
        authorization = authorization_manifest(episode=episode, attention=attention)
        authorization_fingerprint = checksum(authorization)
        cutoff = {"current_utc": now, "release_time": episode["release_ts"], "forecast_cutoff": episode["forecast_cutoff_ts"], "attention_effective_timestamp": attention["effective_timestamp"], "episode_cutoff_lineage": episode["forecast_cutoff_ts"], "attention_cutoff_lineage": attention["forecast_cutoff"], "cutoff_open": parse_utc(now) < parse_utc(episode["forecast_cutoff_ts"]), "call_permitted": parse_utc(now) < parse_utc(episode["forecast_cutoff_ts"])}
        if not cutoff["cutoff_open"]:
            reports = not_executed_reports(authorization=authorization, authorization_fingerprint=authorization_fingerprint, validation={"status": "PASS", **validation}, cutoff=cutoff, decision="R6_REPAIRED_INFORMATION_REQUEST_EXECUTION_BLOCKED_CUTOFF_CLOSED", audit_report=state)
        else:
            if not dispatch:
                raise RepairedRequestExecutionError("DISPATCH_FLAG_REQUIRED")
            pre_manifest = {"authorization_identity": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fingerprint, "episode_identity": episode["episode_id"], "episode_checksum": attention_execution.EXPECTED_EPISODE_CHECKSUM, "attention_identity": attention["attention_identity"], "attention_content_checksum": legacy.ATTENTION_CONTENT, "attention_provenance_checksum": legacy.ATTENTION_PROVENANCE, "attention_lineage_checksum": legacy.ATTENTION_LINEAGE, "alignment_fingerprint": ALIGNMENT_FINGERPRINT, "prompt_version": lineage.REQUEST_PROMPT_VERSION, "prompt_template_checksum": pre["prompt_template_checksum"], "resolved_prompt_checksum": pre["resolved_prompt_checksum"], "category_enum_checksum": CATEGORY_ENUM_CHECKSUM, "response_schema_version": RESPONSE_SCHEMA_VERSION, "response_schema_checksum": pre["response_schema_checksum"], "provider": PROVIDER, "model": MODEL, "provider_call_parameters_checksum": pre["provider_call_parameters_checksum"], "call_sequence_number": 1, "retry_count": 0, "cutoff_validation": cutoff}
            state["gemini_repaired_information_request_calls"] = 1
            response = attention_execution._dispatch(pre["bridge_request"], Path("/Users/junhoshino/projects/presignal/local/token.json"))
            raw = response.get("raw_output")
            base = {"repaired_information_request_call_authorization.json": authorization, "repaired_information_request_call_authorization_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": authorization_fingerprint, "reproducible": checksum(authorization) == authorization_fingerprint}, "repaired_information_request_authorization_validation.json": {"status": "PASS", **validation}, "repaired_information_request_cutoff_revalidation.json": cutoff, "repaired_information_request_pre_call_manifest.json": pre_manifest, "repaired_information_request_provider_request.json": pre["bridge_request"], "repaired_information_request_raw_response.json": {"raw_response": raw, "raw_response_checksum": checksum(raw), "transport_metadata": {key: response.get(key) for key in ("status", "requested_provider", "requested_model", "actual_provider", "actual_model", "started_timestamp", "completed_timestamp", "request_status", "response_status", "terminal_status", "request_id", "prompt_tokens", "completion_tokens", "stop_reason", "error")}}}
            try:
                if response.get("status") != "ok":
                    raise RepairedRequestExecutionError("REQUEST_TRANSPORT_FAILURE")
                rows, report = normalize_and_validate(episode=episode, attention=attention, raw_response=raw, transport=response)
                repeated = [normalize_and_validate(episode=episode, attention=attention, raw_response=raw, transport=response)[0] for _ in range(3)]
                stable = len({checksum(value) for value in repeated}) == 1
                base.update({"repaired_information_request_normalized_response.json": {"canonical_provider_identity": PROVIDER, "transport_model_identity": MODEL, "raw_response_checksum": checksum(raw)}, "canonical_information_requests.json": {"requests": rows, "request_set_checksum": report["request_set_checksum"]}, "canonical_request_validation_report.json": report, "canonical_request_determinism_report.json": {"proof_runs": 3, "identical_runs": stable, "request_set_checksum": report["request_set_checksum"], "request_identities": report["request_identities"]}, "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": state, "final_repaired_information_request_decision.json": {"decision": "R6_REPAIRED_INFORMATION_REQUESTS_VALIDATED_PACK_A_MATERIALIZATION_READY", "call_attempted": True, "call_count": 1, "episode_identity": episode["episode_id"], "attention_identity": attention["attention_identity"]}})
            except Exception as exc:
                reason = str(exc)
                decision = "R6_REPAIRED_INFORMATION_REQUEST_RESPONSE_EMPTY" if reason == "REQUEST_RESPONSE_EMPTY" else "R6_REPAIRED_INFORMATION_REQUEST_CALL_FAILED"
                base.update({"repaired_information_request_normalized_response.json": {"status": "INVALID", "reason": reason}, "canonical_information_requests.json": {"status": "NOT_CREATED", "reason": reason}, "canonical_request_validation_report.json": {"schema_valid": False, "empty_response": reason == "REQUEST_RESPONSE_EMPTY", "next_validation_divergence": reason}, "canonical_request_determinism_report.json": {"status": "NOT_EXECUTED_INVALID_RESPONSE", "proof_runs": 0}, "provider_call_budget_report.json": {"calls_used": 1, "calls_remaining": 0, "retry_budget_remaining": 0}, "external_access_audit.json": state, "final_repaired_information_request_decision.json": {"decision": decision, "call_attempted": True, "call_count": 1, "failure": reason}})
            reports = base
    except Exception as exc:
        reports = {"repaired_information_request_call_authorization.json": {"status": "NOT_EXECUTED"}, "repaired_information_request_call_authorization_fingerprint.json": {"status": "NOT_EXECUTED"}, "repaired_information_request_authorization_validation.json": {"status": "FAILED", "reason": str(exc)}, "repaired_information_request_cutoff_revalidation.json": {"status": "NOT_EXECUTED"}, **{name: {"status": "NOT_EXECUTED"} for name in ("repaired_information_request_pre_call_manifest.json", "repaired_information_request_provider_request.json", "repaired_information_request_raw_response.json", "repaired_information_request_normalized_response.json", "canonical_information_requests.json", "canonical_request_validation_report.json", "canonical_request_determinism_report.json")}, "provider_call_budget_report.json": {"calls_used": 0, "calls_remaining": 1, "retry_budget_remaining": 0}, "external_access_audit.json": state, "final_repaired_information_request_decision.json": {"decision": "R6_REPAIRED_INFORMATION_REQUEST_EXECUTION_BLOCKED_AUTHORIZATION_MISMATCH", "call_attempted": False, "call_count": 0, "failure": str(exc)}}
    for name, value in reports.items():
        write(output / name, value)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--at-utc")
    args = parser.parse_args()
    return run(output=args.output, dispatch=args.dispatch, at_utc=args.at_utc)


if __name__ == "__main__":
    raise SystemExit(main())
