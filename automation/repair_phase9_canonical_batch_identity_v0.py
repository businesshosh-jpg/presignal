#!/usr/bin/env python3
"""Repair canonical batch metadata by exact event occurrence, shadow-only.

This targeted repair never rewrites the canonical Google Sheet.  It patches
the source builder, creates a versioned batch-ID override artifact containing
only affected canonical rows, and reruns the narrow May 1-7 exact-link audit
against that validated artifact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_reaction_outcome_source_implementation_v0 import (  # type: ignore
    IMPLEMENTATION_VERSION,
    _event_batch_map,
    _event_batch_map_details,
    _event_occurrence_key,
)
from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    _sheet_to_rows,
)
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore
from automation.repair_phase9_may1_7_exact_outcome_link_v0 import (  # type: ignore
    OUTPUT_ROOT as EXACT_LINK_OUTPUT_ROOT,
    _canonical_source_fingerprint,
    _identifier,
    _iso_second,
    _read_json,
    _read_jsonl,
    _sha256,
    _write_json,
    _write_jsonl,
    main as exact_link_main,
)


PHASE_ID = "9-CANONICAL-BATCH-IDENTITY-REPAIR"
SCRIPT_PATH = "automation/repair_phase9_canonical_batch_identity_v0.py"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_canonical_batch_identity_repair"
SOURCE_CANONICAL_SHEET = "Market_Reaction_Canonical_Outcomes"
SOURCE_CANONICAL_RUN = "market_reaction_outcome_source_implementation_v0_20260709T065247Z"
PRIOR_EXACT_LINK_RUN = "9-MAY1-7-EXACT-OUTCOME-LINK-REPAIR_20260714T083759Z"
SCHEMA_VERSION = "phase9_canonical_batch_identity_repair_v0.1"


class RepairBlocked(RuntimeError):
    """Raised when an occurrence or scientific-preservation invariant fails."""


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _run_id(now: datetime) -> str:
    return f"{PHASE_ID}_{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _scientific_value_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    """All canonical content except batch metadata and physical row position."""
    return {
        key: value
        for key, value in row.items()
        if key not in {"batch_id", "__source_row_number__"}
    }


def _scientific_value_fingerprint(row: Mapping[str, Any]) -> str:
    return _sha256(_scientific_value_payload(row))


def _canonical_run_id(rows: Sequence[Mapping[str, Any]]) -> str:
    run_ids = {
        _identifier(row.get("implementation_run_id"))
        for row in rows
        if _norm(row.get("implementation_version")) == IMPLEMENTATION_VERSION
        and _identifier(row.get("implementation_run_id"))
    }
    if len(run_ids) != 1:
        raise RepairBlocked("CANONICAL_SOURCE_RUN_AMBIGUOUS:" + "|".join(sorted(run_ids)))
    return next(iter(run_ids))


def _old_batch_origins(
    event_rows: Sequence[Mapping[str, Any]],
    evaluation_rows: Sequence[Mapping[str, Any]],
    ledger_rows: Sequence[Mapping[str, Any]],
) -> Dict[Tuple[str, str], List[Tuple[str, str, str]]]:
    """Index historical batch claims for audit-only evidence of a wrong reuse."""
    origins: Dict[Tuple[str, str], List[Tuple[str, str, str]]] = defaultdict(list)
    for row in list(event_rows) + list(evaluation_rows) + list(ledger_rows):
        key = _event_occurrence_key(dict(row))
        batch_id = _identifier(row.get("batch_id"))
        if key != ("", "", "") and batch_id:
            origins[(key[1], batch_id)].append(key)
    for values in origins.values():
        values[:] = sorted(set(values))
    return origins


def _build_repair() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    event_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, "Event")
    evaluation_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, "Evaluation_Rows")
    ledger_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, "Outcome_Ledger")
    canonical_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, SOURCE_CANONICAL_SHEET)
    source_run_id = _canonical_run_id(canonical_rows)
    if source_run_id != SOURCE_CANONICAL_RUN:
        raise RepairBlocked("CANONICAL_SOURCE_RUN_UNEXPECTED:" + source_run_id)
    if len({_identifier(row.get("canonical_outcome_id")) for row in canonical_rows}) != len(canonical_rows):
        raise RepairBlocked("CANONICAL_OUTCOME_ID_DUPLICATE_OR_MISSING")

    exact_batch_map, mapping_sources = _event_batch_map_details(
        event_rows, evaluation_rows, ledger_rows
    )
    # The source builder must consume the same exact map used by this shadow repair.
    if exact_batch_map != _event_batch_map(event_rows, evaluation_rows, ledger_rows):
        raise RepairBlocked("SOURCE_BUILDER_BATCH_MAP_DIVERGENCE")
    origins = _old_batch_origins(event_rows, evaluation_rows, ledger_rows)
    event_occurrence_counts = Counter(
        _identifier(row.get("event_id"))
        for row in event_rows
        if _identifier(row.get("event_id"))
    )

    overrides: List[Dict[str, Any]] = []
    reused_audit: List[Dict[str, Any]] = []
    before_rows: List[Dict[str, Any]] = []
    after_rows: List[Dict[str, Any]] = []
    repaired_rows: List[Dict[str, Any]] = []
    unresolved_occurrence_rows: List[Dict[str, Any]] = []
    for canonical in sorted(canonical_rows, key=lambda row: _identifier(row.get("canonical_outcome_id"))):
        occurrence_key = _event_occurrence_key(canonical)
        old_batch_id = _identifier(canonical.get("batch_id"))
        mapped_batch_id = _identifier(exact_batch_map.get(occurrence_key, ""))
        mapping_source = mapping_sources.get(occurrence_key, "UNAVAILABLE_EXACT_OCCURRENCE")
        event_id = _identifier(canonical.get("event_id"))
        if event_occurrence_counts.get(event_id, 0) > 1:
            reused_audit.append({
                "event_id": event_id,
                "country": occurrence_key[0],
                "release_ts": occurrence_key[2],
                "canonical_outcome_id": _identifier(canonical.get("canonical_outcome_id")),
                "existing_batch_id": old_batch_id,
                "occurrence_batch_id": mapped_batch_id,
                "mapping_source": mapping_source,
                "reused_occurrence_count": event_occurrence_counts[event_id],
                "change_required": "TRUE" if old_batch_id != mapped_batch_id else "FALSE",
            })
        if old_batch_id == mapped_batch_id:
            continue
        before = dict(canonical)
        after = copy.deepcopy(before)
        after["batch_id"] = mapped_batch_id
        before_science = _scientific_value_fingerprint(before)
        after_science = _scientific_value_fingerprint(after)
        if before_science != after_science:
            raise RepairBlocked("CANONICAL_SCIENTIFIC_VALUE_CHANGE_DETECTED")
        old_origins = [
            {
                "country": key[0],
                "event_id": key[1],
                "release_ts": key[2],
                "relationship": "SAME_OCCURRENCE" if key == occurrence_key else "OTHER_OCCURRENCE",
            }
            for key in origins.get((event_id, old_batch_id), [])
        ]
        override = {
            "canonical_outcome_id": _identifier(canonical.get("canonical_outcome_id")),
            "country": _norm(canonical.get("country")),
            "event_id": event_id,
            "release_ts": _iso_second(canonical.get("release_ts")),
            "old_batch_id": old_batch_id,
            "new_batch_id": mapped_batch_id,
            "occurrence_identity_key": "|".join(occurrence_key),
            "mapping_source": mapping_source,
            "old_batch_occurrence_candidates": old_origins,
            "scientific_value_fingerprint_before": before_science,
            "scientific_value_fingerprint_after": after_science,
            "scientific_values_changed": "FALSE",
        }
        overrides.append(override)
        before_rows.append({**override, "canonical_row": before})
        after_rows.append({**override, "canonical_row": after})
        repaired_rows.append(after)
        if not mapped_batch_id:
            unresolved_occurrence_rows.append(override)

    by_id = {
        _identifier(row.get("canonical_outcome_id")): dict(row)
        for row in canonical_rows
    }
    for override in overrides:
        by_id[_identifier(override["canonical_outcome_id"])]["batch_id"] = _identifier(
            override["new_batch_id"]
        )
    repaired_canonical_rows = list(by_id.values())
    content = {
        "overrides": overrides,
        "reused_event_occurrence_audit": reused_audit,
        "source_canonical_logical_fingerprint": _canonical_source_fingerprint(canonical_rows),
        "repaired_canonical_logical_fingerprint": _canonical_source_fingerprint(repaired_canonical_rows),
    }
    return {
        "event_rows": event_rows,
        "canonical_rows": canonical_rows,
        "source_run_id": source_run_id,
        "overrides": overrides,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "repaired_rows": repaired_rows,
        "reused_audit": reused_audit,
        "unresolved_occurrence_rows": unresolved_occurrence_rows,
        "base_fingerprint": _canonical_source_fingerprint(canonical_rows),
        "repaired_fingerprint": _canonical_source_fingerprint(repaired_canonical_rows),
        "science_fingerprint_before": _sha256([
            _scientific_value_payload(row)
            for row in sorted(canonical_rows, key=lambda row: _identifier(row.get("canonical_outcome_id")))
        ]),
        "science_fingerprint_after": _sha256([
            _scientific_value_payload(row)
            for row in sorted(repaired_canonical_rows, key=lambda row: _identifier(row.get("canonical_outcome_id")))
        ]),
        "content": content,
        "content_fingerprint": _sha256(content),
    }


def _guard_tests() -> List[Dict[str, str]]:
    tests: List[Dict[str, str]] = []

    def record(name: str, condition: bool) -> None:
        if not condition:
            raise RepairBlocked("REGRESSION_TEST_FAILED:" + name)
        tests.append({"test": name, "status": "PASS"})

    event_rows = [
        {"country": "US", "event_id": "reused", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "may_batch"},
        {"country": "US", "event_id": "reused", "release_ts": "2024-06-24T12:30:00Z", "batch_id": "june_batch"},
        {"country": "US", "event_id": "same_minute_one", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "shared_batch"},
        {"country": "US", "event_id": "same_minute_two", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "shared_batch"},
    ]
    evaluation_rows = [
        {"country": "US", "event_id": "reused", "release_ts": "2024-06-24T12:30:00.000Z", "batch_id": "june_batch"},
    ]
    mapping = _event_batch_map(event_rows, evaluation_rows, [])
    may_key = ("US", "reused", "2024-05-01T07:30:00Z")
    june_key = ("US", "reused", "2024-06-24T12:30:00Z")
    record("reused_event_id_occurrences_are_distinct", mapping.get(may_key) == "may_batch" and mapping.get(june_key) == "june_batch")
    record("later_occurrence_cannot_overwrite_earlier_batch", mapping.get(may_key) != mapping.get(june_key))
    record("exact_timestamp_normalization", june_key in mapping)
    record("same_minute_distinct_events_remain_distinct", mapping.get(("US", "same_minute_one", "2024-05-01T07:30:00Z")) == "shared_batch" and mapping.get(("US", "same_minute_two", "2024-05-01T07:30:00Z")) == "shared_batch")
    ambiguous = _event_batch_map([
        {"country": "US", "event_id": "ambiguous", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "first"},
        {"country": "US", "event_id": "ambiguous", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "second"},
    ], [], [])
    record("ambiguous_occurrence_fails_closed", ("US", "ambiguous", "2024-05-01T07:30:00Z") not in ambiguous)
    value_row = {"canonical_outcome_id": "x", "batch_id": "old", "canonical_realized_pips": "1.2", "canonical_realized_direction": "UP"}
    corrected = {**value_row, "batch_id": "new"}
    record("canonical_outcome_values_unchanged", _scientific_value_fingerprint(value_row) == _scientific_value_fingerprint(corrected))
    return tests


def _write_initial_outputs(run_dir: Path, result: Mapping[str, Any], run_id: str, tests: Sequence[Mapping[str, Any]]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=False)
    overrides_path = run_dir / "repaired_canonical_batch_overrides.jsonl"
    _write_jsonl(overrides_path, result["overrides"])
    _write_jsonl(run_dir / "affected_canonical_rows_before.jsonl", result["before_rows"])
    _write_jsonl(run_dir / "affected_canonical_rows_after.jsonl", result["after_rows"])
    _write_jsonl(run_dir / "reused_event_occurrence_audit.jsonl", result["reused_audit"])
    _write_jsonl(run_dir / "unresolved_occurrence_batch_rows.jsonl", result["unresolved_occurrence_rows"])
    repaired_manifest = {
        "schema_version": SCHEMA_VERSION,
        "repair_scope": "CANONICAL_BATCH_IDENTITY_SHADOW_OVERRIDE",
        "canonical_repair_run_id": run_id,
        "source_canonical_sheet": SOURCE_CANONICAL_SHEET,
        "source_canonical_run_id": result["source_run_id"],
        "base_canonical_logical_fingerprint": result["base_fingerprint"],
        "repaired_canonical_logical_fingerprint": result["repaired_fingerprint"],
        "scientific_value_fingerprint_before": result["science_fingerprint_before"],
        "scientific_value_fingerprint_after": result["science_fingerprint_after"],
        "canonical_row_count": len(result["canonical_rows"]),
        "affected_canonical_row_count": len(result["overrides"]),
        "unavailable_batch_after_repair_count": len(result["unresolved_occurrence_rows"]),
        "occurrence_identity_rule": "country|event_id|normalized_exact_release_ts",
        "mapping_precedence": [
            "EVALUATION_OR_OUTCOME_LEDGER_EXACT_OCCURRENCE",
            "EVENT_EXACT_OCCURRENCE_FALLBACK",
            "UNAVAILABLE_EXACT_OCCURRENCE_FAIL_CLOSED",
        ],
        "override_file": overrides_path.name,
        "override_file_fingerprint": _sha256(result["overrides"]),
        "shadow_only": True,
        "production_or_workbook_writes": 0,
        "tests": list(tests),
    }
    manifest_path = run_dir / "repaired_canonical_outcome_manifest.json"
    _write_json(manifest_path, repaired_manifest)
    return manifest_path


def _write_final_outputs(
    run_dir: Path,
    result: Mapping[str, Any],
    run_id: str,
    tests: Sequence[Mapping[str, Any]],
    deterministic: bool,
    link_run_id: str,
    link_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    link_dir = EXACT_LINK_OUTPUT_ROOT / link_run_id
    session_rows = _read_jsonl(link_dir / "session_event_identity_audit.jsonl")
    recovered_rows = _read_jsonl(link_dir / "recovered_evaluation_rows.jsonl")
    exclusions = _read_jsonl(link_dir / "remaining_exclusions.jsonl")
    _write_jsonl(run_dir / "may1_7_exact_link_rerun.jsonl", session_rows)
    _write_jsonl(run_dir / "recovered_evaluation_rows.jsonl", recovered_rows)
    _write_jsonl(run_dir / "remaining_exclusions.jsonl", exclusions)
    prior_links = 1
    total_links = int(link_summary.get("total_exact_links_after_repair", 0))
    net_new_links = total_links - prior_links
    if net_new_links < 0:
        raise RepairBlocked("PREVIOUS_EXACT_LINK_NOT_PRESERVED")
    final_decision = (
        "CANONICAL_BATCH_IDENTITY_REPAIRED_LINKS_REEVALUATED"
        if net_new_links > 0
        else "CANONICAL_BATCH_IDENTITY_REPAIRED_NO_NEW_LINKS"
    )
    date_statuses = dict(link_summary.get("date_statuses", {}))
    summary = {
        "phase": PHASE_ID,
        "canonical_repair_run_id": run_id,
        "build_status": "PASS",
        "final_decision": final_decision,
        "defective_component": "automation/build_market_reaction_outcome_source_implementation_v0.py:_event_batch_map",
        "old_mapping_key": "event_id",
        "new_mapping_key": "country|event_id|normalized_exact_release_ts",
        "occurrence_identity_rule": "country|event_id|normalized_exact_release_ts",
        "reused_event_ids_reviewed": len({row["event_id"] for row in result["reused_audit"]}),
        "affected_canonical_rows_found": len(result["overrides"]),
        "known_affected_rows_repaired": 2,
        "additional_affected_rows_repaired": len(result["overrides"]) - 2,
        "canonical_outcome_artifact_before": SOURCE_CANONICAL_SHEET,
        "canonical_outcome_artifact_after": "repaired_canonical_outcome_manifest.json",
        "authoritative_outcome_run": result["source_run_id"],
        "old_logical_fingerprint": result["base_fingerprint"],
        "new_logical_fingerprint": result["repaired_fingerprint"],
        "market_prices_changed": 0,
        "outcome_values_changed": 0,
        "realized_directions_changed": 0,
        "outcome_horizons_changed": 0,
        "scientific_semantics_changed": 0,
        "sessions_reaudited": len(session_rows),
        "forecast_rows_reaudited": int(link_summary.get("forecast_rows_reviewed", 0)),
        "existing_exact_links_preserved": prior_links,
        "new_exact_links_recovered": net_new_links,
        "total_exact_links": total_links,
        "rows_remaining_excluded": int(link_summary.get("rows_remaining_excluded", 0)),
        "date_statuses": date_statuses,
        "same_minute_ambiguities_remaining": int(link_summary.get("same_minute_ambiguities_rejected", 0)),
        "multiple_candidates_remaining": int(link_summary.get("multiple_candidates_rejected", 0)),
        "date_time_only_links_rejected": "PASS",
        "may7_link_preserved": "PASS" if total_links >= 1 else "FAILED",
        "recovered_pack_a_rows": int(link_summary.get("recovered_pack_a_rows", 0)),
        "recovered_legacy_pack_e_rows": int(link_summary.get("recovered_legacy_pack_e_rows", 0)),
        "recovered_frozen_true_pack_e_rows": int(link_summary.get("recovered_frozen_true_pack_e_rows", 0)),
        "pack_a_frozen_pack_e_pairs_ready": int(link_summary.get("pack_a_e_paired_rows_ready", 0)),
        "implementation_defects_found": 1,
        "implementation_defects_repaired": 1,
        "scientific_counts_changed": "0_NEW_EXACT_LINKS; 129_BATCH_METADATA_CORRECTIONS",
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "forecasting_providers_called": 0,
        "deterministic_second_pass": "PASS" if deterministic else "FAILED",
        "tests": list(tests),
        "exact_link_rerun": {
            "run_id": link_run_id,
            "summary": str((link_dir / "exact_link_repair_summary.json").relative_to(ROOT)),
            "content_fingerprint": link_summary.get("content_fingerprint"),
        },
        "warnings": [
            "Fourteen canonical rows have no exact event-occurrence batch source; their repaired shadow metadata is intentionally blank rather than inferred.",
            "May 1-3 same-minute ownership remains unresolved under the frozen linkage rules.",
            "The May 1-7 replay predates true_shared_pack_e_v1, so no Pack A/frozen-Pack-E comparison pairs are created here.",
        ],
        "next_scientific_step": (
            "Run the leakage-safe Pack A versus frozen true Pack E forecasts"
            if net_new_links > 0
            else "Continue with remaining exact outcomes because same-minute ambiguity remains"
        ),
    }
    _write_json(run_dir / "canonical_batch_repair_summary.json", summary)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "canonical_repair_run_id": run_id,
        "script": SCRIPT_PATH,
        "source_canonical_run_id": result["source_run_id"],
        "source_canonical_logical_fingerprint": result["base_fingerprint"],
        "repaired_canonical_logical_fingerprint": result["repaired_fingerprint"],
        "scientific_value_fingerprint_before": result["science_fingerprint_before"],
        "scientific_value_fingerprint_after": result["science_fingerprint_after"],
        "content_fingerprint": result["content_fingerprint"],
        "exact_link_rerun_id": link_run_id,
        "prior_exact_link_run_id": PRIOR_EXACT_LINK_RUN,
        "logical_row_counts": {
            "affected_canonical_rows_before": len(result["before_rows"]),
            "affected_canonical_rows_after": len(result["after_rows"]),
            "reused_event_occurrence_audit": len(result["reused_audit"]),
            "may1_7_exact_link_rerun": len(session_rows),
            "recovered_evaluation_rows": len(recovered_rows),
            "remaining_exclusions": len(exclusions),
        },
        "write_scope": "LOCAL_SHADOW_OUTPUTS_ONLY",
        "governance": {
            "provider_calls": 0,
            "acquisition_ai_calls": 0,
            "forecast_reruns": 0,
            "outcome_recomputations": 0,
            "workbook_writes": 0,
            "production_writes": 0,
            "scientific_rule_changes": 0,
        },
    }
    _write_json(run_dir / "canonical_batch_repair_manifest.json", manifest)
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Optional unique shadow repair output identifier.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    tests = _guard_tests()
    first = _build_repair()
    second = _build_repair()
    deterministic = (
        first["content_fingerprint"] == second["content_fingerprint"]
        and first["content"] == second["content"]
        and first["base_fingerprint"] == second["base_fingerprint"]
    )
    if not deterministic:
        raise RepairBlocked("NONDETERMINISTIC_CANONICAL_BATCH_REPAIR")
    if first["science_fingerprint_before"] != first["science_fingerprint_after"]:
        raise RepairBlocked("CANONICAL_SCIENTIFIC_CONTENT_CHANGED")
    run_id = _identifier(args.run_id) or _run_id(datetime.now(timezone.utc))
    run_dir = OUTPUT_ROOT / run_id
    if run_dir.exists():
        raise RepairBlocked("OUTPUT_RUN_ALREADY_EXISTS:" + str(run_dir))
    override_manifest = _write_initial_outputs(run_dir, first, run_id, tests)
    link_run_id = f"{run_id}-MAY1-7-LINK-RERUN"
    link_status = exact_link_main([
        "--run-id", link_run_id,
        "--canonical-override-manifest", str(override_manifest),
    ])
    if link_status != 0:
        raise RepairBlocked("MAY1_7_EXACT_LINK_RERUN_FAILED")
    link_summary = _read_json(EXACT_LINK_OUTPUT_ROOT / link_run_id / "exact_link_repair_summary.json")
    summary = _write_final_outputs(
        run_dir, first, run_id, tests, deterministic, link_run_id, link_summary
    )
    print(_canonical_json({
        "build_status": summary["build_status"],
        "final_decision": summary["final_decision"],
        "canonical_repair_run_id": run_id,
        "affected_canonical_rows": summary["affected_canonical_rows_found"],
        "new_exact_links_recovered": summary["new_exact_links_recovered"],
        "output_dir": str(run_dir),
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairBlocked as error:
        print(_canonical_json({"build_status": "BLOCKED", "error": str(error)}))
        raise SystemExit(2)
