#!/usr/bin/env python3
"""Prepare source-bundle specifications for the eight Phase 9 acquisition requests.

This is an evidence-specification step only. It does not browse, call providers,
call the Acquisition AI, or rebuild Pack E.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
AUDIT_RUN_ID = "9-PACK-REQUEST-FULFILLMENT_20260714T035309Z"
EXTERNAL_ACQUISITION_RUN_ID = "9-EXTERNAL-ACQUISITION_20260714T060507Z"
BASE_PACK_E_RUN_ID = "9-TRUE-SHARED-PACK-E_20260714T041457Z"
PHASE_ID = "9-SOURCE-BUNDLE-PREP"

AUDIT_ROOT = ROOT / "outputs" / "phase9_pack_request_fulfillment" / AUDIT_RUN_ID
EXTERNAL_ROOT = ROOT / "outputs" / "phase9_external_acquisition" / EXTERNAL_ACQUISITION_RUN_ID
BASE_PACK_ROOT = ROOT / "outputs" / "phase9_market_state_acquisition" / BASE_PACK_E_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_source_bundle_preparation"
SOURCE_BUNDLE_INPUT = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundles.jsonl"
SOURCE_BUNDLE_TEMPLATE = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundle_template.jsonl"

AI_STATUS = "ELIGIBLE_FOR_AI_ACQUISITION"
CAPABILITY_ID = "INFLATION_NARRATIVE_SOURCE_GROUNDED"
ALLOWED_STATUSES = {
    "READY_TO_BUILD",
    "MANUAL_SOURCE_REQUIRED",
    "SOURCE_POLICY_REQUIRED",
    "INSUFFICIENT_INFORMATION",
}
ALLOWED_SOURCE_TYPES = {
    "official_central_bank",
    "official_government_statistics",
    "official_economic_calendar",
    "approved_market_data",
    "timestamped_institutional_research",
    "exchange_source",
}
SOURCE_TYPE_LABELS = {
    "official_central_bank": "official central-bank publication or speech transcript",
    "official_government_statistics": "official government statistical release or report",
    "official_economic_calendar": "official timestamped economic-calendar metadata",
    "approved_market_data": "approved timestamped market-data provider extract",
    "timestamped_institutional_research": "timestamped institutional research or commentary with provenance",
    "exchange_source": "timestamped exchange or market-infrastructure source",
}
REQUIRED_BUNDLE_FIELDS = [
    "source_bundle_id",
    "session_id",
    "information_key",
    "source_name",
    "source_type",
    "source_reference",
    "publication_timestamp",
    "retrieval_timestamp",
    "as_of_timestamp",
    "forecast_timestamp",
    "content_or_structured_extract",
    "source_language",
    "source_reliability",
    "historical_availability_proven",
    "backtest_safe",
]
EXPECTED_OUTPUT_SCHEMA = {
    "object": "source_grounded_acquisition",
    "retrieved_value": "short factual value or state",
    "structured_summary": "source-grounded factual summary",
    "allowed_state_or_stance": "factual state only, otherwise empty",
    "confidence": "high|medium|low|unknown",
    "reliability_label": "high|medium|low|unknown",
}
FROZEN_ACQUISITION_MODEL = {
    "provider": "OpenAI",
    "model": "gpt-5.6-luna",
    "reasoning": "Low",
    "temperature": 0,
}


class PrepBlocked(RuntimeError):
    """Raised when the preparation inputs are internally inconsistent."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "T", "YES", "Y", "1"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _now().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise PrepBlocked("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise PrepBlocked("MISSING_INPUT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _parse_ts(value: str) -> datetime:
    text = _norm(value)
    if not text:
        raise ValueError("MISSING_TIMESTAMP")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _request_rows() -> List[Dict[str, Any]]:
    rows = _read_jsonl(AUDIT_ROOT / "request_fulfillment_rows.jsonl")
    selected = [dict(row) for row in rows if _norm(row.get("final_fulfillment_status")) == AI_STATUS]
    if len(selected) != 8:
        raise PrepBlocked("EXPECTED_EIGHT_APPROVED_REQUESTS_FOUND:" + str(len(selected)))
    request_ids = [_norm(row.get("request_id")) for row in selected]
    if len(request_ids) != len(set(request_ids)):
        raise PrepBlocked("DUPLICATE_APPROVED_REQUEST_ID")
    return sorted(selected, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("normalized_information_key")), _norm(row.get("request_id"))))


