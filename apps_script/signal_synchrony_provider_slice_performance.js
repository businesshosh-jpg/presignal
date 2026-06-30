/*******************************************************
 * signal_synchrony_provider_slice_performance.js
 * - Diagnostic-only Signal Synchrony v1 - Provider Slice Performance Audit
 * - Descriptive provider-slice performance audit over existing Direct Expression results
 * - No provider calls, no reruns, no routing / weighting / calibration approval
 *******************************************************/

function buildSignalSynchronyProviderSlicePerformance_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var warnings = [];

  try {
    var sources = _signalSynchronyProviderSlicePerformanceLoadSources_(warnings);
    var captureRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.captureBundle);
    var validationRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.validationBundle);
    var outcomeRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.outcomeBundle);
    var cohortRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.cohortBundle);
    var sufficiencyRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.sufficiencyBundle);
    var eventRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.eventBundle);

    var captureIndex = _signalSynchronyProviderSlicePerformanceBuildCaptureIndex_(captureRows);
    var validationIndex = _signalSynchronyProviderSlicePerformanceBuildValidationIndex_(validationRows);
    var microcohortRows = _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(sources.microcohortBundle);
    var outcomeIndex = _signalSynchronyProviderSlicePerformanceBuildKeyIndexSafe_(outcomeRows, 'sample_group_id');
    var cohortIndex = _signalSynchronyProviderSlicePerformanceBuildKeyIndexSafe_(cohortRows, 'sample_group_id');
    var sufficiencyIndex = _signalSynchronyProviderSlicePerformanceBuildKeyIndexSafe_(sufficiencyRows, 'sample_group_id');
    var eventIndex = _signalSynchronyProviderSlicePerformanceBuildEventIndexSafe_(eventRows);

    var auditRows = _signalSynchronyProviderSlicePerformanceBuildAuditRows_(
      generatedTs,
      microcohortRows,
      captureIndex,
      validationIndex,
      outcomeIndex,
      cohortIndex,
      sufficiencyIndex,
      eventIndex,
      warnings
    );
    var summaryRows = _signalSynchronyProviderSlicePerformanceBuildSummaryRows_(generatedTs, auditRows, warnings);

    var auditSheet = getDiagnosticsSheet_(
      'Signal_Synchrony_Provider_Slice_Performance',
      _signalSynchronyProviderSlicePerformanceAuditHeaders_(),
      warnings
    );
    var summarySheet = getDiagnosticsSheet_(
      'Signal_Synchrony_Provider_Slice_Summary',
      _signalSynchronyProviderSlicePerformanceSummaryHeaders_(),
      warnings
    );

    _rewriteSheetRowsPreservingHeaders_(
      auditSheet.sheet,
      auditSheet.headers,
      _characterResidualObjectsToRows_(auditRows, auditSheet.headers)
    );
    _rewriteSheetRowsPreservingHeaders_(
      summarySheet.sheet,
      summarySheet.headers,
      _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
    );

    return {
      status: 'ok',
      generated_ts: generatedTs,
      audit_sheet: auditSheet.sheet.getName(),
      summary_sheet: summarySheet.sheet.getName(),
      audit_rows_written: auditRows.length,
      summary_rows_written: summaryRows.length,
      unique_events: _signalSynchronyProviderSlicePerformanceCountUniqueEvents_(auditRows),
      providers_present: _signalSynchronyProviderSlicePerformanceCountProviders_(auditRows),
      cohorts_present: _signalSynchronyProviderSlicePerformanceCountCohorts_(auditRows),
      comparable_rows: _signalSynchronyProviderSlicePerformanceCountComparable_(auditRows),
      provider_overall_rows: _signalSynchronyProviderSlicePerformanceCountRowsBySection_(summaryRows, 'A'),
      candidate_strength_count: _signalSynchronyProviderSlicePerformanceCountByReadiness_(summaryRows, 'ROUTING_CANDIDATE_SHADOW_ONLY'),
      candidate_watch_count: _signalSynchronyProviderSlicePerformanceCountByReadiness_(summaryRows, 'WATCH'),
      candidate_not_ready_count: _signalSynchronyProviderSlicePerformanceCountByReadiness_(summaryRows, 'NOT_READY'),
      warnings: _uniqueStrings_(warnings)
    };
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildSignalSynchronyProviderSlicePerformance(params) {
  return buildSignalSynchronyProviderSlicePerformance_(params || {});
}

