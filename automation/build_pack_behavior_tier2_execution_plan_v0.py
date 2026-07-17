import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_pack_exposure_prompt_validation_v0 import EXPECTED_FIELDS_BY_LEVEL
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_behavior_tier2_execution_plan_0.1"
EXECUTION_PLAN_VERSION = "behavior_tier2_execution_plan_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4ZX"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_TIER2_EXECUTION_PLAN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_TIER2_DESIGN_SUMMARY = "Pack_Behavior_Tier2_Design_Summary"
INPUT_TIER2_EXPERIMENT_DESIGN = "Pack_Behavior_Tier2_Experiment_Design"
INPUT_TIER2_HYPOTHESIS_PLAN = "Pack_Behavior_Tier2_Hypothesis_Test_Plan"
INPUT_TIER2_SESSION_STRATEGY = "Pack_Behavior_Tier2_Session_Strategy"
INPUT_TIER2_CALL_BUDGET = "Pack_Behavior_Tier2_Call_Budget"
INPUT_TIER2_STOP_RULES = "Pack_Behavior_Tier2_Stop_Rules"
INPUT_TIER2_SUCCESS_CRITERIA = "Pack_Behavior_Tier2_Success_Criteria"
INPUT_TIER2_READINESS = "Pack_Behavior_Tier2_Readiness_Audit"
INPUT_SHADOW = "Market_State_Pack_Shadow"
INPUT_SHADOW_SUMMARY = "Market_State_Pack_Shadow_Summary"
INPUT_PILOT_SUMMARY = "Pack_Exposure_Run_Summary"
INPUT_TIER1_RUNS = "Pack_Behavior_Discovery_Runs"
INPUT_TIER1_SUMMARY = "Pack_Behavior_Discovery_Run_Summary"
INPUT_GENERALIZATION_HYPOTHESES = "Pack_Behavior_Generalization_Hypotheses"

PREVIOUS_PLANNING_SHEETS = [
    "Pack_Behavior_Pattern_Execution_Plan",
    "Pack_Behavior_Pattern_Session_Selection_Plan",
    "Pack_Behavior_Pattern_Call_Budget",
    "Pack_Behavior_Pattern_Batch_Strategy",
    "Pack_Behavior_Pattern_Stop_Hold_Rules",
    "Pack_Behavior_Pattern_Execution_Readiness_Audit",
    "Pack_Behavior_Pattern_Execution_Plan_Summary",
    "Pack_Behavior_Discovery_Failed_Attempt_Governance",
    "Pack_Behavior_Discovery_Rerun_Approval",
    "Pack_Behavior_Discovery_Rerun_Guardrails",
    "Pack_Behavior_Discovery_Governance_Summary",
]

OUTPUT_EXECUTION_PLAN = "Pack_Behavior_Tier2_Execution_Plan"
OUTPUT_BATCH_PLAN = "Pack_Behavior_Tier2_Batch_Plan"
OUTPUT_SESSION_ORDER = "Pack_Behavior_Tier2_Session_Execution_Order"
OUTPUT_CHECKPOINT_PLAN = "Pack_Behavior_Tier2_Checkpoint_Plan"
OUTPUT_FAILURE_RECOVERY = "Pack_Behavior_Tier2_Failure_Recovery"
OUTPUT_GOVERNANCE_CHECKLIST = "Pack_Behavior_Tier2_Governance_Checklist"
OUTPUT_EXECUTION_READINESS = "Pack_Behavior_Tier2_Execution_Readiness"
OUTPUT_SUMMARY = "Pack_Behavior_Tier2_Execution_Plan_Summary"

PROVIDERS = "OpenAI|Gemini|Anthropic"
PACK_LEVELS = "A|B|C|D|E"
PROVIDER_COUNT = 3
PACK_LEVEL_COUNT = 5
MIN_SESSIONS = 5
MAX_SESSIONS = 10
MIN_PROVIDER_CALLS = MIN_SESSIONS * PACK_LEVEL_COUNT * PROVIDER_COUNT
MAX_PROVIDER_CALLS = MAX_SESSIONS * PACK_LEVEL_COUNT * PROVIDER_COUNT

