/*******************************************************
 * provider_character_direct_expression_outcome_check.js
 * - Diagnostic-only Provider Character v2 - Direct Expression Outcome Check v1
 * - Compares accumulated microcohort forecast tendencies against released economic actuals
 * - Derived-only output written to diagnostics workbook
 *******************************************************/

function buildProviderCharacterDirectExpressionOutcomeCheck_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var warnings = [];
  var writeOutput = params.write_output !== false;

  try {
    var microBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Microcohort', warnings, false);
    if (!microBundle) {
      throw new Error('Outcome check requires Provider_Character_Direct_Expression_Microcohort.');
    }
    if (String(microBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
      throw new Error('Outcome check requires Provider_Character_Direct_Expression_Microcohort in diagnostics workbook.');
    }

    var validationBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Validation', warnings, false);
    if (!validationBundle) {
      throw new Error('Outcome check requires Provider_Character_Direct_Expression_Validation.');
    }
    if (String(validationBundle.workbook_type || '').trim() !== 'DIAGNOSTICS') {
      throw new Error('Outcome check requires Provider_Character_Direct_Expression_Validation in diagnostics workbook.');
    }

    var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
    if (!eventBundle) {
      throw new Error('Outcome check requires canonical Event sheet access.');
    }
    if (String(eventBundle.workbook_type || '').trim() !== 'MAIN') {
      throw new Error('Outcome check requires canonical Event sheet from main workbook.');
    }

    var microRows = _providerCharacterMicroExpressionBundleRowsToObjects_(microBundle);
    var validationRows = _providerCharacterMicroExpressionBundleRowsToObjects_(validationBundle);
    var eventRows = _providerCharacterMicroExpressionBundleRowsToObjects_(eventBundle);

    var validationCounts = _providerCharacterDirectExpressionOutcomeCheckValidationCounts_(validationRows);
    var eventMap = _providerCharacterDirectExpressionOutcomeCheckEventMap_(eventRows);
    var outRows = [];

    for (var i = 0; i < microRows.length; i++) {
      var micro = microRows[i] || {};
      var sampleGroupId = String(micro.sample_group_id || '').trim();
      if (!sampleGroupId) continue;
      outRows.push(_providerCharacterDirectExpressionOutcomeCheckBuildRow_(
        generatedTs,
        micro,
        validationCounts[sampleGroupId] || 0,
        eventMap,
        warnings
      ));
    }

    outRows.sort(function(a, b) {
      if (String(a.release_ts || '') !== String(b.release_ts || '')) {
        return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
      }
      if (String(a.provider || '') !== String(b.provider || '')) {
        return String(a.provider || '').localeCompare(String(b.provider || ''));
      }
      return String(a.sample_group_id || '').localeCompare(String(b.sample_group_id || ''));
    });

    var sheetRef = null;
    if (writeOutput) {
      sheetRef = getDiagnosticsSheet_(
        'Provider_Character_Direct_Expression_Outcome_Check',
        _providerCharacterDirectExpressionOutcomeCheckHeaders_(),
        warnings
      );
      _rewriteSheetRowsPreservingHeaders_(
        sheetRef.sheet,
        sheetRef.headers,
        _characterResidualObjectsToRows_(outRows, sheetRef.headers)
      );
    }

    var summary = _providerCharacterDirectExpressionOutcomeCheckSummarize_(outRows);
    return {
      status: 'ok',
      generated_ts: generatedTs,
      outcome_check_sheet: sheetRef ? sheetRef.sheet.getName() : 'Provider_Character_Direct_Expression_Outcome_Check',
      sample_groups_checked: outRows.length,
      actual_available_count: summary.actual_available_count,
      comparable_count: summary.comparable_count,
      forecast_correct_count: summary.forecast_correct_count,
      forecast_wrong_count: summary.forecast_wrong_count,
      correct_rate: summary.correct_rate,
      stable_forecast_count: summary.stable_forecast_count,
      stable_forecast_correct_count: summary.stable_forecast_correct_count,
      stable_forecast_wrong_count: summary.stable_forecast_wrong_count,
      stable_forecast_correct_rate: summary.stable_forecast_correct_rate,
      unstable_forecast_count: summary.unstable_forecast_count,
      unstable_forecast_correct_count: summary.unstable_forecast_correct_count,
      unstable_forecast_wrong_count: summary.unstable_forecast_wrong_count,
      unstable_forecast_correct_rate: summary.unstable_forecast_correct_rate,
      mixed_pattern_count: summary.mixed_pattern_count,
      mixed_pattern_correct_count: summary.mixed_pattern_correct_count,
      mixed_pattern_wrong_count: summary.mixed_pattern_wrong_count,
      unknown_or_uncomparable_count: summary.unknown_or_uncomparable_count,
      actual_missing_count: summary.actual_missing_count,
      warnings: _uniqueStrings_(warnings),
      reminder: 'Outcome check only; not Signal Synchrony.'
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

function buildProviderCharacterDirectExpressionOutcomeCheck(params) {
  return buildProviderCharacterDirectExpressionOutcomeCheck_(params || {});
}

function _providerCharacterDirectExpressionOutcomeCheckHeaders_() {
  return [
    'generated_ts',
    'sample_group_id',
    'event_id',
    'provider',
    'indicator_name',
    'country',
    'release_ts',
    'consensus_value',
    'prev_revision',
    'released_value',
    'released_ts',
    'release_status',
    'actual_economic_direction',
    'actual_vs_previous_direction',
    'actual_source_provider',
    'actual_source_series_id',
    'actual_transform',
    'forecast_direction_distribution',
    'dominant_forecast_direction',
    'normalized_forecast_direction',
    'forecast_direction_concentration',
    'forecast_value_min',
    'forecast_value_max',
    'forecast_value_mean',
    'forecast_value_stddev',
    'pattern_concentration_score',
    'expression_similarity_mean',
    'microcohort_interpretation_label',
    'forecast_matches_actual',
    'outcome_result_label',
    'reproducibility_outcome_label',
    'outcome_check_status',
    'notes'
  ];
}

function _providerCharacterDirectExpressionOutcomeCheckValidationCounts_(validationRows) {
  var counts = {};
  for (var i = 0; i < (validationRows || []).length; i++) {
    var row = validationRows[i] || {};
    if (String(row.validation_run_id || '').trim() !== 'microcohort_rerun_v1') continue;
    if (String(row.validation_mode || '').trim() !== 'microcohort_same_capture_path_rerun') continue;
    var sampleGroupId = String(row.sample_group_id || '').trim();
    if (!sampleGroupId) continue;
    counts[sampleGroupId] = Number(counts[sampleGroupId] || 0) + 1;
  }
  return counts;
}

function _providerCharacterDirectExpressionOutcomeCheckEventMap_(eventRows) {
  var map = {};
  for (var i = 0; i < (eventRows || []).length; i++) {
    var row = eventRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    map[eventId] = row;
  }
  return map;
}

function _providerCharacterDirectExpressionOutcomeCheckBuildRow_(generatedTs, micro, validationCount, eventMap, warnings) {
  micro = micro || {};
  var eventId = String(micro.event_id || '').trim();
  var eventRow = eventMap[eventId] || null;
  if (!eventRow) warnings.push('missing_event:' + eventId);

  var consensusValue = _numOrNull_(eventRow ? eventRow.consensus_value : '');
  var prevRevision = _numOrNull_(eventRow ? eventRow.prev_revision : '');
  var releasedValue = _numOrNull_(eventRow ? eventRow.released_value : '');
  var actualDirection = _providerCharacterDirectExpressionOutcomeCheckActualDirection_(consensusValue, releasedValue, prevRevision);
  var actualVsPreviousDirection = _providerCharacterDirectExpressionOutcomeCheckDirectionFromValues_(releasedValue, prevRevision);
  var normalizedForecastDirection = _providerCharacterDirectExpressionOutcomeCheckNormalizeForecastDirection_(micro.dominant_forecast_direction);

  var forecastMatchesActual = '';
  var outcomeResultLabel = 'DIRECTION_UNCOMPARABLE';
  var outcomeCheckStatus = 'direction_uncomparable';

  if (actualDirection.status === 'actual_missing') {
    outcomeResultLabel = 'ACTUAL_MISSING';
    outcomeCheckStatus = 'actual_missing';
  } else if (actualDirection.status === 'actual_prev_based_only') {
    outcomeResultLabel = 'DIRECTION_UNCOMPARABLE';
    outcomeCheckStatus = 'actual_prev_based_only';
  } else if (normalizedForecastDirection === 'unknown') {
    outcomeResultLabel = 'FORECAST_UNKNOWN';
    outcomeCheckStatus = 'direction_uncomparable';
  } else {
    forecastMatchesActual = (normalizedForecastDirection === actualDirection.direction) ? 'TRUE' : 'FALSE';
    outcomeCheckStatus = 'ok';
    if (forecastMatchesActual === 'TRUE' && actualDirection.direction === 'inline') {
      outcomeResultLabel = 'FORECAST_INLINE_CORRECT';
    } else if (forecastMatchesActual === 'TRUE') {
      outcomeResultLabel = 'FORECAST_CORRECT';
    } else {
      outcomeResultLabel = 'FORECAST_WRONG';
    }
  }

  var reproOutcomeLabel = _providerCharacterDirectExpressionOutcomeCheckReproOutcomeLabel_(
    String(micro.interpretation_label || '').trim(),
    outcomeResultLabel
  );

  return {
    generated_ts: generatedTs,
    sample_group_id: String(micro.sample_group_id || '').trim(),
    event_id: eventId,
    provider: String(micro.provider || '').trim(),
    indicator_name: String(micro.indicator_name || '').trim(),
    country: String(micro.country || '').trim(),
    release_ts: String(micro.release_ts || '').trim(),
    consensus_value: consensusValue == null ? '' : consensusValue,
    prev_revision: prevRevision == null ? '' : prevRevision,
    released_value: releasedValue == null ? '' : releasedValue,
    released_ts: String(eventRow && eventRow.released_ts || '').trim(),
    release_status: String(eventRow && eventRow.release_status || '').trim(),
    actual_economic_direction: actualDirection.direction,
    actual_vs_previous_direction: actualVsPreviousDirection,
    actual_source_provider: String(eventRow && eventRow.source_provider || '').trim(),
    actual_source_series_id: String(eventRow && eventRow.source_series_id || '').trim(),
    actual_transform: String(eventRow && eventRow.transform || '').trim(),
    forecast_direction_distribution: String(micro.forecast_direction_distribution || '').trim(),
    dominant_forecast_direction: String(micro.dominant_forecast_direction || '').trim(),
    normalized_forecast_direction: normalizedForecastDirection,
    forecast_direction_concentration: _numOrNull_(micro.forecast_direction_concentration) == null ? '' : _numOrNull_(micro.forecast_direction_concentration),
    forecast_value_min: _numOrNull_(micro.forecast_value_min) == null ? '' : _numOrNull_(micro.forecast_value_min),
    forecast_value_max: _numOrNull_(micro.forecast_value_max) == null ? '' : _numOrNull_(micro.forecast_value_max),
    forecast_value_mean: _numOrNull_(micro.forecast_value_mean) == null ? '' : _numOrNull_(micro.forecast_value_mean),
    forecast_value_stddev: _numOrNull_(micro.forecast_value_stddev) == null ? '' : _numOrNull_(micro.forecast_value_stddev),
    pattern_concentration_score: _numOrNull_(micro.pattern_concentration_score) == null ? '' : _numOrNull_(micro.pattern_concentration_score),
    expression_similarity_mean: _numOrNull_(micro.expression_similarity_mean_if_available) == null ? '' : _numOrNull_(micro.expression_similarity_mean_if_available),
    microcohort_interpretation_label: String(micro.interpretation_label || '').trim(),
    forecast_matches_actual: forecastMatchesActual,
    outcome_result_label: outcomeResultLabel,
    reproducibility_outcome_label: reproOutcomeLabel,
    outcome_check_status: outcomeCheckStatus,
    notes: [
      'validation_rerun_rows=' + Number(validationCount || 0),
      'not_signal_synchrony_yet=TRUE',
      !eventRow ? 'missing_canonical_event=TRUE' : '',
      actualDirection.status === 'actual_prev_based_only' ? 'actual_direction_prev_based_only=TRUE' : ''
    ].filter(Boolean).join('; ')
  };
}

function _providerCharacterDirectExpressionOutcomeCheckActualDirection_(consensusValue, releasedValue, prevRevision) {
  if (consensusValue == null || releasedValue == null) {
    if (releasedValue != null && prevRevision != null) {
      return {
        direction: 'unknown_or_prev_based',
        status: 'actual_prev_based_only'
      };
    }
    return {
      direction: 'unknown',
      status: 'actual_missing'
    };
  }
  return {
    direction: _providerCharacterDirectExpressionOutcomeCheckDirectionFromValues_(releasedValue, consensusValue),
    status: 'ok'
  };
}

function _providerCharacterDirectExpressionOutcomeCheckDirectionFromValues_(left, right) {
  var a = _numOrNull_(left);
  var b = _numOrNull_(right);
  if (a == null || b == null) return 'unknown';
  if (a > b) return 'above';
  if (a < b) return 'below';
  return 'inline';
}

function _providerCharacterDirectExpressionOutcomeCheckNormalizeForecastDirection_(value) {
  var raw = String(value || '').trim().toLowerCase();
  if (!raw) return 'unknown';
  if (['above', 'stronger', 'higher', 'beat', 'up', 'positive'].indexOf(raw) >= 0) return 'above';
  if (['below', 'weaker', 'lower', 'miss', 'down', 'negative'].indexOf(raw) >= 0) return 'below';
  if (['inline', 'flat', 'unchanged', 'neutral'].indexOf(raw) >= 0) return 'inline';
  return 'unknown';
}

function _providerCharacterDirectExpressionOutcomeCheckReproOutcomeLabel_(interpretationLabel, outcomeResultLabel) {
  var interp = String(interpretationLabel || '').trim();
  var outcome = String(outcomeResultLabel || '').trim();
  if (outcome === 'ACTUAL_MISSING') return 'OUTCOME_UNAVAILABLE';
  if (outcome === 'FORECAST_UNKNOWN' || outcome === 'DIRECTION_UNCOMPARABLE') return 'UNCOMPARABLE';
  var isCorrect = (outcome === 'FORECAST_CORRECT' || outcome === 'FORECAST_INLINE_CORRECT');
  if (interp.indexOf('PATTERN_MIXED') >= 0) return isCorrect ? 'MIXED_PATTERN_CORRECT' : 'MIXED_PATTERN_WRONG';
  if (interp.indexOf('FORECAST_STABLE') === 0) return isCorrect ? 'STABLE_FORECAST_CORRECT' : 'STABLE_FORECAST_WRONG';
  if (interp.indexOf('FORECAST_UNSTABLE') === 0) return isCorrect ? 'UNSTABLE_FORECAST_CORRECT' : 'UNSTABLE_FORECAST_WRONG';
  return 'UNCOMPARABLE';
}

function _providerCharacterDirectExpressionOutcomeCheckSummarize_(rows) {
  var summary = {
    total_sample_groups: 0,
    actual_available_count: 0,
    comparable_count: 0,
    forecast_correct_count: 0,
    forecast_wrong_count: 0,
    correct_rate: '',
    stable_forecast_count: 0,
    stable_forecast_correct_count: 0,
    stable_forecast_wrong_count: 0,
    stable_forecast_correct_rate: '',
    unstable_forecast_count: 0,
    unstable_forecast_correct_count: 0,
    unstable_forecast_wrong_count: 0,
    unstable_forecast_correct_rate: '',
    mixed_pattern_count: 0,
    mixed_pattern_correct_count: 0,
    mixed_pattern_wrong_count: 0,
    unknown_or_uncomparable_count: 0,
    actual_missing_count: 0
  };

  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    summary.total_sample_groups += 1;
    var outcome = String(row.outcome_result_label || '').trim();
    var interp = String(row.microcohort_interpretation_label || '').trim();

    if (String(row.actual_economic_direction || '').trim() && String(row.actual_economic_direction || '').trim() !== 'unknown' && String(row.actual_economic_direction || '').trim() !== 'unknown_or_prev_based') {
      summary.actual_available_count += 1;
    }
    if (outcome === 'ACTUAL_MISSING') {
      summary.actual_missing_count += 1;
      continue;
    }
    if (outcome === 'FORECAST_UNKNOWN' || outcome === 'DIRECTION_UNCOMPARABLE') {
      summary.unknown_or_uncomparable_count += 1;
      continue;
    }

    summary.comparable_count += 1;
    var isCorrect = outcome === 'FORECAST_CORRECT' || outcome === 'FORECAST_INLINE_CORRECT';
    if (isCorrect) summary.forecast_correct_count += 1;
    else if (outcome === 'FORECAST_WRONG') summary.forecast_wrong_count += 1;

    if (interp.indexOf('PATTERN_MIXED') >= 0) {
      summary.mixed_pattern_count += 1;
      if (isCorrect) summary.mixed_pattern_correct_count += 1;
      else summary.mixed_pattern_wrong_count += 1;
    } else if (interp.indexOf('FORECAST_STABLE') === 0) {
      summary.stable_forecast_count += 1;
      if (isCorrect) summary.stable_forecast_correct_count += 1;
      else summary.stable_forecast_wrong_count += 1;
    } else if (interp.indexOf('FORECAST_UNSTABLE') === 0) {
      summary.unstable_forecast_count += 1;
      if (isCorrect) summary.unstable_forecast_correct_count += 1;
      else summary.unstable_forecast_wrong_count += 1;
    }
  }

  if (summary.comparable_count) {
    summary.correct_rate = _round4_(summary.forecast_correct_count / summary.comparable_count);
  }
  if (summary.stable_forecast_count) {
    summary.stable_forecast_correct_rate = _round4_(summary.stable_forecast_correct_count / summary.stable_forecast_count);
  }
  if (summary.unstable_forecast_count) {
    summary.unstable_forecast_correct_rate = _round4_(summary.unstable_forecast_correct_count / summary.unstable_forecast_count);
  }
  return summary;
}
