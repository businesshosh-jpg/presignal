"""Durable simplified replay canary executor.

The legacy ``execute`` helper remains an offline fixture path.  The durable
run API below uses per-record JSON ledgers written through temp-file + fsync +
atomic rename so crash state is visible without silently overwriting accepted
predictions.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from automation.build_simplified_replay_package_v1 import (
    file_sha,
    verify_package_manifest,
    verify_whole_package_fingerprint,
)
from automation.simplified_authoritative_replay_contract_v1 import (
    ReducedForecastError,
    driver_options,
    parse_reduced_output_json,
    reduced_output_response_schema,
    validate_and_resolve,
)


BRIDGE_FUNCTION_NAME = "apiCallAuthoritativeProviderJsonObject"
BRIDGE_SCHEMA_VERSION = "authoritative_historical_replay_bridge_v1"
LEDGER_DIRS = (
    "invocations",
    "raw_responses",
    "reservations",
    "transactions",
    "accepted_predictions",
    "failures",
    "terminal_identity_states",
)
TRANSIENT_FAILURES = {
    "timeout",
    "network_transport_failure",
    "temporary_provider_availability_failure",
}


class DurableExecutionError(ValueError):
    pass


class TransientDispatchError(RuntimeError):
    pass


class TemporaryProviderAvailabilityError(RuntimeError):
    pass


class RawPersistenceError(RuntimeError):
    pass


class PredictionPersistenceError(RuntimeError):
    pass


def execute(package: Path, identity: Mapping[str, Any], members, response: Mapping[str, Any], run_id="FUTURE-TEST-RUN"):
    logs = package / "canary_ledgers"
    logs.mkdir(exist_ok=True)
    fid = identity["forecast_identity"]
    raw = logs / (fid + ".raw.json")
    raw.write_text(json.dumps(response))
    inv = {
        "identity_id": fid,
        "run_id": run_id,
        "provider": identity["provider"],
        "requested_model": identity["model"],
        "raw_response_reference": str(raw),
    }
    (logs / (fid + ".invocation.json")).write_text(json.dumps(inv))
    accepted = logs / (fid + ".prediction.json")
    if accepted.exists():
        raise ValueError("DUPLICATE_ACCEPTED_IDENTITY")
    if response.get("actual_provider") != identity["provider"] or response.get("actual_model") != identity["model"]:
        raise ValueError("PROVIDER_MODEL_MISMATCH")
    payload = json.loads(response["raw_output"])
    resolved = validate_and_resolve(payload, members)
    transaction = "TX_" + uuid.uuid4().hex
    prediction = {
        **inv,
        **resolved,
        "package_id": json.loads((package / "package_manifest.json").read_text())["package_id"],
        "actual_model": response["actual_model"],
        "transaction_reference": transaction,
    }
    accepted.write_text(json.dumps(prediction))
    return prediction


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_id(prefix: str, *parts: Any) -> str:
    import hashlib

    return prefix + "_" + hashlib.sha256(_canon(parts).encode()).hexdigest()[:24]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _fsync_dir(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, value: Mapping[str, Any], *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and path.exists():
        raise DurableExecutionError("DURABLE_RECORD_EXISTS:" + path.name)
    tmp = path.with_name("." + path.name + ".tmp-" + uuid.uuid4().hex)
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    with tmp.open("w") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if overwrite:
        os.replace(tmp, path)
    else:
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            tmp.unlink(missing_ok=True)
            raise DurableExecutionError("DURABLE_RECORD_EXISTS:" + path.name)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            tmp.unlink(missing_ok=True)
    _fsync_dir(path.parent)


def _package_binding(package_dir: Path) -> dict[str, Any]:
    verify_package_manifest(package_dir)
    verify_whole_package_fingerprint(package_dir)
    manifest = _read_json(package_dir / "package_manifest.json")
    binding = _read_json(package_dir / "binding" / "immutable_deployment_binding.json")
    fingerprints = _read_json(package_dir / "fingerprints" / "implementation_fingerprints.json")
    return {
        "package_id": manifest["package_id"],
        "whole_package_fingerprint": (package_dir / "whole_package_sha256.txt").read_text().strip(),
        "apps_script_version": binding["apps_script_version"],
        "bridge_source_fingerprint": fingerprints["bridge_source_fingerprint"],
        "prediction_runner_fingerprint": fingerprints["prediction_runner_fingerprint"],
        "contract_fingerprint": fingerprints["contract_fingerprint"],
        "executor_fingerprint": fingerprints["executor_fingerprint"],
    }


def _assert_binding(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise DurableExecutionError("PACKAGE_RUN_BINDING_MISMATCH:" + key)


def _ledger(run_dir: Path, name: str) -> Path:
    return run_dir / "ledgers" / name


def _record_path(run_dir: Path, ledger: str, record_id: str) -> Path:
    return _ledger(run_dir, ledger) / (record_id + ".json")


def _run_manifest(run_dir: Path) -> dict[str, Any]:
    return _read_json(run_dir / "run_manifest.json")


def initialize_durable_run(
    *,
    package_dir: Path | str,
    durable_run_root: Path | str,
    run_id: str,
    package_id: str,
    whole_package_fingerprint: str,
    apps_script_version: int,
    bridge_source_fingerprint: str,
    prediction_runner_fingerprint: str,
    contract_fingerprint: str,
    executor_fingerprint: str,
) -> dict[str, Any]:
    if not run_id or Path(run_id).name != run_id:
        raise DurableExecutionError("RUN_ID_INVALID")
    package_path = Path(package_dir)
    root = Path(durable_run_root)
    final_dir = root / run_id
    if final_dir.exists():
        raise DurableExecutionError("DUPLICATE_RUN_ID")

    expected_binding = {
        "package_id": package_id,
        "whole_package_fingerprint": whole_package_fingerprint,
        "apps_script_version": apps_script_version,
        "bridge_source_fingerprint": bridge_source_fingerprint,
        "prediction_runner_fingerprint": prediction_runner_fingerprint,
        "contract_fingerprint": contract_fingerprint,
        "executor_fingerprint": executor_fingerprint,
    }
    actual_binding = _package_binding(package_path)
    _assert_binding(expected_binding, actual_binding)

    root.mkdir(parents=True, exist_ok=True)
    temp_dir = root / f".{run_id}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir()
        for name in LEDGER_DIRS:
            _ledger(temp_dir, name).mkdir(parents=True)
        manifest = {
            "run_id": run_id,
            "package_dir": str(package_path),
            "binding": dict(expected_binding),
            "bridge_function_name": BRIDGE_FUNCTION_NAME,
            "bridge_schema_version": BRIDGE_SCHEMA_VERSION,
            "provider_calls_enabled": True,
            "outcome_enabled": False,
            "evaluation_enabled": False,
            "native_v2_prediction_path_required": False,
            "initial_counters": {
                "invocations": 0,
                "raw_responses": 0,
                "accepted_predictions": 0,
                "failures": 0,
                "active_reservations": 0,
                "unresolved_transactions": 0,
            },
        }
        _atomic_write_json(temp_dir / "run_manifest.json", manifest)
        reconcile_run(temp_dir)
        temp_dir.rename(final_dir)
        return _read_json(final_dir / "run_manifest.json")
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise


def production_bridge_dispatch(payload: Mapping[str, Any], *, script_service=None, script_id: str | None = None) -> Any:
    from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function

    service = script_service
    if service is None:
        service = build_script_service(load_credentials())
    return run_script_function(service, script_id or default_script_id(), BRIDGE_FUNCTION_NAME, [dict(payload)])


def _load_package_state(package_dir: Path) -> dict[str, Any]:
    population = {row["forecast_identity"]: row for row in _rows(package_dir / "snapshot" / "authoritative_forecast_population.jsonl")}
    sessions = {row["session_id"]: row for row in _rows(package_dir / "snapshot" / "authoritative_sessions.jsonl")}
    members_by_session: dict[str, list[dict[str, Any]]] = {}
    for row in _rows(package_dir / "snapshot" / "authoritative_session_members.jsonl"):
        members_by_session.setdefault(row["session_id"], []).append(row)
    pack_references = {row["session_id"]: row for row in _rows(package_dir / "snapshot" / "authoritative_pack_references.jsonl")}
    excluded_sessions = {row["session_id"] for row in _rows(package_dir / "snapshot" / "authoritative_excluded_sessions.jsonl")}
    return {
        "population": population,
        "sessions": sessions,
        "members_by_session": members_by_session,
        "pack_references": pack_references,
        "excluded_sessions": excluded_sessions,
    }


def _verify_run_binding(run_dir: Path, package_dir: Path) -> None:
    _assert_binding(_run_manifest(run_dir)["binding"], _package_binding(package_dir))


def _verify_identity_eligibility(package_state: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    forecast_identity = str(identity.get("forecast_identity") or "")
    frozen = package_state["population"].get(forecast_identity)
    if not frozen:
        raise DurableExecutionError("IDENTITY_NOT_IN_FROZEN_POPULATION")
    session_id = str(frozen.get("session_id") or "")
    if session_id in package_state["excluded_sessions"]:
        raise DurableExecutionError("EXCLUDED_IDENTITY")
    if str(frozen.get("arm") or "") not in {"A", "E"}:
        raise DurableExecutionError("INVALID_PACK_ASSIGNMENT")
    if not str(frozen.get("provider") or "") or not str(frozen.get("model") or ""):
        raise DurableExecutionError("INVALID_PROVIDER_MODEL_ROUTE")
    for key in ("session_id", "arm", "provider", "model"):
        if str(identity.get(key) or "") != str(frozen.get(key) or ""):
            raise DurableExecutionError("IDENTITY_ROUTE_MISMATCH:" + key)
    return frozen


def _accepted_path(run_dir: Path, identity_id: str) -> Path:
    return _record_path(run_dir, "accepted_predictions", identity_id)


def _reservation_path(run_dir: Path, identity_id: str) -> Path:
    return _record_path(run_dir, "reservations", identity_id)


def _reserve_identity(run_dir: Path, identity_id: str, record: Mapping[str, Any]) -> None:
    path = _reservation_path(run_dir, identity_id)
    if path.exists():
        current = _read_json(path)
        if current.get("status") == "active":
            raise DurableExecutionError("IDENTITY_ALREADY_RESERVED")
    _atomic_write_json(path, {**dict(record), "status": "active"})


def _release_reservation(run_dir: Path, identity_id: str, status: str) -> None:
    path = _reservation_path(run_dir, identity_id)
    if not path.exists():
        return
    current = _read_json(path)
    current["status"] = "released"
    current["terminal_status"] = status
    current["released_ts"] = time.time()
    _atomic_write_json(path, current)


def _write_failure(run_dir: Path, run_id: str, identity_id: str, transaction_id: str, classification: str, error: Any, attempt: int) -> dict[str, Any]:
    failure_id = _stable_id("FAIL", run_id, identity_id, transaction_id, classification, attempt)
    failure = {
        "failure_id": failure_id,
        "run_id": run_id,
        "identity_id": identity_id,
        "transaction_id": transaction_id,
        "classification": classification,
        "error": str(error),
        "attempt": attempt,
        "retryable": classification in TRANSIENT_FAILURES and attempt == 0,
    }
    _atomic_write_json(_record_path(run_dir, "failures", failure_id), failure, overwrite=False)
    return failure


def _classify_dispatch_exception(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (ConnectionError, TransientDispatchError)):
        return "network_transport_failure"
    if isinstance(error, TemporaryProviderAvailabilityError):
        return "temporary_provider_availability_failure"
    return "dispatch_failure"


def _classify_parse_or_validation(error: Exception) -> str:
    text = str(error)
    if isinstance(error, json.JSONDecodeError):
        return "malformed_reduced_output"
    if isinstance(error, ReducedForecastError):
        if "TOKEN" in text:
            return "invalid_driver_token"
        return "semantic_validation_failure"
    return "parser_failure"


def _default_parser(response: Mapping[str, Any], members: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> dict[str, Any]:
    payload, parser_metadata = parse_reduced_output_json(response.get("raw_output"))
    if isinstance(context, dict):
        context["parser_metadata"] = parser_metadata
    return validate_and_resolve(payload, members)


def _default_raw_response_persistor(path: Path, record: Mapping[str, Any]) -> None:
    _atomic_write_json(path, record, overwrite=False)


def _default_prediction_persistor(path: Path, record: Mapping[str, Any]) -> None:
    _atomic_write_json(path, record, overwrite=False)


def _build_reduced_prompt(
    identity: Mapping[str, Any],
    package_state: Mapping[str, Any],
    members: Sequence[Mapping[str, Any]],
    response_schema: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    session_id = str(identity["session_id"])
    session = package_state["sessions"].get(session_id)
    pack_reference = package_state["pack_references"].get(session_id)
    if not session or not pack_reference:
        raise DurableExecutionError("FROZEN_PROMPT_CONTEXT_MISSING")
    if identity["arm"] == "E":
        if not identity.get("pack_fingerprint") or identity["pack_fingerprint"] != pack_reference.get("pack_fingerprint"):
            raise DurableExecutionError("FROZEN_PACK_REFERENCE_MISMATCH")
        historical_environment = pack_reference
    else:
        if identity.get("pack_fingerprint"):
            raise DurableExecutionError("PACK_A_UNEXPECTED_ENVIRONMENT_REFERENCE")
        historical_environment = None

    schema = dict(response_schema or reduced_output_response_schema(members))
    token_properties = schema["properties"]
    tokens = list(token_properties["primary_driver_token"]["enum"])
    context = {
        "task": "simplified_authoritative_usdjpy_replay_forecast",
        "decision_support_only": True,
        "forecast_identity": identity["forecast_identity"],
        "pack_arm": identity["arm"],
        "forecast_cutoff": session.get("forecast_cutoff", ""),
        "session": session,
        "session_members": list(members),
        "driver_options": driver_options(members),
        "allowed_primary_driver_tokens": tokens,
        "allowed_secondary_driver_tokens": tokens,
        "dynamic_token_enum_schema": {
            "primary_driver_token": token_properties["primary_driver_token"],
            "secondary_driver_token": token_properties["secondary_driver_token"],
        },
        "historical_environment_pack": historical_environment,
        "outcome_data_supplied": False,
        "evaluation_data_supplied": False,
    }
    return {
        "system": (
            "You are a macroeconomic decision-support forecaster. Use only the frozen information "
            "in the request and do not give trading instructions. Return strict JSON only."
        ),
        "user": _canon(context),
        "instruction": (
            "Return exactly one JSON object with exactly these fields: primary_driver_token, "
            "secondary_driver_token, final_usdjpy_direction, reaction_strength, confidence, "
            "primary_thesis, secondary_thesis, reasoning_steps. primary_driver_token must be one "
            "exact listed primary token copied verbatim. secondary_driver_token must be JSON null "
            "or one exact listed secondary token copied verbatim and different from the primary token. "
            "Do not emit event names, labels, partial tokens, or approximate tokens. "
            "final_usdjpy_direction must be UP, DOWN, FLAT, or NO_CLEAR_DIRECTION. reaction_strength "
            "must be WEAK, MODERATE, or STRONG. confidence must be a number from 0 to 1. "
            "primary_thesis must be non-empty. If secondary_driver_token is null, secondary_thesis "
            "must be empty; otherwise secondary_thesis must be non-empty. reasoning_steps must be "
            "an array of 2 to 4 non-empty strings. Do not add fields, markdown, or commentary."
        ),
        "cache_scaffold": "",
    }


def _bridge_payload(
    run_id: str,
    identity: Mapping[str, Any],
    prompt: Mapping[str, str],
    *,
    hard_timeout_seconds: int = 300,
    response_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "provider": identity["provider"],
        "model": identity["model"],
        "authoritative_run_id": run_id,
        "forecast_identity": identity["forecast_identity"],
        "session_id": identity["session_id"],
        "arm": identity["arm"],
        "request_schema_version": BRIDGE_SCHEMA_VERSION,
        "hard_timeout_seconds": hard_timeout_seconds,
        "prompt": dict(prompt),
    }
    if response_schema is not None:
        payload["response_schema"] = dict(response_schema)
    return payload


def execute_live_identity(
    *,
    run_dir: Path | str,
    package_dir: Path | str,
    identity: Mapping[str, Any],
    dispatch_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    parser_fn: Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]], Mapping[str, Any]], dict[str, Any]] | None = None,
    raw_response_persistor: Callable[[Path, Mapping[str, Any]], None] | None = None,
    prediction_persistor: Callable[[Path, Mapping[str, Any]], None] | None = None,
    max_retries: int = 1,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    package_path = Path(package_dir)
    run_manifest = _run_manifest(run_path)
    run_id = run_manifest["run_id"]
    identity_id = str(identity.get("forecast_identity") or "")
    if not identity_id:
        raise DurableExecutionError("FORECAST_IDENTITY_MISSING")
    if _accepted_path(run_path, identity_id).exists():
        raise DurableExecutionError("IDENTITY_ALREADY_ACCEPTED")

    _verify_run_binding(run_path, package_path)
    package_state = _load_package_state(package_path)
    frozen_identity = _verify_identity_eligibility(package_state, identity)
    members = package_state["members_by_session"].get(frozen_identity["session_id"], [])
    if not members:
        raise DurableExecutionError("IDENTITY_SESSION_MEMBERS_MISSING")

    dispatch = dispatch_fn or production_bridge_dispatch
    parser = parser_fn or _default_parser
    raw_writer = raw_response_persistor or _default_raw_response_persistor
    prediction_writer = prediction_persistor or _default_prediction_persistor
    transaction_id = _stable_id("TX", run_id, identity_id)
    invocation_id = _stable_id("INV", run_id, identity_id)
    response_schema = reduced_output_response_schema(members)
    prompt = _build_reduced_prompt(frozen_identity, package_state, members, response_schema)
    payload = _bridge_payload(
        run_id,
        frozen_identity,
        prompt,
        response_schema=response_schema if frozen_identity["provider"] == "Gemini" else None,
    )

    _reserve_identity(run_path, identity_id, {
        "run_id": run_id,
        "identity_id": identity_id,
        "transaction_id": transaction_id,
    })
    invocation = {
        "invocation_id": invocation_id,
        "run_id": run_id,
        "identity_id": identity_id,
        "transaction_id": transaction_id,
        "provider": frozen_identity["provider"],
        "requested_model": frozen_identity["model"],
        "bridge_function_name": BRIDGE_FUNCTION_NAME,
        "payload": payload,
    }
    _atomic_write_json(_record_path(run_path, "invocations", invocation_id), invocation, overwrite=False)
    transaction_path = _record_path(run_path, "transactions", transaction_id)
    transaction = {
        "transaction_id": transaction_id,
        "run_id": run_id,
        "identity_id": identity_id,
        "status": "open",
        "attempt_count": 0,
        "retry_count": 0,
        "raw_response_id": "",
        "prediction_id": "",
    }
    _atomic_write_json(transaction_path, transaction, overwrite=False)

    try:
        attempt = 0
        while True:
            transaction["attempt_count"] = attempt + 1
            _atomic_write_json(transaction_path, transaction)
            try:
                response = dict(dispatch(payload))
                break
            except Exception as error:
                classification = _classify_dispatch_exception(error)
                _write_failure(run_path, run_id, identity_id, transaction_id, classification, error, attempt)
                if classification in TRANSIENT_FAILURES and attempt < max(0, min(int(max_retries), 1)):
                    transaction["retry_count"] += 1
                    transaction["last_retry_classification"] = classification
                    _atomic_write_json(transaction_path, transaction)
                    attempt += 1
                    continue
                transaction["status"] = "failed"
                transaction["failure_classification"] = classification
                _atomic_write_json(transaction_path, transaction)
                _atomic_write_json(_record_path(run_path, "terminal_identity_states", identity_id), {
                    "run_id": run_id,
                    "identity_id": identity_id,
                    "transaction_id": transaction_id,
                    "status": "failed",
                    "classification": classification,
                })
                _release_reservation(run_path, identity_id, "failed")
                reconcile_run(run_path)
                raise DurableExecutionError(classification) from error

        raw_response_id = _stable_id("RAW", run_id, identity_id, transaction["attempt_count"])
        raw_path = _record_path(run_path, "raw_responses", raw_response_id)
        raw_record = {
            "raw_response_id": raw_response_id,
            "run_id": run_id,
            "identity_id": identity_id,
            "transaction_id": transaction_id,
            "response": response,
        }
        try:
            raw_writer(raw_path, raw_record)
        except Exception as error:
            raise RawPersistenceError(str(error)) from error
        if not raw_path.exists() or _read_json(raw_path).get("raw_response_id") != raw_response_id:
            raise RawPersistenceError("RAW_RESPONSE_NOT_DURABLY_PERSISTED")
        transaction["raw_response_id"] = raw_response_id
        transaction["status"] = "raw_response_persisted"
        _atomic_write_json(transaction_path, transaction)

        if response.get("actual_provider") != frozen_identity["provider"] or response.get("actual_model") != frozen_identity["model"]:
            raise DurableExecutionError("model_substitution")

        try:
            parser_context: dict[str, Any] = {
                "run_dir": run_path,
                "raw_response_path": raw_path,
                "transaction_id": transaction_id,
            }
            resolved = parser(response, members, parser_context)
            transaction["parser_metadata"] = parser_context.get("parser_metadata", {"output_normalization": "custom_parser"})
            _atomic_write_json(transaction_path, transaction)
        except Exception as error:
            classification = _classify_parse_or_validation(error)
            _write_failure(run_path, run_id, identity_id, transaction_id, classification, error, transaction["attempt_count"] - 1)
            transaction["status"] = "failed"
            transaction["failure_classification"] = classification
            _atomic_write_json(transaction_path, transaction)
            _atomic_write_json(_record_path(run_path, "terminal_identity_states", identity_id), {
                "run_id": run_id,
                "identity_id": identity_id,
                "transaction_id": transaction_id,
                "status": "failed",
                "classification": classification,
            })
            _release_reservation(run_path, identity_id, "failed")
            reconcile_run(run_path)
            raise DurableExecutionError(classification) from error

        prediction_id = identity_id
        prediction = {
            "prediction_id": prediction_id,
            "run_id": run_id,
            "identity_id": identity_id,
            "transaction_id": transaction_id,
            "package_id": run_manifest["binding"]["package_id"],
            "provider": frozen_identity["provider"],
            "requested_model": frozen_identity["model"],
            "actual_model": response["actual_model"],
            **resolved,
        }
        try:
            prediction_writer(_accepted_path(run_path, identity_id), prediction)
        except Exception as error:
            _write_failure(run_path, run_id, identity_id, transaction_id, "prediction_persistence_failure", error, transaction["attempt_count"] - 1)
            transaction["status"] = "prediction_persistence_failed"
            transaction["failure_classification"] = "prediction_persistence_failure"
            _atomic_write_json(transaction_path, transaction)
            _release_reservation(run_path, identity_id, "failed")
            reconcile_run(run_path)
            raise PredictionPersistenceError("prediction_persistence_failure") from error

        transaction["status"] = "committed"
        transaction["prediction_id"] = prediction_id
        _atomic_write_json(transaction_path, transaction)
        _atomic_write_json(_record_path(run_path, "terminal_identity_states", identity_id), {
            "run_id": run_id,
            "identity_id": identity_id,
            "transaction_id": transaction_id,
            "status": "success",
        })
        _release_reservation(run_path, identity_id, "success")
        reconcile_run(run_path)
        return prediction
    except RawPersistenceError as error:
        _write_failure(run_path, run_id, identity_id, transaction_id, "raw_response_persistence_failure", error, transaction["attempt_count"] - 1)
        transaction["status"] = "failed"
        transaction["failure_classification"] = "raw_response_persistence_failure"
        _atomic_write_json(transaction_path, transaction)
        _atomic_write_json(_record_path(run_path, "terminal_identity_states", identity_id), {
            "run_id": run_id,
            "identity_id": identity_id,
            "transaction_id": transaction_id,
            "status": "failed",
            "classification": "raw_response_persistence_failure",
        })
        _release_reservation(run_path, identity_id, "failed")
        reconcile_run(run_path)
        raise DurableExecutionError("raw_response_persistence_failure") from error
    except DurableExecutionError as error:
        if str(error) == "model_substitution":
            _write_failure(run_path, run_id, identity_id, transaction_id, "model_substitution", error, transaction["attempt_count"] - 1)
            transaction["status"] = "failed"
            transaction["failure_classification"] = "model_substitution"
            _atomic_write_json(transaction_path, transaction)
            _atomic_write_json(_record_path(run_path, "terminal_identity_states", identity_id), {
                "run_id": run_id,
                "identity_id": identity_id,
                "transaction_id": transaction_id,
                "status": "failed",
                "classification": "model_substitution",
            })
            _release_reservation(run_path, identity_id, "failed")
            reconcile_run(run_path)
        raise


def reconcile_run(run_dir: Path | str) -> dict[str, Any]:
    run_path = Path(run_dir)

    def records(name: str) -> list[dict[str, Any]]:
        path = _ledger(run_path, name)
        if not path.exists():
            return []
        return [_read_json(item) for item in sorted(path.glob("*.json"))]

    reservations = records("reservations")
    transactions = records("transactions")
    summary = {
        "invocations": len(records("invocations")),
        "raw_responses": len(records("raw_responses")),
        "accepted_predictions": len(records("accepted_predictions")),
        "failures": len(records("failures")),
        "active_reservations": sum(row.get("status") == "active" for row in reservations),
        "unresolved_transactions": sum(row.get("status") not in {"committed", "failed"} for row in transactions),
        "committed_transactions": sum(row.get("status") == "committed" for row in transactions),
        "failed_transactions": sum(row.get("status") == "failed" for row in transactions),
        "recoverable_transactions": sum(row.get("status") == "prediction_persistence_failed" for row in transactions),
        "terminal_success": sum(row.get("status") == "success" for row in records("terminal_identity_states")),
        "terminal_failed": sum(row.get("status") == "failed" for row in records("terminal_identity_states")),
    }
    _atomic_write_json(run_path / "reconciliation_summary.json", summary)
    return summary
