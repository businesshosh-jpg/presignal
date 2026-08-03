/**
 * automation_api.js
 * API-safe entrypoints for local automation via Apps Script Execution API.
 * These wrappers avoid menu/UI flows and operate on plain parameter objects.
 */

/** Harmless Execution API health endpoint. It performs no provider or sheet work. */
function presignalRuntimeHealthCheck() {
  return {
    status: 'READY',
    timestamp: new Date().toISOString(),
    script_version: 'HEAD',
    dev_mode: true
  };
}

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

function apiRunPredictionForEvent_(params) {
  params = params || {};
  var eventId = String(params.event_id || '').trim();
  if (!eventId) throw new Error('apiRunPredictionForEvent requires event_id.');
  var providers = _apiNormalizeProviderList_(params.providers);
  return {
    status: 'ok',
    prediction: runPredictionForEventId_(eventId, providers)
  };
}

function apiRunPredictionForEvent(params) {
  return apiRunPredictionForEvent_(params);
}

function apiRunMinimalDataAvailabilityAudit_() {
  return {
    status: 'ok',
    data_availability_audit: runMinimalDataAvailabilityAudit_()
  };
}

function apiRunMinimalDataAvailabilityAudit() {
  return apiRunMinimalDataAvailabilityAudit_();
}

function apiBuildMarketContextProviderRepairReport_() {
  return {
    status: 'ok',
    market_context_provider_repair_report: buildMarketContextProviderRepairReport_()
  };
}

function apiBuildMarketContextProviderRepairReport() {
  return apiBuildMarketContextProviderRepairReport_();
}

function apiBuildFeaturePackV2BCoreAudit_(params) {
  params = params || {};
  return {
    status: 'ok',
    feature_pack_v2b_core_audit: buildFeaturePackV2BCoreAudit_(params.event_ids || params.eventIds || null)
  };
}

function apiBuildFeaturePackV2BCoreAudit(params) {
  return apiBuildFeaturePackV2BCoreAudit_(params);
}

function apiBuildMarketContextDataSanityReport_() {
  return {
    status: 'ok',
    market_context_data_sanity_report: buildMarketContextDataSanityReport_()
  };
}

function apiBuildMarketContextDataSanityReport() {
  return apiBuildMarketContextDataSanityReport_();
}

function apiBuildMarketContextSourceValidationReport_() {
  return {
    status: 'ok',
    market_context_source_validation_report: buildMarketContextSourceValidationReport_()
  };
}

function apiBuildMarketContextSourceValidationReport() {
  return apiBuildMarketContextSourceValidationReport_();
}

function apiDebugFeaturePackForEvent_(params) {
  params = params || {};
  var eventId = String(params.event_id || params.eventId || '').trim();
  if (!eventId) throw new Error('apiDebugFeaturePackForEvent requires event_id.');
  return {
    status: 'ok',
    feature_pack: debugFeaturePackForEvent(eventId)
  };
}