EXECUTION_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "plan_component",
    "component_status",
    "component_purpose",
    "execution_phase",
    "input_requirements",
    "output_requirements",
    "verification_sequence",
    "completion_criteria",
    "allowed_actions",
    "forbidden_actions",
    "restart_protocol",
    "archive_strategy",
    "notes",
]

BATCH_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "batch_id",
    "batch_sequence",
    "batch_name",
    "batch_session_count",
    "session_sequence_start",
    "session_sequence_end",
    "expected_provider_calls",
    "batch_goal",
    "preconditions",
    "checkpoint_required",
    "review_required_after_batch",
    "continue_condition",
    "hold_condition",
    "notes",
]

SESSION_ORDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "execution_sequence",
    "batch_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "session_reason",
    "hypothesis_coverage",
    "expected_pack_transitions",
    "expected_provider_coverage",
    "macro_diversity",
    "event_diversity",
    "pack_coverage_status",
    "prompt_validation_requirement",
    "planned_provider_calls",
    "notes",
]

CHECKPOINT_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "checkpoint_id",
    "checkpoint_name",
    "checkpoint_timing",
    "verification_items",
    "expected_evidence",
    "blocking_if_failed",
    "failure_action",
    "notes",
]

FAILURE_RECOVERY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "failure_case_id",
    "failure_case",
    "stop_immediately",
    "continue_allowed",
    "preserve_archive",
    "rerun_allowed",
    "governance_review_required",
    "recovery_procedure",
    "required_label",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "check_id",
    "check_name",
    "check_requirement",
    "blocking",
    "verification_method",
    "required_status_before_execution",
    "failure_action",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "readiness_check_id",
    "readiness_area",
    "check_description",
    "check_status",
    "evidence_sheet",
    "evidence_value",
    "blocking",
    "recommended_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "tier2_execution_plan_id",
    "build_status",
    "final_interpretation",
    "batches_planned",
    "sessions_planned",
    "provider_calls_planned",
    "minimum_provider_calls",
    "maximum_provider_calls",
    "retry_budget",
    "provider_reruns_allowed",
    "checkpoints_defined",
    "failure_recovery_procedures_defined",
    "governance_checks_defined",
    "readiness_checks_defined",
    "tier2_design_confirmed",
    "tier2_execution_started",
    "accuracy_evaluation_count",
    "provider_call_count",
    "forecast_generation_count",
    "production_behavior_change_count",
    "ready_for_tier2_execution",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _plan_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_tier2_execution_plan_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _latest_run_id(rows: Sequence[Dict[str, Any]], field: str) -> str:
    for row in reversed(rows):
        value = _norm(row.get(field))
        if value:
            return value
    return ""


def _used_sessions(pilot_rows: Sequence[Dict[str, Any]], tier1_runs: Sequence[Dict[str, Any]], tier1_summary: Sequence[Dict[str, Any]]) -> Set[str]:
    used: Set[str] = set()
    for row in pilot_rows:
        if _norm(row.get("session_selected")):
            used.add(_norm(row.get("session_selected")))
    for row in tier1_runs:
        if _norm(row.get("session_id")):
            used.add(_norm(row.get("session_id")))
    for row in tier1_summary:
        for part in _norm(row.get("session_ids_executed")).split("|"):
            if part.startswith("US"):
                # Session IDs themselves contain pipes; reconstructing from summary is unreliable.
                pass
    return used


