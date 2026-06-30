/*******************************************************
 * signal_synchrony_cohort_characterization.js
 * - Diagnostic-only Signal Synchrony v1 - Cohort Characterization Audit v1
 * - Pure derived audit over existing Direct Expression capture / validation / microcohort / outcome data
 * - No provider calls, no reruns, no production behavior changes
 *******************************************************/

function menuBuildSignalSynchronyCohortCharacterization_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildSignalSynchronyCohortCharacterization_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Signal synchrony cohort characterization -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Audit=' + (res.audit_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Signal Synchrony Cohort Characterization',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Signal synchrony cohort characterization -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildSignalSynchronyCohortCharacterization_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var warnings = [];

  try {
    var sources = _signalSynchronyCohortCharacterizationLoadSources_(warnings);
    var captureRows = _signalSynchronyCohortCharacterizationBundleRowsToObjects_(sources.captureBundle);
    var validationRows = _signalSynchronyCohortCharacterizationBundleRowsToObjects_(sources.validationBundle);
    var microcohortRows = _signalSynchronyCohortCharacterizationBundleRowsToObjects_(sources.microcohortBundle);
    var outcomeRows = _signalSynchronyCohortCharacterizationBundleRowsToObjects_(sources.outcomeBundle);
    var eventRows = _signalSynchronyCohortCharacterizationBundleRowsToObjects_(sources.eventBundle);

    var captureIndex = _signalSynchronyCohortCharacterizationBuildCaptureIndex_(captureRows);
    var eventIndex = _signalSynchronyCohortCharacterizationBuildEventIndex_(eventRows);
    var validationIndex = _signalSynchronyCohortCharacterizationBuildValidationIndex_(validationRows);
    var outcomeIndex = _signalSynchronyCohortCharacterizationBuildOutcomeIndex_(outcomeRows);

    var auditRows = _signalSynchronyCohortCharacterizationBuildAuditRows_(
      generatedTs,
      microcohortRows,
      captureIndex,
      eventIndex,
      validationIndex,
      outcomeIndex,
      warnings
    );
    var summaryRows = _signalSynchronyCohortCharacterizationBuildSummaryRows_(generatedTs, auditRows, warnings);

    var auditSheet = getDiagnosticsSheet_(
      'Signal_Synchrony_Cohort_Characterization',
      _signalSynchronyCohortCharacterizationAuditHeaders_(),
      warnings
    );
    var summarySheet = getDiagnosticsSheet_(
      'Signal_Synchrony_Cohort_Characterization_Summary',
      _signalSynchronyCohortCharacterizationSummaryHeaders_(),
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
      cohorts_detected: _signalSynchronyCohortCharacterizationCountCohorts_(auditRows),
      sample_groups_written: auditRows.length,
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

function buildSignalSynchronyCohortCharacterization(params) {
  return buildSignalSynchronyCohortCharacterization_(params || {});
}

function _signalSynchronyCohortCharacterizationAuditHeaders_() {
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
    'consensus_value',
    'prev_revision',
    'released_value',
    'released_ts',
    'release_status',
    'actual_economic_direction',
    'actual_vs_previous_direction',
    'actual_available',
    'actual_comparable',
    'actual_source_provider',
    'actual_source_series_id',
    'actual_transform',
    'surprise_value',
    'abs_surprise_value',
    'surprise_vs_previous',
    'abs_surprise_vs_previous',
    'consensus_prev_gap',
    'abs_consensus_prev_gap',
    'dominant_forecast_direction',
    'forecast_direction_concentration',
    'pattern_concentration_score',
    'expression_similarity_mean',
    'rerun_complete',
    'rerun_success_count',
    'rerun_failure_count',
    'microcohort_interpretation_label',
    'forecast_matches_actual',
    'outcome_result_label',
    'reproducibility_outcome_label',
    'outcome_check_status',
    'predictability_index',
    'predictability_bucket',
    'notes'
  ];
}

function _signalSynchronyCohortCharacterizationSummaryHeaders_() {
  return [
    'generated_ts',
    'section',
    'row_type',
    'cohort_id',
    'cohort_group',
    'comparison_label',
    'cohort_left',
    'cohort_right',
    'sample_groups_left',
    'sample_groups_right',
    'scope_type',
    'scope_value',
    'event_family',
    'provider',
    'predictability_bucket',
    'sample_groups',
    'unique_events',
    'providers_present',
    'comparable_rows',
    'correct_count',
    'wrong_count',
    'correct_rate',
    'actual_missing_count',
    'unknown_count',
    'family_distribution_difference',
    'provider_distribution_difference',
    'avg_forecast_direction_concentration',
    'avg_forecast_direction_concentration_left',
    'avg_forecast_direction_concentration_right',
    'avg_forecast_direction_concentration_delta',
    'avg_pattern_concentration_score',
    'avg_pattern_concentration_score_left',
    'avg_pattern_concentration_score_right',
    'avg_pattern_concentration_score_delta',
    'avg_expression_similarity_mean',
    'avg_expression_similarity_mean_left',
    'avg_expression_similarity_mean_right',
    'avg_expression_similarity_mean_delta',
    'avg_abs_surprise_value',
    'avg_abs_surprise_value_left',
    'avg_abs_surprise_value_right',
    'avg_abs_surprise_value_delta',
    'avg_abs_consensus_prev_gap',
    'avg_abs_consensus_prev_gap_left',
    'avg_abs_consensus_prev_gap_right',
    'avg_abs_consensus_prev_gap_delta',
    'avg_predictability_index',
    'avg_predictability_index_left',
    'avg_predictability_index_right',
    'avg_predictability_index_delta',
    'question_id',
    'answer',
    'notes'
  ];
}

function _signalSynchronyCohortCharacterizationLoadSources_(warnings) {
  var captureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
  if (!captureBundle) throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Capture.');
  if (String(captureBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Capture in diagnostics workbook.');
  }

  var validationBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Validation', warnings, false);
  if (!validationBundle) throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Validation.');
  if (String(validationBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Validation in diagnostics workbook.');
  }

  var microcohortBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Microcohort', warnings, false);
  if (!microcohortBundle) throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Microcohort.');
  if (String(microcohortBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Microcohort in diagnostics workbook.');
  }

  var outcomeBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Outcome_Check', warnings, false);
  if (!outcomeBundle) throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Outcome_Check.');
  if (String(outcomeBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
    throw new Error('Cohort characterization requires Provider_Character_Direct_Expression_Outcome_Check in diagnostics workbook.');
  }

  var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
  if (!eventBundle) throw new Error('Cohort characterization requires canonical Event sheet access.');
  if (String(eventBundle.workbook_type || '').trim() !== 'MAIN') {
    throw new Error('Cohort characterization requires canonical Event sheet from main workbook.');
  }

  return {
    captureBundle: captureBundle,
    validationBundle: validationBundle,
    microcohortBundle: microcohortBundle,
    outcomeBundle: outcomeBundle,
    eventBundle: eventBundle
  };
}

function _signalSynchronyCohortCharacterizationBundleRowsToObjects_(bundle) {
  var rows = (bundle && bundle.rows) || [];
  var headers = (bundle && bundle.headers) || [];
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var raw = rows[i] || [];
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = j < raw.length ? raw[j] : '';
    }
    out.push(obj);
  }
  return out;
}

function _signalSynchronyCohortCharacterizationBuildCaptureIndex_(captureRows) {
  var byRowNumber = {};
  var byKey = {};
  for (var i = 0; i < (captureRows || []).length; i++) {
    var row = captureRows[i] || {};
    var rowNumber = i + 2;
    byRowNumber[rowNumber] = row;
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (eventId && provider) {
      byKey[eventId + '||' + provider] = {
        row_number: rowNumber,
        row: row
      };
    }
  }
  return {
    byRowNumber: byRowNumber,
    byKey: byKey
  };
}

function _signalSynchronyCohortCharacterizationBuildEventIndex_(eventRows) {
  var map = {};
  for (var i = 0; i < (eventRows || []).length; i++) {
    var row = eventRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    map[eventId] = row;
  }
  return map;
}

function _signalSynchronyCohortCharacterizationBuildValidationIndex_(validationRows) {
  var map = {};
  for (var i = 0; i < (validationRows || []).length; i++) {
    var row = validationRows[i] || {};
    var sampleGroupId = String(row.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    if (!map[sampleGroupId]) map[sampleGroupId] = [];
    map[sampleGroupId].push(row);
  }
  return map;
}

function _signalSynchronyCohortCharacterizationBuildOutcomeIndex_(outcomeRows) {
  var map = {};
  for (var i = 0; i < (outcomeRows || []).length; i++) {
    var row = outcomeRows[i] || {};
    var sampleGroupId = String(row.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    map[sampleGroupId] = row;
  }
  return map;
}

function _signalSynchronyCohortCharacterizationBuildAuditRows_(generatedTs, microcohortRows, captureIndex, eventIndex, validationIndex, outcomeIndex, warnings) {
  var rows = [];
  for (var i = 0; i < (microcohortRows || []).length; i++) {
    var micro = microcohortRows[i] || {};
    var sampleGroupId = String(micro.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    rows.push(_signalSynchronyCohortCharacterizationBuildAuditRow_(
      generatedTs,
      micro,
      captureIndex,
      eventIndex,
      validationIndex,
      outcomeIndex,
      warnings
    ));
  }

  rows.sort(function(a, b) {
    var aq = _signalSynchronyCohortCharacterizationCohortSortKey_(String(a.cohort_group || ''), String(a.cohort_id || ''));
    var bq = _signalSynchronyCohortCharacterizationCohortSortKey_(String(b.cohort_group || ''), String(b.cohort_id || ''));
    if (aq !== bq) return aq - bq;
    if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
    if (String(a.provider || '') !== String(b.provider || '')) return String(a.provider || '').localeCompare(String(b.provider || ''));
    return String(a.sample_group_id || '').localeCompare(String(b.sample_group_id || ''));
  });
  return rows;
}

function _signalSynchronyCohortCharacterizationBuildAuditRow_(generatedTs, micro, captureIndex, eventIndex, validationIndex, outcomeIndex, warnings) {
  micro = micro || {};
  var sampleGroupId = String(micro.sample_group_id || '').trim();
  var eventId = String(micro.event_id || '').trim();
  var provider = String(micro.provider || '').trim();
  var sourceRowNumber = _signalSynchronyCohortCharacterizationParseSourceRowNumber_(String(micro.notes || '').trim());
  var captureRow = sourceRowNumber != null ? (captureIndex.byRowNumber[sourceRowNumber] || null) : null;
  if (!captureRow && eventId && provider) {
    var key = eventId + '||' + provider;
    captureRow = captureIndex.byKey[key] ? captureIndex.byKey[key].row : null;
    if (!sourceRowNumber && captureIndex.byKey[key]) sourceRowNumber = captureIndex.byKey[key].row_number;
  }
  if (!captureRow) warnings.push('missing_capture_row_for_sample_group:' + sampleGroupId);

  var validationRows = validationIndex[sampleGroupId] || [];
  var validationRowsForCurrentPath = [];
  for (var i = 0; i < validationRows.length; i++) {
    var v = validationRows[i] || {};
    if (String(v.validation_run_id || '').trim() === 'microcohort_rerun_v1' &&
        String(v.validation_mode || '').trim() === 'microcohort_same_capture_path_rerun') {
      validationRowsForCurrentPath.push(v);
    }
  }
  if (!validationRowsForCurrentPath.length && validationRows.length) {
    warnings.push('validation_rows_present_but_not_microcohort_run:' + sampleGroupId);
  }

  var validationRow = validationRowsForCurrentPath.length ? validationRowsForCurrentPath[0] : (validationRows.length ? validationRows[0] : null);
  var outcomeRow = outcomeIndex[sampleGroupId] || null;
  var eventRow = eventIndex[eventId] || null;

  var captureCohortId = String(captureRow && captureRow.cohort_id || '').trim();
  var cohortId = captureCohortId || String(micro.cohort_id || '').trim() || 'unknown';
  var cohortGroup = _signalSynchronyCohortCharacterizationCohortGroup_(cohortId);

  var consensusValue = _numOrNull_(eventRow ? eventRow.consensus_value : micro.consensus_value);
  var prevRevision = _numOrNull_(eventRow ? eventRow.prev_revision : micro.prev_revision);
  var releasedValue = _numOrNull_(eventRow ? eventRow.released_value : micro.released_value);
  var actualDirection = _providerCharacterDirectExpressionOutcomeCheckActualDirection_(consensusValue, releasedValue, prevRevision);
  var actualVsPreviousDirection = _providerCharacterDirectExpressionOutcomeCheckDirectionFromValues_(releasedValue, prevRevision);
  var actualAvailable = releasedValue != null ? 'TRUE' : 'FALSE';
  var actualComparable = actualDirection && actualDirection.status === 'ok' ? 'TRUE' : 'FALSE';

  var forecastDirectionConcentration = _numOrNull_(micro.forecast_direction_concentration);
  var patternConcentrationScore = _numOrNull_(micro.pattern_concentration_score);
  var expressionSimilarityMean = _numOrNull_(micro.expression_similarity_mean_if_available);
  var rerunSuccessCount = Math.max(0, Number(micro.successful_run_count || 0) - 1);
  var rerunFailureCount = Math.max(0, Number(micro.failed_run_count || 0));
  var rerunComplete = (Number(micro.run_count || 0) >= 5 && rerunFailureCount === 0) ? 'TRUE' : 'FALSE';

  var forecastMatchesActual = String(outcomeRow && outcomeRow.forecast_matches_actual || '').trim().toUpperCase();
  if (forecastMatchesActual !== 'TRUE' && forecastMatchesActual !== 'FALSE') forecastMatchesActual = '';
  var outcomeResultLabel = String(outcomeRow && outcomeRow.outcome_result_label || '').trim();
  var reproducibilityOutcomeLabel = String(outcomeRow && outcomeRow.reproducibility_outcome_label || '').trim();
  var outcomeCheckStatus = String(outcomeRow && outcomeRow.outcome_check_status || '').trim();

  var surpriseValue = '';
  var absSurpriseValue = '';
  var surpriseVsPrevious = '';
  var absSurpriseVsPrevious = '';
  var consensusPrevGap = '';
  var absConsensusPrevGap = '';
  if (releasedValue != null && consensusValue != null) {
    surpriseValue = _round4_(releasedValue - consensusValue);
    absSurpriseValue = _round4_(Math.abs(releasedValue - consensusValue));
  }
  if (releasedValue != null && prevRevision != null) {
    surpriseVsPrevious = _round4_(releasedValue - prevRevision);
    absSurpriseVsPrevious = _round4_(Math.abs(releasedValue - prevRevision));
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
    indicator_name: String(micro.indicator_name || captureRow && captureRow.indicator_name || eventRow && eventRow.indicator_name || '').trim(),
    country: String(micro.country || captureRow && captureRow.country || eventRow && eventRow.country || '').trim(),
    release_ts: String(micro.release_ts || captureRow && captureRow.release_ts || eventRow && eventRow.release_ts || '').trim(),
    event_family: String(micro.outcome_family || captureRow && captureRow.outcome_family || '').trim(),
    importance: String(micro.importance || captureRow && captureRow.importance || eventRow && eventRow.importance || '').trim(),
    source_capture_row_number: sourceRowNumber == null ? '' : sourceRowNumber,
    capture_run_id: String(captureRow && captureRow.capture_run_id || '').trim(),
    original_cohort_id: String(validationRow && validationRow.original_cohort_id || captureCohortId || '').trim(),
    original_capture_run_id: String(validationRow && validationRow.original_capture_run_id || captureRow && captureRow.capture_run_id || '').trim(),
    validation_capture_run_id: String(validationRow && validationRow.validation_capture_run_id || '').trim(),
    validation_run_id: String(validationRow && validationRow.validation_run_id || 'microcohort_rerun_v1').trim(),
    validation_mode: String(validationRow && validationRow.validation_mode || 'microcohort_same_capture_path_rerun').trim(),
    consensus_value: consensusValue == null ? '' : consensusValue,
    prev_revision: prevRevision == null ? '' : prevRevision,
    released_value: releasedValue == null ? '' : releasedValue,
    released_ts: String(eventRow && eventRow.released_ts || '').trim(),
    release_status: String(eventRow && eventRow.release_status || '').trim(),
    actual_economic_direction: actualDirection && actualDirection.direction ? String(actualDirection.direction) : 'unknown',
    actual_vs_previous_direction: actualVsPreviousDirection,
    actual_available: actualAvailable,
    actual_comparable: actualComparable,
    actual_source_provider: String(eventRow && eventRow.source_provider || '').trim(),
    actual_source_series_id: String(eventRow && eventRow.source_series_id || '').trim(),
    actual_transform: String(eventRow && eventRow.transform || '').trim(),
    surprise_value: surpriseValue,
    abs_surprise_value: absSurpriseValue,
    surprise_vs_previous: surpriseVsPrevious,
    abs_surprise_vs_previous: absSurpriseVsPrevious,
    consensus_prev_gap: consensusPrevGap,
    abs_consensus_prev_gap: absConsensusPrevGap,
    dominant_forecast_direction: String(micro.dominant_forecast_direction || '').trim(),
    forecast_direction_concentration: forecastDirectionConcentration == null ? '' : forecastDirectionConcentration,
    pattern_concentration_score: patternConcentrationScore == null ? '' : patternConcentrationScore,
    expression_similarity_mean: expressionSimilarityMean == null ? '' : expressionSimilarityMean,
    rerun_complete: rerunComplete,
    rerun_success_count: rerunSuccessCount,
    rerun_failure_count: rerunFailureCount,
    microcohort_interpretation_label: String(micro.interpretation_label || '').trim(),
    forecast_matches_actual: forecastMatchesActual,
    outcome_result_label: outcomeResultLabel,
    reproducibility_outcome_label: reproducibilityOutcomeLabel,
    outcome_check_status: outcomeCheckStatus,
    predictability_index: '',
    predictability_bucket: '',
    notes: ''
  };

  row.predictability_index = _signalSynchronyCohortCharacterizationPredictabilityIndex_(row);
  row.predictability_bucket = _signalSynchronyCohortCharacterizationPredictabilityBucket_(row.predictability_index);
  row.notes = [
    'source_capture_row_number=' + (sourceRowNumber == null ? '' : sourceRowNumber),
    'microcohort_interpretation=' + String(row.microcohort_interpretation_label || ''),
    'outcome_check_status=' + String(row.outcome_check_status || ''),
    'cohort_bucket=' + cohortGroup,
    warnings && warnings.length ? ('warnings=' + _uniqueStrings_(warnings).join('|')) : ''
  ].filter(Boolean).join('; ');
  return row;
}

function _signalSynchronyCohortCharacterizationParseSourceRowNumber_(notes) {
  var text = String(notes || '').trim();
  if (!text) return null;
  var match = text.match(/source_capture_row_number=([0-9]+)/i);
  if (!match) return null;
  var n = Number(match[1]);
  return isFinite(n) && n > 0 ? n : null;
}

function _signalSynchronyCohortCharacterizationCohortGroup_(cohortId) {
  var id = String(cohortId || '').trim();
  if (!id || id === 'unknown') return 'unknown';
  if (id === 'cohort_a_existing_fresh_replay' || id.indexOf('cohort_a') === 0) return 'cohort_a';
  if (id === 'cohort_b_direct_capture_expansion' || id === 'cohort_c_direct_capture_expansion' || id.indexOf('cohort_b') === 0 || id.indexOf('cohort_c') === 0) return 'deterministic';
  if (id === 'signal_synchrony_random_cohort_v1' || id.indexOf('signal_synchrony_random') === 0) return 'random';
  return 'unknown';
}

function _signalSynchronyCohortCharacterizationCohortSortKey_(cohortGroup, cohortId) {
  var rank = {
    'cohort_a': 1,
    'deterministic': 2,
    'random': 3,
    'unknown': 4
  };
  var g = String(cohortGroup || '').trim();
  var id = String(cohortId || '').trim();
  return Number(rank[g] || 9) * 1000000 + _signalSynchronyCohortCharacterizationStringHash_(id);
}

function _signalSynchronyCohortCharacterizationStringHash_(text) {
  var s = String(text || '');
  var hash = 0;
  for (var i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function _signalSynchronyCohortCharacterizationPredictabilityIndex_(row) {
  row = row || {};
  var components = [];

  var dir = _numOrNull_(row.forecast_direction_concentration);
  if (dir != null) components.push(Math.max(0, Math.min(1, dir)));

  var pattern = _numOrNull_(row.pattern_concentration_score);
  if (pattern != null) components.push(Math.max(0, Math.min(1, pattern)));

  components.push(String(row.rerun_complete || '').trim().toUpperCase() === 'TRUE' ? 1 : 0);

  var importance = String(row.importance || '').trim().toLowerCase();
  var importanceScore = 0.5;
  if (importance === 'high') importanceScore = 1;
  else if (importance === 'medium') importanceScore = 0.67;
  else if (importance === 'low') importanceScore = 0.33;
  components.push(importanceScore);

  var gap = _numOrNull_(row.abs_consensus_prev_gap);
  if (gap != null) {
    components.push(_round4_(1 / (1 + Math.max(0, gap))));
  }

  if (!components.length) return '';
  var sum = 0;
  for (var i = 0; i < components.length; i++) sum += Number(components[i] || 0);
  return _round4_(sum / components.length);
}

function _signalSynchronyCohortCharacterizationPredictabilityBucket_(value) {
  var v = _numOrNull_(value);
  if (v == null) return 'unknown';
  if (v >= 0.67) return 'high';
  if (v >= 0.34) return 'medium';
  return 'low';
}

function _signalSynchronyCohortCharacterizationBuildSummaryRows_(generatedTs, rows, warnings) {
  rows = rows || [];
  var out = [];

  var overallStats = _signalSynchronyCohortCharacterizationSummarizeGroup_(rows);
  var cohortGroups = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) { return String(row.cohort_id || '').trim() || 'unknown'; });
  var cohortFamilies = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) {
    return (String(row.cohort_id || '').trim() || 'unknown') + '||' + (String(row.event_family || '').trim() || 'unknown');
  });
  var cohortProviders = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) {
    return (String(row.cohort_id || '').trim() || 'unknown') + '||' + (String(row.provider || '').trim() || 'unknown');
  });
  var cohortBuckets = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) {
    return String(row.cohort_group || '').trim() || 'unknown';
  });

  var methodologyNote = [
    'predictability_index=avg(direction_concentration, pattern_concentration, rerun_complete, importance_score, 1/(1+abs_consensus_prev_gap))',
    'direction_concentration=dominant_direction_count/known_direction_count',
    'pattern_concentration=mean token recurrence concentration across the direct-expression fields',
    'rerun_complete=TRUE only when the sample group has the expected 4 reruns and zero rerun failures'
  ].join('; ');

  out.push({
    generated_ts: generatedTs,
    section: 'METHODOLOGY',
    row_type: 'METHODOLOGY_NOTE',
    cohort_id: '',
    cohort_group: '',
    comparison_label: '',
    scope_type: '',
    scope_value: '',
    event_family: '',
    provider: '',
    predictability_bucket: '',
    sample_groups: '',
    unique_events: '',
    providers_present: '',
    comparable_rows: '',
    correct_count: '',
    wrong_count: '',
    correct_rate: '',
    actual_missing_count: '',
    unknown_count: '',
    family_distribution_difference: '',
    provider_distribution_difference: '',
    avg_forecast_direction_concentration: '',
    avg_pattern_concentration_score: '',
    avg_expression_similarity_mean: '',
    avg_abs_surprise_value: '',
    avg_abs_consensus_prev_gap: '',
    avg_predictability_index: '',
    question_id: 'PREDICTABILITY_FORMULA',
    answer: 'Conservative pre-outcome structural score only; no correctness or outcome match used.',
    notes: methodologyNote
  });

  var cohortKeys = Object.keys(cohortGroups).sort();
  for (var c = 0; c < cohortKeys.length; c++) {
    var cohortId = cohortKeys[c];
    var cohortRows = cohortGroups[cohortId] || [];
    var s = _signalSynchronyCohortCharacterizationSummarizeGroup_(cohortRows);
    out.push({
      generated_ts: generatedTs,
      section: 'A_COHORT_OUTCOME_SUMMARY',
      row_type: 'COHORT_OUTCOME',
      cohort_id: cohortId,
      cohort_group: String(cohortRows[0] && cohortRows[0].cohort_group || '').trim() || _signalSynchronyCohortCharacterizationCohortGroup_(cohortId),
      comparison_label: '',
      scope_type: 'COHORT',
      scope_value: cohortId,
      event_family: '',
      provider: '',
      predictability_bucket: '',
      sample_groups: s.sample_groups,
      unique_events: s.unique_events,
      providers_present: s.providers_present,
      comparable_rows: s.comparable_rows,
      correct_count: s.correct_count,
      wrong_count: s.wrong_count,
      correct_rate: s.correct_rate,
      actual_missing_count: s.actual_missing_count,
      unknown_count: s.unknown_count,
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: s.avg_forecast_direction_concentration,
      avg_pattern_concentration_score: s.avg_pattern_concentration_score,
      avg_expression_similarity_mean: s.avg_expression_similarity_mean,
      avg_abs_surprise_value: s.avg_abs_surprise_value,
      avg_abs_consensus_prev_gap: s.avg_abs_consensus_prev_gap,
      avg_predictability_index: s.avg_predictability_index,
      question_id: '',
      answer: '',
      notes: 'cohort_outcome_summary'
    });
  }

  var familyKeys = Object.keys(cohortFamilies).sort();
  for (var f = 0; f < familyKeys.length; f++) {
    var familyKey = familyKeys[f];
    var parts = familyKey.split('||');
    var familyCohortId = parts[0];
    var family = parts[1] || 'unknown';
    var familyRows = cohortFamilies[familyKey] || [];
    var fs = _signalSynchronyCohortCharacterizationSummarizeGroup_(familyRows);
    out.push({
      generated_ts: generatedTs,
      section: 'B_COHORT_FAMILY_SUMMARY',
      row_type: 'COHORT_FAMILY',
      cohort_id: familyCohortId,
      cohort_group: String(familyRows[0] && familyRows[0].cohort_group || '').trim() || _signalSynchronyCohortCharacterizationCohortGroup_(familyCohortId),
      comparison_label: '',
      scope_type: 'EVENT_FAMILY',
      scope_value: family,
      event_family: family,
      provider: '',
      predictability_bucket: '',
      sample_groups: fs.sample_groups,
      unique_events: fs.unique_events,
      providers_present: fs.providers_present,
      comparable_rows: fs.comparable_rows,
      correct_count: fs.correct_count,
      wrong_count: fs.wrong_count,
      correct_rate: fs.correct_rate,
      actual_missing_count: fs.actual_missing_count,
      unknown_count: fs.unknown_count,
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: fs.avg_forecast_direction_concentration,
      avg_pattern_concentration_score: fs.avg_pattern_concentration_score,
      avg_expression_similarity_mean: fs.avg_expression_similarity_mean,
      avg_abs_surprise_value: fs.avg_abs_surprise_value,
      avg_abs_consensus_prev_gap: fs.avg_abs_consensus_prev_gap,
      avg_predictability_index: fs.avg_predictability_index,
      question_id: '',
      answer: '',
      notes: 'cohort_family_summary'
    });
  }

  var providerKeys = Object.keys(cohortProviders).sort();
  for (var p = 0; p < providerKeys.length; p++) {
    var providerKey = providerKeys[p];
    var providerParts = providerKey.split('||');
    var providerCohortId = providerParts[0];
    var providerName = providerParts[1] || 'unknown';
    var providerRows = cohortProviders[providerKey] || [];
    var ps = _signalSynchronyCohortCharacterizationSummarizeGroup_(providerRows);
    out.push({
      generated_ts: generatedTs,
      section: 'B_COHORT_PROVIDER_SUMMARY',
      row_type: 'COHORT_PROVIDER',
      cohort_id: providerCohortId,
      cohort_group: String(providerRows[0] && providerRows[0].cohort_group || '').trim() || _signalSynchronyCohortCharacterizationCohortGroup_(providerCohortId),
      comparison_label: '',
      scope_type: 'PROVIDER',
      scope_value: providerName,
      event_family: '',
      provider: providerName,
      predictability_bucket: '',
      sample_groups: ps.sample_groups,
      unique_events: ps.unique_events,
      providers_present: ps.providers_present,
      comparable_rows: ps.comparable_rows,
      correct_count: ps.correct_count,
      wrong_count: ps.wrong_count,
      correct_rate: ps.correct_rate,
      actual_missing_count: ps.actual_missing_count,
      unknown_count: ps.unknown_count,
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: ps.avg_forecast_direction_concentration,
      avg_pattern_concentration_score: ps.avg_pattern_concentration_score,
      avg_expression_similarity_mean: ps.avg_expression_similarity_mean,
      avg_abs_surprise_value: ps.avg_abs_surprise_value,
      avg_abs_consensus_prev_gap: ps.avg_abs_consensus_prev_gap,
      avg_predictability_index: ps.avg_predictability_index,
      question_id: '',
      answer: '',
      notes: 'cohort_provider_summary'
    });
  }

  var comparisonSpecs = [
    { label: 'cohort_a_vs_all_others', left: 'cohort_a', right: 'all_others' },
    { label: 'cohort_a_vs_deterministic', left: 'cohort_a', right: 'deterministic' },
    { label: 'cohort_a_vs_random', left: 'cohort_a', right: 'random' },
    { label: 'deterministic_vs_random', left: 'deterministic', right: 'random' }
  ];
  var bucketMap = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) { return String(row.cohort_group || '').trim() || 'unknown'; });
  for (var x = 0; x < comparisonSpecs.length; x++) {
    var spec = comparisonSpecs[x];
    var leftRows = spec.left === 'all_others'
      ? rows.filter(function(row) { return String(row.cohort_group || '').trim() !== 'cohort_a'; })
      : (bucketMap[spec.left] || []);
    var rightRows = spec.right === 'all_others'
      ? allOthers
      : (bucketMap[spec.right] || []);
    var leftStats = _signalSynchronyCohortCharacterizationSummarizeGroup_(leftRows);
    var rightStats = _signalSynchronyCohortCharacterizationSummarizeGroup_(rightRows);
    var leftFamilyDist = _signalSynchronyCohortCharacterizationDistribution_(leftRows, 'event_family');
    var rightFamilyDist = _signalSynchronyCohortCharacterizationDistribution_(rightRows, 'event_family');
    var leftProviderDist = _signalSynchronyCohortCharacterizationDistribution_(leftRows, 'provider');
    var rightProviderDist = _signalSynchronyCohortCharacterizationDistribution_(rightRows, 'provider');
    var familyDifference = _signalSynchronyCohortCharacterizationTvDistance_(leftFamilyDist, rightFamilyDist);
    var providerDifference = _signalSynchronyCohortCharacterizationTvDistance_(leftProviderDist, rightProviderDist);
    out.push({
      generated_ts: generatedTs,
      section: 'C_STRUCTURAL_COMPARISON',
      row_type: 'STRUCTURAL_COMPARISON',
      cohort_id: '',
      cohort_group: '',
      comparison_label: spec.label,
      scope_type: 'COHORT_GROUP',
      scope_value: spec.left + '_vs_' + spec.right,
      event_family: '',
      provider: '',
      predictability_bucket: '',
      sample_groups: '',
      unique_events: '',
      providers_present: '',
      comparable_rows: '',
      correct_count: '',
      wrong_count: '',
      correct_rate: '',
      actual_missing_count: '',
      unknown_count: '',
      family_distribution_difference: familyDifference,
      provider_distribution_difference: providerDifference,
      avg_forecast_direction_concentration: '',
      avg_pattern_concentration_score: '',
      avg_expression_similarity_mean: '',
      avg_abs_surprise_value: '',
      avg_abs_consensus_prev_gap: '',
      avg_predictability_index: '',
      cohort_left: spec.left,
      cohort_right: spec.right,
      sample_groups_left: leftStats.sample_groups,
      sample_groups_right: rightStats.sample_groups,
      avg_forecast_direction_concentration_left: leftStats.avg_forecast_direction_concentration,
      avg_forecast_direction_concentration_right: rightStats.avg_forecast_direction_concentration,
      avg_forecast_direction_concentration_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_forecast_direction_concentration, rightStats.avg_forecast_direction_concentration),
      avg_pattern_concentration_score_left: leftStats.avg_pattern_concentration_score,
      avg_pattern_concentration_score_right: rightStats.avg_pattern_concentration_score,
      avg_pattern_concentration_score_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_pattern_concentration_score, rightStats.avg_pattern_concentration_score),
      avg_expression_similarity_mean_left: leftStats.avg_expression_similarity_mean,
      avg_expression_similarity_mean_right: rightStats.avg_expression_similarity_mean,
      avg_expression_similarity_mean_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_expression_similarity_mean, rightStats.avg_expression_similarity_mean),
      avg_abs_surprise_value_left: leftStats.avg_abs_surprise_value,
      avg_abs_surprise_value_right: rightStats.avg_abs_surprise_value,
      avg_abs_surprise_value_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_abs_surprise_value, rightStats.avg_abs_surprise_value),
      avg_abs_consensus_prev_gap_left: leftStats.avg_abs_consensus_prev_gap,
      avg_abs_consensus_prev_gap_right: rightStats.avg_abs_consensus_prev_gap,
      avg_abs_consensus_prev_gap_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_abs_consensus_prev_gap, rightStats.avg_abs_consensus_prev_gap),
      avg_predictability_index_left: leftStats.avg_predictability_index,
      avg_predictability_index_right: rightStats.avg_predictability_index,
      avg_predictability_index_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_predictability_index, rightStats.avg_predictability_index),
      question_id: '',
      answer: '',
      notes: 'left_family_dist=' + _signalSynchronyCohortCharacterizationDistributionString_(leftFamilyDist) + '; right_family_dist=' + _signalSynchronyCohortCharacterizationDistributionString_(rightFamilyDist) + '; left_provider_dist=' + _signalSynchronyCohortCharacterizationDistributionString_(leftProviderDist) + '; right_provider_dist=' + _signalSynchronyCohortCharacterizationDistributionString_(rightProviderDist)
    });
  }

  var predictabilityBuckets = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) { return String(row.predictability_bucket || '').trim() || 'unknown'; });
  var bucketKeys = Object.keys(predictabilityBuckets).sort(function(a, b) {
    var order = { high: 1, medium: 2, low: 3, unknown: 4 };
    return Number(order[a] || 9) - Number(order[b] || 9);
  });
  for (var b = 0; b < bucketKeys.length; b++) {
    var bucket = bucketKeys[b];
    var bucketRows = predictabilityBuckets[bucket] || [];
    var bs = _signalSynchronyCohortCharacterizationSummarizeGroup_(bucketRows);
    out.push({
      generated_ts: generatedTs,
      section: 'D_PREDICTABILITY_INDEX_SUMMARY',
      row_type: 'PREDICTABILITY_BUCKET',
      cohort_id: '',
      cohort_group: '',
      comparison_label: '',
      scope_type: 'PREDICTABILITY_BUCKET',
      scope_value: bucket,
      event_family: '',
      provider: '',
      predictability_bucket: bucket,
      sample_groups: bs.sample_groups,
      unique_events: bs.unique_events,
      providers_present: bs.providers_present,
      comparable_rows: bs.comparable_rows,
      correct_count: bs.correct_count,
      wrong_count: bs.wrong_count,
      correct_rate: bs.correct_rate,
      actual_missing_count: bs.actual_missing_count,
      unknown_count: bs.unknown_count,
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: bs.avg_forecast_direction_concentration,
      avg_pattern_concentration_score: bs.avg_pattern_concentration_score,
      avg_expression_similarity_mean: bs.avg_expression_similarity_mean,
      avg_abs_surprise_value: bs.avg_abs_surprise_value,
      avg_abs_consensus_prev_gap: bs.avg_abs_consensus_prev_gap,
      avg_predictability_index: bs.avg_predictability_index,
      question_id: '',
      answer: '',
      notes: 'predictability_bucket_summary'
    });
  }

  var predictabilityByCohort = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) {
    return (String(row.cohort_id || '').trim() || 'unknown') + '||' + (String(row.predictability_bucket || '').trim() || 'unknown');
  });
  var predictabilityKeys = Object.keys(predictabilityByCohort).sort();
  for (var pb = 0; pb < predictabilityKeys.length; pb++) {
    var key2 = predictabilityKeys[pb];
    var parts2 = key2.split('||');
    var pcCohortId = parts2[0];
    var pcBucket = parts2[1] || 'unknown';
    var pcRows = predictabilityByCohort[key2] || [];
    var pcs = _signalSynchronyCohortCharacterizationSummarizeGroup_(pcRows);
    out.push({
      generated_ts: generatedTs,
      section: 'D_PREDICTABILITY_BY_COHORT',
      row_type: 'PREDICTABILITY_BY_COHORT',
      cohort_id: pcCohortId,
      cohort_group: String(pcRows[0] && pcRows[0].cohort_group || '').trim() || _signalSynchronyCohortCharacterizationCohortGroup_(pcCohortId),
      comparison_label: '',
      scope_type: 'COHORT_PREDICTABILITY_BUCKET',
      scope_value: pcBucket,
      event_family: '',
      provider: '',
      predictability_bucket: pcBucket,
      sample_groups: pcs.sample_groups,
      unique_events: pcs.unique_events,
      providers_present: pcs.providers_present,
      comparable_rows: pcs.comparable_rows,
      correct_count: pcs.correct_count,
      wrong_count: pcs.wrong_count,
      correct_rate: pcs.correct_rate,
      actual_missing_count: pcs.actual_missing_count,
      unknown_count: pcs.unknown_count,
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: pcs.avg_forecast_direction_concentration,
      avg_pattern_concentration_score: pcs.avg_pattern_concentration_score,
      avg_expression_similarity_mean: pcs.avg_expression_similarity_mean,
      avg_abs_surprise_value: pcs.avg_abs_surprise_value,
      avg_abs_consensus_prev_gap: pcs.avg_abs_consensus_prev_gap,
      avg_predictability_index: pcs.avg_predictability_index,
      question_id: '',
      answer: '',
      notes: 'predictability_by_cohort_summary'
    });
  }

  var noteRows = _signalSynchronyCohortCharacterizationInterpretationNotes_(generatedTs, rows, warnings);
  for (var n = 0; n < noteRows.length; n++) out.push(noteRows[n]);

  out.sort(function(a, b) {
    var order = {
      'METHODOLOGY': 1,
      'A_COHORT_OUTCOME_SUMMARY': 2,
      'B_COHORT_FAMILY_SUMMARY': 3,
      'B_COHORT_PROVIDER_SUMMARY': 4,
      'C_STRUCTURAL_COMPARISON': 5,
      'D_PREDICTABILITY_INDEX_SUMMARY': 6,
      'D_PREDICTABILITY_BY_COHORT': 7,
      'E_INTERPRETATION_NOTES': 8
    };
    var ao = Number(order[String(a.section || '')] || 99);
    var bo = Number(order[String(b.section || '')] || 99);
    if (ao !== bo) return ao - bo;
    return String(a.cohort_id || '').localeCompare(String(b.cohort_id || '')) ||
      String(a.provider || '').localeCompare(String(b.provider || '')) ||
      String(a.predictability_bucket || '').localeCompare(String(b.predictability_bucket || '')) ||
      String(a.comparison_label || '').localeCompare(String(b.comparison_label || '')) ||
      String(a.question_id || '').localeCompare(String(b.question_id || ''));
  });

  if (warnings && warnings.length) {
    out.push({
      generated_ts: generatedTs,
      section: 'E_INTERPRETATION_NOTES',
      row_type: 'DIAGNOSTIC_NOTE',
      cohort_id: '',
      cohort_group: '',
      comparison_label: '',
      scope_type: '',
      scope_value: '',
      event_family: '',
      provider: '',
      predictability_bucket: '',
      sample_groups: '',
      unique_events: '',
      providers_present: '',
      comparable_rows: '',
      correct_count: '',
      wrong_count: '',
      correct_rate: '',
      actual_missing_count: '',
      unknown_count: '',
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: '',
      avg_pattern_concentration_score: '',
      avg_expression_similarity_mean: '',
      avg_abs_surprise_value: '',
      avg_abs_consensus_prev_gap: '',
      avg_predictability_index: '',
      question_id: 'WARNINGS',
      answer: 'See notes for source-mapping or availability warnings.',
      notes: _uniqueStrings_(warnings).join(' | ')
    });
  }

  return out;
}

