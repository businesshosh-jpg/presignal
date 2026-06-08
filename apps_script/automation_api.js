/**
 * automation_api.js
 * API-safe entrypoints for local automation via Apps Script Execution API.
 * These wrappers avoid menu/UI flows and operate on plain parameter objects.
 */

function apiRunPredictionsWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var providers = _apiNormalizeProviderList_(params.providers);
  var passes = _apiRunPredictionsPasses_({
    providers: providers,
    clearCheckpoint: params.clear_checkpoint !== false,
    continueUntilDone: params.continue_until_done !== false,
    maxPasses: Number(params.max_passes || 12)
  });
  return {
    status: passes.final && passes.final.status || 'ok',
    config_applied: applied,
    prediction_passes: passes.passes,
    prediction_final: passes.final
  };
}

function apiRunPredictionsWindow(params) {
  return apiRunPredictionsWindow_(params);
}

function apiFetchActualsWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var win = resolveWindow_('actuals_api');
  if (!win || !win.windowEnabled) {
    throw new Error('Automation actuals run requires WINDOW_ENABLED with valid FROM/TO.');
  }
  return {
    status: 'ok',
    config_applied: applied,
    actuals: runFetchActualsWindowBounds_(
      win.fromUtcIso,
      win.toUtcIso,
      Number(params.actuals_row_cap || params.row_cap || 2000)
    )
  };
}

function apiFetchActualsWindow(params) {
  return apiFetchActualsWindow_(params);
}

function apiScoreMarketReactionWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  return {
    status: 'ok',
    config_applied: applied,
    market_reaction: scoreMarketReactionByConfigWindow_()
  };
}

function apiScoreMarketReactionWindow(params) {
  return apiScoreMarketReactionWindow_(params);
}

function apiBuildEvaluationSheets_() {
  return {
    status: 'ok',
    evaluation: buildEvaluationSheets_()
  };
}

function apiBuildEvaluationSheets() {
  return apiBuildEvaluationSheets_();
}

function apiBuildOutcomeLedgerSheet_() {
  return {
    status: 'ok',
    outcome_ledger: buildOutcomeLedger_()
  };
}

function apiBuildOutcomeLedgerSheet() {
  return apiBuildOutcomeLedgerSheet_();
}

function apiBuildOutcomeLedger_() {
  return apiBuildOutcomeLedgerSheet_();
}

function apiBuildOutcomeSummaries_() {
  return {
    status: 'ok',
    outcome_summaries: buildOutcomeSummaries_()
  };
}

function apiBuildOutcomeSummaries() {
  return apiBuildOutcomeSummaries_();
}

function apiBuildOutcomeDiagnostics_() {
  return {
    status: 'ok',
    outcome_diagnostics: buildOutcomeDiagnostics_()
  };
}

function apiBuildOutcomeDiagnostics() {
  return apiBuildOutcomeDiagnostics_();
}

function apiBuildAttentionFactorSummary_() {
  return {
    status: 'ok',
    attention_factor_summary: buildAttentionFactorSummary_()
  };
}

function apiBuildAttentionFactorSummary() {
  return apiBuildAttentionFactorSummary_();
}

function apiBuildProviderCharacterDiagnostics_() {
  return {
    status: 'ok',
    provider_character_diagnostics: buildProviderCharacterDiagnostics_()
  };
}

function apiBuildProviderCharacterDiagnostics() {
  return apiBuildProviderCharacterDiagnostics_();
}

function apiBuildAttentionEvidenceReport_() {
  return {
    status: 'ok',
    attention_evidence_report: buildAttentionEvidenceReport_()
  };
}

function apiBuildAttentionEvidenceReport() {
  return apiBuildAttentionEvidenceReport_();
}

function apiBuildAttentionBlockStability_() {
  return {
    status: 'ok',
    attention_block_stability: buildAttentionBlockStability_()
  };
}

function apiBuildAttentionBlockStability() {
  return apiBuildAttentionBlockStability_();
}

function apiBuildAttentionDisagreementReview_() {
  return {
    status: 'ok',
    attention_disagreement_review: buildAttentionDisagreementReview_()
  };
}

