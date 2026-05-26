/*******************************************************
 * evaluation_report.gs
 * - Build traceable evaluation/report sheets from Predictions
 * - Source of truth remains Event / Predictions / MR_ProviderRuns
 * - Evaluation sheets are derived reporting layers only
 *******************************************************/

function menuBuildEvaluationSheets_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildEvaluationSheets_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Evaluation → Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Evaluation rows=' + (res.rows_written || 0) +
      ' | summary=' + (res.summary_written || 0) +
      ' | scenario=' + (res.scenario_written || 0),
      'Evaluation',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Evaluation → Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildPredictionAggregatesSheet_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildPredictionAggregatesSheet_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Prediction aggregates → Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Prediction aggregates rows=' + (res.rows_written || 0),
      'Prediction Aggregates',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Prediction aggregates → Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildOutcomeLedgerSheet_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildOutcomeLedger_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Outcome ledger -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Outcome ledger rows=' + (res.rows_written || 0),
      'Outcome Ledger',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Outcome ledger -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildOutcomeSummaries_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildOutcomeSummaries_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Outcome summaries -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'ProviderFamily=' + (res.provider_family_rows_written || 0) +
      ' | Convergence=' + (res.convergence_rows_written || 0) +
      ' | Bucket=' + (res.bucket_rows_written || 0),
      'Outcome Summaries',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Outcome summaries -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildOutcomeDiagnostics_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildOutcomeDiagnostics_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Outcome diagnostics -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Outcome diagnostics rows=' + (res.rows_written || 0),
      'Outcome Diagnostics',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Outcome diagnostics -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildEvaluationSheets_() {
  var predSheet = getSheet((CFG && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions');
  if (!predSheet) throw new Error('Predictions sheet missing');

  var rowSheet = _getOrCreateSheet_('Evaluation_Rows');
  var summarySheet = _getOrCreateSheet_('Evaluation_Summary');
  var batchCompareSheet = _getOrCreateSheet_('Evaluation_BatchCompare');
  var scenarioSheet = _getOrCreateSheet_('Evaluation_Scenario');

  var rowHeaders = _evaluationRowHeaders_();
  var summaryHeaders = _evaluationSummaryHeaders_();
  var batchCompareHeaders = _evaluationBatchCompareHeaders_();
  var scenarioHeaders = _evaluationScenarioHeaders_();

  var predHeaders = (typeof _ensurePredHeaders_ === 'function') ? _ensurePredHeaders_(predSheet) : getHeaderNames(predSheet);
  var predIdx = {};
  for (var i = 0; i < predHeaders.length; i++) predIdx[String(predHeaders[i] || '').trim()] = i;

  var predLastRow = predSheet.getLastRow();
  var predLastCol = predSheet.getLastColumn();
  var data = (predLastRow >= 2 && predLastCol >= 1)
    ? predSheet.getRange(2, 1, predLastRow - 1, predLastCol).getValues()
    : [];

  var rowsOut = [];
  var generatedTs = new Date().toISOString();
  for (var r = 0; r < data.length; r++) {
    var src = data[r];
    var evalTs = _predValue_(src, predIdx, 'eval_ts');
    var realDir = _predValue_(src, predIdx, 'mr_real_dir');
    var rowType = String(_predValue_(src, predIdx, 'type') || '').trim().toLowerCase();
    if (!evalTs && !realDir && rowType !== 'batch') continue;
    rowsOut.push(_buildEvaluationRow_(src, predIdx, generatedTs));
  }

  rowsOut = _dedupeEvaluationRowsByPredictionKey_(rowsOut);
  rowsOut = _filterLegacySplitBatchRows_(rowsOut);

  var summaryOut = _buildEvaluationSummaryRows_(rowsOut, generatedTs);
  var batchCompareOut = _buildEvaluationBatchCompareRows_(rowsOut, generatedTs);
  var scenarioOut = _buildEvaluationScenarioRows_(rowsOut, generatedTs);

  _sortEvaluationRows_(rowHeaders, rowsOut);
  _sortEvaluationSummaryRows_(summaryHeaders, summaryOut);
  _sortEvaluationBatchCompareRows_(batchCompareHeaders, batchCompareOut);
  _sortEvaluationScenarioRows_(scenarioHeaders, scenarioOut);

  _rewriteSheet_(rowSheet, rowHeaders, rowsOut);
  _rewriteSheet_(summarySheet, summaryHeaders, summaryOut);
  _rewriteSheet_(batchCompareSheet, batchCompareHeaders, batchCompareOut);
  _rewriteSheet_(scenarioSheet, scenarioHeaders, scenarioOut);

  return {
    row_sheet: rowSheet.getName(),
    summary_sheet: summarySheet.getName(),
    batch_compare_sheet: batchCompareSheet.getName(),
    scenario_sheet: scenarioSheet.getName(),
    rows_written: rowsOut.length,
    summary_written: summaryOut.length,
    batch_compare_written: batchCompareOut.length,
    scenario_written: scenarioOut.length
  };
}

function getOrCreateOutcomeLedgerSheet_() {
  return _getOrCreateSheet_('Outcome_Ledger');
}

function ensureOutcomeLedgerHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _outcomeLedgerHeaders_());
}

function buildOutcomeLedger_() {
  var predSheet = getSheet((CFG && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions');
  if (!predSheet) throw new Error('Predictions sheet missing');

  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = _outcomeLedgerHeaders_();
  var predHeaders = (typeof _ensurePredHeaders_ === 'function') ? _ensurePredHeaders_(predSheet) : getHeaderNames(predSheet);
  var predIdx = {};
  for (var i = 0; i < predHeaders.length; i++) predIdx[String(predHeaders[i] || '').trim()] = i;

  var predLastRow = predSheet.getLastRow();
  var predLastCol = predSheet.getLastColumn();
  var data = (predLastRow >= 2 && predLastCol >= 1)
    ? predSheet.getRange(2, 1, predLastRow - 1, predLastCol).getValues()
    : [];

  var deduped = _dedupeOutcomeLedgerPredictionRows_(data, predIdx);
  var ledgerBuiltTs = new Date().toISOString();
  var rowsOut = [];
  for (var r = 0; r < deduped.length; r++) {
    var row = _buildOutcomeLedgerRow_(deduped[r], predIdx, ledgerBuiltTs);
    if (row) rowsOut.push(row);
  }

  _sortOutcomeLedgerRows_(ledgerHeaders, rowsOut);
  var actualLedgerHeaders = ensureOutcomeLedgerHeaders_(ledgerSheet);
  var remappedRows = _remapRowsToHeaders_(ledgerHeaders, actualLedgerHeaders, rowsOut);
  _rewriteSheetRowsPreservingHeaders_(ledgerSheet, actualLedgerHeaders, remappedRows);

  return {
    outcome_ledger_sheet: ledgerSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildOutcomeLedgerSheet_() {
  return buildOutcomeLedger_();
}

function buildOutcomeLedgerSheet() {
  return buildOutcomeLedgerSheet_();
}

function getOrCreateOutcomeSummaryProviderFamilySheet_() {
  return _getOrCreateSheet_('Outcome_Summary_ProviderFamily');
}

function getOrCreateOutcomeSummaryConvergenceSheet_() {
  return _getOrCreateSheet_('Outcome_Summary_Convergence');
}

function getOrCreateOutcomeSummaryBucketSheet_() {
  return _getOrCreateSheet_('Outcome_Summary_Bucket');
}

function getOrCreateOutcomeDiagnosticsSheet_() {
  return _getOrCreateSheet_('Outcome_Diagnostics');
}

function ensureOutcomeSummaryHeaders_(sheet, headers) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, headers || []);
}

function ensureOutcomeDiagnosticsHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _outcomeDiagnosticsHeaders_());
}

function buildOutcomeSummaries_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerHeaderMap = _headerIndexMap_(ledgerHeaders);
  var ledgerLastRow = ledgerSheet.getLastRow();
  var ledgerLastCol = ledgerSheet.getLastColumn();
  var ledgerRows = (ledgerLastRow >= 2 && ledgerLastCol >= 1)
    ? ledgerSheet.getRange(2, 1, ledgerLastRow - 1, ledgerLastCol).getValues()
    : [];

  var providerFamilySheet = getOrCreateOutcomeSummaryProviderFamilySheet_();
  var convergenceSheet = getOrCreateOutcomeSummaryConvergenceSheet_();
  var bucketSheet = getOrCreateOutcomeSummaryBucketSheet_();

  var providerFamilyHeaders = _outcomeSummaryProviderFamilyHeaders_();
  var convergenceHeaders = _outcomeSummaryConvergenceHeaders_();
  var bucketHeaders = _outcomeSummaryBucketHeaders_();

  var providerFamilyRows = buildOutcomeSummaryProviderFamily_(ledgerRows, ledgerHeaderMap);
  var convergenceRows = buildOutcomeSummaryConvergence_(ledgerRows, ledgerHeaderMap);
  var bucketRows = buildOutcomeSummaryBucket_(ledgerRows, ledgerHeaderMap);

  _sortOutcomeSummaryProviderFamilyRows_(providerFamilyHeaders, providerFamilyRows);
  _sortOutcomeSummaryConvergenceRows_(convergenceHeaders, convergenceRows);
  _sortOutcomeSummaryBucketRows_(bucketHeaders, bucketRows);

  var actualProviderFamilyHeaders = ensureOutcomeSummaryHeaders_(providerFamilySheet, providerFamilyHeaders);
  var actualConvergenceHeaders = ensureOutcomeSummaryHeaders_(convergenceSheet, convergenceHeaders);
  var actualBucketHeaders = ensureOutcomeSummaryHeaders_(bucketSheet, bucketHeaders);

  _rewriteSheetRowsPreservingHeaders_(
    providerFamilySheet,
    actualProviderFamilyHeaders,
    _remapRowsToHeaders_(providerFamilyHeaders, actualProviderFamilyHeaders, providerFamilyRows)
  );
  _rewriteSheetRowsPreservingHeaders_(
    convergenceSheet,
    actualConvergenceHeaders,
    _remapRowsToHeaders_(convergenceHeaders, actualConvergenceHeaders, convergenceRows)
  );
  _rewriteSheetRowsPreservingHeaders_(
    bucketSheet,
    actualBucketHeaders,
    _remapRowsToHeaders_(bucketHeaders, actualBucketHeaders, bucketRows)
  );

  return {
    provider_family_sheet: providerFamilySheet.getName(),
    convergence_sheet: convergenceSheet.getName(),
    bucket_sheet: bucketSheet.getName(),
    provider_family_rows_written: providerFamilyRows.length,
    convergence_rows_written: convergenceRows.length,
    bucket_rows_written: bucketRows.length
  };
}

function buildOutcomeDiagnostics_() {
  var providerFamilySheet = getOrCreateOutcomeSummaryProviderFamilySheet_();
  var convergenceSheet = getOrCreateOutcomeSummaryConvergenceSheet_();
  var bucketSheet = getOrCreateOutcomeSummaryBucketSheet_();
  var diagnosticsSheet = getOrCreateOutcomeDiagnosticsSheet_();

  var providerFamilyHeaders = getHeaderNames(providerFamilySheet);
  var convergenceHeaders = getHeaderNames(convergenceSheet);
  var bucketHeaders = getHeaderNames(bucketSheet);

  if (!providerFamilyHeaders || !providerFamilyHeaders.length) {
    throw new Error('Outcome_Summary_ProviderFamily sheet is missing headers.');
  }
  if (!convergenceHeaders || !convergenceHeaders.length) {
    throw new Error('Outcome_Summary_Convergence sheet is missing headers.');
  }
  if (!bucketHeaders || !bucketHeaders.length) {
    throw new Error('Outcome_Summary_Bucket sheet is missing headers.');
  }

  var providerFamilyRows = _readDataRows_(providerFamilySheet);
  var convergenceRows = _readDataRows_(convergenceSheet);
  var bucketRows = _readDataRows_(bucketSheet);
  var providerFamilyIdx = _headerIndexMap_(providerFamilyHeaders);
  var convergenceIdx = _headerIndexMap_(convergenceHeaders);
  var bucketIdx = _headerIndexMap_(bucketHeaders);
  var generatedTs = new Date().toISOString();

  var rowsOut = [];
  rowsOut = rowsOut.concat(buildProviderFamilyDiagnostics_(providerFamilyRows, providerFamilyIdx, generatedTs));
  rowsOut = rowsOut.concat(buildConvergenceDiagnostics_(convergenceRows, convergenceIdx, generatedTs));
  rowsOut = rowsOut.concat(buildFailurePatternDiagnostics_(bucketRows, bucketIdx, generatedTs));
  rowsOut = rowsOut.concat(buildUnscoredDataQualityDiagnostics_(providerFamilyRows, providerFamilyIdx, bucketRows, bucketIdx, generatedTs));
  rowsOut = rowsOut.concat(buildAttentionFactorReadinessDiagnostic_(providerFamilyRows, providerFamilyIdx, convergenceRows, convergenceIdx, bucketRows, bucketIdx, generatedTs));

  var headers = _outcomeDiagnosticsHeaders_();
  _sortOutcomeDiagnosticsRows_(headers, rowsOut);
  var actualHeaders = ensureOutcomeDiagnosticsHeaders_(diagnosticsSheet);
  _rewriteSheetRowsPreservingHeaders_(
    diagnosticsSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    diagnostics_sheet: diagnosticsSheet.getName(),
    rows_written: rowsOut.length
  };
}

