"""Durable, manifest-bound R3 historical-verification dispatcher.

The dispatcher deliberately owns only persistence and stage ordering.  It
reuses the R2 frozen-replay population/Outcome helpers, the explicit-input
lineage builders, the R3 runtime binding, and the existing single-pair
provider bridge and evaluator.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat_contract
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_single_event_path_pair_v1 as single
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

OUT = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification"
PREP = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e"
POPULATION = PREP / "fresh_verification_population_plan.json"
R9_MANIFEST = ROOT / "outputs/presignal_v21_step8_r3_r9_provider_isolation/STEP8-R3-R9-3f72650/verification_manifest.json"

STAGES = (
    "PENDING", "ATTENTION_REQUEST_FROZEN", "ATTENTION_SENT", "ATTENTION_RESPONSE_RECEIVED",
    "ATTENTION_ACCEPTED", "ATTENTION_REJECTED", "NOT_FORECAST_SELECTED", "REQUEST_FROZEN",
    "REQUEST_SENT", "REQUEST_ACCEPTED", "REQUEST_REJECTED", "PACKS_FROZEN",
    "FORECAST_PROMPTS_FROZEN", "PACK_A_SENT", "PACK_A_ACCEPTED", "PACK_A_REJECTED",
    "PACK_E_SENT", "PACK_E_ACCEPTED", "PACK_E_REJECTED", "OUTCOME_ATTACHED", "EVALUATED",
    "COMPLETE", "TERMINAL_INCOMPLETE",
)
TERMINAL = {"COMPLETE", "TERMINAL_INCOMPLETE", "NOT_FORECAST_SELECTED"}


class DispatchError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def append(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical(value) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def operation_key(identity: Mapping[str, Any]) -> str:
    return sha256(identity)


def process_start_time(pid: int) -> str | None:
    try:
        return subprocess.check_output(["ps", "-o", "lstart=", "-p", str(pid)], text=True).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def sent_orphans(run: Path) -> list[dict[str, Any]]:
    """Read-only reconstruction of calls which may have reached a provider."""
    ledger = run / "transition_ledger.jsonl"
    if not ledger.exists():
        return []
    result_keys = {path.stem for path in (run / "stage_results").glob("*.json")}
    found = []
    for line in ledger.read_text().splitlines():
        row = json.loads(line)
        if row.get("to") not in {"ATTENTION_SENT", "REQUEST_SENT", "PACK_A_SENT", "PACK_E_SENT"}:
            continue
        key = row["operation_key"]
        if key not in result_keys:
            found.append({"operation_id": key, "identity": row["identity"], "transition_timestamp": row["timestamp"], "classification": "SENT_NO_CONFIRMED_RESPONSE"})
    return found


class RunLease:
    """An advisory OS lock plus durable owner evidence for one immutable run."""

    def __init__(self, run: Path, command: str):
        self.run, self.command = run, command
        self.path = run / "run_lease.json"
        self.lock_path = run / "run_lease.lock"
        self.handle: Any = None
        self.lease_id: str | None = None

    def _metadata(self, status: str, **extra: Any) -> dict[str, Any]:
        return {"run_id": self.run.name, "lease_id": self.lease_id, "owner_pid": os.getpid(), "owner_process_start_time": process_start_time(os.getpid()), "owner_host": socket.gethostname(), "owner_command": self.command, "acquired_at": now(), "heartbeat_at": now(), "lease_expires_at": None, "lease_generation": 1, "status": status, **extra}

    def acquire(self) -> None:
        self.run.mkdir(parents=True, exist_ok=True)
        self.handle = self.lock_path.open("a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            active = read_json(self.path) if self.path.exists() else {}
            self.handle.close(); self.handle = None
            raise DispatchError("V2_1_STEP8_R3_R10_RUN_ALREADY_OWNED:" + canonical(active))
        # Never take a formerly-owned run if an external call may be in flight.
        orphans = sent_orphans(self.run)
        if orphans:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN); self.handle.close(); self.handle = None
            raise DispatchError("V2_1_STEP8_R3_R10_ORPHANED_CALL_BLOCKED")
        self.lease_id = "LEASE_" + uuid.uuid4().hex
        atomic(self.path, self._metadata("ACTIVE"))

    def heartbeat(self) -> None:
        if self.handle is None or self.lease_id is None:
            raise DispatchError("V2_1_STEP8_R3_R10_RUN_ALREADY_OWNED")
        current = read_json(self.path)
        if current.get("lease_id") != self.lease_id or current.get("status") != "ACTIVE":
            raise DispatchError("V2_1_STEP8_R3_R10_RUN_ALREADY_OWNED")
        current["heartbeat_at"] = now()
        atomic(self.path, current)

    def release(self, reason: str) -> None:
        if self.handle is None:
            return
        current = read_json(self.path) if self.path.exists() else self._metadata("RELEASED")
        if current.get("lease_id") == self.lease_id:
            current.update({"status": "RELEASED", "released_at": now(), "release_reason": reason})
            atomic(self.path, current)
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close(); self.handle = None


def lease_status(run: Path) -> dict[str, Any]:
    if not (run / "run_lease.json").exists():
        return {"classification": "NO_LEASE", "metadata": None}
    metadata = read_json(run / "run_lease.json")
    start = process_start_time(int(metadata.get("owner_pid") or 0))
    active = metadata.get("status") == "ACTIVE" and start == metadata.get("owner_process_start_time")
    if active:
        classification = "ACTIVE_OWNER"
    elif sent_orphans(run):
        classification = "STALE_EXTERNAL_CALL_STATUS_UNKNOWN"
    else:
        classification = "STALE_NO_EXTERNAL_CALL_RISK"
    return {"classification": classification, "metadata": metadata}


class ExecutionLoop:
    """Persisted stage dispatcher with an injectable bridge for call-free tests."""

    def __init__(self, run_id: str, dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None, manifest_path: Path = R9_MANIFEST, execution_plan_path: Path | None = None):
        self.gate = binding.gate(manifest_path)
        if self.gate["contract"]["contract_version"] != compat_contract.CONTRACT_VERSION:
            raise DispatchError("V2_1_STEP8_R9_PREVIOUS_CONTRACT_REJECTED")
        self.run = OUT / run_id
        self.state_path = self.run / "execution_state.json"
        self.dispatcher = dispatcher
        self.execution_plan_path = execution_plan_path
        self.execution_plan = read_json(execution_plan_path) if execution_plan_path else None
        self.population_path = Path(self.execution_plan["population_path"]) if self.execution_plan else POPULATION
        self._validate_execution_plan()
        self.lease = RunLease(self.run, " ".join(sys.argv))
        self._source: dict[str, Any] | None = None
        self._episodes: dict[str, dict[str, Any]] | None = None

    def _validate_execution_plan(self) -> None:
        """Fail closed when a final cohort differs from its frozen manifest."""
        if self.execution_plan is None:
            return
        required = ("contract", "providers", "episode_ids", "maximum_processed_episodes", "target_complete_episodes", "checkpoint_complete_episodes", "maximum_forecast_arms")
        if any(key not in self.execution_plan for key in required):
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")
        if self.execution_plan["contract"] != self.gate["contract"] or self.execution_plan["providers"] != self.gate["provider_routes"]:
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")
        population = read_json(self.population_path).get("episodes", [])
        population_ids = [row.get("episode_id") for row in population]
        if self.execution_plan["episode_ids"] != population_ids:
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")
        if len(population_ids) > int(self.execution_plan["maximum_processed_episodes"]):
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")

    def initialize(self) -> dict[str, Any]:
        if self.state_path.exists():
            return read_json(self.state_path)
        state = {
            "run_id": self.run.name,
            "gate": self.gate,
            "processed_episodes": 0,
            "unique_complete_episodes": 0,
            "complete_paired_observations": 0,
            "current": {},
            "terminal_identities": [],
            "processed_episode_ids": [],
            "provider_paths": {},
            "episode_states": {},
            "last_durable_checkpoint": "INITIALIZED",
            "blocking_error": None,
            "forecast_call_reservations": [],
            "execution_plan_fingerprint": sha256(self.execution_plan) if self.execution_plan else None,
        }
        atomic(self.state_path, state)
        atomic(self.run / "run_manifest.json", {**self.gate, "execution_plan": self.execution_plan})
        return state

    def status(self) -> dict[str, Any]:
        state = self.initialize()
        state["lease"] = lease_status(self.run)
        state["orphaned_operations"] = sent_orphans(self.run)
        state["safe_to_resume"] = not state["orphaned_operations"] and state["lease"]["classification"] != "ACTIVE_OWNER"
        return state

    def acquire_ownership(self) -> None:
        if self.lease.handle is None:
            self.lease.acquire()

    def release_ownership(self, reason: str) -> None:
        self.lease.release(reason)

    def _operation_event(self, identity: Mapping[str, Any], state: str, **extra: Any) -> None:
        append(self.run / "operation_journal.jsonl", {
            "operation_id": operation_key(identity), "run_id": identity["run_id"], "episode_id": identity["episode_id"],
            "session_id": identity["session_id"], "provider": identity["provider"], "model": identity["model"],
            "stage": identity["stage"], "information_arm": identity["information_arm"],
            "contract_fingerprint": identity["contract_fingerprint"], "attempt_number": identity["attempt_number"],
            "lease_id": self.lease.lease_id, "owner_pid": os.getpid(), "owner_process_start_time": process_start_time(os.getpid()),
            "state": state, "timestamp": now(), **extra,
        })

    def _record_provider_path(self, episode_id: str, provider: str, state_name: str) -> None:
        state = self.initialize()
        paths = state.setdefault("provider_paths", {}).setdefault(episode_id, {})
        paths[provider] = state_name
        terminals = set(paths.values())
        if all(provider_name in paths and paths[provider_name] in {"COMPLETE", "TERMINAL_INCOMPLETE"} for provider_name in self.gate["provider_routes"]):
            state.setdefault("episode_states", {})[episode_id] = "COMPLETE" if "COMPLETE" in terminals else "TERMINAL_NO_COMPLETE_PROVIDER"
        else:
            state.setdefault("episode_states", {})[episode_id] = "IN_PROGRESS"
        atomic(self.state_path, state)

    def _identity(self, episode: Mapping[str, Any], provider: str, model: str, stage: str, arm: str | None = None, attempt: int = 1) -> dict[str, Any]:
        return {
            "run_id": self.run.name,
            "session_id": episode["session_id"],
            "episode_id": episode["episode_id"],
            "provider": provider,
            "model": model,
            "stage": stage,
            "information_arm": arm,
            "contract_fingerprint": self.gate["contract"]["contract_fingerprint"],
            "attempt_number": attempt,
        }

    def _paths(self, identity: Mapping[str, Any]) -> tuple[Path, Path]:
        key = operation_key(identity)
        return self.run / "stage_payloads" / (key + ".json"), self.run / "stage_results" / (key + ".json")

    def _state(self, identity: Mapping[str, Any]) -> str | None:
        return self.initialize()["current"].get(operation_key(identity))

    def _transition(self, identity: Mapping[str, Any], stage: str, *, result: Mapping[str, Any] | None = None) -> None:
        if stage not in STAGES:
            raise DispatchError("INVALID_STATE")
        state = self.initialize()
        key = operation_key(identity)
        previous = state["current"].get(key)
        if previous in TERMINAL and stage != previous:
            raise DispatchError("V2_1_STEP8_R3_R2_DUPLICATE_ACCEPTED_CALL_BLOCKED")
        append(self.run / "transition_ledger.jsonl", {"identity": dict(identity), "operation_key": key, "from": previous, "to": stage, "result_fingerprint": sha256(result) if result else None, "timestamp": now()})
        state["current"][key] = stage
        if stage in TERMINAL and key not in state["terminal_identities"]:
            state["terminal_identities"].append(key)
        state["last_durable_checkpoint"] = stage
        atomic(self.state_path, state)

    def _persist_payload(self, identity: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
        path, _ = self._paths(identity)
        frozen = {"identity": dict(identity), "payload": dict(payload), "payload_fingerprint": sha256(payload), "persisted_ts": now()}
        if path.exists():
            existing = read_json(path)
            if existing["payload_fingerprint"] != frozen["payload_fingerprint"]:
                raise DispatchError("V2_1_STEP8_R3_R4_DISPATCH_RECONCILIATION_CONFLICT")
            return existing
        atomic(path, frozen)
        return frozen

    def _persist_result(self, identity: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
        _, path = self._paths(identity)
        frozen = {"identity": dict(identity), **dict(result), "result_fingerprint": sha256(result), "persisted_ts": now()}
        if path.exists():
            existing = read_json(path)
            if existing["result_fingerprint"] != frozen["result_fingerprint"]:
                raise DispatchError("V2_1_STEP8_R3_R4_DISPATCH_RECONCILIATION_CONFLICT")
            return existing
        atomic(path, frozen)
        return frozen

    def _persist_raw_bridge_response(self, identity: Mapping[str, Any], response: Mapping[str, Any]) -> None:
        """Durably preserve provider evidence before Python parsing can fail."""
        path = self.run / "raw_provider_responses" / (operation_key(identity) + ".json")
        raw = {
            "identity": dict(identity),
            "raw_output": response.get("raw_output_original", response.get("raw_output")),
            "raw_response_fingerprint": sha256(response.get("raw_output_original", response.get("raw_output"))),
            "response_blocks": response.get("raw_response_blocks"),
            "provider_response_body": response.get("provider_response_body"),
            "stop_reason": response.get("stop_reason"),
            "usage": {
                "prompt_tokens": response.get("prompt_tokens"),
                "completion_tokens": response.get("completion_tokens"),
                "cache_creation_input_tokens": response.get("cache_creation_input_tokens"),
                "cache_read_input_tokens": response.get("cache_read_input_tokens"),
            },
            "transport_status": response.get("status"),
            "response_status": response.get("response_status"),
            "configured_max_output_tokens": response.get("configured_max_output_tokens"),
            "persisted_ts": now(),
        }
        if path.exists():
            existing = read_json(path)
            if existing["raw_response_fingerprint"] != raw["raw_response_fingerprint"]:
                raise DispatchError("V2_1_STEP8_R3_R4_DISPATCH_RECONCILIATION_CONFLICT")
            return
        atomic(path, raw)

    def _call(self, identity: Mapping[str, Any], payload: Mapping[str, Any], handler: Callable[[], Mapping[str, Any]], sent: str, received: str) -> dict[str, Any]:
        self.acquire_ownership()
        self.lease.heartbeat()
        self._persist_payload(identity, payload)
        _, result_path = self._paths(identity)
        if result_path.exists():
            return read_json(result_path)
        # A pre-call transition without a durable response cannot establish
        # whether the provider completed the original identity.  Failing
        # closed preserves the no-duplicate-call contract on resume.
        if self._state(identity) == sent:
            state = self.initialize()
            state["blocking_error"] = "V2_1_STEP8_R3_R4_DISPATCH_RECONCILIATION_CONFLICT"
            atomic(self.state_path, state)
            raise DispatchError("V2_1_STEP8_R3_R4_DISPATCH_RECONCILIATION_CONFLICT")
        self._operation_event(identity, "RESERVED", payload_fingerprint=sha256(payload), prompt_fingerprint=payload.get("prompt_fingerprint"), call_budget_reserved=identity["stage"] == "FORECAST")
        self._operation_event(identity, "DISPATCH_STARTED", dispatch_started_at=now())
        self._transition(identity, sent)
        try:
            returned = dict(handler())
            record = {"stage": identity["stage"], "transport_status": returned.get("transport_status", "ok"), "raw_response": returned.get("raw_response"), "raw_response_fingerprint": sha256(returned.get("raw_response")), "parser_result": returned.get("parser_result"), "validator_result": returned.get("validator_result"), "accepted": bool(returned.get("accepted")), "rejection_reason": returned.get("rejection_reason"), "output": returned.get("output"), "output_lineage": returned.get("output_lineage", {}), "provider_call_metadata": returned.get("provider_call_metadata", {}), "started_ts": returned.get("started_ts", now()), "completed_ts": returned.get("completed_ts", now())}
        except Exception as exc:
            record = {"stage": identity["stage"], "transport_status": "exception", "raw_response": None, "raw_response_fingerprint": sha256(None), "parser_result": None, "validator_result": None, "accepted": False, "rejection_reason": str(exc), "output": None, "output_lineage": {}, "provider_call_metadata": {}, "started_ts": now(), "completed_ts": now()}
        self._operation_event(identity, "RESPONSE_RECEIVED", transport_status=record["transport_status"], raw_response_fingerprint=record["raw_response_fingerprint"], provider_request_id=record["provider_call_metadata"].get("provider_request_id"), response_received_at=now())
        persisted = self._persist_result(identity, record)
        self._operation_event(identity, "TERMINAL_ACCEPTED" if record["accepted"] else "TERMINAL_REJECTED", result_persisted_at=now(), final_classification="ACCEPTED" if record["accepted"] else "REJECTED")
        self._transition(identity, received, result=persisted)
        self.lease.heartbeat()
        return persisted

    def _load_source(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        if self._source is None:
            _, _, _, source = replay.recover_population()
            # Outcome values must not be retained on the pre-forecast path.
            source.pop("outcomes", None)
            planned = read_json(self.population_path)["episodes"]
            self._source = source
            self._episodes = {row["episode_id"]: row for row in planned}
        return self._source, self._episodes or {}

    def episode_ids(self) -> list[str]:
        return [row["episode_id"] for row in read_json(self.population_path)["episodes"]]

    def _reserve_forecast_call(self, identity: Mapping[str, Any]) -> None:
        """Reserve a frozen forecast arm once, before its provider call."""
        if self.execution_plan is None:
            return
        state = self.initialize()
        key = operation_key(identity)
        reservations = state.setdefault("forecast_call_reservations", [])
        if key in reservations:
            return
        if len(reservations) >= int(self.execution_plan["maximum_forecast_arms"]):
            state["blocking_error"] = "V2_1_STEP8_R3_R2_CALL_BUDGET_EXHAUSTED"
            atomic(self.state_path, state)
            raise DispatchError("V2_1_STEP8_R3_R2_CALL_BUDGET_EXHAUSTED")
        reservations.append(key)
        atomic(self.state_path, state)

    def _manifest_gate(self, episode: Mapping[str, Any]) -> None:
        contract = self.gate["contract"]
        if contract != binding.contract_module(contract).spec():
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")
        if episode["episode_id"] not in self._load_source()[1]:
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")

    @staticmethod
    def _snapshot(session: Mapping[str, Any]) -> dict[str, Any]:
        return replay._session_snapshot(session)

    def _lineage_dispatcher(self, provider: str) -> Callable[[Mapping[str, Any]], Mapping[str, Any]]:
        if self.dispatcher is None:
            return replay._context_provider_dispatch(provider, single.bridge_dispatch)
        return replay._context_provider_dispatch(provider, self.dispatcher)

    def _attention(self, episode: Mapping[str, Any], provider: str, model: str, source: Mapping[str, Any]) -> dict[str, Any]:
        identity = self._identity(episode, provider, model, "ATTENTION")
        _, result_path = self._paths(identity)
        if result_path.exists():
            return read_json(result_path)
        session = source["sessions"][episode["session_id"]]
        generation_settings = binding.generation_settings(self.gate["contract"], provider, "ATTENTION")
        payload = {"session": self._snapshot(session), "members": source["members"][episode["session_id"]], "cutoff": episode["forecast_cutoff_ts"], "generation_settings": generation_settings}
        self._persist_payload(identity, payload)
        self._transition(identity, "ATTENTION_REQUEST_FROZEN")
        def handler() -> Mapping[str, Any]:
            result = lineage.build_prospective_attention(study_id="HISTORICAL_R3", collection_run_id=self.run.name, session_snapshot=payload["session"], member_rows=payload["members"], provider=provider, model=model, information_cutoff_ts=payload["cutoff"], attention_run_id="R3_ATT_" + operation_key(identity)[7:27], stage_generated_ts=payload["cutoff"], dispatcher=self._lineage_dispatcher(provider), raw_parser=lambda raw: binding.attention_parser(provider, raw, self.gate["contract"]), instruction_override=binding.attention_instruction(self.gate["contract"], provider), generation_settings=generation_settings, raw_response_persistor=lambda response: self._persist_raw_bridge_response(identity, response))
            accepted = result.get("status") == "parsed"
            rank_error = None
            if accepted:
                try:
                    binding.validate_attention_rank(list(result.get("rows") or []), self.gate["contract"])
                except binding.BindingError as exc:
                    accepted = False
                    rank_error = str(exc)
            response = result.get("response", {})
            return {"raw_response": response.get("raw_output_original", response.get("raw_output")), "parser_result": result.get("status"), "validator_result": "VALID" if accepted else rank_error or result.get("status"), "accepted": accepted, "rejection_reason": None if accepted else rank_error or result.get("error") or result.get("status"), "output": result, "provider_call_metadata": response}
        result = self._call(identity, payload, handler, "ATTENTION_SENT", "ATTENTION_RESPONSE_RECEIVED")
        if result["accepted"]:
            self._transition(identity, "ATTENTION_ACCEPTED", result=result)
        else:
            self._transition(identity, "ATTENTION_REJECTED", result=result)
        return result

    def _requests(self, episode: Mapping[str, Any], provider: str, model: str, attention: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
        identity = self._identity(episode, provider, model, "REQUEST")
        _, result_path = self._paths(identity)
        if result_path.exists():
            return read_json(result_path)
        session = source["sessions"][episode["session_id"]]
        payload = {"attention_result_fingerprint": attention["result_fingerprint"], "cutoff": episode["forecast_cutoff_ts"]}
        self._persist_payload(identity, payload); self._transition(identity, "REQUEST_FROZEN")
        def handler() -> Mapping[str, Any]:
            result = lineage.build_prospective_requests(study_id="HISTORICAL_R3", collection_run_id=self.run.name, session_snapshot=self._snapshot(session), member_rows=source["members"][episode["session_id"]], attention_result=attention["output"], provider=provider, model=model, information_cutoff_ts=episode["forecast_cutoff_ts"], request_run_id="R3_REQ_" + operation_key(identity)[7:27], stage_generated_ts=episode["forecast_cutoff_ts"], dispatcher=self._lineage_dispatcher(provider), raw_parser=lambda raw: binding.attention_parser(provider, raw, self.gate["contract"]), instruction_override=binding.request_instruction(self.gate["contract"], provider), request_normalizer=lambda item: binding.normalize_request_item(item, self.gate["contract"]), raw_response_persistor=lambda response: self._persist_raw_bridge_response(identity, response))
            accepted = result.get("status") == "parsed"
            response = result.get("response", {})
            return {"raw_response": response.get("raw_output_original", response.get("raw_output")), "parser_result": result.get("status"), "validator_result": result.get("status"), "accepted": accepted, "rejection_reason": None if accepted else result.get("error") or result.get("status"), "output": result, "provider_call_metadata": response}
        result = self._call(identity, payload, handler, "REQUEST_SENT", "REQUEST_SENT")
        self._transition(identity, "REQUEST_ACCEPTED" if result["accepted"] else "REQUEST_REJECTED", result=result)
        return result

    def _packs(self, episode: Mapping[str, Any], selected: Mapping[str, tuple[str, Mapping[str, Any]]], source: Mapping[str, Any]) -> dict[str, Any]:
        session_id = episode["session_id"]
        identity = {"run_id": self.run.name, "session_id": session_id, "episode_id": episode["episode_id"], "provider": "SHARED", "model": "SHARED", "stage": "PACKS", "information_arm": None, "contract_fingerprint": self.gate["contract"]["contract_fingerprint"], "attempt_number": 1}
        # The frozen replay package permits a Pack item's cutoff timestamp to
        # live in ``forecast_timestamp``.  The explicit-input Pack builder
        # requires the same fact under ``source_timestamp``; retain both
        # fields so this is serialization normalization, not a data change.
        items = []
        for original in replay._normal_pack_items(source["packs"][session_id], episode["forecast_cutoff_ts"]):
            item = dict(original)
            if not item.get("source_timestamp"):
                item["source_timestamp"] = item.get("historical_availability_timestamp") or item.get("forecast_timestamp")
            items.append(item)
        payload = {"cutoff": episode["forecast_cutoff_ts"], "requests": {p: r[2]["output"]["rows"] for p, r in selected.items()}, "shared_items": items}
        self._persist_payload(identity, payload)
        def handler() -> Mapping[str, Any]:
            packs = lineage.build_prospective_packs(study_id="HISTORICAL_R3", collection_run_id=self.run.name, session_id=session_id, information_cutoff_ts=episode["forecast_cutoff_ts"], pack_freeze_id="R3_PACK_" + operation_key(identity)[7:27], requests_by_provider=payload["requests"], shared_pack_items=items, pack_generated_ts=episode["forecast_cutoff_ts"])
            return {"raw_response": packs, "parser_result": "deterministic_builder", "validator_result": packs["status"], "accepted": packs["status"] == "FROZEN", "rejection_reason": None, "output": packs, "output_lineage": {"shared_items": len(items)}}
        result = self._call(identity, payload, handler, "PACKS_FROZEN", "PACKS_FROZEN")
        if not result["accepted"]:
            raise DispatchError(result["rejection_reason"] or "PACKS_FAILED")
        return result

    def _forecast_input(self, episode: Mapping[str, Any], provider: str, model: str, attention: Mapping[str, Any], requests: Mapping[str, Any], source: Mapping[str, Any], packs: Mapping[str, Any], arm: str) -> dict[str, Any]:
        pack_a = packs["pack_a_by_provider"][provider]
        return replay._pair_input(episode, provider, model, attention["output"], requests["output"], source["packs"][episode["session_id"]], pack_a, arm)

    def _freeze_prompts(self, episode: Mapping[str, Any], provider: str, model: str, inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        prompts = {arm: binding.forecast_prompt(row, provider, self.gate["contract"]) for arm, row in inputs.items()}
        contexts = {arm: __import__("automation.presignal_v21_prospective_flat_contract_v1", fromlist=["prospective_context"]).prospective_context(row, "presignal_event_path_contract_v1_flat_stage_prospective_v1") for arm, row in inputs.items()}
        diff = single.prompt_diff(contexts["PACK_A"], contexts["PACK_E"])
        if not diff["passed"]:
            raise DispatchError("PROMPT_SYMMETRY:" + canonical(diff))
        for arm, row in inputs.items():
            identity = self._identity(episode, provider, model, "FORECAST_PROMPT", arm)
            self._persist_payload(identity, {"prompt": prompts[arm], "input": row, "prompt_fingerprint": sha256(prompts[arm])})
            self._transition(identity, "FORECAST_PROMPTS_FROZEN")
        return {"prompts": prompts, "diff": diff}

    def _forecast(self, episode: Mapping[str, Any], provider: str, model: str, arm: str, row: Mapping[str, Any], prompt: str) -> dict[str, Any]:
        identity = self._identity(episode, provider, model, "FORECAST", arm)
        _, existing_result = self._paths(identity)
        if not existing_result.exists():
            self._reserve_forecast_call(identity)
        payload = single.bridge_payload(row, prompt, run_id=self.run.name, arm=arm)
        payload["forecast_identity"] = "STEP8_R3_" + operation_key(identity)[7:27]
        frozen_payload = {"payload": payload, "prompt_fingerprint": sha256(prompt), "pack_fingerprint": row["pack_fingerprint"]}
        def handler() -> Mapping[str, Any]:
            response = dict(self._lineage_dispatcher(provider)(payload))
            accepted = False; prediction = None; paths = None; reason = None
            try:
                if response.get("status") != "ok" or response.get("actual_provider") != provider or response.get("actual_model") != model:
                    raise DispatchError(response.get("error") or response.get("status") or "EXACT_MODEL_IDENTITY")
                parsed = single.parse_provider_output(response.get("raw_output"))
                prediction, paths = single.response_to_contract(parsed, row, run_id=self.run.name, created_ts=str(response.get("completed_timestamp") or now()), raw_output=response.get("raw_output"), bridge_result=response)
                accepted = True
            except Exception as exc:
                reason = str(exc)
            return {"raw_response": response.get("raw_output"), "parser_result": "parsed" if accepted else reason, "validator_result": "accepted" if accepted else reason, "accepted": accepted, "rejection_reason": reason, "output": {"prediction": prediction, "paths": paths}, "provider_call_metadata": response}
        result = self._call(identity, frozen_payload, handler, "PACK_A_SENT" if arm == "PACK_A" else "PACK_E_SENT", "PACK_A_ACCEPTED" if arm == "PACK_A" else "PACK_E_ACCEPTED")
        self._transition(identity, ("PACK_A_ACCEPTED" if arm == "PACK_A" else "PACK_E_ACCEPTED") if result["accepted"] else ("PACK_A_REJECTED" if arm == "PACK_A" else "PACK_E_REJECTED"), result=result)
        return result

    def _outcome_and_evaluate(self, episode: Mapping[str, Any], provider: str, model: str, forecasts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        if not all(arm["accepted"] or arm["rejection_reason"] for arm in forecasts.values()):
            raise DispatchError("OUTCOME_BEFORE_TERMINAL_ARMS")
        identity = self._identity(episode, provider, model, "OUTCOME")
        frozen_payload = {"outcome_identity": episode["outcome_identity"], "forecast_result_fingerprints": {a: r["result_fingerprint"] for a, r in forecasts.items()}}
        def handler() -> Mapping[str, Any]:
            outcomes = {r["episode_id"]: r for r in replay.read_jsonl(replay.OUTCOMES) if r.get("status") == "VALID"}
            outcome = outcomes.get(episode["episode_id"])
            if not outcome or outcome["outcome_id"] != episode["outcome_identity"]:
                raise DispatchError("OUTCOME_IDENTITY_MISMATCH")
            return {"raw_response": outcome, "parser_result": "deterministic_historical_outcome", "validator_result": "VALID", "accepted": True, "rejection_reason": None, "output": outcome}
        outcome_result = self._call(identity, frozen_payload, handler, "OUTCOME_ATTACHED", "OUTCOME_ATTACHED")
        evaluations: dict[str, Any] = {}
        for arm, forecast in forecasts.items():
            if forecast["accepted"]:
                output = forecast["output"]
                evaluations[arm] = single.evaluate(output["prediction"], output["paths"], outcome_result["output"], generated_ts=now())
        evaluation_identity = self._identity(episode, provider, model, "EVALUATE")
        evaluation_payload = {"outcome_fingerprint": outcome_result["result_fingerprint"], "forecast_fingerprints": {a: r["result_fingerprint"] for a, r in forecasts.items()}}
        self._persist_payload(evaluation_identity, evaluation_payload)
        completed = len(evaluations) == 2
        evaluation_result = self._persist_result(evaluation_identity, {"stage": "EVALUATE", "transport_status": "deterministic", "raw_response": evaluations, "raw_response_fingerprint": sha256(evaluations), "parser_result": "existing_evaluator", "validator_result": "VALID", "accepted": completed, "rejection_reason": None if completed else "INCOMPLETE_PAIRED", "output": evaluations, "output_lineage": {"same_outcome_identity": outcome_result["output"]["outcome_id"]}, "provider_call_metadata": {}, "started_ts": now(), "completed_ts": now()})
        self._transition(evaluation_identity, "EVALUATED", result=evaluation_result)
        self._transition(evaluation_identity, "COMPLETE" if completed else "TERMINAL_INCOMPLETE", result=evaluation_result)
        return {"outcome": outcome_result, "evaluations": evaluations, "complete": completed}

    @staticmethod
    def _is_evaluable_pair(result: Mapping[str, Any]) -> bool:
        """A lifecycle-complete pair counts only with a usable 15-minute Outcome."""
        outcome = result.get("outcome", {})
        evaluations = outcome.get("evaluations", {}) if isinstance(outcome, Mapping) else {}
        return bool(
            outcome.get("complete")
            and isinstance(evaluations, Mapping)
            and isinstance(evaluations.get("PACK_A"), Mapping)
            and isinstance(evaluations.get("PACK_E"), Mapping)
            and isinstance(evaluations["PACK_A"].get("direction_15m_ok"), bool)
            and isinstance(evaluations["PACK_E"].get("direction_15m_ok"), bool)
        )

    def process_episode(self, episode_id: str) -> dict[str, Any]:
        self.acquire_ownership()
        source, episodes = self._load_source()
        episode = episodes[episode_id]; self._manifest_gate(episode)
        state = self.initialize()
        if episode_id in state["processed_episode_ids"]:
            return {"episode_id": episode_id, "status": "ALREADY_PROCESSED"}
        selected: dict[str, tuple[str, Mapping[str, Any], Mapping[str, Any]]] = {}
        terminal: dict[str, str] = {}
        for provider, model in self.gate["provider_routes"].items():
            attention = self._attention(episode, provider, model, source)
            if not attention["accepted"]:
                identity = self._identity(episode, provider, model, "ATTENTION")
                self._transition(identity, "TERMINAL_INCOMPLETE", result=attention)
                terminal[provider] = "ATTENTION_REJECTED"; self._record_provider_path(episode_id, provider, "TERMINAL_INCOMPLETE"); continue
            action = replay.selection_action(attention["output"]["rows"])
            if action != "FORECAST":
                identity = self._identity(episode, provider, model, "ATTENTION")
                self._transition(identity, "NOT_FORECAST_SELECTED", result=attention)
                terminal[provider] = action; self._record_provider_path(episode_id, provider, "TERMINAL_INCOMPLETE"); continue
            request = self._requests(episode, provider, model, attention, source)
            if not request["accepted"]:
                identity = self._identity(episode, provider, model, "REQUEST")
                self._transition(identity, "TERMINAL_INCOMPLETE", result=request)
                terminal[provider] = "REQUEST_REJECTED"; self._record_provider_path(episode_id, provider, "TERMINAL_INCOMPLETE"); continue
            selected[provider] = (model, attention, request)
            self._record_provider_path(episode_id, provider, "IN_PROGRESS")
        packs = self._packs(episode, selected, source)["output"] if selected else None
        results: dict[str, Any] = {}
        if packs:
            for provider, (model, attention, request) in selected.items():
                try:
                    inputs = {arm: self._forecast_input(episode, provider, model, attention, request, source, packs, arm) for arm in ("PACK_A", "PACK_E")}
                    frozen = self._freeze_prompts(episode, provider, model, inputs)
                    forecasts = {arm: self._forecast(episode, provider, model, arm, inputs[arm], frozen["prompts"][arm]) for arm in replay.arm_order("R3PAIR_" + episode["episode_id"] + provider)}
                    outcome = self._outcome_and_evaluate(episode, provider, model, forecasts)
                    results[provider] = {"forecasts": forecasts, "outcome": outcome, "prompt_diff": frozen["diff"]}
                    terminal[provider] = "COMPLETE" if outcome["complete"] else "TERMINAL_INCOMPLETE"
                    self._record_provider_path(episode_id, provider, terminal[provider])
                except Exception as exc:
                    terminal[provider] = "TERMINAL_INCOMPLETE"
                    results[provider] = {"error": str(exc)}
                    self._record_provider_path(episode_id, provider, "TERMINAL_INCOMPLETE")
        state = self.initialize(); state["processed_episodes"] += 1; state["processed_episode_ids"].append(episode_id)
        evaluable_pairs = sum(self._is_evaluable_pair(row) for row in results.values())
        state["complete_paired_observations"] += evaluable_pairs
        if evaluable_pairs:
            state["unique_complete_episodes"] += 1
        state["last_durable_checkpoint"] = "EPISODE_TERMINAL"; atomic(self.state_path, state)
        append(self.run / "progress_checkpoints.jsonl", {"episode_id": episode_id, "processed_episodes": state["processed_episodes"], "unique_complete_episodes": state["unique_complete_episodes"], "complete_paired_observations": state["complete_paired_observations"], "terminal": terminal, "timestamp": now()})
        if self.execution_plan and state["unique_complete_episodes"] >= int(self.execution_plan["checkpoint_complete_episodes"]):
            checkpoint = self.run / "checkpoint_40_recorded.json"
            if not checkpoint.exists():
                atomic(checkpoint, {"checkpoint_complete_episodes": self.execution_plan["checkpoint_complete_episodes"], "processed_episodes": state["processed_episodes"], "unique_complete_episodes": state["unique_complete_episodes"], "timestamp": now()})
        return {"episode_id": episode_id, "terminal": terminal, "results": results}

    def first_episode(self) -> str:
        return self.episode_ids()[0]

    def process_cohort(self) -> dict[str, Any]:
        self.acquire_ownership()
        if self.execution_plan is None:
            raise DispatchError("V2_1_STEP8_R3_R2_RUNTIME_MANIFEST_MISMATCH")
        for episode_id in self.episode_ids():
            state = self.initialize()
            if state["unique_complete_episodes"] >= int(self.execution_plan["target_complete_episodes"]):
                return {"status": "TARGET_COMPLETE", **state}
            if state["processed_episodes"] >= int(self.execution_plan["maximum_processed_episodes"]):
                return {"status": "CEILING_REACHED", **state}
            if episode_id in state["processed_episode_ids"]:
                continue
            self.process_episode(episode_id)
        state = self.initialize()
        status = "TARGET_COMPLETE" if state["unique_complete_episodes"] >= int(self.execution_plan["target_complete_episodes"]) else "POPULATION_EXHAUSTED"
        return {"status": status, **state}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run-id", default="STEP8-R3-R9-SMOKE-3f72650")
    parser.add_argument("--verification-manifest", type=Path, default=R9_MANIFEST)
    parser.add_argument("--execution-plan", type=Path)
    parser.add_argument("--execute-cohort", action="store_true")
    parser.add_argument("--resume-cohort", action="store_true")
    args = parser.parse_args()
    loop = ExecutionLoop(args.run_id, manifest_path=args.verification_manifest, execution_plan_path=args.execution_plan)
    if args.status:
        print(json.dumps(loop.status(), sort_keys=True)); return
    if args.preflight:
        print(json.dumps(binding.gate(args.verification_manifest), sort_keys=True)); return
    try:
        if args.execute_cohort or args.resume_cohort:
            print(json.dumps(loop.process_cohort(), sort_keys=True)); return
        if args.execute or args.resume:
            print(json.dumps(loop.process_episode(loop.first_episode()), sort_keys=True)); return
        raise SystemExit("PRELIGHT_REQUIRED")
    finally:
        loop.release_ownership("COMMAND_EXIT")


if __name__ == "__main__":
    main()
