import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "automation_runs"
DEFAULT_SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_local_day(day_value: str) -> datetime:
    try:
        return datetime.strptime(day_value, "%Y-%m-%d")
    except ValueError as exc:
        raise RuntimeError(f"Invalid --day value '{day_value}'. Use YYYY-MM-DD.") from exc


def _resolve_window_args(args) -> Dict[str, str]:
    if args.day:
        day_start = _parse_local_day(args.day)
        day_end = day_start + timedelta(days=1)
        return {
            "window_from_local": day_start.strftime("%Y-%m-%d 00:00"),
            "window_to_local": day_end.strftime("%Y-%m-%d 00:00"),
        }
    if not args.window_from_local or not args.window_to_local:
        raise RuntimeError("Provide either --day YYYY-MM-DD or both --window-from-local and --window-to-local.")
    return {
        "window_from_local": args.window_from_local,
        "window_to_local": args.window_to_local,
    }


def _upsert_config_window(
    sheets_service,
    spreadsheet_id: str,
    window_from_local: str,
    window_to_local: str,
    tz: str,
    pred_max_work_units_per_run: int = None,
) -> Dict[str, str]:
    from automation.google_clients import batch_update_values, get_sheet_values

    values = get_sheet_values(sheets_service, spreadsheet_id, "Config!A:B")
    if not values:
        raise RuntimeError("Config sheet is empty or missing.")

    row_by_key: Dict[str, int] = {}
    for i, row in enumerate(values[1:], start=2):
        key = row[0].strip() if row and row[0] else ""
        if key:
            row_by_key[key] = i

    entries = {
        "WINDOW_ENABLED": "TRUE",
        "WINDOW_FROM_LOCAL": window_from_local,
        "WINDOW_TO_LOCAL": window_to_local,
        "WINDOW_TZ": tz,
        "PRED_WINDOW_ENABLED": "TRUE",
        "PRED_WINDOW_FROM_LOCAL": window_from_local,
        "PRED_WINDOW_TO_LOCAL": window_to_local,
        "PRED_WINDOW_TZ": tz,
        "MR_WINDOW_ENABLED": "TRUE",
        "MR_WINDOW_FROM_LOCAL": window_from_local,
        "MR_WINDOW_TO_LOCAL": window_to_local,
        "MR_WINDOW_TZ": tz,
    }
    if pred_max_work_units_per_run is not None:
        entries["PRED_MAX_WORK_UNITS_PER_RUN"] = str(int(pred_max_work_units_per_run))

    updates: List[Dict[str, Any]] = []
    append_rows: List[List[str]] = []
    next_row = max(len(values) + 1, 2)
    for key, value in entries.items():
        row = row_by_key.get(key)
        if row:
            updates.append({"range": f"Config!B{row}", "values": [[value]]})
        else:
            append_rows.append([key, value])

    if append_rows:
        updates.append(
            {
                "range": f"Config!A{next_row}:B{next_row + len(append_rows) - 1}",
                "values": append_rows,
            }
        )

    if updates:
        batch_update_values(sheets_service, spreadsheet_id, updates)

    return entries


def _filter_predictions_since(rows: List[List[Any]], started_at_iso: str) -> List[Dict[str, Any]]:
    if not rows:
        return []
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    lo = _parse_iso(started_at_iso)
    out = []
    for row in rows[1:]:
        ts = row[idx["created_ts"]] if idx.get("created_ts") is not None and idx["created_ts"] < len(row) else ""
        dt = _parse_iso(ts)
        if lo and dt and dt >= lo:
            out.append({name: (row[i] if i < len(row) else "") for name, i in idx.items()})
    return out


def _filter_logs(rows: List[List[Any]], started_at_iso: str) -> List[Dict[str, Any]]:
    if not rows:
        return []
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    lo = _parse_iso(started_at_iso)
    out = []
    for row in rows[1:]:
        ts = row[idx["ts"]] if idx.get("ts") is not None and idx["ts"] < len(row) else ""
        dt = _parse_iso(ts)
        if lo and dt and dt >= lo:
            out.append({name: (row[i] if i < len(row) else "") for name, i in idx.items()})
    return out