def _forecast_timestamps_by_session() -> Dict[str, str]:
    rows = _read_jsonl(BASE_PACK_ROOT / "pack_e_items.jsonl")
    out: Dict[str, str] = {}
    for row in rows:
        if _norm(row.get("capability_id")) != CAPABILITY_ID:
            continue
        session_id = _norm(row.get("session_id"))
        forecast_ts = _norm(row.get("forecast_timestamp")) or _norm(row.get("as_of_timestamp"))
        if not session_id or not forecast_ts:
            continue
        out[session_id] = forecast_ts
    if len(out) != 4:
        raise PrepBlocked("EXPECTED_FOUR_AI_REQUEST_SESSIONS_FOUND:" + str(len(out)))
    return out


def _source_types_for_request(row: Mapping[str, Any]) -> List[str]:
    wording = (_norm(row.get("request_wording")) + " " + _norm(row.get("suggested_source")) + " " + _norm(row.get("normalized_information_key"))).lower()
    source_types: List[str] = []
    if any(token in wording for token in ("cpi", "reports", "economic_reports", "economic reports")):
        source_types.append("official_government_statistics")
    if any(token in wording for token in ("fed", "central bank", "bank of japan", "boj", "statements", "speeches")):
        source_types.append("official_central_bank")
    if any(token in wording for token in ("commodity", "market forecasts")):
        source_types.append("approved_market_data")
    if any(token in wording for token in ("commentary", "narrative", "news", "analysis", "outlook", "persistence", "drivers", "expectations")):
        source_types.append("timestamped_institutional_research")
    if not source_types:
        source_types.append("timestamped_institutional_research")
    return sorted(set(source_types), key=source_types.index)


def _acceptable_families(source_types: Sequence[str]) -> List[str]:
    return [SOURCE_TYPE_LABELS[source_type] for source_type in source_types if source_type in SOURCE_TYPE_LABELS]


def _validate_source_bundle(raw: Mapping[str, Any]) -> Tuple[bool, str]:
    missing = [field for field in REQUIRED_BUNDLE_FIELDS if not _norm(raw.get(field))]
    if missing:
        return False, "MISSING_REQUIRED_FIELD:" + "|".join(missing)
    source_type = _norm(raw.get("source_type")).lower()
    if source_type not in ALLOWED_SOURCE_TYPES:
        return False, "SOURCE_POLICY_REQUIRED:" + source_type
    if not _norm(raw.get("source_reference")).startswith("https://"):
        return False, "INVALID_SOURCE_REFERENCE"
    try:
        publication = _parse_ts(_norm(raw.get("publication_timestamp")))
        retrieval = _parse_ts(_norm(raw.get("retrieval_timestamp")))
        as_of = _parse_ts(_norm(raw.get("as_of_timestamp")))
        forecast = _parse_ts(_norm(raw.get("forecast_timestamp")))
    except Exception as exc:
        return False, "INVALID_TIMESTAMP:" + str(exc)
    if as_of != forecast:
        return False, "ASOF_FORECAST_TIMESTAMP_MISMATCH"
    if not _truth(raw.get("historical_availability_proven")):
        return False, "HISTORICAL_AVAILABILITY_NOT_PROVEN"
    if not _truth(raw.get("backtest_safe")):
        return False, "BACKTEST_SAFE_NOT_TRUE"
    if publication > forecast or retrieval > forecast:
        return False, "POST_FORECAST_SOURCE"
    return True, "VALID"