def _complete_shadow_sessions(shadow_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    required = set(EXPECTED_FIELDS_BY_LEVEL["E"])
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = {}
    metadata: Dict[str, Dict[str, str]] = {}
    for row in shadow_rows:
        session_id = _norm(row.get("session_id"))
        field = _norm(row.get("candidate_field"))
        if not session_id or field not in required:
            continue
        by_session.setdefault(session_id, {})[field] = row
        metadata.setdefault(
            session_id,
            {
                "session_id": session_id,
                "session_date": _norm(row.get("session_date")),
                "country": _norm(row.get("country")),
                "session_window_name": _norm(row.get("session_window_name")),
            },
        )
    candidates: List[Dict[str, Any]] = []
    for session_id, fields in by_session.items():
        if set(fields) != required:
            continue
        if all(
            _upper(row.get("data_available_flag")) == "TRUE"
            and _upper(row.get("leakage_check_status")) != "FAIL"
            and _upper(row.get("provider_visible")) != "TRUE"
            and _upper(row.get("used_in_forecast")) != "TRUE"
            for row in fields.values()
        ):
            candidates.append(metadata[session_id])
    return sorted(candidates, key=lambda row: (_norm(row.get("session_date")), _norm(row.get("session_id"))))


def _select_sessions(
    shadow_rows: Sequence[Dict[str, Any]],
    pilot_rows: Sequence[Dict[str, Any]],
    tier1_runs: Sequence[Dict[str, Any]],
    tier1_summary: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    used = _used_sessions(pilot_rows, tier1_runs, tier1_summary)
    candidates = [row for row in _complete_shadow_sessions(shadow_rows) if _norm(row.get("session_id")) not in used]
    return candidates[:MAX_SESSIONS]


def _execution_plan_rows(generated_ts: str, plan_id: str) -> List[Dict[str, Any]]:
    components = [
        ("execution_phases", "Define preflight, batch execution, checkpoints, review, and finalization.", "preflight->batch_1->review->batch_2_optional->final_summary"),
        ("batch_boundaries", "Run Batch 1 first, review before any additional batch.", "Batch 1 = 5 sessions; Batch 2 = optional remaining up to 5 sessions"),
        ("checkpoint_schedule", "Verify archive and derived rows before continuing.", "before execution|after every session|after every batch|before final summary"),
        ("restart_protocol", "Restart only from archived/checkpointed evidence under a new execution approval if interrupted.", "no silent continuation beyond approved checkpoint"),
        ("archive_strategy", "Raw archive first, immediate append, dedupe key, zero missing archives.", "raw_response_archive_key required before parsing-derived outputs"),
        ("verification_sequence", "Preflight inputs, session eligibility, prompt validation, raw archive writability, budget cap, governance checklist.", "all checks pass before execution"),
        ("completion_criteria", "Complete planned sessions, archive all attempts, write behavior outputs, pass governance checks.", "no accuracy evaluation"),
    ]
    rows = []
    for component, purpose, sequence in components:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "plan_component": component,
                "component_status": "DEFINED",
                "component_purpose": purpose,
                "execution_phase": "Phase 9A-4Z future execution only",
                "input_requirements": "Tier2 design sheets|prompt validation|shadow pack|session context|governance approval",
                "output_requirements": "future Tier2 discovery outputs with raw archive and behavior comparison rows",
                "verification_sequence": sequence,
                "completion_criteria": "all provider attempts archived; summary counters match row-level outputs; stop rules clear",
                "allowed_actions": "behavior-only provider-call execution in future approved phase",
                "forbidden_actions": "accuracy|direction_correctness|provider_ranking|pack_ranking|production|routing|weighting|calibration",
                "restart_protocol": "resume only from explicit checkpoint; no silent reruns; failed cells remain evidence",
                "archive_strategy": "raw_archive_first|immediate_append|dedupe_active|stop_on_archive_failure",
                "notes": "This design sheet does not execute Tier 2.",
            }
        )
    return rows


