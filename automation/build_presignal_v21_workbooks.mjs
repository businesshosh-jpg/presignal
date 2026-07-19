import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const MAIN_SHEETS = [
  "Event", "Config", "SeriesMap", "SeriesMap_Suggestions", "FRED_Series_ID",
  "FMP_EventCatalog", "Episode", "Information", "Prediction", "Prediction_Path",
  "Outcome", "Evaluation", "Session_Map", "Schema", "Run_Log",
];

const RESEARCH_SHEETS = [
  "Experiment_Register", "Run_Register", "Evaluation_Metrics", "Case_Review", "Artifact_Register",
];

const HEADERS = {
  Config: ["config_key", "config_value", "meaning", "migration_status", "source_key", "reason"],
  SeriesMap_Suggestions: ["country", "indicator_name_pattern", "provider", "series_id", "freq", "unit_type", "transform", "seasonal_adjustment", "precision_dp", "lag_rule", "notes", "created_ts"],
  Episode: ["object", "schema_version", "system_version", "episode_id", "session_id", "country", "episode_family", "release_ts", "forecast_cutoff_ts", "member_event_count", "member_event_ids", "member_indicator_names", "primary_event_id", "primary_indicator_name", "secondary_event_ids", "secondary_indicator_names", "selection_status", "selection_reason", "same_time_cluster_flag", "created_ts", "updated_ts", "status", "error_message"],
  Information: ["object", "schema_version", "system_version", "record_id", "record_type", "episode_id", "session_id", "provider", "model", "information_key", "information_category", "requested_information", "attention_role", "priority", "reason", "acquisition_method", "source_name", "source_reference", "source_timestamp", "as_of_timestamp", "retrieved_value", "normalized_value", "confidence", "reliability_label", "shared_pack_flag", "provisional_flag", "availability_status", "created_ts", "status", "error_message"],
  Prediction: ["object", "schema_version", "system_version", "run_id", "prediction_id", "episode_id", "session_id", "provider", "model", "information_arm", "pack_id", "pack_fingerprint", "forecast_created_ts", "forecast_cutoff_ts", "prediction_target_type", "prediction_target_id", "primary_event_id", "secondary_event_ids", "no_signal_flag", "no_signal_reason", "confidence", "expected_initial_direction", "expected_reversal_flag", "expected_reversal_horizon_min", "expected_path_summary", "information_used", "missing_information", "invalidation_condition", "raw_output", "prompt_tokens", "completion_tokens", "latency_ms", "prediction_fingerprint", "status", "error_message"],
  Prediction_Path: ["object", "schema_version", "system_version", "run_id", "prediction_id", "path_id", "episode_id", "provider", "model", "information_arm", "stage_index", "stage_type", "target_type", "target_id", "horizon_min", "expected_direction", "expected_pips_min", "expected_pips_max", "stage_confidence", "continuation_probability", "reversal_probability", "stage_reason", "invalidation_condition", "stage_fingerprint", "created_ts", "status", "error_message"],
  Outcome: ["object", "schema_version", "system_version", "outcome_id", "episode_id", "session_id", "release_ts", "anchor_price_ts", "anchor_price", "price_5m", "price_15m", "price_30m", "price_60m", "pips_5m", "pips_15m", "pips_30m", "pips_60m", "direction_5m", "direction_15m", "direction_30m", "direction_60m", "max_up_pips", "max_down_pips", "max_up_ts", "max_down_ts", "initial_direction", "reversal_flag", "reversal_ts", "intervening_event_flag", "market_data_provider", "source_lineage", "acquisition_ts", "outcome_fingerprint", "status", "error_message"],
  Evaluation: ["object", "schema_version", "system_version", "evaluation_id", "run_id", "prediction_id", "outcome_id", "episode_id", "provider", "model", "information_arm", "direction_5m_ok", "direction_15m_ok", "direction_30m_ok", "direction_60m_ok", "magnitude_15m_error", "reversal_ok", "no_signal_ok", "primary_endpoint_name", "primary_endpoint_value", "overall_path_score", "evaluation_note", "evaluation_contract_version", "evaluation_fingerprint", "generated_ts", "status", "error_message"],
  Session_Map: ["object", "schema_version", "system_version", "session_map_id", "session_id", "session_date", "country", "episode_count", "episode_ids", "primary_episode_id", "secondary_episode_ids", "expected_sequence", "expected_overall_path", "actual_sequence", "actual_overall_path", "session_summary_status", "generated_ts", "status", "error_message"],
  Schema: ["schema_version", "parent_schema_version", "schema_section", "schema_item", "change_status", "v2_0_definition", "v2_1_definition", "reason", "effective_status", "source_reference", "notes"],
  Run_Log: ["record_type", "run_id", "stage", "timestamp", "level", "status", "message", "context_json", "source_component"],
  Experiment_Register: ["experiment_id", "experiment_name", "system_version", "hypothesis", "primary_endpoint", "secondary_endpoints", "population_definition", "information_arms", "providers", "status", "created_ts", "frozen_ts", "decision", "notes"],
  Run_Register: ["experiment_id", "run_id", "run_type", "branch", "git_commit", "schema_version", "contract_version", "population_count", "provider_count", "started_ts", "completed_ts", "status", "fingerprint", "notes"],
  Evaluation_Metrics: ["experiment_id", "run_id", "metric_scope", "provider", "information_arm", "horizon_min", "metric_name", "metric_value", "sample_count", "confidence_interval_low", "confidence_interval_high", "generated_ts", "notes"],
  Case_Review: ["experiment_id", "run_id", "episode_id", "provider", "information_arm", "review_type", "classification", "finding", "severity", "reviewer", "reviewed_ts", "notes"],
  Artifact_Register: ["experiment_id", "run_id", "artifact_type", "artifact_name", "artifact_path", "artifact_fingerprint", "created_ts", "status", "notes"],
};

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 2) args[argv[index].replace(/^--/, "")] = argv[index + 1];
  return args;
}

