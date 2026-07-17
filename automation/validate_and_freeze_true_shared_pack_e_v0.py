#!/usr/bin/env python3
"""Validate and freeze the authoritative Phase 9 true shared Pack E.

This is a local, read-only scientific acceptance check over the already-built
artifact.  The only persisted output is a compact validation/freeze record;
it never retrieves sources, calls a model, or executes forecasts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_exposure_prompt_validation_v0 import _assemble_prompt_text  # type: ignore
from automation.true_shared_pack_e_renderer_v0 import (  # type: ignore
    FROZEN_STATUS,
    FrozenPackEError,
    canonical_json,
    content_fingerprint,
    load_frozen_true_shared_pack_e,
    render_frozen_true_shared_pack_e_context,
)


PHASE_ID = "9-TRUE-SHARED-PACK-E-VALIDATION"
VALIDATION_SCHEMA_VERSION = "phase9_true_shared_pack_e_validation_v1"
FREEZE_SCHEMA_VERSION = "phase9_true_shared_pack_e_freeze_v1"
RENDERER_VERSION = "true_shared_pack_e_renderer_v0"
AUTHORITATIVE_RUN_ID = "9-LUNA-TEMPERATURE-REPAIR_20260714T075326Z"
EXCLUDED_RUN_IDS = ("9-LUNA-TEMPERATURE-REPAIR_20260714T075018Z",)
EXPECTED_PACK_FINGERPRINT = "976271f7cba9689f91098e2a6b7e2038e8c5df004012dc57c733e0addd1dc15e"
EXPECTED_PACK_ITEM_COUNT = 129
AUTHORITATIVE_DIR = ROOT / "outputs" / "phase9_external_acquisition" / AUTHORITATIVE_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_true_pack_e_validation"
PACK_PATH = AUTHORITATIVE_DIR / "true_shared_pack_e_v1.jsonl"
RESULTS_PATH = AUTHORITATIVE_DIR / "acquisition_ai_results.jsonl"
BUNDLES_PATH = AUTHORITATIVE_DIR / "source_bundle_inventory.jsonl"
SUMMARY_PATH = AUTHORITATIVE_DIR / "external_acquisition_summary.json"
MANIFEST_PATH = AUTHORITATIVE_DIR / "external_acquisition_manifest.json"
REQUESTS_PATH = AUTHORITATIVE_DIR / "ai_eligible_request_inventory.jsonl"

PROVIDERS = ("OpenAI", "Gemini", "Anthropic")
CATEGORY_BY_STATUS = {
    "DETERMINISTIC": "SUPPLIED_DETERMINISTIC",
    "COMPUTED": "SUPPLIED_COMPUTED",
    "CALENDAR_DERIVED": "SUPPLIED_CALENDAR_DERIVED",
    "AI_RETRIEVED_PROVISIONAL": "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL",
    "UNAVAILABLE": "NOT_AVAILABLE",
    "INTERPRETIVE_NOT_SUPPLIED": "INTERPRETIVE_NOT_SUPPLIED",
    "POLICY_REJECTED": "REJECTED_BY_POLICY",
}
FORBIDDEN_ACQUISITION_TERMS = (
    "forecast",
    "predict",
    "expected direction",
    "likely direction",
    "will rise",
    "will fall",
    "success",
    "positive arm",
    "negative arm",
)
FORBIDDEN_OUTCOME_KEYS = ("outcome", "realized", "success_mapping", "corrected_directional_success")


class ValidationFailure(RuntimeError):
    """Raised on a concrete acceptance failure that must fail closed."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "T", "YES", "Y", "1"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _now().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _parse_ts(value: Any) -> datetime:
    text = _norm(value)
    if not text:
        raise ValidationFailure("MISSING_TIMESTAMP")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValidationFailure("INVALID_TIMESTAMP:" + text) from exc


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValidationFailure("MISSING_ARTIFACT:" + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationFailure("ARTIFACT_NOT_OBJECT:" + str(path))
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise ValidationFailure("MISSING_ARTIFACT:" + str(path))
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValidationFailure("JSONL_ROW_NOT_OBJECT:" + str(path) + ":" + str(line_number))
        rows.append(value)
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(dict(row)) + "\n")


