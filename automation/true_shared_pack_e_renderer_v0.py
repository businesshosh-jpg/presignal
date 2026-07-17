#!/usr/bin/env python3
"""Render a frozen true shared Pack E for the shadow forecasting path.

This module is intentionally a small adapter.  It does not build, mutate, or
select Pack E by recency; it renders only the exact artifact named by a frozen
manifest.  The existing prompt assembler can consume the returned context
without provider-specific transformations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


FROZEN_STATUS = "FROZEN_FOR_PHASE9_A_VS_E_SHADOW_TEST"
VOLATILE_PACK_FIELDS = {"acquisition_run_id", "external_acquisition_run_id", "generated_timestamp"}
PROVISIONAL_STATUS = "AI_RETRIEVED_PROVISIONAL"


class FrozenPackEError(ValueError):
    """Raised when a frozen Pack E artifact cannot be selected safely."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def content_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FrozenPackEError("FROZEN_PACK_E_MANIFEST_MISSING:" + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FrozenPackEError("FROZEN_PACK_E_MANIFEST_NOT_OBJECT")
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FrozenPackEError("FROZEN_PACK_E_ARTIFACT_MISSING:" + str(path))
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FrozenPackEError("FROZEN_PACK_E_ROW_NOT_OBJECT:" + str(line_number))
        rows.append(value)
    return rows


def _logical_pack_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [{key: value for key, value in row.items() if key not in VOLATILE_PACK_FIELDS} for row in rows]


def load_frozen_true_shared_pack_e(freeze_manifest_path: Path) -> Dict[str, Any]:
    """Load one explicitly frozen artifact and fail closed on any mismatch."""

    manifest = _read_json(freeze_manifest_path)
    if _norm(manifest.get("freeze_status")) != FROZEN_STATUS:
        raise FrozenPackEError("FROZEN_PACK_E_STATUS_INVALID")
    pack_path = Path(_norm(manifest.get("authoritative_pack_path")))
    results_path = Path(_norm(manifest.get("authoritative_acquisition_results_path")))
    bundles_path = Path(_norm(manifest.get("authoritative_source_bundle_path")))
    if not pack_path.is_absolute() or not results_path.is_absolute() or not bundles_path.is_absolute():
        raise FrozenPackEError("FROZEN_PACK_E_PATH_NOT_ABSOLUTE")
    rows = _read_jsonl(pack_path)
    results = _read_jsonl(results_path)
    bundles = _read_jsonl(bundles_path)
    expected_count = manifest.get("pack_item_count")
    if not isinstance(expected_count, int) or len(rows) != expected_count:
        raise FrozenPackEError("FROZEN_PACK_E_ITEM_COUNT_MISMATCH")
    expected_fingerprint = _norm(manifest.get("pack_fingerprint"))
    actual_fingerprint = content_fingerprint(_logical_pack_rows(rows))
    if not expected_fingerprint or actual_fingerprint != expected_fingerprint:
        raise FrozenPackEError("FROZEN_PACK_E_FINGERPRINT_MISMATCH")
    authoritative_run_id = _norm(manifest.get("authoritative_run_id"))
    if not authoritative_run_id:
        raise FrozenPackEError("FROZEN_PACK_E_RUN_ID_MISSING")
    if any(_norm(row.get("external_acquisition_run_id")) != authoritative_run_id for row in rows):
        raise FrozenPackEError("FROZEN_PACK_E_MIXED_RUN_CONTENT")
    if any(_norm(row.get("external_acquisition_run_id")) != authoritative_run_id for row in results):
        raise FrozenPackEError("FROZEN_PACK_E_MIXED_RUN_RESULTS")
    keys = [(_norm(row.get("session_id")), _norm(row.get("item_key"))) for row in rows]
    if not all(session_id and item_key for session_id, item_key in keys) or len(keys) != len(set(keys)):
        raise FrozenPackEError("FROZEN_PACK_E_DUPLICATE_OR_MISSING_ITEM_IDENTITY")
    bundle_by_id = {_norm(bundle.get("source_bundle_id")): bundle for bundle in bundles}
    if not bundle_by_id or len(bundle_by_id) != len(bundles):
        raise FrozenPackEError("FROZEN_PACK_E_SOURCE_BUNDLE_IDENTITY_INVALID")
    for result in results:
        if _norm(result.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            continue
        bundle_ids = result.get("source_bundle_ids", [])
        if not isinstance(bundle_ids, list) or not bundle_ids:
            raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_BUNDLE_IDS_INVALID")
        resolved = [bundle_by_id.get(_norm(bundle_id)) for bundle_id in bundle_ids]
        if any(bundle is None for bundle in resolved):
            raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_BUNDLE_MISSING")
        if any(
            _norm(bundle.get("session_id")) != _norm(result.get("session_id"))
            or _norm(bundle.get("information_key")) != _norm(result.get("information_key"))
            or _norm(bundle.get("request_id")) != _norm(result.get("request_id"))
            for bundle in resolved
        ):
            raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_BUNDLE_IDENTITY_MISMATCH")
        expected_references = sorted(_norm(bundle.get("source_reference")) for bundle in resolved)
        expected_timestamps = sorted(_norm(bundle.get("publication_timestamp")) for bundle in resolved)
        if sorted(_norm(value) for value in result.get("source_references", [])) != expected_references:
            raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_REFERENCE_SET_MISMATCH")
        if sorted(_norm(value) for value in result.get("source_timestamps", [])) != expected_timestamps:
            raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_TIMESTAMP_SET_MISMATCH")
    return {
        "manifest": manifest,
        "pack_rows": sorted(rows, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("item_key")))),
        "acquisition_results": results,
        "source_bundles_by_id": bundle_by_id,
        "pack_fingerprint": actual_fingerprint,
    }


