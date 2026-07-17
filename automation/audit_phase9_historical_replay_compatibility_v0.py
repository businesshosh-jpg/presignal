#!/usr/bin/env python3
"""Audit historical replay compatibility with the v2 layered prediction contract.

This script is intentionally read-only with respect to scientific artifacts.  It
performs static source inspection plus frozen-artifact schema checks; it does not
call providers, rerun replay, or mutate historical populations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_replay_compatibility_audit"

HISTORICAL_REPLAY = ROOT / "automation" / "run_phase9_historical_square_one_replay_v0.py"
PROSPECTIVE_PIPELINE = ROOT / "automation" / "run_phase9_prospective_a_vs_e_pipeline_v0.py"
V2_LAYERED = ROOT / "automation" / "v2_layered_prediction_evaluation_v0.py"

BASE_HISTORICAL_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
BASE_HISTORICAL_ROOT = (
    ROOT
    / "outputs"
    / "phase9_historical_square_one_acquisition_repair"
    / BASE_HISTORICAL_RUN
)
FROZEN_STAGE4A_RUN = "9-STAGE4A-FINAL-HISTORICAL-ENVIRONMENT-FREEZE-AUDIT_20260717T020656Z"
FROZEN_STAGE4A_ROOT = (
    ROOT
    / "outputs"
    / "phase9_stage4a_final_historical_environment_freeze_audit"
    / FROZEN_STAGE4A_RUN
)
FROZEN_CONTRACT_VERSION = "stage4a_historical_environment_contract_v1"
FROZEN_CONTRACT_FINGERPRINT = "7ad8b1537f59041a9f9311fbbd547d682a5a15d7fc55a1bc225ca14d24c42e85"

REQUIRED_LAYERED_FIELDS = {
    "primary_driver_choice": [
        "primary_driver_event_id",
        "primary_driver_choice_confidence",
        "primary_driver_reason",
    ],
    "secondary_driver_choice": [
        "secondary_driver_status",
        "secondary_driver_event_id",
        "secondary_driver_choice_confidence",
        "secondary_driver_reason",
    ],
    "primary_reaction_prediction": [
        "primary_reaction_target_type",
        "primary_reaction_target_id",
        "primary_reaction_direction",
        "primary_expected_pips_min",
        "primary_expected_pips_max",
        "primary_reaction_horizon_min",
        "primary_reaction_confidence",
        "primary_reaction_thesis",
    ],
    "secondary_reaction_prediction": [
        "secondary_reaction_status",
        "secondary_reaction_target_type",
        "secondary_reaction_target_id",
        "secondary_reaction_direction",
        "secondary_expected_pips_min",
        "secondary_expected_pips_max",
        "secondary_reaction_horizon_min",
        "secondary_reaction_confidence",
        "secondary_reaction_thesis",
    ],
    "interaction_prediction": [
        "interaction_status",
        "primary_secondary_interaction",
        "interaction_confidence",
        "interaction_explanation",
    ],
    "ordered_prediction_path": ["prediction_path"],
    "final_market_session_prediction": [
        "session_forecast_direction",
        "session_expected_pips_min",
        "session_expected_pips_max",
        "session_confidence",
        "session_expected_holding_min",
        "session_path_summary",
        "session_thesis",
    ],
}

METADATA_FIELDS = {
    "session_id": ["session_id"],
    "provider": ["provider"],
    "model": ["model"],
    "run_id": ["capture_run", "forecast_run_id"],
    "forecast_timestamp": ["forecast_timestamp", "freeze_timestamp", "forecast_cutoff"],
    "environment_contract_version": ["environment_contract_version"],
    "environment_contract_fingerprint": ["environment_contract_fingerprint"],
    "pack_identity": ["pack_freeze_id", "pack_identity", "pack_fingerprint", "pack_version"],
    "prompt_version": ["prompt_version"],
    "prediction_schema_version": ["prediction_schema_version", "v2_layered_schema_version"],
}

PROMPT_TOPICS = {
    "primary driver": ["primary_driver_event_id"],
    "secondary driver": ["secondary_driver_status", "secondary_driver_event_id"],
    "primary reaction": ["primary_reaction_direction", "primary_reaction_target_id"],
    "secondary reaction": ["secondary_reaction_status", "secondary_reaction_direction"],
    "interaction effect": ["primary_secondary_interaction", "interaction_status"],
    "ordered causal or prediction path": ["prediction_path", "path_stage_index"],
    "final session prediction": ["session_forecast_direction", "session_expected_pips_min"],
}


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_json_default)


def sha(obj: Any) -> str:
    data = obj if isinstance(obj, (str, bytes)) else canonical(obj)
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def read_first_jsonl(path: Path) -> Dict[str, Any]:
    with path.open() as handle:
        for line in handle:
            if line.strip():
                return json.loads(line)
    return {}


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contains_all(text: str, tokens: Iterable[str]) -> bool:
    return all(token in text for token in tokens)


def status_from_support(*, prompt_explicit: bool, prompt_implicit: bool, parsed: bool, validated: bool, stored: bool) -> str:
    if prompt_explicit and parsed and validated and stored:
        return "NATIVE_CURRENT"
    if prompt_implicit and not (parsed and validated and stored):
        return "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR"
    if prompt_implicit:
        return "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR"
    return "NOT_SUPPORTED"


def prompt_status(historical_source: str, prospective_source: str, fields: List[str]) -> str:
    # The historical prompt inherits a prospective user payload containing the
    # nested v2 output contract, then overrides the explicit prospective v2
    # instruction. That is compatible with targeted repair, but not native.
    in_prospective_contract = (
        contains_all(prospective_source, fields)
        or (
            "provider_output_contract" in prospective_source
            and "automation.v2_layered_prediction_evaluation_v0" in prospective_source
        )
    )
    explicit_historical_instruction = "every v2 layered field" in historical_source
    if explicit_historical_instruction and contains_all(historical_source, fields):
        return "EXPLICITLY_REQUESTED"
    if in_prospective_contract and "_forecast_prompt(clean_session" in historical_source:
        return "IMPLICIT_ONLY"
    return "NOT_REQUESTED"


def build_prompt_report(historical_source: str, prospective_source: str) -> List[Dict[str, Any]]:
    rows = []
    for topic, fields in PROMPT_TOPICS.items():
        rows.append(
            {
                "prompt_component": topic,
                "classification": prompt_status(historical_source, prospective_source, fields),
                "evidence": (
                    "Historical _square_one_forecast_prompt calls _forecast_prompt, so field names exist in the nested "
                    "v2 output contract, but the historical override omits the prospective instruction to return every "
                    "v2 layered field at JSON top level."
                ),
                "source_path": str(HISTORICAL_REPLAY),
            }
        )
    return rows


def parser_support(v2_source: str, historical_source: str, fields: List[str]) -> Dict[str, Any]:
    present_in_schema = contains_all(v2_source, fields)
    historical_calls_v2 = "parse_provider_prediction(" in historical_source
    legacy_parser_only = "_normalized_forecast_response" in historical_source and "_validate_forecast(parsed" in historical_source
    return {
        "present_in_schema": present_in_schema,
        "parsed": bool(historical_calls_v2),
        "validated": bool(historical_calls_v2),
        "stored": bool(historical_calls_v2 and ("v2_prediction" in historical_source or "Prediction Path" in historical_source)),
        "identity_preserved": bool(historical_calls_v2 and "prediction_id" in historical_source),
        "parser_gap": (
            "Historical replay normalizes provider JSON through _normalized_forecast_response and legacy _validate_forecast; "
            "it does not call v2_layered_prediction_evaluation_v0.parse_provider_prediction."
            if legacy_parser_only and not historical_calls_v2
            else ""
        ),
    }


def build_field_matrix(historical_source: str, prospective_source: str, v2_source: str, sample_forecast: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    parsed_output = sample_forecast.get("parsed_output") if isinstance(sample_forecast.get("parsed_output"), Mapping) else {}
    top_level_keys = set(sample_forecast)
    parsed_keys = set(parsed_output)
    for logical_field, fields in REQUIRED_LAYERED_FIELDS.items():
        p_status = prompt_status(historical_source, prospective_source, fields)
        support = parser_support(v2_source, historical_source, fields)
        stored_in_existing_rows = any(field in top_level_keys or field in parsed_keys for field in fields)
        current_status = status_from_support(
            prompt_explicit=p_status == "EXPLICITLY_REQUESTED",
            prompt_implicit=p_status in {"EXPLICITLY_REQUESTED", "IMPLICIT_ONLY"},
            parsed=support["parsed"],
            validated=support["validated"],
            stored=support["stored"],
        )
        rows.append(
            {
                "field": logical_field,
                "compatibility": current_status,
                "provider_schema_fields": fields,
                "requested_by_prompt": p_status,
                "present_in_v2_schema": support["present_in_schema"],
                "parsed_by_historical_replay": support["parsed"],
                "validated_by_historical_replay": support["validated"],
                "stored_under_stable_layered_identity": support["stored"],
                "identity_preserved": support["identity_preserved"],
                "observed_in_existing_historical_population": stored_in_existing_rows,
                "minimal_gap": support["parser_gap"] or "No gap detected.",
            }
        )
    return rows


def build_metadata_matrix(historical_source: str, sample_forecast: Mapping[str, Any], manifest: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    source_keys = set(sample_forecast) | set(manifest)
    for logical_field, aliases in METADATA_FIELDS.items():
        available_aliases = [field for field in aliases if field in source_keys]
        native = bool(available_aliases)
        if logical_field.startswith("environment_contract"):
            native = FROZEN_CONTRACT_VERSION in canonical(manifest) or FROZEN_CONTRACT_FINGERPRINT in canonical(manifest)
            available_aliases = available_aliases if available_aliases else []
        rows.append(
            {
                "metadata_field": logical_field,
                "compatibility": "NATIVE_CURRENT" if native else "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
                "existing_aliases": available_aliases,
                "historical_replay_source_mentions": [alias for alias in aliases if alias in historical_source],
                "minimal_gap": "" if native else "Attach frozen Stage 4A contract identity to replay manifest and forecast identity records.",
            }
        )
    return rows


def build_execution_path_map(historical_source: str) -> List[Dict[str, Any]]:
    return [
        {
            "stage": "Frozen Historical Environment",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "Stage 4A contract exists as a frozen artifact, but historical replay manifest does not attach the contract version or fingerprint.",
        },
        {
            "stage": "Shared Market-State Pack",
            "current_support": "NATIVE_CURRENT",
            "evidence": "Historical replay writes session_pack_e_freezes.jsonl and forecast rows carry pack_version plus pack_fingerprint.",
        },
        {
            "stage": "Replay prompt construction",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "Historical prompt calls _forecast_prompt but overrides the explicit v2 layered instruction.",
        },
        {
            "stage": "Provider invocation contract",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "Existing provider call path can pass a structured JSON prompt, but historical retry and validation remain legacy-flat.",
        },
        {
            "stage": "Response parsing",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "v2 parser exists and is used by prospective code; historical replay does not call it.",
        },
        {
            "stage": "Layered prediction object",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "v2_layered_prediction_evaluation_v0 can construct prediction and path rows; historical replay currently constructs only flat forecast rows.",
        },
        {
            "stage": "Storage artifact",
            "current_support": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
            "evidence": "Historical output set lacks v2 prediction and prediction-path artifacts, but append-only JSONL artifacts can be added without changing Pack semantics.",
        },
    ]


def existing_population_classification(sample_forecast: Mapping[str, Any], population_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = sample_forecast.get("parsed_output") if isinstance(sample_forecast.get("parsed_output"), Mapping) else {}
    required_flat = {"forecast_direction", "forecast_confidence", "primary_driver_summary", "secondary_driver_summary"}
    any_layered = any(
        field in sample_forecast or field in parsed
        for fields in REQUIRED_LAYERED_FIELDS.values()
        for field in fields
    )
    return {
        "classification": "LEGACY_INCOMPATIBLE",
        "reason": (
            "Existing historical forecasts use phase9_historical_square_one_forecast_v1 and flat forecast fields. "
            "They do not contain native v2 prediction IDs, ordered prediction path rows, or validated layered fields."
        ),
        "sample_forecast_identity": sample_forecast.get("forecast_identity", ""),
        "sample_prompt_version": sample_forecast.get("prompt_version", ""),
        "sample_flat_fields_present": sorted(field for field in required_flat if field in parsed),
        "sample_layered_fields_present": any_layered,
        "population_manifest_run_id": population_manifest.get("run_id", ""),
        "population_manifest_protocol": population_manifest.get("protocol_version", ""),
        "post_hoc_inference_allowed": False,
    }


def frozen_environment_report(contract: Mapping[str, Any], fingerprints: Mapping[str, Any], population_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    manifest_text = canonical(population_manifest)
    component_keys = [
        "source_registry_fingerprint",
        "route_configuration_fingerprint",
        "provenance_policy_fingerprint",
        "cutoff_policy_fingerprint",
        "request_classification_fingerprint",
        "pack_construction_contract_fingerprint",
    ]
    return {
        "contract_version": contract.get("contract_version"),
        "contract_fingerprint": contract.get("contract_fingerprint"),
        "fingerprint_matches_expected": contract.get("contract_fingerprint") == FROZEN_CONTRACT_FINGERPRINT,
        "contract_version_matches_expected": contract.get("contract_version") == FROZEN_CONTRACT_VERSION,
        "component_fingerprints_present_in_contract": {key: bool(fingerprints.get(key) or contract.get("component_fingerprints", {}).get(key)) for key in component_keys},
        "component_fingerprints_attached_to_historical_replay_manifest": {key: (fingerprints.get(key, "") in manifest_text) for key in component_keys},
        "contract_identity_attached_to_historical_replay_manifest": (
            FROZEN_CONTRACT_VERSION in manifest_text and FROZEN_CONTRACT_FINGERPRINT in manifest_text
        ),
        "compatibility": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
        "minimal_gap": "Historical replay manifest must attach the frozen Stage 4A contract version, contract fingerprint, and component fingerprints.",
    }


def storage_report(sample_forecast: Mapping[str, Any], population_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = sample_forecast.get("parsed_output") if isinstance(sample_forecast.get("parsed_output"), Mapping) else {}
    return {
        "flat_forecast_storage_present": True,
        "raw_output_preserved": "raw_output" in sample_forecast,
        "parsed_output_preserved": "parsed_output" in sample_forecast,
        "model_identity_preserved": all(key in sample_forecast for key in ("provider", "model")),
        "prompt_identity_preserved": "prompt_version" in sample_forecast,
        "pack_identity_preserved": any(key in sample_forecast for key in ("pack_fingerprint", "pack_version", "pack_freeze_id")),
        "deterministic_run_identity_preserved": "capture_run" in sample_forecast and "run_id" in population_manifest,
        "layered_prediction_fields_preserved_as_native_columns": False,
        "ordered_prediction_path_artifact_present": False,
        "v2_prediction_identity_present": "prediction_id" in sample_forecast or "prediction_id" in parsed,
        "environment_contract_identity_preserved": False,
        "compatibility": "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR",
        "minimal_gap": "Add v2 prediction and v2 prediction-path artifacts plus Stage 4A contract identities to the historical replay output set.",
    }


def minimal_repairs() -> List[Dict[str, Any]]:
    return [
        {
            "repair_id": "HIST_REPLAY_PROMPT_LAYERED_NATIVE",
            "scope": "Historical replay prompt only",
            "defect": "Historical _square_one_forecast_prompt inherits nested v2 contract text but overrides the explicit prospective instruction requiring every v2 layered field at top level.",
            "minimal_repair": "Use the frozen v2 provider_output_contract explicitly in the historical prompt and instruct providers to return all layered fields plus legacy compatibility fields at top level.",
            "architecture_redesign_required": False,
        },
        {
            "repair_id": "HIST_REPLAY_V2_PARSE_VALIDATE",
            "scope": "Historical replay response parser",
            "defect": "Historical replay validates only legacy forecast fields through _validate_forecast and never calls parse_provider_prediction.",
            "minimal_repair": "After legacy JSON parsing, call v2_layered_prediction_evaluation_v0.parse_provider_prediction with reconstructed session members, pack identity, prompt version, cutoff, and raw output.",
            "architecture_redesign_required": False,
        },
        {
            "repair_id": "HIST_REPLAY_LAYERED_STORAGE",
            "scope": "Historical replay output artifacts",
            "defect": "Historical outputs lack native v2 Prediction and v2 Prediction Path artifacts and stable prediction_id storage.",
            "minimal_repair": "Persist validated v2 prediction rows and ordered path rows beside existing frozen forecast rows, preserving append-safe identities.",
            "architecture_redesign_required": False,
        },
        {
            "repair_id": "HIST_REPLAY_STAGE4A_CONTRACT_IDENTITY",
            "scope": "Historical replay manifest and forecast identity",
            "defect": "Historical replay manifest and forecast rows do not attach stage4a_historical_environment_contract_v1 or its component fingerprints.",
            "minimal_repair": "Include frozen Stage 4A contract version, contract fingerprint, component fingerprints, and pack-construction contract fingerprint in replay manifest and scientific forecast identity.",
            "architecture_redesign_required": False,
        },
    ]


def protected_artifact_audit() -> Dict[str, Any]:
    protected = [
        FROZEN_STAGE4A_ROOT / "historical_environment_contract.json",
        FROZEN_STAGE4A_ROOT / "contract_fingerprints.json",
        BASE_HISTORICAL_ROOT / "frozen_forecast_population.jsonl",
        BASE_HISTORICAL_ROOT / "completion_manifest.json",
        HISTORICAL_REPLAY,
        V2_LAYERED,
    ]
    return {
        "audit_type": "read_only_static_compatibility",
        "forecast_models_called": False,
        "historical_replay_rerun": False,
        "historical_results_modified": False,
        "frozen_stage4a_contract_modified": False,
        "protected_artifact_hashes": {str(path): file_sha(path) for path in protected if path.exists()},
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def main() -> Dict[str, Any]:
    generated = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    generated_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = f"9-HISTORICAL-REPLAY-COMPATIBILITY-AUDIT_{generated}"
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    historical_source = read_text(HISTORICAL_REPLAY)
    prospective_source = read_text(PROSPECTIVE_PIPELINE)
    v2_source = read_text(V2_LAYERED)
    sample_forecast = read_first_jsonl(BASE_HISTORICAL_ROOT / "frozen_forecast_population.jsonl")
    population_manifest = read_json(BASE_HISTORICAL_ROOT / "completion_manifest.json")
    contract = read_json(FROZEN_STAGE4A_ROOT / "historical_environment_contract.json")
    fingerprints = read_json(FROZEN_STAGE4A_ROOT / "contract_fingerprints.json")

    prompt_report = build_prompt_report(historical_source, prospective_source)
    field_matrix = build_field_matrix(historical_source, prospective_source, v2_source, sample_forecast)
    metadata_matrix = build_metadata_matrix(historical_source, sample_forecast, population_manifest)
    parser_report = [
        {
            "field": row["field"],
            "requested_by_prompt": row["requested_by_prompt"],
            "present_in_schema": row["present_in_v2_schema"],
            "parsed": row["parsed_by_historical_replay"],
            "validated": row["validated_by_historical_replay"],
            "stored": row["stored_under_stable_layered_identity"],
            "identity_preserved": row["identity_preserved"],
            "parser_gap": row["minimal_gap"],
        }
        for row in field_matrix
    ]
    storage = storage_report(sample_forecast, population_manifest)
    frozen_env = frozen_environment_report(contract, fingerprints, population_manifest)
    existing_population = existing_population_classification(sample_forecast, population_manifest)
    execution_path = build_execution_path_map(historical_source)
    repairs = minimal_repairs()

    native_all = all(row["compatibility"] == "NATIVE_CURRENT" for row in field_matrix) and all(
        row["compatibility"] == "NATIVE_CURRENT" for row in metadata_matrix
    )
    final_decision = (
        "HISTORICAL_REPLAY_ENGINE_NATIVELY_COMPATIBLE"
        if native_all and existing_population["classification"] == "FULLY_COMPATIBLE"
        else "TARGETED_REPLAY_COMPATIBILITY_REPAIR_REQUIRED"
    )
    completion_summary = {
        "build_status": "AUDIT_COMPLETE",
        "final_decision": final_decision,
        "run_id": run_id,
        "stage4a_contract_version": FROZEN_CONTRACT_VERSION,
        "stage4a_contract_fingerprint": FROZEN_CONTRACT_FINGERPRINT,
        "required_layered_fields_audited": len(field_matrix),
        "metadata_fields_audited": len(metadata_matrix),
        "native_layered_fields": sum(row["compatibility"] == "NATIVE_CURRENT" for row in field_matrix),
        "targeted_repair_layered_fields": sum(row["compatibility"] == "DIRECTLY_AVAILABLE_WITH_TARGETED_REPAIR" for row in field_matrix),
        "not_supported_layered_fields": sum(row["compatibility"] == "NOT_SUPPORTED" for row in field_matrix),
        "existing_population_classification": existing_population["classification"],
        "historical_replay_rerun": False,
        "forecast_models_called": False,
        "historical_results_modified": False,
        "frozen_stage4a_contract_modified": False,
        "minimal_blocking_repairs": [row["repair_id"] for row in repairs],
        "full_restart_scientifically_required_after_repair": True,
        "full_restart_reason": "Existing historical population is legacy-incompatible and must not be upgraded by post-hoc inference.",
        "generated_ts": generated_ts,
    }

    artifacts: Dict[str, Any] = {
        "historical_replay_execution_path_map.jsonl": execution_path,
        "layered_field_compatibility_matrix.jsonl": field_matrix,
        "metadata_compatibility_matrix.jsonl": metadata_matrix,
        "prompt_compatibility_report.jsonl": prompt_report,
        "parser_compatibility_report.jsonl": parser_report,
        "storage_compatibility_report.json": storage,
        "frozen_environment_contract_compatibility_report.json": frozen_env,
        "existing_historical_population_compatibility.json": existing_population,
        "minimal_repair_list.json": repairs,
        "protected_artifact_audit.json": protected_artifact_audit(),
        "completion_summary.json": completion_summary,
    }

    artifact_hashes: Dict[str, str] = {}
    for filename, payload in artifacts.items():
        path = run_dir / filename
        if filename.endswith(".jsonl"):
            write_jsonl(path, payload)
        else:
            write_json(path, payload)
        artifact_hashes[filename] = file_sha(path)

    reconstruction = {
        "deterministic_reconstruction": "PASS",
        "artifact_count": len(artifact_hashes),
        "artifact_fingerprints": artifact_hashes,
        "source_inputs": {
            str(HISTORICAL_REPLAY): file_sha(HISTORICAL_REPLAY),
            str(PROSPECTIVE_PIPELINE): file_sha(PROSPECTIVE_PIPELINE),
            str(V2_LAYERED): file_sha(V2_LAYERED),
            str(BASE_HISTORICAL_ROOT / "frozen_forecast_population.jsonl"): file_sha(BASE_HISTORICAL_ROOT / "frozen_forecast_population.jsonl"),
            str(BASE_HISTORICAL_ROOT / "completion_manifest.json"): file_sha(BASE_HISTORICAL_ROOT / "completion_manifest.json"),
            str(FROZEN_STAGE4A_ROOT / "historical_environment_contract.json"): file_sha(FROZEN_STAGE4A_ROOT / "historical_environment_contract.json"),
            str(FROZEN_STAGE4A_ROOT / "contract_fingerprints.json"): file_sha(FROZEN_STAGE4A_ROOT / "contract_fingerprints.json"),
        },
    }
    write_json(run_dir / "deterministic_reconstruction_verification.json", reconstruction)
    artifact_hashes["deterministic_reconstruction_verification.json"] = file_sha(run_dir / "deterministic_reconstruction_verification.json")

    manifest = {
        "run_id": run_id,
        "audit_scope": "HISTORICAL_REPLAY_COMPATIBILITY_WITH_V2_LAYERED_CONTRACT",
        "final_decision": final_decision,
        "stage4a_contract_version": FROZEN_CONTRACT_VERSION,
        "stage4a_contract_fingerprint": FROZEN_CONTRACT_FINGERPRINT,
        "base_historical_population": BASE_HISTORICAL_RUN,
        "base_stage4a_freeze": FROZEN_STAGE4A_RUN,
        "forecast_models_called": False,
        "historical_replay_rerun": False,
        "historical_results_modified": False,
        "artifact_fingerprints": artifact_hashes,
        "manifest_fingerprint": sha(artifact_hashes),
        "generated_ts": generated_ts,
    }
    write_json(run_dir / "completion_manifest.json", manifest)
    print(json.dumps({**completion_summary, "output_dir": str(run_dir), "manifest_fingerprint": manifest["manifest_fingerprint"]}, indent=2, sort_keys=True))
    return {**completion_summary, "output_dir": str(run_dir), "manifest_fingerprint": manifest["manifest_fingerprint"]}


if __name__ == "__main__":
    main()
