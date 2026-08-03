#!/usr/bin/env python3
"""Evaluate only the attached Slice 001; never accesses external systems."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
ATTACHMENT_RUN = os.environ.get("PRESIGNAL_OUTCOME_ATTACHMENT_RUN", "PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320")
SLICE_ID = os.environ.get("PRESIGNAL_OUTCOME_SLICE_ID", "SLICE-001")
SLICE_LABEL = SLICE_ID.replace("-", "_")
ATTACHMENT_DIR = BASE / ATTACHMENT_RUN
EXPECTED_MANIFEST_SHA = os.environ.get("PRESIGNAL_OUTCOME_EXPECTED_MANIFEST_SHA", "sha256:90765146ec192c58fe841b61b49d239fae321a99b2a73d3f8529ceeaad9f41c8")
EVALUATION_AUTH_PATH = os.environ.get("PRESIGNAL_EVALUATION_AUTH_PATH", "")
AUTHORIZATION_ID = os.environ.get("PRESIGNAL_OUTCOME_AUTHORIZATION_ID", "")
AUTHORIZATION_FINGERPRINT = os.environ.get("PRESIGNAL_OUTCOME_AUTHORIZATION_FINGERPRINT", "")
INVALID_CALLS = {
    "FCL_27720b8b23236b173b96fdee",
    "FCL_7f0463b134c67757968580e8",
    "FCL_e07264654e9d3da6f63088a1",
}
HORIZONS = (5, 15, 30, 60)


def manifest_population() -> dict[str, int]:
    if EVALUATION_AUTH_PATH:
        authorization = read_json(Path(EVALUATION_AUTH_PATH))
        if authorization.get("evaluation_authorized") is not True or authorization.get("manifest_fingerprint") != EXPECTED_MANIFEST_SHA:
            raise ValueError("EVALUATION_AUTHORIZATION_BINDING_CONFLICT")
        population = authorization.get("evaluation_population", {})
        return {
            "episodes": population.get("episodes", len(authorization.get("authorized_identity_ids", []))),
            "valid_forecasts": population["valid_forecasts"],
            "pairs": population.get("complete_pairs", population.get("complete_pack_a_e_pairs")),
        }
    manifest_path = Path(os.environ.get("PRESIGNAL_OUTCOME_MANIFEST_PATH", ""))
    if not manifest_path.exists():
        return {"episodes": 12, "valid_forecasts": 44, "pairs": 12}
    manifest = read_json(manifest_path)
    population = manifest.get("authorized_forecast_population", {})
    return {"episodes": len(manifest.get("episode_manifest", [])), "valid_forecasts": population.get("valid_forecasts", 44), "pairs": population.get("complete_pack_a_e_pairs", 12)}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def paired_difference(left: Any, right: Any) -> Any:
    """Keep a paired metric undefined when either forecast is ineligible."""
    if left is None or right is None:
        return None
    return left - right


def forecast_rows(episode_ids: set[str]) -> list[dict[str, Any]]:
    by_call: dict[str, dict[str, Any]] = {}
    source_by_call: dict[str, str] = {}
    for path in sorted(BASE.glob("PPHB-R1-FORECAST-*/normalized_forecast_results.jsonl")):
        for row in read_jsonl(path):
            call_id = row.get("forecast_call_id")
            if not call_id or row.get("episode_id") not in episode_ids or call_id in INVALID_CALLS:
                continue
            prior = by_call.get(call_id)
            if prior is not None and canonical(prior) != canonical(row):
                if EVALUATION_AUTH_PATH:
                    # Accepted E004 reconciliation selects the earliest invocation.
                    if path.parent.name < source_by_call[call_id]:
                        by_call[call_id] = row
                        source_by_call[call_id] = path.parent.name
                    continue
                raise ValueError("FORECAST_IDENTITY_DUPLICATE_CONFLICT:" + call_id)
            by_call[call_id] = row
            source_by_call.setdefault(call_id, path.parent.name)
    if EVALUATION_AUTH_PATH:
        recovery_path = BASE / "PPHB-R1-FORECAST-FINAL-RESULT-DIAGNOSIS-BATCH-003-20260729T234944Z-a65de810bf75" / "recovered_result_ledger.jsonl"
        if recovery_path.exists():
            metadata: dict[str, dict[str, Any]] = {}
            for manifest_path in BASE.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/batch_call_manifest.jsonl"):
                for manifest_row in read_jsonl(manifest_path):
                    metadata.setdefault(manifest_row.get("forecast_call_id"), manifest_row)
            for recovered in read_jsonl(recovery_path):
                call_id = recovered.get("forecast_call_id")
                prediction = recovered.get("prediction", {})
                if not call_id or prediction.get("episode_id") not in episode_ids or recovered.get("validation_status") != "VALID":
                    continue
                if call_id in by_call:
                    continue
                manifest_row = metadata.get(call_id, {})
                by_call[call_id] = {
                    "episode_id": prediction["episode_id"],
                    "forecast_call_id": call_id,
                    "model": recovered.get("model", manifest_row.get("model")),
                    "pack_type": manifest_row.get("pack_type"),
                    "provider": recovered.get("provider", manifest_row.get("provider")),
                    "prediction": prediction,
                    "paths": recovered.get("paths", []),
                    "terminal_state": "SUCCEEDED_VALID",
                }
                source_by_call[call_id] = recovery_path.parent.name
        # A preserved provider response may be normalized mechanically when
        # the original terminal result was caused only by a parser boundary.
        # This path never dispatches a provider and requires identity metadata
        # from an already accepted forecast for the same Episode.
        metadata: dict[str, dict[str, Any]] = {}
        transport: dict[str, dict[str, Any]] = {}
        raw_candidates: dict[str, dict[str, Any]] = {}
        for manifest_path in BASE.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/batch_call_manifest.jsonl"):
            for manifest_row in read_jsonl(manifest_path):
                call_id = manifest_row.get("forecast_call_id")
                if call_id:
                    metadata.setdefault(call_id, manifest_row)
        for transport_path in BASE.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/raw_transport_results.jsonl"):
            for transport_row in read_jsonl(transport_path):
                call_id = transport_row.get("forecast_call_id")
                if call_id:
                    transport.setdefault(call_id, transport_row)
        for raw_path in BASE.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/raw_provider_outputs.jsonl"):
            for raw_row in read_jsonl(raw_path):
                call_id = raw_row.get("forecast_call_id")
                if call_id:
                    raw_candidates.setdefault(call_id, raw_row)

        episode_identity: dict[str, tuple[str, list[str]]] = {}
        for accepted in by_call.values():
            prediction = accepted.get("prediction", {})
            episode_id = accepted.get("episode_id") or prediction.get("episode_id")
            if episode_id not in episode_ids:
                continue
            identity = (prediction.get("primary_event_id"), prediction.get("secondary_event_ids", []))
            prior_identity = episode_identity.get(episode_id)
            if prior_identity is not None and prior_identity != identity:
                raise ValueError("EPISODE_EVENT_IDENTITY_CONFLICT:" + episode_id)
            episode_identity[episode_id] = identity

        for call_id, raw_row in sorted(raw_candidates.items()):
            if call_id in by_call or call_id in INVALID_CALLS:
                continue
            manifest_row = metadata.get(call_id)
            transport_row = transport.get(call_id)
            episode_id = raw_row.get("episode_id")
            if not manifest_row or not transport_row or episode_id not in episode_ids:
                continue
            if manifest_row.get("authorization_state") != "AUTHORIZED":
                continue
            if transport_row.get("transport_ok") is not True or transport_row.get("provider_error"):
                continue
            identity = episode_identity.get(episode_id)
            if identity is None or not identity[0]:
                raise ValueError("RECOVERY_EPISODE_IDENTITY_UNRESOLVED:" + episode_id)
            try:
                normalized, audit = step6.normalize_provider_output(raw_row["raw_provider_output"])
                input_row = {
                    "information_arm": manifest_row["pack_type"],
                    "pack_id": "BASELINE_NO_PACK",
                    "pack_fingerprint": None,
                    "episode_id": episode_id,
                    "episode_members": [
                        {"event_id": identity[0], "structural_component_role": "STRUCTURAL_PRIMARY"},
                        *[
                            {"event_id": event_id, "structural_component_role": "STRUCTURAL_SECONDARY"}
                            for event_id in identity[1]
                        ],
                    ],
                    "provider": manifest_row["provider"],
                    "model": manifest_row["model"],
                    "source_session_id": manifest_row["source_session_id"],
                    "forecast_cutoff_ts": manifest_row["historical_cutoff"],
                }
                prediction, paths = step6.response_to_contract(
                    normalized,
                    input_row,
                    run_id="PPHB-R1-MECHANICAL-RAW-RECOVERY-SLICE-003",
                    created_ts=transport_row["completion_timestamp"],
                    raw_output=raw_row["raw_provider_output"],
                    bridge_result={
                        "prompt_tokens": transport_row.get("prompt_tokens"),
                        "completion_tokens": transport_row.get("completion_tokens"),
                    },
                )
            except (KeyError, TypeError, ValueError, step6.Step6Error) as exc:
                raise ValueError("PRESERVED_RAW_RECOVERY_FAILED:" + call_id) from exc
            by_call[call_id] = {
                "episode_id": episode_id,
                "forecast_call_id": call_id,
                "model": manifest_row["model"],
                "pack_type": manifest_row["pack_type"],
                "provider": manifest_row["provider"],
                "prediction": prediction,
                "paths": paths,
                "terminal_state": "SUCCEEDED_VALID",
                "recovery_source": "PRESERVED_RAW_PROVIDER_OUTPUT",
                "recovery_audit": audit,
            }
            source_by_call[call_id] = "PRESERVED_RAW_PROVIDER_OUTPUT"
    rows = sorted(by_call.values(), key=lambda row: row["forecast_call_id"])
    expected = manifest_population()
    if len(rows) != expected["valid_forecasts"] or len({row["forecast_call_id"] for row in rows}) != expected["valid_forecasts"]:
        raise ValueError("SLICE_FORECAST_POPULATION_MISMATCH")
    for row in rows:
        if row.get("terminal_state") != "SUCCEEDED_VALID":
            raise ValueError("NON_AUTHORITATIVE_FORECAST_INCLUDED:" + row["forecast_call_id"])
        contract.validate_prediction_path_transaction(row["prediction"], row["paths"])
    return rows


def validate_population() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    decision = read_json(ATTACHMENT_DIR / "attachment_decision.json")
    if decision.get("decision") != "OUTCOME_" + SLICE_LABEL + "_ATTACHED_AND_RECONCILED":
        raise ValueError("ATTACHMENT_DECISION_NOT_ACCEPTED")
    reconciliation = read_json(ATTACHMENT_DIR / "attachment_reconciliation.json")
    expected = manifest_population()
    if reconciliation.get("attached_outcome_count") != expected["episodes"] or reconciliation.get("unattached_candidate_count") != 0:
        raise ValueError("ATTACHMENT_COUNT_CONFLICT")
    links = read_jsonl(ATTACHMENT_DIR / "candidate_to_attachment.jsonl")
    attached = read_jsonl(ATTACHMENT_DIR / "attached_outcomes.jsonl")
    if len(links) != expected["episodes"] or len(attached) != expected["episodes"] or any(row["manifest_sha256"] != EXPECTED_MANIFEST_SHA for row in links):
        raise ValueError("ATTACHMENT_SCOPE_OR_MANIFEST_CONFLICT")
    outcomes: dict[str, dict[str, Any]] = {}
    for row in attached:
        outcome = row["candidate_outcome"]
        contract.validate_outcome(outcome)
        if row["candidate_outcome_fingerprint"] != row["candidate_outcome"]["outcome_fingerprint"]:
            raise ValueError("ATTACHED_OUTCOME_HASH_CONFLICT")
        if outcome["episode_id"] in outcomes:
            raise ValueError("DUPLICATE_ATTACHED_EPISODE")
        outcomes[outcome["episode_id"]] = outcome
    if set(outcomes) != {row["episode_id"] for row in links}:
        raise ValueError("ATTACHED_EPISODE_LINK_CONFLICT")
    forecasts = forecast_rows(set(outcomes))
    episode_pair_keys = {(row["episode_id"], row["prediction"]["forecast_cutoff_ts"]) for row in forecasts}
    if len(episode_pair_keys) != expected["episodes"]:
        raise ValueError("EPISODE_PAIR_SCOPE_CONFLICT")
    return forecasts, outcomes, {
        "attachment_run_id": ATTACHMENT_RUN,
        "attachment_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "attachment_file_hashes": {
            name: file_digest(ATTACHMENT_DIR / name)
            for name in ("candidate_to_attachment.jsonl", "attached_outcomes.jsonl", "attachment_reconciliation.json")
        },
    }


def metric(value: str, numerator: int | None, denominator: int, excluded: int, reason: str, result: Any, **extra: Any) -> dict[str, Any]:
    return {
        "name": value,
        "eligible_forecast_count": denominator + excluded,
        "evaluated_count": denominator,
        "excluded_count": excluded,
        "exclusion_reason": reason,
        "denominator": denominator,
        "numerator": numerator,
        "result": result,
        **extra,
    }


def summarize(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    eligible = [row for row in rows if not row["no_signal"]]
    t15 = [row["t15_correct"] for row in eligible]
    horizon = {
        str(h): metric(
            f"T+{h} horizon accuracy", sum(row[f"h{h}_correct"] for row in eligible), len(eligible),
            len(rows) - len(eligible), "NO_SIGNAL_FORECAST", sum(row[f"h{h}_correct"] for row in eligible) / len(eligible),
            treatment_flat="FLAT is an exact direction label; correct only when realized direction is FLAT.",
            treatment_no_signal="Excluded from directional denominator; no_signal is handled separately by contract.",
        ) for h in HORIZONS
    }
    impulse_supported = [row for row in eligible if row["immediate_supported"]]
    impulse_correct = sum(row["immediate_correct"] for row in impulse_supported)
    magnitudes = [row["magnitude_interval_error_pips"] for row in eligible]
    midpoints = [row["magnitude_midpoint_error_pips"] for row in eligible]
    path_scores = [row["path_score"] for row in eligible]
    reversals = [row["reversal_correct"] for row in eligible]
    return {
        "pack": name,
        "forecast_count": len(rows),
        "no_signal_count": sum(row["no_signal"] for row in rows),
        "metrics": {
            "T+15 directional accuracy": metric(
                "T+15 directional accuracy", sum(t15), len(t15), len(rows) - len(t15), "NO_SIGNAL_FORECAST",
                sum(t15) / len(t15), endpoint="T+15", treatment_flat="Exact FLAT label match.",
                treatment_no_signal="Excluded from denominator; no-signal handling remains separate.",
            ),
            "Immediate Impulse directional accuracy": metric(
                "Immediate Impulse directional accuracy", impulse_correct, len(impulse_supported),
                len(rows) - len(impulse_supported), "APPROXIMATION_ONLY_OUTCOME_NOT_STRICTLY_SCORED",
                None if not impulse_supported else impulse_correct / len(impulse_supported),
                status="NOT_APPLICABLE_STRICT", treatment="Only SUPPORTED outcomes are eligible; this slice uses APPROXIMATION_ONLY.",
            ),
            "magnitude or pip error": metric(
                "magnitude or pip error", None, len(magnitudes), len(rows) - len(magnitudes), "NO_SIGNAL_FORECAST",
                mean(magnitudes), unit="pips", field="T+15 interval distance error", rounding="2 decimal pips in source; aggregate shown to 6 decimals.",
                midpoint_absolute_error_mean_pips=mean(midpoints),
            ),
            "path accuracy": metric(
                "path accuracy", None, len(path_scores), len(rows) - len(path_scores), "NO_SIGNAL_FORECAST",
                mean(path_scores), definition="Mean of T+5/T+15/T+30/T+60 direction correctness per complete validated path.",
            ),
            "reversal accuracy": metric(
                "reversal accuracy", sum(reversals), len(reversals), len(rows) - len(reversals), "NO_SIGNAL_FORECAST",
                sum(reversals) / len(reversals), treatment="Exact expected_reversal_flag versus Outcome reversal_flag.",
            ),
            "horizon accuracy": horizon,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_dir = BASE / args.run_id
    if run_dir.exists():
        raise SystemExit("EVALUATION_RUN_ALREADY_EXISTS")
    forecasts, outcomes, population = validate_population()
    rows: list[dict[str, Any]] = []
    for forecast in forecasts:
        prediction, paths = forecast["prediction"], forecast["paths"]
        outcome = outcomes[forecast["episode_id"]]
        by_h = {path["horizon_min"]: path for path in paths}
        no_signal = bool(prediction["no_signal_flag"])
        h_correct = {h: (None if no_signal else by_h[h]["expected_direction"] == outcome[f"direction_{h}m"]) for h in HORIZONS}
        supported = outcome["immediate_impulse_outcome_state"] == "SUPPORTED" and not no_signal
        interval_error = None if no_signal else contract._interval_error(abs(outcome["pips_15m"]), by_h[15]["expected_pips_min"], by_h[15]["expected_pips_max"])
        midpoint_error = None if no_signal else contract._midpoint_absolute_error(abs(outcome["pips_15m"]), by_h[15]["expected_pips_min"], by_h[15]["expected_pips_max"])
        rows.append({
            "forecast_call_id": forecast["forecast_call_id"], "episode_id": forecast["episode_id"], "pack": forecast["pack_type"],
            "provider": forecast["provider"], "model": forecast["model"], "prediction_id": prediction["prediction_id"],
            "outcome_id": outcome["outcome_id"], "outcome_fingerprint": outcome["outcome_fingerprint"], "no_signal": no_signal,
            "immediate_outcome_state": outcome["immediate_impulse_outcome_state"], "immediate_supported": supported,
            "immediate_correct": (prediction["immediate_impulse_direction"] == outcome["confirmed_initial_direction"] if supported else None),
            "t15_correct": h_correct[15], "h5_correct": h_correct[5], "h15_correct": h_correct[15], "h30_correct": h_correct[30], "h60_correct": h_correct[60],
            "magnitude_interval_error_pips": interval_error, "magnitude_midpoint_error_pips": midpoint_error,
            "path_score": (sum(h_correct.values()) / len(HORIZONS) if not no_signal else None),
            "reversal_correct": (prediction["expected_reversal_flag"] == outcome["reversal_flag"] if not no_signal else None),
        })
    by_pack = {pack: [row for row in rows if row["pack"] == pack] for pack in ("PACK_A", "PACK_E")}
    pairs: defaultdict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        forecast = next(item for item in forecasts if item["forecast_call_id"] == row["forecast_call_id"])
        # Provider/model are part of the deterministic paired-comparison identity.
        pairs[(row["episode_id"], forecast["prediction"]["forecast_cutoff_ts"], row["provider"], row["model"])][row["pack"]] = row
    if any(set(value) != {"PACK_A", "PACK_E"} for value in pairs.values()):
        raise SystemExit("PROVIDER_MODEL_PAIR_PARTITION_CONFLICT")
    pair_rows = []
    for key, arms in sorted(pairs.items()):
        a, e = arms["PACK_A"], arms["PACK_E"]
        pair_rows.append({
            "episode_id": key[0], "forecast_cutoff_ts": key[1], "provider": key[2], "model": key[3],
            "t15_accuracy_difference_a_minus_e": paired_difference(a["t15_correct"], e["t15_correct"]),
            "path_score_difference_a_minus_e": paired_difference(a["path_score"], e["path_score"]),
            "magnitude_interval_error_difference_a_minus_e": paired_difference(a["magnitude_interval_error_pips"], e["magnitude_interval_error_pips"]),
            "reversal_accuracy_difference_a_minus_e": paired_difference(a["reversal_correct"], e["reversal_correct"]),
        })
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_dir.mkdir(parents=True)
    write_json(run_dir / "run_manifest.json", {
        "run_id": args.run_id, "move_type": "MINIMAL_EVALUATION_ATTACHED_OUTCOME_" + SLICE_LABEL,
        "attachment_run_id": ATTACHMENT_RUN, "manifest_sha256": EXPECTED_MANIFEST_SHA,
        "episode_count": manifest_population()["episodes"], "forecast_count": len(forecasts), "episode_pair_groups": len({row["episode_id"] for row in forecasts}), "provider_model_pair_rows": len(pair_rows),
        "external_requests": 0, "google_reads": 0, "google_writes": 0, "market_data_calls": 0, "provider_calls": 0,
        "outcome_recollection": 0, "additional_attachment": 0, "generated_ts": generated,
        "authorization_id": AUTHORIZATION_ID or None, "authorization_fingerprint": AUTHORIZATION_FINGERPRINT or None,
    })
    write_json(run_dir / "population_and_denominator_proof.json", {
        "forecast_population_hash": digest(rows), "outcome_population_hash": digest(list(outcomes.values())),
        "forecast_count": len(forecasts), "outcome_count": len(outcomes), "complete_episode_pair_groups": len({row["episode_id"] for row in forecasts}), "provider_model_pair_rows": len(pair_rows),
        "terminal_invalid_excluded": sorted(INVALID_CALLS), "unexecuted_included": 0, "outside_slice_included": 0,
        "pack_counts": {pack: len(values) for pack, values in by_pack.items()}, "missing_outcomes": [], "duplicate_evaluation_rows": 0,
    })
    write_jsonl(run_dir / "per_forecast_evaluation_rows.jsonl", rows)
    write_json(run_dir / "pack_metrics.json", {"PACK_A": summarize(by_pack["PACK_A"], "PACK_A"), "PACK_E": summarize(by_pack["PACK_E"], "PACK_E")})
    write_json(run_dir / "paired_descriptive_comparison.json", {
        "episode_pair_groups": len({row["episode_id"] for row in forecasts}), "provider_model_pair_rows": len(pair_rows), "rows": pair_rows,
        "interpretation": "Descriptive A-minus-E differences only; no significance, weighting, winner selection, or generalization.",
    })
    write_json(run_dir / "evaluation_decision.json", {
        "decision": "OUTCOME_" + SLICE_LABEL + "_MINIMAL_EVALUATION_COMPLETE", "reproducibility": "" + SLICE_LABEL + "_EVALUATION_REPRODUCIBLE",
        "metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"],
        "composite_score": "NOT_CALCULATED_NOT_AUTHORIZED", "external_requests": 0, "google_operations": 0,
        "limitations": [f"{manifest_population()['episodes']} Episodes and {len(forecasts)} forecasts only", "Immediate Impulse is APPROXIMATION_ONLY and not strict-scored", "descriptive slice; no statistical inference"],
    })
    write_json(run_dir / "reproducibility_and_boundaries.json", {
        "contract": "presignal_event_path_contract_v1_1", "schema_version": "2.1.1", "primary_endpoint": "T+15",
        "secondary_measurement": "Immediate Impulse", "attachment_hashes": population["attachment_file_hashes"],
        "forecast_population_hash": digest(rows), "outcome_population_hash": digest(list(outcomes.values())),
        "no_external_access": True, "no_outcome_modification": True, "no_evaluation_outside_slice": True,
    })
    print(json.dumps({"run_id": args.run_id, "forecast_count": len(forecasts), "pair_rows": len(pair_rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