function apiBuildAttentionDisagreementReview() {
  return apiBuildAttentionDisagreementReview_();
}

function apiBuildAttentionDisagreementSummary_() {
  return {
    status: 'ok',
    attention_disagreement_summary: buildAttentionDisagreementSummary_()
  };
}

function apiBuildAttentionDisagreementSummary() {
  return apiBuildAttentionDisagreementSummary_();
}

function apiBuildAttentionPhase3Candidates_() {
  return {
    status: 'ok',
    attention_phase3_candidates: buildAttentionPhase3Candidates_()
  };
}

function apiBuildAttentionPhase3Candidates() {
  return apiBuildAttentionPhase3Candidates_();
}

function apiBuildAttentionShadowExperiments_() {
  return {
    status: 'ok',
    attention_shadow_experiments: buildAttentionShadowExperiments_()
  };
}

function apiBuildAttentionShadowExperiments() {
  return apiBuildAttentionShadowExperiments_();
}

function apiUpsertEventWindow_(params) {
  params = params || {};

  var fromUtcIso = String(
    params.from_utc_iso ||
    params.window_from_utc ||
    params.from_utc ||
    params.fromUtcIso ||
    ''
  ).trim();
  var toUtcIso = String(
    params.to_utc_iso ||
    params.window_to_utc ||
    params.to_utc ||
    params.toUtcIso ||
    ''
  ).trim();

  if (!fromUtcIso || !toUtcIso) {
    throw new Error('apiUpsertEventWindow requires from_utc_iso and to_utc_iso.');
  }

  var upsert = runFmpRangeToEvent_(fromUtcIso, toUtcIso);
  var batching = (typeof applyBatchingForKeys_ === 'function')
    ? applyBatchingForKeys_()
    : null;

  return {
    status: 'ok',
    window_from_utc: fromUtcIso,
    window_to_utc: toUtcIso,
    upsert: upsert,
    batching: batching
  };
}

function apiUpsertEventWindow(params) {
  return apiUpsertEventWindow_(params);
}

function apiRunPipelineWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var out = {
    status: 'ok',
    config_applied: applied,
    steps: {}
  };

  if (params.run_predictions !== false) {
    var providers = _apiNormalizeProviderList_(params.providers);
    var predictionRun = _apiRunPredictionsPasses_({
      providers: providers,
      clearCheckpoint: params.clear_checkpoint !== false,
      continueUntilDone: params.continue_until_done !== false,
      maxPasses: Number(params.max_passes || 12)
    });
    out.steps.predictions = {
      passes: predictionRun.passes,
      final: predictionRun.final
    };
    if (predictionRun.final && predictionRun.final.status === 'partial') {
      out.status = 'partial';
    }
  }

  if (params.run_actuals) {
    var win = resolveWindow_('actuals_api');
    if (!win || !win.windowEnabled) {
      throw new Error('Automation actuals run requires WINDOW_ENABLED with valid FROM/TO.');
    }
    out.steps.actuals = runFetchActualsWindowBounds_(
      win.fromUtcIso,
      win.toUtcIso,
      Number(params.actuals_row_cap || params.row_cap || 2000)
    );
  }

  if (params.run_market_reaction) {
    out.steps.market_reaction = scoreMarketReactionByConfigWindow_();
  }

  if (params.build_evaluation !== false) {
    out.steps.evaluation = buildEvaluationSheets_();
  }

  return out;
}

function apiRunPipelineWindow(params) {
  return apiRunPipelineWindow_(params);
}

function _apiRunPredictionsPasses_(opts) {
  opts = opts || {};
  var passes = [];
  var providers = opts.providers || null;
  var maxPasses = Math.max(1, Number(opts.maxPasses || 12));

  if (opts.clearCheckpoint && typeof menuClearPredictionCheckpoint_ === 'function') {
    menuClearPredictionCheckpoint_();
  }

  var finalSummary = null;
  for (var i = 0; i < maxPasses; i++) {
    finalSummary = runPredictionsCore_({
      windowMinBeforeMin: CFG.WINDOW_MIN_BEFORE_MIN,
      windowMaxAfterMin: CFG.WINDOW_MAX_AFTER_MIN,
      providers: providers,
      autoContinueEnabledOverride: false
    });
    passes.push(finalSummary);
    if (!opts.continueUntilDone) break;
    if (!finalSummary || finalSummary.status !== 'partial' || !Number(finalSummary.remaining_work_units || 0)) {
      break;
    }
  }

  return {
    passes: passes,
    final: finalSummary
  };
}