function _signalSynchronyCohortCharacterizationInterpretationNotes_(generatedTs, rows, warnings) {
  rows = rows || [];
  var out = [];
  var cohortGroups = _signalSynchronyCohortCharacterizationGroupBy_(rows, function(row) { return String(row.cohort_group || '').trim() || 'unknown'; });
  var cohortA = cohortGroups.cohort_a || [];
  var deterministic = cohortGroups.deterministic || [];
  var random = cohortGroups.random || [];
  var allOthers = rows.filter(function(row) { return String(row.cohort_group || '').trim() !== 'cohort_a'; });

  var compAll = _signalSynchronyCohortCharacterizationComparisonStats_(cohortA, allOthers);
  var compDet = _signalSynchronyCohortCharacterizationComparisonStats_(cohortA, deterministic);
  var compRnd = _signalSynchronyCohortCharacterizationComparisonStats_(cohortA, random);
  var compDetRnd = _signalSynchronyCohortCharacterizationComparisonStats_(deterministic, random);

  function note(questionId, answer, notes) {
    out.push({
      generated_ts: generatedTs,
      section: 'E_INTERPRETATION_NOTES',
      row_type: 'INTERPRETATION_NOTE',
      cohort_id: '',
      cohort_group: '',
      comparison_label: '',
      scope_type: '',
      scope_value: '',
      event_family: '',
      provider: '',
      predictability_bucket: '',
      sample_groups: '',
      unique_events: '',
      providers_present: '',
      comparable_rows: '',
      correct_count: '',
      wrong_count: '',
      correct_rate: '',
      actual_missing_count: '',
      unknown_count: '',
      family_distribution_difference: '',
      provider_distribution_difference: '',
      avg_forecast_direction_concentration: '',
      avg_pattern_concentration_score: '',
      avg_expression_similarity_mean: '',
      avg_abs_surprise_value: '',
      avg_abs_consensus_prev_gap: '',
      avg_predictability_index: '',
      question_id: questionId,
      answer: answer,
      notes: notes
    });
  }

  function describeDifference(comp) {
    return 'family_tv=' + (comp.family_tv === '' ? 'n/a' : comp.family_tv) +
      '; provider_tv=' + (comp.provider_tv === '' ? 'n/a' : comp.provider_tv) +
      '; direction_delta=' + (comp.direction_delta === '' ? 'n/a' : comp.direction_delta) +
      '; pattern_delta=' + (comp.pattern_delta === '' ? 'n/a' : comp.pattern_delta) +
      '; surprise_delta=' + (comp.surprise_delta === '' ? 'n/a' : comp.surprise_delta) +
      '; predictability_delta=' + (comp.predictability_delta === '' ? 'n/a' : comp.predictability_delta);
  }

  var answer1 = compDet.family_tv !== '' || compRnd.family_tv !== ''
    ? 'Cohort A looks ' + _signalSynchronyCohortCharacterizationDifferencePhrase_(compAll) + ' relative to later cohorts, but the evidence is descriptive.'
    : 'Cohort A structure is not clearly distinguishable from later cohorts with the available rows.';
  note('Q1', answer1, 'A_vs_all_others; ' + describeDifference(compAll));

  var answer2 = compDet.family_tv !== '' || compRnd.family_tv !== ''
    ? 'Cohort A appears ' + _signalSynchronyCohortCharacterizationDifferencePhrase_(compDet) + ' in event-family mix versus deterministic cohorts and ' + _signalSynchronyCohortCharacterizationDifferencePhrase_(compRnd) + ' versus random cohorts.'
    : 'Event-family concentration differences are not clear enough to call from the current sample.';
  note('Q2', answer2, 'A_vs_deterministic; A_vs_random; ' + describeDifference(compDet) + '; ' + describeDifference(compRnd));

  var answer3 = compDet.provider_tv !== '' || compRnd.provider_tv !== ''
    ? 'Cohort A appears ' + _signalSynchronyCohortCharacterizationDifferencePhrase_(compDet, 'provider') + ' in provider mix versus deterministic cohorts and ' + _signalSynchronyCohortCharacterizationDifferencePhrase_(compRnd, 'provider') + ' versus random cohorts.'
    : 'Provider concentration differences are not clearly separable in the current sample.';
  note('Q3', answer3, 'provider_distribution_only; ' + describeDifference(compDet) + '; ' + describeDifference(compRnd));

  var answer4 = _signalSynchronyCohortCharacterizationCompareDirection_(cohortA, deterministic, 'forecast_direction_concentration');
  note('Q4', answer4, 'A_vs_deterministic_direction=' + describeDifference(compDet));

  var answer5 = _signalSynchronyCohortCharacterizationCompareDirection_(cohortA, deterministic, 'pattern_concentration_score');
  note('Q5', answer5, 'A_vs_deterministic_pattern=' + describeDifference(compDet));

  var answer6 = _signalSynchronyCohortCharacterizationCompareSurprise_(cohortA, deterministic);
  note('Q6', answer6, 'A_vs_deterministic_surprise=' + describeDifference(compDet));

  var answer7 = _signalSynchronyCohortCharacterizationComparePredictability_(cohortA, deterministic);
  note('Q7', answer7, 'A_vs_deterministic_predictability=' + describeDifference(compDet));

  var answer8 = _signalSynchronyCohortCharacterizationRandomReproductionNote_(cohortA, random, 'Q8');
  note('Q8', answer8, 'A_vs_random=' + describeDifference(compRnd));

  var answer9 = _signalSynchronyCohortCharacterizationRandomVsDeterministicNote_(deterministic, random);
  note('Q9', answer9, 'deterministic_vs_random=' + describeDifference(compDetRnd));

  var answer10 = _signalSynchronyCohortCharacterizationOverallConclusion_(compAll, compDet, compRnd, compDetRnd, cohortA, deterministic, random);
  note('Q10', answer10, 'conclusion=' + describeDifference(compAll) + '; ' + describeDifference(compDet) + '; ' + describeDifference(compRnd) + '; ' + describeDifference(compDetRnd));

  return out;
}