def _filter_rows_since(rows: List[List[Any]], started_at_iso: str, time_column: str) -> List[Dict[str, Any]]:
    if not rows:
        return []
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    lo = _parse_iso(started_at_iso)
    out = []
    for row in rows[1:]:
        ts = row[idx[time_column]] if idx.get(time_column) is not None and idx[time_column] < len(row) else ""
        dt = _parse_iso(ts)
        if lo and dt and dt >= lo:
            out.append({name: (row[i] if i < len(row) else "") for name, i in idx.items()})
    return out


def _safe_number(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _release_window_bounds(artifact: Dict[str, Any]):
    params = artifact.get("pipeline_params", {})
    window_from_local = params.get("window_from_local", "")
    window_to_local = params.get("window_to_local", "")
    window_tz = params.get("window_tz", "UTC") or "UTC"
    if not window_from_local or not window_to_local:
        return None, None

    try:
        tzinfo = ZoneInfo(window_tz)
        lo = datetime.strptime(window_from_local, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo).astimezone(timezone.utc)
        hi = datetime.strptime(window_to_local, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo).astimezone(timezone.utc)
        return lo, hi
    except Exception:
        return None, None


def _rows_in_release_window(rows: List[Dict[str, Any]], lo, hi) -> List[Dict[str, Any]]:
    if not lo or not hi:
        return rows

    out = []
    for row in rows:
        release_dt = _parse_iso(str(row.get("release_ts", "")))
        if release_dt and lo <= release_dt < hi:
            out.append(row)
    return out


def _window_bounds_from_params(params: Dict[str, Any]):
    window_from_local = params.get("window_from_local", "")
    window_to_local = params.get("window_to_local", "")
    window_tz = params.get("window_tz", "UTC") or "UTC"
    if not window_from_local or not window_to_local:
        return None, None
    try:
        tzinfo = ZoneInfo(window_tz)
        lo = datetime.strptime(window_from_local, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo).astimezone(timezone.utc)
        hi = datetime.strptime(window_to_local, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo).astimezone(timezone.utc)
        return lo, hi
    except Exception:
        return None, None


def _filter_dict_rows_by_release_window(rows: List[Dict[str, Any]], lo, hi) -> List[Dict[str, Any]]:
    if not lo or not hi:
        return rows
    out = []
    for row in rows or []:
        dt = _parse_iso(str(row.get("release_ts", "")))
        if dt and lo <= dt < hi:
            out.append(row)
    return out


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _infer_testing_family_key(indicator_name: str) -> str:
    name = str(indicator_name or "").strip().lower()
    if not name:
        return ""
    if name.startswith("cftc "):
        return "cftc_positions"
    if name.startswith("eia "):
        return "eia"
    if name.startswith("ism "):
        return "ism"
    if name.startswith("mba "):
        return "mba_mortgage"
    if "jobless claims" in name:
        return "jobless_claims"
    if "payroll" in name or "unemployment rate" in name or "average hourly earnings" in name:
        return "monthly_labor"
    if "cpi" in name or "inflation rate" in name or "retail sales" in name:
        return "macro_inflation_retail"
    if "speech" in name or "press conference" in name or "testimony" in name:
        return "fed_speeches"
    if "minutes" in name or "beige book" in name or "statement" in name or "report" in name:
        return "statement_report_text"
    if "auction" in name:
        return "treasury_auctions"
    return ""


def _parse_log_context(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("ctx") or row.get("context") or row.get("json") or row.get("context_json") or ""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _provider_stats_for_window(log_rows: List[Dict[str, Any]], scenario_rows: List[Dict[str, Any]], allowed_providers: List[str]) -> Dict[str, Dict[str, int]]:
    stats: Dict[str, Dict[str, int]] = {}
    allowed = set(str(p).strip() for p in (allowed_providers or []) if str(p).strip())
    for row in log_rows or []:
        ctx = _parse_log_context(row)
        provider = str(ctx.get("provider") or "").strip()
        if not provider:
            continue
        if allowed and provider not in allowed:
            continue
        s = stats.setdefault(provider, {"retries": 0, "errors": 0, "prediction_ok": 0, "scenario_hits": 0, "scenario_misses": 0})
        msg = str(row.get("msg") or row.get("message") or "")
        level = str(row.get("level") or "").lower()
        if msg == "Prediction ok":
            s["prediction_ok"] += 1
        elif msg.startswith("Retrying"):
            s["retries"] += 1
        elif level == "error":
            s["errors"] += 1
    for row in scenario_rows or []:
        provider = str(row.get("ai_name") or "").strip()
        if not provider:
            continue
        if allowed and provider not in allowed:
            continue
        s = stats.setdefault(provider, {"retries": 0, "errors": 0, "prediction_ok": 0, "scenario_hits": 0, "scenario_misses": 0})
        if str(row.get("scenario_eval_result", "")).lower() == "hit":
            s["scenario_hits"] += 1
        elif str(row.get("scenario_eval_result", "")).lower() == "miss":
            s["scenario_misses"] += 1
    return stats


def _prediction_rows_in_release_window(artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    lo, hi = _release_window_bounds(artifact)
    return _filter_dict_rows_by_release_window(artifact.get("predictions", []), lo, hi)


def _build_testing_framework_(artifact: Dict[str, Any], scenario_rows: List[Dict[str, Any]], batch_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    predictions = _prediction_rows_in_release_window(artifact)
    logs = artifact.get("logs", []) or []
    active_providers = list(artifact.get("pipeline_params", {}).get("providers", []) or [])
    findings: List[Dict[str, Any]] = []
    categories: List[str] = []

    def add_finding(category: str, severity: str, title: str, evidence: Dict[str, Any], recommendation: str):
        categories.append(category)
        findings.append({
            "category": category,
            "severity": severity,
            "title": title,
            "evidence": evidence,
            "recommendation": recommendation,
        })

    misses = [row for row in scenario_rows if str(row.get("scenario_eval_result", "")).lower() == "miss"]
    for row in misses[:5]:
        add_finding(
            "family_rule",
            "high",
            "Watchlist missed the realized best member",
            {
                "release_ts": row.get("release_ts", ""),
                "ai_name": row.get("ai_name", ""),
                "best_member_indicator_name": row.get("best_member_indicator_name", ""),
                "watch_member_indicator_names": row.get("watch_member_indicator_names", ""),
                "scenario_eval_note": row.get("scenario_eval_note", ""),
            },
            "Refine the recurring family/watchlist and then run a targeted retest on that release cluster.",
        )

    best_member_wins = sum(1 for row in batch_rows if str(row.get("winner", "")).lower() == "best_member")
    batch_wins = sum(1 for row in batch_rows if str(row.get("winner", "")).lower() == "batch")
    weak_like = sum(
        1 for row in batch_rows
        if str(row.get("selected_anchor_mode", "")).lower() in ("weak_anchor", "no_clear_anchor", "no_anchor")
    )
    if batch_rows and best_member_wins > batch_wins and weak_like > 0:
        add_finding(
            "confidence_risk",
            "medium",
            "Batch-level confidence is weaker than member/scenario behavior",
            {
                "best_member_wins": best_member_wins,
                "batch_wins": batch_wins,
                "weak_or_no_anchor_rows": weak_like,
            },
            "Keep or strengthen scenario-mode behavior here instead of forcing stronger batch direction calls.",
        )

    low_signal_hits = [
        row for row in scenario_rows
        if str(row.get("pre_risk_level", "")).lower() == "low"
        and str(row.get("pre_volatility_level", "")).lower() == "low"
        and str(row.get("scenario_eval_result", "")).lower() == "hit"
    ]
    if low_signal_hits and not misses:
        add_finding(
            "low_signal_suppression",
            "info",
            "Low-signal handling worked as intended",
            {"hit_rows": len(low_signal_hits)},
            "No new rule needed here; keep this family conservative and move on.",
        )

    batch_members: Dict[str, Dict[str, Any]] = {}
    for row in predictions:
        if str(row.get("type") or "").lower() != "member":
            continue
        batch_id = str(row.get("batch_id") or "").strip()
        if not batch_id:
            continue
        rec = batch_members.setdefault(
            batch_id,
            {"genres": set(), "families": set(), "count": 0, "release_ts": row.get("release_ts", "")},
        )
        genre = str(row.get("genre") or "").strip()
        if genre:
            rec["genres"].add(genre)
        family_key = _infer_testing_family_key(row.get("indicator_name") or "")
        if family_key:
            rec["families"].add(family_key)
        rec["count"] += 1
    mixed = []
    for batch_id, rec in batch_members.items():
        genres = sorted(list(rec["genres"]))
        families = sorted(list(rec["families"]))
        same_known_family = len(families) == 1
        if len(genres) >= 2 and rec["count"] >= 4 and not same_known_family:
            mixed.append({
                "batch_id": batch_id,
                "release_ts": rec["release_ts"],
                "genres": genres,
                "families": families,
                "member_rows": rec["count"],
            })
    if mixed and best_member_wins >= batch_wins:
        add_finding(
            "batch_splitting",
            "medium",
            "A mixed-genre same-time batch may be too broad",
            mixed[0],
            "Review whether this batch should stay unified or be split into cleaner release families.",
        )

    provider_stats = _provider_stats_for_window(logs, scenario_rows, active_providers)
    if provider_stats:
        retry_leader = max(provider_stats.items(), key=lambda kv: kv[1].get("retries", 0))
        retry_values = sorted(v.get("retries", 0) for v in provider_stats.values())
        baseline = retry_values[0] if retry_values else 0
        if retry_leader[1].get("retries", 0) >= baseline + 2 and retry_leader[1].get("retries", 0) > 0:
            add_finding(
                "provider_policy",
                "medium",
                "One provider needed materially more retries",
                {
                    "provider": retry_leader[0],
                    "retries": retry_leader[1].get("retries", 0),
                    "provider_stats": provider_stats,
                },
                "Watch this provider on similar days; if it keeps happening, adjust retry policy or provider usage.",
            )

    if predictions and not scenario_rows and not batch_rows:
        add_finding(
            "evaluation_coverage",
            "info",
            "The day produced predictions but no scored evaluation rows",
            {"prediction_rows": len(predictions)},
            "Treat this as a low-learning day unless actuals/scoring should have produced evaluation output.",
        )

    runtime_markers = []
    pred_step = ((artifact.get("pipeline_result") or {}).get("steps") or {}).get("predictions") or {}
    for group in pred_step.get("groups", []) or []:
        if group.get("status") in ("timeout_fallback_to_provider_split", "partial"):
            runtime_markers.append(group.get("status"))
        for p in group.get("passes", []) or []:
            if p.get("recovery"):
                runtime_markers.append(p.get("recovery"))
    if runtime_markers:
        add_finding(
            "automation_runtime",
            "info",
            "The runner had to recover or checkpoint during prediction",
            {"runtime_markers": runtime_markers[:10]},
            "The automation held up, but keep an eye on this day shape when tuning chunk sizes.",
        )

    unique_categories = []
    for category in categories:
        if category not in unique_categories:
            unique_categories.append(category)

    priority_order = [
        "family_rule",
        "batch_splitting",
        "confidence_risk",
        "provider_policy",
        "evaluation_coverage",
        "automation_runtime",
        "low_signal_suppression",
    ]
    primary_category = "no_action"
    for category in priority_order:
        if category in unique_categories:
            primary_category = category
            break

    next_action = {
        "family_rule": "Refine the recurring family/watchlist and run a targeted retest on the affected release.",
        "batch_splitting": "Review whether the same-time rows should be split into cleaner release families before predicting them together again.",
        "confidence_risk": "Tune scenario/anchor confidence behavior rather than forcing stronger directional batch calls.",
        "provider_policy": "Review provider-specific retry/stability patterns and decide whether to adjust provider usage or retry policy.",
        "evaluation_coverage": "No immediate prediction change; move to the next day unless this window was expected to produce scored evaluation.",
        "automation_runtime": "No prediction rule change first; stabilize the automation/runtime path for this day shape.",
        "low_signal_suppression": "No new rule needed; keep this family conservative and move on to the next day.",
        "no_action": "No immediate change needed; move to the next day.",
    }[primary_category]

    return {
        "testing_framework_version": "v1",
        "lesson_categories": unique_categories,
        "primary_lesson_category": primary_category,
        "learning_findings": findings[:10],
        "next_recommended_action": next_action,
        "provider_stats": provider_stats,
    }


def _build_run_summary(artifact: Dict[str, Any], mode: str) -> Dict[str, Any]:
    release_lo, release_hi = _release_window_bounds(artifact)
    scenario_rows = _rows_in_release_window(artifact.get("evaluation_scenario", []), release_lo, release_hi)
    batch_rows = _rows_in_release_window(artifact.get("evaluation_batch_compare", []), release_lo, release_hi)

    scenario_hits = sum(1 for row in scenario_rows if str(row.get("scenario_eval_result", "")).lower() == "hit")
    scenario_misses = sum(1 for row in scenario_rows if str(row.get("scenario_eval_result", "")).lower() == "miss")
    best_member_wins = sum(1 for row in batch_rows if str(row.get("winner", "")).lower() == "best_member")
    batch_wins = sum(1 for row in batch_rows if str(row.get("winner", "")).lower() == "batch")
    ties = sum(1 for row in batch_rows if str(row.get("winner", "")).lower() == "tie")

    candidates = []
    for row in scenario_rows:
        if str(row.get("scenario_eval_result", "")).lower() != "miss":
            continue
        candidates.append({
            "release_ts": row.get("release_ts", ""),
            "ai_name": row.get("ai_name", ""),
            "best_member_indicator_name": row.get("best_member_indicator_name", ""),
            "watch_member_indicator_names": row.get("watch_member_indicator_names", ""),
            "scenario_eval_note": row.get("scenario_eval_note", ""),
        })

    summary = {
        "mode": mode,
        "pipeline_status": artifact.get("pipeline_result", {}).get("status", "ok"),
        "prediction_rows_captured": len(artifact.get("predictions", [])),
        "log_rows_captured": len(artifact.get("logs", [])),
        "scenario_rows_captured": len(scenario_rows),
        "batch_compare_rows_captured": len(batch_rows),
        "scenario_hits": scenario_hits,
        "scenario_misses": scenario_misses,
        "best_member_wins": best_member_wins,
        "batch_wins": batch_wins,
        "ties": ties,
        "family_rule_candidates": candidates[:10],
    }
    summary.update(_build_testing_framework_(artifact, scenario_rows, batch_rows))
    return summary


def _load_prediction_log_summary_from_sheet(
    sheets_service,
    spreadsheet_id: str,
    base_params: Dict[str, Any],
    providers: List[str],
    since_iso: str,
) -> Dict[str, Any]:
    from automation.google_clients import get_sheet_values

    target_lo, target_hi = _window_bounds_from_params(base_params)
    target_start = target_lo.isoformat().replace("+00:00", "Z") if target_lo else ""
    target_end = target_hi.isoformat().replace("+00:00", "Z") if target_hi else ""
    target_providers = sorted([str(p) for p in (providers or [])])

    rows = get_sheet_values(sheets_service, spreadsheet_id, "log!A:D")
    recent = rows[-400:] if len(rows) > 400 else rows
    for row in reversed(recent):
        if len(row) < 4:
            continue
        ts = str(row[0] or "")
        msg = str(row[2] or "")
        raw_ctx = row[3]
        if ts and since_iso and ts < since_iso:
            break
        if "Prediction run " not in msg:
            continue
        try:
            ctx = json.loads(raw_ctx or "{}")
        except Exception:
            continue
        ctx_providers = sorted([str(p) for p in (ctx.get("providers") or [])])
        if target_start and str(ctx.get("window_start_iso") or "") != target_start:
            continue
        if target_end and str(ctx.get("window_end_iso") or "") != target_end:
            continue
        if target_providers and ctx_providers != target_providers:
            continue
        summary = dict(ctx)
        summary["log_ts"] = ts
        summary["log_message"] = msg
        return summary
    return {}


def _prediction_cap_sequence(initial_cap: int) -> List[int]:
    seq = []
    for value in [initial_cap]:
        try:
            n = int(value)
        except Exception:
            continue
        if n < 1:
            continue
        if n not in seq:
            seq.append(n)
    for value in [8, 4, 2, 1]:
        if value >= (seq[0] if seq else value + 1):
            continue
        if value not in seq:
            seq.append(value)
    return seq or [1]


def _is_transport_timeout_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in text
        for token in [
            "timed out",
            "timeout",
            "broken pipe",
            "connection reset",
            "remote end closed",
            "ssleoferror",
            "eof occurred in violation of protocol",
            "eof occurred",
        ]
    )


def _apply_prediction_runtime_config(
    sheets_service,
    spreadsheet_id: str,
    base_params: Dict[str, Any],
    pred_max_work_units_per_run: int,
) -> None:
    _upsert_config_window(
        sheets_service,
        spreadsheet_id,
        base_params["window_from_local"],
        base_params["window_to_local"],
        base_params["window_tz"],
        pred_max_work_units_per_run,
    )


def _run_prediction_group_(
    script_service,
    script_id: str,
    sheets_service,
    spreadsheet_id: str,
    base_params: Dict[str, Any],
    providers: List[str],
    per_call_passes: int,
    cap_sequence: List[int],
) -> Dict[str, Any]:
    from automation.google_clients import run_script_function

    passes = []
    clear_checkpoint = True
    final = None
    max_rounds = max(
        1,
        int(base_params.get("prediction_round_limit", int(base_params.get("max_passes", 12)) * 6))
    )
    cap_index = 0

    for _ in range(max_rounds):
        current_cap = cap_sequence[min(cap_index, len(cap_sequence) - 1)]
        _apply_prediction_runtime_config(
            sheets_service,
            spreadsheet_id,
            base_params,
            current_cap,
        )
        call_started_iso = _iso_now()
        try:
            resp = run_script_function(
                script_service,
                script_id,
                "apiRunPredictionsWindow",
                [{
                    "window_from_local": base_params["window_from_local"],
                    "window_to_local": base_params["window_to_local"],
                    "window_tz": base_params["window_tz"],
                    "providers": providers,
                    "clear_checkpoint": clear_checkpoint,
                    "continue_until_done": False,
                    "max_passes": 1,
                }],
            )
            clear_checkpoint = False
            passes.append({
                "providers": providers,
                "pred_max_work_units_per_run": current_cap,
                "response": resp,
            })
            final = (resp or {}).get("prediction_final") or {}
            if str(final.get("status", "")).lower() != "partial":
                break
            if not int(final.get("remaining_work_units") or 0):
                break
            continue
        except Exception as exc:
            recovered_summary = {}
            if _is_transport_timeout_error(exc):
                recovered_summary = _load_prediction_log_summary_from_sheet(
                    sheets_service,
                    spreadsheet_id,
                    base_params,
                    providers,
                    call_started_iso,
                )
            if recovered_summary:
                clear_checkpoint = False
                passes.append({
                    "providers": providers,
                    "pred_max_work_units_per_run": current_cap,
                    "transport_error": str(exc),
                    "recovery": "log_summary_resume",
                    "summary": recovered_summary,
                })
                final = recovered_summary
                if str(final.get("status", "")).lower() != "partial":
                    break
                if not int(final.get("remaining_work_units") or 0):
                    break
                continue
            if _is_transport_timeout_error(exc) and cap_index < len(cap_sequence) - 1:
                passes.append({
                    "providers": providers,
                    "pred_max_work_units_per_run": current_cap,
                    "transport_error": str(exc),
                    "recovery": "shrink_work_unit_cap",
                })
                clear_checkpoint = False
                cap_index += 1
                continue
            raise RuntimeError(
                f"Prediction group failed for providers={providers or ['ALL']} "
                f"at work_units={current_cap}: {exc}"
            ) from exc

    return {
        "providers": providers,
        "passes": passes,
        "final": final or {},
        "status": str((final or {}).get("status") or "ok").lower(),
        "pred_max_work_units_per_run": cap_sequence[min(cap_index, len(cap_sequence) - 1)],
    }


def _run_prediction_sequence(
    script_service,
    script_id: str,
    sheets_service,
    spreadsheet_id: str,
    base_params: Dict[str, Any],
    per_call_passes: int,
    pred_max_work_units_per_run: int,
) -> Dict[str, Any]:
    provider_list = list(base_params.get("providers") or [])
    cap_sequence = _prediction_cap_sequence(pred_max_work_units_per_run)
    group_runs = []

    try:
        primary = _run_prediction_group_(
            script_service,
            script_id,
            sheets_service,
            spreadsheet_id,
            base_params,
            provider_list,
            per_call_passes,
            cap_sequence,
        )
        group_runs.append(primary)
    except Exception as exc:
        if not provider_list or len(provider_list) <= 1 or not _is_transport_timeout_error(exc):
            raise
        group_runs.append({
            "providers": provider_list,
            "status": "timeout_fallback_to_provider_split",
            "error": str(exc),
        })
        single_cap_sequence = _prediction_cap_sequence(min(pred_max_work_units_per_run, 2))
        for provider in provider_list:
            group_runs.append(_run_prediction_group_(
                script_service,
                script_id,
                sheets_service,
                spreadsheet_id,
                base_params,
                [provider],
                per_call_passes,
                single_cap_sequence,
            ))

    _apply_prediction_runtime_config(
        sheets_service,
        spreadsheet_id,
        base_params,
        pred_max_work_units_per_run,
    )

    flat_passes = []
    final_status = "ok"
    finals = []
    for group in group_runs:
        if group.get("passes"):
            flat_passes.extend(group["passes"])
        if group.get("final"):
            finals.append({
                "providers": group.get("providers", []),
                "prediction_final": group.get("final", {}),
            })
        status = str(group.get("status") or "ok").lower()
        if status == "partial":
            final_status = "partial"

    return {
        "passes": flat_passes,
        "groups": group_runs,
        "final": finals[-1]["prediction_final"] if finals else {},
        "finals_by_group": finals,
        "status": final_status,
    }


def _run_pipeline_sequence(
    script_service,
    script_id: str,
    sheets_service,
    spreadsheet_id: str,
    params: Dict[str, Any],
    prediction_passes_per_call: int,
    pred_max_work_units_per_run: int,
) -> Dict[str, Any]:
    from automation.google_clients import run_script_function

    out: Dict[str, Any] = {"status": "ok", "steps": {}}

    if params.get("run_predictions", True):
        pred = _run_prediction_sequence(
            script_service,
            script_id,
            sheets_service,
            spreadsheet_id,
            params,
            prediction_passes_per_call,
            pred_max_work_units_per_run,
        )
        out["steps"]["predictions"] = pred
        if pred.get("status") == "partial":
            out["status"] = "partial"

    if params.get("run_actuals"):
        out["steps"]["actuals"] = run_script_function(
            script_service,
            script_id,
            "apiFetchActualsWindow",
            [{
                "window_from_local": params["window_from_local"],
                "window_to_local": params["window_to_local"],
                "window_tz": params["window_tz"],
            }],
        )

    if params.get("run_market_reaction"):
        out["steps"]["market_reaction"] = run_script_function(
            script_service,
            script_id,
            "apiScoreMarketReactionWindow",
            [{
                "window_from_local": params["window_from_local"],
                "window_to_local": params["window_to_local"],
                "window_tz": params["window_tz"],
            }],
        )

    if params.get("build_evaluation", True):
        out["steps"]["evaluation"] = run_script_function(
            script_service,
            script_id,
            "apiBuildEvaluationSheets",
            [],
        )

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PreSignal automation pipeline via Apps Script API.")
    parser.add_argument("--mode", default="day-run", choices=["day-run", "targeted-retest", "review-summary"])
    parser.add_argument("--day", help="Local day window, e.g. 2024-05-13")
    parser.add_argument("--window-from-local", help="Local window start, e.g. 2024-05-03 23:45")
    parser.add_argument("--window-to-local", help="Local window end, e.g. 2024-05-03 23:46")
    parser.add_argument("--tz", default="UTC", help="IANA timezone for local window values")
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--script-id", default="")
    parser.add_argument("--providers", default="", help="Comma-separated provider list")
    parser.add_argument("--run-actuals", action="store_true")
    parser.add_argument("--run-market-reaction", action="store_true")
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--max-passes", type=int, default=12)
    parser.add_argument("--prediction-passes-per-call", type=int, default=2)
    parser.add_argument("--pred-max-work-units-per-run", type=int, default=12)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--artifact", help="Existing artifact path for review-summary mode")
    args = parser.parse_args()

    if args.mode == "review-summary":
        if not args.artifact:
            raise RuntimeError("--artifact is required for review-summary mode.")
        artifact = json.loads(Path(args.artifact).read_text())
        print(json.dumps(_build_run_summary(artifact, args.mode), ensure_ascii=False, indent=2))
        return

    from automation.google_clients import (
        batch_update_values,
        build_script_service,
        build_sheets_service,
        default_script_id,
        get_sheet_values,
        load_credentials,
        run_script_function,
    )

    if not args.script_id:
        args.script_id = default_script_id()

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)

    started_at = _iso_now()
    window_args = _resolve_window_args(args)
    config_update = _upsert_config_window(
        sheets_service,
        args.spreadsheet_id,
        window_args["window_from_local"],
        window_args["window_to_local"],
        args.tz,
        args.pred_max_work_units_per_run,
    )

    params: Dict[str, Any] = {
        "window_from_local": window_args["window_from_local"],
        "window_to_local": window_args["window_to_local"],
        "window_tz": args.tz,
        "providers": [p.strip() for p in args.providers.split(",") if p.strip()],
        "run_predictions": True,
        "run_actuals": args.run_actuals or args.mode == "day-run",
        "run_market_reaction": args.run_market_reaction or args.mode == "day-run",
        "build_evaluation": not args.skip_evaluation,
        "continue_until_done": True,
        "clear_checkpoint": True,
        "max_passes": args.max_passes,
        "prediction_round_limit": max(24, args.max_passes * 6),
        "runner_mode": args.mode,
    }

    pipeline_result = _run_pipeline_sequence(
        script_service,
        args.script_id,
        sheets_service,
        args.spreadsheet_id,
        params,
        max(1, int(args.prediction_passes_per_call)),
        max(1, int(args.pred_max_work_units_per_run)),
    )

    prediction_rows = get_sheet_values(sheets_service, args.spreadsheet_id, "Predictions!A:CV")
    log_rows = get_sheet_values(sheets_service, args.spreadsheet_id, "log!A:D")
    scenario_rows = get_sheet_values(sheets_service, args.spreadsheet_id, "Evaluation_Scenario!A:AZ")
    batch_compare_rows = get_sheet_values(sheets_service, args.spreadsheet_id, "Evaluation_BatchCompare!A:AZ")

    artifact = {
        "started_at": started_at,
        "mode": args.mode,
        "config_update": config_update,
        "pipeline_params": params,
        "pipeline_result": pipeline_result,
        "predictions": _filter_predictions_since(prediction_rows, started_at),
        "logs": _filter_logs(log_rows, started_at),
        "evaluation_scenario": _filter_rows_since(scenario_rows, started_at, "generated_ts"),
        "evaluation_batch_compare": _filter_rows_since(batch_compare_rows, started_at, "generated_ts"),
    }
    artifact["summary"] = _build_run_summary(artifact, args.mode)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_prefix = "day_run" if args.mode == "day-run" else "targeted_retest"
    out_path = output_dir / f"{file_prefix}_{stamp}.json"
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2))

    print(json.dumps({
        "artifact": str(out_path),
        "status": pipeline_result.get("status", "ok"),
        "summary": artifact["summary"]
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