function _outcomeDiagnosticsHeaders_() {
  return [
    'generated_ts',
    'diagnostic_type',
    'scope',
    'scope_key',
    'outcome_family',
    'ai_name',
    'metric_name',
    'metric_value',
    'metric_detail',
    'diagnostic_level',
    'diagnostic_summary',
    'recommended_next_step',
    'decision_support_note'
  ];
}

function buildProviderFamilyDiagnostics_(providerFamilyRows, providerFamilyIdx, generatedTs) {
  var rowsOut = [];
  var byFamily = {};
  for (var i = 0; i < (providerFamilyRows || []).length; i++) {
    var row = providerFamilyRows[i];
    var family = String(_predValue_(row, providerFamilyIdx, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, providerFamilyIdx, 'ai_name') || '').trim();
    var rowsScored = _numOrNull_(_predValue_(row, providerFamilyIdx, 'rows_scored')) || 0;
    var overallHitRate = _numOrNull_(_predValue_(row, providerFamilyIdx, 'overall_hit_rate'));
    var avgOutcomeScore = _numOrNull_(_predValue_(row, providerFamilyIdx, 'avg_outcome_score'));

    if (!byFamily[family]) byFamily[family] = [];
    byFamily[family].push({
      row: row,
      family: family,
      ai_name: aiName,
      rows_scored: rowsScored,
      overall_hit_rate: overallHitRate,
      avg_outcome_score: avgOutcomeScore
    });

    if (rowsScored >= 5 && ((overallHitRate != null && overallHitRate <= 0.25) || (avgOutcomeScore != null && avgOutcomeScore <= 1.25))) {
      rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
        diagnostic_type: 'provider_family_weakness',
        scope: 'provider_family',
        scope_key: family + '|' + aiName,
        outcome_family: family,
        ai_name: aiName,
        metric_name: overallHitRate != null ? 'overall_hit_rate' : 'avg_outcome_score',
        metric_value: overallHitRate != null ? overallHitRate : avgOutcomeScore,
        metric_detail: 'rows_scored=' + rowsScored +
          '; overall_hit_rate=' + _fmtDiagMetric_(overallHitRate) +
          '; avg_outcome_score=' + _fmtDiagMetric_(avgOutcomeScore),
        diagnostic_level: (overallHitRate != null && overallHitRate <= 0.15) || (avgOutcomeScore != null && avgOutcomeScore <= 0.75) ? 'high' : 'moderate',
        diagnostic_summary: 'Provider appears weak for this family based on current scored outcomes.',
        recommended_next_step: 'Do not downweight automatically yet; monitor after larger sample.'
      }));
    }
  }

  Object.keys(byFamily).sort().forEach(function(family) {
    var candidates = byFamily[family].slice().sort(function(a, b) {
      var aPrimary = a.overall_hit_rate != null ? a.overall_hit_rate : -1;
      var bPrimary = b.overall_hit_rate != null ? b.overall_hit_rate : -1;
      if (aPrimary !== bPrimary) return bPrimary - aPrimary;
      var aSecondary = a.avg_outcome_score != null ? a.avg_outcome_score : -1;
      var bSecondary = b.avg_outcome_score != null ? b.avg_outcome_score : -1;
      if (aSecondary !== bSecondary) return bSecondary - aSecondary;
      return String(a.ai_name).localeCompare(String(b.ai_name));
    });
    var winner = candidates[0];
    var diagnosticLevel = 'weak';
    var metricName = winner.overall_hit_rate != null ? 'overall_hit_rate' : 'avg_outcome_score';
    var metricValue = winner.overall_hit_rate != null ? winner.overall_hit_rate : winner.avg_outcome_score;
    if (winner.rows_scored < 5) diagnosticLevel = 'low_confidence';
    else if (winner.overall_hit_rate != null && winner.overall_hit_rate >= 0.60) diagnosticLevel = 'strong';
    else if (winner.overall_hit_rate != null && winner.overall_hit_rate >= 0.45) diagnosticLevel = 'moderate';
    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'provider_family_strength',
      scope: 'family',
      scope_key: family,
      outcome_family: family,
      ai_name: winner.ai_name,
      metric_name: metricName,
      metric_value: metricValue,
      metric_detail: 'best_provider=' + winner.ai_name +
        '; rows_scored=' + winner.rows_scored +
        '; overall_hit_rate=' + _fmtDiagMetric_(winner.overall_hit_rate) +
        '; avg_outcome_score=' + _fmtDiagMetric_(winner.avg_outcome_score),
      diagnostic_level: diagnosticLevel,
      diagnostic_summary: 'Best current provider for this family based on Step 2 summary performance.',
      recommended_next_step: winner.rows_scored < 5
        ? 'Collect more scored outcomes before weighting.'
        : 'Use as candidate provider-weighting evidence after more samples.'
    }));
  });

  return rowsOut;
}

function buildConvergenceDiagnostics_(convergenceRows, convergenceIdx, generatedTs) {
  var rowsOut = [];
  var families = {};
  for (var i = 0; i < (convergenceRows || []).length; i++) {
    var row = convergenceRows[i];
    var family = String(_predValue_(row, convergenceIdx, 'outcome_family') || '').trim() || 'other';
    if (!families[family]) {
      families[family] = {
        total: 0,
        high: 0,
        low: 0,
        large_spread: 0
      };
    }
    var g = families[family];
    g.total += 1;
    var level = String(_predValue_(row, convergenceIdx, 'convergence_level') || '').trim().toLowerCase();
    var scoreSpread = _numOrNull_(_predValue_(row, convergenceIdx, 'score_spread'));
    if (level === 'high') g.high += 1;
    if (level === 'low') g.low += 1;
    if (level === 'low' && scoreSpread != null && scoreSpread >= 2) g.large_spread += 1;
  }

  Object.keys(families).sort().forEach(function(family) {
    var g = families[family];
    var highRate = g.total ? g.high / g.total : 0;
    var lowRate = g.total ? g.low / g.total : 0;
    var usefulRate = g.total ? g.large_spread / g.total : 0;
    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'convergence_risk',
      scope: 'family',
      scope_key: family,
      outcome_family: family,
      ai_name: '',
      metric_name: 'high_convergence_rate',
      metric_value: _roundRate_(highRate),
      metric_detail: 'high=' + g.high + '; total=' + g.total + '; high_convergence_rate=' + _fmtDiagMetric_(highRate),
      diagnostic_level: highRate >= 0.70 ? 'high' : (highRate >= 0.40 ? 'moderate' : 'low'),
      diagnostic_summary: 'Providers frequently produce similar direction/strength/pips for this family.',
      recommended_next_step: 'If convergence is high, design Attention Factor Selection carefully to measure natural factor choice without forcing provider roles.'
    }));
    if (g.large_spread > 0) {
      rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
        diagnostic_type: 'useful_disagreement',
        scope: 'family',
        scope_key: family,
        outcome_family: family,
        ai_name: '',
        metric_name: 'useful_disagreement_rate',
        metric_value: _roundRate_(usefulRate),
        metric_detail: 'low_convergence_rows=' + g.low + '; large_score_spread_rows=' + g.large_spread + '; total=' + g.total,
        diagnostic_level: usefulRate >= 0.20 ? 'high' : 'moderate',
        diagnostic_summary: 'Provider disagreement may contain useful information for this family.',
        recommended_next_step: 'Preserve multi-provider diversity; later test ensemble weighting.'
      }));
    }
  });

  return rowsOut;
}

function buildFailurePatternDiagnostics_(bucketRows, bucketIdx, generatedTs) {
  var rowsOut = [];
  for (var i = 0; i < (bucketRows || []).length; i++) {
    var row = bucketRows[i];
    var family = String(_predValue_(row, bucketIdx, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, bucketIdx, 'ai_name') || '').trim();
    var rowType = String(_predValue_(row, bucketIdx, 'type') || '').trim();
    var rowsScored = _numOrNull_(_predValue_(row, bucketIdx, 'rows_scored')) || 0;
    var failureType = String(_predValue_(row, bucketIdx, 'most_common_failure_type') || '').trim();
    if (!failureType || failureType === 'unscored_only' || rowsScored < 1) continue;
    var directionMiss = _numOrNull_(_predValue_(row, bucketIdx, 'direction_miss_count')) || 0;
    var strengthMiss = _numOrNull_(_predValue_(row, bucketIdx, 'strength_miss_count')) || 0;
    var sustainMiss = _numOrNull_(_predValue_(row, bucketIdx, 'sustain_miss_count')) || 0;
    var dominantCount = Math.max(directionMiss, strengthMiss, sustainMiss);
    var dominanceRate = rowsScored ? dominantCount / rowsScored : 0;
    var summary = 'Failures are mostly ' + failureType.replace(/_/g, ' ') + '.';
    var nextStep = 'Continue monitoring failure mix.';
    if (failureType === 'direction_miss') nextStep = 'Improve directional context or no-signal filter.';
    else if (failureType === 'strength_miss') nextStep = 'Improve expected pips/strength calibration.';
    else if (failureType === 'sustain_miss') nextStep = 'Improve sustain modeling and whipsaw memory.';

    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'failure_pattern',
      scope: 'family_provider_type',
      scope_key: family + '|' + aiName + '|' + rowType,
      outcome_family: family,
      ai_name: aiName,
      metric_name: failureType,
      metric_value: dominantCount,
      metric_detail: 'rows_scored=' + rowsScored +
        '; direction_miss_count=' + directionMiss +
        '; strength_miss_count=' + strengthMiss +
        '; sustain_miss_count=' + sustainMiss,
      diagnostic_level: dominanceRate >= 0.50 ? 'high' : 'moderate',
      diagnostic_summary: summary,
      recommended_next_step: nextStep
    }));
  }
  return rowsOut;
}

function buildUnscoredDataQualityDiagnostics_(providerFamilyRows, providerFamilyIdx, bucketRows, bucketIdx, generatedTs) {
  var rowsOut = [];
  var seen = {};
  var highestRate = 0;
  var highestDetail = 'No major unscored data-quality issue detected at current thresholds.';
  for (var i = 0; i < (providerFamilyRows || []).length; i++) {
    var row = providerFamilyRows[i];
    var family = String(_predValue_(row, providerFamilyIdx, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, providerFamilyIdx, 'ai_name') || '').trim();
    var rowsTotal = _numOrNull_(_predValue_(row, providerFamilyIdx, 'rows_total')) || 0;
    if (!rowsTotal) continue;
    var unscoredCount = _numOrNull_(_predValue_(row, providerFamilyIdx, 'unscored_count')) || 0;
    var unscoredRate = unscoredCount / rowsTotal;
    if (unscoredRate > highestRate) {
      highestRate = unscoredRate;
      highestDetail = 'highest_provider_family=' + family + '|' + aiName +
        '; unscored_count=' + unscoredCount +
        '; rows_total=' + rowsTotal +
        '; unscored_rate=' + _fmtDiagMetric_(unscoredRate);
    }
    if (unscoredRate < 0.25) continue;
    var scopeKey = family + '|' + aiName;
    seen[scopeKey] = true;
    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'unscored_data_quality',
      scope: 'provider_family',
      scope_key: scopeKey,
      outcome_family: family,
      ai_name: aiName,
      metric_name: 'unscored_rate',
      metric_value: _roundRate_(unscoredRate),
      metric_detail: 'unscored_count=' + unscoredCount + '; rows_total=' + rowsTotal,
      diagnostic_level: unscoredRate >= 0.50 ? 'high' : (unscoredRate >= 0.25 ? 'moderate' : 'low'),
      diagnostic_summary: 'Large share of rows are unscored, so performance conclusions may be unreliable.',
      recommended_next_step: 'Improve market-reaction scoring coverage or data availability before learning from this family.'
    }));
  }

  for (var j = 0; j < (bucketRows || []).length; j++) {
    var brow = bucketRows[j];
    var bFamily = String(_predValue_(brow, bucketIdx, 'outcome_family') || '').trim() || 'other';
    var bAiName = String(_predValue_(brow, bucketIdx, 'ai_name') || '').trim();
    var bType = String(_predValue_(brow, bucketIdx, 'type') || '').trim();
    var bRowsTotal = _numOrNull_(_predValue_(brow, bucketIdx, 'rows_total')) || 0;
    if (!bRowsTotal) continue;
    var bUnscoredRate = _numOrNull_(_predValue_(brow, bucketIdx, 'unscored_rate'));
    if (bUnscoredRate == null) {
      var bUnscoredCount = _numOrNull_(_predValue_(brow, bucketIdx, 'unscored_count')) || 0;
      bUnscoredRate = bUnscoredCount / bRowsTotal;
    }
    if (bUnscoredRate > highestRate) {
      highestRate = bUnscoredRate;
      highestDetail = 'highest_family_provider_type=' + bFamily + '|' + bAiName + '|' + bType +
        '; rows_total=' + bRowsTotal +
        '; unscored_rate=' + _fmtDiagMetric_(bUnscoredRate);
    }
    if (bUnscoredRate < 0.50) continue;
    var bScopeKey = bFamily + '|' + bAiName + '|' + bType;
    if (seen[bScopeKey]) continue;
    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'unscored_data_quality',
      scope: 'family_provider_type',
      scope_key: bScopeKey,
      outcome_family: bFamily,
      ai_name: bAiName,
      metric_name: 'unscored_rate',
      metric_value: _roundRate_(bUnscoredRate),
      metric_detail: 'type=' + bType + '; rows_total=' + bRowsTotal + '; unscored_rate=' + _fmtDiagMetric_(bUnscoredRate),
      diagnostic_level: bUnscoredRate >= 0.50 ? 'high' : 'moderate',
      diagnostic_summary: 'Large share of rows are unscored, so performance conclusions may be unreliable.',
      recommended_next_step: 'Improve market-reaction scoring coverage or data availability before learning from this family.'
    }));
  }

  if (!rowsOut.length) {
    rowsOut.push(_makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'unscored_data_quality',
      scope: 'global',
      scope_key: 'all',
      outcome_family: '',
      ai_name: '',
      metric_name: 'max_unscored_rate',
      metric_value: _roundRate_(highestRate),
      metric_detail: highestDetail,
      diagnostic_level: highestRate >= 0.50 ? 'high' : (highestRate >= 0.25 ? 'moderate' : 'low'),
      diagnostic_summary: highestRate >= 0.25
        ? 'Some unscored data-quality risk exists, but it does not dominate enough slices to trigger targeted flags at current thresholds.'
        : 'No major unscored data-quality issue detected at current thresholds.',
      recommended_next_step: 'Continue monitoring market-reaction scoring coverage before learning too aggressively from sparse families.'
    }));
  }

  return rowsOut;
}