function _signalSynchronyCohortCharacterizationComparisonStats_(leftRows, rightRows) {
  leftRows = leftRows || [];
  rightRows = rightRows || [];
  var leftStats = _signalSynchronyCohortCharacterizationSummarizeGroup_(leftRows);
  var rightStats = _signalSynchronyCohortCharacterizationSummarizeGroup_(rightRows);
  return {
    family_tv: _signalSynchronyCohortCharacterizationTvDistance_(
      _signalSynchronyCohortCharacterizationDistribution_(leftRows, 'event_family'),
      _signalSynchronyCohortCharacterizationDistribution_(rightRows, 'event_family')
    ),
    provider_tv: _signalSynchronyCohortCharacterizationTvDistance_(
      _signalSynchronyCohortCharacterizationDistribution_(leftRows, 'provider'),
      _signalSynchronyCohortCharacterizationDistribution_(rightRows, 'provider')
    ),
    direction_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_forecast_direction_concentration, rightStats.avg_forecast_direction_concentration),
    pattern_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_pattern_concentration_score, rightStats.avg_pattern_concentration_score),
    surprise_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_abs_surprise_value, rightStats.avg_abs_surprise_value),
    predictability_delta: _signalSynchronyCohortCharacterizationDelta_(leftStats.avg_predictability_index, rightStats.avg_predictability_index)
  };
}

