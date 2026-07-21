"""Durable, manifest-bound R3 historical-verification dispatcher.

The dispatcher deliberately owns only persistence and stage ordering.  It
reuses the R2 frozen-replay population/Outcome helpers, the explicit-input
lineage builders, the R3 runtime binding, and the existing single-pair
provider bridge and evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r3_contract_v1 as compat_contract
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_single_event_path_pair_v1 as single
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

OUT = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification"
PREP = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e"
POPULATION = PREP / "fresh_verification_population_plan.json"
R7_MANIFEST = ROOT / "outputs/presignal_v21_step8_r3_r7_final_contract_repair/STEP8-R3-R7-c671e5f/verification_manifest.json"

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


class ExecutionLoop:
    """Persisted stage dispatcher with an injectable bridge for call-free tests."""

    def __init__(self, run_id: str, dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None, manifest_path: Path = R7_MANIFEST):
        self.gate = binding.gate(manifest_path)
        if self.gate["contract"]["contract_version"] != compat_contract.CONTRACT_VERSION:
            raise DispatchError("V2_1_STEP8_R7_PREVIOUS_CONTRACT_REJECTED")
        self.run = OUT / run_id
        self.state_path = self.run / "execution_state.json"
        self.dispatcher = dispatcher
        self._source: dict[str, Any] | None = None
        self._episodes: dict[str, dict[str, Any]] | None = None

    def initialize(self) -> dict[str, Any]:
        if self.state_path.exists():
            return read_json(self.state_path)
        state = {
            "run_id": self.run.name,
            "gate": self.gate,
            "processed_episodes": 0,
            "unique_complete_episodes": 0,
            "current": {},
            "terminal_identities": [],
            "processed_episode_ids": [],
            "last_durable_checkpoint": "INITIALIZED",
            "blocking_error": None,
        }
        atomic(self.state_path, state)
        atomic(self.run / "run_manifest.json", self.gate)
        return state

    def status(self) -> dict[str, Any]:
        return self.initialize()

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
        self._persist_payload(identity, payload)
        _, result_path = self._paths(identity)
        if result_path.exists():
            return read_json(result_path)
        self._transition(identity, sent)
        try:
            returned = dict(handler())
            record = {"stage": identity["stage"], "transport_status": returned.get("transport_status", "ok"), "raw_response": returned.get("raw_response"), "raw_response_fingerprint": sha256(returned.get("raw_response")), "parser_result": returned.get("parser_result"), "validator_result": returned.get("validator_result"), "accepted": bool(returned.get("accepted")), "rejection_reason": returned.get("rejection_reason"), "output": returned.get("output"), "output_lineage": returned.get("output_lineage", {}), "provider_call_metadata": returned.get("provider_call_metadata", {}), "started_ts": returned.get("started_ts", now()), "completed_ts": returned.get("completed_ts", now())}
        except Exception as exc:
            record = {"stage": identity["stage"], "transport_status": "exception", "raw_response": None, "raw_response_fingerprint": sha256(None), "parser_result": None, "validator_result": None, "accepted": False, "rejection_reason": str(exc), "output": None, "output_lineage": {}, "provider_call_metadata": {}, "started_ts": now(), "completed_ts": now()}
        persisted = self._persist_result(identity, record)
        self._transition(identity, received, result=persisted)
        return persisted

    def _load_source(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        if self._source is None:
            _, _, _, source = replay.recover_population()
            # Outcome values must not be retained on the pre-forecast path.
            source.pop("outcomes", None)
            planned = read_json(POPULATION)["episodes"]
            self._source = source
            self._episodes = {row["episode_id"]: row for row in planned}
        return self._source, self._episodes or {}

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
        session = source["sessions"][episode["session_id"]]
        generation_settings = binding.generation_settings(self.gate["contract"], provider, "ATTENTION")
        payload = {"session": self._snapshot(session), "members": source["members"][episode["session_id"]], "cutoff": episode["forecast_cutoff_ts"], "generation_settings": generation_settings}
        self._persist_payload(identity, payload)
        self._transition(identity, "ATTENTION_REQUEST_FROZEN")
        def handler() -> Mapping[str, Any]:
            result = lineage.build_prospective_attention(study_id="HISTORICAL_R3", collection_run_id=self.run.name, session_snapshot=payload["session"], member_rows=payload["members"], provider=provider, model=model, information_cutoff_ts=payload["cutoff"], attention_run_id="R3_ATT_" + operation_key(identity)[7:27], stage_generated_ts=payload["cutoff"], dispatcher=self._lineage_dispatcher(provider), raw_parser=lambda raw: binding.attention_parser(provider, raw, self.gate["contract"]), instruction_override=binding.attention_instruction(self.gate["contract"], provider), generation_settings=generation_settings, raw_response_persistor=lambda response: self._persist_raw_bridge_response(identity, response))
            accepted = result.get("status") == "parsed"
            response = result.get("response", {})
            return {"raw_response": response.get("raw_output_original", response.get("raw_output")), "parser_result": result.get("status"), "validator_result": result.get("status"), "accepted": accepted, "rejection_reason": None if accepted else result.get("error") or result.get("status"), "output": result, "provider_call_metadata": response}
        result = self._call(identity, payload, handler, "ATTENTION_SENT", "ATTENTION_RESPONSE_RECEIVED")
        if result["accepted"]:
            self._transition(identity, "ATTENTION_ACCEPTED", result=result)
        else:
            self._transition(identity, "ATTENTION_REJECTED", result=result)
        return result

    def _requests(self, episode: Mapping[str, Any], provider: str, model: str, attention: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
        identity = self._identity(episode, provider, model, "REQUEST")
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

    def process_episode(self, episode_id: str) -> dict[str, Any]:
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
                self._transition(identity, "TERMINAL_INCOMPLETE", result=attention); terminal[provider] = "ATTENTION_REJECTED"; continue
            action = replay.selection_action(attention["output"]["rows"])
            if action != "FORECAST":
                identity = self._identity(episode, provider, model, "ATTENTION")
                self._transition(identity, "NOT_FORECAST_SELECTED", result=attention); terminal[provider] = action; continue
            request = self._requests(episode, provider, model, attention, source)
            if not request["accepted"]:
                identity = self._identity(episode, provider, model, "REQUEST")
                self._transition(identity, "TERMINAL_INCOMPLETE", result=request); terminal[provider] = "REQUEST_REJECTED"; continue
            selected[provider] = (model, attention, request)
        packs = self._packs(episode, selected, source)["output"] if selected else None
        results: dict[str, Any] = {}
        if packs:
            for provider, (model, attention, request) in selected.items():
                inputs = {arm: self._forecast_input(episode, provider, model, attention, request, source, packs, arm) for arm in ("PACK_A", "PACK_E")}
                frozen = self._freeze_prompts(episode, provider, model, inputs)
                forecasts = {arm: self._forecast(episode, provider, model, arm, inputs[arm], frozen["prompts"][arm]) for arm in replay.arm_order("R3PAIR_" + episode["episode_id"] + provider)}
                outcome = self._outcome_and_evaluate(episode, provider, model, forecasts)
                results[provider] = {"forecasts": forecasts, "outcome": outcome, "prompt_diff": frozen["diff"]}
                terminal[provider] = "COMPLETE" if outcome["complete"] else "TERMINAL_INCOMPLETE"
        state = self.initialize(); state["processed_episodes"] += 1; state["processed_episode_ids"].append(episode_id)
        if any(row["outcome"]["complete"] for row in results.values()): state["unique_complete_episodes"] += 1
        state["last_durable_checkpoint"] = "EPISODE_TERMINAL"; atomic(self.state_path, state)
        append(self.run / "progress_checkpoints.jsonl", {"episode_id": episode_id, "processed_episodes": state["processed_episodes"], "unique_complete_episodes": state["unique_complete_episodes"], "terminal": terminal, "timestamp": now()})
        return {"episode_id": episode_id, "terminal": terminal, "results": results}

    def first_episode(self) -> str:
        return read_json(POPULATION)["episodes"][0]["episode_id"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run-id", default="STEP8-R3-R7-SMOKE-c671e5f")
    parser.add_argument("--verification-manifest", type=Path, default=R7_MANIFEST)
    args = parser.parse_args()
    loop = ExecutionLoop(args.run_id, manifest_path=args.verification_manifest)
    if args.status:
        print(json.dumps(loop.status(), sort_keys=True)); return
    if args.preflight:
        print(json.dumps(binding.gate(args.verification_manifest), sort_keys=True)); return
    if args.execute or args.resume:
        print(json.dumps(loop.process_episode(loop.first_episode()), sort_keys=True)); return
    raise SystemExit("PRELIGHT_REQUIRED")


if __name__ == "__main__":
    main()