function buildAttentionFactorReadinessDiagnostic_(providerFamilyRows, providerFamilyIdx, convergenceRows, convergenceIdx, bucketRows, bucketIdx, generatedTs) {
  var totalScored = 0;
  var familyScoredRows = {};
  var severeUnscoredFamilies = {};
  var familyTotals = {};
  for (var i = 0; i < (providerFamilyRows || []).length; i++) {
    var row = providerFamilyRows[i];
    var family = String(_predValue_(row, providerFamilyIdx, 'outcome_family') || '').trim() || 'other';
    var rowsScored = _numOrNull_(_predValue_(row, providerFamilyIdx, 'rows_scored')) || 0;
    var rowsTotal = _numOrNull_(_predValue_(row, providerFamilyIdx, 'rows_total')) || 0;
    var unscoredCount = _numOrNull_(_predValue_(row, providerFamilyIdx, 'unscored_count')) || 0;
    totalScored += rowsScored;
    familyScoredRows[family] = (familyScoredRows[family] || 0) + rowsScored;
    familyTotals[family] = (familyTotals[family] || 0) + rowsTotal;
    severeUnscoredFamilies[family] = severeUnscoredFamilies[family] || { total: 0, unscored: 0 };
    severeUnscoredFamilies[family].total += rowsTotal;
    severeUnscoredFamilies[family].unscored += unscoredCount;
  }

  var convergenceMeasured = (convergenceRows || []).length > 0;
  var familyNames = Object.keys(familyTotals);
  var severeFamilies = 0;
  for (var j = 0; j < familyNames.length; j++) {
    var family = familyNames[j];
    var stats = severeUnscoredFamilies[family];
    var rate = stats.total ? stats.unscored / stats.total : 0;
    if (rate >= 0.50) severeFamilies += 1;
  }

  var ledgerExists = familyNames.length > 0;
  var summariesExist = (providerFamilyRows || []).length > 0 && (convergenceRows || []).length > 0 && (bucketRows || []).length > 0;
  var enoughScoredRows = totalScored >= 500;
  var severeDominatesAllFamilies = familyNames.length > 0 && severeFamilies === familyNames.length;
  var readinessLevel = 'not_ready';
  if (ledgerExists && summariesExist && enoughScoredRows && convergenceMeasured && !severeDominatesAllFamilies) readinessLevel = 'ready';
  else if (ledgerExists && summariesExist && convergenceMeasured && totalScored >= 150 && severeFamilies < familyNames.length) readinessLevel = 'partial';

  var summary = 'Attention Factor Selection v1 is not ready yet based on current diagnostic coverage.';
  if (readinessLevel === 'ready') summary = 'Attention Factor Selection v1 is ready for implementation with current diagnostic coverage.';
  else if (readinessLevel === 'partial') summary = 'Attention Factor Selection v1 is partially supported, but some data-quality or sample-depth gaps remain.';

  return [
    _makeOutcomeDiagnosticRow_(generatedTs, {
      diagnostic_type: 'attention_factor_readiness',
      scope: 'global',
      scope_key: 'all',
      outcome_family: '',
      ai_name: '',
      metric_name: 'readiness_scorecard',
      metric_value: readinessLevel,
      metric_detail: 'ledger_exists=' + (ledgerExists ? 'TRUE' : 'FALSE') +
        '; summaries_exist=' + (summariesExist ? 'TRUE' : 'FALSE') +
        '; total_scored=' + totalScored +
        '; convergence_rows=' + (convergenceRows || []).length +
        '; severe_unscored_families=' + severeFamilies + '/' + familyNames.length,
      diagnostic_level: readinessLevel,
      diagnostic_summary: summary,
      recommended_next_step: readinessLevel === 'not_ready'
        ? 'Collect more scored outcomes and improve unscored coverage before changing prediction prompts.'
        : 'Implement Attention Factor Selection v1 with equal task framing across providers and no provider-specific roles.'
    })
  ];
}

function _makeOutcomeDiagnosticRow_(generatedTs, attrs) {
  attrs = attrs || {};
  return [
    generatedTs,
    attrs.diagnostic_type || '',
    attrs.scope || '',
    attrs.scope_key || '',
    attrs.outcome_family || '',
    attrs.ai_name || '',
    attrs.metric_name || '',
    attrs.metric_value === undefined ? '' : attrs.metric_value,
    attrs.metric_detail || '',
    attrs.diagnostic_level || '',
    attrs.diagnostic_summary || '',
    attrs.recommended_next_step || '',
    'Diagnostic analysis only; not trading advice.'
  ];
}

function _readDataRows_(sheet) {
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  return (lastRow >= 2 && lastCol >= 1)
    ? sheet.getRange(2, 1, lastRow - 1, lastCol).getValues()
    : [];
}

function _fmtDiagMetric_(value) {
  if (value === '' || value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (!isFinite(value)) return '';
  return String(_roundRate_(value));
}

function _outcomeSummaryProviderFamilyHeaders_() {
  return [
    'generated_ts',
    'outcome_family',
    'ai_name',
    'rows_total',
    'rows_scored',
    'full_hit_count',
    'partial_hit_count',
    'weak_fit_count',
    'miss_count',
    'unscored_count',
    'avg_outcome_score',
    'dir_hit_count',
    'dir_hit_rate',
    'strength_hit_count',
    'strength_hit_rate',
    'sustain_hit_count',
    'sustain_hit_rate',
    'overall_hit_count',
    'overall_hit_rate',
    'decision_support_note'
  ];
}

function _outcomeSummaryConvergenceHeaders_() {
  return [
    'generated_ts',
    'group_key',
    'event_id',
    'batch_id',
    'release_ts',
    'release_date',
    'outcome_family',
    'indicator_name',
    'type',
    'provider_count',
    'provider_names',
    'unique_pred_dirs',
    'dir_converged_flag',
    'avg_pred_net_pips',
    'pred_pips_min',
    'pred_pips_max',
    'pred_pips_spread',
    'unique_pred_strengths',
    'strength_converged_flag',
    'outcome_buckets',
    'best_outcome_score',
    'worst_outcome_score',
    'score_spread',
    'convergence_level',
    'decision_support_note'
  ];
}

function _outcomeSummaryBucketHeaders_() {
  return [
    'generated_ts',
    'outcome_family',
    'ai_name',
    'type',
    'rows_total',
    'rows_scored',
    'full_hit_count',
    'full_hit_rate',
    'partial_hit_count',
    'partial_hit_rate',
    'weak_fit_count',
    'weak_fit_rate',
    'miss_count',
    'miss_rate',
    'unscored_count',
    'unscored_rate',
    'direction_miss_count',
    'strength_miss_count',
    'sustain_miss_count',
    'most_common_failure_type',
    'decision_support_note'
  ];
}

function buildOutcomeSummaryProviderFamily_(ledgerRows, ledgerHeaderMap) {
  var generatedTs = new Date().toISOString();
  var groups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    var family = String(_predValue_(row, ledgerHeaderMap, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, ledgerHeaderMap, 'ai_name') || '').trim() || '';
    var key = family + '|' + aiName;
    if (!groups[key]) {
      groups[key] = {
        outcome_family: family,
        ai_name: aiName,
        rows_total: 0,
        rows_scored: 0,
        full_hit_count: 0,
        partial_hit_count: 0,
        weak_fit_count: 0,
        miss_count: 0,
        unscored_count: 0,
        outcome_score_sum: 0,
        outcome_score_count: 0,
        dir_hit_count: 0,
        strength_hit_count: 0,
        sustain_hit_count: 0,
        overall_hit_count: 0
      };
    }
    var g = groups[key];
    var bucket = String(_predValue_(row, ledgerHeaderMap, 'outcome_bucket') || '').trim();
    var scored = _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'scored_flag'));
    g.rows_total += 1;
    if (scored) g.rows_scored += 1;
    if (bucket === 'full_hit') g.full_hit_count += 1;
    else if (bucket === 'partial_hit') g.partial_hit_count += 1;
    else if (bucket === 'weak_fit') g.weak_fit_count += 1;
    else if (bucket === 'miss') g.miss_count += 1;
    if (bucket === 'unscored' || !scored) g.unscored_count += 1;

    var score = _numOrNull_(_predValue_(row, ledgerHeaderMap, 'outcome_score'));
    if (scored && score != null) {
      g.outcome_score_sum += score;
      g.outcome_score_count += 1;
    }
    if (scored && _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_dir_ok'))) g.dir_hit_count += 1;
    if (scored && _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_strength_ok'))) g.strength_hit_count += 1;
    if (scored && _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_sustain_ok'))) g.sustain_hit_count += 1;
    if (scored && _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'overall_ok'))) g.overall_hit_count += 1;
  }

  var rowsOut = [];
  Object.keys(groups).forEach(function(key) {
    var g = groups[key];
    rowsOut.push([
      generatedTs,
      g.outcome_family,
      g.ai_name,
      g.rows_total,
      g.rows_scored,
      g.full_hit_count,
      g.partial_hit_count,
      g.weak_fit_count,
      g.miss_count,
      g.unscored_count,
      g.outcome_score_count ? _roundRate_(g.outcome_score_sum / g.outcome_score_count) : '',
      g.dir_hit_count,
      _rateOrBlank_(g.dir_hit_count, g.rows_scored),
      g.strength_hit_count,
      _rateOrBlank_(g.strength_hit_count, g.rows_scored),
      g.sustain_hit_count,
      _rateOrBlank_(g.sustain_hit_count, g.rows_scored),
      g.overall_hit_count,
      _rateOrBlank_(g.overall_hit_count, g.rows_scored),
      'Derived performance summary only; not trading advice.'
    ]);
  });
  return rowsOut;
}