def render_frozen_true_shared_pack_e_context(
    frozen_pack: Mapping[str, Any], session_id: str
) -> Dict[str, Any]:
    """Return canonical, provider-neutral Pack E context for one session."""

    manifest = frozen_pack.get("manifest", {})
    rows = [row for row in frozen_pack.get("pack_rows", []) if _norm(row.get("session_id")) == _norm(session_id)]
    if not rows:
        raise FrozenPackEError("FROZEN_PACK_E_SESSION_NOT_FOUND:" + _norm(session_id))
    result_by_key = {
        (_norm(row.get("session_id")), _norm(row.get("information_key"))): row
        for row in frozen_pack.get("acquisition_results", [])
        if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"
    }
    source_bundles_by_id = frozen_pack.get("source_bundles_by_id", {})
    entries: List[Dict[str, Any]] = []
    for row in rows:
        status = _norm(row.get("status"))
        entry: Dict[str, Any] = {
            "item_key": _norm(row.get("item_key")),
            "information_class": _norm(row.get("information_class")),
            "availability_status": status,
            "value_type": _norm(row.get("value_type")),
            "value": _norm(row.get("value")) if status not in {"UNAVAILABLE", "INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED"} else "",
            "as_of_timestamp": _norm(row.get("as_of_timestamp")),
            "source_timestamp": _norm(row.get("source_timestamp")),
            "source_lineage": row.get("input_lineage", []),
            "provisional_status": _norm(row.get("provisional_status")),
            "backtest_safe": _norm(row.get("backtest_safe")),
            "data_available_flag": _norm(row.get("data_available_flag")),
            "reason": _norm(row.get("reason")),
            "requested_information_keys": row.get("requested_information_keys", []),
        }
        if status == PROVISIONAL_STATUS:
            information_keys = row.get("requested_information_keys", [])
            if not isinstance(information_keys, list) or len(information_keys) != 1:
                raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_REQUEST_IDENTITY_INVALID")
            result = result_by_key.get((_norm(session_id), _norm(information_keys[0])))
            if not result:
                raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_RESULT_MISSING")
            source_bundle_ids = result.get("source_bundle_ids", [])
            resolved_bundles = [source_bundles_by_id.get(_norm(bundle_id)) for bundle_id in source_bundle_ids]
            if any(bundle is None for bundle in resolved_bundles):
                raise FrozenPackEError("FROZEN_PACK_E_RENDER_SOURCE_BUNDLE_MISSING")
            entry.update({
                "structured_summary": _norm(result.get("structured_summary")),
                # Resolve by stable bundle ID to avoid relying on legacy
                # parallel-array order in an archived acquisition result.
                "source_references": [_norm(bundle.get("source_reference")) for bundle in resolved_bundles],
                "source_timestamps": [_norm(bundle.get("publication_timestamp")) for bundle in resolved_bundles],
                "source_bundle_ids": source_bundle_ids,
                "confidence": _norm(result.get("confidence")),
                "reliability_label": _norm(result.get("reliability_label")),
                "acquisition_provider": _norm(result.get("acquisition_provider")),
                "acquisition_model": _norm(result.get("acquisition_model")),
                "reasoning_effort": _norm(result.get("acquisition_reasoning")),
                "temperature_mode": _norm(result.get("acquisition_temperature_mode")),
                "temperature_parameter_sent": result.get("acquisition_temperature_parameter_sent"),
            })
            if not entry["structured_summary"] or not entry["source_references"]:
                raise FrozenPackEError("FROZEN_PACK_E_PROVISIONAL_SOURCE_SUMMARY_MISSING")
        entries.append(entry)
    entries.sort(key=lambda row: row["item_key"])
    return {
        "assigned_market_state_context": entries,
        "instruction": "Use only these assigned fields. Provisional source-grounded items are not deterministic facts. Unavailable, interpretive, and policy-rejected items must not be fabricated.",
        "true_shared_pack_e": {
            "pack_version": _norm(manifest.get("pack_version")),
            "authoritative_run_id": _norm(manifest.get("authoritative_run_id")),
            "pack_fingerprint": _norm(manifest.get("pack_fingerprint")),
            "freeze_status": _norm(manifest.get("freeze_status")),
        },
    }