def _batch_rows(generated_ts: str, plan_id: str, session_count: int) -> List[Dict[str, Any]]:
    batch1 = min(5, session_count)
    batch2 = max(0, session_count - batch1)
    rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "execution_plan_version": EXECUTION_PLAN_VERSION,
            "tier2_execution_plan_id": plan_id,
            "batch_id": "T2_BATCH_1",
            "batch_sequence": 1,
            "batch_name": "Tier 2 initial hypothesis batch",
            "batch_session_count": batch1,
            "session_sequence_start": 1 if batch1 else "",
            "session_sequence_end": batch1 if batch1 else "",
            "expected_provider_calls": batch1 * PACK_LEVEL_COUNT * PROVIDER_COUNT,
            "batch_goal": "Test high-priority hypotheses over the minimum Tier 2 sample.",
            "preconditions": "Tier2 execution approval|raw archive writable|session eligibility confirmed|provider cap approved",
            "checkpoint_required": "TRUE",
            "review_required_after_batch": "TRUE",
            "continue_condition": "invalid rate <=20%; raw archive complete; high-priority hypothesis coverage adequate",
            "hold_condition": "invalid rate >20%|raw archive failure|provider outage cluster|governance violation",
            "notes": "Do not execute Batch 2 without Batch 1 review.",
        }
    ]
    if batch2:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "batch_id": "T2_BATCH_2",
                "batch_sequence": 2,
                "batch_name": "Tier 2 optional hypothesis-completion batch",
                "batch_session_count": batch2,
                "session_sequence_start": batch1 + 1,
                "session_sequence_end": session_count,
                "expected_provider_calls": batch2 * PACK_LEVEL_COUNT * PROVIDER_COUNT,
                "batch_goal": "Complete planned 5-10 session sample if Batch 1 review supports continuation.",
                "preconditions": "Batch 1 review passed|governance approval for continuation|budget remaining",
                "checkpoint_required": "TRUE",
                "review_required_after_batch": "TRUE",
                "continue_condition": "final summary safe for Tier2 review",
                "hold_condition": "same as Batch 1 or new invalid-output cluster",
                "notes": "Optional; not part of this planning phase execution.",
            }
        )
    return rows


def _session_order_rows(generated_ts: str, plan_id: str, sessions: Sequence[Dict[str, Any]], hypotheses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    high_hypotheses = "|".join(_norm(row.get("hypothesis_id")) for row in hypotheses if _upper(row.get("tier2_test_priority")) == "HIGH")
    all_hypotheses = "|".join(_norm(row.get("hypothesis_id")) for row in hypotheses if _norm(row.get("hypothesis_id")))
    rows = []
    for idx, session in enumerate(sessions, start=1):
        batch_id = "T2_BATCH_1" if idx <= 5 else "T2_BATCH_2"
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "execution_sequence": idx,
                "batch_id": batch_id,
                "session_id": _norm(session.get("session_id")),
                "session_date": _norm(session.get("session_date")),
                "country": _norm(session.get("country")),
                "session_window_name": _norm(session.get("session_window_name")),
                "session_reason": "earliest eligible complete deterministic pack session not used by pilot/Tier1",
                "hypothesis_coverage": high_hypotheses if idx <= 5 else all_hypotheses,
                "expected_pack_transitions": "A_to_B|B_to_C|C_to_D|D_to_E|A_to_D|A_to_E",
                "expected_provider_coverage": PROVIDERS,
                "macro_diversity": "calendar sequence diversity; verify before execution",
                "event_diversity": "session event mix from Market_Session_Members; verify before execution",
                "pack_coverage_status": "COMPLETE_LANE_A_DETERMINISTIC_PACK",
                "prompt_validation_requirement": "latest prompt validation must pass before execution",
                "planned_provider_calls": PACK_LEVEL_COUNT * PROVIDER_COUNT,
                "notes": "Execution order is explicit planning only; no provider call made.",
            }
        )
    return rows


def _checkpoint_rows(generated_ts: str, plan_id: str) -> List[Dict[str, Any]]:
    checkpoints = [
        ("T2_CP_001", "before_execution", "Before first provider call", "raw archive sheet writable|headers present|dedupe key active|provider cap approved|Pack Q excluded|accuracy excluded"),
        ("T2_CP_002", "after_each_session", "After every session", "15 provider attempts expected|15 raw archive rows|metadata rows|behavior rows|invalid rows isolated|stop-rule status"),
        ("T2_CP_003", "after_batch_1", "After Batch 1", "75 attempts if five sessions|raw archive complete|invalid rate <=20%|hypothesis coverage check"),
        ("T2_CP_004", "before_batch_2", "Before optional Batch 2", "Batch 1 review approval|remaining budget|no unresolved stop rule"),
        ("T2_CP_005", "after_batch_2", "After optional Batch 2", "all planned attempts archived|invalid-output clusters reviewed|derived rows complete"),
        ("T2_CP_006", "before_final_summary", "Before final summary", "row-count reconciliation|dedupe integrity|raw archive completeness|governance checklist complete"),
    ]
    rows = []
    for cid, name, timing, items in checkpoints:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "checkpoint_id": cid,
                "checkpoint_name": name,
                "checkpoint_timing": timing,
                "verification_items": items,
                "expected_evidence": "checkpoint log row plus summary counter agreement",
                "blocking_if_failed": "TRUE",
                "failure_action": "STOP_OR_HOLD_FOR_REVIEW",
                "notes": "Checkpoint design only; future execution must write evidence.",
            }
        )
    return rows