function buildOutcomeSummaryConvergence_(ledgerRows, ledgerHeaderMap) {
  var generatedTs = new Date().toISOString();
  var groups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    var rowType = String(_predValue_(row, ledgerHeaderMap, 'type') || '').trim().toLowerCase();
    var eventId = String(_predValue_(row, ledgerHeaderMap, 'event_id') || '').trim();
    var batchId = String(_predValue_(row, ledgerHeaderMap, 'batch_id') || '').trim();
    var groupKey = '';
    if (rowType === 'batch' && batchId) groupKey = batchId;
    else if (eventId) groupKey = eventId;
    else if (batchId) groupKey = batchId;
    if (!groupKey) continue;

    if (!groups[groupKey]) {
      groups[groupKey] = {
        group_key: groupKey,
        event_id: eventId,
        batch_id: batchId,
        release_ts: String(_predValue_(row, ledgerHeaderMap, 'release_ts') || '').trim(),
        release_date: String(_predValue_(row, ledgerHeaderMap, 'release_date') || '').trim(),
        outcome_family: String(_predValue_(row, ledgerHeaderMap, 'outcome_family') || '').trim(),
        indicator_name: String(_predValue_(row, ledgerHeaderMap, 'indicator_name') || '').trim(),
        type: String(_predValue_(row, ledgerHeaderMap, 'type') || '').trim(),
        provider_names: {},
        pred_dirs: {},
        pred_strengths: {},
        outcome_buckets: {},
        pred_pips: [],
        scored_scores: []
      };
    }
    var g = groups[groupKey];
    var aiName = String(_predValue_(row, ledgerHeaderMap, 'ai_name') || '').trim();
    var predDir = String(_predValue_(row, ledgerHeaderMap, 'mr_pred_dir') || '').trim();
    var predStrength = String(_predValue_(row, ledgerHeaderMap, 'mr_pred_strength') || '').trim();
    var bucket = String(_predValue_(row, ledgerHeaderMap, 'outcome_bucket') || '').trim();
    var predPips = _numOrNull_(_predValue_(row, ledgerHeaderMap, 'mr_pred_net_pips'));
    var outcomeScore = _numOrNull_(_predValue_(row, ledgerHeaderMap, 'outcome_score'));
    var scored = _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'scored_flag'));

    if (aiName) g.provider_names[aiName] = true;
    if (predDir) g.pred_dirs[predDir] = true;
    if (predStrength) g.pred_strengths[predStrength] = true;
    if (bucket) g.outcome_buckets[bucket] = true;
    if (predPips != null) g.pred_pips.push(predPips);
    if (scored && outcomeScore != null) g.scored_scores.push(outcomeScore);
  }

  var rowsOut = [];
  Object.keys(groups).forEach(function(key) {
    var g = groups[key];
    var providerNames = Object.keys(g.provider_names).sort();
    var predDirs = Object.keys(g.pred_dirs).sort();
    var predStrengths = Object.keys(g.pred_strengths).sort();
    var buckets = Object.keys(g.outcome_buckets).sort();
    var providerCount = providerNames.length;
    var uniquePredDirs = predDirs.length;
    var uniquePredStrengths = predStrengths.length;
    var dirConverged = providerCount >= 2 && uniquePredDirs === 1;
    var strengthConverged = providerCount >= 2 && uniquePredStrengths === 1;
    var predMin = '';
    var predMax = '';
    var predAvg = '';
    var predSpread = '';
    if (g.pred_pips.length) {
      predMin = Math.min.apply(null, g.pred_pips);
      predMax = Math.max.apply(null, g.pred_pips);
      predAvg = _roundRate_(_sumNumbers_(g.pred_pips) / g.pred_pips.length);
      predSpread = _roundRate_(predMax - predMin);
    }
    var bestScore = '';
    var worstScore = '';
    var scoreSpread = '';
    if (g.scored_scores.length) {
      bestScore = Math.max.apply(null, g.scored_scores);
      worstScore = Math.min.apply(null, g.scored_scores);
      scoreSpread = bestScore - worstScore;
    }
    var convergenceLevel = 'unknown';
    if (providerCount < 2) convergenceLevel = 'insufficient_providers';
    else if (uniquePredDirs > 1) convergenceLevel = 'low';
    else if (dirConverged && strengthConverged && predSpread !== '' && predSpread <= 3) convergenceLevel = 'high';
    else if (dirConverged) convergenceLevel = 'medium';

    rowsOut.push([
      generatedTs,
      g.group_key,
      g.event_id,
      g.batch_id,
      g.release_ts,
      g.release_date,
      g.outcome_family,
      g.indicator_name,
      g.type,
      providerCount,
      providerNames.join(', '),
      uniquePredDirs,
      dirConverged ? 'TRUE' : 'FALSE',
      predAvg,
      predMin,
      predMax,
      predSpread,
      uniquePredStrengths,
      strengthConverged ? 'TRUE' : 'FALSE',
      buckets.join(', '),
      bestScore,
      worstScore,
      scoreSpread,
      convergenceLevel,
      'Provider convergence audit only; not trading advice.'
    ]);
  });
  return rowsOut;
}

function buildOutcomeSummaryBucket_(ledgerRows, ledgerHeaderMap) {
  var generatedTs = new Date().toISOString();
  var groups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    var family = String(_predValue_(row, ledgerHeaderMap, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, ledgerHeaderMap, 'ai_name') || '').trim();
    var rowType = String(_predValue_(row, ledgerHeaderMap, 'type') || '').trim();
    var key = family + '|' + aiName + '|' + rowType;
    if (!groups[key]) {
      groups[key] = {
        outcome_family: family,
        ai_name: aiName,
        type: rowType,
        rows_total: 0,
        rows_scored: 0,
        full_hit_count: 0,
        partial_hit_count: 0,
        weak_fit_count: 0,
        miss_count: 0,
        unscored_count: 0,
        direction_miss_count: 0,
        strength_miss_count: 0,
        sustain_miss_count: 0
      };
    }
    var g = groups[key];
    var bucket = String(_predValue_(row, ledgerHeaderMap, 'outcome_bucket') || '').trim();
    var scored = _isTrueCell_(_predValue_(row, ledgerHeaderMap, 'scored_flag'));
    g.rows_total += 1;
    if (scored) g.rows_scored += 1;
    if (bucket === 'full_hit') g.full_hit_count += 1;
    else if (bucket === 'partial_hit') g.partial_hit_count += 1;
    else if (bucket === 'weak_fit') g.weak_fit_count += 1;
    else if (bucket === 'miss') g.miss_count += 1;
    if (bucket === 'unscored' || !scored) g.unscored_count += 1;
    if (scored && !_isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_dir_ok'))) g.direction_miss_count += 1;
    if (scored && !_isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_strength_ok'))) g.strength_miss_count += 1;
    if (scored && !_isTrueCell_(_predValue_(row, ledgerHeaderMap, 'mr_sustain_ok'))) g.sustain_miss_count += 1;
  }

  var rowsOut = [];
  Object.keys(groups).forEach(function(key) {
    var g = groups[key];
    rowsOut.push([
      generatedTs,
      g.outcome_family,
      g.ai_name,
      g.type,
      g.rows_total,
      g.rows_scored,
      g.full_hit_count,
      _rateOrBlank_(g.full_hit_count, g.rows_total),
      g.partial_hit_count,
      _rateOrBlank_(g.partial_hit_count, g.rows_total),
      g.weak_fit_count,
      _rateOrBlank_(g.weak_fit_count, g.rows_total),
      g.miss_count,
      _rateOrBlank_(g.miss_count, g.rows_total),
      g.unscored_count,
      _rateOrBlank_(g.unscored_count, g.rows_total),
      g.direction_miss_count,
      g.strength_miss_count,
      g.sustain_miss_count,
      _mostCommonFailureType_(g),
      'Failure-pattern summary only; not trading advice.'
    ]);
  });
  return rowsOut;
}

function _outcomeLedgerHeaders_() {
  return [
    'created_ts',
    'ledger_built_ts',
    'event_id',
    'batch_id',
    'type',
    'prediction_id',
    'run_id',
    'release_date',
    'release_ts',
    'indicator_name',
    'country',
    'genre',
    'importance',
    'ai_name',
    'ai_model',
    'status',
    'qualitative_result',
    'mr_pred_dir',
    'mr_pred_net_pips',
    'mr_pred_strength',
    'mr_pred_sustain_min',
    'mr_real_dir',
    'mr_real_strength',
    'mr_real_sustain_min',
    'realized_pips',
    'mr_dir_ok',
    'mr_strength_ok',
    'mr_sustain_ok',
    'overall_ok',
    'outcome_family',
    'outcome_score',
    'outcome_bucket',
    'scored_flag',
    'prediction_bias',
    'confidence',
    'pre_signal_mode',
    'pre_risk_level',
    'pre_volatility_level',
    'batch_anchor_mode',
    'batch_anchor_confidence',
    'no_trade_advice_flag'
  ];
}

function _ensureOutcomeLedgerHeadersAppendOnly_(sheet, requiredHeaders) {
  var lastCol = sheet.getLastColumn();
  if (lastCol < 1) {
    sheet.getRange(1, 1, 1, requiredHeaders.length).setValues([requiredHeaders]);
    sheet.setFrozenRows(1);
    return requiredHeaders.slice();
  }

  var existing = sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(function(h){
    return String(h || '').trim();
  });
  var seen = {};
  existing.forEach(function(h){ if (h) seen[h] = true; });

  var missing = [];
  (requiredHeaders || []).forEach(function(h){
    if (!seen[h]) {
      seen[h] = true;
      missing.push(h);
    }
  });

  if (missing.length) {
    sheet.getRange(1, existing.length + 1, 1, missing.length).setValues([missing]);
    existing = existing.concat(missing);
  }

  sheet.setFrozenRows(1);
  return existing;
}

function _remapRowsToHeaders_(sourceHeaders, targetHeaders, rows) {
  var sourceIdx = _headerIndexMap_(sourceHeaders);
  return (rows || []).map(function(row){
    return targetHeaders.map(function(header){
      var idx = sourceIdx[header];
      return idx === undefined ? '' : row[idx];
    });
  });
}

function _buildOutcomeLedgerRow_(src, idx, ledgerBuiltTs) {
  var eventId = String(_predValue_(src, idx, 'event_id') || '').trim();
  var aiName = String(_predValue_(src, idx, 'ai_name') || '').trim();
  if (!eventId || !aiName) return null;

  var releaseTs = String(_predValue_(src, idx, 'release_ts') || '');
  var predictionId = String(_predValue_(src, idx, 'prediction_id') || '').trim();
  var indicatorName = String(_predValue_(src, idx, 'indicator_name') || '');
  var genre = String(_predValue_(src, idx, 'genre') || '');
  var scored = _outcomeLedgerRowIsScored_(src, idx);
  var rowObject = {
    scored_flag: scored ? 'TRUE' : 'FALSE',
    mr_real_dir: _predValue_(src, idx, 'mr_real_dir'),
    realized_pips: _predValue_(src, idx, 'realized_pips'),
    mr_dir_ok: _predValue_(src, idx, 'mr_dir_ok'),
    dir_ok: _predValue_(src, idx, 'dir_ok'),
    mr_strength_ok: _predValue_(src, idx, 'mr_strength_ok'),
    mr_sustain_ok: _predValue_(src, idx, 'mr_sustain_ok'),
    overall_ok: _predValue_(src, idx, 'overall_ok')
  };
  var dirOk = _isTrueCell_(rowObject.mr_dir_ok) || _isTrueCell_(rowObject.dir_ok);
  var strengthOk = _isTrueCell_(rowObject.mr_strength_ok);
  var sustainOk = _isTrueCell_(rowObject.mr_sustain_ok);
  var overallOk = _isTrueCell_(rowObject.overall_ok);
  var score = computeOutcomeScore_(rowObject);
  var confidence = _predValue_(src, idx, 'batch_anchor_confidence');
  if (confidence === '' || confidence === null || confidence === undefined) {
    confidence = _predValue_(src, idx, 'scenario_confidence');
  }

  return [
    _predValue_(src, idx, 'created_ts'),
    ledgerBuiltTs,
    eventId,
    _predValue_(src, idx, 'batch_id'),
    _predValue_(src, idx, 'type'),
    predictionId,
    _predValue_(src, idx, 'run_id'),
    _deriveReleaseDate_(releaseTs),
    releaseTs,
    indicatorName,
    _predValue_(src, idx, 'country'),
    genre,
    _predValue_(src, idx, 'importance'),
    aiName,
    _predValue_(src, idx, 'ai_model'),
    _predValue_(src, idx, 'status'),
    _predValue_(src, idx, 'qualitative_result'),
    _predValue_(src, idx, 'mr_pred_dir'),
    _predValue_(src, idx, 'mr_pred_net_pips'),
    _predValue_(src, idx, 'mr_pred_strength'),
    _predValue_(src, idx, 'mr_pred_sustain_min'),
    _predValue_(src, idx, 'mr_real_dir'),
    _predValue_(src, idx, 'mr_real_strength'),
    _predValue_(src, idx, 'mr_real_sustain_min'),
    _predValue_(src, idx, 'realized_pips'),
    dirOk ? 'TRUE' : 'FALSE',
    strengthOk ? 'TRUE' : 'FALSE',
    sustainOk ? 'TRUE' : 'FALSE',
    overallOk ? 'TRUE' : 'FALSE',
    deriveOutcomeFamily_(indicatorName, genre),
    score,
    computeOutcomeBucket_(score, overallOk, scored),
    scored ? 'TRUE' : 'FALSE',
    _outcomeLedgerPredictionBias_(_predValue_(src, idx, 'mr_pred_dir')),
    confidence,
    _predValue_(src, idx, 'pre_signal_mode'),
    _predValue_(src, idx, 'pre_risk_level'),
    _predValue_(src, idx, 'pre_volatility_level'),
    _predValue_(src, idx, 'batch_anchor_mode'),
    _predValue_(src, idx, 'batch_anchor_confidence'),
    'TRUE'
  ];
}

function _dedupeOutcomeLedgerPredictionRows_(rows, predIdx) {
  if (!rows || !rows.length) return [];

  var latestByKey = {};
  var order = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var eventId = String(_predValue_(row, predIdx, 'event_id') || '').trim();
    var aiName = String(_predValue_(row, predIdx, 'ai_name') || '').trim();
    if (!eventId || !aiName) continue;
    var predictionId = String(_predValue_(row, predIdx, 'prediction_id') || '').trim();
    var key = predictionId || (eventId + '|' + aiName);
    if (!latestByKey.hasOwnProperty(key)) {
      latestByKey[key] = row;
      order.push(key);
      continue;
    }
    if (_outcomeLedgerPredictionRowIsNewer_(row, latestByKey[key], predIdx)) latestByKey[key] = row;
  }

  var out = [];
  for (var j = 0; j < order.length; j++) out.push(latestByKey[order[j]]);
  return out;
}