function apiDebugFeaturePackForEvent(params) {
  return apiDebugFeaturePackForEvent_(params);
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

function apiBuildActiveDecisionReports_() {
  return {
    status: 'ok',
    active_decision_reports: buildActiveDecisionReports_()
  };
}

function apiBuildActiveDecisionReports() {
  return apiBuildActiveDecisionReports_();
}

function apiBuildProjectStatus_() {
  return {
    status: 'ok',
    project_status: buildProjectStatus_()
  };
}

function apiBuildProjectStatus() {
  return apiBuildProjectStatus_();
}

function apiBuildDecisionLog_() {
  return {
    status: 'ok',
    decision_log: buildDecisionLog_()
  };
}

function apiBuildDecisionLog() {
  return apiBuildDecisionLog_();
}

function apiReadWorkbookRoutingConfig_() {
  return {
    status: 'ok',
    workbook_routing_config: readWorkbookRoutingConfig_()
  };
}

function apiReadWorkbookRoutingConfig() {
  return apiReadWorkbookRoutingConfig_();
}

function apiRunControlledV2BReplayComparison_(params) {
  return {
    status: 'ok',
    controlled_v2b_replay_comparison: runControlledV2BReplayComparison_(params || {})
  };
}

function apiRunControlledV2BReplayComparison(params) {
  return apiRunControlledV2BReplayComparison_(params);
}

function apiBuildControlledV2BReplaySummary_() {
  return {
    status: 'ok',
    controlled_v2b_replay_summary: buildControlledV2BReplaySummary_()
  };
}

function apiBuildControlledV2BReplaySummary() {
  return apiBuildControlledV2BReplaySummary_();
}

function apiProbeMarketContextCrudeSymbols_() {
  var warnings = [];
  var out = {};
  var eodKey = null;
  try { eodKey = _getEodhdApiKey_(); } catch (e) {}
  var fmpKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  var fmpBase = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  if (eodKey && typeof _mcprSafeEodhdSearch_ === 'function') {
    out.eodhd = _mcprSafeEodhdSearch_('crude oil', eodKey, warnings).symbols || [];
  }
  if (fmpKey && typeof _mcprSafeFmpSearch_ === 'function') {
    out.fmp = _mcprSafeFmpSearch_('crude oil', fmpKey, fmpBase, warnings).symbols || [];
  }
  return { status: 'ok', crude_symbol_search: out, warnings: warnings };
}

function apiProbeMarketContextCrudeSymbols() {
  return apiProbeMarketContextCrudeSymbols_();
}

function apiProbeHistoricalPrices_(params) {
  params = params || {};
  var symbols = Array.isArray(params.symbols) ? params.symbols : [];
  var provider = String(params.provider || 'fmp').toLowerCase();
  var fromDate = String(params.from_date || '2024-05-01');
  var toDate = String(params.to_date || '2024-07-10');
  var out = [];
  for (var i = 0; i < symbols.length; i++) {
    var symbol = String(symbols[i] || '').trim();
    if (!symbol) continue;
    try {
      if (provider === 'fmp') {
        var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
        var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
        var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, fromDate, toDate) || [];
        out.push({
          symbol: symbol,
          provider: 'fmp',
          row_count: rows.length,
          first_date: rows.length ? rows[rows.length - 1].date : '',
          last_date: rows.length ? rows[0].date : '',
          sample_first: rows.length ? rows[rows.length - 1] : null,
          sample_last: rows.length ? rows[0] : null
        });
      } else {
        var eodKey = _getEodhdApiKey_();
        var rowsEod = _eodhdFetchEodWindow_(symbol, eodKey, fromDate, toDate, 'a') || [];
        out.push({
          symbol: symbol,
          provider: 'eodhd',
          row_count: rowsEod.length,
          first_date: rowsEod.length ? rowsEod[0].date : '',
          last_date: rowsEod.length ? rowsEod[rowsEod.length - 1].date : '',
          sample_first: rowsEod.length ? rowsEod[0] : null,
          sample_last: rowsEod.length ? rowsEod[rowsEod.length - 1] : null
        });
      }
    } catch (e) {
      out.push({ symbol: symbol, provider: provider, error: String(e) });
    }
  }
  return { status: 'ok', provider: provider, from_date: fromDate, to_date: toDate, results: out };
}