function _apiApplyWindowConfig_(params) {
  params = params || {};
  var tz = String(
    params.window_tz ||
    params.tz ||
    params.pred_window_tz ||
    params.mr_window_tz ||
    'Asia/Tokyo'
  ).trim();
  var fromLocal = _apiFirstNonEmpty_([
    params.window_from_local,
    params.from_local,
    params.from
  ]);
  var toLocal = _apiFirstNonEmpty_([
    params.window_to_local,
    params.to_local,
    params.to
  ]);
  if (!fromLocal || !toLocal) {
    throw new Error('Automation window params require window_from_local and window_to_local.');
  }

  var predEnabled = params.pred_window_enabled;
  if (predEnabled == null) predEnabled = true;
  var mrEnabled = params.mr_window_enabled;
  if (mrEnabled == null) mrEnabled = true;

  var entries = {
    WINDOW_ENABLED: 'TRUE',
    WINDOW_FROM_LOCAL: String(fromLocal),
    WINDOW_TO_LOCAL: String(toLocal),
    WINDOW_TZ: tz,
    PRED_WINDOW_ENABLED: predEnabled ? 'TRUE' : 'FALSE',
    PRED_WINDOW_FROM_LOCAL: String(_apiFirstNonEmpty_([params.pred_window_from_local, fromLocal])),
    PRED_WINDOW_TO_LOCAL: String(_apiFirstNonEmpty_([params.pred_window_to_local, toLocal])),
    PRED_WINDOW_TZ: String(_apiFirstNonEmpty_([params.pred_window_tz, tz])),
    MR_WINDOW_ENABLED: mrEnabled ? 'TRUE' : 'FALSE',
    MR_WINDOW_FROM_LOCAL: String(_apiFirstNonEmpty_([params.mr_window_from_local, fromLocal])),
    MR_WINDOW_TO_LOCAL: String(_apiFirstNonEmpty_([params.mr_window_to_local, toLocal])),
    MR_WINDOW_TZ: String(_apiFirstNonEmpty_([params.mr_window_tz, tz]))
  };
  _apiUpsertConfigEntries_(entries);
  return entries;
}

function _apiUpsertConfigEntries_(entries) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(CONFIG_SHEET_NAME || 'Config');
  if (!sh) throw new Error('Config sheet not found');

  var lastRow = Math.max(1, sh.getLastRow());
  var values = sh.getRange(1, 1, lastRow, 2).getValues();
  if (!values.length) values = [['key', 'value']];

  var rowByKey = {};
  for (var i = 1; i < values.length; i++) {
    var key = String(values[i][0] || '').trim();
    if (key) rowByKey[key] = i + 1;
  }

  var updates = [];
  var appends = [];
  Object.keys(entries || {}).forEach(function(key) {
    var value = entries[key];
    if (rowByKey[key]) {
      updates.push({ row: rowByKey[key], value: value });
    } else {
      appends.push([key, value]);
    }
  });

  for (var u = 0; u < updates.length; u++) {
    sh.getRange(updates[u].row, 2).setValue(updates[u].value);
  }
  if (appends.length) {
    sh.getRange(sh.getLastRow() + 1, 1, appends.length, 2).setValues(appends);
  }
}

function _apiNormalizeProviderList_(providers) {
  if (!providers || !providers.length) return null;
  return providers.map(function(p){ return _normalizeProviderName_(p); }).filter(Boolean);
}

function _apiFirstNonEmpty_(values) {
  values = values || [];
  for (var i = 0; i < values.length; i++) {
    var v = values[i];
    if (v != null && String(v).trim() !== '') return v;
  }
  return '';
}