function menuBuildSignalSynchronyProviderSlicePerformance_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildSignalSynchronyProviderSlicePerformance_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Signal synchrony provider slice performance -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Audit=' + (res.audit_rows_written || 0) + ' | Summary=' + (res.summary_rows_written || 0),
      'Signal Synchrony Provider Slice Performance',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Signal synchrony provider slice performance -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function _signalSynchronyProviderSlicePerformanceLoadSources_(warnings) {
  var captureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
  if (!captureBundle) throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Capture.');
  if (String(captureBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Capture in diagnostics workbook.');
  }

  var validationBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Validation', warnings, false);
  if (!validationBundle) throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Validation.');
  if (String(validationBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Validation in diagnostics workbook.');
  }

  var microBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Microcohort', warnings, false);
  if (!microBundle) throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Microcohort.');
  if (String(microBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Microcohort in diagnostics workbook.');
  }

  var outcomeBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Outcome_Check', warnings, false);
  if (!outcomeBundle) throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Outcome_Check.');
  if (String(outcomeBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Provider_Character_Direct_Expression_Outcome_Check in diagnostics workbook.');
  }

  var cohortBundle = _characterResidualReadSheetBundle_('Signal_Synchrony_Cohort_Characterization', warnings, false);
  if (!cohortBundle) throw new Error('Provider slice audit requires Signal_Synchrony_Cohort_Characterization.');
  if (String(cohortBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Signal_Synchrony_Cohort_Characterization in diagnostics workbook.');
  }

  var sufficiencyBundle = _characterResidualReadSheetBundle_('Signal_Synchrony_Rerun_Count_Sufficiency', warnings, false);
  if (!sufficiencyBundle) throw new Error('Provider slice audit requires Signal_Synchrony_Rerun_Count_Sufficiency.');
  if (String(sufficiencyBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Provider slice audit requires Signal_Synchrony_Rerun_Count_Sufficiency in diagnostics workbook.');
  }

  var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
  if (!eventBundle) throw new Error('Provider slice audit requires canonical Event sheet access.');
  if (String(eventBundle.workbook_type || '').trim() !== 'MAIN') {
    throw new Error('Provider slice audit requires canonical Event sheet from main workbook.');
  }

  return {
    captureBundle: captureBundle,
    validationBundle: validationBundle,
    microcohortBundle: microBundle,
    outcomeBundle: outcomeBundle,
    cohortBundle: cohortBundle,
    sufficiencyBundle: sufficiencyBundle,
    eventBundle: eventBundle
  };
}

function _signalSynchronyProviderSlicePerformanceBundleRowsToObjects_(bundle) {
  return _providerCharacterMicroExpressionBundleRowsToObjects_(bundle || {});
}

function _signalSynchronyProviderSlicePerformanceBuildCaptureIndex_(captureRows) {
  var byKey = {};
  for (var i = 0; i < (captureRows || []).length; i++) {
    var row = captureRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '||' + provider;
    if (!byKey[key]) {
      byKey[key] = {
        row: row,
        row_number: i + 2
      };
    }
  }
  return byKey;
}

function _signalSynchronyProviderSlicePerformanceBuildValidationIndex_(validationRows) {
  var byKey = {};
  for (var i = 0; i < (validationRows || []).length; i++) {
    var row = validationRows[i] || {};
    var sampleGroupId = String(row.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    if (!byKey[sampleGroupId]) byKey[sampleGroupId] = [];
    byKey[sampleGroupId].push(row);
  }
  return byKey;
}

function _signalSynchronyProviderSlicePerformanceBuildKeyIndexSafe_(rows, fieldName) {
  var byKey = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(row[fieldName] || '').trim();
    if (!key) continue;
    byKey[key] = row;
  }
  return byKey;
}

function _signalSynchronyProviderSlicePerformanceBuildEventIndexSafe_(eventRows) {
  var byKey = {};
  for (var i = 0; i < (eventRows || []).length; i++) {
    var row = eventRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    byKey[eventId] = row;
  }
  return byKey;
}

function _signalSynchronyProviderSlicePerformanceBuildAuditRows_(generatedTs, microcohortRows, captureIndex, validationIndex, outcomeIndex, cohortIndex, sufficiencyIndex, eventIndex, warnings) {
  var rows = [];
  for (var i = 0; i < (microcohortRows || []).length; i++) {
    var micro = microcohortRows[i] || {};
    var sampleGroupId = String(micro.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    rows.push(_signalSynchronyProviderSlicePerformanceBuildAuditRow_(
      generatedTs,
      micro,
      captureIndex,
      validationIndex,
      outcomeIndex,
      cohortIndex,
      sufficiencyIndex,
      eventIndex,
      warnings
    ));
  }

  rows.sort(function(a, b) {
    var aq = _signalSynchronyProviderSlicePerformanceSortKey_(String(a.cohort_group || ''), String(a.cohort_id || ''), String(a.event_family || ''), String(a.provider || ''), String(a.release_ts || ''), String(a.sample_group_id || ''));
    var bq = _signalSynchronyProviderSlicePerformanceSortKey_(String(b.cohort_group || ''), String(b.cohort_id || ''), String(b.event_family || ''), String(b.provider || ''), String(b.release_ts || ''), String(b.sample_group_id || ''));
    if (aq !== bq) return aq - bq;
    return String(a.sample_group_id || '').localeCompare(String(b.sample_group_id || ''));
  });
  return rows;
}

function _signalSynchronyProviderSlicePerformanceBuildAuditRow_(generatedTs, micro, captureIndex, validationIndex, outcomeIndex, cohortIndex, sufficiencyIndex, eventIndex, warnings) {
  micro = micro || {};
  var sampleGroupId = String(micro.sample_group_id || '').trim();
  var eventId = String(micro.event_id || '').trim();
  var provider = String(micro.provider || '').trim();

  var captureKey = eventId + '||' + provider;
  var captureRef = captureIndex[captureKey] || null;
  var captureRow = captureRef ? captureRef.row : null;
  if (!captureRow) warnings.push('missing_capture_row:' + sampleGroupId);

  var validationRows = validationIndex[sampleGroupId] || [];
  var validationRow = _signalSynchronyProviderSlicePerformancePickValidationRow_(validationRows);
  if (!validationRow && validationRows.length) warnings.push('validation_row_fallback:' + sampleGroupId);

  var outcomeRow = outcomeIndex[sampleGroupId] || null;
  if (!outcomeRow) warnings.push('missing_outcome_row:' + sampleGroupId);

  var cohortRow = cohortIndex[sampleGroupId] || null;
  if (!cohortRow) warnings.push('missing_cohort_characterization_row:' + sampleGroupId);

  var suffRow = sufficiencyIndex[sampleGroupId] || null;
  if (!suffRow) warnings.push('missing_sufficiency_row:' + sampleGroupId);

  var eventRow = eventIndex[eventId] || null;
  if (!eventRow) warnings.push('missing_event_row:' + sampleGroupId);

  var cohortId = String(cohortRow && cohortRow.cohort_id || suffRow && suffRow.cohort_id || captureRow && captureRow.cohort_id || '').trim() || 'unknown';
  var cohortGroup = String(cohortRow && cohortRow.cohort_group || suffRow && suffRow.cohort_group || _signalSynchronyProviderSlicePerformanceCohortGroup_(cohortId) || 'unknown').trim();

  var eventFamily = String(suffRow && suffRow.event_family || cohortRow && cohortRow.event_family || captureRow && captureRow.outcome_family || micro.outcome_family || '').trim();
  var importance = String(suffRow && suffRow.importance || cohortRow && cohortRow.importance || captureRow && captureRow.importance || eventRow && eventRow.importance || '').trim();

  var consensusValue = _numOrNull_(eventRow ? eventRow.consensus_value : micro.consensus_value);
  var prevRevision = _numOrNull_(eventRow ? eventRow.prev_revision : micro.prev_revision);
  var releasedValue = _numOrNull_(eventRow ? eventRow.released_value : micro.released_value);
  var actualDirection = _providerCharacterDirectExpressionOutcomeCheckActualDirection_(consensusValue, releasedValue, prevRevision);
  var actualVsPreviousDirection = _providerCharacterDirectExpressionOutcomeCheckDirectionFromValues_(releasedValue, prevRevision);
  var actualAvailable = releasedValue != null ? 'TRUE' : 'FALSE';
  var actualComparable = actualDirection && actualDirection.status === 'ok' ? 'TRUE' : 'FALSE';

  var outcomeLabel = String(outcomeRow && outcomeRow.outcome_result_label || '').trim();
  var forecastMatchesActual = String(outcomeRow && outcomeRow.forecast_matches_actual || '').trim().toUpperCase();
  if (forecastMatchesActual !== 'TRUE' && forecastMatchesActual !== 'FALSE') forecastMatchesActual = '';
  var outcomeCheckStatus = String(outcomeRow && outcomeRow.outcome_check_status || '').trim();

  var validationRunId = String(validationRow && validationRow.validation_run_id || '').trim();
  var validationMode = String(validationRow && validationRow.validation_mode || '').trim();

  var sourceCaptureRowNumber = _numOrNull_(captureRef ? captureRef.row_number : null);
  var originalCoho = String(validationRow && validationRow.original_cohort_id || captureRow && captureRow.cohort_id || cohortId || '').trim();
  var captureRunId = String(captureRow && captureRow.capture_run_id || '').trim();
  var originalCaptureRunId = String(validationRow && validationRow.original_capture_run_id || captureRunId || '').trim();
  var validationCaptureRunId = String(validationRow && validationRow.validation_capture_run_id || '').trim();

  var rerunSuccessCount = Math.max(0, Number(cohortRow && cohortRow.rerun_success_count || 0));
  var rerunFailureCount = Math.max(0, Number(cohortRow && cohortRow.rerun_failure_count || 0));
  var rerunComplete = String(cohortRow && cohortRow.rerun_complete || '').trim();
  var stabilityLabel = String(suffRow && suffRow.interpretation_label || '').trim();
  var recommendedProtocol = String(suffRow && suffRow.recommended_protocol || '').trim();
  var stabilityReason = String(suffRow && suffRow.stability_threshold_reason || '').trim();

  var predictionDirectionConcentration = _numOrNull_(micro.forecast_direction_concentration);
  var patternConcentration = _numOrNull_(micro.pattern_concentration_score);
  var expressionSimilarity = _numOrNull_(micro.expression_similarity_mean_if_available);
  var reproducibilityLabel = String(micro.interpretation_label || '').trim();
  var predictabilityIndex = _numOrNull_(cohortRow && cohortRow.predictability_index);
  var predictabilityBucket = String(cohortRow && cohortRow.predictability_bucket || '').trim() || _signalSynchronyProviderSlicePerformancePredictabilityBucket_(predictabilityIndex);

  var surpriseValue = '';
  var absSurpriseValue = '';
  var consensusPrevGap = '';
  var absConsensusPrevGap = '';
  if (releasedValue != null && consensusValue != null) {
    surpriseValue = _round4_(releasedValue - consensusValue);
    absSurpriseValue = _round4_(Math.abs(releasedValue - consensusValue));
  }
  if (consensusValue != null && prevRevision != null) {
    consensusPrevGap = _round4_(consensusValue - prevRevision);
    absConsensusPrevGap = _round4_(Math.abs(consensusValue - prevRevision));
  }

  var row = {
    generated_ts: generatedTs,
    cohort_id: cohortId,
    cohort_group: cohortGroup,
    sample_group_id: sampleGroupId,
    event_id: eventId,
    provider: provider,
    indicator_name: String(micro.indicator_name || suffRow && suffRow.indicator_name || captureRow && captureRow.indicator_name || eventRow && eventRow.indicator_name || '').trim(),
    country: String(micro.country || suffRow && suffRow.country || captureRow && captureRow.country || eventRow && eventRow.country || '').trim(),
    release_ts: String(micro.release_ts || suffRow && suffRow.release_ts || captureRow && captureRow.release_ts || eventRow && eventRow.release_ts || '').trim(),
    event_family: eventFamily,
    importance: importance,
    source_capture_row_number: sourceCaptureRowNumber == null ? '' : sourceCaptureRowNumber,
    capture_run_id: captureRunId,
    original_cohort_id: originalCoho,
    original_capture_run_id: originalCaptureRunId,
    validation_capture_run_id: validationCaptureRunId,
    validation_run_id: validationRunId,
    validation_mode: validationMode,
    actual_available: actualAvailable,
    actual_comparable: actualComparable,
    forecast_matches_actual: forecastMatchesActual,
    outcome_result_label: outcomeLabel,
    outcome_check_status: outcomeCheckStatus,
    dominant_forecast_direction: String(micro.dominant_forecast_direction || '').trim(),
    forecast_direction_concentration: predictionDirectionConcentration == null ? '' : predictionDirectionConcentration,
    pattern_concentration_score: patternConcentration == null ? '' : patternConcentration,
    expression_similarity_mean: expressionSimilarity == null ? '' : expressionSimilarity,
    reproducibility_outcome_label: reproducibilityLabel,
    rerun_complete: rerunComplete,
    rerun_success_count: Number(cohortRow && cohortRow.rerun_success_count || 0),
    rerun_failure_count: Number(cohortRow && cohortRow.rerun_failure_count || 0),
    stability_label: stabilityLabel,
    recommended_protocol: recommendedProtocol,
    stability_threshold_reason: stabilityReason,
    consensus_value: consensusValue == null ? '' : consensusValue,
    prev_revision: prevRevision == null ? '' : prevRevision,
    released_value: releasedValue == null ? '' : releasedValue,
    surprise_value: surpriseValue,
    abs_surprise_value: absSurpriseValue,
    consensus_prev_gap: consensusPrevGap,
    abs_consensus_prev_gap: absConsensusPrevGap,
    predictability_index: predictabilityIndex == null ? '' : predictabilityIndex,
    predictability_bucket: predictabilityBucket,
    actual_economic_direction: actualDirection && actualDirection.direction ? String(actualDirection.direction) : 'unknown',
    actual_vs_previous_direction: actualVsPreviousDirection,
    actual_source_provider: String(eventRow && eventRow.source_provider || '').trim(),
    actual_source_series_id: String(eventRow && eventRow.source_series_id || '').trim(),
    actual_transform: String(eventRow && eventRow.transform || '').trim(),
    slice_family: eventFamily,
    slice_family_importance: eventFamily && importance ? eventFamily + '|' + importance : '',
    slice_family_predictability: eventFamily && predictabilityBucket ? eventFamily + '|' + predictabilityBucket : '',
    slice_provider_family: provider && eventFamily ? provider + '|' + eventFamily : '',
    slice_provider_family_importance: provider && eventFamily && importance ? provider + '|' + eventFamily + '|' + importance : '',
    slice_provider_family_predictability: provider && eventFamily && predictabilityBucket ? provider + '|' + eventFamily + '|' + predictabilityBucket : '',
    notes: [
      'microcohort_interpretation=' + reproducibilityLabel,
      'stability_label=' + stabilityLabel,
      'recommended_protocol=' + recommendedProtocol,
      stabilityReason ? ('stability_threshold_reason=' + stabilityReason) : '',
      'cohort_bucket=' + cohortGroup,
      warnings && warnings.length ? ('warnings=' + _uniqueStrings_(warnings).join('|')) : ''
    ].filter(Boolean).join('; ')
  };

  return row;
}

function _signalSynchronyProviderSlicePerformancePickValidationRow_(validationRows) {
  validationRows = validationRows || [];
  if (!validationRows.length) return null;
  for (var i = 0; i < validationRows.length; i++) {
    var row = validationRows[i] || {};
    if (String(row.validation_run_id || '').trim() === 'microcohort_rerun_v1' && String(row.validation_mode || '').trim() === 'microcohort_same_capture_path_rerun') {
      return row;
    }
  }
  return validationRows[0] || null;
}

function _signalSynchronyProviderSlicePerformanceSortKey_(cohortGroup, cohortId, family, provider, releaseTs, sampleGroupId) {
  var rank = {
    'cohort_a': 1,
    'deterministic': 2,
    'random': 3,
    'unknown': 4
  };
  var g = String(cohortGroup || '').trim();
  return Number(rank[g] || 9) * 100000000 + _signalSynchronyProviderSlicePerformanceStringHash_(String(cohortId || '') + '|' + String(family || '') + '|' + String(provider || '') + '|' + String(releaseTs || '') + '|' + String(sampleGroupId || ''));
}

function _signalSynchronyProviderSlicePerformanceStringHash_(text) {
  var s = String(text || '');
  var hash = 0;
  for (var i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function _signalSynchronyProviderSlicePerformanceCohortGroup_(cohortId) {
  var id = String(cohortId || '').trim();
  if (!id || id === 'unknown') return 'unknown';
  if (id === 'cohort_a_existing_fresh_replay' || id.indexOf('cohort_a') === 0) return 'cohort_a';
  if (id === 'cohort_b_direct_capture_expansion' || id === 'cohort_c_direct_capture_expansion' || id.indexOf('cohort_b') === 0 || id.indexOf('cohort_c') === 0) return 'deterministic';
  if (id === 'signal_synchrony_random_cohort_v1' || id.indexOf('signal_synchrony_random') === 0) return 'random';
  return 'unknown';
}

function _signalSynchronyProviderSlicePerformancePredictabilityBucket_(value) {
  var v = _numOrNull_(value);
  if (v == null) return 'unknown';
  if (v >= 0.67) return 'high';
  if (v >= 0.34) return 'medium';
  return 'low';
}

function _signalSynchronyProviderSlicePerformanceCountUniqueEvents_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var eventId = String((rows[i] || {}).event_id || '').trim();
    if (eventId) out[eventId] = true;
  }
  return Object.keys(out).length;
}

function _signalSynchronyProviderSlicePerformanceCountProviders_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var provider = String((rows[i] || {}).provider || '').trim();
    if (provider) out[provider] = true;
  }
  return Object.keys(out).length;
}

function _signalSynchronyProviderSlicePerformanceCountCohorts_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var cohortId = String((rows[i] || {}).cohort_id || '').trim();
    if (cohortId) out[cohortId] = true;
  }
  return Object.keys(out).length;
}

function _signalSynchronyProviderSlicePerformanceCountComparable_(rows) {
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (String(row.outcome_result_label || '').trim() === 'FORECAST_CORRECT' ||
        String(row.outcome_result_label || '').trim() === 'FORECAST_INLINE_CORRECT' ||
        String(row.outcome_result_label || '').trim() === 'FORECAST_WRONG') {
      count += 1;
    }
  }
  return count;
}

function _signalSynchronyProviderSlicePerformanceCountRowsBySection_(rows, section) {
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    if (String((rows[i] || {}).section || '').trim() === String(section || '').trim()) count += 1;
  }
  return count;
}

function _signalSynchronyProviderSlicePerformanceCountByReadiness_(rows, readiness) {
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    if (String((rows[i] || {}).routing_readiness || '').trim() === String(readiness || '').trim()) count += 1;
  }
  return count;
}