function _signalSynchronyCohortCharacterizationDifferencePhrase_(comparisonStats, mode) {
  comparisonStats = comparisonStats || {};
  var familyTv = _numOrNull_(comparisonStats.family_tv);
  var providerTv = _numOrNull_(comparisonStats.provider_tv);
  var directionDelta = _numOrNull_(comparisonStats.direction_delta);
  var patternDelta = _numOrNull_(comparisonStats.pattern_delta);
  var surpriseDelta = _numOrNull_(comparisonStats.surprise_delta);
  var predictabilityDelta = _numOrNull_(comparisonStats.predictability_delta);

  var anchor = familyTv != null && familyTv >= 0.2 ? 'materially different' : 'only modestly different';
  if (mode === 'provider') {
    anchor = providerTv != null && providerTv >= 0.2 ? 'materially different' : 'only modestly different';
  }
  if (directionDelta != null && directionDelta > 0.05) return anchor + ' and higher on forecast concentration';
  if (directionDelta != null && directionDelta < -0.05) return anchor + ' and lower on forecast concentration';
  if (patternDelta != null && patternDelta > 0.05) return anchor + ' and higher on pattern concentration';
  if (patternDelta != null && patternDelta < -0.05) return anchor + ' and lower on pattern concentration';
  if (surpriseDelta != null && surpriseDelta > 0.1) return anchor + ' with larger surprise gaps';
  if (surpriseDelta != null && surpriseDelta < -0.1) return anchor + ' with smaller surprise gaps';
  if (predictabilityDelta != null && predictabilityDelta > 0.05) return anchor + ' and slightly higher predictability';
  if (predictabilityDelta != null && predictabilityDelta < -0.05) return anchor + ' and slightly lower predictability';
  return anchor;
}