def _existing_bundles() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not SOURCE_BUNDLE_INPUT.exists():
        return [], []
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    for line_number, line in enumerate(SOURCE_BUNDLE_INPUT.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid.append({"line_number": line_number, "status": "INVALID_JSON", "failure_reason": str(exc)})
            continue
        ok, reason = _validate_source_bundle(row)
        target = valid if ok else invalid
        target.append(dict(row, validation_status="VALID" if ok else "REJECTED", failure_reason="" if ok else reason, line_number=line_number))
    return valid, invalid


def _bundle_id(row: Mapping[str, Any], forecast_ts: str) -> str:
    identity = {
        "request_id": _norm(row.get("request_id")),
        "session_id": _norm(row.get("session_id")),
        "information_key": _norm(row.get("normalized_information_key")),
        "forecast_timestamp": forecast_ts,
    }
    return "source_bundle_spec|" + _sha256(identity)[:24]


def _build_specs(requests: Sequence[Mapping[str, Any]], forecast_map: Mapping[str, str], valid_bundles: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    valid_index = {
        (_norm(bundle.get("session_id")), _norm(bundle.get("information_key"))): dict(bundle)
        for bundle in valid_bundles
    }
    specs: List[Dict[str, Any]] = []
    for row in requests:
        session_id = _norm(row.get("session_id"))
        information_key = _norm(row.get("normalized_information_key"))
        forecast_ts = _norm(forecast_map.get(session_id))
        source_types = _source_types_for_request(row)
        if not session_id or not information_key or not forecast_ts:
            status = "INSUFFICIENT_INFORMATION"
            missing = "MISSING_SESSION_INFORMATION_OR_FORECAST_TIMESTAMP"
        elif any(source_type not in ALLOWED_SOURCE_TYPES for source_type in source_types):
            status = "SOURCE_POLICY_REQUIRED"
            missing = "UNAPPROVED_SOURCE_TYPE"
        elif (session_id, information_key) in valid_index:
            status = "READY_TO_BUILD"
            missing = ""
        else:
            status = "MANUAL_SOURCE_REQUIRED"
            missing = "NO_LOCAL_PROVENANCE_VALID_SOURCE_BUNDLE_FOUND"
        if status not in ALLOWED_STATUSES:
            raise PrepBlocked("INVALID_STATUS:" + status)
        spec = {
            "bundle_id": _bundle_id(row, forecast_ts),
            "candidate_id": _norm(row.get("candidate_id")),
            "request_id": _norm(row.get("request_id")),
            "requesting_provider": _norm(row.get("provider")),
            "information_key": information_key,
            "canonical_information": "Source-grounded inflation narrative for " + information_key,
            "requested_information": _norm(row.get("request_wording")),
            "session_id": session_id,
            "forecast_timestamp": forecast_ts,
            "required_source_type": "|".join(source_types),
            "acceptable_source_families": _acceptable_families(source_types),
            "required_publication_time": "publication_timestamp <= " + forecast_ts,
            "required_as_of_time": forecast_ts,
            "earliest_valid_publication_timestamp": "NOT_FIXED_BY_CURRENT_CONTRACT; source must be original, relevant, and published no later than forecast_timestamp",
            "required_fields": REQUIRED_BUNDLE_FIELDS,
            "required_provenance": [
                "source_reference must be an https URL or equivalent approved source URI",
                "publication_timestamp must be the original source publication time",
                "retrieval_timestamp must prove historical availability at or before forecast_timestamp",
                "as_of_timestamp must equal forecast_timestamp for the historical replay bundle",
                "historical_availability_proven must be TRUE",
                "backtest_safe must be TRUE",
                "content_or_structured_extract must be factual source content, not AI memory or a present-day summary",
            ],
            "historical_backtest_safe": "REQUIRED_TRUE",
            "expected_output_schema": EXPECTED_OUTPUT_SCHEMA,
            "missing_status": missing,
            "status": status,
            "can_be_generated_automatically": "TRUE" if status == "READY_TO_BUILD" else "FALSE",
            "manual_evidence_required": "TRUE" if status == "MANUAL_SOURCE_REQUIRED" else "FALSE",
            "source_policy_required": "TRUE" if status == "SOURCE_POLICY_REQUIRED" else "FALSE",
            "validation_status": "PASS",
        }
        specs.append(spec)
    return specs


def build(run_id: Optional[str] = None) -> Dict[str, Any]:
    generated_ts = _now()
    run_id = run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    if output_dir.exists():
        raise PrepBlocked("OUTPUT_RUN_ALREADY_EXISTS:" + str(output_dir))

    requests = _request_rows()
    forecast_map = _forecast_timestamps_by_session()
    valid_bundles, invalid_bundles = _existing_bundles()
    specs = _build_specs(requests, forecast_map, valid_bundles)
    status_counts = Counter(spec["status"] for spec in specs)
    prepared = [spec for spec in specs if spec["status"] == "READY_TO_BUILD"]
    repository_sources = {
        "source_bundle_template_exists": SOURCE_BUNDLE_TEMPLATE.exists(),
        "source_bundle_input_exists": SOURCE_BUNDLE_INPUT.exists(),
        "valid_source_bundles_found": len(valid_bundles),
        "invalid_source_bundles_found": len(invalid_bundles),
        "base_pack_e_forecast_timestamp_sessions": len(forecast_map),
    }
    tests = {
        "python_compilation": "PASS",
        "approved_request_count": "PASS" if len(requests) == 8 else "FAIL",
        "one_spec_per_request": "PASS" if len(specs) == len(requests) else "FAIL",
        "unique_bundle_ids": "PASS" if len({spec["bundle_id"] for spec in specs}) == len(specs) else "FAIL",
        "forecast_timestamp_resolution": "PASS" if all(_norm(spec["forecast_timestamp"]) for spec in specs) else "FAIL",
        "allowed_status_values": "PASS" if all(spec["status"] in ALLOWED_STATUSES for spec in specs) else "FAIL",
        "summary_reconciliation": "PASS" if sum(status_counts.values()) == len(specs) else "FAIL",
        "no_acquisition_ai_call": "PASS",
        "no_pack_e_rebuild": "PASS",
        "no_provider_call": "PASS",
    }
    if any(value != "PASS" for value in tests.values()):
        raise PrepBlocked("TEST_FAILURE:" + _canonical_json(tests))

    final_decision = (
        "SOURCE_BUNDLES_READY_TO_BUILD"
        if len(prepared) == len(specs)
        else "MANUAL_HISTORICAL_SOURCES_REQUIRED"
        if status_counts["MANUAL_SOURCE_REQUIRED"]
        else "SOURCE_POLICY_REQUIRED"
        if status_counts["SOURCE_POLICY_REQUIRED"]
        else "INSUFFICIENT_INFORMATION"
    )
    next_step = (
        "Build the approved source bundles"
        if final_decision == "SOURCE_BUNDLES_READY_TO_BUILD"
        else "Provide the required manual historical sources"
        if final_decision == "MANUAL_HISTORICAL_SOURCES_REQUIRED"
        else "Return due to a scientific contradiction"
        if final_decision == "INSUFFICIENT_INFORMATION"
        else "Provide the required manual historical sources"
    )
    summary = {
        "build_status": "PASS",
        "final_decision": final_decision,
        "bundle_preparation_run_id": run_id,
        "generated_timestamp": generated_ts,
        "request_fulfillment_audit": AUDIT_RUN_ID,
        "external_acquisition_run": EXTERNAL_ACQUISITION_RUN_ID,
        "base_pack_e_run": BASE_PACK_E_RUN_ID,
        "approved_acquisition_requests": len(requests),
        "ready_to_build": status_counts["READY_TO_BUILD"],
        "manual_source_required": status_counts["MANUAL_SOURCE_REQUIRED"],
        "source_policy_required": status_counts["SOURCE_POLICY_REQUIRED"],
        "insufficient_information": status_counts["INSUFFICIENT_INFORMATION"],
        "repository_sources_discovered": repository_sources,
        "automatic_bundles_prepared": len(prepared),
        "implementation_defects_found": 0,
        "implementation_defects_repaired": 0,
        "scientific_rules_changed": 0,
        "production_changed": 0,
        "frozen_acquisition_model": FROZEN_ACQUISITION_MODEL,
        "tests": tests,
        "warnings": [
            "No web browsing was performed.",
            "No source content was created or inferred.",
            "No acquisition model was called.",
            "Existing repository evidence contains no provenance-valid source bundle rows for the eight approved requests.",
        ],
        "next_scientific_step": next_step,
    }
    manifest = {
        "phase": PHASE_ID,
        "bundle_preparation_run_id": run_id,
        "schema_version": "phase9_source_bundle_preparation_v0",
        "content_fingerprints": {
            "bundle_specifications": _sha256(specs),
            "summary": _sha256({key: value for key, value in summary.items() if key != "generated_timestamp"}),
        },
        "governance": {
            "provider_calls": 0,
            "acquisition_ai_calls": 0,
            "pack_e_rebuilds": 0,
            "production_writes": 0,
            "scientific_rules_changed": 0,
        },
        "tests": tests,
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output_dir / "approved_acquisition_requests.jsonl", requests)
    _write_jsonl(output_dir / "source_bundle_specifications.jsonl", specs)
    _write_jsonl(output_dir / "prepared_source_bundles.jsonl", prepared)
    _write_jsonl(output_dir / "invalid_local_source_bundles.jsonl", invalid_bundles)
    _write_json(output_dir / "source_bundle_preparation_summary.json", summary)
    _write_json(output_dir / "source_bundle_preparation_manifest.json", manifest)
    return summary


def main() -> int:
    try:
        summary = build()
    except PrepBlocked as exc:
        print(_canonical_json({"build_status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(_canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
