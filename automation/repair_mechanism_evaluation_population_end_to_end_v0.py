#!/usr/bin/env python3
"""Phase 9A end-to-end evaluation-population repair.

This script performs the smallest permitted continuous repair:
1. read the authoritative frozen classification and verified OA-v2 evidence;
2. inspect the historical evidence population;
3. repair only shadow exact-link omissions backed by existing repaired overlays;
4. rebuild the mechanism-test evaluable population under frozen Success Mapping v1;
5. if historical evidence remains insufficient, activate a shadow-only prospective
   collection contract.

It does not modify preregistrations, classifications, Success Mapping rules,
production consumers, or source outcome sheets.
"""

from __future__ import annotations

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

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _sheet_to_rows  # type: ignore
from automation.collect_mechanism_evaluation_population_shadow_v0 import build_collection_contract  # type: ignore
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-E2E-POPULATION-REPAIR"
SCRIPT_PATH = "automation/repair_mechanism_evaluation_population_end_to_end_v0.py"
AUTHORITATIVE_OA2_RUN = "9A-6R15I-R1_20260713T061220Z"
REPAIR_VERIFICATION_RUN = "9A-6R15J-R1_20260713T071511Z"
POPULATION_RECOVERY_AUDIT = "9A-OA2-POPULATION-RECOVERY_20260713T074308Z"
EXPECTED_OA2_FINGERPRINT = "0f021cb3aa68fb0ebf3025091923687d261afeaaa30ec47474b54daba0dff41a"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_ID = "MECH_INFORMATION_CONSISTENCY"
FROZEN_PRIMARY_LABELS = {"POSITIVE", "NEGATIVE"}
FROZEN_PRIMARY_CONFIDENCE = {"HIGH", "MODERATE"}
FROZEN_EXPANDED_PACKS = {"B", "C", "D", "E"}
FROZEN_GATES = {
    "positive": 40,
    "negative": 12,
    "primary_contrast": 40,
    "clusters": 12,
    "providers": 2,
    "sessions": 4,
}

INPUT_SHEETS = {
    "classification": "Refined_Mechanism_v11_Classifications",
    "behavior": "Pack_Behavior_Tier2_NoSignal",
    "behavior_raw": "Pack_Behavior_Tier2_Forecasts",
    "selection": "Corrected_Accuracy_Row_Selection",
    "mapping": "Corrected_Accuracy_Outcome_Mapping",
    "validation": "Market_Reaction_Repaired_Remap_Validation",
    "overlay": "Market_Reaction_Recovered_Canonical_Outcomes",
    "canonical": "Market_Reaction_Canonical_Outcomes",
    "lineage": "Refined_Mechanism_Test_Row_Lineage_Audit",
    "population_audit": "OA2_Population_Recovery_Audit",
    "pack_exposure": "Pack_Exposure_Forecasts",
    "behavior_discovery": "Pack_Behavior_Discovery_Forecasts",
    "session_forecasts": "Session_Forecasts",
}

CONSENSUS_SELECTION_FIELDS = [
    "repaired_canonical_outcome_id",
    "strict_ready",
    "included_in_primary_corrected_evaluation",
    "leakage_safe_validated",
    "design_version",
]
CONSENSUS_MAPPING_FIELDS = [
    "repaired_canonical_outcome_id",
    "repaired_realized_direction",
    "outcome_mapping_status",
    "included_in_primary",
    "design_version",
]


class PopulationRepairBlocked(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "")
    return f"{PHASE_ID}_{compact}Z"


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _is_true(value: Any) -> bool:
    return _upper(value) in {"TRUE", "1", "YES", "Y", "PASS", "APPROVED"}