function apiProbeHistoricalPrices(params) {
  return apiProbeHistoricalPrices_(params);
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

function apiBuildCharacterResidualArchitecture_() {
  return {
    status: 'ok',
    character_residual_architecture: buildCharacterResidualArchitecture_()
  };
}

function apiBuildCharacterResidualArchitecture() {
  return apiBuildCharacterResidualArchitecture_();
}

function apiBuildCharacterRecurrenceValidation_() {
  return {
    status: 'ok',
    character_recurrence_validation: buildCharacterRecurrenceValidation_()
  };
}

function apiBuildCharacterRecurrenceValidation() {
  return apiBuildCharacterRecurrenceValidation_();
}

function apiBuildProviderCharacterEconomicOutcomeLink_() {
  return {
    status: 'ok',
    provider_character_economic_outcome_link: buildProviderCharacterEconomicOutcomeLink_()
  };
}

function apiBuildProviderCharacterEconomicOutcomeLink(params) {
  return apiBuildProviderCharacterEconomicOutcomeLink_();
}

function apiBuildProviderCharacterEconomicFalsification_() {
  return {
    status: 'ok',
    provider_character_economic_falsification: buildProviderCharacterEconomicFalsification_()
  };
}

function apiBuildProviderCharacterEconomicFalsification(params) {
  return apiBuildProviderCharacterEconomicFalsification_();
}

function apiBuildProviderCharacterMicroExpressionPilot_() {
  return {
    status: 'ok',
    provider_character_micro_expression_pilot: buildProviderCharacterMicroExpressionPilot_()
  };
}

function apiBuildProviderCharacterMicroExpressionPilot(params) {
  return apiBuildProviderCharacterMicroExpressionPilot_();
}

function apiBuildProviderCharacterRawOutputMicroExpressionReplay_() {
  return {
    status: 'ok',
    provider_character_raw_output_micro_expression_replay: buildProviderCharacterRawOutputMicroExpressionReplay_()
  };
}

function apiBuildProviderCharacterRawOutputMicroExpressionReplay(params) {
  return apiBuildProviderCharacterRawOutputMicroExpressionReplay_();
}

function apiBuildProviderCharacterFreshVsOriginalReplay_() {
  return {
    status: 'ok',
    provider_character_fresh_vs_original_micro_expression_replay: buildProviderCharacterFreshVsOriginalReplay_()
  };
}

function apiBuildProviderCharacterFreshVsOriginalReplay(params) {
  return apiBuildProviderCharacterFreshVsOriginalReplay_();
}

function apiBuildProviderCharacterDirectExpressionCapture_() {
  return {
    status: 'ok',
    provider_character_direct_expression_capture: buildProviderCharacterDirectExpressionCapture_({})
  };
}

function apiBuildProviderCharacterDirectExpressionCapture(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_capture: buildProviderCharacterDirectExpressionCapture_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionRandomCohort_() {
  return {
    status: 'ok',
    provider_character_direct_expression_random_cohort: buildProviderCharacterDirectExpressionRandomCohort_({})
  };
}

function apiBuildProviderCharacterDirectExpressionRandomCohort(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_random_cohort: buildProviderCharacterDirectExpressionRandomCohort_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionRecurrence_() {
  return {
    status: 'ok',
    provider_character_direct_expression_recurrence: buildProviderCharacterDirectExpressionRecurrence_()
  };
}

function apiBuildProviderCharacterDirectExpressionRecurrence(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_recurrence: buildProviderCharacterDirectExpressionRecurrence_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionEconomicLink_() {
  return {
    status: 'ok',
    provider_character_direct_expression_economic_link: buildProviderCharacterDirectExpressionEconomicLink_({})
  };
}

function apiBuildProviderCharacterDirectExpressionEconomicLink(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_economic_link: buildProviderCharacterDirectExpressionEconomicLink_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionValidation_() {
  return {
    status: 'ok',
    provider_character_direct_expression_validation: buildProviderCharacterDirectExpressionValidation_()
  };
}

function apiBuildProviderCharacterDirectExpressionValidation(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_validation: buildProviderCharacterDirectExpressionValidation_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionMicrocohortRerun_() {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_rerun: buildProviderCharacterDirectExpressionMicrocohortRerun_()
  };
}

function apiBuildProviderCharacterDirectExpressionMicrocohortRerun(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_rerun: buildProviderCharacterDirectExpressionMicrocohortRerun_(params || {})
  };
}

function apiListProviderCharacterDirectExpressionMicrocohortEligibleRows_(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_eligible_rows: listProviderCharacterDirectExpressionMicrocohortEligibleRows_(params || {})
  };
}

function apiListProviderCharacterDirectExpressionMicrocohortEligibleRows(params) {
  return apiListProviderCharacterDirectExpressionMicrocohortEligibleRows_(params);
}

function apiBuildProviderCharacterDirectExpressionEligibilityAudit_() {
  return {
    status: 'ok',
    provider_character_direct_expression_eligibility_audit: buildProviderCharacterDirectExpressionEligibilityAudit_({})
  };
}

function apiBuildProviderCharacterDirectExpressionEligibilityAudit(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_eligibility_audit: buildProviderCharacterDirectExpressionEligibilityAudit_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionOutcomeCheck_() {
  return {
    status: 'ok',
    provider_character_direct_expression_outcome_check: buildProviderCharacterDirectExpressionOutcomeCheck_()
  };
}

function apiBuildProviderCharacterDirectExpressionOutcomeCheck(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_outcome_check: buildProviderCharacterDirectExpressionOutcomeCheck_(params || {})
  };
}

function apiBuildSignalSynchronyCohortCharacterization_() {
  return {
    status: 'ok',
    signal_synchrony_cohort_characterization: buildSignalSynchronyCohortCharacterization_()
  };
}

function apiBuildSignalSynchronyCohortCharacterization(params) {
  return {
    status: 'ok',
    signal_synchrony_cohort_characterization: buildSignalSynchronyCohortCharacterization_(params || {})
  };
}

function apiBuildAttentionProviderIndividuality_() {
  return {
    status: 'ok',
    attention_provider_individuality: buildAttentionProviderIndividuality_()
  };
}

function apiBuildAttentionProviderIndividuality() {
  return apiBuildAttentionProviderIndividuality_();
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

function apiBuildFamilyStructureReport_() {
  return {
    status: 'ok',
    family_structure_report: buildFamilyStructureReport_()
  };
}

function apiBuildFamilyStructureReport() {
  return apiBuildFamilyStructureReport_();
}

function apiBuildBatchSplittingCandidates_() {
  return {
    status: 'ok',
    batch_splitting_candidates: buildBatchSplittingCandidates_()
  };
}

function apiBuildBatchSplittingCandidates() {
  return apiBuildBatchSplittingCandidates_();
}

function apiBuildBatchSplitCounterfactuals_() {
  return {
    status: 'ok',
    batch_split_counterfactuals: buildBatchSplitCounterfactuals_()
  };
}

function apiBuildBatchSplitCounterfactuals() {
  return apiBuildBatchSplitCounterfactuals_();
}

function apiBuildBatchBaselineCoverageAudit_() {
  return {
    status: 'ok',
    batch_baseline_coverage_audit: buildBatchBaselineCoverageAudit_()
  };
}

function apiBuildBatchBaselineCoverageAudit() {
  return apiBuildBatchBaselineCoverageAudit_();
}

function apiBuildBatchSplitGroupCounterfactuals_() {
  return {
    status: 'ok',
    batch_split_group_counterfactuals: buildBatchSplitGroupCounterfactuals_()
  };
}

function apiBuildBatchSplitGroupCounterfactuals() {
  return apiBuildBatchSplitGroupCounterfactuals_();
}

function apiBuildEconomicValueAccuracy_() {
  return {
    status: 'ok',
    economic_value_accuracy: buildEconomicValueAccuracy_()
  };
}

function apiBuildEconomicValueAccuracy() {
  return apiBuildEconomicValueAccuracy_();
}

function apiBuildAttentionEconomicValueReport_() {
  return {
    status: 'ok',
    attention_economic_value_report: buildAttentionEconomicValueReport_()
  };
}

function apiBuildAttentionEconomicValueReport() {
  return apiBuildAttentionEconomicValueReport_();
}

function apiRunAttentionV3ReplayExperiment_(params) {
  return {
    status: 'ok',
    attention_v3_replay_experiment: runAttentionV3ReplayExperiment_(params || {})
  };
}

function apiRunAttentionV3ReplayExperiment(params) {
  return apiRunAttentionV3ReplayExperiment_(params);
}

function apiRunAttentionC0ReliabilityReplay_(params) {
  return {
    status: 'ok',
    attention_c0_reliability_replay: runAttentionC0ReliabilityReplay_(params || {})
  };
}

function apiRunAttentionC0ReliabilityReplay(params) {
  return apiRunAttentionC0ReliabilityReplay_(params);
}

function apiBuildProviderFamilyEconomicAccuracy_() {
  return {
    status: 'ok',
    provider_family_economic_accuracy: buildProviderFamilyEconomicAccuracy_()
  };
}

function apiBuildProviderFamilyEconomicAccuracy() {
  return apiBuildProviderFamilyEconomicAccuracy_();
}

function apiBuildEconomicToMarketTranslationErrors_() {
  return {
    status: 'ok',
    economic_to_market_translation_errors: buildEconomicToMarketTranslationErrors_()
  };
}

function apiBuildEconomicToMarketTranslationErrors() {
  return apiBuildEconomicToMarketTranslationErrors_();
}

function apiBuildMarketSensitivityFilterCandidates_() {
  return {
    status: 'ok',
    market_sensitivity_filter_candidates: buildMarketSensitivityFilterCandidates_()
  };
}

function apiBuildMarketSensitivityFilterCandidates() {
  return apiBuildMarketSensitivityFilterCandidates_();
}

function apiBuildMarketSensitivityFilterSummary_() {
  return {
    status: 'ok',
    market_sensitivity_filter_summary: buildMarketSensitivityFilterSummary_()
  };
}

function apiBuildMarketSensitivityFilterSummary() {
  return apiBuildMarketSensitivityFilterSummary_();
}

function apiBuildMarketSensitivityNoSignalCounterfactuals_() {
  return {
    status: 'ok',
    market_sensitivity_no_signal_counterfactuals: buildMarketSensitivityNoSignalCounterfactuals_()
  };
}

function apiBuildMarketSensitivityNoSignalCounterfactuals() {
  return apiBuildMarketSensitivityNoSignalCounterfactuals_();
}

function apiBuildInflationNoSignalReview_() {
  return {
    status: 'ok',
    inflation_no_signal_review: buildInflationNoSignalReview_()
  };
}

function apiBuildInflationNoSignalReview() {
  return apiBuildInflationNoSignalReview_();
}

function apiUpsertEventWindow_(params) {
  params = params || {};

  var operationId = String(params.operation_id || '').trim();
  var authorizationId = String(params.authorization_id || '').trim();
  var sourceWindowFingerprint = String(params.source_window_fingerprint || '').trim();
  if (!operationId || !authorizationId || !sourceWindowFingerprint) {
    throw new Error('apiUpsertEventWindow requires operation_id, authorization_id, and source_window_fingerprint.');
  }
  var invocationId = Utilities.getUuid();
  var dispatchTimestamp = new Date().toISOString();
  var preSheetFingerprint = apiEventSheetFingerprint_();

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

  var postSheetFingerprint = apiEventSheetFingerprint_();
  var completionTimestamp = new Date().toISOString();
  var statusCounts = apiEventStatusCounts_();
  return {
    status: 'ok',
    terminal_status: 'COMPLETED',
    remote_state: 'CERTAIN',
    operation_id: operationId,
    invocation_id: invocationId,
    authorization_id: authorizationId,
    source_window_fingerprint: sourceWindowFingerprint,
    pre_refresh_event_sheet_fingerprint: preSheetFingerprint,
    post_refresh_event_sheet_fingerprint: postSheetFingerprint,
    dispatch_timestamp: dispatchTimestamp,
    completion_timestamp: completionTimestamp,
    window_from_utc: fromUtcIso,
    window_to_utc: toUtcIso,
    upsert: upsert,
    batching: batching,
    status_counts: statusCounts
  };
}

function apiEventSheetFingerprint_() {
  var sheet = getEventSheet();
  var values = sheet.getDataRange().getValues();
  var payload = JSON.stringify(values);
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, payload, Utilities.Charset.UTF_8);
  return 'sha256:' + bytes.map(function(byte) { var value = (byte < 0 ? byte + 256 : byte).toString(16); return value.length === 1 ? '0' + value : value; }).join('');
}

function apiEventStatusCounts_() {
  var sheet = getEventSheet();
  var values = sheet.getDataRange().getValues();
  if (!values.length) return {scheduled: 0, released: 0, cancelled: 0, superseded: 0, rejected: 0};
  var headers = values[0].map(function(value) { return String(value || '').trim().toLowerCase(); });
  var index = headers.indexOf('release_status');
  var counts = {scheduled: 0, released: 0, cancelled: 0, superseded: 0, rejected: 0};
  if (index < 0) return counts;
  values.slice(1).forEach(function(row) { var status = String(row[index] || '').trim().toLowerCase(); if (Object.prototype.hasOwnProperty.call(counts, status)) counts[status]++; });
  return counts;
}

function apiUpsertEventWindow(params) {
  return apiUpsertEventWindow_(params);
}

/** Read-only deployment verification for the schedule-refresh attribution contract. */
function apiGetScheduleRefreshAttributionContract() {
  return {
    status: 'READY',
    contract_version: 'presignal_r2_schedule_refresh_attribution_v1',
    canonical_function: 'apiUpsertEventWindow_',
    required_request_fields: ['operation_id', 'authorization_id', 'source_window_fingerprint'],
    required_response_fields: ['operation_id', 'invocation_id', 'authorization_id', 'source_window_fingerprint', 'pre_refresh_event_sheet_fingerprint', 'post_refresh_event_sheet_fingerprint', 'dispatch_timestamp', 'completion_timestamp', 'upsert', 'status_counts', 'terminal_status', 'remote_state'],
    event_semantics_changed: false
  };
}

function apiDiagnoseProspectiveEventIdentityRuntime(payload) {
  var out = {status: 'error', last_stage: 'ENTRYPOINT_STARTED', spreadsheet_id: '', spreadsheet_name: '', sheet_name: '', sheet_row_count: 0, normalized_header_map: {}, event_id_column: -1, batch_id_column: -1, type_column: -1, future_rows_found: 0, eligible_rows_found: 0, missing_event_id_before: 0, missing_batch_id_before: 0, missing_type_before: 0, flush_completed: false, postpass_called: false, postpass_argument_mode: 'undefined_all_rows', postpass_return_type: '', postpass_return_value: null, updated_keys_count: 0, missing_event_id_after: 0, missing_batch_id_after: 0, missing_type_after: 0, writeback_detected: false, error_name: '', error_message: '', error_stage: ''};
  try {
    var ss = SpreadsheetApp.getActive(); out.last_stage = 'SPREADSHEET_RESOLVED'; out.spreadsheet_id = String(ss.getId()); out.spreadsheet_name = String(ss.getName());
    var sh = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event'); if (!sh) throw new Error('EVENT_SHEET_MISSING');
    out.last_stage = 'EVENT_SHEET_RESOLVED'; out.sheet_name = String(sh.getName()); out.sheet_row_count = Number(sh.getLastRow());
    var values = sh.getDataRange().getValues(), headers = (values[0] || []).map(function(h){ return String(h || '').trim().toLowerCase(); });
    headers.forEach(function(h, i){ out.normalized_header_map[h] = i + 1; }); out.event_id_column = headers.indexOf('event_id') + 1; out.batch_id_column = headers.indexOf('batch_id') + 1; out.type_column = headers.indexOf('type') + 1; out.last_stage = 'HEADERS_RESOLVED';
    var cTs=headers.indexOf('release_ts'), cE=out.event_id_column-1, cB=out.batch_id_column-1, cT=out.type_column-1, now=Date.now();
    function count(rows, after) { rows.slice(1).forEach(function(r){ var d=new Date(r[cTs]); if (!isNaN(d) && d.getTime()>now) { out.future_rows_found++; if (!String(r[cE]||'') || !String(r[cB]||'') || !String(r[cT]||'')) { out.eligible_rows_found++; out['missing_event_id_'+after] += !String(r[cE]||'') ? 1 : 0; out['missing_batch_id_'+after] += !String(r[cB]||'') ? 1 : 0; out['missing_type_'+after] += !String(r[cT]||'') ? 1 : 0; } } }); }
    count(values, 'before'); out.last_stage = 'FUTURE_ROWS_IDENTIFIED'; SpreadsheetApp.flush(); out.flush_completed = true; out.last_stage = 'PRE_FLUSH_COMPLETE';
    out.postpass_called = true; out.last_stage = 'POSTPASS_INVOKED'; var result = applyBatchingForKeys_(sh, undefined); out.postpass_return_type = typeof result; out.postpass_return_value = result || null; out.updated_keys_count = result && result.updatedKeys ? result.updatedKeys.length : 0; out.last_stage = 'POSTPASS_RETURNED';
    values = sh.getDataRange().getValues(); out.future_rows_found=0; count(values, 'after'); out.writeback_detected = out.missing_event_id_after < out.missing_event_id_before || out.missing_batch_id_after < out.missing_batch_id_before || out.missing_type_after < out.missing_type_before; out.last_stage = 'POST_REPAIR_READ_COMPLETE'; out.status = 'ok'; out.last_stage = 'ENTRYPOINT_RETURNED'; return out;
  } catch (e) { out.error_name = String(e && e.name || 'Error'); out.error_message = String(e && e.message || e); out.error_stage = out.last_stage; out.last_stage = 'POSTPASS_THROWN'; return out; }
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