function _outcomeLedgerPredictionRowIsNewer_(candidate, existing, predIdx) {
  var candidateCreatedMs = _evaluationDateMs_(_predValue_(candidate, predIdx, 'created_ts'));
  var existingCreatedMs = _evaluationDateMs_(_predValue_(existing, predIdx, 'created_ts'));
  if (candidateCreatedMs !== existingCreatedMs) return candidateCreatedMs > existingCreatedMs;

  var candidateEvalMs = _evaluationDateMs_(_predValue_(candidate, predIdx, 'eval_ts'));
  var existingEvalMs = _evaluationDateMs_(_predValue_(existing, predIdx, 'eval_ts'));
  if (candidateEvalMs !== existingEvalMs) return candidateEvalMs > existingEvalMs;

  return true;
}

function _outcomeLedgerRowIsScored_(row, idx) {
  var realDir = String(_predValue_(row, idx, 'mr_real_dir') || '').trim().toLowerCase();
  if (realDir === 'up' || realDir === 'down' || realDir === 'flat') return true;
  var realizedPips = _predValue_(row, idx, 'realized_pips');
  if (realizedPips !== '' && realizedPips !== null && realizedPips !== undefined) {
    var n = Number(realizedPips);
    if (isFinite(n)) return true;
  }
  return false;
}

function computeOutcomeScore_(rowObject) {
  rowObject = rowObject || {};
  var scored = _outcomeLedgerComputedScoredFlag_(rowObject);
  var dirOk = _isTrueCell_(rowObject.mr_dir_ok) || _isTrueCell_(rowObject.dir_ok);
  var strengthOk = _isTrueCell_(rowObject.mr_strength_ok);
  var sustainOk = _isTrueCell_(rowObject.mr_sustain_ok);
  var overallOk = _isTrueCell_(rowObject.overall_ok);
  if (!scored) return '';
  var score = 0;
  if (dirOk) score += 2;
  if (strengthOk) score += 1;
  if (sustainOk) score += 1;
  if (overallOk) score += 2;
  return score;
}

function _outcomeLedgerScore_(scored, dirOk, strengthOk, sustainOk, overallOk) {
  return computeOutcomeScore_({
    scored_flag: scored ? 'TRUE' : 'FALSE',
    mr_dir_ok: dirOk ? 'TRUE' : 'FALSE',
    mr_strength_ok: strengthOk ? 'TRUE' : 'FALSE',
    mr_sustain_ok: sustainOk ? 'TRUE' : 'FALSE',
    overall_ok: overallOk ? 'TRUE' : 'FALSE'
  });
}

function computeOutcomeBucket_(score, overallOk, scoredFlag) {
  var scored = _isTrueCell_(scoredFlag) || scoredFlag === true;
  var overall = _isTrueCell_(overallOk) || overallOk === true;
  if (!scored) return 'unscored';
  if (overall) return 'full_hit';
  if (score >= 3) return 'partial_hit';
  if (score >= 1) return 'weak_fit';
  return 'miss';
}

function _outcomeLedgerBucket_(scored, score, overallOk) {
  return computeOutcomeBucket_(score, overallOk, scored ? 'TRUE' : 'FALSE');
}

function _outcomeLedgerPredictionBias_(reactionDir) {
  var dir = String(reactionDir || '').trim().toLowerCase();
  if (dir === 'up') return 'upside_bias';
  if (dir === 'down') return 'downside_bias';
  if (dir === 'flat') return 'flat_bias';
  return '';
}

function deriveOutcomeFamily_(indicatorName, genre) {
  var text = String(indicatorName || '') + ' ' + String(genre || '');
  var s = text.toLowerCase();
  if (/\bcpi\b|\bpce\b|\bppi\b|\binflation\b/.test(s)) return 'inflation';
  if (/\bnfp\b|\bpayroll\b|\bunemployment\b|\bwages\b|\bjobless claims\b|\bclaims\b/.test(s)) return 'labor';
  if (/\bgdp\b|\bretail sales\b|\bdurable goods\b|\bfactory orders\b|\bpmi\b|\bism\b/.test(s)) return 'growth';
  if (/\bhousing\b|\bmortgage\b|\bhome sales\b|\bbuilding permits\b/.test(s)) return 'housing';
  if (/\bcrude\b|\boil\b|\bgasoline\b|\bdistillate\b|\beia\b|\bapi\b/.test(s)) return 'energy';
  if (/\bfed\b|\bfomc\b|\bpowell\b|\bminutes\b|\bspeech\b|\btestimony\b/.test(s)) return 'central_bank';
  if (/\bcftc\b|\bpositioning\b/.test(s)) return 'positioning';
  return 'other';
}

function _outcomeLedgerFamilyKey_(indicatorName) {
  return deriveOutcomeFamily_(indicatorName, '');
}

function _deriveReleaseDate_(releaseTs) {
  var s = String(releaseTs || '').trim();
  if (!s) return '';
  var isoMatch = s.match(/^(\d{4}-\d{2}-\d{2})/);
  if (isoMatch) return isoMatch[1];
  var d = new Date(s);
  if (isNaN(d.getTime())) return '';
  return Utilities.formatDate(d, 'UTC', 'yyyy-MM-dd');
}

function _outcomeLedgerComputedScoredFlag_(rowObject) {
  rowObject = rowObject || {};
  if (_isTrueCell_(rowObject.scored_flag)) return true;
  var realDir = String(rowObject.mr_real_dir || '').trim().toLowerCase();
  if (realDir === 'up' || realDir === 'down' || realDir === 'flat') return true;
  var realizedPips = rowObject.realized_pips;
  if (realizedPips !== '' && realizedPips !== null && realizedPips !== undefined) {
    var n = Number(realizedPips);
    if (isFinite(n)) return true;
  }
  return false;
}