function _signalSynchronyProviderSlicePerformanceBuildSummaryRows_(generatedTs, auditRows, warnings) {
  auditRows = auditRows || [];
  var out = [];
  var globalBaseline = _signalSynchronyProviderSlicePerformanceSummarizeRows_(auditRows, function() { return true; });

  out.push({
    generated_ts: generatedTs,
    section: 'METHODOLOGY',
    row_type: 'METHODOLOGY_NOTE',
    provider: '',
    event_family: '',
    importance: '',
    predictability_bucket: '',
    slice_type: 'methodology',
    slice_key: 'Signal Synchrony Provider Slice Performance',
    sample_groups: Number(auditRows.length || 0),
    unique_events: _signalSynchronyProviderSlicePerformanceCountUniqueEvents_(auditRows),
    providers_present: _signalSynchronyProviderSlicePerformanceCountProviders_(auditRows),
    comparable_rows: globalBaseline.comparable_rows,
    correct_count: globalBaseline.correct_count,
    wrong_count: globalBaseline.wrong_count,
    correct_rate: globalBaseline.correct_rate,
    global_baseline_rate: globalBaseline.correct_rate,
    provider_baseline_rate: '',
    slice_baseline_rate: globalBaseline.correct_rate,
    provider_delta_vs_global_baseline: '0',
    provider_delta_vs_provider_baseline: '',
    provider_delta_vs_slice_baseline: '0',
    best_provider_in_family_flag: '',
    best_provider_in_slice_flag: '',
    thin_sample_flag: globalBaseline.comparable_rows < 8 ? 'TRUE' : 'FALSE',
    very_thin_sample_flag: globalBaseline.comparable_rows < 5 ? 'TRUE' : 'FALSE',
    confidence_label: _signalSynchronyProviderSlicePerformanceConfidenceLabel_(globalBaseline.comparable_rows),
    candidate_interpretation: 'Methodology note: baseline definitions are deterministic and descriptive only.',
    routing_readiness: 'NOT_READY',
    cohort_count: _signalSynchronyProviderSlicePerformanceCountCohorts_(auditRows),
    cohort_distribution: _signalSynchronyProviderSlicePerformanceCohortDistribution_(auditRows),
    notes: 'global_baseline_rate=' + String(globalBaseline.correct_rate || '') + '; provider_baseline_rate=per-provider; slice_baseline_rate=per-slice; candidate_rules=comparable>=8 & correct_rate>=0.50 & delta>=0.10'
  });

  var providerOverallGroups = _signalSynchronyProviderSlicePerformanceGroupBy_(auditRows, function(row) { return String(row.provider || '').trim() || 'unknown'; });
  var providerNames = Object.keys(providerOverallGroups).sort();
  var providerStats = {};
  for (var p = 0; p < providerNames.length; p++) {
    var providerName = providerNames[p];
    providerStats[providerName] = _signalSynchronyProviderSlicePerformanceSummarizeRows_(providerOverallGroups[providerName], function() { return true; });
    var rows = providerOverallGroups[providerName] || [];
    var providerCorrectRate = providerStats[providerName].correct_rate;
    var providerRow = {
      generated_ts: generatedTs,
      section: 'A',
      row_type: 'PROVIDER_OVERALL',
      provider: providerName,
      event_family: '',
      importance: '',
      predictability_bucket: '',
      slice_type: 'provider_overall',
      slice_key: providerName,
      sample_groups: rows.length,
      unique_events: _signalSynchronyProviderSlicePerformanceCountUniqueEvents_(rows),
      providers_present: 1,
      comparable_rows: providerStats[providerName].comparable_rows,
      correct_count: providerStats[providerName].correct_count,
      wrong_count: providerStats[providerName].wrong_count,
      correct_rate: providerCorrectRate,
      global_baseline_rate: globalBaseline.correct_rate,
      provider_baseline_rate: providerCorrectRate,
      slice_baseline_rate: providerCorrectRate,
      provider_delta_vs_global_baseline: _signalSynchronyProviderSlicePerformanceDelta_(providerCorrectRate, globalBaseline.correct_rate),
      provider_delta_vs_provider_baseline: '0',
      provider_delta_vs_slice_baseline: '0',
      best_provider_in_family_flag: '',
      best_provider_in_slice_flag: '',
      thin_sample_flag: providerStats[providerName].comparable_rows < 8 ? 'TRUE' : 'FALSE',
      very_thin_sample_flag: providerStats[providerName].comparable_rows < 5 ? 'TRUE' : 'FALSE',
      confidence_label: _signalSynchronyProviderSlicePerformanceConfidenceLabel_(providerStats[providerName].comparable_rows),
      candidate_interpretation: 'Provider overall summary only.',
      routing_readiness: 'NOT_READY',
      cohort_count: _signalSynchronyProviderSlicePerformanceCountCohorts_(rows),
      cohort_distribution: _signalSynchronyProviderSlicePerformanceCohortDistribution_(rows),
      average_forecast_direction_concentration: providerStats[providerName].avg_forecast_direction_concentration,
      average_pattern_concentration_score: providerStats[providerName].avg_pattern_concentration_score,
      average_expression_similarity_mean: providerStats[providerName].avg_expression_similarity_mean,
      average_predictability_index: providerStats[providerName].avg_predictability_index,
      actual_missing_count: providerStats[providerName].actual_missing_count,
      notes: 'provider_overall_summary'
    };
    out.push(providerRow);
  }

  var familyRows = _signalSynchronyProviderSlicePerformanceBuildProviderSliceRows_(generatedTs, auditRows, 'provider_family', function(row) { return String(row.provider || '').trim() + '||' + String(row.event_family || '').trim(); }, function(row) { return String(row.event_family || '').trim(); }, function(row) { return String(row.event_family || '').trim(); }, warnings);
  var familyImportanceRows = _signalSynchronyProviderSlicePerformanceBuildProviderSliceRows_(generatedTs, auditRows, 'provider_family_importance', function(row) { return String(row.provider || '').trim() + '||' + String(row.event_family || '').trim() + '||' + String(row.importance || '').trim(); }, function(row) { return String(row.event_family || '').trim() + '|' + String(row.importance || '').trim(); }, function(row) { return String(row.event_family || '').trim() + '|' + String(row.importance || '').trim(); }, warnings);
  var familyPredictabilityRows = _signalSynchronyProviderSlicePerformanceBuildProviderSliceRows_(generatedTs, auditRows, 'provider_family_predictability', function(row) { return String(row.provider || '').trim() + '||' + String(row.event_family || '').trim() + '||' + String(row.predictability_bucket || '').trim(); }, function(row) { return String(row.event_family || '').trim() + '|' + String(row.predictability_bucket || '').trim(); }, function(row) { return String(row.event_family || '').trim() + '|' + String(row.predictability_bucket || '').trim(); }, warnings);

  out = out.concat(familyRows.rows, familyImportanceRows.rows, familyPredictabilityRows.rows);

  var candidateRows = [];
  var weaknessRows = [];
  var readinessRows = [];
  var allSliceRows = familyRows.rows.concat(familyImportanceRows.rows, familyPredictabilityRows.rows);
  for (var i = 0; i < allSliceRows.length; i++) {
    var row = allSliceRows[i] || {};
    var comparableRows = Number(row.comparable_rows || 0);
    var correctRate = _numOrNull_(row.correct_rate);
    var deltaSlice = _numOrNull_(row.provider_delta_vs_slice_baseline);
    var deltaGlobal = _numOrNull_(row.provider_delta_vs_global_baseline);
    if (comparableRows >= 8 && correctRate != null && deltaSlice != null && deltaGlobal != null && correctRate >= 0.5 && deltaSlice >= 0.10 && deltaGlobal >= 0.05) {
      candidateRows.push(_signalSynchronyProviderSlicePerformanceCandidateRow_(generatedTs, row, globalBaseline.correct_rate, warnings));
    }
    if (comparableRows >= 8 && correctRate != null && deltaSlice != null && correctRate <= 0.35 && deltaSlice <= -0.10) {
      weaknessRows.push(_signalSynchronyProviderSlicePerformanceWeaknessRow_(generatedTs, row, warnings));
    }
  }

  readinessRows = candidateRows.map(function(candidate) {
    var copy = JSON.parse(JSON.stringify(candidate));
    copy.section = 'G';
    copy.row_type = 'ROUTING_READINESS_NOTE';
    copy.notes = 'routing_readiness=' + String(candidate.routing_readiness || '') + '; cohort_count=' + String(candidate.cohort_count || '') + '; ' + String(candidate.notes || '');
    return copy;
  });

  out = out.concat(candidateRows, weaknessRows, readinessRows);

  out.sort(function(a, b) {
    var sa = String(a.section || '');
    var sb = String(b.section || '');
    var ra = String(a.row_type || '');
    var rb = String(b.row_type || '');
    if (sa !== sb) return sa.localeCompare(sb);
    if (ra !== rb) return ra.localeCompare(rb);
    if (String(a.provider || '') !== String(b.provider || '')) return String(a.provider || '').localeCompare(String(b.provider || ''));
    if (String(a.event_family || '') !== String(b.event_family || '')) return String(a.event_family || '').localeCompare(String(b.event_family || ''));
    if (String(a.importance || '') !== String(b.importance || '')) return String(a.importance || '').localeCompare(String(b.importance || ''));
    if (String(a.predictability_bucket || '') !== String(b.predictability_bucket || '')) return String(a.predictability_bucket || '').localeCompare(String(b.predictability_bucket || ''));
    return String(a.slice_key || '').localeCompare(String(b.slice_key || ''));
  });

  return out;
}

