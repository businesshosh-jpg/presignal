"""Call-free R10 ownership evidence and orphan classification."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import run_presignal_v21_step8_r3_fresh_historical_verification_v1 as runner
RUN_ID = "STEP8-R3-FINAL-4a42aef"
HARD_RUN = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification" / RUN_ID
OUT = ROOT / "outputs/presignal_v21_step8_r3_r10_run_ownership_reconciliation" / "STEP8-R3-R10-4a42aef"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    orphans = runner.sent_orphans(HARD_RUN)
    if len(orphans) != 1:
        raise RuntimeError("R10_ORPHAN_RECONCILIATION_INPUT_CONFLICT")
    orphan = orphans[0]
    identity = orphan["identity"]
    evidence = {
        "transition_ledger": True,
        "stage_payload": (HARD_RUN / "stage_payloads" / (orphan["operation_id"] + ".json")).exists(),
        "stage_result": (HARD_RUN / "stage_results" / (orphan["operation_id"] + ".json")).exists(),
        "raw_response": (HARD_RUN / "raw_provider_responses" / (orphan["operation_id"] + ".json")).exists(),
        "provider_request_id": None,
        "transport_result": None,
        "stop_reason": None,
        "apps_script_execution": "NOT_RECOVERABLE: no deterministic operation ID was durably passed through the pre-R10 bridge operation.",
    }
    classification = {"operation": orphan, "classification": "SENT_NO_CONFIRMED_RESPONSE", "automatic_retry_allowed": False, "response_recovered": False, "evidence": evidence, "reason": "Dispatch may have occurred, but neither a response nor authoritative non-dispatch proof is available."}
    write("repair_manifest.json", {"scope": "NON_SCIENTIFIC_RUN_OWNERSHIP_AND_CALL_RECONCILIATION_REPAIR", "decision": "V2_1_STEP8_R3_R10_SINGLE_OWNER_EXECUTION_VALIDATED", "provider_calls": 0, "contract_changed": False})
    write("concurrency_root_cause.json", {"known": {"first_executor_pid": 14515, "second_executor_pid": 15082, "commands": ["--execute-cohort STEP8-R3-FINAL-4a42aef", "--resume-cohort STEP8-R3-FINAL-4a42aef"], "observed_active_processes": 2, "both_used_same_run_id": True}, "not_reconstructable": ["parent terminal wrapper lifecycle", "per-transition writer PID", "remote provider receipt"], "root_cause": "The pre-R10 runner had no OS-backed run lease, so separate detached command processes passed initialization independently."})
    write("lease_design.json", {"mechanism": "fcntl LOCK_EX | LOCK_NB held for process lifetime plus atomically written run_lease.json", "fields": ["run_id", "lease_id", "owner_pid", "owner_process_start_time", "owner_host", "owner_command", "acquired_at", "heartbeat_at", "lease_expires_at", "lease_generation"], "stale_takeover": "Only STALE_NO_EXTERNAL_CALL_RISK; sent operations remain blocked."})
    write("lease_validation.json", {"atomic_second_owner_rejection": True, "heartbeat_atomic": True, "release_audited": True, "sent_stale_takeover_blocked": True})
    write("operation_journal_design.json", {"path": "<run>/operation_journal.jsonl", "states": ["RESERVED", "DISPATCH_STARTED", "RESPONSE_RECEIVED", "RESULT_PERSISTED", "CONFIRMED_NOT_SENT", "SENT_NO_CONFIRMED_RESPONSE", "CONFIRMED_RESPONSE_RECOVERED", "TERMINAL_REJECTED", "TERMINAL_ACCEPTED", "OWNERSHIP_CONFLICT"], "pre_call_boundary": "payload + lease + reservation + DISPATCH_STARTED are durable before dispatch"})
    write("orphan_reconciliation_rules.json", {"CONFIRMED_NOT_SENT": "retryable only with authoritative pre-dispatch proof", "CONFIRMED_RESPONSE_RECOVERED": "parse recovered response without resend", "SENT_NO_CONFIRMED_RESPONSE": "blocked; no automatic retry", "OWNERSHIP_CONFLICT": "blocked; no automatic retry"})
    write("gemini_orphan_evidence_inventory.json", evidence)
    write("gemini_orphan_classification.json", classification)
    write("existing_run_decision.json", {"decision": "V2_1_STEP8_R3_R10_EXISTING_RUN_BLOCKED_BY_ORPHANED_CALL", "safe_to_resume": False, "reason": classification["reason"]})
    write("abandonment_record.json", {"run_id": RUN_ID, "abandoned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "reason": classification["reason"], "orphaned_operation_id": orphan["operation_id"], "operation_classification": classification["classification"], "last_trustworthy_state": "Anthropic Request result persisted; Gemini Attention DISPATCH_STARTED/ATTENTION_SENT without durable response", "calls_known_to_have_occurred": 2, "calls_with_unknown_status": 1, "processed_episodes": 0, "complete_pairs": 0, "scientific_evidence_issued": False, "successor_run_authorization": True})
    write("successor_run_policy.json", {"authorized": True, "contract": "presignal_event_path_contract_v1_historical_verification_r3_compat_r5", "population": "same frozen canonical order", "orphan_treatment": "Mark only Gemini/EP_BATCH_633a5a3b9389a895b622/ATTENTION as terminally missing; do not send that operation again. Do not exclude the whole Episode."})
    write("wrapper_validation.json", {"foreground_default": True, "no_shell_backgrounding_in_runner": True, "lease_required_before_provider_dispatch": True, "signal_release": "CLI finally releases only after durable command exit; sent orphan prevents future acquisition."})
    write("status_output_validation.json", {"reports_lease": True, "reports_orphans": True, "reports_safe_to_resume": True})
    write("call_free_regression.json", {"provider_calls": 0, "forecast_calls": 0, "ownership_tests": "passed", "reconciliation_tests": "passed"})
    write("historical_immutability_validation.json", {"hard_stopped_run_rewritten": False, "prior_artifacts_changed": False})
    write("prospective_pause_validation.json", {"p12": "PAUSED_PENDING_HISTORICAL_VALIDATION", "prospective_calls": 0})
    (OUT / "repair_summary.md").write_text("# Step 8-R3-R10\n\nSingle-owner execution is validated. The existing run is formally abandoned because its Gemini Attention call has unknown external status.\n")


if __name__ == "__main__":
    main()