function buildPredictionAggregatesSheet_() {
  var predSheet = getSheet((CFG && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions');
  if (!predSheet) throw new Error('Predictions sheet missing');

  var aggSheet = _getOrCreateSheet_('Prediction_Aggregates');
  var aggHeaders = _predictionAggregateHeaders_();
  var predHeaders = (typeof _ensurePredHeaders_ === 'function') ? _ensurePredHeaders_(predSheet) : getHeaderNames(predSheet);
  var predIdx = {};
  for (var i = 0; i < predHeaders.length; i++) predIdx[String(predHeaders[i] || '').trim()] = i;

  var predLastRow = predSheet.getLastRow();
  var predLastCol = predSheet.getLastColumn();
  var data = (predLastRow >= 2 && predLastCol >= 1)
    ? predSheet.getRange(2, 1, predLastRow - 1, predLastCol).getValues()
    : [];

  var groups = {};
  for (var r = 0; r < data.length; r++) {
    var row = data[r];
    var eventId = String(_predValue_(row, predIdx, 'event_id') || '').trim();
    if (!eventId) continue;
    if (!groups[eventId]) groups[eventId] = [];
    groups[eventId].push(row);
  }

  var generatedTs = new Date().toISOString();
  var rowsOut = [];
  Object.keys(groups).forEach(function(eventId) {
    var dedupedRows = (typeof _dedupePredictionRowsForAggregate_ === 'function')
      ? _dedupePredictionRowsForAggregate_(groups[eventId], predIdx)
      : groups[eventId];
    rowsOut.push(_buildPredictionAggregateRow_(dedupedRows, predIdx, generatedTs));
  });

  _sortPredictionAggregateRows_(aggHeaders, rowsOut);
  _rewriteSheet_(aggSheet, aggHeaders, rowsOut);

  return {
    aggregate_sheet: aggSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildPredictionAggregatesSheet() {
  return buildPredictionAggregatesSheet_();
}

function _predictionAggregateHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'batch_id',
    'type',
    'country',
    'indicator_name',
    'release_ts',
    'provider_count',
    'economic_aggregate_bias',
    'economic_agreement_level',
    'market_aggregate_bias',
    'market_agreement_level',
    'market_disagreement_level',
    'up_count',
    'down_count',
    'flat_count',
    'uncertain_count',
    'whipsaw_risk',
    'volatility_risk',
    'aggregate_confidence',
    'summary_note',
    'no_trade_advice_flag'
  ];
}

function _buildPredictionAggregateRow_(rows, predIdx, generatedTs) {
  var first = rows[0];
  var aggregate = _buildPredictionAggregateFromRows_(rows, predIdx);
  return [
    generatedTs,
    aggregate.event_id,
    String(_predValue_(first, predIdx, 'batch_id') || ''),
    String(_predValue_(first, predIdx, 'type') || ''),
    String(_predValue_(first, predIdx, 'country') || ''),
    String(_predValue_(first, predIdx, 'indicator_name') || ''),
    String(_predValue_(first, predIdx, 'release_ts') || ''),
    aggregate.provider_count,
    aggregate.economic_agreement.aggregate_bias,
    aggregate.economic_agreement.agreement_level,
    aggregate.market_reaction_agreement.aggregate_bias,
    aggregate.market_reaction_agreement.agreement_level,
    aggregate.market_reaction_agreement.disagreement_level,
    aggregate.market_reaction_agreement.up_count,
    aggregate.market_reaction_agreement.down_count,
    aggregate.market_reaction_agreement.flat_count,
    aggregate.market_reaction_agreement.uncertain_count,
    aggregate.risk_summary.whipsaw_risk,
    aggregate.risk_summary.volatility_risk,
    aggregate.risk_summary.confidence,
    _predictionAggregateSummaryNote_(aggregate),
    aggregate.no_trade_advice_flag ? 'TRUE' : 'FALSE'
  ];
}

function _buildPredictionAggregateFromRows_(rows, predIdx) {
  var uniqueProvider = {};
  var economicCounts = { stronger: 0, weaker: 0, inline: 0, uncertain: 0 };
  var reactionCounts = { up: 0, down: 0, flat: 0, uncertain: 0 };
  var predictedPips = [];
  var first = rows[0];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var aiName = String(_predValue_(row, predIdx, 'ai_name') || '').trim();
    if (aiName) uniqueProvider[aiName] = true;

    var status = String(_predValue_(row, predIdx, 'status') || '').trim().toLowerCase();
    if (status !== 'ok') {
      economicCounts.uncertain++;
      reactionCounts.uncertain++;
      continue;
    }

    var econBias = (typeof _aggregateEconomicBucket_ === 'function')
      ? _aggregateEconomicBucket_(_predValue_(row, predIdx, 'qualitative_result'))
      : 'uncertain';
    economicCounts[econBias]++;

    var reactionBias = (typeof _aggregateReactionBucket_ === 'function')
      ? _aggregateReactionBucket_(_predValue_(row, predIdx, 'mr_pred_dir'))
      : 'uncertain';
    reactionCounts[reactionBias]++;

    var pips = _numOrNull_(_predValue_(row, predIdx, 'mr_pred_net_pips'));
    if (pips != null) predictedPips.push(Math.abs(pips));
  }

  return {
    event_id: String(_predValue_(first, predIdx, 'event_id') || ''),
    provider_count: Object.keys(uniqueProvider).length,
    economic_agreement: {
      stronger_count: economicCounts.stronger,
      weaker_count: economicCounts.weaker,
      inline_count: economicCounts.inline,
      uncertain_count: economicCounts.uncertain,
      aggregate_bias: _aggregateBiasFromCounts_(economicCounts, ['stronger', 'weaker', 'inline'], 'uncertain'),
      agreement_level: _aggregateAgreementLevel_(economicCounts, ['stronger', 'weaker', 'inline'])
    },
    market_reaction_agreement: {
      up_count: reactionCounts.up,
      down_count: reactionCounts.down,
      flat_count: reactionCounts.flat,
      uncertain_count: reactionCounts.uncertain,
      aggregate_bias: _aggregateBiasFromCounts_(reactionCounts, ['up', 'down', 'flat'], 'uncertain'),
      agreement_level: _aggregateAgreementLevel_(reactionCounts, ['up', 'down', 'flat']),
      disagreement_level: _aggregateDisagreementLevel_(reactionCounts, ['up', 'down', 'flat'])
    },
    risk_summary: {
      whipsaw_risk: _aggregateWhipsawRisk_(reactionCounts),
      volatility_risk: _aggregateVolatilityRisk_(predictedPips),
      confidence: _aggregateConfidence_(
        economicCounts,
        reactionCounts,
        ['stronger', 'weaker', 'inline'],
        ['up', 'down', 'flat']
      )
    },
    no_trade_advice_flag: true
  };
}

function _predictionAggregateSummaryNote_(aggregate) {
  return (
    'Aggregate provider view: economic bias=' + aggregate.economic_agreement.aggregate_bias +
    ', reaction bias=' + aggregate.market_reaction_agreement.aggregate_bias +
    ', confidence=' + aggregate.risk_summary.confidence +
    ', whipsaw risk=' + aggregate.risk_summary.whipsaw_risk +
    '. No trade advice.'
  );
}

function _evaluationRowHeaders_() {
  return [
    'generated_ts',
    'release_date',
    'release_ts',
    'event_id',
    'batch_id',
    'prediction_id',
    'run_id',
    'type',
    'indicator_name',
    'country',
    'genre',
    'importance',
    'fx_pair',
    'ai_name',
    'ai_model',
    'schema_version',
    'status',
    'qualitative_result',
    'consensus_value',
    'prev_revision',
    'ai_forecast_value',
    'released_value',
    'mr_pred_dir',
    'mr_pred_net_pips',
    'mr_pred_strength',
    'mr_pred_sustain_min',
    'mr_real_dir',
    'mr_real_strength',
    'mr_real_sustain_min',
    'mr_dir_ok',
    'mr_strength_ok',
    'mr_sustain_ok',
    'overall_ok',
    'realized_pips',
    'mr_real_max_up_pips',
    'mr_real_max_down_pips',
    'mr_final_provider',
    'eval_note',
    'mr_compare_status',
    'mr_compare_note',
    'eval_ts',
    'trace_prediction_key',
    'batch_anchor_mode',
    'batch_anchor_confidence',
    'batch_anchor_event_id',
    'batch_anchor_indicator_name',
    'batch_anchor_score',
    'batch_anchor_margin',
    'batch_anchor_runner_up_event_id',
    'batch_anchor_runner_up_indicator_name',
    'batch_anchor_reason',
    'pre_signal_mode',
    'pre_risk_level',
    'pre_volatility_level',
    'watch_member_event_ids',
    'watch_member_indicator_names',
    'scenario_confidence'
  ];
}

function _evaluationSummaryHeaders_() {
  return [
    'generated_ts',
    'release_date',
    'ai_name',
    'scope',
    'rows_scored',
    'dir_ok_count',
    'dir_ok_rate',
    'strength_ok_count',
    'strength_ok_rate',
    'sustain_ok_count',
    'sustain_ok_rate',
    'overall_ok_count',
    'overall_ok_rate',
    'avg_realized_abs_pips',
    'avg_pred_abs_pips',
    'breakdown',
    'genre',
    'importance',
    'event_type'
  ];
}

function _evaluationBatchCompareHeaders_() {
  return [
    'generated_ts',
    'release_date',
    'release_ts',
    'batch_id',
    'ai_name',
    'member_count',
    'batch_indicator_name',
    'batch_pred_dir',
    'batch_pred_net_pips',
    'batch_pred_strength',
    'batch_pred_sustain_min',
    'batch_dir_ok',
    'batch_strength_ok',
    'batch_sustain_ok',
    'batch_overall_ok',
    'best_member_event_id',
    'best_member_indicator_name',
    'best_member_genre',
    'best_member_importance',
    'best_member_pred_dir',
    'best_member_pred_net_pips',
    'best_member_pred_strength',
    'best_member_pred_sustain_min',
    'best_member_dir_ok',
    'best_member_strength_ok',
    'best_member_sustain_ok',
    'best_member_overall_ok',
    'winner',
    'winner_reason',
    'mr_real_dir',
    'mr_real_strength',
    'realized_pips',
    'selected_anchor_mode',
    'selected_anchor_confidence',
    'selected_anchor_event_id',
    'selected_anchor_indicator_name',
    'selected_anchor_score',
    'selected_anchor_margin',
    'selected_anchor_runner_up_event_id',
    'selected_anchor_runner_up_indicator_name',
    'selected_anchor_reason',
    'selected_anchor_dir_ok',
    'selected_anchor_strength_ok',
    'selected_anchor_sustain_ok',
    'selected_anchor_overall_ok',
    'selected_anchor_matches_best_member'
  ];
}

function _evaluationScenarioHeaders_() {
  return [
    'generated_ts',
    'release_date',
    'release_ts',
    'batch_id',
    'ai_name',
    'pre_signal_mode',
    'pre_risk_level',
    'pre_volatility_level',
    'scenario_confidence',
    'watch_member_count',
    'watch_member_event_ids',
    'watch_member_indicator_names',
    'best_member_event_id',
    'best_member_indicator_name',
    'best_member_genre',
    'best_member_importance',
    'best_member_rank_in_watchlist',
    'watchlist_hit',
    'scenario_eval_result',
    'batch_anchor_mode',
    'batch_pred_dir',
    'batch_pred_net_pips',
    'batch_pred_strength',
    'batch_overall_ok',
    'best_member_pred_dir',
    'best_member_pred_net_pips',
    'best_member_pred_strength',
    'best_member_overall_ok',
    'mr_real_dir',
    'mr_real_strength',
    'realized_pips',
    'scenario_eval_note'
  ];
}

function _buildEvaluationRow_(src, idx, generatedTs) {
  var releaseTs = _predValue_(src, idx, 'release_ts');
  var releaseDate = String(releaseTs || '').slice(0, 10);
  var eventId = _predValue_(src, idx, 'event_id');
  var aiName = _predValue_(src, idx, 'ai_name');
  var predictionId = _predValue_(src, idx, 'prediction_id');
  var type = _predValue_(src, idx, 'type');
  var releasedValue = (String(type || '').toLowerCase() === 'batch') ? '' : _predValue_(src, idx, 'released_value');
  return [
    generatedTs,
    releaseDate,
    releaseTs,
    eventId,
    _predValue_(src, idx, 'batch_id'),
    predictionId,
    _predValue_(src, idx, 'run_id'),
    type,
    _predValue_(src, idx, 'indicator_name'),
    _predValue_(src, idx, 'country'),
    _predValue_(src, idx, 'genre'),
    _predValue_(src, idx, 'importance'),
    _predValue_(src, idx, 'fx_pair'),
    aiName,
    _predValue_(src, idx, 'ai_model'),
    _predValue_(src, idx, 'schema_version'),
    _predValue_(src, idx, 'status'),
    _predValue_(src, idx, 'qualitative_result'),
    _predValue_(src, idx, 'consensus_value'),
    _predValue_(src, idx, 'prev_revision'),
    _predValue_(src, idx, 'ai_forecast_value'),
    releasedValue,
    _predValue_(src, idx, 'mr_pred_dir'),
    _predValue_(src, idx, 'mr_pred_net_pips'),
    _predValue_(src, idx, 'mr_pred_strength'),
    _predValue_(src, idx, 'mr_pred_sustain_min'),
    _predValue_(src, idx, 'mr_real_dir'),
    _predValue_(src, idx, 'mr_real_strength'),
    _predValue_(src, idx, 'mr_real_sustain_min'),
    _predValue_(src, idx, 'mr_dir_ok'),
    _predValue_(src, idx, 'mr_strength_ok'),
    _predValue_(src, idx, 'mr_sustain_ok'),
    _predValue_(src, idx, 'overall_ok'),
    _predValue_(src, idx, 'realized_pips'),
    _predValue_(src, idx, 'mr_real_max_up_pips'),
    _predValue_(src, idx, 'mr_real_max_down_pips'),
    _predValue_(src, idx, 'mr_final_provider'),
    _predValue_(src, idx, 'eval_note'),
    _predValue_(src, idx, 'mr_compare_status'),
    _predValue_(src, idx, 'mr_compare_note'),
    _predValue_(src, idx, 'eval_ts'),
    eventId + '|' + aiName + '|' + predictionId,
    _predValue_(src, idx, 'batch_anchor_mode'),
    _predValue_(src, idx, 'batch_anchor_confidence'),
    _predValue_(src, idx, 'batch_anchor_event_id'),
    _predValue_(src, idx, 'batch_anchor_indicator_name'),
    _predValue_(src, idx, 'batch_anchor_score'),
    _predValue_(src, idx, 'batch_anchor_margin'),
    _predValue_(src, idx, 'batch_anchor_runner_up_event_id'),
    _predValue_(src, idx, 'batch_anchor_runner_up_indicator_name'),
    _predValue_(src, idx, 'batch_anchor_reason'),
    _predValue_(src, idx, 'pre_signal_mode'),
    _predValue_(src, idx, 'pre_risk_level'),
    _predValue_(src, idx, 'pre_volatility_level'),
    _predValue_(src, idx, 'watch_member_event_ids'),
    _predValue_(src, idx, 'watch_member_indicator_names'),
    _predValue_(src, idx, 'scenario_confidence')
  ];
}

function _evaluationRowHeaderIndex_() {
  var headers = _evaluationRowHeaders_();
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;
  return idx;
}

function _dedupeEvaluationRowsByPredictionKey_(rows) {
  if (!rows || !rows.length) return [];

  var ridx = _evaluationRowHeaderIndex_();
  var latestByKey = {};
  var order = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var predictionId = String(row[ridx.prediction_id] || '').trim();
    var eventId = String(row[ridx.event_id] || '').trim();
    var aiName = String(row[ridx.ai_name] || '').trim();
    var key = predictionId || (eventId + '|' + aiName);
    if (!key) continue;

    if (!latestByKey.hasOwnProperty(key)) {
      latestByKey[key] = row;
      order.push(key);
      continue;
    }

    if (_evaluationRowIsNewer_(row, latestByKey[key], ridx)) {
      latestByKey[key] = row;
    }
  }

  var out = [];
  for (var j = 0; j < order.length; j++) out.push(latestByKey[order[j]]);
  return out;
}

function _evaluationRowIsNewer_(candidate, existing, ridx) {
  var candidateEvalMs = _evaluationDateMs_(candidate[ridx.eval_ts]);
  var existingEvalMs = _evaluationDateMs_(existing[ridx.eval_ts]);
  if (candidateEvalMs !== existingEvalMs) return candidateEvalMs > existingEvalMs;

  var candidateGeneratedMs = _evaluationDateMs_(candidate[ridx.generated_ts]);
  var existingGeneratedMs = _evaluationDateMs_(existing[ridx.generated_ts]);
  if (candidateGeneratedMs !== existingGeneratedMs) return candidateGeneratedMs > existingGeneratedMs;

  return true;
}

function _evaluationDateMs_(value) {
  var ms = Date.parse(String(value || '').trim());
  return isFinite(ms) ? ms : -1;
}

function _filterLegacySplitBatchRows_(rows) {
  if (!rows || !rows.length) return [];

  var ridx = _evaluationRowHeaderIndex_();
  var splitBases = {};

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var batchId = String(row[ridx.batch_id] || '').trim();
    var aiName = String(row[ridx.ai_name] || '').trim();
    var releaseTs = String(row[ridx.release_ts] || '').trim();
    var splitPos = batchId.indexOf('__');
    if (splitPos < 0 || !aiName || !releaseTs) continue;
    splitBases[releaseTs + '|' + aiName + '|' + batchId.slice(0, splitPos)] = true;
  }

  if (!Object.keys(splitBases).length) return rows;

  var out = [];
  for (var j = 0; j < rows.length; j++) {
    var candidate = rows[j];
    var candidateType = String(candidate[ridx.type] || '').trim().toLowerCase();
    var candidateBatchId = String(candidate[ridx.batch_id] || '').trim();
    var candidateAiName = String(candidate[ridx.ai_name] || '').trim();
    var candidateReleaseTs = String(candidate[ridx.release_ts] || '').trim();
    var legacyKey = candidateReleaseTs + '|' + candidateAiName + '|' + candidateBatchId;
    if (candidateType === 'batch' && splitBases[legacyKey]) continue;
    out.push(candidate);
  }
  return out;
}

function _evaluationFindMemberByEventId_(members, eventId, ridx) {
  var target = String(eventId || '').trim();
  if (!target) return null;
  for (var i = 0; i < (members || []).length; i++) {
    if (String(members[i][ridx.event_id] || '').trim() === target) return members[i];
  }
  return null;
}