function _signalSynchronyCohortCharacterizationCompareDirection_(leftRows, rightRows, fieldName) {
  leftRows = leftRows || [];
  rightRows = rightRows || [];
  var leftAvg = _signalSynchronyCohortCharacterizationAverage_(leftRows, fieldName);
  var rightAvg = _signalSynchronyCohortCharacterizationAverage_(rightRows, fieldName);
  if (leftAvg == null || rightAvg == null) return 'Insufficient data to compare ' + fieldName + ' across cohorts.';
  var delta = rightAvg - leftAvg;
  if (Math.abs(delta) <= 0.03) return 'Cohort A is broadly similar on ' + fieldName + ' relative to the comparison cohort.';
  if (delta > 0) return 'The comparison cohort is higher on ' + fieldName + ' than Cohort A.';
  return 'Cohort A is higher on ' + fieldName + ' than the comparison cohort.';
}

function _signalSynchronyCohortCharacterizationCompareSurprise_(leftRows, rightRows) {
  var leftAvg = _signalSynchronyCohortCharacterizationAverage_(leftRows, 'abs_surprise_value');
  var rightAvg = _signalSynchronyCohortCharacterizationAverage_(rightRows, 'abs_surprise_value');
  if (leftAvg == null || rightAvg == null) return 'Surprise gap comparison remains inconclusive.';
  var delta = rightAvg - leftAvg;
  if (Math.abs(delta) <= 0.1) return 'Cohort A and the comparison cohort have similar surprise gaps.';
  if (delta > 0) return 'The comparison cohort has larger surprise gaps than Cohort A.';
  return 'Cohort A has larger surprise gaps than the comparison cohort.';
}

