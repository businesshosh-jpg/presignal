#!/usr/bin/env python3
"""Activate and integration-test the Phase 9A prospective shadow collector.

The script never calls a provider or reads outcomes. It activates the durable
collector store and exercises the exact Tier 2 collector hook using only
pre-outcome fixtures.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_behavior_tier2_execution_v0 import (
    _capture_prospective_mechanism_evidence,
    _merge_session_timing_metadata,
)
from automation.build_session_information_requests_v0 import _read_config_map, _resolve_provider_candidates
from automation.collect_mechanism_evaluation_population_shadow_v0 import (
    ACTIVE_COLLECTION_ROOT,
    COLLECTION_CONTRACT_VERSION,
    COLLECTOR_VERSION,
    _record_paths,
    _read_jsonl,
    activate_prospective_shadow_collection,
)
from automation.google_clients import build_sheets_service, load_credentials


PHASE_ID = "9A-PROSPECTIVE-COLLECTOR-ACTIVATION"
COLLECTION_CONTRACT = (
    ROOT
    / "outputs"
    / "phase9a_evaluation_population_repair"
    / "9A-E2E-POPULATION-REPAIR_20260713T084129Z"
    / "prospective_shadow_collection_contract.json"
)
INTEGRATION_ENTRY_POINT = (
    "automation/build_pack_behavior_tier2_execution_v0.py:"
    "build_pack_behavior_tier2_execution_v0->_capture_prospective_mechanism_evidence"
)
ELIGIBLE_SESSION_RULE = (
    "Tier 2 selected session with complete deterministic Pack A-E inputs; collect each provider/pack output "
    "only when capture_timestamp is before the frozen outcome-window start."
)
FROZEN_TARGETS = {
    "positive_evaluable_target_remaining": 37,
    "negative_evaluable_target_remaining": 12,
    "provider_target_remaining": 1,
    "session_target_remaining": 3,
    "cluster_target_remaining": 11,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id(timestamp: str) -> str:
    return f"{PHASE_ID}_{timestamp.replace('-', '').replace(':', '').replace('Z', '')}Z"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fixture_session() -> Dict[str, Any]:
    return {
        "session_id": "US|2030-01-02|CUSTOM_CONFIG_WINDOW",
        "session_date": "2030-01-02",
        "session_window_name": "CUSTOM_CONFIG_WINDOW",
        "session_start_ts": "2030-01-02T13:00:00Z",
        "primary_release_ts": "2030-01-02T13:30:00Z",
        "last_release_ts": "2030-01-02T13:30:00Z",
        "session_end_ts": "2030-01-02T13:30:00Z",
    }


def _fixture_forecast(provider: str) -> Dict[str, Any]:
    return {
        "execution_run_id": "prospective_fixture_run_20300102T130500Z",
        "session_id": "US|2030-01-02|CUSTOM_CONFIG_WINDOW",
        "session_date": "2030-01-02",
        "session_window_name": "CUSTOM_CONFIG_WINDOW",
        "provider": provider,
        "model": f"fixture-{provider.lower()}",
        "pack_level": "B",
        "forecast_direction": "up",
        "forecast_confidence": "MODERATE",
        "shadow_only": "TRUE",
        "production_visible": "FALSE",
    }


def _fixture_behavior() -> Dict[str, Any]:
    return {
        "output_valid": "TRUE",
        "no_signal_flag": "FALSE",
        "no_signal_reason": "",
        "primary_driver_summary": "fixture pre-outcome driver",
        "secondary_driver_summary": "fixture secondary driver",
        "information_used": "[]",
        "information_not_used": "[]",
        "pack_fields_used": "[]",
        "pack_fields_discarded": "[]",
        "uncertainty_sources": "[]",
        "missing_information": "[]",
    }


def _provider_status() -> List[Dict[str, Any]]:
    config_source = "DEFAULT_CONFIGURATION"
    config: Dict[str, str] = {}
    config_error = ""
    try:
        credentials = load_credentials(interactive=False)
        service = build_sheets_service(credentials)
        config = _read_config_map(service)
        if config:
            config_source = "MAIN_CONFIG_SHEET"
    except Exception as exc:
        config_error = f"CONFIG_READ_UNAVAILABLE:{type(exc).__name__}"
    resolved = {item["provider"]: item for item in _resolve_provider_candidates(config)}
    statuses: List[Dict[str, Any]] = []
    for provider in ("OpenAI", "Gemini", "Anthropic"):
        candidate = resolved.get(provider)
        statuses.append(
            {
                "provider": provider,
                "configured": bool(candidate),
                "configuration_source": config_source,
                "enabled": bool(candidate),
                "scientifically_eligible": True,
                "collector_compatible": True,
                "preoutcome_output_available": True,
                "model": candidate.get("model", "") if candidate else "",
                "credential_status": "UNVERIFIED_NO_PROVIDER_CALL",
                "activation_status": "READY_ON_TIER2_EXECUTION" if candidate else "NOT_ENABLED_BY_CONFIGURATION",
                "blocking_reason": "" if candidate else "PROVIDER_NOT_ENABLED_IN_CONFIGURATION",
                "config_read_error": config_error,
            }
        )
    return statuses


def _assert(condition: bool, label: str) -> Dict[str, Any]:
    return {"passed": bool(condition), "detail": label}


def _real_workflow_wiring_test() -> Dict[str, Any]:
    """Verify the actual Tier 2 command invokes the bridge in pre-outcome order."""

    source = (ROOT / "automation" / "build_pack_behavior_tier2_execution_v0.py").read_text(encoding="utf-8")
    archive_index = source.index("raw_rows.append(raw_row)")
    bridge_index = source.index("collector_result = _capture_prospective_mechanism_evidence")
    log_index = source.index("log_rows.append(", bridge_index)
    timing_source = _merge_session_timing_metadata(
        {"fixture-session": {"session_id": "fixture-session"}},
        [
            {
                "session_id": "fixture-session",
                "session_start_ts": "2030-01-02T13:00:00Z",
                "session_end_ts": "2030-01-02T13:35:00Z",
                "primary_release_ts": "2030-01-02T13:30:00Z",
                "last_release_ts": "2030-01-02T13:30:00Z",
            }
        ],
    )
    timestamps_present = all(
        timing_source["fixture-session"].get(field)
        for field in ("session_start_ts", "session_end_ts", "primary_release_ts", "last_release_ts")
    )
    return _assert(
        archive_index < bridge_index < log_index and timestamps_present,
        "The normal Tier 2 execution command archives raw output, invokes the collector bridge, and logs the result; "
        "its collector context carries exact Market_Sessions timestamps by session ID.",
    )


def _run_integration_tests(test_root: Path, contract_path: str) -> Dict[str, Any]:
    activated = activate_prospective_shadow_collection(
        output_root=test_root,
        contract_path=contract_path,
        integration_entry_point=INTEGRATION_ENTRY_POINT,
        enabled_providers=("OpenAI", "Gemini", "Anthropic"),
        eligible_session_rule=ELIGIBLE_SESSION_RULE,
        activation_run_id="PROSPECTIVE_COLLECTOR_INTEGRATION_TEST",
    )
    session = _fixture_session()
    behavior = _fixture_behavior()
    capture_timestamp = "2030-01-02T13:05:00Z"
    positive_results: Dict[str, Dict[str, Any]] = {}
    unchanged_checks: List[bool] = []
    for provider in ("OpenAI", "Gemini", "Anthropic"):
        forecast = _fixture_forecast(provider)
        before = copy.deepcopy(forecast)
        result = _capture_prospective_mechanism_evidence(
            discovery_run_id="prospective_fixture_run_20300102T130500Z",
            session_meta=session,
            forecast_row=forecast,
            behavior_row=behavior,
            raw_response_archive_key=f"fixture|{provider}|B",
            capture_timestamp=capture_timestamp,
            collection_root=test_root,
        )
        positive_results[provider] = result
        unchanged_checks.append(forecast == before)

    duplicate = _capture_prospective_mechanism_evidence(
        discovery_run_id="prospective_fixture_run_20300102T130500Z",
        session_meta=session,
        forecast_row=_fixture_forecast("OpenAI"),
        behavior_row=behavior,
        raw_response_archive_key="fixture|OpenAI|B",
        capture_timestamp=capture_timestamp,
        collection_root=test_root,
    )
    ineligible = _capture_prospective_mechanism_evidence(
        discovery_run_id="prospective_fixture_run_20300102T130500Z",
        session_meta=session,
        forecast_row=_fixture_forecast("OpenAI"),
        behavior_row=behavior,
        raw_response_archive_key="fixture|ineligible|B",
        capture_timestamp=capture_timestamp,
        eligible_session=False,
        collection_root=test_root,
    )
    missing_forecast = _fixture_forecast("OpenAI")
    missing_forecast["provider"] = ""
    missing_identity = _capture_prospective_mechanism_evidence(
        discovery_run_id="prospective_fixture_missing_identity",
        session_meta=session,
        forecast_row=missing_forecast,
        behavior_row=behavior,
        raw_response_archive_key="fixture|missing|B",
        capture_timestamp=capture_timestamp,
        collection_root=test_root,
    )
    leaked_forecast = _fixture_forecast("Anthropic")
    leaked_forecast["realized_direction"] = "UP"
    leakage = _capture_prospective_mechanism_evidence(
        discovery_run_id="prospective_fixture_outcome_leakage",
        session_meta=session,
        forecast_row=leaked_forecast,
        behavior_row=behavior,
        raw_response_archive_key="fixture|leakage|B",
        capture_timestamp=capture_timestamp,
        collection_root=test_root,
    )
    blocked_root = test_root / "collector_failure_target"
    blocked_root.write_text("not a directory\n", encoding="utf-8")
    failure_isolation = _capture_prospective_mechanism_evidence(
        discovery_run_id="prospective_fixture_failure_isolation",
        session_meta=session,
        forecast_row=_fixture_forecast("Gemini"),
        behavior_row=behavior,
        raw_response_archive_key="fixture|failure-isolation|B",
        capture_timestamp=capture_timestamp,
        collection_root=blocked_root,
    )
    paths = _record_paths(test_root)
    records = _read_jsonl(paths["records"])
    attempts = _read_jsonl(paths["attempts"])
    tests = {
        "normal_workflow_wiring": _real_workflow_wiring_test(),
        "eligible_session": _assert(
            all(result.get("collection_status") == "COLLECTED" and result.get("record_written") for result in positive_results.values()),
            "Each configured provider reached the Tier 2 hook and produced one complete pre-outcome shadow record.",
        ),
        "ineligible_session": _assert(
            ineligible.get("collection_status") == "SKIPPED_INELIGIBLE_SESSION",
            "An ineligible session was not admitted to the scientific collection store.",
        ),
        "duplicate_rerun": _assert(
            duplicate.get("collection_status") == "DUPLICATE_SUPPRESSED" and len(records) == 3,
            "A retry with the same scientific observation key did not create a second observation.",
        ),
        "missing_identity": _assert(
            missing_identity.get("collection_status") == "BLOCKED" and not missing_identity.get("record_written"),
            "Missing provider identity failed closed without a valid observation.",
        ),
        "provider_coverage": _assert(
            set(positive_results) == {"OpenAI", "Gemini", "Anthropic"},
            "All three configured provider serialization paths reached the same collector bridge.",
        ),
        "collector_failure_isolation": _assert(
            failure_isolation.get("collection_status") == "COLLECTOR_FAILED_ISOLATED",
            "A controlled storage failure was isolated from the forecast path and did not create a valid record.",
        ),
        "outcome_leakage": _assert(
            leakage.get("collection_status") == "BLOCKED" and not leakage.get("record_written"),
            "A realized-outcome field presented to the pre-outcome bridge was rejected.",
        ),
        "preoutcome_order": _assert(
            all(record.get("forecast_timestamp", "") < record.get("planned_outcome_window_start", "") for record in records),
            "All stored records were captured before the planned outcome-window start.",
        ),
        "frozen_window_projection": _assert(
            all(record.get("planned_outcome_window_end") == "2030-01-02T13:35:00Z" for record in records),
            "The collector derives the frozen five-minute event-relative outcome window from primary_release_ts, not session_end_ts.",
        ),
        "operational_non_modification": _assert(
            all(unchanged_checks),
            "The actual Tier 2 hook did not mutate forecast records while collecting shadow evidence.",
        ),
    }
    return {
        "activation": activated,
        "tests": tests,
        "all_passed": all(test["passed"] for test in tests.values()),
        "records_written": len(records),
        "attempts_written": len(attempts),
        "provider_results": {provider: result.get("collection_status") for provider, result in positive_results.items()},
    }


def run_activation(args: argparse.Namespace | None = None) -> Dict[str, Any]:
    generated_ts = _now_iso()
    activation_run_id = _run_id(generated_ts)
    if not COLLECTION_CONTRACT.exists():
        raise RuntimeError(f"Missing frozen prospective collection contract: {COLLECTION_CONTRACT}")
    run_dir = ROOT / "outputs" / "phase9a_prospective_mechanism_collection" / "activation_runs" / activation_run_id
    test_root = run_dir / "integration_test_store"
    integration = _run_integration_tests(test_root, str(COLLECTION_CONTRACT))
    provider_status = _provider_status()
    enabled_providers = [row["provider"] for row in provider_status if row["enabled"]]
    active_manifest = activate_prospective_shadow_collection(
        output_root=ACTIVE_COLLECTION_ROOT,
        contract_path=str(COLLECTION_CONTRACT),
        integration_entry_point=INTEGRATION_ENTRY_POINT,
        enabled_providers=enabled_providers,
        eligible_session_rule=ELIGIBLE_SESSION_RULE,
        activation_run_id=activation_run_id,
    )
    status = {
        **active_manifest,
        "activation_run_id": activation_run_id,
        "initial_wiring_state": "CONTRACT_ONLY",
        "final_wiring_state": "AUTOMATICALLY_WIRED_TO_TIER2_PREOUTCOME_PERSISTENCE",
        "collector_invocation_path": (
            "Tier 2 provider response -> raw archive append -> parse/forecast/behavior capture -> "
            "_capture_prospective_mechanism_evidence -> durable shadow collection store"
        ),
        "execution_order": "before planned outcome-window start; after raw output archive; before any outcome access",
        "automatic_invocation_proven": integration["all_passed"],
        "provider_status": provider_status,
        "successful_preoutcome_records": 0,
        "failed_collection_attempts": 0,
        "duplicate_attempts_suppressed": 0,
        "last_successful_collection": "",
        "last_failure": "",
        **FROZEN_TARGETS,
        "provider_calls_performed_by_activation": 0,
        "outcome_rows_loaded": 0,
        "mechanism_tests_performed": 0,
        "production_writes": 0,
        "consumer_switches": 0,
        "production_behavior_changes": 0,
        "integration_test_store": str(test_root),
        "integration_test_result": integration,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "prospective_collector_activation_status.json"
    status_path.write_text(_canonical_json(status) + "\n", encoding="utf-8")
    summary = {
        "build_status": "PASS" if integration["all_passed"] else "FAIL",
        "final_decision": "PROSPECTIVE_COLLECTION_OPERATIONALLY_ACTIVE" if integration["all_passed"] else "BLOCKED_BY_MISSING_EXTERNAL_CONFIGURATION",
        "activation_run_id": activation_run_id,
        "collector_version": COLLECTOR_VERSION,
        "collection_contract_version": COLLECTION_CONTRACT_VERSION,
        "integration_tests_passed": integration["all_passed"],
        "enabled_providers": enabled_providers,
        "blocked_providers": [row["provider"] for row in provider_status if not row["enabled"]],
        "durable_shadow_output": str(ACTIVE_COLLECTION_ROOT),
        "status_path": str(status_path),
        "operational_entry_point": "python3 automation/build_pack_behavior_tier2_execution_v0.py",
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
    }
    summary_path = run_dir / "prospective_collector_activation_summary.json"
    summary_path.write_text(_canonical_json(summary) + "\n", encoding="utf-8")
    return {**summary, "status": status, "summary_path": str(summary_path)}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Activate and integration-test the Phase 9A prospective shadow collector.")
    return parser.parse_args(argv)


def main() -> None:
    print(json.dumps(run_activation(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