function _signalSynchronyProviderSlicePerformanceBuildProviderSliceRows_(generatedTs, auditRows, sliceType, keyFn, sliceKeyFn, bestKeyFn, warnings) {
  var grouped = _signalSynchronyProviderSlicePerformanceGroupBy_(auditRows, keyFn);
  var sliceBaselineMap = _signalSynchronyProviderSlicePerformanceBuildSliceBaselineMap_(auditRows, sliceKeyFn);
  var cohortMap = _signalSynchronyProviderSlicePerformanceBuildSliceCohortMap_(auditRows, keyFn);
  var bestGroups = _signalSynchronyProviderSlicePerformanceGroupBy_(auditRows, bestKeyFn || sliceKeyFn);
  var out = [];

  var keys = Object.keys(grouped).sort();
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var rows = grouped[key] || [];
    var stats = _signalSynchronyProviderSlicePerformanceSummarizeRows_(rows, function() { return true; });
    var baseline = sliceBaselineMap[sliceKeyFn(rows[0] || {})] || _signalSynchronyProviderSlicePerformanceSummarizeRows_([], function() { return false; });
    var providerName = String(rows[0] && rows[0].provider || '').trim();
    var familyName = String(rows[0] && rows[0].event_family || '').trim();
    var importance = String(rows[0] && rows[0].importance || '').trim();
    var bucket = String(rows[0] && rows[0].predictability_bucket || '').trim();
    var providerBaseline = _signalSynchronyProviderSlicePerformanceSummarizeRows_(auditRows, function(r) { return String(r.provider || '').trim() === providerName; });
    var deltaGlobal = _signalSynchronyProviderSlicePerformanceDelta_(stats.correct_rate, baseline.global_rate);
    var deltaProvider = _signalSynchronyProviderSlicePerformanceDelta_(stats.correct_rate, providerBaseline.correct_rate);
    var deltaSlice = _signalSynchronyProviderSlicePerformanceDelta_(stats.correct_rate, baseline.correct_rate);
    var bestKey = String(bestKeyFn ? bestKeyFn(rows[0] || {}) : sliceKeyFn(rows[0] || {})).trim() || 'unknown';
    var bestFlag = _signalSynchronyProviderSlicePerformanceIsBestProvider_(bestGroups[bestKey] || [], providerName, stats.correct_rate);
    var cohortCount = Number(cohortMap[key] && cohortMap[key].cohort_count || 0);
    var readiness = _signalSynchronyProviderSlicePerformanceRoutingReadiness_(rows.length, stats.correct_rate, deltaSlice, cohortCount, rows);
    out.push({
      generated_ts: generatedTs,
      section: sliceType === 'provider_family' ? 'B' : (sliceType === 'provider_family_importance' ? 'C' : 'D'),
      row_type: sliceType.toUpperCase(),
      provider: providerName,
      event_family: familyName,
      importance: importance,
      predictability_bucket: bucket,
      slice_type: sliceType,
      slice_key: key,
      sample_groups: rows.length,
      unique_events: _signalSynchronyProviderSlicePerformanceCountUniqueEvents_(rows),
      providers_present: _signalSynchronyProviderSlicePerformanceCountProviders_(rows),
      comparable_rows: stats.comparable_rows,
      correct_count: stats.correct_count,
      wrong_count: stats.wrong_count,
      correct_rate: stats.correct_rate,
      global_baseline_rate: baseline.global_rate,
      provider_baseline_rate: providerBaseline.correct_rate,
      slice_baseline_rate: baseline.correct_rate,
      provider_delta_vs_global_baseline: deltaGlobal,
      provider_delta_vs_provider_baseline: deltaProvider,
      provider_delta_vs_slice_baseline: deltaSlice,
      best_provider_in_family_flag: sliceType === 'provider_family' ? bestFlag : '',
      best_provider_in_slice_flag: sliceType === 'provider_family' ? '' : bestFlag,
      thin_sample_flag: stats.comparable_rows < 8 ? 'TRUE' : 'FALSE',
      very_thin_sample_flag: stats.comparable_rows < 5 ? 'TRUE' : 'FALSE',
      confidence_label: _signalSynchronyProviderSlicePerformanceConfidenceLabel_(stats.comparable_rows),
      candidate_interpretation: _signalSynchronyProviderSlicePerformanceSliceInterpretation_(stats.correct_rate, baseline.correct_rate, deltaSlice, stats.comparable_rows),
      routing_readiness: readiness,
      cohort_count: cohortCount,
      cohort_distribution: _signalSynchronyProviderSlicePerformanceCohortDistribution_(rows),
      actual_missing_count: stats.actual_missing_count,
      average_forecast_direction_concentration: stats.avg_forecast_direction_concentration,
      average_pattern_concentration_score: stats.avg_pattern_concentration_score,
      average_expression_similarity_mean: stats.avg_expression_similarity_mean,
      average_predictability_index: stats.avg_predictability_index,
      notes: 'slice_type=' + sliceType + '; slice_baseline_rate=' + String(baseline.correct_rate || '') + '; global_baseline_rate=' + String(baseline.global_rate || '')
    });
  }

  return { rows: out };
}