def _failure_recovery_rows(generated_ts: str, plan_id: str) -> List[Dict[str, Any]]:
    failures = [
        ("T2_FR_001", "provider_timeout", "FALSE", "TRUE", "TRUE", "FALSE", "TRUE", "Archive timeout response, mark invalid, continue if raw archive succeeds.", "TIMEOUT"),
        ("T2_FR_002", "provider_5xx", "FALSE", "TRUE", "TRUE", "FALSE", "TRUE", "Archive provider error, mark invalid, continue if threshold not breached.", "PROVIDER_ERROR"),
        ("T2_FR_003", "malformed_json", "FALSE", "TRUE", "TRUE", "FALSE", "FALSE", "Archive raw response, mark invalid, do not repair or infer.", "MALFORMED_JSON"),
        ("T2_FR_004", "schema_failure", "FALSE", "TRUE", "TRUE", "FALSE", "FALSE", "Archive raw response, mark schema validation failure, continue if threshold not breached.", "SCHEMA_VALIDATION_FAILURE"),
        ("T2_FR_005", "google_sheets_append_failure", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE", "Stop immediately after append retries fail; no further provider calls.", "RAW_ARCHIVE_WRITE_FAILURE"),
        ("T2_FR_006", "partial_batch_interruption", "TRUE", "FALSE", "TRUE", "FALSE", "TRUE", "Preserve completed raw archive rows and require governance review before any continuation.", "PARTIAL_BATCH_INTERRUPTION"),
        ("T2_FR_007", "local_crash", "TRUE", "FALSE", "TRUE", "FALSE", "TRUE", "Use checkpoint and raw archive to classify state; no silent resume.", "LOCAL_CRASH"),
        ("T2_FR_008", "network_interruption", "TRUE", "FALSE", "TRUE", "FALSE", "TRUE", "Preserve any archived rows; require review if execution state is ambiguous.", "NETWORK_INTERRUPTION"),
    ]
    rows = []
    for fid, case, stop, cont, archive, rerun, review, procedure, label in failures:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "failure_case_id": fid,
                "failure_case": case,
                "stop_immediately": stop,
                "continue_allowed": cont,
                "preserve_archive": archive,
                "rerun_allowed": rerun,
                "governance_review_required": review,
                "recovery_procedure": procedure,
                "required_label": label,
                "notes": "No silent provider reruns; reruns require new run_id and future approval.",
            }
        )
    return rows


def _governance_rows(generated_ts: str, plan_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("T2_GOV_001", "raw_archive_first", "Raw archive sheet exists and is writable before provider calls."),
        ("T2_GOV_002", "immediate_archive_append", "Each provider response is appended before derived parsing/capture."),
        ("T2_GOV_003", "dedupe_active", "raw_response_archive_key dedupe is active."),
        ("T2_GOV_004", "provider_cap_enforced", "Provider call cap is enforced before dispatch."),
        ("T2_GOV_005", "retry_count_enforced", "Provider retry budget is zero."),
        ("T2_GOV_006", "pack_q_excluded", "Pack Q is not included."),
        ("T2_GOV_007", "accuracy_excluded", "No accuracy or direction correctness evaluation occurs."),
        ("T2_GOV_008", "production_excluded", "No production writes or behavior changes occur."),
        ("T2_GOV_009", "provider_reruns_prohibited", "Provider reruns are prohibited unless new run_id approval exists."),
        ("T2_GOV_010", "stop_rules_enabled", "Tier 2 stop rules are loaded before execution."),
        ("T2_GOV_011", "excluded_fields_absent", "fed_expectations, UPCOMING_EVENT_RISK_LABEL, Lane B/C items absent."),
        ("T2_GOV_012", "raw_archive_completeness_required", "raw_responses_archived equals provider_call_count."),
    ]
    rows = []
    for cid, name, requirement in checks:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "check_id": cid,
                "check_name": name,
                "check_requirement": requirement,
                "blocking": "TRUE",
                "verification_method": "future execution preflight and summary counter audit",
                "required_status_before_execution": "PASS",
                "failure_action": "STOP_OR_HOLD_FOR_REVIEW",
                "notes": "Governance checklist is design-only here.",
            }
        )
    return rows