function _signalSynchronyCohortCharacterizationComparePredictability_(leftRows, rightRows) {
  var leftAvg = _signalSynchronyCohortCharacterizationAverage_(leftRows, 'predictability_index');
  var rightAvg = _signalSynchronyCohortCharacterizationAverage_(rightRows, 'predictability_index');
  if (leftAvg == null || rightAvg == null) return 'Predictability index comparison remains inconclusive.';
  var delta = rightAvg - leftAvg;
  if (Math.abs(delta) <= 0.05) return 'Cohort A and the comparison cohort are similar on the predictability index.';
  if (delta > 0) return 'The comparison cohort has a slightly higher predictability index than Cohort A.';
  return 'Cohort A has a slightly higher predictability index than the comparison cohort.';
}

function _signalSynchronyCohortCharacterizationRandomReproductionNote_(leftRows, rightRows, questionId) {
  var leftRate = _signalSynchronyCohortCharacterizationAverage_(leftRows, 'correct_rate');
  var rightRate = _signalSynchronyCohortCharacterizationAverage_(rightRows, 'correct_rate');
  if (leftRate == null || rightRate == null) return 'Random cohort reproduction remains unresolved.';
  var delta = rightRate - leftRate;
  if (Math.abs(delta) <= 0.05) return 'Random cohort behaves broadly like Cohort A on outcome alignment.';
  if (delta > 0) return 'Random cohort is slightly more aligned than Cohort A in this sample.';
  return 'Random cohort is slightly less aligned than Cohort A in this sample.';
}