function _signalSynchronyProviderSlicePerformanceBuildSliceBaselineMap_(auditRows, sliceKeyFn) {
  var grouped = _signalSynchronyProviderSlicePerformanceGroupBy_(auditRows, function(row) {
    return String(sliceKeyFn(row) || '').trim() || 'unknown';
  });
  var out = {};
  var keys = Object.keys(grouped);
  var global = _signalSynchronyProviderSlicePerformanceSummarizeRows_(auditRows, function() { return true; });
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    out[key] = grouped[key];
    out[key] = {
      correct_rate: _signalSynchronyProviderSlicePerformanceSummarizeRows_(grouped[key], function() { return true; }).correct_rate,
      global_rate: global.correct_rate,
      rows: grouped[key]
    };
  }
  return out;
}

function _signalSynchronyProviderSlicePerformanceBuildSliceCohortMap_(auditRows, keyFn) {
  var grouped = _signalSynchronyProviderSlicePerformanceGroupBy_(auditRows, keyFn);
  var out = {};
  var keys = Object.keys(grouped);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var rows = grouped[key] || [];
    var cohorts = {};
    for (var j = 0; j < rows.length; j++) {
      var cohortGroup = String(rows[j] && rows[j].cohort_group || '').trim() || 'unknown';
      cohorts[cohortGroup] = true;
    }
    out[key] = {
      cohort_count: Object.keys(cohorts).length,
      cohort_distribution: _signalSynchronyProviderSlicePerformanceCohortDistribution_(rows)
    };
  }
  return out;
}

