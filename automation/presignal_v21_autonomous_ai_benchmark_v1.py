#!/usr/bin/env python3
"""Isolated setup and source-control adapter for the v2.1 autonomous-AI pilot.

This module is intentionally read-only over Step 8-R3-FINAL-R1.  It writes only
the benchmark workbook it creates and its matching artifact directory.  Provider
calls are opt-in; normal setup freezes the cohort without making a model call.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import time
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_RUN = ROOT / "outputs/presignal_v21_step8_r3_final_historical_verification_r1/STEP8-R3-FINAL-R1-e8bf771"
ARTIFACT_ROOT = ROOT / "outputs/presignal_v21_autonomous_ai_benchmark"
CONTRACT = "presignal_event_path_contract_v1_historical_verification_r3_compat_r5"
CONTRACT_FINGERPRINT = "sha256:b342ce7c93e1ef5dc9a168a24ce31305b82bd1cd7fba690250193a73dcb8991d"
SAMPLE_SEED = 20260807
SAMPLE_SIZE = 10
DISCOVERY_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

SHEETS: dict[str, list[str]] = {
    "Experiment_Config": ["config_key", "config_value"],
    "Episode_Sample": ["sample_order", "episode_id", "release_timestamp", "forecast_cutoff", "event_or_cluster_members", "event_family", "importance", "provider", "model", "existing_presignal_forecast_reference", "existing_pack_e_reference", "outcome_reference", "memory_risk_category", "selection_status"],
    "Autonomous_Research_Log": ["episode_id", "research_run_id", "query_order", "search_query", "source_title", "source_url", "source_publisher", "source_publication_timestamp", "retrieval_timestamp", "forecast_cutoff", "source_cutoff_status", "extracted_evidence", "evidence_category", "source_accepted", "rejection_reason", "token_usage", "latency_ms", "error_status"],
    "Autonomous_Forecasts": ["episode_id", "provider", "model", "forecast_timestamp", "forecast_cutoff", "direction_5m", "direction_15m", "direction_30m", "direction_60m", "magnitude_5m", "magnitude_15m", "magnitude_30m", "magnitude_60m", "continuation_probability", "reversal_probability", "likely_reversal_horizon", "confidence", "primary_catalyst", "causal_interpretation", "information_used", "missing_information", "invalidation_conditions", "no_signal_status", "raw_output", "validation_status"],
    "PreSignal_Reference": ["episode_id", "provider", "model", "pack_e_forecast_id", "forecast_timestamp", "forecast_cutoff", "pack_e_reference", "prediction_5m", "prediction_15m", "prediction_30m", "prediction_60m", "reversal_prediction", "confidence", "outcome_reference"],
    "Outcome_Comparison": ["episode_id", "provider", "presignal_5m_correctness", "autonomous_ai_5m_correctness", "presignal_15m_correctness", "autonomous_ai_15m_correctness", "presignal_30m_correctness", "autonomous_ai_30m_correctness", "presignal_60m_correctness", "autonomous_ai_60m_correctness", "reversal_correctness", "magnitude_error", "path_score", "completion_status", "token_cost", "latency_ms", "research_source_count", "cutoff_violation_count", "benchmark_winner_for_episode", "interpretation_note"],
    "Run_Status": ["experiment_state", "current_episode", "completed_episodes", "failed_episodes", "active_run", "start_time", "end_time", "terminal_decision", "interruption_reason"],
    "log": ["timestamp", "run_id", "level", "event", "details"],
}


class BenchmarkError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def eligible_rows() -> list[dict[str, Any]]:
    """Read only validity/lineage fields; no correctness metric is inspected."""
    rows = jsonl(SOURCE_RUN / "evaluation_results.jsonl")
    result = []
    for row in rows:
        forecast = ((row.get("pack_e_forecast") or {}).get("prediction") or {})
        paths = (row.get("pack_e_forecast") or {}).get("paths") or []
        if not (row.get("completion") == "COMPLETE_PAIRED" and row.get("pack_e_accepted") is True):
            continue
        if forecast.get("status") != "VALID" or not forecast.get("forecast_cutoff_ts"):
            continue
        if {item.get("horizon_min") for item in paths} != {5, 15, 30, 60}:
            continue
        result.append(row)
    return result


def resolve_source(seed: int = SAMPLE_SEED) -> dict[str, Any]:
    if not SOURCE_RUN.exists():
        raise BenchmarkError("AUTHORITATIVE_EPISODE_SOURCE_NOT_RESOLVED")
    manifest = json.loads((SOURCE_RUN / "run_manifest.json").read_text())
    contract = manifest.get("contract") or {}
    if contract.get("contract_version") != CONTRACT or contract.get("contract_fingerprint") != CONTRACT_FINGERPRINT:
        raise BenchmarkError("AUTHORITATIVE_CONTRACT_MISMATCH")
    population = {item["episode_id"]: item for item in json.loads((SOURCE_RUN / "frozen_execution_population.json").read_text())["episodes"]}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows():
        if row["episode_id"] not in population:
            raise BenchmarkError("AUTHORITATIVE_EPISODE_LINEAGE_MISSING")
        grouped[row["episode_id"]].append(row)
    if len(grouped) != 45:
        raise BenchmarkError("AUTHORITATIVE_ELIGIBLE_COUNT_MISMATCH:" + str(len(grouped)))
    provider_counts = Counter(row["provider"] for rows in grouped.values() for row in rows)
    candidates = sorted(grouped)
    sample_ids = random.Random(seed).sample(candidates, SAMPLE_SIZE)
    coverage = {
        provider: sum(any(row["provider"] == provider for row in grouped[eid]) for eid in sample_ids)
        for provider in provider_counts
    }
    chosen = max(coverage, key=lambda provider: (coverage[provider], provider_counts[provider], provider))
    if coverage[chosen] != SAMPLE_SIZE:
        raise BenchmarkError("INSUFFICIENT_ELIGIBLE_EPISODES_FOR_SELECTED_PROVIDER")
    selected = []
    for order, episode_id in enumerate(sample_ids, start=1):
        row = next(item for item in grouped[episode_id] if item["provider"] == chosen)
        selected.append({"sample_order": order, "episode": population[episode_id], "reference": row})
    models = {item["reference"]["model"] for item in selected}
    if len(models) != 1:
        raise BenchmarkError("SELECTED_PROVIDER_MODEL_AMBIGUOUS")
    return {
        "source_run": str(SOURCE_RUN), "contract": contract, "eligible_unique_episode_count": len(grouped),
        "eligible_provider_counts": dict(sorted(provider_counts.items())), "seed": seed,
        "provider": chosen, "model": models.pop(), "sample": selected,
        "selection_fingerprint": fingerprint({"seed": seed, "provider": chosen, "episodes": sample_ids}),
    }


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _path(reference: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {item["horizon_min"]: item for item in (reference["pack_e_forecast"] or {}).get("paths", [])}


def episode_rows(resolution: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples, references = [], []
    for item in resolution["sample"]:
        episode, reference = item["episode"], item["reference"]
        prediction = reference["pack_e_forecast"]["prediction"]
        paths = _path(reference)
        members = episode["episode_members"]
        samples.append({
            "sample_order": item["sample_order"], "episode_id": episode["episode_id"], "release_timestamp": episode["release_ts"],
            "forecast_cutoff": episode["forecast_cutoff_ts"], "event_or_cluster_members": canonical([{k: m.get(k) for k in ("event_id", "indicator_name", "importance", "type")} for m in members]),
            "event_family": ", ".join(sorted({str(m.get("genre") or "unknown") for m in members})), "importance": ", ".join(sorted({str(m.get("importance") or "unknown") for m in members})),
            "provider": resolution["provider"], "model": resolution["model"], "existing_presignal_forecast_reference": prediction["prediction_id"],
            "existing_pack_e_reference": prediction["pack_id"], "outcome_reference": reference["pack_e_evaluation"]["outcome_id"], "memory_risk_category": "NORMAL_MEMORY_RISK", "selection_status": "FROZEN",
        })
        references.append({
            "episode_id": episode["episode_id"], "provider": resolution["provider"], "model": resolution["model"], "pack_e_forecast_id": prediction["prediction_id"],
            "forecast_timestamp": prediction["forecast_created_ts"], "forecast_cutoff": prediction["forecast_cutoff_ts"], "pack_e_reference": prediction["pack_id"],
            "prediction_5m": paths[5]["expected_direction"], "prediction_15m": paths[15]["expected_direction"], "prediction_30m": paths[30]["expected_direction"], "prediction_60m": paths[60]["expected_direction"],
            "reversal_prediction": prediction["expected_reversal_flag"], "confidence": prediction["confidence"], "outcome_reference": reference["pack_e_evaluation"]["outcome_id"],
        })
    return samples, references


def config_rows(resolution: Mapping[str, Any], run_id: str) -> list[dict[str, Any]]:
    values = {
        "experiment_id": run_id, "creation_timestamp": now(), "classification": "EXPLORATORY_HISTORICAL_AUTONOMOUS_AI_BENCHMARK",
        "authoritative_source_run": "STEP8-R3-FINAL-R1-e8bf771", "contract": CONTRACT, "contract_fingerprint": CONTRACT_FINGERPRINT,
        "provider": resolution["provider"], "model": resolution["model"], "episode_count": SAMPLE_SIZE, "random_selection_seed": resolution["seed"],
        "forecast_target": "USDJPY_EVENT_PATH_T_PLUS_5_15_30_60", "primary_endpoint": "15-minute directional accuracy",
        "secondary_endpoints": "5m,30m,60m,magnitude,continuation,reversal,path,no-signal,completeness", "research_cutoff_policy": "pre-cutoff demonstrably published sources only",
        "source_timestamp_policy": "page-level datePublished required; undated sources rejected", "research_budget": "10 queries maximum and 10 accepted sources maximum per Episode",
        "allowed_actions": "benchmark-only public-source discovery, timestamp validation, same-provider forecast", "prohibited_actions": "no source workbook writes; no Pack regeneration; no P12; no routing/weighting/calibration", "benchmark_status": "INITIALIZED_PENDING_RESEARCH_TRACE",
    }
    return [{"config_key": key, "config_value": _string(value)} for key, value in values.items()]


def create_workbook(resolution: Mapping[str, Any], run_id: str) -> str:
    from automation.google_clients import batch_update_values, build_sheets_service, load_credentials
    service = build_sheets_service(load_credentials(False))
    response = service.spreadsheets().create(body={"properties": {"title": "presignal_autonomous_ai_benchmark"}, "sheets": [{"properties": {"title": name}} for name in SHEETS]}).execute()
    spreadsheet_id = response["spreadsheetId"]
    samples, references = episode_rows(resolution)
    status = [{"experiment_state": "INITIALIZED_PENDING_RESEARCH_TRACE", "current_episode": "", "completed_episodes": 0, "failed_episodes": 0, "active_run": run_id, "start_time": now(), "end_time": "", "terminal_decision": "", "interruption_reason": ""}]
    log = [{"timestamp": now(), "run_id": run_id, "level": "INFO", "event": "BENCHMARK_INITIALIZED", "details": canonical({"selection_fingerprint": resolution["selection_fingerprint"], "source_run": "STEP8-R3-FINAL-R1-e8bf771"})}]
    content = {"Experiment_Config": config_rows(resolution, run_id), "Episode_Sample": samples, "PreSignal_Reference": references, "Run_Status": status, "log": log}
    updates = []
    for sheet, headers in SHEETS.items():
        rows = content.get(sheet, [])
        updates.append({"range": f"'{sheet}'!A1", "values": [headers] + [[row.get(header, "") for header in headers] for row in rows]})
    batch_update_values(service, spreadsheet_id, updates)
    return spreadsheet_id


def page_metadata(url: str, timeout: int = 20) -> dict[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "PreSignalBenchmark/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(1_000_000).decode("utf-8", "replace")
    def meta(name: str) -> str:
        pattern = r'<meta[^>]+(?:property|name)=["\']' + re.escape(name) + r'["\'][^>]+content=["\']([^"\']+)["\']'
        found = re.search(pattern, body, re.I)
        return html.unescape(found.group(1)).strip() if found else ""
    published = meta("article:published_time") or meta("datePublished") or meta("date")
    title = meta("og:title") or (re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S).group(1).strip() if re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S) else "")
    publisher = meta("og:site_name")
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", body, flags=re.I | re.S)
    return {"title": html.unescape(title)[:300], "publisher": publisher[:200], "published": published, "evidence": " ".join(html.unescape(text).split())[:4000]}


def validate_source(*, url: str, cutoff: str) -> dict[str, Any]:
    retrieved = now()
    try:
        metadata = page_metadata(url)
    except Exception as exc:
        return {"source_url": url, "retrieval_timestamp": retrieved, "source_accepted": False, "source_cutoff_status": "REJECTED", "rejection_reason": "RETRIEVAL_ERROR", "error_status": str(exc)}
    try:
        published = iso(metadata["published"]).astimezone(timezone.utc)
    except Exception:
        return {**metadata, "source_url": url, "retrieval_timestamp": retrieved, "source_accepted": False, "source_cutoff_status": "REJECTED", "rejection_reason": "UNDATED_OR_UNPARSEABLE_PUBLICATION_TIMESTAMP", "error_status": ""}
    cutoff_at = iso(cutoff)
    if published > cutoff_at:
        return {**metadata, "source_url": url, "retrieval_timestamp": retrieved, "source_accepted": False, "source_cutoff_status": "REJECTED", "rejection_reason": "POST_CUTOFF_SOURCE", "error_status": ""}
    return {**metadata, "source_url": url, "retrieval_timestamp": retrieved, "source_accepted": True, "source_cutoff_status": "ACCEPTED_PRE_CUTOFF", "rejection_reason": "", "error_status": ""}


def _bridge(provider: str, model: str, run_id: str, episode: Mapping[str, Any], arm: str, prompt: str) -> Mapping[str, Any]:
    """The existing Apps Script route remains the sole provider transport."""
    from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function
    payload = {"provider": provider, "model": model, "authoritative_run_id": run_id,
               "forecast_identity": "BENCH_" + hashlib.sha256((episode["episode_id"] + arm).encode()).hexdigest()[:20],
               "session_id": episode["session_id"], "arm": arm, "hard_timeout_seconds": 180,
               "request_schema_version": "authoritative_historical_replay_bridge_v1",
               "prompt": {"system": "Return strict JSON only.", "user": prompt, "instruction": "Follow the historical cutoff policy exactly.", "cache_scaffold": ""}}
    result = run_script_function(build_script_service(load_credentials(False), 240), default_script_id(), "apiCallAuthoritativeProviderJsonObject", [payload])
    if not isinstance(result, Mapping) or result.get("status") != "ok" or result.get("actual_provider") != provider or result.get("actual_model") != model:
        raise BenchmarkError("GEMINI_PROVIDER_IDENTITY_OR_TRANSPORT_FAILURE")
    return result


def _queries(raw: str, episode: Mapping[str, Any]) -> list[str]:
    try:
        value = json.loads(raw)
        items = value.get("queries", [])
        if not isinstance(items, list):
            raise ValueError()
        queries = [str(item).strip() for item in items if isinstance(item, str) and item.strip()]
    except Exception as exc:
        raise BenchmarkError("GEMINI_RESEARCH_PLAN_FAILED") from exc
    if not queries:
        raise BenchmarkError("GEMINI_RESEARCH_PLAN_FAILED")
    return queries[:8]


def _discover(query: str, cutoff: str) -> list[dict[str, str]]:
    """A bounded GDELT article-list lookup; pages still need their own timestamp proof."""
    end = iso(cutoff).strftime("%Y%m%d%H%M%S")
    start = (iso(cutoff).replace(year=iso(cutoff).year - 1)).strftime("%Y%m%d%H%M%S")
    params = urllib.parse.urlencode({"query": query, "mode": "artlist", "format": "json", "maxrecords": 8, "startdatetime": start, "enddatetime": end})
    request = urllib.request.Request(DISCOVERY_URL + "?" + params, headers={"User-Agent": "PreSignalBenchmark/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8", "replace"))
    return [{"url": str(item.get("url") or ""), "title": str(item.get("title") or ""), "domain": str(item.get("domain") or "")} for item in body.get("articles", []) if item.get("url")]


def seed_audit(resolution: Mapping[str, Any]) -> dict[str, Any]:
    """Exact reconstruction of the original increasing-seed feasibility search."""
    eligible = sorted({row["episode_id"] for row in eligible_rows()})
    provider_by_episode: dict[str, set[str]] = defaultdict(set)
    for row in eligible_rows(): provider_by_episode[row["episode_id"]].add(row["provider"])
    tested = []
    for seed in range(20260722, SAMPLE_SEED + 1):
        draw = random.Random(seed).sample(eligible, SAMPLE_SIZE)
        counts = {p: sum(p in provider_by_episode[e] for e in draw) for p in ("Gemini", "OpenAI")}
        tested.append({"seed": seed, "gemini_eligible_episode_count": counts["Gemini"], "openai_eligible_episode_count": counts["OpenAI"]})
    return {"original_attempted_seed": 20260722, "seed_progression_rule": "increment integer seed by one until one provider covers all ten frozen sample slots", "tested_seeds": tested, "correctness_fields_read": False, "selection_fields_read": ["episode_id", "provider", "model", "validity", "forecast_cutoff", "path_horizons"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Read only: resolve the authoritative source and sample.")
    parser.add_argument("--initialize", action="store_true", help="Create the isolated workbook and frozen artifact manifest.")
    parser.add_argument("--record-seed-audit", type=Path, help="Append the reconstructed seed audit to an existing benchmark manifest.")
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    args = parser.parse_args()
    if not args.check and not args.initialize and not args.record_seed_audit:
        parser.error("choose --check, --initialize, or --record-seed-audit")
    resolution = resolve_source(args.seed)
    if args.check:
        print(json.dumps({key: value for key, value in resolution.items() if key != "sample"} | {"episode_ids": [item["episode"]["episode_id"] for item in resolution["sample"]]}, indent=2, sort_keys=True))
        return 0
    if args.record_seed_audit:
        manifest = json.loads(args.record_seed_audit.read_text())
        if manifest.get("selection_fingerprint") != resolution["selection_fingerprint"]:
            raise BenchmarkError("FROZEN_SAMPLE_FINGERPRINT_MISMATCH")
        manifest["sampling_attempt_audit"] = seed_audit(resolution)
        write_json(args.record_seed_audit, manifest)
        print(json.dumps({"status": "SEED_ATTEMPT_AUDIT_RECORDED", "tested_seed_count": len(manifest["sampling_attempt_audit"]["tested_seeds"])}))
        return 0
    run_id = "AUTONOMOUS-AI-BENCHMARK-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    artifact = ARTIFACT_ROOT / run_id
    spreadsheet_id = create_workbook(resolution, run_id)
    write_json(artifact / "benchmark_manifest.json", {**resolution, "spreadsheet_id": spreadsheet_id, "run_id": run_id, "created_at": now(), "status": "AUTONOMOUS_AI_BENCHMARK_READY"})
    print(json.dumps({"decision": "AUTONOMOUS_AI_BENCHMARK_READY", "run_id": run_id, "spreadsheet_id": spreadsheet_id, "artifact_directory": str(artifact)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