function _signalSynchronyCohortCharacterizationRandomVsDeterministicNote_(deterministicRows, randomRows) {
  var det = _signalSynchronyCohortCharacterizationAverage_(deterministicRows, 'correct_rate');
  var rnd = _signalSynchronyCohortCharacterizationAverage_(randomRows, 'correct_rate');
  if (det == null || rnd == null) return 'Deterministic versus random comparison remains unresolved.';
  var delta = rnd - det;
  if (Math.abs(delta) <= 0.05) return 'Random and deterministic cohorts are broadly similar on outcome alignment.';
  if (delta > 0) return 'Random cohort is slightly more aligned than deterministic cohorts in this sample.';
  return 'Random cohort is slightly less aligned than deterministic cohorts in this sample.';
}

function _signalSynchronyCohortCharacterizationOverallConclusion_(compAll, compDet, compRnd, compDetRnd, cohortA, deterministic, random) {
  var familyTv = _numOrNull_(compAll.family_tv);
  var providerTv = _numOrNull_(compAll.provider_tv);
  var directionDelta = _numOrNull_(compAll.direction_delta);
  var patternDelta = _numOrNull_(compAll.pattern_delta);
  var surpriseDelta = _numOrNull_(compAll.surprise_delta);
  var predictabilityDelta = _numOrNull_(compAll.predictability_delta);
  var parts = [];
  if (familyTv != null && familyTv >= 0.2) parts.push('Cohort A looks structurally different in family mix');
  else parts.push('Cohort A does not look strongly family-distinct');
  if (providerTv != null && providerTv >= 0.2) parts.push('provider mix also differs modestly');
  if (directionDelta != null && Math.abs(directionDelta) >= 0.05) parts.push('forecast concentration differs modestly');
  if (patternDelta != null && Math.abs(patternDelta) >= 0.05) parts.push('pattern concentration differs modestly');
  if (surpriseDelta != null && Math.abs(surpriseDelta) >= 0.1) parts.push('surprise gaps are not identical');
  if (predictabilityDelta != null && Math.abs(predictabilityDelta) >= 0.05) parts.push('predictability index shifts slightly');
  parts.push('the result is descriptive, not statistical proof');
  return parts.join('; ');
}