function _signalSynchronyProviderSlicePerformanceCandidateRow_(generatedTs, row, globalRate, warnings) {
  var cohortCount = Number(row.cohort_count || 0);
  var readiness = _signalSynchronyProviderSlicePerformanceRoutingReadiness_(Number(row.comparable_rows || 0), _numOrNull_(row.correct_rate), _numOrNull_(row.provider_delta_vs_slice_baseline), cohortCount, []);
  var interpretation = 'possible provider-slice edge';
  return {
    generated_ts: generatedTs,
    section: 'E',
    row_type: 'CANDIDATE_STRENGTH',
    provider: String(row.provider || '').trim(),
    event_family: String(row.event_family || '').trim(),
    importance: String(row.importance || '').trim(),
    predictability_bucket: String(row.predictability_bucket || '').trim(),
    slice_type: String(row.slice_type || '').trim(),
    slice_key: String(row.slice_key || '').trim(),
    sample_groups: Number(row.sample_groups || 0),
    unique_events: Number(row.unique_events || 0),
    providers_present: Number(row.providers_present || 0),
    comparable_rows: Number(row.comparable_rows || 0),
    correct_count: Number(row.correct_count || 0),
    wrong_count: Number(row.wrong_count || 0),
    correct_rate: row.correct_rate,
    slice_baseline_rate: row.slice_baseline_rate,
    provider_delta_vs_slice_baseline: row.provider_delta_vs_slice_baseline,
    global_baseline_rate: globalRate,
    provider_delta_vs_global_baseline: row.provider_delta_vs_global_baseline,
    confidence_label: _signalSynchronyProviderSlicePerformanceConfidenceLabel_(Number(row.comparable_rows || 0)),
    candidate_interpretation: interpretation,
    routing_readiness: readiness,
    cohort_count: cohortCount,
    cohort_distribution: String(row.cohort_distribution || '').trim(),
    notes: 'candidate_strength'
  };
}

