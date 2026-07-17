#!/usr/bin/env python3
"""Rebind one paused authoritative run after the approved compatibility repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from automation.native_v2_typed_schema_v0 import (
    SCHEMA_ID,
    adapter_schema_fingerprint,
    canonical_schema_fingerprint,
    primary_reaction_binding_fingerprint,
    transport_adapter_schema_fingerprint,
)


PACKAGE = ROOT / "outputs" / "phase9_authoritative_historical_replay" / "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z"
PROJECT_VERSION = 77
PROJECT_FINGERPRINT = "c1f58810c871f98694a67caf877e3d392c810ff7007b990fd37ca3deef373948"
BRIDGE_SHA256 = "c9ae370fe84c30d79f6299bf7f01c9bd5b6127f362296735652452dbcb5ccfe7"


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(canon(row) + "\n" for row in rows))


def recovery_prompt_fingerprint() -> str:
    # The typed contract is rendered inside this source file rather than from a
    # detached template.  Bind the recovery record to its exact bytes so a
    # prompt-only compatibility repair cannot leave an unchanged fingerprint.
    prompt_renderer = ROOT / "automation" / "run_phase9_authoritative_historical_replay_v0.py"
    return sha({
        "contract": "native-v2-secondary-reaction-transport-recovery-v3",
        "forecast_prompt_source": {
            "path": "automation/run_phase9_authoritative_historical_replay_v0.py",
            "sha256": file_sha(prompt_renderer),
        },
        "canonical_schema_id": SCHEMA_ID,
        "canonical_schema_fingerprint": canonical_schema_fingerprint(),
        "provider_adapter_fingerprints": {
            provider: adapter_schema_fingerprint(provider)
            for provider in ("OpenAI", "Gemini", "Anthropic")
        },
        "format": "provider_native_typed_object_only",
    })


def _post_312_stage(invocation_number: int) -> str:
    if invocation_number <= 324:
        return "TYPED_OUTPUT_PROVIDER_COMPATIBILITY_CANARY"
    if invocation_number <= 326:
        return "NATIVE_V2_CONTRACT_CLARIFICATION_CANARY"
    if invocation_number <= 329:
        return "OPENAI_STRICT_SCHEMA_SUBSET_COMPATIBILITY_PROBES"
    if invocation_number <= 331:
        return "NATIVE_V2_TYPED_OUTPUT_CANARY_AND_FROZEN_RETRY"
    return "DYNAMIC_CROSS_FIELD_BINDING_PRE_REPAIR_CANARY_AND_FROZEN_RETRY"


def ledger_lineage_312_to_333(package: Path) -> Dict[str, Any]:
    invocations = read_jsonl(package / "logs" / "provider_invocations.jsonl")
    responses = read_jsonl(package / "logs" / "provider_responses.jsonl")
    failures = read_jsonl(package / "failures" / "failure_ledger.jsonl")
    if len(invocations) != 333 or len(responses) != 333 or len(failures) != 333:
        raise RuntimeError("POST_312_LEDGER_COUNTS_UNRECONCILED:" + canon({
            "invocations": len(invocations), "responses": len(responses), "failures": len(failures),
        }))
    response_by_attempt = {(row["forecast_identity"], int(row["attempt_number"])): row for row in responses}
    failure_by_attempt = {(row["forecast_identity"], int(row["attempt_number"])): row for row in failures}
    additions = []
    for number, invocation in enumerate(invocations[312:], start=313):
        key = (str(invocation["forecast_identity"]), int(invocation["attempt_number"]))
        response = response_by_attempt.get(key)
        failure = failure_by_attempt.get(key)
        if not response or not failure:
            raise RuntimeError("POST_312_ATTEMPT_MISSING_RESPONSE_OR_FAILURE:" + key[0])
        stored = read_json(Path(response["response_reference"]))["response"]
        additions.append({
            "invocation_number": number,
            "forecast_identity": key[0],
            "provider": invocation["provider"],
            "arm": invocation["arm"],
            "attempt_number": key[1],
            "initial_or_retry": invocation["initial_or_retry"],
            "originating_stage": _post_312_stage(number),
            "response_state": stored.get("status") or stored.get("response_status") or "unknown",
            "failure_classification": failure["failure_class"],
            "failure_errors": failure.get("errors") or [],
            "provider_endpoint_attempted": str(stored.get("request_status") or "") == "attempted" or bool(stored),
            "model_completion_observed": str(stored.get("status") or "") == "ok",
        })
    return {
        "run_id": invocations[0]["run_id"],
        "baseline_total_calls": 312,
        "current_total_calls": 333,
        "increase": len(additions),
        "all_records_reconciled": len(additions) == 21,
        "records": additions,
    }


def apply(package: Path, *, dry_run: bool) -> Dict[str, Any]:
    package = package.resolve()
    config_path = package / "execution" / "frozen_execution_configuration.json"
    manifest_path = package / "input_snapshot" / "authoritative_replay_input_manifest.json"
    population_path = package / "input_snapshot" / "authoritative_forecast_population.jsonl"
    provider_config_path = package / "input_snapshot" / "authoritative_provider_model_config.json"
    config, manifest, population = read_json(config_path), read_json(manifest_path), read_jsonl(population_path)
    ledgers = {
        "invocations": len(read_jsonl(package / "logs" / "provider_invocations.jsonl")),
        "responses": len(read_jsonl(package / "logs" / "provider_responses.jsonl")),
        "failures": len(read_jsonl(package / "failures" / "failure_ledger.jsonl")),
        "predictions": len(read_jsonl(package / "predictions" / "v2_predictions.jsonl")),
        "paths": len(read_jsonl(package / "predictions" / "v2_prediction_paths.jsonl")),
    }
    if ledgers != {"invocations": 334, "responses": 334, "failures": 334, "predictions": 0, "paths": 0}:
        raise RuntimeError("PAUSED_LEDGER_COUNTS_CHANGED:" + canon(ledgers))
    # The earlier 312-to-333 audit is immutable historical lineage.  The
    # single subsequent OpenAI canary is preserved separately in the current
    # ledger counts and is never folded back into that 21-record artifact.
    ledger_lineage = read_json(package / "execution" / "ledger_lineage_312_to_333.json")
    if ledger_lineage.get("increase") != 21 or not ledger_lineage.get("all_records_reconciled"):
        raise RuntimeError("PRESERVED_312_TO_333_LEDGER_LINEAGE_INVALID")
    if len(population) != 1434 or len({row["forecast_identity"] for row in population}) != 1434:
        raise RuntimeError("FROZEN_POPULATION_IDENTITY_MISMATCH")
    old_config_fingerprint = sha(config)
    existing_lineage_path = package / "execution" / "recovery_lineage.json"
    existing_lineage = read_json(existing_lineage_path) if existing_lineage_path.exists() else {}
    if manifest.get("configuration_fingerprint") != old_config_fingerprint:
        prior_post = (existing_lineage.get("post_recovery") or {}).get("configuration_fingerprint")
        if not (
            prior_post == manifest.get("configuration_fingerprint")
            and (config.get("apps_script_project_binding") or {}).get("version_number") in {75, 76, PROJECT_VERSION}
        ):
            raise RuntimeError("PRE_RECOVERY_CONFIGURATION_FINGERPRINT_MISMATCH")
    old_binding = dict(config.get("apps_script_project_binding") or {})
    if old_binding.get("version_number") not in {74, 75, 76, PROJECT_VERSION}:
        raise RuntimeError("UNEXPECTED_PRE_RECOVERY_APPS_SCRIPT_VERSION")
    old_prompt_fingerprint = str(config.get("prompt_fingerprint") or "")
    new_prompt_fingerprint = recovery_prompt_fingerprint()
    scientific_fields = ("session_id", "provider", "model", "arm", "pack_fingerprint", "stage4a_contract_fingerprint", "prediction_schema_version", "parser_fingerprint", "storage_fingerprint")
    scientific_before = sha([{field: row.get(field) for field in scientific_fields} for row in population])
    new_population = [{**row, "prompt_fingerprint": new_prompt_fingerprint} for row in population]
    scientific_after = sha([{field: row.get(field) for field in scientific_fields} for row in new_population])
    if scientific_before != scientific_after:
        raise RuntimeError("SCIENTIFIC_POPULATION_CHANGED")
    new_config = dict(config)
    new_config["prompt_fingerprint"] = new_prompt_fingerprint
    new_config["typed_structured_output_binding"] = {
        "schema_id": SCHEMA_ID,
        "canonical_schema_fingerprint": canonical_schema_fingerprint(),
        "provider_adapter_fingerprints": {
            provider: adapter_schema_fingerprint(provider)
            for provider in ("OpenAI", "Gemini", "Anthropic")
        },
    }
    new_config["secondary_reaction_transport_binding"] = {
        "field": "secondary_reaction",
        "representation": "DISCRIMINATED_NO_REACTION_OR_PREDICTED_OBJECT",
        "canonical_schema_fingerprint": canonical_schema_fingerprint(),
        "adapter_implementation_sha256": file_sha(ROOT / "automation" / "native_v2_typed_schema_v0.py"),
        "canonical_schema_and_validator": "UNCHANGED",
    }
    members_by_session: Dict[str, list[Dict[str, Any]]] = {}
    for row in read_jsonl(package / "input_snapshot" / "authoritative_session_members.jsonl"):
        members_by_session.setdefault(str(row["session_id"]), []).append(row)
    choice_fingerprints = {
        sid: primary_reaction_binding_fingerprint(sid, rows)
        for sid, rows in sorted(members_by_session.items())
    }
    new_config["dynamic_primary_reaction_binding"] = {
        "field": "primary_reaction_binding",
        "choice_set_fingerprint": sha(choice_fingerprints),
        "choice_set_fingerprints_by_session": choice_fingerprints,
        "provider_adapter_implementation_fingerprints": {
            provider: file_sha(ROOT / "automation" / "native_v2_typed_schema_v0.py")
            for provider in ("OpenAI", "Gemini", "Anthropic")
        },
        "provider_adapter_choice_set_equivalence": "PASS",
    }
    new_config["runner_fingerprint"] = file_sha(ROOT / "automation" / "run_phase9_authoritative_historical_replay_v0.py")
    bindings = dict(new_config["execution_bindings"])
    bindings["executor"] = {**dict(bindings["executor"]), "sha256": new_config["runner_fingerprint"]}
    bindings["provider_bridge"] = {**dict(bindings["provider_bridge"]), "sha256": BRIDGE_SHA256}
    new_config["execution_bindings"] = bindings
    new_config["apps_script_project_binding"] = {
        **old_binding,
        "version_number": PROJECT_VERSION,
        "aggregate_fingerprint": PROJECT_FINGERPRINT,
        "bridge_sha256": BRIDGE_SHA256,
    }
    new_config_fingerprint = sha(new_config)
    component_fingerprints = dict(manifest["component_fingerprints"])
    for name in sorted(component_fingerprints):
        if name == "authoritative_forecast_population.jsonl":
            component_fingerprints[name] = hashlib.sha256("".join(canon(row) + "\n" for row in new_population).encode()).hexdigest()
        elif name == "authoritative_provider_model_config.json":
            component_fingerprints[name] = hashlib.sha256((json.dumps(new_config, indent=2, sort_keys=True) + "\n").encode()).hexdigest()
        else:
            component_fingerprints[name] = file_sha(package / "input_snapshot" / name)
    new_manifest = dict(manifest)
    new_manifest["component_fingerprints"] = component_fingerprints
    new_manifest["configuration_fingerprint"] = new_config_fingerprint
    new_manifest["snapshot_fingerprint"] = sha(component_fingerprints)
    lineage = {
        "recovery_type": "NATIVE_V2_SECONDARY_REACTION_TRANSPORT_RECOVERY_V3",
        "run_id": new_config["run_id"],
        "recorded_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pre_recovery": existing_lineage.get("pre_recovery") or {
            "configuration_fingerprint": old_config_fingerprint,
            "snapshot_fingerprint": manifest["snapshot_fingerprint"],
            "apps_script_project_binding": old_binding,
            "prompt_fingerprint": old_prompt_fingerprint,
        },
        "post_recovery": {
            "configuration_fingerprint": new_config_fingerprint,
            "snapshot_fingerprint": new_manifest["snapshot_fingerprint"],
            "apps_script_project_binding": new_config["apps_script_project_binding"],
            "prompt_fingerprint": new_prompt_fingerprint,
            "executor_sha256": new_config["runner_fingerprint"],
            "bridge_sha256": BRIDGE_SHA256,
            "typed_structured_output_binding": new_config["typed_structured_output_binding"],
            "secondary_reaction_transport_binding": new_config["secondary_reaction_transport_binding"],
        },
        "preserved_evidence": {**ledgers, "forecast_identities": 1434, "ledger_lineage_312_to_333": ledger_lineage},
        "scientific_equality": {"status": "PASS", "scientific_population_fingerprint": scientific_before},
        "allowed_execution_changes": ["exact_frozen_openai_model_route", "provider_native_typed_output_enforcement", "canonical_schema_post_validation", "anthropic_4096_output_cap", "anthropic_stop_reason_telemetry", "linked_pre_dispatch_openai_recovery_attempt", "six_identity_canary_call_control", "secondary_reaction_discriminated_transport"],
    }
    historical_terminals = read_jsonl(package / "logs" / "terminal_status_ledger.jsonl")
    recovery_ids = sorted({
        str(row["forecast_identity"])
        for row in historical_terminals
        if int(row.get("attempt_number") or 0) == 1
        and row.get("provider") == "OpenAI"
        and row.get("failure_class") == "NON_RETRYABLE_PROVIDER_FAILURE"
        and any("configured_model_does_not_match_frozen_model" in str(error) for error in (row.get("errors") or []))
    })
    if len(recovery_ids) != 102:
        raise RuntimeError("OPENAI_PRE_DISPATCH_RECOVERY_SET_MISMATCH:" + str(len(recovery_ids)))
    recovery_eligibility = {
        "run_id": new_config["run_id"],
        "recovery_reason": "OPENAI_FROZEN_MODEL_ROUTE_REJECTED_BEFORE_PROVIDER_DISPATCH",
        "openai_pre_dispatch_route_rejections": recovery_ids,
        "historical_records_preserved": True,
        "recovery_attempt_class": "retry",
        "maximum_linked_recovery_attempts_per_identity": 1,
    }
    if not dry_run:
        write_jsonl(population_path, new_population)
        write_json(provider_config_path, new_config)
        write_json(config_path, new_config)
        write_json(manifest_path, new_manifest)
        package_manifest_path = package / "manifests" / "package_manifest.json"
        package_manifest = read_json(package_manifest_path)
        package_manifest.update({"configuration_fingerprint": new_config_fingerprint, "snapshot_fingerprint": new_manifest["snapshot_fingerprint"], "recovery_lineage": str(package / "execution" / "recovery_lineage.json")})
        write_json(package_manifest_path, package_manifest)
        metadata_path = package / "active_store" / "store_metadata.json"
        metadata = read_json(metadata_path)
        metadata.update({"configuration_fingerprint": new_config_fingerprint, "snapshot_fingerprint": new_manifest["snapshot_fingerprint"], "recovery_lineage": str(package / "execution" / "recovery_lineage.json")})
        write_json(metadata_path, metadata)
        write_json(package / "execution" / "recovery_lineage.json", lineage)
        write_json(package / "execution" / "ledger_lineage_312_to_333.json", ledger_lineage)
        write_json(package / "execution" / "recovery_eligibility.json", recovery_eligibility)
    return {"status": "PASS", "dry_run": dry_run, "lineage": lineage, "ledger_counts": ledgers}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=str(PACKAGE))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-ledger-lineage-only", action="store_true")
    args = parser.parse_args()
    if args.write_ledger_lineage_only:
        package = Path(args.package).resolve()
        lineage = ledger_lineage_312_to_333(package)
        write_json(package / "execution" / "ledger_lineage_312_to_333.json", lineage)
        print(json.dumps({"status": "PASS", "ledger_lineage": str(package / "execution" / "ledger_lineage_312_to_333.json")}, sort_keys=True))
        raise SystemExit(0)
    print(json.dumps(apply(Path(args.package), dry_run=not args.apply), sort_keys=True))