def _readiness_rows(
    generated_ts: str,
    plan_id: str,
    design_summary: Dict[str, Any],
    session_rows: Sequence[Dict[str, Any]],
    missing: Sequence[str],
) -> List[Dict[str, Any]]:
    checks = [
        ("T2_EXEC_READY_001", "tier2_design_complete", "Tier 2 design summary confirms design complete", _upper(design_summary.get("tier2_design_complete")) == "TRUE", INPUT_TIER2_DESIGN_SUMMARY, _norm(design_summary.get("tier2_design_complete")), True),
        ("T2_EXEC_READY_002", "execution_not_started", "Tier 2 execution has not started", _upper(design_summary.get("tier2_execution_started")) == "FALSE", INPUT_TIER2_DESIGN_SUMMARY, _norm(design_summary.get("tier2_execution_started")), True),
        ("T2_EXEC_READY_003", "batching_complete", "Batch plan is defined", True, OUTPUT_BATCH_PLAN, "defined", True),
        ("T2_EXEC_READY_004", "session_order_complete", "At least five eligible planned sessions exist", len(session_rows) >= MIN_SESSIONS, OUTPUT_SESSION_ORDER, len(session_rows), True),
        ("T2_EXEC_READY_005", "checkpoints_complete", "Checkpoint plan is defined", True, OUTPUT_CHECKPOINT_PLAN, "defined", True),
        ("T2_EXEC_READY_006", "failure_recovery_complete", "Failure recovery procedures are defined", True, OUTPUT_FAILURE_RECOVERY, "defined", True),
        ("T2_EXEC_READY_007", "governance_complete", "Governance checklist is defined", True, OUTPUT_GOVERNANCE_CHECKLIST, "defined", True),
        ("T2_EXEC_READY_008", "provider_budget_complete", "Provider budget is 75-150 calls and retry budget zero", True, OUTPUT_SUMMARY, f"{MIN_PROVIDER_CALLS}-{MAX_PROVIDER_CALLS}", True),
        ("T2_EXEC_READY_009", "accuracy_excluded", "Accuracy remains excluded", True, OUTPUT_SUMMARY, "0", True),
        ("T2_EXEC_READY_010", "production_excluded", "Production remains excluded", True, OUTPUT_SUMMARY, "0", True),
        ("T2_EXEC_READY_011", "missing_input_check", "No required input sheets missing", not missing, "input_scan", "|".join(missing), False),
        ("T2_EXEC_READY_012", "ready_for_tier2_execution", "Execution protocol is complete and ready for future execution approval", len(session_rows) >= MIN_SESSIONS and not missing, OUTPUT_SUMMARY, "TRUE", True),
    ]
    rows = []
    for cid, area, desc, ok, sheet, value, blocking in checks:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_plan_version": EXECUTION_PLAN_VERSION,
                "tier2_execution_plan_id": plan_id,
                "readiness_check_id": cid,
                "readiness_area": area,
                "check_description": desc,
                "check_status": "PASS" if ok else ("BLOCKED" if blocking else "PASS_WITH_WARNINGS"),
                "evidence_sheet": sheet,
                "evidence_value": value,
                "blocking": "TRUE" if blocking else "FALSE",
                "recommended_action": "continue" if ok else ("repair before execution" if blocking else "review limitation"),
                "notes": "Readiness for execution does not mean accuracy or production readiness.",
            }
        )
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_TIER2_EXECUTION_PLAN", OUTPUT_EXECUTION_PLAN, "behavior_tier2_execution_plan"),
        ("PACK_BEHAVIOR_TIER2_BATCH_PLAN", OUTPUT_BATCH_PLAN, "behavior_tier2_batch_plan"),
        ("PACK_BEHAVIOR_TIER2_SESSION_EXECUTION_ORDER", OUTPUT_SESSION_ORDER, "behavior_tier2_session_execution_order"),
        ("PACK_BEHAVIOR_TIER2_CHECKPOINT_PLAN", OUTPUT_CHECKPOINT_PLAN, "behavior_tier2_checkpoint_plan"),
        ("PACK_BEHAVIOR_TIER2_FAILURE_RECOVERY", OUTPUT_FAILURE_RECOVERY, "behavior_tier2_failure_recovery"),
        ("PACK_BEHAVIOR_TIER2_GOVERNANCE_CHECKLIST", OUTPUT_GOVERNANCE_CHECKLIST, "behavior_tier2_governance_checklist"),
        ("PACK_BEHAVIOR_TIER2_EXECUTION_READINESS", OUTPUT_EXECUTION_READINESS, "behavior_tier2_execution_readiness"),
        ("PACK_BEHAVIOR_TIER2_EXECUTION_PLAN_SUMMARY", OUTPUT_SUMMARY, "behavior_tier2_execution_plan_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-4ZX Tier 2 behavior execution plan; no execution.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        row_number = by_id.get(key)
        if not row_number:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4ZX Tier 2 execution plan.")
    return parser.parse_args(argv)


def build_pack_behavior_tier2_execution_plan_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    plan_id = _plan_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing: List[str] = []

    design_summary_rows = _safe_rows(service, titles, INPUT_TIER2_DESIGN_SUMMARY, missing)
    design_summary = design_summary_rows[-1] if design_summary_rows else {}
    for sheet in [
        INPUT_TIER2_EXPERIMENT_DESIGN,
        INPUT_TIER2_HYPOTHESIS_PLAN,
        INPUT_TIER2_SESSION_STRATEGY,
        INPUT_TIER2_CALL_BUDGET,
        INPUT_TIER2_STOP_RULES,
        INPUT_TIER2_SUCCESS_CRITERIA,
        INPUT_TIER2_READINESS,
        INPUT_GENERALIZATION_HYPOTHESES,
        *PREVIOUS_PLANNING_SHEETS,
    ]:
        _safe_rows(service, titles, sheet, missing)

    if _upper(design_summary.get("ready_for_tier2_execution_planning")) != "TRUE":
        raise RuntimeError("Tier 2 design summary does not mark ready_for_tier2_execution_planning TRUE.")
    if _upper(design_summary.get("tier2_execution_started")) == "TRUE":
        raise RuntimeError("Tier 2 execution appears to have started; execution plan must not overwrite state.")

    shadow_summary = _safe_rows(service, titles, INPUT_SHADOW_SUMMARY, missing)
    shadow_rows_all = _safe_rows(service, titles, INPUT_SHADOW, missing)
    shadow_run_id = _latest_run_id(shadow_summary, "shadow_pack_run_id")
    shadow_rows = [row for row in shadow_rows_all if not shadow_run_id or _norm(row.get("shadow_pack_run_id")) == shadow_run_id]
    pilot_rows = _safe_rows(service, titles, INPUT_PILOT_SUMMARY, missing)
    tier1_runs = _safe_rows(service, titles, INPUT_TIER1_RUNS, missing)
    tier1_summary = _safe_rows(service, titles, INPUT_TIER1_SUMMARY, missing)
    hypotheses = _safe_rows(service, titles, INPUT_GENERALIZATION_HYPOTHESES, missing)
    sessions = _select_sessions(shadow_rows, pilot_rows, tier1_runs, tier1_summary)

    execution_rows = _execution_plan_rows(generated_ts, plan_id)
    session_rows = _session_order_rows(generated_ts, plan_id, sessions, hypotheses)
    batch_rows = _batch_rows(generated_ts, plan_id, len(session_rows))
    checkpoint_rows = _checkpoint_rows(generated_ts, plan_id)
    recovery_rows = _failure_recovery_rows(generated_ts, plan_id)
    governance_rows = _governance_rows(generated_ts, plan_id)
    readiness_rows = _readiness_rows(generated_ts, plan_id, design_summary, session_rows, missing)
    blocked = any(_upper(row.get("check_status")) == "BLOCKED" for row in readiness_rows)
    provider_calls_planned = len(session_rows) * PACK_LEVEL_COUNT * PROVIDER_COUNT
    build_status = "FAIL" if blocked else ("PASS_WITH_WARNINGS" if missing or len(session_rows) < MAX_SESSIONS else "PASS")
    final_interpretation = (
        "BEHAVIOR_TIER2_EXECUTION_PLAN_BLOCKED"
        if blocked
        else ("BEHAVIOR_TIER2_EXECUTION_PLAN_READY_WITH_WARNINGS" if missing or len(session_rows) < MAX_SESSIONS else "BEHAVIOR_TIER2_EXECUTION_PLAN_READY")
    )
    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "tier2_execution_plan_id": plan_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "batches_planned": len(batch_rows),
        "sessions_planned": len(session_rows),
        "provider_calls_planned": provider_calls_planned,
        "minimum_provider_calls": MIN_PROVIDER_CALLS,
        "maximum_provider_calls": MAX_PROVIDER_CALLS,
        "retry_budget": 0,
        "provider_reruns_allowed": "FALSE",
        "checkpoints_defined": len(checkpoint_rows),
        "failure_recovery_procedures_defined": len(recovery_rows),
        "governance_checks_defined": len(governance_rows),
        "readiness_checks_defined": len(readiness_rows),
        "tier2_design_confirmed": "TRUE",
        "tier2_execution_started": "FALSE",
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_tier2_execution": "TRUE" if not blocked else "FALSE",
        "ready_for_accuracy_evaluation": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A4ZY_TIER2_EXECUTION" if not blocked else "RUN_PHASE9A4ZX_EXECUTION_PLAN_REPAIR",
        "notes": _truncate_text(json.dumps({"missing_inputs": sorted(set(missing)), "shadow_run_id": shadow_run_id}, ensure_ascii=True), 500),
    }

    for sheet, headers, rows in [
        (OUTPUT_EXECUTION_PLAN, EXECUTION_PLAN_HEADERS, execution_rows),
        (OUTPUT_BATCH_PLAN, BATCH_PLAN_HEADERS, batch_rows),
        (OUTPUT_SESSION_ORDER, SESSION_ORDER_HEADERS, session_rows),
        (OUTPUT_CHECKPOINT_PLAN, CHECKPOINT_HEADERS, checkpoint_rows),
        (OUTPUT_FAILURE_RECOVERY, FAILURE_RECOVERY_HEADERS, recovery_rows),
        (OUTPUT_GOVERNANCE_CHECKLIST, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_EXECUTION_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry_error = ""
    try:
        registry = _upsert_registry_rows(service)
    except Exception as exc:
        registry = {"updated": 0, "appended": 0}
        registry_error = str(exc)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "tier2_execution_plan_id": plan_id,
        "batches_planned": len(batch_rows),
        "sessions_planned": len(session_rows),
        "provider_calls_planned": provider_calls_planned,
        "checkpoints_defined": len(checkpoint_rows),
        "failure_recovery_procedures_defined": len(recovery_rows),
        "governance_checks_defined": len(governance_rows),
        "readiness_audit_result": "PASS" if not blocked else "BLOCKED",
        "recommended_next_step": summary["recommended_next_step"],
        "sheets_written": {
            OUTPUT_EXECUTION_PLAN: len(execution_rows),
            OUTPUT_BATCH_PLAN: len(batch_rows),
            OUTPUT_SESSION_ORDER: len(session_rows),
            OUTPUT_CHECKPOINT_PLAN: len(checkpoint_rows),
            OUTPUT_FAILURE_RECOVERY: len(recovery_rows),
            OUTPUT_GOVERNANCE_CHECKLIST: len(governance_rows),
            OUTPUT_EXECUTION_READINESS: len(readiness_rows),
            OUTPUT_SUMMARY: 1,
        },
        "safety": {
            "provider_call_count": 0,
            "forecast_generation_count": 0,
            "accuracy_evaluation_count": 0,
            "production_behavior_change_count": 0,
        },
        "registry": registry,
        "registry_error": registry_error,
    }


def main() -> None:
    result = build_pack_behavior_tier2_execution_plan_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