function sha256(value) {
  return `sha256:${crypto.createHash("sha256").update(value).digest("hex")}`;
}

function text(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function canonicalRows(rows) {
  return rows
    .map((row) => [...row])
    .filter((row) => row.some((value) => text(value) !== ""));
}

function requireUniqueHeaders(sheetName, rows) {
  if (!rows.length) throw new Error(`${sheetName}: source table is empty`);
  const header = rows[0].map((value) => text(value));
  if (!header.length || header.some((value) => !value)) throw new Error(`${sheetName}: source header contains an empty name`);
  const duplicates = header.filter((value, index) => header.indexOf(value) !== index);
  if (duplicates.length) throw new Error(`${sheetName}: source header duplicates ${[...new Set(duplicates)].join(", ")}`);
  return header;
}

function sourceTable(snapshot, name) {
  const rows = canonicalRows(snapshot.source_tables[name] || []);
  requireUniqueHeaders(name, rows);
  return rows;
}

function selectConfig(sourceRows) {
  const headings = sourceRows[0].map((value) => text(value).toLowerCase());
  const keyIndex = headings.indexOf("key");
  const valueIndex = headings.indexOf("value");
  const meaningIndex = headings.indexOf("meaning");
  if (keyIndex < 0 || valueIndex < 0) throw new Error("Config: expected key and value columns");

  const retained = [];
  const decisions = [];
  for (const row of sourceRows.slice(1)) {
    const key = text(row[keyIndex]);
    const value = text(row[valueIndex]);
    const meaning = meaningIndex < 0 ? "" : text(row[meaningIndex]);
    if (!key) continue;
    const normalized = key.toUpperCase();
    if (!value && row.filter((cell) => text(cell)).length === 1) {
      decisions.push({ config_key: key, source_value_present: false, migration_status: "NOT_APPLICABLE", target_value: "", reason: "Section label, not a configuration value." });
      continue;
    }
    let targetKey = key;
    let targetValue = value;
    let status = "RETIRED";
    let reason = "Not needed for the clean v2.1 workbook foundation.";
    if (normalized === "WINDOW_TZ") {
      targetKey = "SYSTEM_TIMEZONE";
      status = "RENAMED";
      reason = "Retains the common operating timezone without retaining prediction-window behavior.";
    } else if (normalized.endsWith("SPREADSHEET_ID")) {
      targetKey = normalized.replace(/_SPREADSHEET_ID$/, "_WORKBOOK_ID");
      targetValue = "INACTIVE_PLACEHOLDER";
      status = "RESET";
      reason = "Workbook routing is intentionally inactive pending an approved cutover.";
    } else if (/(SECRET|TOKEN|PASSWORD)/.test(normalized) || (/(API[_-]?KEY)/.test(normalized) && !/PROPERTY/.test(normalized))) {
      targetValue = "";
      status = "MANUAL_SECRET_REQUIRED";
      reason = "Secrets are never copied into the workbook.";
    } else if (/(PACK_[BCD]|PHASE|REPLAY|DIAGNOSTIC|REPAIR|HISTORICAL|EVALUATION|PIPS|PREDICTION_WINDOW|WINDOW)/.test(normalized)) {
      status = "RETIRED";
      reason = "Legacy experiment, replay, repair, scoring, or window setting.";
    } else if (/(TZ|TIMEZONE|PROVIDER|MODEL|FMP|FRED|EODHD|MARKET_DATA|EVENT|SERIESMAP|SOURCE|API_KEY_PROPERTY|KEY_PROPERTY)/.test(normalized)) {
      status = "MIGRATED";
      reason = "Reusable source, provider, model, mapping, or foundation setting.";
    }
    if (status === "RETIRED") targetValue = "";
    decisions.push({ config_key: targetKey, source_value_present: value !== "", migration_status: status, target_value: targetValue, reason });
    if (["MIGRATED", "RENAMED", "RESET", "MANUAL_SECRET_REQUIRED"].includes(status)) retained.push([targetKey, targetValue, meaning, status, key, reason]);
  }
  const existing = new Set(retained.map((row) => row[0]));
  for (const [key, reason] of [["PRESIGNAL_MAIN_WORKBOOK_ID", "Inactive destination identifier placeholder."], ["PRESIGNAL_RESEARCH_WORKBOOK_ID", "Inactive destination identifier placeholder."]]) {
    if (!existing.has(key)) {
      retained.push([key, "INACTIVE_PLACEHOLDER", "", "RESET", "", reason]);
      decisions.push({ config_key: key, source_value_present: false, migration_status: "RESET", target_value: "INACTIVE_PLACEHOLDER", reason });
    }
  }
  return { rows: [HEADERS.Config, ...retained], decisions };
}

function schemaRows() {
  const source = "Frozen v2.0 schema lineage";
  const row = (section, item, status, oldDef, newDef, reason) => ["2.1", "2.0", section, item, status, oldDef, newDef, reason, "ACTIVE", source, ""];
  return [HEADERS.Schema,
    row("Identity", "Provider/model lineage", "INHERITED", "Provider and model identify a forecast origin.", "Provider and model remain row-level lineage.", "Retain provenance."),
    row("Forecast", "Forecast cutoff", "INHERITED", "Forecast cutoff bounds information availability.", "Episode forecast cutoff bounds information availability.", "Preserve replay-safe timing."),
    row("Forecast", "Pack identity and fingerprint", "INHERITED", "Pack identity and fingerprint identify supplied context.", "Pack identity and fingerprint remain on Prediction.", "Preserve context lineage."),
    row("Drivers", "Primary/secondary driver identity", "INHERITED", "Primary and secondary drivers support clustered releases.", "Primary/secondary event identities are episode fields and copied to Prediction.", "Preserve causal context."),
    row("Drivers", "Same-time release cluster", "INHERITED", "Batch concept represents same-time releases.", "Episode represents a coherent same-time release cluster when selected.", "Preserve cluster handling."),
    row("Prediction", "Native Prediction", "INHERITED", "Prediction is a provider-level native output.", "Prediction is authoritative per episode x provider x information arm.", "Retain native output lineage."),
    row("Prediction", "Ordered Prediction Path", "INHERITED", "Prediction Path stores ordered reaction stages.", "Prediction_Path stores ordered 5/15/30/60-minute stages.", "Retain stage semantics."),
    row("Outcome", "Outcome provenance", "INHERITED", "Outcome records market-data provenance.", "Outcome records deterministic USD/JPY episode provenance.", "Retain auditability."),
    row("Evaluation", "Component-level Evaluation", "INHERITED", "Evaluation has component-level results.", "Evaluation stores event-path components and a primary endpoint.", "Retain explainability."),
    row("Prediction", "No-signal support", "INHERITED", "No-signal is a valid provider response.", "No-signal remains explicit in Prediction and Evaluation.", "Avoid forced forecasts."),
    row("Forecast", "Primary forecast object", "MODIFIED", "Market Session.", "Selected Event Episode or same-time Release Cluster.", "Make event reaction primary."),
    row("Evaluation", "Primary evaluation", "MODIFIED", "Session direction.", "EPISODE_REACTION_DIRECTION_15M (15-minute event-path direction).", "Use the specified primary endpoint."),
    row("Outcome", "Reaction horizons", "MODIFIED", "Previous fixed event reaction horizon.", "5, 15, 30, and 60 minutes.", "Represent the full event path."),
    row("Session", "Market Session", "MODIFIED", "Primary forecast and outcome object.", "Derived supporting Session_Map summary.", "Keep sessions secondary."),
    row("Identity", "episode_id", "NEW", "Not present.", "Deterministic episode identity field.", "Identify selected episodes."),
    row("Episode", "Selection status", "NEW", "Not present.", "FORECAST, WATCH, IGNORE, NO_SIGNAL, or PENDING.", "Make selection explicit."),
    row("Outcome", "Multi-horizon path and reversal", "NEW", "Not represented as an episode outcome contract.", "5/15/30/60-minute outcomes plus reversal fields.", "Evaluate paths and reversals."),
    row("Prediction", "Information arms", "NEW", "Multiple experiment Pack arms.", "BASELINE and FULL_CONTEXT only.", "Keep active comparison compact."),
    row("Retirement", "Broad-session headline evaluation", "RETIRED", "Direct broad-session headline evaluation.", "Not an active v2.1 object.", "Session is derived only."),
    row("Retirement", "Pack B/C/D active arms", "RETIRED", "Required active experiment arms.", "Not active; only BASELINE and FULL_CONTEXT.", "Remove experiment debt."),
    row("Retirement", "Populated v2.0 active tables", "RETIRED", "Active prediction/evaluation history in operational tabs.", "Frozen outside v2.1 workbook.", "Do not import historical rows."),
    row("Retirement", "Mechanism and repair tabs", "RETIRED", "Phase- and repair-specific operational sheets.", "Frozen diagnostic artifacts only.", "Keep the active workbook compact."),
  ];
}

function padRows(rows) {
  const width = Math.max(0, ...rows.map((row) => row.length));
  return rows.map((row) => Array.from({ length: width }, (_, index) => row[index] ?? ""));
}

async function addSheet(workbook, name, rows) {
  const sheet = workbook.worksheets.add(name);
  const matrix = padRows(rows);
  sheet.getRangeByIndexes(0, 0, matrix.length, matrix[0].length).values = matrix;
  const header = sheet.getRangeByIndexes(0, 0, 1, matrix[0].length);
  header.format.fill = "#1F4E78";
  header.format.font = { bold: true, color: "#FFFFFF" };
  header.format.wrapText = true;
  header.format.rowHeight = 30;
  header.format.columnWidth = 16;
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
}

async function writeWorkbook(sheetNames, sheetRows, targetPath) {
  const workbook = Workbook.create();
  for (const name of sheetNames) await addSheet(workbook, name, sheetRows[name]);
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(targetPath);
}

async function main() {
  const args = parseArgs(process.argv);
  const snapshot = JSON.parse(await fs.readFile(args.snapshot, "utf8"));
  const sourceEvent = sourceTable(snapshot, "Event");
  const sourceConfig = sourceTable(snapshot, "Config");
  const sourceSeriesMap = sourceTable(snapshot, "SeriesMap");
  const sourceFred = sourceTable(snapshot, "FRED_Series_ID");
  const sourceFmp = sourceTable(snapshot, "FMP_EventCatalog");
  const config = selectConfig(sourceConfig);
  const mainRows = {
    Event: sourceEvent,
    Config: config.rows,
    SeriesMap: sourceSeriesMap,
    SeriesMap_Suggestions: [HEADERS.SeriesMap_Suggestions],
    FRED_Series_ID: sourceFred,
    FMP_EventCatalog: sourceFmp,
    Episode: [HEADERS.Episode], Information: [HEADERS.Information], Prediction: [HEADERS.Prediction],
    Prediction_Path: [HEADERS.Prediction_Path], Outcome: [HEADERS.Outcome], Evaluation: [HEADERS.Evaluation],
    Session_Map: [HEADERS.Session_Map], Schema: schemaRows(), Run_Log: [HEADERS.Run_Log],
  };
  const researchRows = Object.fromEntries(RESEARCH_SHEETS.map((name) => [name, [HEADERS[name]]]));
  await writeWorkbook(MAIN_SHEETS, mainRows, args.main);
  await writeWorkbook(RESEARCH_SHEETS, researchRows, args.research);
  const targetRows = Object.fromEntries(Object.entries(mainRows).map(([name, rows]) => [name, rows.length]));
  Object.assign(targetRows, Object.fromEntries(Object.entries(researchRows).map(([name, rows]) => [name, rows.length])));
  const result = {
    source_table_fingerprints: Object.fromEntries(["Event", "Config", "SeriesMap", "FRED_Series_ID", "FMP_EventCatalog"].map((name) => [name, sha256(JSON.stringify(snapshot.source_tables[name]))])),
    target_rows: targetRows,
    config_decisions: config.decisions,
    main_sheets: MAIN_SHEETS,
    research_sheets: RESEARCH_SHEETS,
  };
  await fs.writeFile(args.result, `${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