function _signalSynchronyProviderSlicePerformanceWeaknessRow_(generatedTs, row, warnings) {
  return {
    generated_ts: generatedTs,
    section: 'F',
    row_type: 'CANDIDATE_WEAKNESS',
    provider: String(row.provider || '').trim(),
    event_family: String(row.event_family || '').trim(),
    importance: String(row.importance || '').trim(),
    predictability_bucket: String(row.predictability_bucket || '').trim(),
    slice_type: String(row.slice_type || '').trim(),
    slice_key: String(row.slice_key || '').trim(),
    sample_groups: Number(row.sample_groups || 0),
    unique_events: Number(row.unique_events || 0),
    providers_present: Number(row.providers_present || 0),
    comparable_rows: Number(row.comparable_rows || 0),
    correct_count: Number(row.correct_count || 0),
    wrong_count: Number(row.wrong_count || 0),
    correct_rate: row.correct_rate,
    slice_baseline_rate: row.slice_baseline_rate,
    provider_delta_vs_slice_baseline: row.provider_delta_vs_slice_baseline,
    confidence_label: _signalSynchronyProviderSlicePerformanceConfidenceLabel_(Number(row.comparable_rows || 0)),
    weakness_interpretation: 'possible provider-slice weakness',
    notes: 'candidate_weakness'
  };
}

function _signalSynchronyProviderSlicePerformanceSummarizeRows_(rows, predicateFn) {
  rows = rows || [];
  predicateFn = predicateFn || function() { return true; };
  var comparable = 0;
  var correct = 0;
  var wrong = 0;
  var actualMissing = 0;
  var unknown = 0;
  var directionVals = [];
  var patternVals = [];
  var similarityVals = [];
  var predictVals = [];
  var providers = {};
  var events = {};
  var cohorts = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (!predicateFn(row)) continue;
    var provider = String(row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    var cohortId = String(row.cohort_id || '').trim();
    if (provider) providers[provider] = true;
    if (eventId) events[eventId] = true;
    if (cohortId) cohorts[cohortId] = true;

    var outcome = String(row.outcome_result_label || '').trim();
    if (outcome === 'ACTUAL_MISSING') {
      actualMissing += 1;
    } else if (outcome === 'FORECAST_CORRECT' || outcome === 'FORECAST_INLINE_CORRECT') {
      comparable += 1;
      correct += 1;
    } else if (outcome === 'FORECAST_WRONG') {
      comparable += 1;
      wrong += 1;
    } else if (outcome === 'FORECAST_UNKNOWN' || outcome === 'DIRECTION_UNCOMPARABLE' || outcome === 'UNCOMPARABLE' || outcome === 'OUTCOME_UNAVAILABLE') {
      unknown += 1;
    }

    var d = _numOrNull_(row.forecast_direction_concentration);
    if (d != null) directionVals.push(d);
    var p = _numOrNull_(row.pattern_concentration_score);
    if (p != null) patternVals.push(p);
    var s = _numOrNull_(row.expression_similarity_mean);
    if (s != null) similarityVals.push(s);
    var pi = _numOrNull_(row.predictability_index);
    if (pi != null) predictVals.push(pi);
  }

  var correctRate = comparable ? _round4_(correct / comparable) : '';
  return {
    sample_groups: rows.length,
    unique_events: Object.keys(events).length,
    providers_present: Object.keys(providers).sort().join('|'),
    provider_count: Object.keys(providers).length,
    comparable_rows: comparable,
    correct_count: correct,
    wrong_count: wrong,
    correct_rate: correctRate,
    actual_missing_count: actualMissing,
    unknown_count: unknown,
    avg_forecast_direction_concentration: _signalSynchronyProviderSlicePerformanceAverageFromArray_(directionVals),
    avg_pattern_concentration_score: _signalSynchronyProviderSlicePerformanceAverageFromArray_(patternVals),
    avg_expression_similarity_mean: _signalSynchronyProviderSlicePerformanceAverageFromArray_(similarityVals),
    avg_predictability_index: _signalSynchronyProviderSlicePerformanceAverageFromArray_(predictVals),
    cohort_count: Object.keys(cohorts).length
  };
}

function _signalSynchronyProviderSlicePerformanceAverageFromArray_(values) {
  values = values || [];
  var sum = 0;
  var count = 0;
  for (var i = 0; i < values.length; i++) {
    var n = _numOrNull_(values[i]);
    if (n == null) continue;
    sum += n;
    count += 1;
  }
  return count ? _round4_(sum / count) : '';
}

function _signalSynchronyProviderSlicePerformanceGroupBy_(rows, keyFn) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(keyFn(row, i) || '').trim() || 'unknown';
    if (!out[key]) out[key] = [];
    out[key].push(row);
  }
  return out;
}