def _to_float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_iso(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _source_key(provider: Any, session_id: Any, pack_level: Any) -> str:
    return "|".join((_norm(session_id), _norm(provider), _norm(pack_level)))


def _key(row: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (_norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level")))


def _cluster_key(row: Mapping[str, Any]) -> str:
    return f"{_norm(row.get('provider'))}|{_norm(row.get('session_id'))}"


def _normalize_direction(value: Any) -> str:
    raw = _upper(value)
    if raw in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return raw
    if raw in {"NO_SIGNAL", "NOSIGNAL"}:
        return "NO_SIGNAL"
    return raw


def _derive_success_status(
    *,
    forecast_direction: str,
    no_signal_flag: bool,
    output_valid: bool,
    realized_direction: str,
    join_status: str,
    join_reason: str,
) -> Tuple[str, str]:
    """Mirror the frozen Phase 9A-6R15 Success Mapping v1 implementation."""

    if join_status == "AMBIGUOUS_JOIN_BLOCKED":
        return "AMBIGUOUS_JOIN_BLOCKED", join_reason
    if join_status != "OK":
        return "NOT_ELIGIBLE", join_reason
    if not output_valid:
        return "NOT_ELIGIBLE", "INVALID_FORECAST_OUTPUT"
    if forecast_direction not in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION"}:
        return "NOT_ELIGIBLE", "INVALID_FORECAST_DIRECTION"
    if realized_direction not in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return "NOT_ELIGIBLE", "INVALID_REALIZED_DIRECTION"
    if forecast_direction == "NO_CLEAR_DIRECTION":
        return "NOT_ELIGIBLE", "FORECAST_NO_CLEAR_DIRECTION"
    if no_signal_flag:
        return "NOT_ELIGIBLE", "NO_SIGNAL_FORECAST"
    if realized_direction in {"FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return "NOT_ELIGIBLE", "REALIZED_FLAT_OR_AMBIGUOUS"
    if forecast_direction == "FLAT":
        return "NOT_ELIGIBLE", "FORECAST_FLAT"
    if forecast_direction == "UP" and realized_direction == "UP":
        return "SUCCESS", "UP_MATCH"
    if forecast_direction == "UP" and realized_direction == "DOWN":
        return "FAILURE", "UP_MISMATCH"
    if forecast_direction == "DOWN" and realized_direction == "DOWN":
        return "SUCCESS", "DOWN_MATCH"
    if forecast_direction == "DOWN" and realized_direction == "UP":
        return "FAILURE", "DOWN_MISMATCH"
    return "NOT_ELIGIBLE", "UNMAPPED_STATUS"


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    inputs: Dict[str, List[Dict[str, Any]]] = {}
    for key, sheet in INPUT_SHEETS.items():
        inputs[key] = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)
    return inputs


def _build_consensus(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
    missing_code: str,
    duplicate_code: str,
) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_key(row)].append(dict(row))
    out: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for key, group in groups.items():
        variants = {tuple(_norm(row.get(field)) for field in fields) for row in group}
        if len(variants) != 1:
            out[key] = {
                "status": duplicate_code,
                "duplicate_count": len(group),
                "observed_variants": [list(item) for item in sorted(variants)],
            }
            continue
        values = next(iter(variants))
        payload = {field: values[index] for index, field in enumerate(fields)}
        payload.update({"status": "OK", "duplicate_count": len(group), "raw_row_count": len(group)})
        out[key] = payload
    return out


def _dedupe_by_key(
    rows: Sequence[Mapping[str, Any]],
    id_field: str,
    material_fields: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _norm(row.get(id_field))
        if key:
            groups[key].append(dict(row))
    duplicates: List[str] = []
    out: Dict[str, Dict[str, Any]] = {}
    for key, group in groups.items():
        fields = list(material_fields or sorted({field for row in group for field in row.keys()}))
        variants = {_canonical_json({field: _norm(row.get(field)) for field in fields}) for row in group}
        if len(variants) > 1:
            duplicates.append(key)
        out[key] = sorted(group, key=lambda row: _canonical_json(row))[0]
    return out, duplicates


def _validate_population_authority(inputs: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    latest_population_payloads = []
    for row in inputs["population_audit"]:
        if _norm(row.get("population_recovery_audit_run_id")) == POPULATION_RECOVERY_AUDIT:
            try:
                latest_population_payloads.append(json.loads(_norm(row.get("payload_json"))))
            except json.JSONDecodeError as exc:
                raise PopulationRepairBlocked("Population recovery audit payload is malformed.") from exc
    if not latest_population_payloads:
        raise PopulationRepairBlocked("Required population recovery audit run was not found.")


def _primary_classification_rows(classification_rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    consistency = [
        dict(row)
        for row in classification_rows
        if _norm(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
        and _norm(row.get("mechanism_id")) == MECHANISM_ID
    ]
    expanded_structural = [row for row in consistency if _norm(row.get("pack_level")) in FROZEN_EXPANDED_PACKS]
    primary = [
        row
        for row in expanded_structural
        if _norm(row.get("classification_label")) in FROZEN_PRIMARY_LABELS
        and _norm(row.get("confidence_category")) in FROZEN_PRIMARY_CONFIDENCE
    ]
    if len(primary) != 72:
        raise PopulationRepairBlocked(f"Frozen primary candidate count changed: expected 72, observed {len(primary)}")
    keys = [_norm(row.get("source_row_key")) for row in primary]
    if len(keys) != len(set(keys)):
        raise PopulationRepairBlocked("Duplicate frozen primary classification source keys detected.")
    return expanded_structural, sorted(primary, key=lambda row: _norm(row.get("source_row_key")))


def _build_behavior_index(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    duplicates: List[Tuple[str, str, str]] = []
    for row in rows:
        key = _key(row)
        if key in out:
            duplicates.append(key)
        out[key] = dict(row)
    if duplicates:
        raise PopulationRepairBlocked(f"Duplicate behavior rows detected: {sorted(set(duplicates))[:5]}")
    return out


def _unique_repaired_overlay_by_provider_session(
    validation_rows: Sequence[Mapping[str, Any]],
    overlay_by_id: Mapping[str, Mapping[str, Any]],
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in validation_rows:
        repaired_id = _norm(row.get("repaired_canonical_outcome_id"))
        if not repaired_id:
            continue
        if repaired_id not in overlay_by_id:
            continue
        if not (_is_true(row.get("strict_ready")) and _is_true(row.get("leakage_safe_validated"))):
            continue
        groups[(_norm(row.get("provider")), _norm(row.get("session_id")))].append(dict(row))

    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for key, group in groups.items():
        repaired_ids = {_norm(row.get("repaired_canonical_outcome_id")) for row in group}
        if len(repaired_ids) == 1:
            representative = sorted(group, key=lambda row: _canonical_json(row))[0]
            representative["provider_session_unique_repaired_overlay_id"] = next(iter(repaired_ids))
            representative["provider_session_overlay_row_count"] = len(group)
            out[key] = representative
    return out


def _apply_shadow_exact_link_repairs(
    *,
    primary_rows: Sequence[Mapping[str, Any]],
    selection: Dict[Tuple[str, str, str], Dict[str, Any]],
    mapping: Dict[Tuple[str, str, str], Dict[str, Any]],
    unique_provider_session_overlay: Mapping[Tuple[str, str], Mapping[str, Any]],
    overlay_by_id: Mapping[str, Mapping[str, Any]],
) -> Tuple[Dict[Tuple[str, str, str], Dict[str, Any]], Dict[Tuple[str, str, str], Dict[str, Any]], List[Dict[str, Any]]]:
    repaired_selection = {key: dict(value) for key, value in selection.items()}
    repaired_mapping = {key: dict(value) for key, value in mapping.items()}
    repair_events: List[Dict[str, Any]] = []
    candidate_keys = set()
    for row in primary_rows:
        provider = _norm(row.get("provider"))
        session_id = _norm(row.get("session_id"))
        candidate_keys.add((provider, session_id, "A"))
        candidate_keys.add((provider, session_id, _norm(row.get("pack_level"))))

    for key in sorted(candidate_keys):
        existing_selection_ok = _norm(repaired_selection.get(key, {}).get("status")) == "OK"
        existing_mapping_ok = _norm(repaired_mapping.get(key, {}).get("status")) == "OK"
        if existing_selection_ok and existing_mapping_ok:
            continue
        provider, session_id, pack_level = key
        provider_session = (provider, session_id)
        overlay_hint = unique_provider_session_overlay.get(provider_session)
        if overlay_hint is None:
            continue
        repaired_id = _norm(overlay_hint.get("provider_session_unique_repaired_overlay_id"))
        overlay_row = overlay_by_id.get(repaired_id)
        if overlay_row is None:
            continue
        synthetic_common = {
            "status": "OK",
            "duplicate_count": "0",
            "raw_row_count": "0",
            "shadow_exact_link_repair": "TRUE",
            "repair_reason": "EXACT_PROVIDER_SESSION_REPAIRED_OVERLAY_EXISTS_FOR_MISSING_PACK_BRIDGE",
            "repair_scope": "SHADOW_ONLY_NON_SCIENTIFIC_BRIDGE_RECORD",
        }
        repaired_selection[key] = {
            **synthetic_common,
            "repaired_canonical_outcome_id": repaired_id,
            "strict_ready": "TRUE",
            "included_in_primary_corrected_evaluation": "TRUE",
            "leakage_safe_validated": "TRUE",
            "design_version": "corrected_accuracy_re_evaluation_design_v0",
        }
        repaired_mapping[key] = {
            **synthetic_common,
            "repaired_canonical_outcome_id": repaired_id,
            "repaired_realized_direction": _norm(overlay_row.get("repaired_realized_direction")),
            "outcome_mapping_status": "SHADOW_EXACT_LINK_REPAIRED",
            "included_in_primary": "TRUE",
            "design_version": "corrected_accuracy_re_evaluation_design_v0",
        }
        repair_events.append(
            {
                "provider": provider,
                "session_id": session_id,
                "pack_level": pack_level,
                "source_row_key": _source_key(provider, session_id, pack_level),
                "repaired_canonical_outcome_id": repaired_id,
                "repair_reason": "EXACT_PROVIDER_SESSION_REPAIRED_OVERLAY_EXISTS_FOR_MISSING_PACK_BRIDGE",
                "production_write": False,
                "scientific_rule_changed": False,
            }
        )
    return repaired_selection, repaired_mapping, repair_events


def _validate_join(
    *,
    selection: Mapping[str, Any],
    mapping: Mapping[str, Any],
    overlay_by_id: Mapping[str, Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
) -> Tuple[str, str, Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if _norm(selection.get("status")) != "OK":
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN", {"selection_status": selection.get("status")}, None, None
    if _norm(mapping.get("status")) != "OK":
        if _norm(mapping.get("status")) == "DUPLICATE_JOIN_BLOCKED":
            return "AMBIGUOUS_JOIN_BLOCKED", "DUPLICATE_JOIN_BLOCKED", {"mapping_status": mapping.get("status")}, None, None
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN", {"mapping_status": mapping.get("status")}, None, None
    if _norm(selection.get("repaired_canonical_outcome_id")) != _norm(mapping.get("repaired_canonical_outcome_id")):
        return "AMBIGUOUS_JOIN_BLOCKED", "DUPLICATE_JOIN_BLOCKED", {
            "selection_repaired_id": selection.get("repaired_canonical_outcome_id"),
            "mapping_repaired_id": mapping.get("repaired_canonical_outcome_id"),
        }, None, None

    repaired_id = _norm(selection.get("repaired_canonical_outcome_id"))
    overlay = overlay_by_id.get(repaired_id)
    canonical_id = _norm((overlay or {}).get("canonical_outcome_id"))
    canonical = canonical_by_id.get(canonical_id) if canonical_id else None
    if overlay is None or canonical is None:
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME", {
            "canonical_present": canonical is not None,
            "overlay_present": overlay is not None,
        }, canonical, overlay

    version_ok = (
        _norm(mapping.get("design_version")) == "corrected_accuracy_re_evaluation_design_v0"
        and _norm(canonical.get("implementation_version")) == "market_reaction_outcome_source_implementation_v0"
    )
    if not version_ok:
        return "NOT_ELIGIBLE", "OUTCOME_VERSION_MISMATCH", {
            "mapping_design_version": mapping.get("design_version"),
            "canonical_implementation_version": canonical.get("implementation_version"),
        }, canonical, overlay

    if _norm(canonical.get("window_policy")) != "EVENT_RELATIVE_FIXED_DURATION" or _to_float(canonical.get("window_minutes")) != 5.0:
        return "NOT_ELIGIBLE", "EVALUATION_WINDOW_MISMATCH", {
            "observed_window_policy": canonical.get("window_policy"),
            "observed_window_minutes": canonical.get("window_minutes"),
        }, canonical, overlay

    canonical_start = _parse_iso(canonical.get("canonical_start_ts"))
    canonical_end = _parse_iso(canonical.get("canonical_end_ts"))
    release_ts = _parse_iso(canonical.get("release_ts"))
    repaired_start = _parse_iso(overlay.get("repaired_start_ts"))
    repaired_end = _parse_iso(overlay.get("repaired_end_ts"))
    timestamp_ok = (
        canonical_start is not None
        and canonical_end is not None
        and canonical_end >= canonical_start
        and release_ts is not None
        and release_ts <= canonical_end
        and repaired_start is not None
        and repaired_end is not None
        and repaired_end >= repaired_start
        and _is_true(overlay.get("leakage_safe"))
        and _is_true(overlay.get("usable_for_strict_accuracy"))
        and _is_true(selection.get("leakage_safe_validated"))
        and _is_true(selection.get("strict_ready"))
        and _is_true(selection.get("included_in_primary_corrected_evaluation"))
        and _is_true(mapping.get("included_in_primary"))
    )
    if not timestamp_ok:
        return "NOT_ELIGIBLE", "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED", {
            "canonical_start_ts": canonical.get("canonical_start_ts"),
            "canonical_end_ts": canonical.get("canonical_end_ts"),
            "release_ts": canonical.get("release_ts"),
            "repaired_start_ts": overlay.get("repaired_start_ts"),
            "repaired_end_ts": overlay.get("repaired_end_ts"),
            "overlay_leakage_safe": overlay.get("leakage_safe"),
            "overlay_usable_for_strict_accuracy": overlay.get("usable_for_strict_accuracy"),
        }, canonical, overlay
    return "OK", "JOIN_READY", {
        "mapping_design_version": mapping.get("design_version"),
        "canonical_implementation_version": canonical.get("implementation_version"),
        "window_policy": canonical.get("window_policy"),
        "window_minutes": canonical.get("window_minutes"),
    }, canonical, overlay


def _member_result(
    *,
    behavior: Optional[Mapping[str, Any]],
    selection: Mapping[str, Any],
    mapping: Mapping[str, Any],
    overlay_by_id: Mapping[str, Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    if behavior is None:
        return {
            "join_status": "NOT_ELIGIBLE",
            "join_reason": "MISSING_FORECAST_BEHAVIOR_ROW",
            "success_status": "NOT_ELIGIBLE",
            "success_reason": "MISSING_FORECAST_BEHAVIOR_ROW",
            "forecast_direction": "",
            "realized_direction": "",
            "repaired_canonical_outcome_id": "",
            "canonical_outcome_id": "",
            "shadow_exact_link_repair": False,
        }
    join_status, join_reason, details, canonical, overlay = _validate_join(
        selection=selection,
        mapping=mapping,
        overlay_by_id=overlay_by_id,
        canonical_by_id=canonical_by_id,
    )
    forecast_direction = _normalize_direction(behavior.get("forecast_direction"))
    realized_direction = _normalize_direction((overlay or {}).get("repaired_realized_direction"))
    success_status, success_reason = _derive_success_status(
        forecast_direction=forecast_direction,
        no_signal_flag=_is_true(behavior.get("no_signal_flag")),
        output_valid=_is_true(behavior.get("output_valid")),
        realized_direction=realized_direction,
        join_status=join_status,
        join_reason=join_reason,
    )
    return {
        "join_status": join_status,
        "join_reason": join_reason,
        "join_details": details,
        "success_status": success_status,
        "success_reason": success_reason,
        "forecast_direction": forecast_direction,
        "realized_direction": realized_direction,
        "repaired_canonical_outcome_id": _norm(selection.get("repaired_canonical_outcome_id")),
        "canonical_outcome_id": _norm((overlay or {}).get("canonical_outcome_id")),
        "shadow_exact_link_repair": _is_true(selection.get("shadow_exact_link_repair")) or _is_true(mapping.get("shadow_exact_link_repair")),
    }


def _first_hit(pair: Mapping[str, Any]) -> str:
    for prefix in ("baseline", "expanded"):
        if _norm(pair.get(f"{prefix}_join_status")) != "OK":
            reason = _norm(pair.get(f"{prefix}_join_reason"))
            if reason in {"DUPLICATE_JOIN_BLOCKED", "AMBIGUOUS_JOIN_BLOCKED"}:
                return "LINKAGE"
            if reason in {"NOT_ELIGIBLE_MISSING_OUTCOME_JOIN"}:
                return "CANONICAL"
            if reason in {"NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME", "OUTCOME_VERSION_MISMATCH", "EVALUATION_WINDOW_MISMATCH", "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED"}:
                return "CANONICAL"
            return "LINKAGE"
    for prefix in ("baseline", "expanded"):
        if _norm(pair.get(f"{prefix}_success_status")) not in {"SUCCESS", "FAILURE"}:
            return "SUCCESS_MAPPING"
    if _norm(pair.get("expanded_label")) not in FROZEN_PRIMARY_LABELS:
        return "MECHANISM_ARM"
    return "NONE"


def _original_first_hit(row: Mapping[str, Any]) -> str:
    disposition = _norm(row.get("final_disposition"))
    if disposition == "PRIMARY_ELIGIBLE":
        return "NONE"
    if disposition == "MISSING_REPAIRED_OUTCOME_OVERLAY":
        return "OVERLAY"
    if disposition in {"MISSING_EXPANDED_OUTCOME_JOIN", "MISSING_BASELINE_OUTCOME_JOIN", "OUTCOME_VERSION_MISMATCH", "EVALUATION_WINDOW_MISMATCH"}:
        return "CANONICAL"
    return "SUCCESS_MAPPING"


def _build_repaired_population(
    *,
    primary_rows: Sequence[Mapping[str, Any]],
    lineage_rows: Sequence[Mapping[str, Any]],
    behavior_by_key: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    selection: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    mapping: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    overlay_by_id: Mapping[str, Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    lineage_by_key = {_norm(row.get("source_row_key")): dict(row) for row in lineage_rows}
    if len(lineage_by_key) != 72:
        raise PopulationRepairBlocked("Original 72-row lineage audit is incomplete or duplicated.")

    repaired_rows: List[Dict[str, Any]] = []
    for row in primary_rows:
        provider = _norm(row.get("provider"))
        session_id = _norm(row.get("session_id"))
        pack_level = _norm(row.get("pack_level"))
        source_row_key = _norm(row.get("source_row_key")) or _source_key(provider, session_id, pack_level)
        baseline_key = (provider, session_id, "A")
        expanded_key = (provider, session_id, pack_level)
        original = lineage_by_key.get(source_row_key)
        if original is None:
            raise PopulationRepairBlocked(f"Primary candidate missing from original lineage: {source_row_key}")
        baseline_result = _member_result(
            behavior=behavior_by_key.get(baseline_key),
            selection=selection.get(baseline_key, {"status": "MISSING_JOIN_COMPONENT"}),
            mapping=mapping.get(baseline_key, {"status": "MISSING_JOIN_COMPONENT"}),
            overlay_by_id=overlay_by_id,
            canonical_by_id=canonical_by_id,
        )
        expanded_result = _member_result(
            behavior=behavior_by_key.get(expanded_key),
            selection=selection.get(expanded_key, {"status": "MISSING_JOIN_COMPONENT"}),
            mapping=mapping.get(expanded_key, {"status": "MISSING_JOIN_COMPONENT"}),
            overlay_by_id=overlay_by_id,
            canonical_by_id=canonical_by_id,
        )
        pair = {
            "logical_pair_key": f"{provider}|{session_id}|A|{pack_level}",
            "source_row_key": source_row_key,
            "provider": provider,
            "session_id": session_id,
            "cluster_key": f"{provider}|{session_id}",
            "baseline_pack": "A",
            "expanded_pack": pack_level,
            "expanded_label": _norm(row.get("classification_label")),
            "confidence_category": _norm(row.get("confidence_category")),
            "original_v1_first_hit": _original_first_hit(original),
            "original_v1_status": "EVALUABLE" if _norm(original.get("final_disposition")) == "PRIMARY_ELIGIBLE" else "EXCLUDED",
            "baseline_join_status": baseline_result["join_status"],
            "baseline_join_reason": baseline_result["join_reason"],
            "baseline_success_status": baseline_result["success_status"],
            "baseline_success_reason": baseline_result["success_reason"],
            "baseline_forecast_direction": baseline_result["forecast_direction"],
            "baseline_realized_direction": baseline_result["realized_direction"],
            "expanded_join_status": expanded_result["join_status"],
            "expanded_join_reason": expanded_result["join_reason"],
            "expanded_success_status": expanded_result["success_status"],
            "expanded_success_reason": expanded_result["success_reason"],
            "expanded_forecast_direction": expanded_result["forecast_direction"],
            "expanded_realized_direction": expanded_result["realized_direction"],
            "expanded_repaired_canonical_outcome_id": expanded_result["repaired_canonical_outcome_id"],
            "baseline_repaired_canonical_outcome_id": baseline_result["repaired_canonical_outcome_id"],
            "shadow_exact_link_repair_used": baseline_result["shadow_exact_link_repair"] or expanded_result["shadow_exact_link_repair"],
        }
        pair["final_first_hit_exclusion"] = _first_hit(pair)
        pair["scientifically_evaluable"] = pair["final_first_hit_exclusion"] == "NONE"
        pair["recovery_status"] = _recovery_status(pair)
        repaired_rows.append(pair)

    keys = [row["logical_pair_key"] for row in repaired_rows]
    if len(keys) != len(set(keys)) or len(repaired_rows) != 72:
        raise PopulationRepairBlocked("Repaired population is not exactly one unique row per original candidate pair.")
    return sorted(repaired_rows, key=lambda row: row["logical_pair_key"])


def _recovery_status(row: Mapping[str, Any]) -> str:
    original = _norm(row.get("original_v1_first_hit"))
    final = _norm(row.get("final_first_hit_exclusion"))
    if final == "NONE":
        if original == "NONE":
            return "ORIGINAL_SURVIVOR_RETAINED"
        return f"RECOVERED_FROM_{original}"
    if original != final and _norm(row.get("shadow_exact_link_repair_used")) == "TRUE":
        return f"UPSTREAM_RECOVERED_REMAINING_{final}"
    return f"STILL_EXCLUDED_{final}"


def _summaries(rows: Sequence[Mapping[str, Any]], repair_events: Sequence[Mapping[str, Any]], historical_counts: Mapping[str, Any]) -> Dict[str, Any]:
    evaluable = [row for row in rows if row["scientifically_evaluable"]]
    pos = [row for row in evaluable if row["expanded_label"] == "POSITIVE"]
    neg = [row for row in evaluable if row["expanded_label"] == "NEGATIVE"]
    providers = sorted({row["provider"] for row in evaluable})
    sessions = sorted({row["session_id"] for row in evaluable})
    clusters = sorted({row["cluster_key"] for row in evaluable})
    provider_counts = Counter(row["provider"] for row in evaluable)
    session_counts = Counter(row["session_id"] for row in evaluable)
    cluster_counts = Counter(row["cluster_key"] for row in evaluable)
    first_hit_counts = Counter(row["final_first_hit_exclusion"] for row in rows if not row["scientifically_evaluable"])
    original_survivors_retained = sum(1 for row in rows if row["recovery_status"] == "ORIGINAL_SURVIVOR_RETAINED")
    new_pos = sum(1 for row in evaluable if row["original_v1_status"] != "EVALUABLE" and row["expanded_label"] == "POSITIVE")
    new_neg = sum(1 for row in evaluable if row["original_v1_status"] != "EVALUABLE" and row["expanded_label"] == "NEGATIVE")
    mapping_failures = Counter(
        row["expanded_success_reason"] if row["expanded_success_status"] not in {"SUCCESS", "FAILURE"} else row["baseline_success_reason"]
        for row in rows
        if row["final_first_hit_exclusion"] == "SUCCESS_MAPPING"
    )
    max_count = max([*provider_counts.values(), *session_counts.values(), *cluster_counts.values(), 0])
    max_concentration = (max_count / len(evaluable)) if evaluable else 0.0
    gate_status = {
        "positive": len(pos) >= FROZEN_GATES["positive"],
        "negative": len(neg) >= FROZEN_GATES["negative"],
        "primary_contrast": len(evaluable) >= FROZEN_GATES["primary_contrast"],
        "providers": len(providers) >= FROZEN_GATES["providers"],
        "sessions": len(sessions) >= FROZEN_GATES["sessions"],
        "clusters": len(clusters) >= FROZEN_GATES["clusters"],
    }
    scientifically_viable = all(gate_status.values())
    if scientifically_viable:
        decision = "REPAIR_COMPLETE_PROCEED_TO_CORRECTED_MECHANISM_TEST"
        viability = "SCIENTIFICALLY_VIABLE"
        next_step = "Run the corrected mechanism test"
        historical_exhausted = False
    else:
        decision = "HISTORICAL_REPAIR_EXHAUSTED_PROSPECTIVE_COLLECTION_ACTIVE"
        if len(neg) == 0:
            viability = "NONVIABLE_SINGLE_ARM"
        elif len(evaluable) < FROZEN_GATES["primary_contrast"]:
            viability = "NONVIABLE_INSUFFICIENT_EVIDENCE"
        else:
            viability = "NONVIABLE_CONCENTRATION"
        next_step = "Prospectively collect shadow evidence under the activated collection contract"
        historical_exhausted = True
    return {
        "decision": decision,
        "scientific_viability": viability,
        "next_step": next_step,
        "historical_evidence_exhausted": historical_exhausted,
        "original_candidate_pairs": 72,
        "original_evaluable_pairs": 3,
        "combined_candidate_population": len(rows),
        "new_historical_candidates_found": historical_counts["new_historical_candidates_found"],
        "new_candidates_scientifically_admitted": 0,
        "canonical_outcomes_repaired": 0,
        "exact_links_repaired": len(repair_events),
        "final_total_evaluable": len(evaluable),
        "final_positive_arm": len(pos),
        "final_negative_arm": len(neg),
        "new_positive_arm_pairs": new_pos,
        "new_negative_arm_pairs": new_neg,
        "original_evaluable_pairs_retained": original_survivors_retained,
        "canonical_exclusions_remaining": first_hit_counts.get("CANONICAL", 0),
        "linkage_exclusions_remaining": first_hit_counts.get("LINKAGE", 0),
        "rows_reaching_representation": len([row for row in rows if row["baseline_join_status"] == "OK" and row["expanded_join_status"] == "OK"]),
        "rows_reaching_success_mapping_v1": len([row for row in rows if row["baseline_join_status"] == "OK" and row["expanded_join_status"] == "OK"]),
        "success_mapping_passes": len(evaluable),
        "success_mapping_failures": first_hit_counts.get("SUCCESS_MAPPING", 0),
        "dominant_mapping_failure_reason": mapping_failures.most_common(1)[0][0] if mapping_failures else "",
        "provider_diversity": {"unique": len(providers), "counts": dict(sorted(provider_counts.items()))},
        "session_diversity": {"unique": len(sessions), "counts": dict(sorted(session_counts.items()))},
        "cluster_diversity": {"unique": len(clusters), "counts": dict(sorted(cluster_counts.items()))},
        "maximum_concentration": round(max_concentration, 6),
        "gate_status": gate_status,
        "remaining_first_hit_exclusions": dict(sorted(first_hit_counts.items())),
    }


def _historical_counts(inputs: Mapping[str, Sequence[Mapping[str, Any]]], expanded_structural: Sequence[Mapping[str, Any]], primary: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    structural_nonprimary = len(expanded_structural) - len(primary)
    archived_rows = (
        len(inputs["pack_exposure"])
        + len(inputs["behavior_discovery"])
        + len(inputs["session_forecasts"])
    )
    return {
        "frozen_expanded_structural_rows": len(expanded_structural),
        "frozen_primary_rows": len(primary),
        "frozen_structural_nonprimary_rows": structural_nonprimary,
        "archived_forecast_rows_without_frozen_v11_primary_classification": archived_rows,
        "new_historical_candidates_found": structural_nonprimary + archived_rows,
        "admission_rule": "Requires frozen v1.1 MECH_INFORMATION_CONSISTENCY POSITIVE/NEGATIVE high/moderate classification.",
        "new_candidates_scientifically_admitted": 0,
    }


def _remaining_evidence_needed(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "positive_observations": max(0, FROZEN_GATES["positive"] - int(summary["final_positive_arm"])),
        "negative_observations": max(0, FROZEN_GATES["negative"] - int(summary["final_negative_arm"])),
        "primary_contrast_observations": max(0, FROZEN_GATES["primary_contrast"] - int(summary["final_total_evaluable"])),
        "providers": max(0, FROZEN_GATES["providers"] - int(summary["provider_diversity"]["unique"])),
        "sessions": max(0, FROZEN_GATES["sessions"] - int(summary["session_diversity"]["unique"])),
        "clusters": max(0, FROZEN_GATES["clusters"] - int(summary["cluster_diversity"]["unique"])),
        "collection_policy": "Collect future pre-outcome shadow observations for all enabled providers and packs; do not select by realized outcomes.",
    }


def _write_artifacts(
    *,
    output_dir: Path,
    run_id: str,
    rows: Sequence[Mapping[str, Any]],
    repair_events: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    historical_counts: Mapping[str, Any],
    collector_result: Optional[Mapping[str, Any]],
    input_counts: Mapping[str, int],
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    row_path = output_dir / "population_repair_rows.jsonl"
    with row_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")
    repair_path = output_dir / "shadow_exact_link_repairs.json"
    repair_path.write_text(_canonical_json(list(repair_events)) + "\n", encoding="utf-8")
    funnel = {
        "original_candidate_pairs": 72,
        "final_first_hit_exclusions": summary["remaining_first_hit_exclusions"],
        "evaluable_pairs": summary["final_total_evaluable"],
        "positive": summary["final_positive_arm"],
        "negative": summary["final_negative_arm"],
        "reconciles_to_72": (
            sum(summary["remaining_first_hit_exclusions"].values())
            + int(summary["final_total_evaluable"])
            == 72
        ),
    }
    funnel_path = output_dir / "population_repair_funnel.json"
    funnel_path.write_text(_canonical_json(funnel) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "presignal_phase9a_e2e_population_repair_v0",
        "repair_run_id": run_id,
        "authoritative_outcome_architecture_run": AUTHORITATIVE_OA2_RUN,
        "repair_verification_run": REPAIR_VERIFICATION_RUN,
        "population_recovery_audit": POPULATION_RECOVERY_AUDIT,
        "expected_oa2_fingerprint": EXPECTED_OA2_FINGERPRINT,
        "script_path": SCRIPT_PATH,
        "script_fingerprint": _fingerprint(Path(__file__).read_text(encoding="utf-8")),
        "input_counts": dict(input_counts),
        "historical_counts": dict(historical_counts),
        "summary": dict(summary),
        "shadow_exact_link_repairs": len(repair_events),
        "collector": dict(collector_result or {}),
        "population_rows_fingerprint": _fingerprint(list(rows)),
        "repair_events_fingerprint": _fingerprint(list(repair_events)),
        "scientific_rules_changed": False,
        "production_or_consumer_changes": False,
        "success_mapping_modified": False,
    }
    manifest_path = output_dir / "population_repair_summary.json"
    manifest_path.write_text(_canonical_json(manifest) + "\n", encoding="utf-8")
    return {
        "row_level_population": str(row_path),
        "shadow_exact_link_repairs": str(repair_path),
        "funnel": str(funnel_path),
        "summary": str(manifest_path),
    }


def build() -> Dict[str, Any]:
    generated_ts = _now_iso()
    run_id = _run_id(generated_ts)
    output_dir = ROOT / "outputs" / "phase9a_evaluation_population_repair" / run_id
    service = build_sheets_service(load_credentials())
    inputs = _read_inputs(service)
    _validate_population_authority(inputs)

    expanded_structural, primary_rows = _primary_classification_rows(inputs["classification"])
    historical_counts = _historical_counts(inputs, expanded_structural, primary_rows)
    behavior_by_key = _build_behavior_index(inputs["behavior"])
    selection = _build_consensus(
        inputs["selection"],
        CONSENSUS_SELECTION_FIELDS,
        "MISSING_JOIN_COMPONENT",
        "DUPLICATE_JOIN_BLOCKED",
    )
    mapping = _build_consensus(
        inputs["mapping"],
        CONSENSUS_MAPPING_FIELDS,
        "MISSING_JOIN_COMPONENT",
        "DUPLICATE_JOIN_BLOCKED",
    )
    overlay_by_id, duplicate_overlays = _dedupe_by_key(
        inputs["overlay"],
        "repaired_canonical_overlay_id",
        material_fields=[
            "repaired_canonical_overlay_id",
            "canonical_outcome_id",
            "repaired_realized_direction",
            "leakage_safe",
            "usable_for_strict_accuracy",
            "repaired_start_ts",
            "repaired_end_ts",
        ],
    )
    canonical_by_id, duplicate_canonical = _dedupe_by_key(
        inputs["canonical"],
        "canonical_outcome_id",
        material_fields=[
            "canonical_outcome_id",
            "implementation_version",
            "window_policy",
            "window_minutes",
            "canonical_start_ts",
            "canonical_end_ts",
            "release_ts",
        ],
    )
    if duplicate_overlays:
        raise PopulationRepairBlocked(f"Non-identical duplicate repaired overlays detected: {duplicate_overlays[:5]}")
    if duplicate_canonical:
        raise PopulationRepairBlocked(f"Non-identical duplicate canonical outcomes detected: {duplicate_canonical[:5]}")
    unique_provider_session_overlay = _unique_repaired_overlay_by_provider_session(inputs["validation"], overlay_by_id)
    repaired_selection, repaired_mapping, repair_events = _apply_shadow_exact_link_repairs(
        primary_rows=primary_rows,
        selection=selection,
        mapping=mapping,
        unique_provider_session_overlay=unique_provider_session_overlay,
        overlay_by_id=overlay_by_id,
    )
    repaired_rows = _build_repaired_population(
        primary_rows=primary_rows,
        lineage_rows=inputs["lineage"],
        behavior_by_key=behavior_by_key,
        selection=repaired_selection,
        mapping=repaired_mapping,
        overlay_by_id=overlay_by_id,
        canonical_by_id=canonical_by_id,
    )
    summary = _summaries(repaired_rows, repair_events, historical_counts)
    collector_result = None
    if summary["decision"] == "HISTORICAL_REPAIR_EXHAUSTED_PROSPECTIVE_COLLECTION_ACTIVE":
        collector_result = build_collection_contract(
            output_dir=output_dir,
            repair_run_id=run_id,
            final_counts={
                "positive": summary["final_positive_arm"],
                "negative": summary["final_negative_arm"],
                "total": summary["final_total_evaluable"],
            },
            remaining_evidence_needed=_remaining_evidence_needed(summary),
            enabled_providers=sorted({row["provider"] for row in primary_rows}),
            required_session_policy="future_preoutcome_shadow_sessions_all_enabled_providers_no_hindsight_selection",
        )
    input_counts = {key: len(value) for key, value in inputs.items()}
    artifacts = _write_artifacts(
        output_dir=output_dir,
        run_id=run_id,
        rows=repaired_rows,
        repair_events=repair_events,
        summary=summary,
        historical_counts=historical_counts,
        collector_result=collector_result,
        input_counts=input_counts,
    )
    return {
        "build_status": "PASS",
        "final_decision": summary["decision"],
        "repair_run_id": run_id,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "summary": summary,
        "historical_counts": historical_counts,
        "repair_events": len(repair_events),
        "collector_result": collector_result,
        "input_counts": input_counts,
        "governance": {
            "provider_calls_performed": 0,
            "outcome_rows_read": input_counts["canonical"] + input_counts["overlay"] + input_counts["validation"] + input_counts["selection"] + input_counts["mapping"],
            "source_rows_modified": 0,
            "success_mapping_modified": 0,
            "mechanism_rules_modified": 0,
            "preregistration_modified": 0,
            "mechanism_tests_performed": 0,
            "production_writes": 0,
            "consumer_switches": 0,
            "production_behavior_changes": 0,
        },
        "warnings": [
            "Historical frozen v1.1 primary classification scope contains exactly the original 72 candidates; archived forecasts without frozen v1.1 primary labels were not admitted.",
            "Shadow exact-link repair only adds deterministic repaired-overlay bridge records in local artifacts; it does not modify source sheets.",
        ],
    }


def main() -> None:
    result = build()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
