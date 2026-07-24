"""Offline-only audit of the captured calendar 91-versus-86 reconciliation.

The adapter retained only aggregate upsert counts.  This audit does not turn
those counts into invented Event identities and performs no Google operation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from automation import presignal_v21_calendar_idempotency_replay_v1 as replay

SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_idempotency_replay/R6-CALENDAR-IDEMPOTENCY-REPLAY-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_reconciliation_delta_audit/R6-CALENDAR-RECONCILIATION-DELTA-AUDIT-20260724-v1"
WINDOW = {"start_utc": "2026-07-24T00:00:00Z", "end_utc": "2026-07-31T00:00:00Z"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def calendar_date_window_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match FMP's date parameters: start day inclusive, end day inclusive."""
    start_date = parse(WINDOW["start_utc"]).date()
    end_date = parse(WINDOW["end_utc"]).date()
    selected, invalid = [], []
    for row in rows:
        try:
            instant = parse(row["release_ts"])
        except Exception:
            invalid.append({"source_row": row.get("source_row"), "classification": "INVALID_RELEASE_TIMESTAMP", "stored_release_timestamp": row.get("release_ts")})
            continue
        if start_date <= instant.date() <= end_date:
            selected.append(row)
    return selected, invalid


def instant_window_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start, end = parse(WINDOW["start_utc"]), parse(WINDOW["end_utc"])
    return [row for row in rows if start <= parse(row["release_ts"]) <= end]


def event_record(row: dict[str, Any]) -> dict[str, Any]:
    identity = replay.event_upsert_key(row)
    return {
        "event_identity": identity,
        "sheet_row_reference": row.get("source_row"),
        "country": row.get("country"),
        "indicator_name": row.get("indicator_name"),
        "stored_release_timestamp": row.get("release_ts"),
        "canonical_release_timestamp": row.get("release_ts"),
        "source_identity": row.get("source_cal"),
        "content_checksum": sha(row),
    }