function _signalSynchronyProviderSlicePerformanceBuildCandidateFamilies_(rows) {
  return _signalSynchronyProviderSlicePerformanceGroupBy_(rows, function(row) {
    return String(row.slice_type || '').trim() + '||' + String(row.slice_key || '').trim();
  });
}

function _signalSynchronyProviderSlicePerformanceBuildCandidateRowSet_(rows, filterFn) {
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (filterFn && !filterFn(row)) continue;
    out.push(row);
  }
  return out;
}

function _signalSynchronyProviderSlicePerformanceDelta_(a, b) {
  var na = _numOrNull_(a);
  var nb = _numOrNull_(b);
  if (na == null || nb == null) return '';
  return _round4_(na - nb);
}

function _signalSynchronyProviderSlicePerformanceConfidenceLabel_(comparableRows) {
  var n = Number(comparableRows || 0);
  if (n >= 20) return 'HIGHER_CONFIDENCE';
  if (n >= 12) return 'MEDIUM_CONFIDENCE';
  if (n >= 8) return 'LOW_CONFIDENCE';
  return 'THIN_SAMPLE';
}

function _signalSynchronyProviderSlicePerformanceSliceInterpretation_(correctRate, baselineRate, deltaSlice, comparableRows) {
  var n = Number(comparableRows || 0);
  var cr = _numOrNull_(correctRate);
  var dr = _numOrNull_(deltaSlice);
  if (n < 8 || cr == null || dr == null || _numOrNull_(baselineRate) == null) return 'insufficient_sample';
  if (cr >= 0.55 && dr >= 0.15) return 'possible provider-slice edge';
  if (cr <= 0.35 && dr <= -0.10) return 'possible provider-slice weakness';
  return 'slice neutral or unclear';
}

function _signalSynchronyProviderSlicePerformanceRoutingReadiness_(comparableRows, correctRate, deltaSlice, cohortCount, rows) {
  var n = Number(comparableRows || 0);
  var cr = _numOrNull_(correctRate);
  var ds = _numOrNull_(deltaSlice);
  var cohorts = Number(cohortCount || 0);
  if (n >= 12 && cr != null && ds != null && cr >= 0.55 && ds >= 0.15 && cohorts >= 2) return 'ROUTING_CANDIDATE_SHADOW_ONLY';
  if (n >= 8 && cr != null && ds != null && cr >= 0.50 && ds >= 0.10) return 'WATCH';
  return 'NOT_READY';
}

function _signalSynchronyProviderSlicePerformanceIsBestProvider_(sliceRows, providerName, correctRate) {
  sliceRows = sliceRows || [];
  var target = _numOrNull_(correctRate);
  if (target == null) return 'FALSE';
  var best = null;
  var byProvider = _signalSynchronyProviderSlicePerformanceGroupBy_(sliceRows, function(row) { return String(row.provider || '').trim() || 'unknown'; });
  var keys = Object.keys(byProvider || {});
  for (var i = 0; i < keys.length; i++) {
    var rows = byProvider[keys[i]] || [];
    if (!rows.length) continue;
    var stats = _signalSynchronyProviderSlicePerformanceSummarizeRows_(rows, function() { return true; });
    var c = _numOrNull_(stats.correct_rate);
    if (c == null) continue;
    if (best == null || c > best) best = c;
  }
  if (best == null) return 'FALSE';
  return Math.abs(best - target) < 0.0001 ? 'TRUE' : 'FALSE';
}

function _signalSynchronyProviderSlicePerformanceCohortDistribution_(rows) {
  var counts = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var cohort = String((rows[i] || {}).cohort_group || '').trim() || 'unknown';
    counts[cohort] = Number(counts[cohort] || 0) + 1;
  }
  var keys = Object.keys(counts).sort();
  var out = [];
  for (var j = 0; j < keys.length; j++) {
    out.push(keys[j] + ':' + counts[keys[j]]);
  }
  return out.join('|');
}

function _signalSynchronyProviderSlicePerformanceAuditHeaders_() {
  return [
    'generated_ts',
    'cohort_id',
    'cohort_group',
    'sample_group_id',
    'event_id',
    'provider',
    'indicator_name',
    'country',
    'release_ts',
    'event_family',
    'importance',
    'source_capture_row_number',
    'capture_run_id',
    'original_cohort_id',
    'original_capture_run_id',
    'validation_capture_run_id',
    'validation_run_id',
    'validation_mode',
    'actual_available',
    'actual_comparable',
    'forecast_matches_actual',
    'outcome_result_label',
    'outcome_check_status',
    'dominant_forecast_direction',
    'forecast_direction_concentration',
    'pattern_concentration_score',
    'expression_similarity_mean',
    'reproducibility_outcome_label',
    'rerun_complete',
    'rerun_success_count',
    'rerun_failure_count',
    'stability_label',
    'recommended_protocol',
    'stability_threshold_reason',
    'consensus_value',
    'prev_revision',
    'released_value',
    'surprise_value',
    'abs_surprise_value',
    'consensus_prev_gap',
    'abs_consensus_prev_gap',
    'predictability_index',
    'predictability_bucket',
    'actual_economic_direction',
    'actual_vs_previous_direction',
    'actual_source_provider',
    'actual_source_series_id',
    'actual_transform',
    'slice_family',
    'slice_family_importance',
    'slice_family_predictability',
    'slice_provider_family',
    'slice_provider_family_importance',
    'slice_provider_family_predictability',
    'notes'
  ];
}

function _signalSynchronyProviderSlicePerformanceSummaryHeaders_() {
  return [
    'generated_ts',
    'section',
    'row_type',
    'provider',
    'event_family',
    'importance',
    'predictability_bucket',
    'slice_type',
    'slice_key',
    'sample_groups',
    'unique_events',
    'providers_present',
    'comparable_rows',
    'correct_count',
    'wrong_count',
    'correct_rate',
    'global_baseline_rate',
    'provider_baseline_rate',
    'slice_baseline_rate',
    'provider_delta_vs_global_baseline',
    'provider_delta_vs_provider_baseline',
    'provider_delta_vs_slice_baseline',
    'best_provider_in_family_flag',
    'best_provider_in_slice_flag',
    'thin_sample_flag',
    'very_thin_sample_flag',
    'confidence_label',
    'candidate_interpretation',
    'routing_readiness',
    'cohort_count',
    'cohort_distribution',
    'actual_missing_count',
    'average_forecast_direction_concentration',
    'average_pattern_concentration_score',
    'average_expression_similarity_mean',
    'average_predictability_index',
    'notes'
  ];
}