function _signalSynchronyCohortCharacterizationSummarizeGroup_(rows) {
  rows = rows || [];
  var total = rows.length;
  var uniqueEvents = {};
  var providers = {};
  var comparable = 0;
  var correct = 0;
  var wrong = 0;
  var actualMissing = 0;
  var unknown = 0;
  var directionVals = [];
  var patternVals = [];
  var similarityVals = [];
  var surpriseVals = [];
  var gapVals = [];
  var predictVals = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (eventId) uniqueEvents[eventId] = true;
    if (provider) providers[provider] = true;

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
    var su = _numOrNull_(row.abs_surprise_value);
    if (su != null) surpriseVals.push(su);
    var g = _numOrNull_(row.abs_consensus_prev_gap);
    if (g != null) gapVals.push(g);
    var pi = _numOrNull_(row.predictability_index);
    if (pi != null) predictVals.push(pi);
  }

  var correctRate = comparable ? _round4_(correct / comparable) : '';
  return {
    sample_groups: total,
    unique_events: Object.keys(uniqueEvents).length,
    providers_present: Object.keys(providers).sort().join('|'),
    provider_count: Object.keys(providers).length,
    comparable_rows: comparable,
    correct_count: correct,
    wrong_count: wrong,
    correct_rate: correctRate,
    actual_missing_count: actualMissing,
    unknown_count: unknown,
    avg_forecast_direction_concentration: _signalSynchronyCohortCharacterizationAverageFromArray_(directionVals),
    avg_pattern_concentration_score: _signalSynchronyCohortCharacterizationAverageFromArray_(patternVals),
    avg_expression_similarity_mean: _signalSynchronyCohortCharacterizationAverageFromArray_(similarityVals),
    avg_abs_surprise_value: _signalSynchronyCohortCharacterizationAverageFromArray_(surpriseVals),
    avg_abs_consensus_prev_gap: _signalSynchronyCohortCharacterizationAverageFromArray_(gapVals),
    avg_predictability_index: _signalSynchronyCohortCharacterizationAverageFromArray_(predictVals)
  };
}

function _signalSynchronyCohortCharacterizationGroupBy_(rows, keyFn) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(keyFn(row, i) || '').trim() || 'unknown';
    if (!out[key]) out[key] = [];
    out[key].push(row);
  }
  return out;
}

function _signalSynchronyCohortCharacterizationAverage_(rows, fieldName) {
  rows = rows || [];
  var values = [];
  for (var i = 0; i < rows.length; i++) {
    var v = _numOrNull_(rows[i] && rows[i][fieldName]);
    if (v != null) values.push(v);
  }
  return _signalSynchronyCohortCharacterizationAverageFromArray_(values);
}

function _signalSynchronyCohortCharacterizationAverageFromArray_(values) {
  values = values || [];
  var sum = 0;
  var count = 0;
  for (var i = 0; i < values.length; i++) {
    var v = _numOrNull_(values[i]);
    if (v == null) continue;
    sum += Number(v || 0);
    count += 1;
  }
  return count ? _round4_(sum / count) : '';
}

function _signalSynchronyCohortCharacterizationDistribution_(rows, fieldName) {
  var counts = {};
  var total = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    var key = String(rows[i] && rows[i][fieldName] || '').trim() || 'unknown';
    counts[key] = Number(counts[key] || 0) + 1;
    total += 1;
  }
  var out = {};
  Object.keys(counts).sort().forEach(function(key) {
    out[key] = total ? _round4_(counts[key] / total) : 0;
  });
  return out;
}

function _signalSynchronyCohortCharacterizationDistributionString_(dist) {
  var keys = Object.keys(dist || {}).sort();
  var out = [];
  for (var i = 0; i < keys.length; i++) {
    out.push(keys[i] + ':' + dist[keys[i]]);
  }
  return out.join('|');
}

function _signalSynchronyCohortCharacterizationTvDistance_(distA, distB) {
  var keys = {};
  Object.keys(distA || {}).forEach(function(k) { keys[k] = true; });
  Object.keys(distB || {}).forEach(function(k) { keys[k] = true; });
  var sum = 0;
  var count = 0;
  Object.keys(keys).forEach(function(key) {
    sum += Math.abs(Number(distA && distA[key] || 0) - Number(distB && distB[key] || 0));
    count += 1;
  });
  return count ? _round4_(sum / 2) : '';
}

function _signalSynchronyCohortCharacterizationDelta_(left, right) {
  var a = _numOrNull_(left);
  var b = _numOrNull_(right);
  if (a == null || b == null) return '';
  return _round4_(b - a);
}

function _signalSynchronyCohortCharacterizationCountCohorts_(rows) {
  var seen = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var cohort = String(rows[i] && rows[i].cohort_id || '').trim();
    if (cohort) seen[cohort] = true;
  }
  return Object.keys(seen).length;
}