function _evaluationRelevantMembers_(batchRow, members, ridx) {
  var familyKey = _evaluationBatchFamilyKey_(batchRow, members, ridx);
  if (!familyKey) return members || [];

  var filtered = [];
  for (var i = 0; i < (members || []).length; i++) {
    if (_evaluationMemberRelevantForFamily_(members[i], familyKey, ridx)) filtered.push(members[i]);
  }
  return filtered.length ? filtered : (members || []);
}

function _evaluationBatchFamilyKey_(batchRow, members, ridx) {
  var authoritativeText = [
    batchRow ? batchRow[ridx.indicator_name] : '',
    batchRow ? batchRow[ridx.batch_anchor_indicator_name] : '',
    batchRow ? batchRow[ridx.batch_anchor_runner_up_indicator_name] : '',
    batchRow ? batchRow[ridx.watch_member_indicator_names] : ''
  ].join(' | ');
  var authoritativeKeys = _evaluationFamilyKeysFromText_(authoritativeText);
  if (authoritativeKeys.length === 1) return authoritativeKeys[0];
  if (authoritativeKeys.length > 1) return '';

  var seen = {};
  for (var i = 0; i < (members || []).length; i++) {
    var memberKeys = _evaluationFamilyKeysFromText_(members[i][ridx.indicator_name]);
    for (var k = 0; k < memberKeys.length; k++) seen[memberKeys[k]] = true;
  }
  var keys = Object.keys(seen);
  return keys.length === 1 ? keys[0] : '';
}

function _evaluationFamilyKeysFromText_(value) {
  var text = _normalizeEvaluationName_(value);
  var out = [];

  if (/\b(non farm payrolls?|nfp|unemployment rate|u 6 unemployment|average hourly earnings|average weekly hours|participation rate|labor force participation|private payrolls?|manufacturing payrolls?|government payrolls?)\b/.test(text)) {
    out.push('monthly_labor');
  }
  if (/\b(initial jobless claims|continuing jobless claims|jobless claims 4 week|jobless claims four week)\b/.test(text)) {
    out.push('jobless_claims');
  }
  if (/\b(ism services|ism non manufacturing|non manufacturing pmi|non manufacturing new orders|non manufacturing prices|non manufacturing business activity|non manufacturing employment)\b/.test(text)) {
    out.push('ism_services');
  }
  if (/\bism manufacturing\b/.test(text)) {
    out.push('ism_manufacturing');
  }
  if (/\bs p global\b/.test(text) && /\b(pmi|services|composite|manufacturing)\b/.test(text)) {
    out.push('sp_global_pmi');
  }
  if (/\bfactory orders\b/.test(text)) {
    out.push('factory_orders');
  }
  if (/\bdurable goods orders\b|\bnon defense goods orders ex air\b/.test(text)) {
    out.push('durable_goods');
  }
  if (/\b(30 year mortgage rate|15 year mortgage rate)\b/.test(text)) {
    out.push('mortgage_rates');
  }
  if (/\b(all car sales|all truck sales|vehicle sales)\b/.test(text)) {
    out.push('vehicle_sales');
  }
  if (/\bmba mortgage\b/.test(text)) {
    out.push('mba_mortgage');
  }
  return out;
}

function _evaluationMemberRelevantForFamily_(member, familyKey, ridx) {
  var name = _normalizeEvaluationName_(member ? member[ridx.indicator_name] : '');
  var genre = _normalizeEvaluationName_(member ? member[ridx.genre] : '');

  if (_evaluationIsSidePositioningMember_(name, genre)) return false;

  if (familyKey === 'monthly_labor') {
    return genre === 'labor' ||
      /\b(non farm payrolls?|nfp|unemployment rate|u 6 unemployment|average hourly earnings|average weekly hours|participation rate|labor force participation|private payrolls?|manufacturing payrolls?|government payrolls?)\b/.test(name);
  }
  if (familyKey === 'jobless_claims') {
    return /\b(initial jobless claims|continuing jobless claims|jobless claims 4 week|jobless claims four week)\b/.test(name);
  }
  if (familyKey === 'ism_services') {
    return (/\bism\b/.test(name) && /\b(services|non manufacturing)\b/.test(name)) ||
      /\bnon manufacturing\b/.test(name);
  }
  if (familyKey === 'ism_manufacturing') {
    return /\bism manufacturing\b/.test(name) && !/\bnon manufacturing\b/.test(name);
  }
  if (familyKey === 'sp_global_pmi') {
    return /\bs p global\b/.test(name) && /\b(pmi|services|composite|manufacturing)\b/.test(name);
  }
  if (familyKey === 'factory_orders') {
    return /\bfactory orders\b/.test(name);
  }
  if (familyKey === 'durable_goods') {
    return /\bdurable goods orders\b|\bnon defense goods orders ex air\b/.test(name);
  }
  if (familyKey === 'mortgage_rates') {
    return /\b(30 year mortgage rate|15 year mortgage rate)\b/.test(name);
  }
  if (familyKey === 'vehicle_sales') {
    return /\b(all car sales|all truck sales|vehicle sales)\b/.test(name);
  }
  if (familyKey === 'mba_mortgage') {
    return /\bmba mortgage\b/.test(name);
  }
  return true;
}

function _evaluationIsSidePositioningMember_(name, genre) {
  return genre === 'energy' ||
    /\b(cftc|speculative net positions?|crude oil|natural gas|gold|silver|copper|wheat|corn|soybeans?|s p 500|nasdaq)\b/.test(name);
}

function _buildEvaluationSummaryRows_(rows, generatedTs) {
  var keyMap = {};
  var out = [];

  function add(key, row, meta) {
    if (!keyMap[key]) {
      keyMap[key] = {
        generated_ts: generatedTs,
        release_date: row[1],
        ai_name: row[13],
        scope: meta.scope || '',
        breakdown: meta.breakdown || '',
        genre: meta.genre || '',
        importance: meta.importance || '',
        event_type: meta.event_type || '',
        rows_scored: 0,
        dir_ok_count: 0,
        strength_ok_count: 0,
        sustain_ok_count: 0,
        overall_ok_count: 0,
        realized_abs_sum: 0,
        pred_abs_sum: 0
      };
    }
    var bucket = keyMap[key];
    bucket.rows_scored++;
    bucket.dir_ok_count += _isTrueCell_(row[29]) ? 1 : 0;
    bucket.strength_ok_count += _isTrueCell_(row[30]) ? 1 : 0;
    bucket.sustain_ok_count += _isTrueCell_(row[31]) ? 1 : 0;
    bucket.overall_ok_count += _isTrueCell_(row[32]) ? 1 : 0;
    bucket.realized_abs_sum += Math.abs(_numOrZero_(row[33]));
    bucket.pred_abs_sum += Math.abs(_numOrZero_(row[23]));
  }

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (!_evaluationRowIsScored_(row)) continue;
    var releaseDate = row[1];
    var aiName = row[13];
    var type = String(row[7] || '').toLowerCase();
    var genre = String(row[10] || '').trim();
    var importance = String(row[11] || '').trim();
    var safeType = type || 'unknown';
    var safeGenre = genre || 'unknown';
    var safeImportance = importance || 'unknown';

    add(releaseDate + '|' + aiName + '|by_scope|all', row, {
      breakdown: 'by_scope',
      scope: 'all'
    });
    add(releaseDate + '|' + aiName + '|by_scope|' + safeType, row, {
      breakdown: 'by_scope',
      scope: safeType,
      event_type: safeType
    });
    add(releaseDate + '|' + aiName + '|by_genre|' + safeGenre, row, {
      breakdown: 'by_genre',
      scope: 'all',
      genre: safeGenre
    });
    add(releaseDate + '|' + aiName + '|by_importance|' + safeImportance, row, {
      breakdown: 'by_importance',
      scope: 'all',
      importance: safeImportance
    });
    add(releaseDate + '|' + aiName + '|by_type|' + safeType, row, {
      breakdown: 'by_type',
      scope: 'all',
      event_type: safeType
    });
    add(releaseDate + '|' + aiName + '|by_genre_type|' + safeGenre + '|' + safeType, row, {
      breakdown: 'by_genre_type',
      scope: 'all',
      genre: safeGenre,
      event_type: safeType
    });
  }

  var keys = Object.keys(keyMap).sort();
  for (var k = 0; k < keys.length; k++) {
    var b = keyMap[keys[k]];
    var n = b.rows_scored || 1;
    out.push([
      b.generated_ts,
      b.release_date,
      b.ai_name,
      b.scope,
      b.rows_scored,
      b.dir_ok_count,
      _roundRate_(b.dir_ok_count / n),
      b.strength_ok_count,
      _roundRate_(b.strength_ok_count / n),
      b.sustain_ok_count,
      _roundRate_(b.sustain_ok_count / n),
      b.overall_ok_count,
      _roundRate_(b.overall_ok_count / n),
      _round2_(b.realized_abs_sum / n),
      _round2_(b.pred_abs_sum / n),
      b.breakdown,
      b.genre,
      b.importance,
      b.event_type
    ]);
  }
  return out;
}

function _buildEvaluationBatchCompareRows_(rows, generatedTs) {
  var groups = {};
  var out = [];
  var ridx = _evaluationRowHeaderIndex_();

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var type = String(row[ridx.type] || '').toLowerCase();
    var batchId = String(row[ridx.batch_id] || '').trim();
    var aiName = String(row[ridx.ai_name] || '').trim();
    if (!batchId || !aiName) continue;
    if (type !== 'batch' && type !== 'member') continue;

    var key = batchId + '|' + aiName;
    if (!groups[key]) {
      groups[key] = {
        batch: null,
        members: []
      };
    }
    if (type === 'batch') groups[key].batch = row;
    if (type === 'member') groups[key].members.push(row);
  }

  var keys = Object.keys(groups).sort();
  for (var k = 0; k < keys.length; k++) {
    var g = groups[keys[k]];
    if (!g.batch || !g.members.length) continue;
    if (!_evaluationRowIsScored_(g.batch)) continue;

    var comparisonMembers = _evaluationRelevantMembers_(g.batch, g.members, ridx);
    var best = comparisonMembers[0];
    var bestScore = _evaluationCompareScore_(best);
    for (var m = 1; m < comparisonMembers.length; m++) {
      var candidate = comparisonMembers[m];
      var candidateScore = _evaluationCompareScore_(candidate);
      if (_isBetterEvaluationScore_(candidateScore, bestScore)) {
        best = candidate;
        bestScore = candidateScore;
      }
    }

    var batchScore = _evaluationCompareScore_(g.batch);
    var winner = 'tie';
    var winnerReason = 'same_score';
    if (_isBetterEvaluationScore_(batchScore, bestScore)) {
      winner = 'batch';
      winnerReason = _evaluationWinnerReason_(batchScore, bestScore);
    } else if (_isBetterEvaluationScore_(bestScore, batchScore)) {
      winner = 'best_member';
      winnerReason = _evaluationWinnerReason_(bestScore, batchScore);
    }

    var selectedAnchorMode = String(g.batch[ridx.batch_anchor_mode] || '').trim();
    var selectedAnchorConfidence = String(g.batch[ridx.batch_anchor_confidence] || '').trim();
    var selectedAnchorEventId = String(g.batch[ridx.batch_anchor_event_id] || '').trim();
    var selectedAnchor = _evaluationFindMemberByEventId_(g.members, selectedAnchorEventId, ridx);
    var selectedAnchorMatchBest = '';
    if (selectedAnchorEventId) {
      selectedAnchorMatchBest = String(
        String(best[ridx.event_id] || '').trim() === selectedAnchorEventId ? 'TRUE' : 'FALSE'
      );
    } else if (selectedAnchorMode === 'no_clear_anchor') {
      selectedAnchorMatchBest = 'NO_ANCHOR';
    }

    out.push([
      generatedTs,
      g.batch[ridx.release_date],
      g.batch[ridx.release_ts],
      g.batch[ridx.batch_id],
      g.batch[ridx.ai_name],
      g.members.length,
      g.batch[ridx.indicator_name],
      g.batch[ridx.mr_pred_dir],
      g.batch[ridx.mr_pred_net_pips],
      g.batch[ridx.mr_pred_strength],
      g.batch[ridx.mr_pred_sustain_min],
      g.batch[ridx.mr_dir_ok],
      g.batch[ridx.mr_strength_ok],
      g.batch[ridx.mr_sustain_ok],
      g.batch[ridx.overall_ok],
      best[ridx.event_id],
      best[ridx.indicator_name],
      best[ridx.genre],
      best[ridx.importance],
      best[ridx.mr_pred_dir],
      best[ridx.mr_pred_net_pips],
      best[ridx.mr_pred_strength],
      best[ridx.mr_pred_sustain_min],
      best[ridx.mr_dir_ok],
      best[ridx.mr_strength_ok],
      best[ridx.mr_sustain_ok],
      best[ridx.overall_ok],
      winner,
      winnerReason,
      g.batch[ridx.mr_real_dir],
      g.batch[ridx.mr_real_strength],
      g.batch[ridx.realized_pips],
      selectedAnchorMode,
      selectedAnchorConfidence,
      selectedAnchorEventId,
      g.batch[ridx.batch_anchor_indicator_name],
      g.batch[ridx.batch_anchor_score],
      g.batch[ridx.batch_anchor_margin],
      g.batch[ridx.batch_anchor_runner_up_event_id],
      g.batch[ridx.batch_anchor_runner_up_indicator_name],
      g.batch[ridx.batch_anchor_reason],
      selectedAnchor ? selectedAnchor[ridx.mr_dir_ok] : '',
      selectedAnchor ? selectedAnchor[ridx.mr_strength_ok] : '',
      selectedAnchor ? selectedAnchor[ridx.mr_sustain_ok] : '',
      selectedAnchor ? selectedAnchor[ridx.overall_ok] : '',
      selectedAnchorMatchBest
    ]);
  }

  return out;
}

