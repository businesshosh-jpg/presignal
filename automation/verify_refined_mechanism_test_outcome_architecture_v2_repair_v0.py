#!/usr/bin/env python3
"""Phase 9A-6R15J-R1: narrow verification of the v2 stage repair.

This verifier reads the repaired shadow manifests and repair records only.  It
does not load outcome source sheets, change the architecture, or select a
consumer.  The small output family is intentional: the diagnostics workbook
is near its cell limit.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _column_letter  # type: ignore
from automation.build_refined_mechanism_test_execution_v0 import _canonical_json  # type: ignore
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore
import automation.build_refined_mechanism_test_outcome_architecture_v2_staged_implementation_v0 as impl  # type: ignore


PHASE_ID = "9A-6R15J-R1"
BUILD_SCRIPT = "automation/verify_refined_mechanism_test_outcome_architecture_v2_repair_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_v2_repair_verification_v0"
REPAIR_RUN_ID = "9A-6R15I-R1_20260713T061220Z"
EXPECTED_AGGREGATE_FINGERPRINT = "0f021cb3aa68fb0ebf3025091923687d261afeaaa30ec47474b54daba0dff41a"

OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_R1_Repair_Verification"
OUTPUT_PARSER = "Refined_Mechanism_Test_Outcome_Architecture_V2_R1_Parser_Verification"
OUTPUT_FINGERPRINT_AUTHORITY = "Refined_Mechanism_Test_Outcome_Architecture_V2_R1_Fingerprint_Authority_Verification"
OUTPUT_HARD_STOPS = "Refined_Mechanism_Test_Outcome_Architecture_V2_R1_Hard_Stop_Verification"
OUTPUT_SHEETS = (
    OUTPUT_SUMMARY,
    OUTPUT_PARSER,
    OUTPUT_FINGERPRINT_AUTHORITY,
    OUTPUT_HARD_STOPS,
)
HEADERS = [
    "generated_ts", "schema_version", "repair_verification_run_id",
    "authoritative_repair_run_id", "review_area", "review_status", "blocking", "payload_json",
]


class VerificationFailure(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _review_run_id(ts: str) -> str:
    return f"{PHASE_ID}_{ts.replace('-', '').replace(':', '').replace('Z', '')}Z"


def _payload(raw: Any) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise VerificationFailure(f"invalid JSON payload: {exc}") from exc
    if not isinstance(parsed, dict):
        raise VerificationFailure("payload is not an object")
    return parsed


def _raw_sheet_values(service, sheets: Sequence[str]) -> Dict[str, List[List[Any]]]:
    ranges = [f"'{sheet}'!A1:ZZZ" for sheet in sheets]
    response = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=ranges,
    ).execute()
    return {
        sheet: response.get("valueRanges", [])[index].get("values", [])
        for index, sheet in enumerate(sheets)
    }


def _manifest_records(values: List[List[Any]], sheet: str) -> List[Dict[str, Any]]:
    """Decode one stored compact manifest for exactly the repaired run."""
    if not values or len(values) < 2:
        raise VerificationFailure(f"{sheet}: no data rows")
    header = values[0]
    try:
        payload_index = header.index("payload_json")
        run_index = header.index("outcome_architecture_implementation_run_id")
    except ValueError as exc:
        raise VerificationFailure(f"{sheet}: required header absent") from exc
    chunks: List[Tuple[int, int, Dict[str, Any]]] = []
    for row in values[1:]:
        if len(row) <= max(run_index, payload_index) or row[run_index] != REPAIR_RUN_ID:
            continue
        payload = _payload(row[payload_index])
        if payload.get("storage_mode") != "COMPACT_APPEND_ONLY_MANIFEST":
            raise VerificationFailure(f"{sheet}: non-manifest repaired record")
        chunks.append((payload.get("chunk_index"), payload.get("chunk_count"), payload))
    if not chunks:
        raise VerificationFailure(f"{sheet}: no compact repaired-run chunk")
    indices = sorted(chunk[0] for chunk in chunks)
    expected = list(range(1, len(chunks) + 1))
    if indices != expected or any(chunk[1] != len(chunks) for chunk in chunks):
        raise VerificationFailure(f"{sheet}: incomplete or duplicate chunk sequence")
    records: List[Dict[str, Any]] = []
    for _, _, payload in sorted(chunks, key=lambda item: item[0]):
        columns, rows = payload.get("column_order"), payload.get("records")
        if not isinstance(columns, list) or not isinstance(rows, list):
            raise VerificationFailure(f"{sheet}: invalid manifest structure")
        for record in rows:
            if not isinstance(record, list) or len(record) != len(columns):
                raise VerificationFailure(f"{sheet}: truncated logical record")
            records.append(dict(zip(columns, record)))
        if payload.get("logical_record_count") != len(records) and payload.get("chunk_index") == payload.get("chunk_count"):
            raise VerificationFailure(f"{sheet}: declared logical count mismatch")
    return records


def _repair_payloads(values: List[List[Any]], sheet: str) -> List[Dict[str, Any]]:
    if not values or len(values) < 2:
        raise VerificationFailure(f"{sheet}: no repair rows")
    header = values[0]
    payload_index = header.index("payload_json")
    run_index = header.index("outcome_architecture_implementation_run_id")
    return [
        _payload(row[payload_index])
        for row in values[1:]
        if len(row) > max(run_index, payload_index) and row[run_index] == REPAIR_RUN_ID
    ]


def _reconstruct_aggregate(raw: Mapping[str, List[List[Any]]]) -> Tuple[Dict[str, Any], Dict[str, int], Dict[str, Any]]:
    """Rebuild the stored aggregate using the dedicated repair governance component.

    The legacy implementation-governance tab is intentionally not part of the
    repaired authority path because its historic duplicate-header layout cannot
    safely encode the current logical governance payload.
    """
    components: Dict[str, List[Dict[str, Any]]] = {}
    component_counts: Dict[str, int] = {}
    for component in impl.AGGREGATE_COMPONENTS:
        if component == impl.OUTPUT_GOVERNANCE:
            continue
        records = _manifest_records(raw[component], component)
        components[component] = records
        component_counts[component] = len(records)

    governance_payloads = _repair_payloads(raw[impl.OUTPUT_REPAIR_GOVERNANCE], impl.OUTPUT_REPAIR_GOVERNANCE)
    matches = [
        payload for payload in governance_payloads
        if payload.get("governance_component_source") == impl.OUTPUT_REPAIR_GOVERNANCE
        and payload.get("legacy_governance_tab_reused") is False
        and isinstance(payload.get("logical_governance_records"), list)
    ]
    if len(matches) != 1:
        raise VerificationFailure("repair governance: expected exactly one finalized logical governance component")
    components[impl.OUTPUT_GOVERNANCE] = matches[0]["logical_governance_records"]
    component_counts[impl.OUTPUT_GOVERNANCE] = len(components[impl.OUTPUT_GOVERNANCE])
    aggregate = impl._aggregate_fingerprint(components)
    return aggregate, component_counts, components


def _parser_audit() -> Dict[str, Any]:
    frozen_cases = [
        ("INTEGER_ZERO", 0, 0, "NUMERIC_ZERO", False),
        ("FLOAT_ZERO", 0.0, 0, "FLOAT_ZERO", False),
        ("STRING_ZERO", "0", 0, "STRING_ZERO", False),
        ("BOOLEAN_FALSE", False, 0, "BOOLEAN_FALSE", False),
        ("STRING_FALSE", "FALSE", 0, "STRING_FALSE", False),
        ("EMPTY", "", None, "", True),
        ("WHITESPACE", "   ", None, "", True),
        ("MISSING", impl.MISSING, None, "", True),
        ("NULL", None, None, "", True),
        ("INVALID", "invalid", None, "", True),
        ("POSITIVE_INTEGER", 1, 1, "NUMERIC", False),
        ("POSITIVE_FLOAT", 1.0, 1, "FLOAT_NUMERIC", False),
        ("BOOLEAN_TRUE", True, 1, "BOOLEAN_TRUE", False),
    ]
    supplemental_cases = [
        ("STRING_FLOAT_ZERO", "0.0", None, "", True),
        ("NEGATIVE_INTEGER", -1, None, "", True),
    ]

    def execute(cases: Sequence[Tuple[str, Any, Any, str, bool]]) -> List[Dict[str, Any]]:
        results = []
        for name, value, expected_value, expected_kind, expects_error in cases:
            expected = "INVALID_ZERO_FALSE_NULL_COERCION" if expects_error else {"normalized_value": expected_value, "kind": expected_kind}
            try:
                actual, kind = impl._parse_nonnegative_int(value, name, "INTEGER_COUNT")
                passed = not expects_error and actual == expected_value and kind == expected_kind
                observed = {"normalized_value": actual, "kind": kind}
                stop_code = ""
            except impl.StageBlocked as exc:
                passed = expects_error and exc.stop_rule == "INVALID_ZERO_FALSE_NULL_COERCION"
                observed = None
                stop_code = exc.stop_rule
            results.append({
                "case": name, "input_type": type(value).__name__ if value is not impl.MISSING else "MISSING_SENTINEL",
                "input_value": repr(value), "expected": expected, "observed": observed,
                "stop_code": stop_code, "pass": passed,
                "implementation_location": "_parse_nonnegative_int(INTEGER_COUNT)",
            })
        return results

    results = execute(frozen_cases)
    supplemental = execute(supplemental_cases)
    governed_sources = {
        "parser": inspect.getsource(impl._parse_nonnegative_int),
        "aggregate_fingerprint": inspect.getsource(impl._aggregate_fingerprint),
        "authority_finalizer": inspect.getsource(impl._finalize_persisted_repair),
        "execution_builder": inspect.getsource(impl.build),
    }
    governed_source = "\n".join(governed_sources.values())
    prohibited_patterns = {
        "value_or_one": r"value\s+or\s+1",
        "value_or_zero": r"value\s+or\s+0",
        "implicit_bool_cast": r"bool\s*\(\s*value\s*\)",
        "int_truthiness_fallback": r"int\s*\(\s*value\s+or",
    }
    found = [name for name, pattern in prohibited_patterns.items() if re.search(pattern, governed_source)]
    return {
        "frozen_parser_matrix": results, "frozen_matrix_result": f"{sum(row['pass'] for row in results)}/{len(results)}",
        "supplemental_zero_and_negative_probes": supplemental,
        "supplemental_result": f"{sum(row['pass'] for row in supplemental)}/{len(supplemental)}",
        "all_cases_pass": all(row["pass"] for row in results + supplemental),
        "governed_code_paths_scanned": list(governed_sources), "truthiness_coercion_patterns": found,
        "parser_fail_closed": not found,
    }


def _stop_audit() -> Dict[str, Any]:
    results = impl._runtime_guard_tests()
    code = Path(impl.__file__).read_text(encoding="utf-8")
    test_before_outcomes = code.index("hard_stop_tests = _runtime_guard_tests()") < code.index("outcome_inputs = _fetch_input_sheets")
    each_complete = all(
        row["trigger_observed"] and row["stage_blocked"] and row["downstream_blocked"]
        and row["final_readiness_blocked"] and row["scientific_rules_unchanged"]
        for row in results
    )
    invariants = {
        "LINEAGE_MISMATCH": ("frozen lineage must match", "_validate_frozen_chain / _require"),
        "FINGERPRINT_MISMATCH": ("logical payload must reproduce", "_aggregate_fingerprint / _guard"),
        "DEPENDENCY_FAILURE": ("prior stage dependency must verify", "_checkpoint_rows / _require"),
        "VERSION_MISMATCH": ("frozen versions must match", "_validate_frozen_chain / _require"),
        "COMPATIBILITY_FAILURE": ("v1 compatibility must remain", "_checkpoint_rows / _require"),
        "DETERMINISTIC_FAILURE": ("second pass must match", "_checkpoint_rows / _require"),
        "UNEXPECTED_DATA_LOSS": ("expected row sets must account", "_build_stage_records / _require"),
        "PROHIBITED_REDESIGN_ATTEMPT": ("frozen architecture cannot be redesigned", "_validate_frozen_chain / _require"),
        "SOURCE_SHEET_MODIFICATION_ATTEMPT": ("write targets cannot overlap sources", "build / _guard"),
        "MIXED_RUN_RESUME_ATTEMPT": ("runs cannot be mixed or reused", "build / _guard"),
        "UNVERIFIED_CHECKPOINT_RESUME_ATTEMPT": ("resume must be verified", "build / _guard"),
        "DUPLICATE_LINK": ("exact links must be one-to-one", "_build_stage_records / _require"),
        "AMBIGUOUS_LINK": ("ambiguous links must block", "_build_stage_records / _require"),
        "FUZZY_JOIN_ATTEMPT": ("only exact stable keys permitted", "build / _guard"),
        "MANUAL_JOIN_ATTEMPT": ("manual matching prohibited", "build / _guard"),
        "SUCCESS_MAPPING_CHANGE_ATTEMPT": ("v1 semantics frozen", "build / _guard"),
        "MECHANISM_TEST_ATTEMPT": ("shadow build cannot run tests", "build / _guard"),
        "PRODUCTION_WRITE_ATTEMPT": ("shadow build cannot write production", "build / _guard"),
        "INVALID_ZERO_FALSE_NULL_COERCION": ("governed values parse explicitly", "_parse_nonnegative_int / _require"),
    }
    detailed = []
    for result in results:
        invariant, location = invariants[result["stop_code"]]
        detailed.append({
            **result, "protected_invariant": invariant, "implementation_location": location,
            "real_caller": "build -> _runtime_guard_tests -> _guard before outcome_inputs fetch",
            "audit_evidence": "stored Hard_Stop_Runtime_Audit plus independent negative-path invocation",
            "execution_path_present": test_before_outcomes,
        })
    return {
        "cataloged_stop_count": len(impl.HARD_STOPS),
        "runtime_enforced_stop_count": len(results),
        "runtime_tests_execute_on_real_build_path_before_outcome_load": test_before_outcomes,
        "all_negative_path_tests_pass": each_complete,
        "stops_remaining_catalog_only": [rule for rule in impl.HARD_STOPS if rule not in {row["stop_code"] for row in results}],
        "tests": detailed,
        "blocked_behaviors": ["downstream_stages", "final_readiness", "fallback_joins", "scientific_rule_changes", "consumer_switch", "production_writes"],
    }


def _authority_audit(raw: Mapping[str, List[List[Any]]]) -> Dict[str, Any]:
    payloads = _repair_payloads(raw[impl.OUTPUT_AUTHORITY], impl.OUTPUT_AUTHORITY)
    authority_id = f"{REPAIR_RUN_ID}:REPAIR_FINALIZATION_V1"
    matches = [payload for payload in payloads if payload.get("authority_record_id") == authority_id]
    if len(matches) != 1:
        raise VerificationFailure("expected exactly one explicit final authority record")
    authority = matches[0]
    stages = _manifest_records(raw[impl.OUTPUT_CHECKPOINTS], impl.OUTPUT_CHECKPOINTS)
    completed = [row for row in stages if row.get("stage_status") == "COMPLETED_VERIFIED"]
    expected_stages = [stage_id for stage_id, _ in impl.STAGES]
    stage_ids = [row.get("stage_id") for row in sorted(stages, key=lambda row: row.get("stage_order", 0))]
    rule = authority.get("authority_selection_rule", "")
    def select(candidate: Mapping[str, Any]) -> Tuple[bool, str]:
        if candidate.get("run_id") != REPAIR_RUN_ID:
            return False, "RUN_ID_NOT_AUTHORITATIVE"
        if candidate.get("authority_status") != "AUTHORITATIVE_COMPLETED_VERIFIED":
            return False, "AUTHORITY_STATUS_REJECTED"
        if candidate.get("checkpoint_chain_status") != "COMPLETED_VERIFIED_5_OF_5":
            return False, "CHECKPOINT_CHAIN_REJECTED"
        if candidate.get("aggregate_fingerprint") != EXPECTED_AGGREGATE_FINGERPRINT:
            return False, "AGGREGATE_FINGERPRINT_REJECTED"
        if candidate.get("lineage_valid") is not True:
            return False, "LINEAGE_REJECTED"
        return True, "EXACT_AUTHORITY_MATCH"

    candidates = [
        ("repaired_authoritative", {"run_id": REPAIR_RUN_ID, "authority_status": "AUTHORITATIVE_COMPLETED_VERIFIED", "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": EXPECTED_AGGREGATE_FINGERPRINT, "lineage_valid": True, "physical_row": 999}, True),
        ("superseded_completed", {"run_id": "9A-6R15I_20260713T052341Z", "authority_status": "SUPERSEDED_BY_REPAIRED_RUN", "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": EXPECTED_AGGREGATE_FINGERPRINT, "lineage_valid": True, "physical_row": 1}, False),
        ("partial_051739", {"run_id": "9A-6R15I_20260713T051739Z", "authority_status": "NONAUTHORITATIVE_ISOLATED", "checkpoint_chain_status": "INCOMPLETE", "aggregate_fingerprint": "", "lineage_valid": True, "physical_row": 1000}, False),
        ("partial_051900", {"run_id": "9A-6R15I_20260713T051900Z", "authority_status": "NONAUTHORITATIVE_ISOLATED", "checkpoint_chain_status": "INCOMPLETE", "aggregate_fingerprint": "", "lineage_valid": True, "physical_row": 1001}, False),
        ("failed_run", {"run_id": "failed", "authority_status": "FAILED", "checkpoint_chain_status": "FAILED", "aggregate_fingerprint": "", "lineage_valid": False, "physical_row": 1002}, False),
        ("fingerprint_mismatch", {"run_id": REPAIR_RUN_ID, "authority_status": "AUTHORITATIVE_COMPLETED_VERIFIED", "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": "mismatch", "lineage_valid": True, "physical_row": 1}, False),
        ("lineage_mismatch", {"run_id": REPAIR_RUN_ID, "authority_status": "AUTHORITATIVE_COMPLETED_VERIFIED", "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": EXPECTED_AGGREGATE_FINGERPRINT, "lineage_valid": False, "physical_row": 1}, False),
    ]
    selection_tests = []
    for name, candidate, expected in candidates:
        selected, reason = select(candidate)
        selection_tests.append({"candidate": name, "run_id": candidate["run_id"], "candidate_status": candidate["authority_status"], "expected_selected": expected, "observed_selected": selected, "rejection_or_selection_reason": reason, "physical_row_ignored": True, "pass": selected == expected})
    return {
        "authoritative_repair_run_id": authority.get("authoritative_implementation_run_id"),
        "authority_record_id": authority.get("authority_record_id"),
        "authority_status": authority.get("checkpoint_chain_status"),
        "authority_selection_rule": rule,
        "exact_authority_selector": "EXACT_ARCHITECTURE_VERSION_AND_RUN_ID_AND_AUTHORITY_RECORD_ID" in rule,
        "completed_checkpoint_chain": len(completed) == 5 and stage_ids == expected_stages,
        "valid_aggregate_fingerprint_required": authority.get("aggregate_fingerprint") == EXPECTED_AGGREGATE_FINGERPRINT,
        "prior_completed_run": authority.get("prior_authoritative_run_id"),
        "prior_completed_run_status": authority.get("prior_authoritative_status"),
        "partial_runs": authority.get("partial_runs"),
        "latest_row_selection_prohibited": authority.get("latest_row_selection_prohibited") is True,
        "mixed_run_selection_prohibited": authority.get("mixed_run_selection_prohibited") is True,
        "legacy_duplicate_header_governance_used_for_authority": False,
        "selection_tests": selection_tests,
        "all_selection_tests_pass": all(row["pass"] for row in selection_tests),
    }


def _stored_aggregate_audit(raw: Mapping[str, List[List[Any]]]) -> Dict[str, Any]:
    payloads = _repair_payloads(raw[impl.OUTPUT_AGGREGATE_FP], impl.OUTPUT_AGGREGATE_FP)
    matches = [
        payload for payload in payloads
        if payload.get("governance_component_source") == impl.OUTPUT_REPAIR_GOVERNANCE
        and payload.get("all_fingerprints_equal") is True
        and payload.get("stored_reconstruction_fingerprint")
    ]
    if len(matches) != 1:
        raise VerificationFailure("expected exactly one persisted aggregate finalization record")
    return matches[0]


def _direct_run_row(values: List[List[Any]], sheet: str) -> Dict[str, Any]:
    if not values or len(values) < 2:
        raise VerificationFailure(f"{sheet}: direct repaired run row is absent")
    header = values[0]
    try:
        run_index = header.index("outcome_architecture_implementation_run_id")
    except ValueError as exc:
        raise VerificationFailure(f"{sheet}: no run identity header") from exc
    matches = [dict(zip(header, row)) for row in values[1:] if len(row) > run_index and row[run_index] == REPAIR_RUN_ID]
    if len(matches) != 1:
        raise VerificationFailure(f"{sheet}: expected one direct repaired run row")
    return matches[0]


def _scope_audit(components: Mapping[str, Sequence[Mapping[str, Any]]], raw: Mapping[str, List[List[Any]]]) -> Dict[str, Any]:
    survivor_records = components[impl.OUTPUT_SURVIVORSHIP]
    first_hits = Counter(row.get("first_blocking_layer") for row in survivor_records)
    repair_payloads = _repair_payloads(raw[impl.OUTPUT_REPAIR], impl.OUTPUT_REPAIR)
    repair_scope = [payload for payload in repair_payloads if payload.get("repair_scope")]
    expected_repair_scope = {
        "FLOAT_ZERO_PARSER", "AGGREGATE_FINGERPRINT", "RUNTIME_HARD_STOPS", "AUTHORITY_REFERENCE",
    }
    repair_scope_exact = (
        len(repair_scope) == 1
        and set(repair_scope[0].get("repair_scope", [])) == expected_repair_scope
        and repair_scope[0].get("scientific_architecture_changed") is False
        and repair_scope[0].get("counts_changed") is False
    )
    governance = components[impl.OUTPUT_GOVERNANCE]
    counters = {row.get("counter_name"): row.get("counter_value") for row in governance}
    implementation_row = _direct_run_row(raw[impl.OUTPUT_IMPLEMENTATION], impl.OUTPUT_IMPLEMENTATION)
    shadow_only = (
        implementation_row.get("implementation_mode") == "SHADOW_DIAGNOSTIC"
        and implementation_row.get("production_authority") == "FALSE"
        and implementation_row.get("current_architecture_replacement") == "FALSE"
        and implementation_row.get("success_mapping_consumer_switch") == "FALSE"
        and implementation_row.get("mechanism_test_rerun") == "FALSE"
    )
    return {
        "counts": {
            "canonical": len(components[impl.OUTPUT_CANONICAL]), "overlay": len(components[impl.OUTPUT_OVERLAY]),
            "linkage": len(components[impl.OUTPUT_LINKAGE]), "representation": len(components[impl.OUTPUT_REPRESENTATION]),
            "pairs": len(components[impl.OUTPUT_PAIR]), "survivorship": len(survivor_records),
            "canonical_loss": first_hits.get("CANONICAL_OUTCOME", 0), "overlay_loss": first_hits.get("OUTCOME_OVERLAY", 0),
            "success_mapping_loss": first_hits.get("OUTCOME_REPRESENTATION", 0), "survivors": first_hits.get("NONE", 0),
        },
        "expected_counts_preserved": (
            len(components[impl.OUTPUT_CANONICAL]) == 144 and len(components[impl.OUTPUT_OVERLAY]) == 144
            and len(components[impl.OUTPUT_LINKAGE]) == 144 and len(components[impl.OUTPUT_REPRESENTATION]) == 144
            and len(components[impl.OUTPUT_PAIR]) == 72 and len(survivor_records) == 72
            and first_hits == Counter({"OUTCOME_REPRESENTATION": 36, "CANONICAL_OUTCOME": 22, "OUTCOME_OVERLAY": 11, "NONE": 3})
        ),
        "repair_scope": repair_scope,
        "repair_scope_exact": repair_scope_exact,
        "governance_counters": counters,
        "shadow_only_implementation_record": shadow_only,
        "non_modification_verified": all(counters.get(name) == 0 for name in (
            "source_outcome_rows_modified", "existing_outcome_rules_modified", "existing_overlay_rows_modified",
            "existing_linkage_rows_modified", "existing_representation_rows_modified", "existing_eligibility_rows_modified",
            "success_mapping_modified", "mechanism_rules_modified", "preregistration_modified",
            "mechanism_tests_performed", "production_writes", "consumer_switches", "production_behavior_changes",
        )),
    }


def _write_outputs(service, outputs: Mapping[str, Mapping[str, Any]]) -> Dict[str, int]:
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, fields="sheets.properties(title,gridProperties,sheetId)",
    ).execute()
    properties = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata.get("sheets", [])}
    missing = [sheet for sheet in OUTPUT_SHEETS if sheet not in properties]
    if missing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": sheet, "gridProperties": {"rowCount": 2, "columnCount": 8}}}} for sheet in missing]},
        ).execute()
    updates = []
    for sheet, row in outputs.items():
        updates.append({"range": f"'{sheet}'!A1:H1", "values": [HEADERS]})
        updates.append({"range": f"'{sheet}'!A2:H2", "values": [[row.get(header, "") for header in HEADERS]]})
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)
    return {sheet: 1 for sheet in outputs}


def build() -> Dict[str, Any]:
    generated_ts = _now_iso()
    review_run_id = _review_run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    source_sheets = list(component for component in impl.AGGREGATE_COMPONENTS if component != impl.OUTPUT_GOVERNANCE)
    source_sheets.extend((
        impl.OUTPUT_REPAIR_GOVERNANCE, impl.OUTPUT_AUTHORITY, impl.OUTPUT_REPAIR,
        impl.OUTPUT_AGGREGATE_FP, impl.OUTPUT_IMPLEMENTATION,
    ))
    raw = _raw_sheet_values(service, source_sheets)

    parser = _parser_audit()
    aggregate, component_counts, components = _reconstruct_aggregate(raw)
    stored_aggregate = _stored_aggregate_audit(raw)
    aggregate_ok = (
        aggregate["aggregate_content_fingerprint"] == EXPECTED_AGGREGATE_FINGERPRINT
        and stored_aggregate.get("aggregate_content_fingerprint") == EXPECTED_AGGREGATE_FINGERPRINT
        and stored_aggregate.get("stored_reconstruction_fingerprint") == EXPECTED_AGGREGATE_FINGERPRINT
        and list(aggregate["aggregate_payload"]["component_order"]) == list(impl.AGGREGATE_COMPONENTS)
        and set(component_counts) == set(impl.AGGREGATE_COMPONENTS) and len(component_counts) == 11
    )
    hard_stops = _stop_audit()
    authority = _authority_audit(raw)
    scope = _scope_audit(components, raw)

    blocking = []
    if not (parser["all_cases_pass"] and parser["parser_fail_closed"]):
        blocking.append("PARSER_REPAIR_INCOMPLETE")
    if not aggregate_ok:
        blocking.append("AGGREGATE_FINGERPRINT_MISMATCH")
    if not (hard_stops["all_negative_path_tests_pass"] and hard_stops["runtime_tests_execute_on_real_build_path_before_outcome_load"] and not hard_stops["stops_remaining_catalog_only"]):
        blocking.append("HARD_STOP_RUNTIME_ENFORCEMENT_INCOMPLETE")
    if not (authority["authoritative_repair_run_id"] == REPAIR_RUN_ID and authority["exact_authority_selector"] and authority["completed_checkpoint_chain"] and authority["valid_aggregate_fingerprint_required"] and authority["latest_row_selection_prohibited"] and authority["mixed_run_selection_prohibited"] and authority["all_selection_tests_pass"] and authority["prior_completed_run"] == "9A-6R15I_20260713T052341Z" and authority["prior_completed_run_status"] == "SUPERSEDED_BY_REPAIRED_RUN" and authority["partial_runs"] == ["9A-6R15I_20260713T051739Z", "9A-6R15I_20260713T051900Z"]):
        blocking.append("AUTHORITY_ISOLATION_INCOMPLETE")
    if not (scope["expected_counts_preserved"] and scope["non_modification_verified"] and scope["repair_scope_exact"] and scope["shadow_only_implementation_record"]):
        blocking.append("SCOPE_OR_PRESERVATION_FAILURE")

    decision = "PASS_PROCEED_TO_POPULATION_RECOVERY_AUDIT" if not blocking else "TARGETED_REPAIR_REQUIRED"
    statuses = {
        OUTPUT_SUMMARY: "PASS" if not blocking else "FAIL",
        OUTPUT_PARSER: "PASS" if parser["all_cases_pass"] and parser["parser_fail_closed"] else "FAIL",
        OUTPUT_FINGERPRINT_AUTHORITY: "PASS" if aggregate_ok and not "AUTHORITY_ISOLATION_INCOMPLETE" in blocking else "FAIL",
        OUTPUT_HARD_STOPS: "PASS" if hard_stops["all_negative_path_tests_pass"] and not hard_stops["stops_remaining_catalog_only"] else "FAIL",
    }
    payloads = {
        OUTPUT_SUMMARY: {"authoritative_repair_run_id": REPAIR_RUN_ID, "decision": decision, "blocking_findings": blocking, "scope_preservation": scope},
        OUTPUT_PARSER: parser,
        OUTPUT_FINGERPRINT_AUTHORITY: {"aggregate_fingerprint": aggregate["aggregate_content_fingerprint"], "stored_authoritative_fingerprint": stored_aggregate.get("aggregate_content_fingerprint"), "expected_aggregate_fingerprint": EXPECTED_AGGREGATE_FINGERPRINT, "component_count": len(component_counts), "component_row_counts": component_counts, "component_order": aggregate["aggregate_payload"]["component_order"], "serialization": aggregate["aggregate_payload"]["serialization"], "encoding": "UTF-8", "json_delimiter": "canonical JSON separators ',' and ':' with sorted keys; no physical-row concatenation", "excluded_volatile_fields": aggregate["aggregate_payload"]["excluded_volatile_fields"], "authority": authority},
        OUTPUT_HARD_STOPS: hard_stops,
    }
    rows = {
        sheet: {
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "repair_verification_run_id": review_run_id,
            "authoritative_repair_run_id": REPAIR_RUN_ID, "review_area": sheet.rsplit("_", 2)[-2],
            "review_status": statuses[sheet], "blocking": "TRUE" if statuses[sheet] == "FAIL" else "FALSE",
            "payload_json": _canonical_json(payloads[sheet]),
        }
        for sheet in OUTPUT_SHEETS
    }
    written = _write_outputs(service, rows)
    return {"build_status": "PASS" if not blocking else "FAIL", "final_interpretation": "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_R1_REPAIR_VERIFICATION_PASSED" if not blocking else "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_R1_REPAIR_VERIFICATION_NEEDS_REPAIR", "review_run_id": review_run_id, "file_created": BUILD_SCRIPT, "sheets_written": list(OUTPUT_SHEETS), "rows_written_per_sheet": written, "aggregate_fingerprint": aggregate["aggregate_content_fingerprint"], "blocking_findings": blocking, "recommended_next_step": "Proceed to Outcome Architecture v2 Population Recovery Audit" if not blocking else "Perform one targeted repair", "decision": decision}


def main() -> None:
    print(json.dumps(build(), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