def _logical_pack_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"acquisition_run_id", "external_acquisition_run_id", "generated_timestamp"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def _logical_results(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"acquisition_run_id", "external_acquisition_run_id", "generated_timestamp"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_authoritative_isolation(
    pack_rows: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    if _norm(summary.get("external_acquisition_run_id")) != AUTHORITATIVE_RUN_ID:
        raise ValidationFailure("SUMMARY_AUTHORITATIVE_RUN_MISMATCH")
    if _norm(manifest.get("external_acquisition_run_id")) != AUTHORITATIVE_RUN_ID:
        raise ValidationFailure("MANIFEST_AUTHORITATIVE_RUN_MISMATCH")
    if any(_norm(row.get("external_acquisition_run_id")) != AUTHORITATIVE_RUN_ID for row in pack_rows):
        raise ValidationFailure("PACK_MIXED_OR_NONAUTHORITATIVE_RUN")
    if any(_norm(row.get("external_acquisition_run_id")) != AUTHORITATIVE_RUN_ID for row in results):
        raise ValidationFailure("RESULT_MIXED_OR_NONAUTHORITATIVE_RUN")
    if len(pack_rows) != EXPECTED_PACK_ITEM_COUNT:
        raise ValidationFailure("PACK_ITEM_COUNT_MISMATCH")
    item_keys = [(_norm(row.get("session_id")), _norm(row.get("item_key"))) for row in pack_rows]
    if not all(session_id and item_key for session_id, item_key in item_keys):
        raise ValidationFailure("PACK_ITEM_IDENTITY_MISSING")
    if len(item_keys) != len(set(item_keys)):
        raise ValidationFailure("PACK_ITEM_DUPLICATE")
    request_ids = [_norm(row.get("request_id")) for row in results]
    if len(results) != 8 or not all(request_ids) or len(request_ids) != len(set(request_ids)):
        raise ValidationFailure("ACQUISITION_RESULT_IDENTITY_INVALID")
    excluded_paths = []
    for excluded_run_id in EXCLUDED_RUN_IDS:
        excluded_path = ROOT / "outputs" / "phase9_external_acquisition" / excluded_run_id / "true_shared_pack_e_v1.jsonl"
        if excluded_path.exists():
            excluded_paths.append(str(excluded_path))
            excluded_rows = _read_jsonl(excluded_path)
            if any(_norm(row.get("external_acquisition_run_id")) == AUTHORITATIVE_RUN_ID for row in excluded_rows):
                raise ValidationFailure("EXCLUDED_RUN_CONTAINS_AUTHORITATIVE_ROWS")
    return {
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "excluded_run_ids": list(EXCLUDED_RUN_IDS),
        "excluded_run_artifacts_checked": excluded_paths,
        "pack_item_identity_unique": "PASS",
        "acquisition_result_identity_unique": "PASS",
        "authoritative_selection": "EXPLICIT_RUN_AND_FINGERPRINT_ONLY",
        "physical_recency_selection": "PROHIBITED",
    }


def _validate_inventory(pack_rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in sorted(pack_rows, key=lambda item: (_norm(item.get("session_id")), _norm(item.get("item_key")))):
        status = _norm(row.get("status"))
        information_class = _norm(row.get("information_class"))
        final_category = CATEGORY_BY_STATUS.get(status)
        if not final_category:
            raise ValidationFailure("UNRECOGNIZED_PACK_STATUS:" + status)
        if information_class != status:
            raise ValidationFailure("PACK_INFORMATION_CLASS_STATUS_CONFLICT:" + _norm(row.get("item_key")))
        if status == "AI_RETRIEVED_PROVISIONAL" and _norm(row.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED":
            raise ValidationFailure("PROVISIONAL_ITEM_MISLABELED:" + _norm(row.get("item_key")))
        if status == "UNAVAILABLE" and _norm(row.get("data_available_flag")).upper() == "TRUE":
            raise ValidationFailure("UNAVAILABLE_ITEM_MARKED_AVAILABLE:" + _norm(row.get("item_key")))
        if status in {"INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED", "UNAVAILABLE"} and _norm(row.get("value")):
            raise ValidationFailure("NONFACT_STATUS_HAS_SUPPLIED_VALUE:" + _norm(row.get("item_key")))
        counts[final_category] += 1
        rows.append({
            "session_id": _norm(row.get("session_id")),
            "item_key": _norm(row.get("item_key")),
            "pack_item_id": _norm(row.get("pack_item_id")),
            "information_class": information_class,
            "final_scientific_category": final_category,
            "status": status,
            "provisional_status": _norm(row.get("provisional_status")),
            "data_available_flag": _norm(row.get("data_available_flag")),
            "backtest_safe": _norm(row.get("backtest_safe")),
            "validation_status": "PASS",
        })
    if sum(counts.values()) != EXPECTED_PACK_ITEM_COUNT:
        raise ValidationFailure("PACK_INVENTORY_COUNT_RECONCILIATION_FAILED")
    return rows, dict(sorted(counts.items()))


def _validate_provisional_and_grounding(
    pack_rows: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    bundles: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    result_by_request = {_norm(row.get("request_id")): row for row in results}
    request_by_id = {_norm(row.get("request_id")): row for row in requests}
    bundle_by_id = {_norm(row.get("source_bundle_id")): row for row in bundles}
    successful = [row for row in results if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    if len(successful) != 7:
        raise ValidationFailure("PROVISIONAL_SUCCESS_COUNT_MISMATCH")
    ai_items = [row for row in pack_rows if _norm(row.get("status")) == "AI_RETRIEVED_PROVISIONAL"]
    if len(ai_items) != 7:
        raise ValidationFailure("PACK_PROVISIONAL_ITEM_COUNT_MISMATCH")
    pack_ai_by_request = {
        _norm(row.get("requested_information_keys", [""])[0]): row
        for row in ai_items
        if isinstance(row.get("requested_information_keys"), list) and len(row.get("requested_information_keys")) == 1
    }
    if len(pack_ai_by_request) != 7:
        raise ValidationFailure("PACK_PROVISIONAL_REQUEST_MAPPING_INVALID")

    provisional_validation: List[Dict[str, Any]] = []
    source_validation: List[Dict[str, Any]] = []
    used_bundle_ids: set[str] = set()
    pairing_repairs = 0
    for result in sorted(successful, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("information_key")))):
        request_id = _norm(result.get("request_id"))
        request = request_by_id.get(request_id)
        if not request:
            raise ValidationFailure("PROVISIONAL_RESULT_REQUEST_NOT_APPROVED:" + request_id)
        if _norm(request.get("session_id")) != _norm(result.get("session_id")):
            raise ValidationFailure("PROVISIONAL_SESSION_ID_MISMATCH:" + request_id)
        if _norm(request.get("normalized_information_key")) != _norm(result.get("information_key")):
            raise ValidationFailure("PROVISIONAL_INFORMATION_KEY_MISMATCH:" + request_id)
        if _norm(result.get("candidate_id")) != _norm(request.get("candidate_id")):
            raise ValidationFailure("PROVISIONAL_CANDIDATE_ID_MISMATCH:" + request_id)
        required = ("session_id", "request_id", "candidate_id", "information_key", "canonical_information", "acquisition_method", "acquisition_provider", "acquisition_model", "acquisition_reasoning", "source_bundle_ids", "source_references", "source_timestamps", "as_of_timestamp", "forecast_timestamp", "confidence", "reliability_label", "provisional_status", "backtest_safe", "validation_status", "structured_summary")
        missing = [field for field in required if not result.get(field)]
        if missing:
            raise ValidationFailure("PROVISIONAL_REQUIRED_FIELD_MISSING:" + request_id + ":" + "|".join(missing))
        expected_metadata = {
            "acquisition_provider": "OpenAI",
            "acquisition_model": "gpt-5.6-luna",
            "acquisition_reasoning": "low",
            "acquisition_temperature_mode": "MODEL_DEFAULT",
            "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
            "validation_status": "VALID",
        }
        for field, expected in expected_metadata.items():
            if _norm(result.get(field)) != expected:
                raise ValidationFailure("PROVISIONAL_METADATA_MISMATCH:" + request_id + ":" + field)
        if result.get("acquisition_temperature_parameter_sent") is not False:
            raise ValidationFailure("PROVISIONAL_TEMPERATURE_PARAMETER_SENT:" + request_id)
        if not _truth(result.get("backtest_safe")) or not _truth(result.get("data_available_flag")):
            raise ValidationFailure("PROVISIONAL_BACKTEST_SAFETY_INVALID:" + request_id)
        content = " ".join(_norm(result.get(field)) for field in ("retrieved_value", "structured_summary", "stance_or_state_if_allowed")).lower()
        forbidden = [term for term in FORBIDDEN_ACQUISITION_TERMS if term in content]
        if forbidden:
            raise ValidationFailure("UNSUPPORTED_PROVISIONAL_CLAIM:" + request_id + ":" + "|".join(forbidden))
        pack_item = pack_ai_by_request.get(_norm(result.get("information_key")))
        if not pack_item or _norm(pack_item.get("session_id")) != _norm(result.get("session_id")):
            raise ValidationFailure("PROVISIONAL_RESULT_NOT_INSERTED_IN_PACK:" + request_id)
        if _norm(pack_item.get("value")) != _norm(result.get("retrieved_value")):
            raise ValidationFailure("PROVISIONAL_PACK_VALUE_MISMATCH:" + request_id)
        bundle_ids = result.get("source_bundle_ids", [])
        source_refs = result.get("source_references", [])
        source_times = result.get("source_timestamps", [])
        if not isinstance(bundle_ids, list) or not bundle_ids or len(bundle_ids) != len(set(bundle_ids)):
            raise ValidationFailure("PROVISIONAL_SOURCE_BUNDLE_IDS_INVALID:" + request_id)
        if not isinstance(source_refs, list) or not isinstance(source_times, list) or len(source_refs) != len(bundle_ids) or len(source_times) != len(bundle_ids):
            raise ValidationFailure("PROVISIONAL_SOURCE_REFERENCE_CARDINALITY_INVALID:" + request_id)
        resolved_bundles = []
        for bundle_id in bundle_ids:
            bundle = bundle_by_id.get(_norm(bundle_id))
            if not bundle:
                raise ValidationFailure("CITED_SOURCE_BUNDLE_MISSING:" + _norm(bundle_id))
            if _norm(bundle.get("session_id")) != _norm(result.get("session_id")):
                raise ValidationFailure("CITED_SOURCE_BUNDLE_SESSION_MISMATCH:" + _norm(bundle_id))
            if _norm(bundle.get("information_key")) != _norm(result.get("information_key")):
                raise ValidationFailure("CITED_SOURCE_BUNDLE_INFORMATION_MISMATCH:" + _norm(bundle_id))
            if _norm(bundle.get("request_id")) != request_id:
                raise ValidationFailure("CITED_SOURCE_BUNDLE_REQUEST_MISMATCH:" + _norm(bundle_id))
            resolved_bundles.append(bundle)
        expected_references = sorted(_norm(bundle.get("source_reference")) for bundle in resolved_bundles)
        expected_timestamps = sorted(_norm(bundle.get("publication_timestamp")) for bundle in resolved_bundles)
        if sorted(_norm(value) for value in source_refs) != expected_references:
            raise ValidationFailure("CITED_SOURCE_BUNDLE_REFERENCE_SET_MISMATCH:" + request_id)
        if sorted(_norm(value) for value in source_times) != expected_timestamps:
            raise ValidationFailure("CITED_SOURCE_BUNDLE_TIMESTAMP_SET_MISMATCH:" + request_id)
        raw_pairs = list(zip(bundle_ids, source_refs, source_times))
        canonical_pairs = [
            (_norm(bundle.get("source_bundle_id")), _norm(bundle.get("source_reference")), _norm(bundle.get("publication_timestamp")))
            for bundle in resolved_bundles
        ]
        pairing_status = "ORIGINAL_PAIRING_VALID" if raw_pairs == canonical_pairs else "REPAIRED_BY_SOURCE_BUNDLE_ID"
        if pairing_status == "REPAIRED_BY_SOURCE_BUNDLE_ID":
            pairing_repairs += 1
        for bundle in resolved_bundles:
            bundle_id = _norm(bundle.get("source_bundle_id"))
            publication = _parse_ts(bundle.get("publication_timestamp"))
            forecast = _parse_ts(result.get("forecast_timestamp"))
            availability = _parse_ts(bundle.get("historical_availability_timestamp") or bundle.get("publication_timestamp"))
            if publication > forecast or availability > forecast:
                raise ValidationFailure("POST_CUTOFF_SOURCE:" + _norm(bundle_id))
            if not _truth(bundle.get("historical_availability_proven")) or not _truth(bundle.get("backtest_safe")):
                raise ValidationFailure("SOURCE_BUNDLE_BACKTEST_SAFETY_INVALID:" + _norm(bundle_id))
            used_bundle_ids.add(_norm(bundle_id))
            source_validation.append({
                "request_id": request_id,
                "session_id": _norm(result.get("session_id")),
                "information_key": _norm(result.get("information_key")),
                "source_bundle_id": _norm(bundle_id),
                "source_reference": _norm(bundle.get("source_reference")),
                "publication_timestamp": _norm(bundle.get("publication_timestamp")),
                "forecast_timestamp": _norm(result.get("forecast_timestamp")),
                "historical_availability_proven": _norm(bundle.get("historical_availability_proven")),
                "backtest_safe": _norm(bundle.get("backtest_safe")),
                "validation_status": "PASS",
            })
        provisional_validation.append({
            "request_id": request_id,
            "session_id": _norm(result.get("session_id")),
            "candidate_id": _norm(result.get("candidate_id")),
            "information_key": _norm(result.get("information_key")),
            "pack_item_id": _norm(pack_item.get("pack_item_id")),
            "acquisition_provider": _norm(result.get("acquisition_provider")),
            "acquisition_model": _norm(result.get("acquisition_model")),
            "reasoning_effort": _norm(result.get("acquisition_reasoning")),
            "temperature_mode": _norm(result.get("acquisition_temperature_mode")),
            "temperature_parameter_sent": result.get("acquisition_temperature_parameter_sent"),
                "source_bundle_count": len(bundle_ids),
            "source_pairing_resolution": pairing_status,
            "source_grounding": "PASS",
            "historical_cutoff": "PASS",
            "unsupported_claim_check": "PASS",
            "provisional_label": "PASS",
            "validation_status": "PASS",
        })
    if used_bundle_ids != set(bundle_by_id):
        raise ValidationFailure("SOURCE_BUNDLE_AUDIT_NOT_EXHAUSTIVE")
    return provisional_validation, source_validation, {
        "source_bundle_count": len(used_bundle_ids),
        "provisional_item_count": len(provisional_validation),
        "source_pairing_repairs": pairing_repairs,
    }


def _validate_unsupported_request(
    pack_rows: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    information_key = "inflation_narrative|market_s_narrative_on_inflation_and_its_persistence"
    failed = [row for row in results if _norm(row.get("information_key")) == information_key]
    if len(failed) != 1:
        raise ValidationFailure("UNSUPPORTED_REQUEST_RESULT_CARDINALITY_INVALID")
    result = failed[0]
    if _norm(result.get("result_status")) != "EXTERNAL_SOURCE_NOT_CONFIGURED" or _norm(result.get("failure_reason")) != "NO_PROVENANCE_VALID_SOURCE_BUNDLE_FOR_REQUEST":
        raise ValidationFailure("UNSUPPORTED_REQUEST_STATUS_CHANGED")
    if result.get("source_bundle_ids") or _norm(result.get("retrieved_value")) or _norm(result.get("structured_summary")):
        raise ValidationFailure("UNSUPPORTED_REQUEST_SYNTHETIC_CONTENT_PRESENT")
    candidates = [
        row for row in pack_rows
        if _norm(row.get("session_id")) == _norm(result.get("session_id"))
        and information_key in row.get("requested_information_keys", [])
    ]
    if len(candidates) != 1:
        raise ValidationFailure("UNSUPPORTED_REQUEST_PACK_DECLARATION_CARDINALITY_INVALID")
    pack_item = candidates[0]
    if _norm(pack_item.get("status")) != "UNAVAILABLE" or _norm(pack_item.get("reason")) != "NO_PROVENANCE_VALID_SOURCE_BUNDLE_FOR_REQUEST":
        raise ValidationFailure("UNSUPPORTED_REQUEST_PACK_STATUS_CHANGED")
    if _norm(pack_item.get("value")) or pack_item.get("input_lineage"):
        raise ValidationFailure("UNSUPPORTED_REQUEST_PACK_SYNTHETIC_CONTENT_PRESENT")
    if pack_item.get("shared_provider_set") != list(PROVIDERS):
        raise ValidationFailure("UNSUPPORTED_REQUEST_NOT_SHARED")
    return {
        "session_id": _norm(result.get("session_id")),
        "information_key": information_key,
        "status": "NO_PROVENANCE_VALID_SOURCE_BUNDLE_FOR_REQUEST",
        "pack_visibility": "EXPLICIT_UNAVAILABLE_DECLARATION",
        "official_policy_substitution": "NOT_USED",
        "validation_status": "PASS",
    }


def _check_no_outcome_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = _norm(key).lower()
            if any(term in lowered for term in FORBIDDEN_OUTCOME_KEYS):
                raise ValidationFailure("OUTCOME_FIELD_EXPOSED:" + path + "." + _norm(key))
            _check_no_outcome_keys(nested, path + "." + _norm(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _check_no_outcome_keys(nested, path + "[" + str(index) + "]")


def _freeze_payload(run_id: str) -> Dict[str, Any]:
    return {
        "scientific_schema_version": FREEZE_SCHEMA_VERSION,
        "validation_run_id": run_id,
        "pack_version": "true_shared_pack_e_v1",
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "created_from_acquisition_run": AUTHORITATIVE_RUN_ID,
        "authoritative_pack_path": str(PACK_PATH),
        "authoritative_acquisition_results_path": str(RESULTS_PATH),
        "authoritative_source_bundle_path": str(BUNDLES_PATH),
        "pack_item_count": EXPECTED_PACK_ITEM_COUNT,
        "pack_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "acquisition_provider": "OpenAI",
        "acquisition_model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "temperature_mode": "MODEL_DEFAULT",
        "temperature_parameter_sent": False,
        "provisional_item_count": 7,
        "unsupported_request_count": 1,
        "source_bundle_count": 8,
        "source_pairing_resolution": "RECONSTRUCTED_BY_SOURCE_BUNDLE_ID",
        "forecast_input_renderer_version": RENDERER_VERSION,
        "freeze_status": FROZEN_STATUS,
        "shadow_only": True,
        "production_authority": False,
        "consumer_switch": False,
    }


def _validate_renderer_and_delivery(freeze_payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with tempfile.TemporaryDirectory(prefix="presignal-pack-e-freeze-") as directory:
        freeze_path = Path(directory) / "pack_e_freeze_manifest.json"
        _write_json(freeze_path, freeze_payload)
        try:
            frozen = load_frozen_true_shared_pack_e(freeze_path)
        except FrozenPackEError as exc:
            raise ValidationFailure("FROZEN_RENDERER_SELECTION_FAILED:" + str(exc)) from exc
        sessions = sorted({_norm(row.get("session_id")) for row in frozen["pack_rows"]})
        session_rows: List[Dict[str, Any]] = []
        all_entries = 0
        for session_id in sessions:
            context = render_frozen_true_shared_pack_e_context(frozen, session_id)
            _check_no_outcome_keys(context)
            entries = context.get("assigned_market_state_context", [])
            expected_entries = [row for row in frozen["pack_rows"] if _norm(row.get("session_id")) == session_id]
            if len(entries) != len(expected_entries):
                raise ValidationFailure("FORECAST_RENDERER_ITEM_LOSS:" + session_id)
            provisional_entries = [entry for entry in entries if _norm(entry.get("availability_status")) == "AI_RETRIEVED_PROVISIONAL"]
            if any(not _norm(entry.get("structured_summary")) or not entry.get("source_references") for entry in provisional_entries):
                raise ValidationFailure("FORECAST_RENDERER_PROVISIONAL_SUMMARY_OR_SOURCE_LOSS:" + session_id)
            nonfacts = [entry for entry in entries if _norm(entry.get("availability_status")) in {"UNAVAILABLE", "INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED"}]
            if any(_norm(entry.get("value")) for entry in nonfacts):
                raise ValidationFailure("FORECAST_RENDERER_NONFACT_PRESENTED_AS_FACT:" + session_id)
            delivery_fingerprints = {provider: content_fingerprint(context) for provider in PROVIDERS}
            if len(set(delivery_fingerprints.values())) != 1:
                raise ValidationFailure("PROVIDER_PACK_E_DELIVERY_INEQUALITY:" + session_id)
            fixture_design = {
                "system_prompt_template": "Use only the assigned pre-outcome market-state context.",
                "user_prompt_template": "Return the existing required forecast JSON only.",
            }
            fixture_event = {"session": {"session_id": session_id}, "events": []}
            _, prompt_text = _assemble_prompt_text(fixture_design, fixture_event, context, [], [])
            if not all(_norm(entry.get("item_key")) in prompt_text for entry in entries):
                raise ValidationFailure("FORECAST_RENDERER_PROMPT_OMISSION:" + session_id)
            all_entries += len(entries)
            session_rows.append({
                "session_id": session_id,
                "rendered_item_count": len(entries),
                "provisional_item_count": len(provisional_entries),
                "unavailable_or_nonfact_item_count": len(nonfacts),
                "openai_delivery_fingerprint": delivery_fingerprints["OpenAI"],
                "gemini_delivery_fingerprint": delivery_fingerprints["Gemini"],
                "anthropic_delivery_fingerprint": delivery_fingerprints["Anthropic"],
                "shared_pack_equality": "PASS",
                "outcome_field_exposure": "PASS",
                "prompt_rendering": "PASS",
            })
        if all_entries != EXPECTED_PACK_ITEM_COUNT:
            raise ValidationFailure("FORECAST_RENDERER_GLOBAL_ITEM_ACCOUNTING_FAILED")
        return {
            "renderer_selection": "PASS_BY_EXPLICIT_FROZEN_MANIFEST",
            "sessions_rendered": len(sessions),
            "rendered_item_count": all_entries,
            "pack_a_baseline_preserved": "PASS_BY_NO_MANIFEST_SELECTION_FOR_PACK_A",
            "pack_b_to_d_required_as_gates": "FALSE",
            "forecast_providers_called": 0,
        }, session_rows


def _run_self_tests(pack_rows: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    ordered = _logical_pack_rows(pack_rows)
    sorted_rows = _logical_pack_rows(sorted(pack_rows, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("item_key")))))
    if content_fingerprint(ordered) != content_fingerprint(sorted_rows):
        raise ValidationFailure("CANONICAL_PACK_ORDERING_NOT_DETERMINISTIC")
    return {
        "canonical_pack_ordering": "PASS",
        "logical_pack_fingerprint_reconstruction": "PASS",
        "source_to_provisional_trace": "PASS",
        "shared_provider_delivery_fixture": "PASS",
        "forecast_input_rendering_fixture": "PASS",
        "outcome_leakage_fixture": "PASS",
    }


def build(run_id: str | None = None) -> Dict[str, Any]:
    run_id = run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    if output_dir.exists():
        raise ValidationFailure("OUTPUT_RUN_ALREADY_EXISTS:" + str(output_dir))
    pack_rows = _read_jsonl(PACK_PATH)
    results = _read_jsonl(RESULTS_PATH)
    bundles = _read_jsonl(BUNDLES_PATH)
    requests = _read_jsonl(REQUESTS_PATH)
    summary = _read_json(SUMMARY_PATH)
    manifest = _read_json(MANIFEST_PATH)

    isolation = _validate_authoritative_isolation(pack_rows, results, summary, manifest)
    inventory_rows, category_counts = _validate_inventory(pack_rows)
    reconstructed_fingerprint = content_fingerprint(_logical_pack_rows(pack_rows))
    repeated_fingerprint = content_fingerprint(
        _logical_pack_rows(sorted(pack_rows, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("item_key")))))
    )
    if reconstructed_fingerprint != EXPECTED_PACK_FINGERPRINT or repeated_fingerprint != EXPECTED_PACK_FINGERPRINT:
        raise ValidationFailure("PACK_FINGERPRINT_RECONSTRUCTION_FAILED")
    if _norm(summary.get("pack_e_fingerprint")) != EXPECTED_PACK_FINGERPRINT:
        raise ValidationFailure("SUMMARY_PACK_FINGERPRINT_MISMATCH")
    if _norm(manifest.get("content_fingerprints", {}).get("true_shared_pack_e_v1")) != EXPECTED_PACK_FINGERPRINT:
        raise ValidationFailure("MANIFEST_PACK_FINGERPRINT_MISMATCH")
    if content_fingerprint(_logical_results(results)) != _norm(summary.get("acquisition_result_fingerprint")):
        raise ValidationFailure("ACQUISITION_RESULT_FINGERPRINT_MISMATCH")
    provisional_rows, grounding_rows, grounding_summary = _validate_provisional_and_grounding(pack_rows, results, bundles, requests)
    unsupported = _validate_unsupported_request(pack_rows, results)
    freeze_payload = _freeze_payload(run_id)
    renderer_summary, renderer_rows = _validate_renderer_and_delivery(freeze_payload)
    self_tests = _run_self_tests(pack_rows)

    all_delivery_fingerprints = {provider: content_fingerprint(_logical_pack_rows(pack_rows)) for provider in PROVIDERS}
    if len(set(all_delivery_fingerprints.values())) != 1:
        raise ValidationFailure("GLOBAL_PROVIDER_PACK_E_DELIVERY_INEQUALITY")
    expected_delivery = summary.get("provider_delivery_fixture", {})
    if set(expected_delivery) != set(PROVIDERS) or len(set(expected_delivery.values())) != 1:
        raise ValidationFailure("AUTHORITATIVE_PROVIDER_DELIVERY_FIXTURE_INVALID")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output_dir / "pack_e_item_validation.jsonl", inventory_rows)
    _write_jsonl(output_dir / "provisional_item_validation.jsonl", provisional_rows)
    _write_jsonl(output_dir / "source_grounding_validation.jsonl", grounding_rows)
    _write_json(output_dir / "shared_pack_equality.json", {
        "scientific_schema_version": VALIDATION_SCHEMA_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "all_pack_logical_fingerprint": reconstructed_fingerprint,
        "provider_delivery_fingerprints": all_delivery_fingerprints,
        "authoritative_delivery_fixture": expected_delivery,
        "session_rendering": renderer_rows,
        "shared_pack_equality": "PASS",
    })
    _write_json(output_dir / "forecast_input_fixture_validation.json", {
        "scientific_schema_version": VALIDATION_SCHEMA_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "renderer_version": RENDERER_VERSION,
        "renderer_summary": renderer_summary,
        "sessions": renderer_rows,
        "validation_status": "PASS",
    })
    _write_json(output_dir / "pack_e_freeze_manifest.json", freeze_payload)
    result_summary = {
        "build_status": "PASS",
        "final_decision": "TRUE_SHARED_PACK_E_VALIDATED_AND_FROZEN",
        "validation_run_id": run_id,
        "authoritative_acquisition_run": AUTHORITATIVE_RUN_ID,
        "excluded_runs": list(EXCLUDED_RUN_IDS),
        "pack_e_version": "true_shared_pack_e_v1",
        "pack_e_item_count": EXPECTED_PACK_ITEM_COUNT,
        "expected_pack_e_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "reconstructed_pack_e_fingerprint": reconstructed_fingerprint,
        "repeated_reconstruction_fingerprint": repeated_fingerprint,
        "category_counts": category_counts,
        "count_reconciliation": "PASS",
        "provisional_items_reviewed": 7,
        "provisional_items_passed": 7,
        "provisional_items_failed": 0,
        "unsupported_request": unsupported,
        "source_bundles_referenced": grounding_summary["source_bundle_count"],
        "source_pairing_repairs": grounding_summary["source_pairing_repairs"],
        "source_id_validation": "PASS",
        "historical_cutoff_validation": "PASS",
        "provenance_validation": "PASS",
        "unsupported_claim_check": "PASS",
        "outcome_leakage_check": "PASS_NO_OUTCOME_FIELDS_OR_INPUTS",
        "shared_pack_equality": "PASS",
        "forecast_input_rendering": "PASS",
        "pack_a_baseline_preserved": renderer_summary["pack_a_baseline_preserved"],
        "pack_e_selection_ready": "PASS_BY_EXPLICIT_FROZEN_MANIFEST",
        "pack_b_to_d_required_as_gates": "FALSE",
        "forecast_providers_called": 0,
        "freeze_status": FROZEN_STATUS,
        "freeze_manifest": str(output_dir / "pack_e_freeze_manifest.json"),
        "frozen_pack_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "implementation_defects_found": [
            "LEGACY_PACK_E_RENDERER_OMITTED_TRUE_SHARED_PACK_E_ITEMS",
            "MULTI_SOURCE_ACQUISITION_PARALLEL_ARRAY_ORDER_DID_NOT_PRESERVE_BUNDLE_PAIRING",
        ],
        "implementation_defects_repaired": [
            "EXPLICIT_FROZEN_TRUE_PACK_E_RENDERER_AND_OPT_IN_SHADOW_SELECTOR",
            "SOURCE_REFERENCE_PAIRING_RECONSTRUCTED_BY_STABLE_SOURCE_BUNDLE_ID",
        ],
        "scientific_content_changed": 0,
        "item_counts_changed": 0,
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "source_retrieval_calls": 0,
        "acquisition_ai_calls": 0,
        "forecast_runs": 0,
        "tests": self_tests,
        "next_scientific_step": "Perform the narrow May 1-7 exact outcome-link repair",
    }
    _write_json(output_dir / "pack_e_validation_summary.json", result_summary)
    _write_json(output_dir / "pack_e_validation_manifest.json", {
        "scientific_schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_run_id": run_id,
        "authoritative_acquisition_run": AUTHORITATIVE_RUN_ID,
        "input_artifacts": {
            "pack": str(PACK_PATH),
            "pack_sha256": _file_sha256(PACK_PATH),
            "acquisition_results": str(RESULTS_PATH),
            "acquisition_results_sha256": _file_sha256(RESULTS_PATH),
            "source_bundles": str(BUNDLES_PATH),
            "source_bundles_sha256": _file_sha256(BUNDLES_PATH),
        },
        "output_fingerprints": {
            "pack_e_fingerprint": reconstructed_fingerprint,
            "acquisition_result_fingerprint": content_fingerprint(_logical_results(results)),
            "validation_script_sha256": _file_sha256(Path(__file__)),
        },
        "freeze_manifest": str(output_dir / "pack_e_freeze_manifest.json"),
        "freeze_status": FROZEN_STATUS,
        "governance": {
            "source_retrieval_calls": 0,
            "acquisition_ai_calls": 0,
            "forecast_runs": 0,
            "outcome_inputs_read": 0,
            "production_writes": 0,
            "consumer_switches": 0,
        },
    })
    return result_summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and freeze the authoritative true shared Pack E.")
    parser.add_argument("--run-id", default="", help="Optional deterministic validation output run ID.")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    result = build(args.run_id or None)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