function _buildEvaluationScenarioRows_(rows, generatedTs) {
  var groups = {};
  var out = [];
  var ridx = _evaluationRowHeaderIndex_();

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var type = String(row[ridx.type] || '').toLowerCase();
    var batchId = String(row[ridx.batch_id] || '').trim();
    var aiName = String(row[ridx.ai_name] || '').trim();
    if (!batchId || !aiName) continue;
    if (type !== 'batch' && type !== 'member') continue;

    var key = batchId + '|' + aiName;
    if (!groups[key]) groups[key] = { batch: null, members: [] };
    if (type === 'batch') groups[key].batch = row;
    if (type === 'member') groups[key].members.push(row);
  }

  var keys = Object.keys(groups).sort();
  for (var k = 0; k < keys.length; k++) {
    var g = groups[keys[k]];
    if (!g.batch || !g.members.length) continue;

    var mode = String(g.batch[ridx.pre_signal_mode] || '').trim().toLowerCase();
    if (mode !== 'scenario') continue;
    var watchIds = _splitEvaluationPipeList_(g.batch[ridx.watch_member_event_ids]);
    var watchNames = _splitEvaluationPipeList_(g.batch[ridx.watch_member_indicator_names]);

    var scenarioMembers = _evaluationRelevantMembers_(g.batch, g.members, ridx);
    if (!_evaluationRowIsScored_(g.batch) && !_evaluationAnyScoredRows_(scenarioMembers)) continue;
    var best = scenarioMembers[0];
    var bestScore = _evaluationCompareScore_(best);
    for (var m = 1; m < scenarioMembers.length; m++) {
      var candidate = scenarioMembers[m];
      var candidateScore = _evaluationCompareScore_(candidate);
      if (_isBetterEvaluationScore_(candidateScore, bestScore)) {
        best = candidate;
        bestScore = candidateScore;
      }
    }

    var bestRank = _evaluationWatchlistRank_(best, watchIds, watchNames, ridx);
    var watchHit = bestRank > 0;
    var result = _evaluationScenarioResult_(mode, watchIds, watchNames, best, watchHit);

    out.push([
      generatedTs,
      g.batch[ridx.release_date],
      g.batch[ridx.release_ts],
      g.batch[ridx.batch_id],
      g.batch[ridx.ai_name],
      g.batch[ridx.pre_signal_mode],
      g.batch[ridx.pre_risk_level],
      g.batch[ridx.pre_volatility_level],
      g.batch[ridx.scenario_confidence],
      Math.max(watchIds.length, watchNames.length),
      g.batch[ridx.watch_member_event_ids],
      g.batch[ridx.watch_member_indicator_names],
      best[ridx.event_id],
      best[ridx.indicator_name],
      best[ridx.genre],
      best[ridx.importance],
      bestRank || '',
      watchHit ? 'TRUE' : 'FALSE',
      result,
      g.batch[ridx.batch_anchor_mode],
      g.batch[ridx.mr_pred_dir],
      g.batch[ridx.mr_pred_net_pips],
      g.batch[ridx.mr_pred_strength],
      g.batch[ridx.overall_ok],
      best[ridx.mr_pred_dir],
      best[ridx.mr_pred_net_pips],
      best[ridx.mr_pred_strength],
      best[ridx.overall_ok],
      g.batch[ridx.mr_real_dir],
      g.batch[ridx.mr_real_strength],
      g.batch[ridx.realized_pips],
      _evaluationScenarioNote_(result, best, ridx)
    ]);
  }

  return out;
}

function _splitEvaluationPipeList_(value) {
  return String(value || '')
    .split('|')
    .map(function(v){ return String(v || '').trim(); })
    .filter(function(v){ return !!v; });
}

function _evaluationWatchlistRank_(best, watchIds, watchNames, ridx) {
  if (!best) return 0;
  var bestId = String(best[ridx.event_id] || '').trim();
  for (var i = 0; i < watchIds.length; i++) {
    if (bestId && String(watchIds[i] || '').trim() === bestId) return i + 1;
  }

  var bestName = _normalizeEvaluationName_(best[ridx.indicator_name]);
  for (var n = 0; n < watchNames.length; n++) {
    if (bestName && _normalizeEvaluationName_(watchNames[n]) === bestName) return n + 1;
  }
  return 0;
}

function _evaluationScenarioResult_(mode, watchIds, watchNames, best, watchHit) {
  if (!best) return 'no_best_member';
  if (!watchIds.length && !watchNames.length) return 'no_watchlist';
  return watchHit ? 'hit' : 'miss';
}

function _evaluationScenarioNote_(result, best, ridx) {
  var bestName = best ? String(best[ridx.indicator_name] || '') : '';
  if (result === 'hit') return 'watchlist_included_best_member=' + bestName;
  if (result === 'miss') return 'watchlist_missed_best_member=' + bestName;
  return result;
}

function _normalizeEvaluationName_(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function _evaluationCompareScore_(row) {
  return {
    overall: _boolScore_(row[32]),
    dir: _boolScore_(row[29]),
    strength: _boolScore_(row[30]),
    sustain: _boolScore_(row[31]),
    pred_gap: Math.abs(Math.abs(_numOrZero_(row[23])) - Math.abs(_numOrZero_(row[33]))),
    pred_abs: Math.abs(_numOrZero_(row[23]))
  };
}

function _isBetterEvaluationScore_(a, b) {
  if (a.overall !== b.overall) return a.overall > b.overall;
  var aDirStrength = a.dir + a.strength;
  var bDirStrength = b.dir + b.strength;
  if (aDirStrength !== bDirStrength) return aDirStrength > bDirStrength;
  if (a.dir !== b.dir) return a.dir > b.dir;
  if (a.strength !== b.strength) return a.strength > b.strength;
  if (a.sustain !== b.sustain) return a.sustain > b.sustain;
  if (a.pred_gap !== b.pred_gap) return a.pred_gap < b.pred_gap;
  if (a.pred_abs !== b.pred_abs) return a.pred_abs < b.pred_abs;
  return false;
}

function _evaluationWinnerReason_(winnerScore, loserScore) {
  if (winnerScore.overall !== loserScore.overall) return 'overall_ok';
  var winnerDirStrength = winnerScore.dir + winnerScore.strength;
  var loserDirStrength = loserScore.dir + loserScore.strength;
  if (winnerDirStrength !== loserDirStrength) return 'dir_strength_combo';
  if (winnerScore.dir !== loserScore.dir) return 'dir_ok';
  if (winnerScore.strength !== loserScore.strength) return 'strength_ok';
  if (winnerScore.sustain !== loserScore.sustain) return 'sustain_ok';
  if (winnerScore.pred_gap !== loserScore.pred_gap) return 'closer_pip_fit';
  if (winnerScore.pred_abs !== loserScore.pred_abs) return 'smaller_pred_abs';
  return 'same_score';
}

function _evaluationRowIsScored_(row) {
  if (!row || !row.length) return false;
  var realDir = String(row[26] || '').trim().toLowerCase();
  if (realDir === 'up' || realDir === 'down' || realDir === 'flat') return true;
  var realizedPips = row[33];
  if (realizedPips !== '' && realizedPips !== null && realizedPips !== undefined) {
    var n = Number(realizedPips);
    if (isFinite(n)) return true;
  }
  return false;
}

function _evaluationAnyScoredRows_(rows) {
  for (var i = 0; i < (rows || []).length; i++) {
    if (_evaluationRowIsScored_(rows[i])) return true;
  }
  return false;
}

function _predValue_(row, idx, key) {
  var i = idx[key];
  return (i === undefined || i >= row.length) ? '' : row[i];
}

function _getOrCreateSheet_(name) {
  var ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function _rewriteSheet_(sheet, headers, rows) {
  sheet.clearContents();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  if (rows && rows.length) {
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }
  sheet.setFrozenRows(1);
}

function _rewriteSheetRowsPreservingHeaders_(sheet, headers, rows) {
  var lastRow = sheet.getLastRow();
  var lastCol = Math.max(sheet.getLastColumn(), headers.length);
  if (lastRow > 1 && lastCol > 0) {
    sheet.getRange(2, 1, lastRow - 1, lastCol).clearContent();
  }
  if (rows && rows.length) {
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }
  sheet.setFrozenRows(1);
}

function _headerIndexMap_(headers) {
  var out = {};
  for (var i = 0; i < headers.length; i++) out[String(headers[i] || '')] = i;
  return out;
}

function _cmpText_(a, b) {
  a = String(a == null ? '' : a);
  b = String(b == null ? '' : b);
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

function _cmpByColumns_(a, b, cols) {
  for (var i = 0; i < cols.length; i++) {
    var c = cols[i];
    var av = a[c];
    var bv = b[c];
    var cmp = _cmpText_(av, bv);
    if (cmp !== 0) return cmp;
  }
  return 0;
}

function _sortEvaluationRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.ai_name,
      idx.type,
      idx.batch_id,
      idx.event_id,
      idx.prediction_id
    ]);
  });
}

function _sortEvaluationSummaryRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_date,
      idx.ai_name,
      idx.scope,
      idx.genre,
      idx.importance,
      idx.event_type
    ]);
  });
}

function _sortEvaluationBatchCompareRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.ai_name,
      idx.batch_id,
      idx.best_member_indicator_name
    ]);
  });
}

function _sortEvaluationScenarioRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.ai_name,
      idx.batch_id,
      idx.best_member_indicator_name
    ]);
  });
}

function _sortPredictionAggregateRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.type,
      idx.batch_id,
      idx.event_id
    ]);
  });
}

function _sortOutcomeLedgerRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.outcome_family,
      idx.ai_name,
      idx.type,
      idx.event_id,
      idx.prediction_id
    ]);
  });
}

function _sortOutcomeSummaryProviderFamilyRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.outcome_family,
      idx.ai_name
    ]);
  });
}

function _sortOutcomeSummaryConvergenceRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.type,
      idx.group_key
    ]);
  });
}

function _sortOutcomeSummaryBucketRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.outcome_family,
      idx.ai_name,
      idx.type
    ]);
  });
}

function _sortOutcomeDiagnosticsRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.diagnostic_type,
      idx.outcome_family,
      idx.ai_name,
      idx.scope,
      idx.scope_key
    ]);
  });
}

function _isTrueCell_(v) {
  return String(v || '').trim().toUpperCase() === 'TRUE';
}

function _numOrZero_(v) {
  var n = Number(v);
  return isFinite(n) ? n : 0;
}

function _numOrNull_(v) {
  if (v === '' || v === null || v === undefined) return null;
  var n = Number(v);
  return isFinite(n) ? n : null;
}

function _boolScore_(v) {
  return _isTrueCell_(v) ? 1 : 0;
}

function _roundRate_(v) {
  return Math.round(v * 10000) / 10000;
}

function _rateOrBlank_(num, den) {
  var numerator = Number(num || 0);
  var denominator = Number(den || 0);
  if (!(denominator > 0)) return '';
  return _roundRate_(numerator / denominator);
}

function _sumNumbers_(arr) {
  var sum = 0;
  for (var i = 0; i < (arr || []).length; i++) {
    sum += Number(arr[i] || 0);
  }
  return sum;
}

function _mostCommonFailureType_(g) {
  if (!g || !(Number(g.rows_scored || 0) > 0)) return 'unscored_only';
  var direction = Number(g.direction_miss_count || 0);
  var strength = Number(g.strength_miss_count || 0);
  var sustain = Number(g.sustain_miss_count || 0);
  var best = Math.max(direction, strength, sustain);
  if (best === direction) return 'direction_miss';
  if (best === strength) return 'strength_miss';
  return 'sustain_miss';
}

function _round2_(v) {
  return Math.round(v * 100) / 100;
}
