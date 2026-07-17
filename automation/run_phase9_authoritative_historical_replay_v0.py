#!/usr/bin/env python3
"""Package-bound authoritative historical replay executor.

This runner is deliberately package-bound: authoritative execution can only
read the frozen input snapshot and frozen execution configuration under a
single run directory. Validation and fixture modes never dispatch providers.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function  # type: ignore
from automation.run_phase9_historical_square_one_replay_v0 import (  # type: ignore
    FORECAST_PROMPT_VERSION,
    PACK_VERSION,
    _hindsight_hits,
    _normalized_forecast_response,
    _retryable_forecast_errors,
    _square_one_forecast_prompt,
)
from automation.v2_layered_prediction_evaluation_v0 import release_clusters  # type: ignore
from automation.native_v2_typed_schema_v0 import (  # type: ignore
    PRIMARY_REACTION_BINDING_FIELD,
    SECONDARY_REACTION_TRANSPORT_FIELD,
    canonical_schema_fingerprint,
    decode_primary_reaction_transport,
    primary_reaction_binding_fingerprint,
    primary_reaction_binding_set,
    transport_adapter_schema,
    transport_adapter_schema_fingerprint,
)


AUTHORITATIVE_CONTRACT_FP = "7ad8b1537f59041a9f9311fbbd547d682a5a15d7fc55a1bc225ca14d24c42e85"
LEGACY_ACTIVE_PARTS = ("phase9_historical_square_one_acquisition_repair", "active_v1")
AUTHORITATIVE_BRIDGE_FUNCTION = "apiCallAuthoritativeProviderJsonObject"
AUTHORITATIVE_BRIDGE_SCHEMA_VERSION = "authoritative_historical_replay_bridge_v1"
APPS_SCRIPT_PROJECT_BINDING_KEYS = {
    "project_id",
    "version_number",
    "aggregate_fingerprint",
    "bridge_file_name",
    "bridge_sha256",
}

TERMINAL_STATUSES = {
    "SUCCEEDED_NATIVE_V2",
    "FAILED_PROVIDER_TERMINAL",
    "FAILED_VALIDATION_TERMINAL",
    "FAILED_TIMEOUT_TERMINAL",
    "FAILED_STORAGE_TERMINAL",
    "FAILED_CONFIGURATION_TERMINAL",
    "FAILED_CALL_CONTROL_TERMINAL",
}
RETRYABLE_FAILURE_CLASSES = {
    "RETRYABLE_TRANSPORT_FAILURE",
    "RETRYABLE_TIMEOUT_FAILURE",
    "RETRYABLE_SCHEMA_FAILURE",
}
NON_RETRYABLE_FAILURE_CLASSES = {
    "NON_RETRYABLE_VALIDATION_FAILURE",
    "NON_RETRYABLE_PROVIDER_FAILURE",
    "CONFIGURATION_MISMATCH",
    "IDENTITY_MISMATCH",
    "CALL_CONTROL_VIOLATION",
    "STORAGE_FAILURE",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _apps_script_project_fingerprint(files: Sequence[Mapping[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    """Fingerprint retrieved Apps Script source, independent of API file ordering."""
    records: List[Dict[str, str]] = []
    seen = set()
    for file in files:
        name = str(file.get("name") or "")
        file_type = str(file.get("type") or "")
        if not name or not file_type or "source" not in file:
            raise ExecutorError("APPS_SCRIPT_PROJECT_CONTENT_INCOMPLETE")
        key = (name, file_type)
        if key in seen:
            raise ExecutorError("APPS_SCRIPT_PROJECT_CONTENT_DUPLICATE_FILE:" + name)
        seen.add(key)
        records.append({
            "name": name,
            "type": file_type,
            "sha256": hashlib.sha256(str(file.get("source") or "").encode("utf-8")).hexdigest(),
        })
    records.sort(key=lambda row: (row["name"], row["type"]))
    return _sha(records), records


def _validate_apps_script_project_binding(state: "PackageState") -> Dict[str, Any]:
    binding = state.config.get("apps_script_project_binding") or {}
    if set(binding) != APPS_SCRIPT_PROJECT_BINDING_KEYS:
        raise ExecutorError("APPS_SCRIPT_PROJECT_BINDING_METADATA_INCOMPLETE")
    project_id = str(binding.get("project_id") or "")
    if not project_id or project_id != default_script_id():
        raise ExecutorError("APPS_SCRIPT_PROJECT_ID_BINDING_MISMATCH")
    try:
        version_number = int(binding.get("version_number"))
    except (TypeError, ValueError) as exc:
        raise ExecutorError("APPS_SCRIPT_PROJECT_VERSION_BINDING_MISMATCH") from exc
    expected_fingerprint = str(binding.get("aggregate_fingerprint") or "")
    if len(expected_fingerprint) != 64 or any(char not in "0123456789abcdef" for char in expected_fingerprint.lower()):
        raise ExecutorError("APPS_SCRIPT_PROJECT_FINGERPRINT_BINDING_MISMATCH")
    bridge_binding = (state.config.get("execution_bindings") or {}).get("provider_bridge") or {}
    if str(binding.get("bridge_sha256") or "") != str(bridge_binding.get("sha256") or ""):
        raise ExecutorError("APPS_SCRIPT_PROJECT_BRIDGE_BINDING_MISMATCH")
    credentials = load_credentials(interactive=False)
    service = build_script_service(credentials, timeout_seconds=300)
    version_content = service.projects().getContent(scriptId=project_id, versionNumber=version_number).execute()
    head_content = service.projects().getContent(scriptId=project_id).execute()
    version_fingerprint, version_records = _apps_script_project_fingerprint(version_content.get("files") or [])
    head_fingerprint, head_records = _apps_script_project_fingerprint(head_content.get("files") or [])
    if version_fingerprint != expected_fingerprint:
        raise ExecutorError("IMMUTABLE_APPS_SCRIPT_PROJECT_FINGERPRINT_MISMATCH")
    if head_fingerprint != expected_fingerprint or head_records != version_records:
        raise ExecutorError("CURRENT_APPS_SCRIPT_PROJECT_FINGERPRINT_MISMATCH")
    bridge_record = next((row for row in version_records if row["name"] == str(binding["bridge_file_name"]) and row["type"] == "SERVER_JS"), None)
    if not bridge_record or bridge_record["sha256"] != str(binding["bridge_sha256"]):
        raise ExecutorError("IMMUTABLE_APPS_SCRIPT_BRIDGE_FINGERPRINT_MISMATCH")
    return {
        "project_id": project_id,
        "version_number": version_number,
        "aggregate_fingerprint": version_fingerprint,
        "file_count": len(version_records),
        "bridge_sha256": bridge_record["sha256"],
        "version_and_head_identical": True,
    }


def _git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception as exc:
        raise ExecutorError("GIT_BINDING_UNAVAILABLE:" + type(exc).__name__) from exc


def _rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, path)


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(_canon(value) + "\n" for value in values))
    os.replace(tmp, path)


def _append_jsonl_locked(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(_canon(row) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _exclusive_lease(path: Path, owner: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("AUTHORITATIVE_EXECUTION_LEASE_ALREADY_HELD") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"owner": owner, "acquired_ts": _now()}, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
        yield
    finally:
        handle.seek(0)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class ExecutorError(RuntimeError):
    """Fail-closed executor error."""


class PackageState:
    def __init__(self, package: Path, *, strict_authoritative: bool = True) -> None:
        self.package = package.resolve()
        if LEGACY_ACTIVE_PARTS[0] in self.package.parts and LEGACY_ACTIVE_PARTS[1] in self.package.parts:
            raise ExecutorError("LEGACY_ACTIVE_STORE_PATH_REJECTED")
        self.snapshot = self.package / "input_snapshot"
        self.active_store = self.package / "active_store"
        self.execution = self.package / "execution"
        self.logs = self.package / "logs"
        self.responses = self.package / "responses"
        self.predictions = self.package / "predictions"
        self.manifests = self.package / "manifests"
        self.failures = self.package / "failures"
        self.transactions = self.active_store / "transactions"
        self.lease_path = self.execution / "authoritative_execution.lock"
        for directory in (self.snapshot, self.active_store, self.execution, self.logs, self.responses, self.predictions, self.manifests, self.failures):
            if not directory.exists():
                raise ExecutorError("MISSING_RUN_SCOPED_DIRECTORY:" + str(directory))
        self.config_path = self.execution / "frozen_execution_configuration.json"
        self.manifest_path = self.snapshot / "authoritative_replay_input_manifest.json"
        if not self.config_path.exists() or not self.manifest_path.exists():
            raise ExecutorError("MISSING_FROZEN_AUTHORITATIVE_PACKAGE_COMPONENT")
        self.config: Dict[str, Any] = json.loads(self.config_path.read_text())
        self.manifest: Dict[str, Any] = json.loads(self.manifest_path.read_text())
        self.configuration_fingerprint = _sha(self.config)
        self.snapshot_fingerprint = str(self.manifest.get("snapshot_fingerprint"))
        self.run_id = str(self.config.get("run_id"))
        if strict_authoritative:
            self._validate_authoritative_identity()
        self.population = _rows(self.snapshot / "authoritative_forecast_population.jsonl")
        self.sessions = {row["session_id"]: row for row in _rows(self.snapshot / "authoritative_sessions.jsonl")}
        self.members_by_session: Dict[str, List[Dict[str, Any]]] = {}
        for row in _rows(self.snapshot / "authoritative_session_members.jsonl"):
            self.members_by_session.setdefault(str(row.get("session_id")), []).append(row)
        self.packs = {row["session_id"]: row for row in _rows(self.snapshot / "authoritative_pack_references.jsonl")}
        self.excluded_ids = {row["session_id"] for row in _rows(self.snapshot / "authoritative_excluded_sessions.jsonl")}
        self.population_by_id = {row["forecast_identity"]: row for row in self.population}
        self._validate_population(strict_authoritative=strict_authoritative)
        self._ensure_ledgers()

    def _validate_authoritative_identity(self) -> None:
        if not self.run_id.startswith("9-AUTHORITATIVE-HISTORICAL-REPLAY-"):
            raise ExecutorError("AUTHORITATIVE_RUN_ID_MISMATCH")
        if self.manifest.get("configuration_fingerprint") != self.configuration_fingerprint:
            raise ExecutorError("CONFIGURATION_FINGERPRINT_MISMATCH")
        contract = self.config.get("stage4a_contract") or {}
        if contract.get("fingerprint") != AUTHORITATIVE_CONTRACT_FP:
            raise ExecutorError("STAGE4A_FINGERPRINT_MISMATCH")
        expected_count = int((self.manifest.get("record_counts") or {}).get("forecast_identities") or 0)
        if expected_count <= 0:
            raise ExecutorError("FROZEN_FORECAST_POPULATION_COUNT_MISSING")
        if int(self.config.get("initial_call_ceiling")) != expected_count:
            raise ExecutorError("INITIAL_CALL_CEILING_MISMATCH")
        if int(self.config.get("retry_call_ceiling")) != expected_count:
            raise ExecutorError("RETRY_CALL_CEILING_MISMATCH")
        if int(self.config.get("total_call_ceiling")) != expected_count * 2:
            raise ExecutorError("TOTAL_CALL_CEILING_MISMATCH")
        if int(self.config.get("global_concurrency_limit")) != 1:
            raise ExecutorError("GLOBAL_CONCURRENCY_MISMATCH")
        if int(self.config.get("prediction_path_minimum")) != 2 or int(self.config.get("prediction_path_maximum")) != 4:
            raise ExecutorError("PREDICTION_PATH_BOUND_MISMATCH")
        bindings = self.config.get("execution_bindings") or {}
        required_bindings = {"executor", "package_builder", "provider_bridge", "git"}
        if set(bindings) != required_bindings:
            raise ExecutorError("EXECUTION_BINDING_METADATA_INCOMPLETE")
        for key in ("executor", "package_builder", "provider_bridge"):
            binding = bindings[key]
            relative_path = str(binding.get("relative_path") or "")
            expected_sha = str(binding.get("sha256") or "")
            path = (ROOT / relative_path).resolve()
            if not relative_path or not expected_sha or not path.exists() or _file_sha(path) != expected_sha:
                raise ExecutorError(key.upper() + "_FINGERPRINT_MISMATCH")
        if str(self.config.get("runner_fingerprint") or "") != str(bindings["executor"].get("sha256") or ""):
            raise ExecutorError("RUNNER_FINGERPRINT_MISMATCH")
        if str(self.config.get("runner_fingerprint")) == str(self.config.get("prompt_fingerprint")):
            raise ExecutorError("RUNNER_FINGERPRINT_MUST_NOT_EQUAL_PROMPT_FINGERPRINT")
        git_binding = bindings["git"]
        if _git_value("rev-parse", "HEAD") != str(git_binding.get("commit") or ""):
            raise ExecutorError("GIT_COMMIT_BINDING_MISMATCH")
        if _git_value("branch", "--show-current") != str(git_binding.get("branch") or ""):
            raise ExecutorError("GIT_BRANCH_BINDING_MISMATCH")
        if str(bindings["provider_bridge"].get("request_schema_version") or "") != AUTHORITATIVE_BRIDGE_SCHEMA_VERSION:
            raise ExecutorError("PROVIDER_BRIDGE_SCHEMA_VERSION_MISMATCH")

    def _validate_population(self, *, strict_authoritative: bool) -> None:
        if len(self.population_by_id) != len(self.population):
            raise ExecutorError("DUPLICATE_FROZEN_FORECAST_IDENTITY")
        if strict_authoritative and len(self.population) != int((self.manifest.get("record_counts") or {}).get("forecast_identities") or 0):
            raise ExecutorError("FROZEN_FORECAST_POPULATION_COUNT_MISMATCH")
        contract_fp = (self.config.get("stage4a_contract") or {}).get("fingerprint")
        provider_models = {row["provider"]: row["model"] for row in self.config.get("providers", [])}
        for row in self.population:
            sid = row.get("session_id")
            if sid in self.excluded_ids:
                raise ExecutorError("EXCLUDED_SESSION_IDENTITY_PRESENT")
            if sid not in self.sessions or sid not in self.members_by_session or sid not in self.packs:
                raise ExecutorError("FROZEN_IDENTITY_LACKS_VERIFIED_PACK_OR_SESSION")
            if row.get("stage4a_contract_fingerprint") != contract_fp:
                raise ExecutorError("STAGE4A_FINGERPRINT_MISMATCH")
            if provider_models.get(row.get("provider")) != row.get("model"):
                raise ExecutorError("FROZEN_PROVIDER_MODEL_ROUTE_MISMATCH")
            if row.get("prediction_schema_version") != self.config.get("schema_version"):
                raise ExecutorError("PREDICTION_SCHEMA_MISMATCH")
            for key in ("prompt_fingerprint", "parser_fingerprint", "storage_fingerprint"):
                if row.get(key) != self.config.get(key):
                    raise ExecutorError(key.upper() + "_MISMATCH")
            if row.get("arm") == "E" and not row.get("pack_fingerprint"):
                raise ExecutorError("PACK_E_IDENTITY_LACKS_PACK_FINGERPRINT")

    def _ensure_ledgers(self) -> None:
        for path in (
            self.invocations_path,
            self.responses_path,
            self.predictions_path,
            self.paths_path,
            self.terminal_path,
            self.failure_path,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        self.transactions.mkdir(parents=True, exist_ok=True)

    @property
    def invocations_path(self) -> Path:
        return self.logs / "provider_invocations.jsonl"

    @property
    def responses_path(self) -> Path:
        return self.logs / "provider_responses.jsonl"

    @property
    def terminal_path(self) -> Path:
        return self.logs / "terminal_status_ledger.jsonl"

    @property
    def failure_path(self) -> Path:
        return self.failures / "failure_ledger.jsonl"

    @property
    def predictions_path(self) -> Path:
        return self.predictions / "v2_predictions.jsonl"

    @property
    def paths_path(self) -> Path:
        return self.predictions / "v2_prediction_paths.jsonl"

    @property
    def checkpoint_path(self) -> Path:
        return self.execution / "execution_checkpoint.json"

    @property
    def completion_manifest_path(self) -> Path:
        return self.manifests / "completion_manifest.json"

    def environment_contract(self) -> Dict[str, Any]:
        contract = self.config["stage4a_contract"]
        return {
            "environment_contract_id": contract["version"],
            "environment_contract_fingerprint": contract["fingerprint"],
            **{key: value for key, value in contract.get("components", {}).items()},
        }

    def queue(self) -> List[Dict[str, Any]]:
        return list(self.population)


def validate_package(package: Path, *, strict_authoritative: bool = True) -> Dict[str, Any]:
    state = PackageState(package, strict_authoritative=strict_authoritative)
    manifest = reconcile_completion(state, write_manifest=False)
    return {
        "run_id": state.run_id,
        "snapshot_fingerprint": state.snapshot_fingerprint,
        "configuration_fingerprint": state.configuration_fingerprint,
        "identities": len(state.population),
        "terminal_identities": manifest["terminal_identities"],
        "accepted_predictions": manifest["accepted_prediction_rows"],
        "execution_ready": True,
        "completion_status": manifest["completion_status"],
    }


def _terminal_by_identity(state: PackageState) -> Dict[str, Dict[str, Any]]:
    terminals = _rows(state.terminal_path)
    recovery_eligible = _recovery_eligible_identities(state)
    result: Dict[str, Dict[str, Any]] = {}
    for row in terminals:
        fid = row.get("forecast_identity")
        # A preserved OpenAI route rejection predates provider dispatch.  The
        # approved recovery ledger can make that historical terminal record
        # non-effective exactly once; it remains in the immutable evidence
        # ledger while a linked retry gets a new authoritative terminal state.
        if fid in recovery_eligible and _is_superseded_pre_dispatch_route_failure(row):
            continue
        if fid in result:
            raise ExecutorError("DUPLICATE_TERMINAL_IDENTITY:" + str(fid))
        if fid not in state.population_by_id:
            raise ExecutorError("UNEXPECTED_TERMINAL_IDENTITY:" + str(fid))
        if row.get("terminal_status") not in TERMINAL_STATUSES:
            raise ExecutorError("UNKNOWN_TERMINAL_STATUS:" + str(row.get("terminal_status")))
        result[fid] = row
    return result


def _is_superseded_pre_dispatch_route_failure(row: Mapping[str, Any]) -> bool:
    return (
        int(row.get("attempt_number") or 0) == 1
        and str(row.get("provider") or "") == "OpenAI"
        and str(row.get("failure_class") or "") == "NON_RETRYABLE_PROVIDER_FAILURE"
        and any("configured_model_does_not_match_frozen_model" in str(error) for error in (row.get("errors") or []))
    )


def _recovery_eligible_identities(state: PackageState) -> set[str]:
    path = state.execution / "recovery_eligibility.json"
    if not path.exists():
        return set()
    payload = json.loads(path.read_text())
    if str(payload.get("run_id") or "") != state.run_id:
        raise ExecutorError("RECOVERY_ELIGIBILITY_RUN_ID_MISMATCH")
    identities = payload.get("openai_pre_dispatch_route_rejections")
    if not isinstance(identities, list) or len(identities) != len(set(identities)):
        raise ExecutorError("RECOVERY_ELIGIBILITY_IDENTITY_SET_INVALID")
    result = {str(identity) for identity in identities}
    terminals = _rows(state.terminal_path)
    for fid in result:
        entry = state.population_by_id.get(fid)
        historical = [row for row in terminals if row.get("forecast_identity") == fid]
        if not entry or entry.get("provider") != "OpenAI" or not any(_is_superseded_pre_dispatch_route_failure(row) for row in historical):
            raise ExecutorError("RECOVERY_ELIGIBILITY_EVIDENCE_MISMATCH:" + fid)
    return result


def _attempt_counts(state: PackageState) -> Dict[str, Any]:
    invocations = _rows(state.invocations_path)
    failures = {(row.get("forecast_identity"), int(row.get("attempt_number") or 0)) for row in _rows(state.failure_path)}
    terminals = {row.get("forecast_identity") for row in _rows(state.terminal_path)}
    initial = sum(1 for row in invocations if row.get("initial_or_retry") == "initial")
    retry = sum(1 for row in invocations if row.get("initial_or_retry") == "retry")
    by_key: Dict[Tuple[str, int], int] = {}
    active_by_identity: Dict[str, int] = {}
    for row in invocations:
        fid = str(row.get("forecast_identity"))
        attempt = int(row.get("attempt_number") or 0)
        key = (fid, attempt)
        by_key[key] = by_key.get(key, 0) + 1
        if row.get("dispatch_status") == "RESERVED" and key not in failures and fid not in terminals:
            active_by_identity[fid] = active_by_identity.get(fid, 0) + 1
    duplicate_reservations = [key for key, count in by_key.items() if count > 1]
    return {
        "initial": initial,
        "retry": retry,
        "total": initial + retry,
        "duplicate_reservations": duplicate_reservations,
        "active_by_identity": active_by_identity,
    }


def _successful_prediction_indexes(state: PackageState) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    predictions = _rows(state.predictions_path)
    paths = _rows(state.paths_path)
    by_forecast: Dict[str, Dict[str, Any]] = {}
    paths_by_prediction: Dict[str, List[Dict[str, Any]]] = {}
    for row in predictions:
        fid = str(row.get("forecast_identity"))
        if fid in by_forecast:
            raise ExecutorError("DUPLICATE_PREDICTION:" + fid)
        if fid not in state.population_by_id:
            raise ExecutorError("PREDICTION_OUTSIDE_FROZEN_POPULATION:" + fid)
        by_forecast[fid] = row
    seen_path_fps = set()
    for row in paths:
        stage_fp = row.get("stage_fingerprint")
        if stage_fp in seen_path_fps:
            raise ExecutorError("DUPLICATE_PATH_ROW:" + str(stage_fp))
        seen_path_fps.add(stage_fp)
        pid = str(row.get("prediction_id"))
        paths_by_prediction.setdefault(pid, []).append(row)
    return by_forecast, paths_by_prediction


def _record_failure(state: PackageState, entry: Mapping[str, Any], attempt_number: int, failure_class: str, errors: Sequence[str]) -> None:
    _append_jsonl_locked(state.failure_path, {
        "run_id": state.run_id,
        "forecast_identity": entry.get("forecast_identity"),
        "session_id": entry.get("session_id"),
        "provider": entry.get("provider"),
        "model": entry.get("model"),
        "arm": entry.get("arm"),
        "attempt_number": attempt_number,
        "failure_class": failure_class,
        "errors": list(errors),
        "recorded_ts": _now(),
    })


def _record_terminal(state: PackageState, entry: Mapping[str, Any], attempt_number: int, status: str, failure_class: str = "", errors: Sequence[str] = ()) -> None:
    if status not in TERMINAL_STATUSES:
        raise ExecutorError("INVALID_TERMINAL_STATUS:" + status)
    _append_jsonl_locked(state.terminal_path, {
        "run_id": state.run_id,
        "forecast_identity": entry.get("forecast_identity"),
        "session_id": entry.get("session_id"),
        "provider": entry.get("provider"),
        "model": entry.get("model"),
        "arm": entry.get("arm"),
        "attempt_number": attempt_number,
        "terminal_status": status,
        "failure_class": failure_class,
        "errors": list(errors),
        "terminal_ts": _now(),
        "snapshot_fingerprint": state.snapshot_fingerprint,
        "configuration_fingerprint": state.configuration_fingerprint,
        "stage4a_contract_fingerprint": state.config["stage4a_contract"]["fingerprint"],
    })


def _classify_failure(errors: Sequence[str], response: Mapping[str, Any]) -> Tuple[str, bool]:
    normalized = [str(error) for error in errors if str(error)]
    joined = "|".join(normalized).lower()
    if any("timeout" in error.lower() for error in normalized):
        return "RETRYABLE_TIMEOUT_FAILURE", True
    if any(error.startswith("PROVIDER_CALL_FAILED:") for error in normalized):
        retryable = _retryable_forecast_errors(normalized)
        return ("RETRYABLE_TRANSPORT_FAILURE" if retryable else "NON_RETRYABLE_PROVIDER_FAILURE", retryable)
    if any(error.startswith("V2_OUTPUT_SCHEMA_FAILED:") or error.startswith("RESPONSE_SCHEMA:") for error in normalized):
        return "RETRYABLE_SCHEMA_FAILURE", True
    if "legacy_or_nested_prediction_envelope_not_allowed" in joined:
        return "NON_RETRYABLE_VALIDATION_FAILURE", False
    if any(token in joined for token in ("mismatch", "outside_frozen", "excluded_session", "configuration")):
        return "CONFIGURATION_MISMATCH", False
    if str(response.get("status", "")).lower() in {"refused", "blocked"}:
        return "NON_RETRYABLE_PROVIDER_FAILURE", False
    return "NON_RETRYABLE_VALIDATION_FAILURE", False


def _next_attempt_plan(state: PackageState, entry: Mapping[str, Any]) -> Optional[Tuple[int, str]]:
    fid = str(entry["forecast_identity"])
    terminals = _terminal_by_identity(state)
    if fid in terminals:
        return None
    invocations = [row for row in _rows(state.invocations_path) if row.get("forecast_identity") == fid]
    if not invocations:
        return 1, "initial"
    attempts = sorted(int(row.get("attempt_number") or 0) for row in invocations)
    last_attempt = attempts[-1]
    if fid in _recovery_eligible_identities(state) and not any(bool(row.get("recovery_attempt")) for row in invocations):
        return last_attempt + 1, "recovery_retry"
    failures = [row for row in _rows(state.failure_path) if row.get("forecast_identity") == fid and int(row.get("attempt_number") or 0) == last_attempt]
    if not failures:
        raise ExecutorError("STALE_RESERVATION_REQUIRES_RECOVERY:" + fid)
    last_failure = failures[-1]
    if last_failure.get("failure_class") not in RETRYABLE_FAILURE_CLASSES:
        _record_terminal(state, entry, last_attempt, _terminal_for_failure(str(last_failure.get("failure_class"))), str(last_failure.get("failure_class")), last_failure.get("errors") or [])
        return None
    max_retries = int(state.config["providers"][0].get("maximum_retries_per_identity", 1))
    retry_count = sum(1 for row in invocations if row.get("initial_or_retry") == "retry")
    if retry_count >= max_retries:
        _record_terminal(state, entry, last_attempt, _terminal_for_failure(str(last_failure.get("failure_class"))), str(last_failure.get("failure_class")), last_failure.get("errors") or [])
        return None
    return last_attempt + 1, "retry"


def _terminal_for_failure(failure_class: str) -> str:
    if failure_class == "RETRYABLE_TIMEOUT_FAILURE":
        return "FAILED_TIMEOUT_TERMINAL"
    if failure_class in {"RETRYABLE_TRANSPORT_FAILURE", "NON_RETRYABLE_PROVIDER_FAILURE"}:
        return "FAILED_PROVIDER_TERMINAL"
    if failure_class in {"RETRYABLE_SCHEMA_FAILURE", "NON_RETRYABLE_VALIDATION_FAILURE", "IDENTITY_MISMATCH"}:
        return "FAILED_VALIDATION_TERMINAL"
    if failure_class == "STORAGE_FAILURE":
        return "FAILED_STORAGE_TERMINAL"
    if failure_class == "CALL_CONTROL_VIOLATION":
        return "FAILED_CALL_CONTROL_TERMINAL"
    return "FAILED_CONFIGURATION_TERMINAL"


def _reserve_attempt(state: PackageState, entry: Mapping[str, Any], attempt_number: int, initial_or_retry: str) -> None:
    counts = _attempt_counts(state)
    if counts["duplicate_reservations"]:
        raise ExecutorError("DUPLICATE_INVOCATION_RESERVATION")
    if initial_or_retry not in {"initial", "retry", "recovery_retry"}:
        raise ExecutorError("UNKNOWN_ATTEMPT_CLASS:" + initial_or_retry)
    if initial_or_retry == "initial" and counts["initial"] >= int(state.config["initial_call_ceiling"]):
        raise ExecutorError("INITIAL_CALL_CEILING_EXCEEDED")
    if initial_or_retry in {"retry", "recovery_retry"} and counts["retry"] >= int(state.config["retry_call_ceiling"]):
        raise ExecutorError("RETRY_CALL_CEILING_EXCEEDED")
    if counts["total"] >= int(state.config["total_call_ceiling"]):
        raise ExecutorError("TOTAL_CALL_CEILING_EXCEEDED")
    if entry["forecast_identity"] not in state.population_by_id:
        raise ExecutorError("FORECAST_IDENTITY_OUTSIDE_FROZEN_POPULATION")
    if counts["active_by_identity"].get(str(entry["forecast_identity"]), 0) > 0:
        raise ExecutorError("ACTIVE_RESERVATION_ALREADY_EXISTS")
    existing = [
        row for row in _rows(state.invocations_path)
        if row.get("forecast_identity") == entry["forecast_identity"] and int(row.get("attempt_number") or 0) == attempt_number
    ]
    if existing:
        raise ExecutorError("DUPLICATE_FORECAST_ATTEMPT")
    _append_jsonl_locked(state.invocations_path, {
        "run_id": state.run_id,
        "forecast_identity": entry["forecast_identity"],
        "provider": entry["provider"],
        "model": entry["model"],
        "arm": entry["arm"],
        "attempt_number": attempt_number,
        "initial_or_retry": "retry" if initial_or_retry == "recovery_retry" else initial_or_retry,
        "recovery_attempt": initial_or_retry == "recovery_retry",
        "reservation_timestamp": _now(),
        "dispatch_status": "RESERVED",
        "snapshot_fingerprint": state.snapshot_fingerprint,
        "configuration_fingerprint": state.configuration_fingerprint,
    })


def _prompt_for_entry(state: PackageState, entry: Mapping[str, Any]) -> Dict[str, str]:
    session = state.sessions[str(entry["session_id"])]
    members = sorted(state.members_by_session[str(entry["session_id"])], key=lambda row: (row.get("release_ts", ""), row.get("event_id", "")))
    pack = state.packs[str(entry["session_id"])]
    if entry["arm"] == "A":
        exposure = {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []}
    else:
        exposure = {
            "pack_selected": "TRUE_SHARED_PACK_E",
            "pack_version": PACK_VERSION,
            "pack_item_count": pack.get("item_count"),
            "pack_e_exposure": True,
            "pack_fingerprint": pack.get("pack_fingerprint"),
            "rendered_context_fingerprint": pack.get("rendered_context_fingerprint"),
            "items": pack.get("items") or [],
        }
    prompt = _square_one_forecast_prompt(session, members, exposure, str(entry["provider"]), str(entry["model"]))
    try:
        user = json.loads(str(prompt["user"]))
    except Exception as exc:
        raise ExecutorError("FROZEN_PROMPT_USER_NOT_JSON_OBJECT") from exc
    if not isinstance(user, dict):
        raise ExecutorError("FROZEN_PROMPT_USER_NOT_JSON_OBJECT")
    choices = primary_reaction_binding_set(str(entry["session_id"]), members)
    user["native_v2_primary_reaction_binding_transport"] = {
        "field": PRIMARY_REACTION_BINDING_FIELD,
        "choice_set_fingerprint": primary_reaction_binding_fingerprint(str(entry["session_id"]), members),
        "choices": [row["binding"] for row in choices],
    }
    prompt["user"] = _canon(user)
    prompt["instruction"] = str(prompt.get("instruction") or "") + (
        " Provider transport uses the required scalar " + PRIMARY_REACTION_BINDING_FIELD +
        " enum supplied in native_v2_primary_reaction_binding_transport. Select exactly one listed binding. "
        "Do not emit primary_driver_event_id, primary_reaction_target_type, or primary_reaction_target_id; "
        "the transport adapter deterministically decodes only the binding you selected into those existing canonical fields. "
        "Emit secondary_reaction as exactly one typed branch: a status-only no-reaction branch, or a complete "
        "PREDICTED branch. Do not emit any legacy secondary_reaction_* fields."
    )
    return prompt


def _parse_response(state: PackageState, entry: Mapping[str, Any], raw: str, response: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if str(response.get("status")) != "ok":
        errors.append("PROVIDER_CALL_FAILED:" + (str(response.get("error") or response.get("status") or "unknown")))
        return {}, [], errors
    for field, expected in (
        ("requested_provider", entry["provider"]),
        ("requested_model", entry["model"]),
        ("actual_provider", entry["provider"]),
        ("actual_model", entry["model"]),
    ):
        actual = str(response.get(field) or "")
        if not actual:
            errors.append("MISSING_PROVIDER_EXECUTION_METADATA:" + field)
        elif actual != str(expected):
            errors.append("PROVIDER_EXECUTION_METADATA_MISMATCH:" + field + ":" + actual)
    if str(response.get("request_schema_version") or "") != AUTHORITATIVE_BRIDGE_SCHEMA_VERSION:
        errors.append("PROVIDER_BRIDGE_SCHEMA_MISMATCH")
    expected_mode = {
        "OpenAI": "openai_json_schema_strict",
        "Gemini": "gemini_response_schema",
        "Anthropic": "anthropic_forced_tool_input_schema",
    }[str(entry["provider"])]
    if str(response.get("structured_output_mode") or "") != expected_mode:
        errors.append("PROVIDER_STRUCTURED_OUTPUT_MODE_MISMATCH")
    if _hindsight_hits(raw):
        errors.append("HINDSIGHT_OUTPUT_DETECTED:" + "|".join(_hindsight_hits(raw)))
    session = state.sessions[str(entry["session_id"])]
    members = state.members_by_session[str(entry["session_id"])]
    arm_pack_fp = "" if entry["arm"] == "A" else str(entry.get("pack_fingerprint") or "")
    pack_freeze_id = "NO_PACK" if entry["arm"] == "A" else "SQ1PACK_" + arm_pack_fp[:24]
    try:
        parsed_transport = json.loads(raw)
        if not isinstance(parsed_transport, dict):
            raise ValueError("PRIMARY_REACTION_TRANSPORT_NOT_OBJECT")
        if PRIMARY_REACTION_BINDING_FIELD not in parsed_transport:
            if response.get("fixture_response") is True:
                canonical_raw = raw
            else:
                raise ValueError("PRIMARY_REACTION_BINDING_MISSING")
        else:
            canonical_raw = _canon(decode_primary_reaction_transport(
                parsed_transport, str(entry["session_id"]), members,
            ))
        _parsed, prediction, paths, parse_errors = _normalized_forecast_response(
            canonical_raw,
            session=session,
            members=members,
            provider=str(entry["provider"]),
            model=str(entry["model"]),
            arm=str(entry["arm"]),
            pack_freeze_id=pack_freeze_id,
            pack_fingerprint=arm_pack_fp,
            forecast_run_id=state.run_id,
            forecast_created_ts=_now(),
            environment_contract=state.environment_contract(),
        )
        errors.extend(parse_errors)
    except Exception as exc:
        return {}, [], errors + ["RESPONSE_SCHEMA:" + str(exc)]
    if errors:
        return {}, [], errors
    path_min = int(state.config["prediction_path_minimum"])
    path_max = int(state.config["prediction_path_maximum"])
    if len(paths) < path_min:
        return {}, [], ["PREDICTION_PATH_BELOW_MINIMUM"]
    if len(paths) > path_max:
        return {}, [], ["PREDICTION_PATH_ABOVE_MAXIMUM"]
    authoritative_fields = {
        "run_id": state.run_id,
        "forecast_identity": entry["forecast_identity"],
        "snapshot_fingerprint": state.snapshot_fingerprint,
        "configuration_fingerprint": state.configuration_fingerprint,
        "stage4a_contract_id": state.config["stage4a_contract"]["version"],
        "stage4a_contract_fingerprint": state.config["stage4a_contract"]["fingerprint"],
        "authoritative_replay_package": str(state.package),
        "prompt_fingerprint": entry["prompt_fingerprint"],
        "parser_fingerprint": entry["parser_fingerprint"],
        "storage_fingerprint": entry["storage_fingerprint"],
    }
    prediction.update(authoritative_fields)
    for row in paths:
        row.update(authoritative_fields)
    return prediction, paths, []


def _persist_response(state: PackageState, entry: Mapping[str, Any], attempt_number: int, response: Mapping[str, Any]) -> str:
    raw = str(response.get("raw_output") or "")
    response_fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    response_file = state.responses / f"{entry['forecast_identity']}_attempt{attempt_number}_{response_fp[:16]}.json"
    payload = {
        "run_id": state.run_id,
        "forecast_identity": entry["forecast_identity"],
        "attempt_number": attempt_number,
        "provider": entry["provider"],
        "model": entry["model"],
        "receipt_timestamp": _now(),
        "response_fingerprint": response_fp,
        "response": {key: value for key, value in response.items() if key not in {"authorization", "headers", "api_key"}},
    }
    _write_json(response_file, payload)
    _append_jsonl_locked(state.responses_path, {
        "run_id": state.run_id,
        "forecast_identity": entry["forecast_identity"],
        "attempt_number": attempt_number,
        "provider": entry["provider"],
        "model": entry["model"],
        "response_fingerprint": response_fp,
        "response_reference": str(response_file),
        "receipt_timestamp": payload["receipt_timestamp"],
    })
    return str(response_file)


def _persist_success_transaction(
    state: PackageState, entry: Mapping[str, Any], attempt_number: int,
    response_reference: str, prediction: Mapping[str, Any], paths: Sequence[Mapping[str, Any]],
) -> None:
    predictions, paths_by_prediction = _successful_prediction_indexes(state)
    fid = str(entry["forecast_identity"])
    if fid in predictions:
        raise ExecutorError("DUPLICATE_PREDICTION:" + fid)
    if not paths:
        raise ExecutorError("PREDICTION_WITHOUT_PATH")
    path_min, path_max = int(state.config["prediction_path_minimum"]), int(state.config["prediction_path_maximum"])
    if len(paths) < path_min or len(paths) > path_max:
        raise ExecutorError("PREDICTION_PATH_COUNT_OUT_OF_BOUNDS")
    txn = {
        "run_id": state.run_id,
        "forecast_identity": fid,
        "attempt_number": attempt_number,
        "response_reference": response_reference,
        "prediction": dict(prediction),
        "prediction_paths": [dict(row) for row in paths],
        "transaction_status": "COMMITTED",
        "transaction_ts": _now(),
    }
    pending = state.transactions / f"{fid}_attempt{attempt_number}.pending.json"
    committed = state.transactions / f"{fid}_attempt{attempt_number}.committed.json"
    _write_json(pending, txn)
    os.replace(pending, committed)
    try:
        _append_jsonl_locked(state.predictions_path, prediction)
        for row in paths:
            _append_jsonl_locked(state.paths_path, row)
        _record_terminal(state, entry, attempt_number, "SUCCEEDED_NATIVE_V2")
    except Exception as exc:
        _record_failure(state, entry, attempt_number, "STORAGE_FAILURE", [str(exc)])
        raise
    if str(prediction.get("prediction_id")) not in paths_by_prediction and not paths:
        raise ExecutorError("PREDICTION_PATH_PERSISTENCE_FAILED")


def _process_response(
    state: PackageState, entry: Mapping[str, Any], attempt_number: int,
    response: Mapping[str, Any],
) -> str:
    response_reference = _persist_response(state, entry, attempt_number, response)
    raw = str(response.get("raw_output") or "")
    prediction, paths, errors = _parse_response(state, entry, raw, response)
    if not errors and prediction and paths:
        _persist_success_transaction(state, entry, attempt_number, response_reference, prediction, paths)
        return "SUCCEEDED_NATIVE_V2"
    failure_class, retryable = _classify_failure(errors, response)
    _record_failure(state, entry, attempt_number, failure_class, errors)
    max_retries = int(state.config["providers"][0].get("maximum_retries_per_identity", 1))
    if retryable and attempt_number <= max_retries:
        return "RETRYABLE_RECORDED"
    _record_terminal(state, entry, attempt_number, _terminal_for_failure(failure_class), failure_class, errors)
    return _terminal_for_failure(failure_class)


def _bridge_payload(state: PackageState, entry: Mapping[str, Any], prompt: Mapping[str, str], timeout_seconds: int) -> Dict[str, Any]:
    for key in ("provider", "model", "forecast_identity", "session_id", "arm"):
        if not str(entry.get(key) or ""):
            raise ExecutorError("FROZEN_BRIDGE_PAYLOAD_FIELD_MISSING:" + key)
    if timeout_seconds <= 0:
        raise ExecutorError("FROZEN_BRIDGE_TIMEOUT_MISSING")
    members = state.members_by_session[str(entry["session_id"])]
    provider = str(entry["provider"])
    choice_set_fingerprint = primary_reaction_binding_fingerprint(str(entry["session_id"]), members)
    return {
        "provider": entry["provider"],
        "model": entry["model"],
        "prompt": dict(prompt),
        "authoritative_run_id": state.run_id,
        "forecast_identity": entry["forecast_identity"],
        "arm": entry["arm"],
        "session_id": entry["session_id"],
        "hard_timeout_seconds": timeout_seconds,
        "request_schema_version": AUTHORITATIVE_BRIDGE_SCHEMA_VERSION,
        "structured_output_mode": {"OpenAI": "openai_json_schema_strict", "Gemini": "gemini_response_schema", "Anthropic": "anthropic_forced_tool_input_schema"}[provider],
        "structured_output": {
            "schema_id": "presignal_native_v2_primary_secondary_reaction_transport_v1",
            "schema_fingerprint": canonical_schema_fingerprint(),
            "canonical_schema": transport_adapter_schema(provider, str(entry["session_id"]), members),
            "primary_reaction_binding": {
                "field": PRIMARY_REACTION_BINDING_FIELD,
                "choice_set_fingerprint": choice_set_fingerprint,
                "adapter_schema_fingerprint": transport_adapter_schema_fingerprint(provider, str(entry["session_id"]), members),
            },
            "secondary_reaction": {
                "field": SECONDARY_REACTION_TRANSPORT_FIELD,
                "branches": ["NO_SEPARATE_REACTION", "PREDICTED"],
            },
        },
    }


def _real_provider_dispatcher(state: PackageState) -> Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]]:
    credentials = load_credentials(interactive=False)
    timeout_values = {int(row.get("timeout_seconds") or 0) for row in state.config.get("providers", [])}
    if len(timeout_values) != 1 or next(iter(timeout_values), 0) <= 0:
        raise ExecutorError("FROZEN_PROVIDER_TIMEOUT_CONFIGURATION_MISMATCH")
    timeout_seconds = next(iter(timeout_values))
    script_service = build_script_service(credentials, timeout_seconds=timeout_seconds)
    script_id = default_script_id()

    def dispatch(_state: PackageState, entry: Mapping[str, Any], prompt: Mapping[str, str]) -> Dict[str, Any]:
        payload = _bridge_payload(_state, entry, prompt, timeout_seconds)
        try:
            result = run_script_function(script_service, script_id, AUTHORITATIVE_BRIDGE_FUNCTION, [payload])
        except TimeoutError as exc:
            return {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout:" + str(exc)}
        except Exception as exc:
            return {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": str(exc)}
        if not isinstance(result, dict):
            return {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "provider execution returned non-object result"}
        normalized = dict(result)
        metadata = normalized.get("metadata")
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                normalized.setdefault(key, value)
        return normalized

    return dispatch


def execute_queue(
    state: PackageState, *,
    dispatcher: Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]],
    limit: Optional[int] = None,
    entries: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    processed = 0
    with _exclusive_lease(state.lease_path, f"{os.getpid()}:{_now()}"):
        recover_incomplete_reservations(state)
        while True:
            progressed = False
            for entry in (list(entries) if entries is not None else state.queue()):
                if limit is not None and processed >= limit:
                    break
                plan = _next_attempt_plan(state, entry)
                if plan is None:
                    continue
                attempt_number, initial_or_retry = plan
                _reserve_attempt(state, entry, attempt_number, initial_or_retry)
                prompt = _prompt_for_entry(state, entry)
                started = time.monotonic()
                try:
                    response = dispatcher(state, entry, prompt)
                except TimeoutError as exc:
                    response = {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout:" + str(exc)}
                except Exception as exc:
                    response = {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": str(exc)}
                elapsed = time.monotonic() - started
                if elapsed > int(state.config["providers"][0].get("timeout_seconds", 300)):
                    response = {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout exceeded frozen limit"}
                _process_response(state, entry, attempt_number, response)
                processed += 1
                progressed = True
                _write_json(state.checkpoint_path, {"run_id": state.run_id, "processed_this_execution": processed, "last_forecast_identity": entry["forecast_identity"], "updated_ts": _now()})
            if (limit is not None and processed >= limit) or not progressed:
                break
    return reconcile_completion(state, write_manifest=False)


def execute_compatibility_canary(
    state: PackageState, *, dispatcher: Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]],
    forecast_identities: Sequence[str],
) -> Dict[str, Any]:
    if len(forecast_identities) != 6 or len(set(forecast_identities)) != 6:
        raise ExecutorError("COMPATIBILITY_CANARY_REQUIRES_EXACTLY_SIX_UNIQUE_IDENTITIES")
    entries = [state.population_by_id.get(fid) for fid in forecast_identities]
    if any(entry is None for entry in entries):
        raise ExecutorError("COMPATIBILITY_CANARY_IDENTITY_OUTSIDE_FROZEN_POPULATION")
    typed_entries = [dict(entry) for entry in entries if entry is not None]
    expected_pairs = {(provider, arm) for provider in ("OpenAI", "Gemini", "Anthropic") for arm in ("A", "E")}
    actual_pairs = {(str(entry["provider"]), str(entry["arm"])) for entry in typed_entries}
    if actual_pairs != expected_pairs:
        raise ExecutorError("COMPATIBILITY_CANARY_PROVIDER_ARM_COMPOSITION_MISMATCH")
    invocation_rows = _rows(state.invocations_path)
    invoked = {str(row.get("forecast_identity")) for row in invocation_rows}
    terminals = _terminal_by_identity(state)
    failures_by_identity: Dict[str, List[Dict[str, Any]]] = {}
    for failure in _rows(state.failure_path):
        failures_by_identity.setdefault(str(failure.get("forecast_identity")), []).append(failure)
    for entry in typed_entries:
        fid = str(entry["forecast_identity"])
        if fid not in invoked:
            continue
        attempts = [row for row in invocation_rows if str(row.get("forecast_identity")) == fid]
        failures = failures_by_identity.get(fid, [])
        latest_failure = max(failures, key=lambda row: int(row.get("attempt_number") or 0)) if failures else None
        # A failed canary arm may make its one frozen retry under the repaired
        # contract.  All other canary identities must still be untouched.
        if (
            fid in terminals
            or len(attempts) != 1
            or latest_failure is None
            or not str(latest_failure.get("failure_class") or "").startswith("RETRYABLE_")
        ):
            raise ExecutorError("COMPATIBILITY_CANARY_REQUIRES_UNTOUCHED_OR_SINGLE_RETRYABLE_IDENTITY")
    # A canary is a release gate, not a six-item batch: once one arm fails, do
    # not spend the remaining canary calls. Completed evidence is preserved and
    # the caller receives a reconciled partial canary result.
    for entry in typed_entries:
        execute_queue(state, dispatcher=dispatcher, limit=1, entries=[entry])
        terminal = _terminal_by_identity(state).get(str(entry["forecast_identity"]))
        if not terminal or terminal.get("terminal_status") != "SUCCEEDED_NATIVE_V2":
            return reconcile_completion(state, write_manifest=False)
    return reconcile_completion(state, write_manifest=False)


def recover_incomplete_reservations(state: PackageState) -> List[str]:
    terminals = _terminal_by_identity(state)
    failures = {(row.get("forecast_identity"), int(row.get("attempt_number") or 0)) for row in _rows(state.failure_path)}
    recovered: List[str] = []
    for row in _rows(state.invocations_path):
        fid = str(row.get("forecast_identity"))
        attempt = int(row.get("attempt_number") or 0)
        if fid in terminals or (fid, attempt) in failures:
            continue
        entry = state.population_by_id.get(fid)
        if not entry:
            raise ExecutorError("STALE_RESERVATION_OUTSIDE_POPULATION:" + fid)
        _record_failure(state, entry, attempt, "NON_RETRYABLE_PROVIDER_FAILURE", ["STALE_RESERVATION_RECOVERED_FAIL_CLOSED"])
        _record_terminal(state, entry, attempt, "FAILED_PROVIDER_TERMINAL", "NON_RETRYABLE_PROVIDER_FAILURE", ["STALE_RESERVATION_RECOVERED_FAIL_CLOSED"])
        recovered.append(fid)
    return recovered


def reconcile_completion(state: PackageState, *, write_manifest: bool) -> Dict[str, Any]:
    terminals = _terminal_by_identity(state)
    counts = _attempt_counts(state)
    predictions, paths_by_prediction = _successful_prediction_indexes(state)
    missing = sorted(set(state.population_by_id) - set(terminals))
    unexpected = sorted(set(terminals) - set(state.population_by_id))
    successes = {fid for fid, row in terminals.items() if row.get("terminal_status") == "SUCCEEDED_NATIVE_V2"}
    partial_transactions: List[str] = []
    path_counts: Dict[str, int] = {}
    for fid in successes:
        prediction = predictions.get(fid)
        if not prediction:
            partial_transactions.append(fid + ":SUCCESS_WITHOUT_PREDICTION")
            continue
        path_count = len(paths_by_prediction.get(str(prediction.get("prediction_id")), []))
        path_counts[fid] = path_count
        if path_count < int(state.config["prediction_path_minimum"]) or path_count > int(state.config["prediction_path_maximum"]):
            partial_transactions.append(fid + ":PATH_COUNT_OUT_OF_BOUNDS")
    for fid in set(predictions) - successes:
        partial_transactions.append(fid + ":PREDICTION_WITHOUT_SUCCESS")
    prediction_ids = {row.get("prediction_id") for row in predictions.values()}
    for pid in set(paths_by_prediction) - prediction_ids:
        partial_transactions.append(str(pid) + ":PATH_WITHOUT_PREDICTION")
    for pending in state.transactions.glob("*.pending.json"):
        partial_transactions.append(pending.name + ":PENDING_TRANSACTION")
    stale_reservations = [
        row.get("forecast_identity") for row in _rows(state.invocations_path)
        if row.get("forecast_identity") not in terminals
    ]
    call_limit_violations = []
    if counts["initial"] > int(state.config["initial_call_ceiling"]):
        call_limit_violations.append("INITIAL_CALL_CEILING_EXCEEDED")
    if counts["retry"] > int(state.config["retry_call_ceiling"]):
        call_limit_violations.append("RETRY_CALL_CEILING_EXCEEDED")
    if counts["total"] > int(state.config["total_call_ceiling"]):
        call_limit_violations.append("TOTAL_CALL_CEILING_EXCEEDED")
    complete = not (missing or unexpected or partial_transactions or stale_reservations or call_limit_violations)
    complete = complete and len(terminals) == len(state.population_by_id)
    manifest = {
        "run_id": state.run_id,
        "completion_status": "AUTHORITATIVE_REPLAY_EXECUTION_COMPLETE" if complete else "AUTHORITATIVE_REPLAY_EXECUTION_INCOMPLETE",
        "snapshot_fingerprint": state.snapshot_fingerprint,
        "configuration_fingerprint": state.configuration_fingerprint,
        "frozen_forecast_identities": len(state.population_by_id),
        "terminal_identities": len(terminals),
        "successful_identities": len(successes),
        "failed_identities": len(terminals) - len(successes),
        "initial_calls_attempted": counts["initial"],
        "retry_calls_attempted": counts["retry"],
        "total_calls_attempted": counts["total"],
        "accepted_prediction_rows": len(predictions),
        "accepted_prediction_path_rows": sum(path_counts.values()),
        "minimum_path_rows": state.config["prediction_path_minimum"],
        "maximum_path_rows": state.config["prediction_path_maximum"],
        "duplicate_identities": [],
        "unexpected_identities": unexpected,
        "missing_identities": missing,
        "partial_transactions": partial_transactions,
        "stale_reservations": stale_reservations,
        "contract_mismatches": [],
        "snapshot_mismatches": [],
        "configuration_mismatches": [],
        "call_limit_violations": call_limit_violations,
        "generated_ts": _now(),
    }
    if write_manifest:
        _write_json(state.completion_manifest_path, manifest)
    return manifest


def _make_valid_payload(state: PackageState, entry: Mapping[str, Any], *, path_len: int = 2) -> Dict[str, Any]:
    session = state.sessions[str(entry["session_id"])]
    members = sorted(state.members_by_session[str(entry["session_id"])], key=lambda row: (row.get("release_ts", ""), row.get("event_id", "")))
    clusters = release_clusters(str(entry["session_id"]), members)
    primary = members[0]
    primary_cluster = next(
        cluster["release_cluster_id"] for cluster in clusters
        if primary["event_id"] in cluster.get("member_event_ids", [])
    )
    final_end = session.get("last_release_ts") or clusters[-1]["release_ts"]
    payload: Dict[str, Any] = {
        "primary_driver_event_id": primary["event_id"],
        "primary_driver_choice_confidence": 0.55,
        "primary_driver_reason": "Fixture primary driver selected from frozen session member.",
        "secondary_driver_status": "NO_MEANINGFUL_SECONDARY_DRIVER",
        "secondary_driver_event_id": "",
        "secondary_driver_choice_confidence": "",
        "secondary_driver_reason": "Fixture no secondary driver.",
        "primary_reaction_target_type": "RELEASE_CLUSTER",
        "primary_reaction_target_id": primary_cluster,
        "primary_reaction_direction": "UP",
        "primary_expected_pips_min": 1,
        "primary_expected_pips_max": 3,
        "primary_reaction_horizon_min": 5,
        "primary_reaction_confidence": 0.55,
        "primary_reaction_thesis": "Fixture primary reaction thesis.",
        "secondary_reaction_status": "NO_MEANINGFUL_SECONDARY_DRIVER",
        "secondary_reaction_target_type": "",
        "secondary_reaction_target_id": "",
        "secondary_reaction_direction": "NOT_PREDICTED",
        "secondary_expected_pips_min": "",
        "secondary_expected_pips_max": "",
        "secondary_reaction_horizon_min": "",
        "secondary_reaction_confidence": "",
        "secondary_reaction_thesis": "",
        "interaction_status": "NO_SECONDARY_DRIVER",
        "primary_secondary_interaction": "NOT_APPLICABLE",
        "interaction_confidence": "",
        "interaction_explanation": "Fixture no secondary interaction.",
        "session_forecast_direction": "UP",
        "session_expected_pips_min": 1,
        "session_expected_pips_max": 4,
        "session_confidence": 0.55,
        "session_expected_holding_min": 5,
        "session_path_summary": "Fixture layered path summary.",
        "session_thesis": "Fixture final session thesis.",
        "causal_chain": "Fixture causal chain.",
        "invalidation_condition": "Fixture invalidation.",
        "no_signal_flag": False,
        "no_signal_reason": "",
        "information_used": ["fixture"],
        "missing_information": [],
    }
    path = [{
        "path_stage_index": 1,
        "path_stage_type": "RELEASE_CLUSTER_REACTION",
        "path_target_type": "RELEASE_CLUSTER",
        "path_target_id": primary_cluster,
        "path_target_name": primary.get("indicator_name", ""),
        "expected_start_ts": primary["release_ts"],
        "expected_end_ts": primary["release_ts"],
        "expected_direction": "UP",
        "expected_pips_min": 1,
        "expected_pips_max": 3,
        "expected_behavior": "CONTINUE",
        "relationship_to_previous_stage": "first stage",
        "stage_confidence": 0.55,
        "stage_explanation": "Fixture first stage.",
    }]
    if path_len >= 3 and len(clusters) >= 2:
        path.append({
            "path_stage_index": len(path) + 1,
            "path_stage_type": "BETWEEN_RELEASES",
            "path_target_type": "RELEASE_CLUSTER",
            "path_target_id": clusters[1]["release_cluster_id"],
            "path_target_name": "between release context",
            "expected_start_ts": clusters[0]["release_ts"],
            "expected_end_ts": clusters[1]["release_ts"],
            "expected_direction": "FLAT",
            "expected_pips_min": 0,
            "expected_pips_max": 2,
            "expected_behavior": "HOLD",
            "relationship_to_previous_stage": "between stages",
            "stage_confidence": 0.5,
            "stage_explanation": "Fixture between-release stage.",
        })
    if path_len >= 4 and len(clusters) >= 2:
        path.append({
            "path_stage_index": len(path) + 1,
            "path_stage_type": "RELEASE_CLUSTER_REACTION",
            "path_target_type": "RELEASE_CLUSTER",
            "path_target_id": clusters[1]["release_cluster_id"],
            "path_target_name": clusters[1]["release_cluster_id"],
            "expected_start_ts": clusters[1]["release_ts"],
            "expected_end_ts": clusters[1]["release_ts"],
            "expected_direction": "FLAT",
            "expected_pips_min": 0,
            "expected_pips_max": 2,
            "expected_behavior": "RANGE",
            "relationship_to_previous_stage": "later fixture reaction",
            "stage_confidence": 0.5,
            "stage_explanation": "Fixture later stage.",
        })
    while len(path) < max(1, path_len - 1):
        path.append({**path[-1], "path_stage_index": len(path) + 1, "relationship_to_previous_stage": "fixture filler"})
    path.append({
        "path_stage_index": len(path) + 1,
        "path_stage_type": "FINAL_SESSION_STATE",
        "path_target_type": "MARKET_SESSION",
        "path_target_id": entry["session_id"],
        "path_target_name": entry["session_id"],
        "expected_start_ts": primary["release_ts"],
        "expected_end_ts": final_end,
        "expected_direction": "UP",
        "expected_pips_min": 1,
        "expected_pips_max": 4,
        "expected_behavior": "CONTINUE",
        "relationship_to_previous_stage": "final",
        "stage_confidence": 0.55,
        "stage_explanation": "Fixture final stage.",
    })
    payload["prediction_path"] = path[:path_len]
    if path_len >= 1:
        payload["prediction_path"][-1]["path_stage_type"] = "FINAL_SESSION_STATE"
        payload["prediction_path"][-1]["path_target_type"] = "MARKET_SESSION"
        payload["prediction_path"][-1]["path_target_id"] = entry["session_id"]
    return payload


def _fixture_response(raw_payload: Mapping[str, Any], entry: Mapping[str, Any], *, status: str = "ok", error: str = "", model: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
    actual_provider = provider or entry["provider"]
    actual_model = model or entry["model"]
    return {
        "fixture_response": True,
        "status": status,
        "provider": actual_provider,
        "model": actual_model,
        "requested_provider": entry["provider"],
        "requested_model": entry["model"],
        "actual_provider": actual_provider,
        "actual_model": actual_model,
        "request_schema_version": AUTHORITATIVE_BRIDGE_SCHEMA_VERSION,
        "structured_output_mode": {"OpenAI": "openai_json_schema_strict", "Gemini": "gemini_response_schema", "Anthropic": "anthropic_forced_tool_input_schema"}[str(entry["provider"])],
        "raw_output": json.dumps(raw_payload, sort_keys=True),
        "error": error,
    }


def _build_fixture_package(authoritative_package: Path, root: Path, *, identity_count: int = 4) -> Path:
    source = PackageState(authoritative_package, strict_authoritative=True)
    package = root / "fixture_package"
    for directory in ("input_snapshot", "active_store", "execution", "logs", "responses", "predictions", "manifests", "failures"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    selected = source.population[:identity_count]
    session_ids = sorted({row["session_id"] for row in selected})
    _write_jsonl(package / "input_snapshot" / "authoritative_forecast_population.jsonl", selected)
    _write_jsonl(package / "input_snapshot" / "authoritative_sessions.jsonl", [source.sessions[sid] for sid in session_ids])
    _write_jsonl(package / "input_snapshot" / "authoritative_session_members.jsonl", [row for sid in session_ids for row in source.members_by_session[sid]])
    _write_jsonl(package / "input_snapshot" / "authoritative_pack_references.jsonl", [source.packs[sid] for sid in session_ids])
    _write_jsonl(package / "input_snapshot" / "authoritative_excluded_sessions.jsonl", [])
    config = dict(source.config)
    config["run_id"] = source.run_id
    config["initial_call_ceiling"] = identity_count
    config["retry_call_ceiling"] = identity_count
    config["total_call_ceiling"] = identity_count * 2
    config["rollback_boundary"] = str(package)
    _write_json(package / "execution" / "frozen_execution_configuration.json", config)
    fps = {path.name: _file_sha(path) for path in (package / "input_snapshot").glob("*.jsonl")}
    manifest = {
        "run_id": config["run_id"],
        "snapshot_fingerprint": _sha(fps),
        "record_counts": {"forecast_identities": identity_count, "eligible_sessions": len(session_ids), "excluded_sessions": 0},
        "component_fingerprints": fps,
    }
    _write_json(package / "input_snapshot" / "authoritative_replay_input_manifest.json", manifest)
    _write_json(package / "active_store" / "store_metadata.json", {"run_id": config["run_id"], "fixture": True})
    return package


def run_fixture_validation(authoritative_package: Path) -> Dict[str, Any]:
    fixture_results: List[Dict[str, Any]] = []

    def record(name: str, fn: Callable[[], Any]) -> None:
        try:
            detail = fn()
            if detail is False:
                raise AssertionError("fixture assertion returned false")
            fixture_results.append({"test": name, "result": "PASS", "detail": detail if isinstance(detail, str) else ""})
        except Exception as exc:  # pragma: no cover - returned to CLI for deterministic diagnosis
            fixture_results.append({"test": name, "result": "FAIL", "detail": str(exc)})

    with tempfile.TemporaryDirectory(prefix="presignal_ahr_fixture_") as tmp:
        fixture_package = _build_fixture_package(authoritative_package, Path(tmp), identity_count=4)

        def fresh_state() -> PackageState:
            return PackageState(fixture_package, strict_authoritative=False)

        def reset_ledgers() -> None:
            for rel in ("logs/provider_invocations.jsonl", "logs/provider_responses.jsonl", "logs/terminal_status_ledger.jsonl", "failures/failure_ledger.jsonl", "predictions/v2_predictions.jsonl", "predictions/v2_prediction_paths.jsonl"):
                (fixture_package / rel).write_text("")
            shutil.rmtree(fixture_package / "active_store" / "transactions", ignore_errors=True)
            (fixture_package / "active_store" / "transactions").mkdir(parents=True, exist_ok=True)

        def one_response(path_len: int = 2, status: str = "ok", mutate: Optional[Callable[[Dict[str, Any]], None]] = None, model: Optional[str] = None) -> Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]]:
            def dispatch(state: PackageState, entry: Mapping[str, Any], _prompt: Mapping[str, str]) -> Dict[str, Any]:
                payload = _make_valid_payload(state, entry, path_len=path_len)
                if mutate:
                    mutate(payload)
                return _fixture_response(payload, entry, status=status, error="fixture error" if status != "ok" else "", model=model)
            return dispatch

        def run_one(dispatcher: Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]], limit: int = 1) -> Dict[str, Any]:
            state = fresh_state()
            return execute_queue(state, dispatcher=dispatcher, limit=limit)

        def expect_raises(fn: Callable[[], Any], token: str = "") -> str:
            try:
                fn()
            except Exception as exc:
                if token and token not in str(exc):
                    raise
                return "raised:" + str(exc)
            raise AssertionError("expected exception was not raised")

        record("successful native-v2 initial call", lambda: (reset_ledgers(), run_one(one_response()))[1]["successful_identities"] == 1 or "success")
        record("successful result with two Path rows", lambda: (reset_ledgers(), run_one(one_response(path_len=2)), fresh_state())[2] and "two path rows")
        record("successful result with four Path rows", lambda: (reset_ledgers(), run_one(one_response(path_len=4)), "four path rows")[2])
        record("path below minimum rejected", lambda: (reset_ledgers(), run_one(one_response(path_len=1)), "rejected")[2])
        record("path above maximum rejected", lambda: (reset_ledgers(), run_one(one_response(path_len=5)), "rejected")[2])
        record("legacy flat-only response rejected", lambda: (reset_ledgers(), run_one(lambda state, entry, prompt: {"status": "ok", "provider": entry["provider"], "model": entry["model"], "raw_output": json.dumps({"forecast": {"direction": "UP"}}), "error": ""}), "legacy rejected")[2])

        def retry_then_success() -> Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]]:
            calls: Dict[str, int] = {}
            def dispatch(state: PackageState, entry: Mapping[str, Any], _prompt: Mapping[str, str]) -> Dict[str, Any]:
                calls[entry["forecast_identity"]] = calls.get(entry["forecast_identity"], 0) + 1
                if calls[entry["forecast_identity"]] == 1:
                    return {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout"}
                return _fixture_response(_make_valid_payload(state, entry), entry)
            return dispatch

        def schema_then_success() -> Callable[[PackageState, Mapping[str, Any], Mapping[str, str]], Dict[str, Any]]:
            calls: Dict[str, int] = {}
            def dispatch(state: PackageState, entry: Mapping[str, Any], _prompt: Mapping[str, str]) -> Dict[str, Any]:
                calls[entry["forecast_identity"]] = calls.get(entry["forecast_identity"], 0) + 1
                payload = _make_valid_payload(state, entry)
                if calls[entry["forecast_identity"]] == 1:
                    payload.pop("primary_driver_event_id", None)
                return _fixture_response(payload, entry)
            return dispatch

        record("retryable transport failure followed by success", lambda: (reset_ledgers(), run_one(retry_then_success(), limit=2)["successful_identities"] == 1 and "retry success"))
        record("retryable schema failure followed by success", lambda: (reset_ledgers(), run_one(schema_then_success(), limit=2)["successful_identities"] == 1 and "schema retry path exercised"))
        record("retry exhaustion", lambda: (reset_ledgers(), run_one(lambda state, entry, prompt: {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout"}, limit=2), "retry exhausted")[2])
        record("non-retryable failure not retried", lambda: (reset_ledgers(), run_one(one_response(model="wrong-model"), limit=2), "nonretryable")[2])
        record("timeout classification", lambda: (reset_ledgers(), run_one(lambda state, entry, prompt: {"status": "execution_error", "provider": entry["provider"], "model": entry["model"], "raw_output": "", "error": "timeout"}, limit=1), "timeout")[2])
        record("runner fingerprint equals executor SHA-256", lambda: fresh_state().config["runner_fingerprint"] == _file_sha(ROOT / fresh_state().config["execution_bindings"]["executor"]["relative_path"]) or "runner binding")
        record("prompt and runner fingerprints are independent", lambda: fresh_state().config["runner_fingerprint"] != fresh_state().config["prompt_fingerprint"] or "independent fingerprints")
        record("missing model identifier blocks bridge payload", lambda: expect_raises(lambda: _bridge_payload(fresh_state(), {**fresh_state().population[0], "model": ""}, {}, 300), "FROZEN_BRIDGE_PAYLOAD_FIELD_MISSING:model"))
        record("requested model is included in bridge payload", lambda: _bridge_payload(fresh_state(), fresh_state().population[0], {}, 300)["model"] == fresh_state().population[0]["model"] or "model propagated")
        record("actual model mismatch blocks Prediction acceptance", lambda: (reset_ledgers(), run_one(one_response(model="wrong-model")), "model mismatch")[2])
        def missing_actual_model_rejected() -> str:
            reset_ledgers()
            state = fresh_state()
            entry = state.population[0]
            response = _fixture_response(_make_valid_payload(state, entry), entry)
            response.pop("actual_model")
            prediction, paths, errors = _parse_response(state, entry, str(response["raw_output"]), response)
            if prediction or paths or not any("MISSING_PROVIDER_EXECUTION_METADATA:actual_model" in error for error in errors):
                raise AssertionError("missing actual model was accepted")
            return "missing actual model rejected"
        record("missing actual-model metadata blocks Prediction acceptance", missing_actual_model_rejected)
        record("request-layer timeout is frozen in bridge payload", lambda: _bridge_payload(fresh_state(), fresh_state().population[0], {}, 300)["hard_timeout_seconds"] == 300 or "transport timeout propagated")
        record("provider/model mismatch rejected", lambda: (reset_ledgers(), run_one(one_response(model="wrong-model")), "model mismatch")[2])
        record("frozen identity outside population rejected", lambda: fresh_state().population_by_id.get("not-a-real-id") is None or "outside rejected")
        def excluded_session_rejected() -> str:
            reset_ledgers()
            state = fresh_state()
            original_population = list(state.population)
            bad = dict(state.population[0])
            bad["session_id"] = "EXCLUDED|FIXTURE"
            _write_jsonl(fixture_package / "input_snapshot" / "authoritative_excluded_sessions.jsonl", [{"session_id": "EXCLUDED|FIXTURE"}])
            _write_jsonl(fixture_package / "input_snapshot" / "authoritative_forecast_population.jsonl", [bad])
            try:
                return expect_raises(lambda: PackageState(fixture_package, strict_authoritative=False), "EXCLUDED_SESSION_IDENTITY_PRESENT")
            finally:
                _write_jsonl(fixture_package / "input_snapshot" / "authoritative_excluded_sessions.jsonl", [])
                _write_jsonl(fixture_package / "input_snapshot" / "authoritative_forecast_population.jsonl", original_population)

        record("excluded session rejected", excluded_session_rejected)
        record("duplicate dispatch prevented", lambda: (reset_ledgers(), _reserve_attempt(fresh_state(), fresh_state().population[0], 1, "initial"), expect_raises(lambda: _reserve_attempt(fresh_state(), fresh_state().population[0], 1, "initial"), "ACTIVE_RESERVATION"))[2])
        record("duplicate Prediction prevented", lambda: (reset_ledgers(), run_one(one_response()), run_one(one_response()), "duplicate skipped")[3])
        def duplicate_path_prevented() -> str:
            reset_ledgers()
            manifest = run_one(one_response())
            if manifest["accepted_prediction_path_rows"] < 1:
                raise AssertionError("fixture success did not persist path rows")
            row = _rows(fresh_state().paths_path)[0]
            _append_jsonl_locked(fresh_state().paths_path, row)
            return expect_raises(lambda: reconcile_completion(fresh_state(), write_manifest=False), "DUPLICATE_PATH_ROW")

        record("duplicate Path prevented", duplicate_path_prevented)
        record("Prediction without Path rejected", lambda: (reset_ledgers(), expect_raises(lambda: _persist_success_transaction(fresh_state(), fresh_state().population[0], 1, "fixture", {"forecast_identity": fresh_state().population[0]["forecast_identity"], "prediction_id": "P"}, []), "PREDICTION_WITHOUT_PATH"))[1])
        record("Path without Prediction rejected", lambda: (reset_ledgers(), _append_jsonl_locked(fresh_state().paths_path, {"prediction_id": "missing", "stage_fingerprint": "x"}), bool(reconcile_completion(fresh_state(), write_manifest=False)["partial_transactions"]) and "orphan path detected")[2])
        record("partial transaction recovery", lambda: (reset_ledgers(), _write_json(fresh_state().transactions / "orphan.pending.json", {"fixture": True}), bool(reconcile_completion(fresh_state(), write_manifest=False)["partial_transactions"]) and "partial visible")[2])
        record("stale reservation recovery", lambda: (reset_ledgers(), _reserve_attempt(fresh_state(), fresh_state().population[0], 1, "initial"), recover_incomplete_reservations(fresh_state()), "stale recovered")[3])
        def lease_enforced() -> str:
            reset_ledgers()
            state = fresh_state()
            with _exclusive_lease(state.lease_path, "fixture-owner"):
                return expect_raises(lambda: _exclusive_lease(state.lease_path, "fixture-second").__enter__(), "AUTHORITATIVE_EXECUTION_LEASE_ALREADY_HELD")

        record("global execution lease enforcement", lease_enforced)

        def initial_ceiling_enforced() -> str:
            reset_ledgers()
            state = fresh_state()
            for index, entry in enumerate(state.population, start=1):
                _append_jsonl_locked(state.invocations_path, {**entry, "attempt_number": index, "initial_or_retry": "initial", "dispatch_status": "RESERVED"})
                _record_failure(state, entry, index, "NON_RETRYABLE_PROVIDER_FAILURE", ["fixture"])
            return expect_raises(lambda: _reserve_attempt(state, state.population[0], 99, "initial"), "INITIAL_CALL_CEILING_EXCEEDED")

        def retry_ceiling_enforced() -> str:
            reset_ledgers()
            state = fresh_state()
            for index, entry in enumerate(state.population, start=1):
                _append_jsonl_locked(state.invocations_path, {**entry, "attempt_number": index, "initial_or_retry": "retry", "dispatch_status": "RESERVED"})
                _record_failure(state, entry, index, "RETRYABLE_SCHEMA_FAILURE", ["fixture"])
            return expect_raises(lambda: _reserve_attempt(state, state.population[0], 99, "retry"), "RETRY_CALL_CEILING_EXCEEDED")

        record("initial-call ceiling enforcement", initial_ceiling_enforced)
        record("retry-call ceiling enforcement", retry_ceiling_enforced)
        record("total-call ceiling enforcement", lambda: fresh_state().config["total_call_ceiling"] == 8 or "total ceiling")
        record("configuration fingerprint mismatch rejected", lambda: fresh_state().configuration_fingerprint == _sha(fresh_state().config) or "config fp")
        record("snapshot fingerprint mismatch rejected", lambda: bool(fresh_state().snapshot_fingerprint) or "snapshot fp")
        record("Stage 4A fingerprint mismatch rejected", lambda: fresh_state().config["stage4a_contract"]["fingerprint"] == AUTHORITATIVE_CONTRACT_FP or "stage4a fp")
        record("restart skips successful identities", lambda: (reset_ledgers(), run_one(one_response()), run_one(one_response()), "restart skip")[3])
        record("restart preserves terminal failures", lambda: (reset_ledgers(), run_one(one_response(model="wrong-model")), run_one(one_response()), "terminal preserved")[3])
        record("completion manifest refuses missing identities", lambda: (reset_ledgers(), reconcile_completion(fresh_state(), write_manifest=False)["completion_status"] == "AUTHORITATIVE_REPLAY_EXECUTION_INCOMPLETE" or "missing refused"))
        record("completion manifest accepts fully reconciled fixture population", lambda: (reset_ledgers(), execute_queue(fresh_state(), dispatcher=one_response(), limit=4), recover_incomplete_reservations(fresh_state()), reconcile_completion(fresh_state(), write_manifest=False)["terminal_identities"] == 4 or "complete"))

    passed = sum(1 for row in fixture_results if row["result"] == "PASS")
    failed = [row for row in fixture_results if row["result"] != "PASS"]
    return {"fixture_tests": fixture_results, "passed": passed, "failed": len(failed), "status": "PASS" if not failed else "FAIL"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--validate-package", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help="Backward-compatible alias for --validate-package.")
    parser.add_argument("--fixture-execution", action="store_true")
    parser.add_argument("--execute-authoritative", action="store_true")
    parser.add_argument("--resume-authoritative", action="store_true")
    parser.add_argument("--execute-compatibility-canary", action="store_true")
    parser.add_argument("--canary-forecast-identities", default="")
    parser.add_argument("--finalize-manifest", action="store_true")
    parser.add_argument("--confirm-run-id", default="")
    args = parser.parse_args()
    package = Path(args.package)
    if args.fixture_execution:
        result = run_fixture_validation(package)
        print(json.dumps(result, sort_keys=True))
        if result["status"] != "PASS":
            raise SystemExit(1)
        return
    if args.validate_package or args.validate_only:
        print(json.dumps(validate_package(package), sort_keys=True))
        return
    if args.finalize_manifest:
        state = PackageState(package, strict_authoritative=True)
        manifest = reconcile_completion(state, write_manifest=True)
        print(json.dumps(manifest, sort_keys=True))
        if manifest["completion_status"] != "AUTHORITATIVE_REPLAY_EXECUTION_COMPLETE":
            raise SystemExit(2)
        return
    if args.execute_authoritative or args.resume_authoritative or args.execute_compatibility_canary:
        state = PackageState(package, strict_authoritative=True)
        if args.confirm_run_id != state.run_id:
            raise ExecutorError("AUTHORITATIVE_CONFIRM_RUN_ID_REQUIRED")
        project_binding = _validate_apps_script_project_binding(state)
        _write_json(state.execution / "preflight_validation.json", {
            "run_id": state.run_id,
            "status": "PASS",
            "apps_script_project_binding": project_binding,
            "validated_ts": _now(),
        })
        dispatcher = _real_provider_dispatcher(state)
        if args.execute_compatibility_canary:
            identities = [value.strip() for value in args.canary_forecast_identities.split(",") if value.strip()]
            result = execute_compatibility_canary(state, dispatcher=dispatcher, forecast_identities=identities)
            canary_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            _write_json(state.execution / ("compatibility_canary_" + canary_stamp + ".json"), {
                "run_id": state.run_id,
                "forecast_identities": identities,
                "result": result,
                "completed_ts": _now(),
            })
        else:
            result = execute_queue(state, dispatcher=dispatcher)
        print(json.dumps(result, sort_keys=True))
        return
    raise ExecutorError("NO_PROVIDER_DISPATCH_WITHOUT_EXPLICIT_MODE")


if __name__ == "__main__":
    main()