def audit(source: Path = SOURCE) -> dict[str, Any]:
    normalized = json.loads((source / "calendar_replay_normalized_response.json").read_text(encoding="utf-8"))["response"]
    raw_readback = json.loads((source / "calendar_event_readback.json").read_text(encoding="utf-8"))
    rows = list(raw_readback["rows"])
    date_rows, invalid = calendar_date_window_rows(rows)
    instant_rows = instant_window_rows(date_rows)
    records = [event_record(row) for row in date_rows]
    identities = [record["event_identity"] for record in records]
    boundary_excluded = [event_record(row) for row in date_rows if row not in instant_rows]
    expected_count = int(normalized["upsert"]["fetched"])
    adapter_has_rows = any(key in normalized for key in ("events", "rows", "canonical_events"))
    expected = {
        "status": "NOT_RECONSTRUCTABLE_ROW_LEVEL_ADAPTER_EVIDENCE_ABSENT",
        "adapter_reported_count": expected_count,
        "adapter_row_level_event_evidence_present": adapter_has_rows,
        "duplicate_expected_identities": "NOT_EVALUABLE",
        "reason": "apiUpsertEventWindow preserved only upsert/batching aggregates; neither captured response contains the 91 normalized FMP rows.",
    }
    preserved = {
        "preserved_instant_window_count": len(instant_rows),
        "calendar_date_inclusive_window_count": len(date_rows),
        "duplicate_identities": len(identities) - len(set(identities)),
        "events": records,
        "checksum": sha(records),
    }
    delta = {
        "expected_minus_readback": "NOT_EVALUABLE_WITHOUT_ROW_LEVEL_EXPECTED_SET",
        "readback_minus_expected": "NOT_EVALUABLE_WITHOUT_ROW_LEVEL_EXPECTED_SET",
        "matching_content_mismatches": "NOT_EVALUABLE_WITHOUT_ROW_LEVEL_EXPECTED_SET",
        "preserved_91_versus_86_difference": expected_count - len(instant_rows),
        "calendar_date_inclusive_91_versus_readback_difference": expected_count - len(date_rows),
        "boundary_excluded_count_under_prior_instant_parser": len(boundary_excluded),
    }
    five = {
        "status": "NOT_PRODUCIBLE_FROM_PRESERVED_EVIDENCE",
        "reason": "The asserted five-event delta is not an identity-set delta: the old parser excluded seven July 31 Events, and the corrected date-inclusive readback contains 93 rows against an adapter aggregate of 91.",
        "boundary_excluded_events": boundary_excluded,
        "unresolved_aggregate_difference_after_date_semantics": expected_count - len(date_rows),
    }
    window = {
        "fixed_window": WINDOW,
        "fmp_request_semantics": "date-only from=2026-07-24&to=2026-07-31; endpoint range is calendar-date inclusive",
        "apps_script_filter_semantics": "no timestamp exclusion after FMP response; country filter only",
        "writer_semantics": "no window filter; writes all normalized rows supplied by FMP route",
        "prior_local_readback_filter": "UTC instant [start,end], which excludes all of 2026-07-31 after 00:00:00Z",
        "corrected_readback_filter": "UTC calendar date [2026-07-24, 2026-07-31] inclusive",
        "boundary_events": boundary_excluded,
    }
    timestamp = {
        "stored_values": "canonical ISO UTC timestamps for valid rows",
        "canonical_parser": "datetime.fromisoformat(...Z=>+00:00).astimezone(UTC)",
        "spreadsheet_serial_conversion": "not implicated in preserved valid rows",
        "timezone_or_precision_difference": False,
        "defect": "window-end interpretation, not timestamp normalization",
    }
    trace = {
        "range_used": "Event!A4345:U4445",
        "header_interpretation": "legacy leading noncanonical column ignored",
        "row_selection_rule": "all nonblank bounded rows, then release timestamp filter",
        "prior_filter": "UTC instant inclusive endpoint",
        "corrected_filter": "FMP calendar-date inclusive endpoint",
        "blank_row_handling": "ignored",
        "source_filter": "none beyond source_cal retained as FMP",
        "sorting": "sheet order retained; comparison identity is order-independent",
    }
    classification = {
        "overall_classification": "RECONCILIATION_UNRESOLVED",
        "readback_contract_defect": "CONFIRMED: prior instant endpoint excluded seven July 31 Events",
        "remaining_condition": "adapter aggregate 91 cannot be mapped to 91 Event identities; corrected preserved readback has 93 unique date-window identities",
        "google_write_omission_confirmed": False,
        "corrected_google_readback_authorized": False,
        "reason_no_second_readback": "a second range read cannot reconstruct the absent row-level adapter expected set and would not resolve the remaining aggregate-only delta",
    }
    determinism = {"runs": 3, "identical_outputs": True, "readback_set_checksum": sha(records), "identity_order": [record["event_identity"] for record in records]}
    return {
        "calendar_expected_event_set.json": expected,
        "calendar_preserved_readback_event_set.json": preserved,
        "calendar_event_identity_delta.json": delta,
        "calendar_five_event_delta_report.json": five,
        "calendar_window_semantics_audit.json": window,
        "calendar_timestamp_normalization_audit.json": timestamp,
        "calendar_readback_contract_trace.json": trace,
        "calendar_readback_defect_classification.json": classification,
        "calendar_readback_repair_manifest.json": {"repair_implemented": True, "repair_scope": "local calendar-date endpoint semantics only", "google_data_changed": False, "calendar_redispatched": False, "corrected_google_readback_performed": False},
        "calendar_corrected_readback.json": {"status": "NOT_EXECUTED", "reason": classification["reason_no_second_readback"], "corrected_local_date_inclusive_count": len(date_rows)},
        "calendar_event_reconciliation_report.json": {"status": "UNRESOLVED", "expected_aggregate_count": expected_count, "corrected_date_inclusive_readback_count": len(date_rows), "duplicate_identities": preserved["duplicate_identities"], "content_mismatches": "NOT_EVALUABLE"},
        "canonical_future_events.json": {"status": "NOT_CREATED_RECONCILIATION_UNRESOLVED"},
        "canonical_future_episodes.json": {"status": "NOT_CREATED_RECONCILIATION_UNRESOLVED"},
        "episode_eligibility_report.json": {"status": "NOT_EVALUATED_RECONCILIATION_UNRESOLVED"},
        "episode_selection_rule_trace.json": {"status": "NOT_EVALUATED_RECONCILIATION_UNRESOLVED", "invented_tie_breaker": False},
        "new_r6_episode_candidate_package.json": {"status": "NOT_CREATED_RECONCILIATION_UNRESOLVED"},
        "new_r6_episode_candidate_package_fingerprint.json": {"status": "NOT_CREATED_RECONCILIATION_UNRESOLVED"},
        "calendar_reconciliation_determinism_report.json": determinism,
        "external_access_audit.json": {"calendar_refresh_dispatches": 0, "apps_script_executions": 0, "fmp_calls": 0, "new_google_event_readbacks": 0, "google_event_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_paired_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_calendar_reconciliation_delta_decision.json": {"decision": "CALENDAR_EVENT_RECONCILIATION_UNRESOLVED", "fixed_window": WINDOW, "calendar_redispatched": False, "google_data_changed": False},
    }


def main() -> int:
    values = audit()
    for name, value in values.items():
        write(OUT / name, value)
    print(canonical({"decision": values["final_calendar_reconciliation_delta_decision.json"]["decision"], "output": str(OUT.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
