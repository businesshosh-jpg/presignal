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

function menuBuildAttentionFactorSummary_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionFactorSummary_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention factor summary -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention factor summary rows=' + (res.rows_written || 0),
      'Attention Factor Summary',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention factor summary -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildProviderCharacterDiagnostics_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDiagnostics_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character diagnostics -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Provider character diagnostics rows=' + (res.rows_written || 0),
      'Provider Character Diagnostics',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character diagnostics -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionProviderIndividuality_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionProviderIndividuality_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention provider individuality -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention provider individuality rows=' + (res.rows_written || 0),
      'Attention Provider Individuality',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention provider individuality -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionEvidenceReport_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionEvidenceReport_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention evidence report -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention evidence report rows=' + (res.rows_written || 0),
      'Attention Evidence Report',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention evidence report -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionBlockStability_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionBlockStability_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention block stability -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention block stability rows=' + (res.rows_written || 0),
      'Attention Block Stability',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention block stability -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionDisagreementReview_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionDisagreementReview_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention disagreement review -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention disagreement review rows=' + (res.rows_written || 0),
      'Attention Disagreement Review',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention disagreement review -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionDisagreementSummary_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionDisagreementSummary_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention disagreement summary -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention disagreement summary rows=' + (res.rows_written || 0),
      'Attention Disagreement Summary',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention disagreement summary -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionPhase3Candidates_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionPhase3Candidates_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention Phase3 candidates -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention Phase3 candidates rows=' + (res.rows_written || 0),
      'Attention Phase3 Candidates',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention Phase3 candidates -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildAttentionShadowExperiments_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildAttentionShadowExperiments_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Attention shadow experiments -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Attention shadow rows=' + (res.rows_written || 0) +
      ' | summary=' + (res.summary_rows_written || 0),
      'Attention Shadow Experiments',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Attention shadow experiments -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildFamilyStructureReport_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildFamilyStructureReport_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Family structure report -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Family structure rows=' + (res.rows_written || 0),
      'Family Structure Report',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Family structure report -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildBatchSplittingCandidates_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildBatchSplittingCandidates_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Batch splitting candidates -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast('Batch splitting candidates=' + (res.rows_written || 0), 'Batch Splitting Candidates', 8);
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Batch splitting candidates -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildBatchSplitCounterfactuals_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildBatchSplitCounterfactuals_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Batch split counterfactuals -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast('Batch split counterfactuals=' + (res.rows_written || 0), 'Batch Split Counterfactuals', 8);
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Batch split counterfactuals -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildBatchBaselineCoverageAudit_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildBatchBaselineCoverageAudit_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Batch baseline coverage audit -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast('Batch baseline audit rows=' + (res.rows_written || 0), 'Batch Baseline Coverage Audit', 8);
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Batch baseline coverage audit -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuBuildBatchSplitGroupCounterfactuals_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildBatchSplitGroupCounterfactuals_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Batch split group counterfactuals -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast('Batch split group counterfactuals=' + (res.rows_written || 0), 'Batch Split Group Counterfactuals', 8);
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Batch split group counterfactuals -> Build sheet failed', {
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

function getOrCreateAttentionFactorSummarySheet_() {
  return _getOrCreateSheet_('Attention_Factor_Summary');
}

function getOrCreateProviderCharacterDiagnosticsSheet_() {
  return _getOrCreateSheet_('Provider_Character_Diagnostics');
}

function getOrCreateAttentionProviderIndividualitySheet_() {
  return _getOrCreateSheet_('Attention_Provider_Individuality');
}

function getOrCreateAttentionEvidenceReportSheet_() {
  return _getOrCreateSheet_('Attention_Evidence_Report');
}

function getOrCreateAttentionBlockStabilitySheet_() {
  return _getOrCreateSheet_('Attention_Block_Stability');
}

function getOrCreateAttentionDisagreementReviewSheet_() {
  return _getOrCreateSheet_('Attention_Disagreement_Review');
}

function getOrCreateAttentionDisagreementSummarySheet_() {
  return _getOrCreateSheet_('Attention_Disagreement_Summary');
}

function getOrCreateAttentionPhase3CandidatesSheet_() {
  return _getOrCreateSheet_('Attention_Phase3_Candidates');
}

function getOrCreateAttentionShadowExperimentsSheet_() {
  return _getOrCreateSheet_('Attention_Shadow_Experiments');
}

function getOrCreateAttentionShadowSummarySheet_() {
  return _getOrCreateSheet_('Attention_Shadow_Summary');
}

function getOrCreateFamilyStructureReportSheet_() {
  return _getOrCreateSheet_('Family_Structure_Report');
}

function getOrCreateBatchSplittingCandidatesSheet_() {
  return _getOrCreateSheet_('Batch_Splitting_Candidates');
}

function getOrCreateBatchSplitCounterfactualsSheet_() {
  return _getOrCreateSheet_('Batch_Split_Counterfactuals');
}

function getOrCreateBatchBaselineCoverageAuditSheet_() {
  return _getOrCreateSheet_('Batch_Baseline_Coverage_Audit');
}

function getOrCreateBatchSplitGroupCounterfactualsSheet_() {
  return _getOrCreateSheet_('Batch_Split_Group_Counterfactuals');
}

function ensureOutcomeSummaryHeaders_(sheet, headers) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, headers || []);
}

function ensureOutcomeDiagnosticsHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _outcomeDiagnosticsHeaders_());
}

function ensureAttentionFactorSummaryHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionFactorSummaryHeaders_());
}

function ensureProviderCharacterDiagnosticsHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _providerCharacterDiagnosticsHeaders_());
}

function ensureAttentionProviderIndividualityHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionProviderIndividualityHeaders_());
}

function ensureAttentionEvidenceReportHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionEvidenceReportHeaders_());
}

function ensureAttentionBlockStabilityHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionBlockStabilityHeaders_());
}

function ensureAttentionDisagreementReviewHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionDisagreementReviewHeaders_());
}

function ensureAttentionDisagreementSummaryHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionDisagreementSummaryHeaders_());
}

function ensureAttentionPhase3CandidateHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _attentionPhase3CandidateHeaders_());
}

function ensureAttentionShadowHeaders_(sheet, headers) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, headers || []);
}

function ensureFamilyStructureReportHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _familyStructureReportHeaders_());
}

function ensureBatchSplittingCandidatesHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _batchSplittingCandidatesHeaders_());
}

function ensureBatchSplitCounterfactualsHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _batchSplitCounterfactualsHeaders_());
}

function ensureBatchBaselineCoverageAuditHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _batchBaselineCoverageAuditHeaders_());
}

function ensureBatchSplitGroupCounterfactualsHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _batchSplitGroupCounterfactualsHeaders_());
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

function buildAttentionFactorSummary_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerRows = _readDataRows_(ledgerSheet);
  var ledgerIdx = _headerIndexMap_(ledgerHeaders);
  var summarySheet = getOrCreateAttentionFactorSummarySheet_();
  var headers = _attentionFactorSummaryHeaders_();
  var rowsOut = buildAttentionFactorSummaryRows_(ledgerRows, ledgerIdx, new Date().toISOString());
  _sortAttentionFactorSummaryRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionFactorSummaryHeaders_(summarySheet);
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_factor_summary_sheet: summarySheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildProviderCharacterDiagnostics_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerRows = _readDataRows_(ledgerSheet);
  var ledgerIdx = _headerIndexMap_(ledgerHeaders);
  var diagnosticsSheet = getOrCreateProviderCharacterDiagnosticsSheet_();
  var headers = _providerCharacterDiagnosticsHeaders_();
  var rowsOut = buildProviderCharacterDiagnosticsRows_(ledgerRows, ledgerIdx, new Date().toISOString());
  _sortProviderCharacterDiagnosticsRows_(headers, rowsOut);

  var actualHeaders = ensureProviderCharacterDiagnosticsHeaders_(diagnosticsSheet);
  _rewriteSheetRowsPreservingHeaders_(
    diagnosticsSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    provider_character_diagnostics_sheet: diagnosticsSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionProviderIndividuality_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerRows = _readDataRows_(ledgerSheet);
  var ledgerIdx = _headerIndexMap_(ledgerHeaders);
  var reportSheet = getOrCreateAttentionProviderIndividualitySheet_();
  var headers = _attentionProviderIndividualityHeaders_();
  var rowsOut = buildAttentionProviderIndividualityRows_(ledgerRows, ledgerIdx, new Date().toISOString());
  _sortAttentionProviderIndividualityRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionProviderIndividualityHeaders_(reportSheet);
  _rewriteSheetRowsPreservingHeaders_(
    reportSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_provider_individuality_sheet: reportSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionEvidenceReport_() {
  var summarySheet = getOrCreateAttentionFactorSummarySheet_();
  var characterSheet = getOrCreateProviderCharacterDiagnosticsSheet_();
  var reportSheet = getOrCreateAttentionEvidenceReportSheet_();

  var summaryHeaders = getHeaderNames(summarySheet);
  var characterHeaders = getHeaderNames(characterSheet);
  if (!summaryHeaders || !summaryHeaders.length) {
    throw new Error('Attention_Factor_Summary sheet is missing headers.');
  }
  if (!characterHeaders || !characterHeaders.length) {
    throw new Error('Provider_Character_Diagnostics sheet is missing headers.');
  }

  var summaryRows = _readDataRows_(summarySheet);
  var characterRows = _readDataRows_(characterSheet);
  var summaryIdx = _headerIndexMap_(summaryHeaders);
  var characterIdx = _headerIndexMap_(characterHeaders);
  var headers = _attentionEvidenceReportHeaders_();
  var rowsOut = buildAttentionEvidenceReportRows_(summaryRows, summaryIdx, characterRows, characterIdx, new Date().toISOString());
  _sortAttentionEvidenceReportRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionEvidenceReportHeaders_(reportSheet);
  _rewriteSheetRowsPreservingHeaders_(
    reportSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_evidence_report_sheet: reportSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionBlockStability_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerRows = _readDataRows_(ledgerSheet);
  var ledgerIdx = _headerIndexMap_(ledgerHeaders);
  var stabilitySheet = getOrCreateAttentionBlockStabilitySheet_();
  var headers = _attentionBlockStabilityHeaders_();
  var rowsOut = buildAttentionBlockStabilityRows_(ledgerRows, ledgerIdx, new Date().toISOString());
  _sortAttentionBlockStabilityRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionBlockStabilityHeaders_(stabilitySheet);
  _rewriteSheetRowsPreservingHeaders_(
    stabilitySheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_block_stability_sheet: stabilitySheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionDisagreementReview_() {
  var ledgerSheet = getOrCreateOutcomeLedgerSheet_();
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }

  var ledgerRows = _readDataRows_(ledgerSheet);
  var ledgerIdx = _headerIndexMap_(ledgerHeaders);
  var reviewSheet = getOrCreateAttentionDisagreementReviewSheet_();
  var headers = _attentionDisagreementReviewHeaders_();
  var rowsOut = buildAttentionDisagreementReviewRows_(ledgerRows, ledgerIdx, new Date().toISOString());
  _sortAttentionDisagreementReviewRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionDisagreementReviewHeaders_(reviewSheet);
  _rewriteSheetRowsPreservingHeaders_(
    reviewSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_disagreement_review_sheet: reviewSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionDisagreementSummary_() {
  var reviewSheet = getOrCreateAttentionDisagreementReviewSheet_();
  var reviewHeaders = getHeaderNames(reviewSheet);
  if (!reviewHeaders || !reviewHeaders.length) {
    throw new Error('Attention_Disagreement_Review sheet is missing headers.');
  }

  var reviewRows = _readDataRows_(reviewSheet);
  var reviewIdx = _headerIndexMap_(reviewHeaders);
  var summarySheet = getOrCreateAttentionDisagreementSummarySheet_();
  var headers = _attentionDisagreementSummaryHeaders_();
  var rowsOut = buildAttentionDisagreementSummaryRows_(reviewRows, reviewIdx, new Date().toISOString());
  _sortAttentionDisagreementSummaryRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionDisagreementSummaryHeaders_(summarySheet);
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_disagreement_summary_sheet: summarySheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionPhase3Candidates_() {
  var reviewSheet = getOrCreateAttentionDisagreementReviewSheet_();
  var reviewHeaders = getHeaderNames(reviewSheet);
  if (!reviewHeaders || !reviewHeaders.length) {
    throw new Error('Attention_Disagreement_Review sheet is missing headers.');
  }

  var summarySheet = getOrCreateAttentionDisagreementSummarySheet_();
  var summaryHeaders = getHeaderNames(summarySheet);
  if (!summaryHeaders || !summaryHeaders.length) {
    throw new Error('Attention_Disagreement_Summary sheet is missing headers.');
  }

  var reviewRows = _readDataRows_(reviewSheet);
  var reviewIdx = _headerIndexMap_(reviewHeaders);
  var summaryRows = _readDataRows_(summarySheet);
  var summaryIdx = _headerIndexMap_(summaryHeaders);
  var candidateSheet = getOrCreateAttentionPhase3CandidatesSheet_();
  var headers = _attentionPhase3CandidateHeaders_();
  var rowsOut = buildAttentionPhase3CandidateRows_(reviewRows, reviewIdx, summaryRows, summaryIdx, new Date().toISOString());
  _sortAttentionPhase3CandidateRows_(headers, rowsOut);

  var actualHeaders = ensureAttentionPhase3CandidateHeaders_(candidateSheet);
  _rewriteSheetRowsPreservingHeaders_(
    candidateSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    attention_phase3_candidates_sheet: candidateSheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildAttentionShadowExperiments_() {
  var ledgerRowsBundle = getOutcomeLedgerRowsForShadow_();
  var ledgerRows = ledgerRowsBundle.rows;
  var ledgerIdx = ledgerRowsBundle.idx;
  var convergenceInfo = _getConvergenceInfoForShadow_();
  var groups = groupOutcomeRowsForShadow_(ledgerRows, ledgerIdx);
  var generatedTs = new Date().toISOString();
  var rowsOut = [];

  Object.keys(groups).sort().forEach(function(groupKey) {
    var groupRows = groups[groupKey] || [];
    var baseline = computeShadowBaselineForGroup_(groupRows, ledgerIdx);
    var info = convergenceInfo[groupKey] || _deriveShadowConvergenceInfo_(groupRows, ledgerIdx);
    rowsOut = rowsOut.concat(buildProviderFactorCandidateRows_(groupRows, ledgerIdx, baseline, generatedTs));
    rowsOut = rowsOut.concat(buildDisagreementProviderSelectorRows_(groupRows, ledgerIdx, baseline, info, generatedTs));
    rowsOut = rowsOut.concat(buildLowSignalWatchlistRows_(groupRows, ledgerIdx, generatedTs));
    rowsOut = rowsOut.concat(buildHiddenDetailRiskConfidenceRows_(groupRows, ledgerIdx, generatedTs));
    rowsOut = rowsOut.concat(buildConvergenceNoWeightingRows_(groupRows, ledgerIdx, info, generatedTs));
  });

  var experimentHeaders = _attentionShadowExperimentHeaders_();
  _sortAttentionShadowExperimentRows_(experimentHeaders, rowsOut);
  var experimentSheet = getOrCreateAttentionShadowExperimentsSheet_();
  var actualExperimentHeaders = ensureAttentionShadowHeaders_(experimentSheet, experimentHeaders);
  _rewriteSheetRowsPreservingHeaders_(
    experimentSheet,
    actualExperimentHeaders,
    _remapRowsToHeaders_(experimentHeaders, actualExperimentHeaders, rowsOut)
  );

  var summaryResult = buildAttentionShadowSummary_({
    generated_ts: generatedTs,
    experiment_headers: experimentHeaders,
    experiment_rows: rowsOut
  });

  return {
    attention_shadow_experiments_sheet: experimentSheet.getName(),
    attention_shadow_summary_sheet: summaryResult.sheet_name,
    rows_written: rowsOut.length,
    summary_rows_written: summaryResult.rows_written
  };
}

function buildAttentionShadowSummary_(opts) {
  opts = opts || {};
  var headers = _attentionShadowSummaryHeaders_();
  var experimentHeaders = opts.experiment_headers || _attentionShadowExperimentHeaders_();
  var experimentIdx = _headerIndexMap_(experimentHeaders);
  var experimentRows = opts.experiment_rows || [];
  var rowsOut = _buildAttentionShadowSummaryRows_(experimentRows, experimentIdx, opts.generated_ts || new Date().toISOString());
  _sortAttentionShadowSummaryRows_(headers, rowsOut);
  var summarySheet = getOrCreateAttentionShadowSummarySheet_();
  var actualHeaders = ensureAttentionShadowHeaders_(summarySheet, headers);
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );
  return {
    sheet_name: summarySheet.getName(),
    rows_written: rowsOut.length
  };
}

function buildFamilyStructureReport_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var sources = {
    ledger: _readFamilyStructureSource_('Outcome_Ledger', warnings),
    providerFamily: _readFamilyStructureSource_('Outcome_Summary_ProviderFamily', warnings),
    convergence: _readFamilyStructureSource_('Outcome_Summary_Convergence', warnings),
    batchCompare: _readFamilyStructureSource_('Evaluation_BatchCompare', warnings),
    scenario: _readFamilyStructureSource_('Evaluation_Scenario', warnings),
    diagnostics: _readFamilyStructureSource_('Outcome_Diagnostics', warnings),
    disagreementReview: _readFamilyStructureSource_('Attention_Disagreement_Review', warnings),
    disagreementSummary: _readFamilyStructureSource_('Attention_Disagreement_Summary', warnings),
    phase3: _readFamilyStructureSource_('Attention_Phase3_Candidates', warnings)
  };

  var rowsOut = [];
  var composition = _familyStructureBatchCompositionMap_(sources.ledger);
  var batchCompare = _familyStructureBatchCompareMap_(sources.batchCompare);
  rowsOut = rowsOut.concat(_buildFamilyPerformanceSummaryRows_(generatedTs, sources, warnings));
  rowsOut = rowsOut.concat(_buildBatchCompositionSummaryRows_(generatedTs, composition, batchCompare, warnings));
  rowsOut = rowsOut.concat(_buildBatchVsMemberComparisonRows_(generatedTs, batchCompare, composition, warnings));
  rowsOut = rowsOut.concat(_buildFamilyMixingRiskRows_(generatedTs, composition, batchCompare, warnings));
  rowsOut = rowsOut.concat(_buildRecurringFamilyRuleRows_(generatedTs, sources, batchCompare, warnings));
  rowsOut = rowsOut.concat(_buildRecurringBatchSplittingRows_(generatedTs, composition, batchCompare, warnings));
  rowsOut = rowsOut.concat(_buildFamilyInvestigationSummaryRows_(generatedTs, rowsOut, composition, batchCompare, warnings));

  var headers = _familyStructureReportHeaders_();
  _sortFamilyStructureReportRows_(headers, rowsOut);
  var reportSheet = getOrCreateFamilyStructureReportSheet_();
  var actualHeaders = ensureFamilyStructureReportHeaders_(reportSheet);
  _rewriteSheetRowsPreservingHeaders_(
    reportSheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );

  return {
    family_structure_report_sheet: reportSheet.getName(),
    rows_written: rowsOut.length,
    warnings: _uniqueSortedStrings_(warnings)
  };
}

function buildBatchSplittingCandidates_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var source = _readFamilyStructureSource_('Family_Structure_Report', warnings);
  if (!source.rows.length) {
    warnings.push('missing_or_empty_source:Family_Structure_Report');
  }
  var headers = _batchSplittingCandidatesHeaders_();
  var rowsOut = _buildBatchSplittingCandidateRows_(generatedTs, source, warnings);
  _sortBatchSplittingCandidateRows_(headers, rowsOut);
  var sheet = getOrCreateBatchSplittingCandidatesSheet_();
  var actualHeaders = ensureBatchSplittingCandidatesHeaders_(sheet);
  _rewriteSheetRowsPreservingHeaders_(
    sheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );
  return {
    batch_splitting_candidates_sheet: sheet.getName(),
    rows_written: rowsOut.length,
    warnings: _uniqueSortedStrings_(warnings)
  };
}

function buildBatchSplitCounterfactuals_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var source = _readFamilyStructureSource_('Batch_Splitting_Candidates', warnings);
  var batchCompare = _readFamilyStructureSource_('Evaluation_BatchCompare', warnings);
  if (!source.rows.length) {
    warnings.push('missing_or_empty_source:Batch_Splitting_Candidates');
  }
  var headers = _batchSplitCounterfactualsHeaders_();
  var rowsOut = _buildBatchSplitCounterfactualRows_(generatedTs, source, warnings, _batchBaselineEvalCompareCoverageMap_(batchCompare));
  _sortBatchSplitCounterfactualRows_(headers, rowsOut);
  var sheet = getOrCreateBatchSplitCounterfactualsSheet_();
  var actualHeaders = ensureBatchSplitCounterfactualsHeaders_(sheet);
  _rewriteSheetRowsPreservingHeaders_(
    sheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );
  return {
    batch_split_counterfactuals_sheet: sheet.getName(),
    rows_written: rowsOut.length,
    warnings: _uniqueSortedStrings_(warnings)
  };
}

function buildBatchBaselineCoverageAudit_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var sources = {
    counterfactuals: _readFamilyStructureSource_('Batch_Split_Counterfactuals', warnings),
    ledger: _readFamilyStructureSource_('Outcome_Ledger', warnings),
    batchCompare: _readFamilyStructureSource_('Evaluation_BatchCompare', warnings)
  };
  var headers = _batchBaselineCoverageAuditHeaders_();
  var rowsOut = _buildBatchBaselineCoverageAuditRows_(generatedTs, sources, warnings);
  _sortBatchBaselineCoverageAuditRows_(headers, rowsOut);
  var sheet = getOrCreateBatchBaselineCoverageAuditSheet_();
  var actualHeaders = ensureBatchBaselineCoverageAuditHeaders_(sheet);
  _rewriteSheetRowsPreservingHeaders_(
    sheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );
  return {
    batch_baseline_coverage_audit_sheet: sheet.getName(),
    rows_written: rowsOut.length,
    warnings: _uniqueSortedStrings_(warnings)
  };
}

function buildBatchSplitGroupCounterfactuals_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var sources = {
    counterfactuals: _readFamilyStructureSource_('Batch_Split_Counterfactuals', warnings),
    ledger: _readFamilyStructureSource_('Outcome_Ledger', warnings)
  };
  var headers = _batchSplitGroupCounterfactualsHeaders_();
  var rowsOut = _buildBatchSplitGroupCounterfactualRows_(generatedTs, sources, warnings);
  _sortBatchSplitGroupCounterfactualRows_(headers, rowsOut);
  var sheet = getOrCreateBatchSplitGroupCounterfactualsSheet_();
  var actualHeaders = ensureBatchSplitGroupCounterfactualsHeaders_(sheet);
  _rewriteSheetRowsPreservingHeaders_(
    sheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowsOut)
  );
  return {
    batch_split_group_counterfactuals_sheet: sheet.getName(),
    rows_written: rowsOut.length,
    warnings: _uniqueSortedStrings_(warnings)
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

function _attentionFactorSummaryHeaders_() {
  return [
    'generated_ts',
    'summary_type',
    'scope',
    'scope_key',
    'outcome_family',
    'ai_name',
    'attention_factor',
    'attention_factor_rank',
    'factor_combo',
    'rows_total',
    'rows_scored',
    'full_hit_count',
    'partial_hit_count',
    'weak_fit_count',
    'miss_count',
    'overall_hit_count',
    'overall_hit_rate',
    'dir_hit_count',
    'dir_hit_rate',
    'avg_outcome_score',
    'attention_validity_ok_count',
    'attention_partial_count',
    'attention_missing_or_invalid_count',
    'diagnostic_note',
    'decision_support_note'
  ];
}

function _providerCharacterDiagnosticsHeaders_() {
  return _outcomeDiagnosticsHeaders_();
}

function _attentionProviderIndividualityHeaders_() {
  return [
    'generated_ts',
    'report_section',
    'scope',
    'scope_key',
    'provider',
    'event_family',
    'attention_factor',
    'row_count',
    'share_within_provider',
    'overall_share',
    'rank_within_provider',
    'share_within_provider_family',
    'rank_within_provider_family',
    'event_id',
    'batch_id',
    'type',
    'release_ts',
    'release_date',
    'indicator_name',
    'providers_present',
    'distinct_attention_factors_count',
    'all_same_factor',
    'partial_divergence',
    'full_divergence',
    'prediction_direction_diverged',
    'qualitative_result_diverged',
    'same_direction_different_factors_count',
    'different_direction_different_factors_count',
    'same_direction_same_factor_count',
    'different_direction_same_factor_count',
    'top_attention_factors',
    'top_family_attention_factors',
    'concentration_score',
    'individuality_label',
    'individuality_evidence',
    'performance_evidence_note',
    'diagnostic_note',
    'decision_support_note'
  ];
}

function _familyStructureReportHeaders_() {
  return [
    'generated_ts',
    'section',
    'scope',
    'scope_key',
    'source_sheet',
    'source_layer',
    'outcome_family',
    'event_family',
    'family',
    'family_combo_key',
    'batch_id',
    'event_id',
    'release_ts',
    'release_date',
    'country',
    'type',
    'provider_count',
    'row_count',
    'rows_scored',
    'member_count',
    'distinct_family_count',
    'batch_count',
    'total_member_count',
    'batch_prediction_count',
    'member_prediction_count',
    'member_event_ids',
    'member_indicator_names',
    'member_families',
    'is_mixed_family_batch',
    'has_low_signal_family',
    'has_clear_anchor',
    'batch_anchor_mode',
    'batch_anchor_confidence',
    'batch_anchor_event_id',
    'batch_anchor_indicator_name',
    'batch_anchor_margin',
    'dir_ok_rate',
    'mr_strength_ok_rate',
    'mr_sustain_ok_rate',
    'overall_ok_rate',
    'avg_realized_abs_pips',
    'avg_pred_abs_pips',
    'convergence_rate',
    'disagreement_rate',
    'batch_dir_ok_rate',
    'best_member_dir_ok_rate',
    'batch_overall_ok_rate',
    'best_member_overall_ok_rate',
    'batch_vs_best_member_delta',
    'best_member_event_id',
    'best_member_indicator_name',
    'best_member_family',
    'anchor_matches_best_member',
    'anchor_match_rate',
    'problematic_batch_count',
    'rule_or_finding',
    'affected_batches',
    'affected_events',
    'why_splitting_may_matter',
    'batch_prediction_result',
    'member_prediction_result',
    'evidence_summary',
    'recommended_next_question',
    'total_families_reviewed',
    'total_batches_reviewed',
    'mixed_family_batch_count',
    'mixed_family_batch_rate',
    'batch_underperformance_count',
    'anchor_mismatch_count',
    'strongest_family_rule_candidates',
    'strongest_batch_splitting_candidates',
    'recommendation_label',
    'diagnostic_label',
    'summary_note',
    'decision_support_note',
    'warnings'
  ];
}

function _batchSplittingCandidatesHeaders_() {
  return [
    'generated_ts',
    'candidate_rank',
    'candidate_priority',
    'candidate_key',
    'batch_id',
    'release_ts',
    'release_date',
    'family_combo_key',
    'member_families',
    'member_count',
    'distinct_family_count',
    'member_event_ids',
    'member_indicator_names',
    'is_mixed_family_batch',
    'has_low_signal_family',
    'best_member_outperformed_batch',
    'batch_prediction_result',
    'member_prediction_result',
    'batch_overall_ok_rate',
    'best_member_overall_ok_rate',
    'batch_vs_best_member_delta',
    'split_candidate_score',
    'split_reason',
    'repeated_combo_count',
    'combo_problematic_count',
    'combo_batch_dir_ok_rate',
    'combo_best_member_dir_ok_rate',
    'diagnostic_label',
    'recommended_next_question',
    'decision_support_note'
  ];
}

function _batchSplitCounterfactualsHeaders_() {
  return [
    'generated_ts',
    'counterfactual_rank',
    'counterfactual_id',
    'source_candidate_rank',
    'source_candidate_priority',
    'batch_id',
    'release_ts',
    'release_date',
    'family_combo_key',
    'member_families',
    'member_count',
    'distinct_family_count',
    'member_event_ids',
    'member_indicator_names',
    'baseline_method',
    'baseline_result_source',
    'baseline_batch_overall_ok_rate',
    'baseline_batch_result_available',
    'split_proxy_method',
    'split_proxy_result_source',
    'split_proxy_overall_ok_rate',
    'split_proxy_result_available',
    'counterfactual_delta',
    'counterfactual_result_label',
    'would_have_helped_flag',
    'would_have_hurt_flag',
    'inconclusive_flag',
    'split_reason',
    'repeated_combo_count',
    'combo_problematic_count',
    'evidence_strength',
    'activation_status',
    'activation_blocker',
    'decision_support_note'
  ];
}

function _batchBaselineCoverageAuditHeaders_() {
  return [
    'generated_ts',
    'row_type',
    'audit_rank',
    'batch_id',
    'release_ts',
    'family_combo_key',
    'source_counterfactual_label',
    'source_evidence_strength',
    'baseline_batch_result_available',
    'ledger_batch_row_count',
    'ledger_batch_provider_count',
    'ledger_batch_scored_count',
    'ledger_batch_overall_ok_count',
    'ledger_member_row_count',
    'ledger_member_scored_count',
    'evaluation_batch_compare_row_count',
    'evaluation_batch_compare_scored_count',
    'evaluation_batch_overall_ok_count',
    'member_proxy_available',
    'coverage_gap_label',
    'coverage_gap_detail',
    'recommended_next_step',
    'total_counterfactual_rows',
    'baseline_available_count',
    'missing_baseline_count',
    'missing_eval_compare_count',
    'ledger_unscored_batch_count',
    'missing_ledger_batch_count',
    'decision_support_note'
  ];
}

function _batchSplitGroupCounterfactualsHeaders_() {
  return [
    'generated_ts',
    'group_counterfactual_rank',
    'batch_id',
    'release_ts',
    'family_combo_key',
    'baseline_batch_overall_ok_rate',
    'best_member_proxy_overall_ok_rate',
    'best_family_group',
    'best_family_group_member_count',
    'best_family_group_scored_count',
    'best_family_group_overall_ok_rate',
    'best_family_group_event_ids',
    'best_family_group_indicator_names',
    'all_family_group_rates',
    'group_vs_batch_delta',
    'group_vs_best_member_delta',
    'counterfactual_result_label',
    'would_have_helped_flag',
    'possible_damage_flag',
    'evidence_strength',
    'activation_status',
    'activation_blocker',
    'decision_support_note'
  ];
}

function _attentionEvidenceReportHeaders_() {
  return [
    'generated_ts',
    'evidence_type',
    'scope',
    'scope_key',
    'outcome_family',
    'ai_name',
    'attention_factor',
    'factor_combo',
    'sample_size',
    'metric_name',
    'metric_value',
    'baseline_value',
    'lift_vs_baseline',
    'evidence_level',
    'evidence_summary',
    'recommended_next_step',
    'decision_support_note'
  ];
}

function _attentionBlockStabilityHeaders_() {
  return [
    'generated_ts',
    'diagnostic_type',
    'block_id',
    'block_label',
    'block_start_date',
    'block_end_date',
    'scope',
    'scope_key',
    'outcome_family',
    'ai_name',
    'attention_factor',
    'metric_name',
    'metric_value',
    'baseline_block_id',
    'baseline_value',
    'delta_vs_baseline',
    'rows_total',
    'rows_scored',
    'overall_hit_rate',
    'avg_outcome_score',
    'convergence_rate',
    'stability_level',
    'diagnostic_summary',
    'recommended_next_step',
    'decision_support_note'
  ];
}

function _attentionDisagreementReviewHeaders_() {
  return [
    'generated_ts',
    'review_type',
    'target_key',
    'release_date',
    'release_ts',
    'event_id',
    'batch_id',
    'type',
    'outcome_family',
    'indicator_name',
    'country',
    'provider_count',
    'provider_names',
    'direction_set',
    'strength_set',
    'pips_min',
    'pips_max',
    'pips_spread',
    'realized_pips',
    'mr_real_dir',
    'winner_provider',
    'winner_score',
    'score_spread',
    'disagreement_kind',
    'disagreement_level',
    'usefulness_label',
    'provider_score_detail',
    'provider_prediction_detail',
    'provider_attention_detail',
    'recommended_next_step',
    'decision_support_note'
  ];
}

function _attentionDisagreementSummaryHeaders_() {
  return [
    'generated_ts',
    'summary_type',
    'scope',
    'scope_key',
    'outcome_family',
    'winner_provider',
    'attention_factor',
    'disagreement_kind',
    'rows_total',
    'useful_disagreement_count',
    'possible_signal_count',
    'no_clear_winner_count',
    'unscored_or_thin_count',
    'high_disagreement_count',
    'avg_score_spread',
    'avg_pips_spread',
    'top_winner_provider',
    'top_attention_factor',
    'diagnostic_level',
    'diagnostic_summary',
    'recommended_next_step',
    'decision_support_note'
  ];
}

function _attentionPhase3CandidateHeaders_() {
  return [
    'generated_ts',
    'candidate_type',
    'candidate_key',
    'target_key',
    'release_date',
    'release_ts',
    'event_id',
    'batch_id',
    'type',
    'outcome_family',
    'indicator_name',
    'country',
    'winner_provider',
    'attention_factor',
    'disagreement_kind',
    'usefulness_label',
    'score_spread',
    'pips_spread',
    'evidence_rows',
    'useful_rows',
    'evidence_level',
    'candidate_summary',
    'future_experiment_hint',
    'status',
    'decision_support_note'
  ];
}

function _attentionShadowExperimentHeaders_() {
  return [
    'generated_ts',
    'experiment_id',
    'experiment_name',
    'experiment_version',
    'experiment_type',
    'rule_description',
    'source_scope',
    'event_id',
    'batch_id',
    'type',
    'release_ts',
    'release_date',
    'outcome_family',
    'indicator_name',
    'country',
    'provider_count',
    'candidate_provider',
    'candidate_factor',
    'candidate_factor_weight',
    'candidate_rule_triggered',
    'baseline_method',
    'baseline_provider',
    'baseline_outcome_score',
    'baseline_outcome_bucket',
    'candidate_outcome_score',
    'candidate_outcome_bucket',
    'candidate_vs_baseline_delta',
    'candidate_won_flag',
    'candidate_lost_flag',
    'candidate_tied_flag',
    'direction_changed_flag',
    'miss_avoided_flag',
    'severe_miss_created_flag',
    'shadow_signal_mode',
    'shadow_confidence_action',
    'shadow_behavior_note',
    'activation_status',
    'activation_blocker',
    'decision_support_note'
  ];
}

function _attentionShadowSummaryHeaders_() {
  return [
    'generated_ts',
    'experiment_name',
    'outcome_family',
    'candidate_provider',
    'candidate_factor',
    'rows_total',
    'rows_scored',
    'candidate_win_count',
    'candidate_loss_count',
    'candidate_tie_count',
    'candidate_win_rate',
    'avg_candidate_delta',
    'miss_avoided_count',
    'severe_miss_created_count',
    'activation_readiness',
    'activation_blocker',
    'decision_support_note'
  ];
}

function getOutcomeLedgerRowsForShadow_() {
  var ledgerSheet = getSheet('Outcome_Ledger');
  if (!ledgerSheet) {
    throw new Error('Outcome_Ledger sheet is required before building Attention_Shadow_Experiments.');
  }
  var ledgerHeaders = getHeaderNames(ledgerSheet);
  if (!ledgerHeaders || !ledgerHeaders.length) {
    throw new Error('Outcome_Ledger sheet is missing headers.');
  }
  return {
    rows: _readDataRows_(ledgerSheet),
    headers: ledgerHeaders,
    idx: _headerIndexMap_(ledgerHeaders)
  };
}

function groupOutcomeRowsForShadow_(rows, headerMap) {
  var groups = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i];
    var groupKey = _attentionShadowGroupKey_(row, headerMap);
    if (!groupKey) continue;
    if (!groups[groupKey]) groups[groupKey] = [];
    groups[groupKey].push(row);
  }
  return groups;
}

function extractAttentionFactorsFromOutcomeRow_(rowObj) {
  var out = [];
  for (var i = 1; i <= 3; i++) {
    var factor = String(rowObj['attention_factor_' + i] || '').trim();
    if (!factor) continue;
    out.push({
      factor: factor,
      weight: _numOrNull_(rowObj['attention_factor_' + i + '_weight']),
      rank: i
    });
  }
  return out;
}

function computeShadowBaselineForGroup_(groupRows, ledgerIdx) {
  var bestScore = null;
  var bestRow = null;
  var scoreSum = 0;
  var scoreCount = 0;
  for (var i = 0; i < (groupRows || []).length; i++) {
    var score = _numOrNull_(_predValue_(groupRows[i], ledgerIdx, 'outcome_score'));
    if (score == null) continue;
    scoreSum += score;
    scoreCount += 1;
    if (bestScore == null || score > bestScore) {
      bestScore = score;
      bestRow = groupRows[i];
    }
  }
  return {
    method: 'best_equal_provider_observed',
    provider_average_score: scoreCount ? _roundRate_(scoreSum / scoreCount) : null,
    baseline_provider: bestRow ? String(_predValue_(bestRow, ledgerIdx, 'ai_name') || '').trim() : '',
    baseline_outcome_score: bestScore,
    baseline_outcome_bucket: bestRow ? String(_predValue_(bestRow, ledgerIdx, 'outcome_bucket') || '').trim() : '',
    baseline_pred_dir: bestRow ? String(_predValue_(bestRow, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase() : ''
  };
}

function buildProviderFactorCandidateRows_(groupRows, ledgerIdx, baseline, generatedTs) {
  var rowsOut = [];
  var providerCount = _attentionShadowProviderCount_(groupRows, ledgerIdx);
  for (var i = 0; i < (groupRows || []).length; i++) {
    var row = groupRows[i];
    var factors = _attentionFactorsWithWeightsFromLedgerRow_(row, ledgerIdx);
    for (var f = 0; f < factors.length; f++) {
      rowsOut.push(_makeAttentionShadowExperimentRow_(generatedTs, {
        experiment_name: 'provider_factor_candidate',
        experiment_type: 'provider_selector_shadow',
        rule_description: 'Provider plus selected reasoning factor is compared against the best observed equal-provider row.',
        source_scope: 'outcome_ledger',
        source_row: row,
        ledger_idx: ledgerIdx,
        provider_count: providerCount,
        candidate_provider: String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim(),
        candidate_factor: factors[f].factor,
        candidate_factor_weight: factors[f].weight,
        candidate_rule_triggered: 'TRUE',
        baseline: baseline,
        candidate_score: _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score')),
        candidate_bucket: String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '').trim(),
        candidate_pred_dir: String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase(),
        shadow_behavior_note: 'Counterfactual provider-factor selector audit only.',
        activation_blocker: _isTrueCell_(_predValue_(row, ledgerIdx, 'scored_flag')) ? 'needs_more_future_blocks' : 'unscored_row'
      }));
    }
  }
  return rowsOut;
}

function buildDisagreementProviderSelectorRows_(groupRows, ledgerIdx, baseline, convergenceInfo, generatedTs) {
  var rowsOut = [];
  var providerCount = _attentionShadowProviderCount_(groupRows, ledgerIdx);
  var isDisagreement = _attentionShadowIsDisagreement_(groupRows, ledgerIdx, convergenceInfo);
  if (providerCount < 2 || !isDisagreement) return rowsOut;
  for (var i = 0; i < (groupRows || []).length; i++) {
    var row = groupRows[i];
    rowsOut.push(_makeAttentionShadowExperimentRow_(generatedTs, {
      experiment_name: 'disagreement_provider_selector',
      experiment_type: 'provider_selector_shadow',
      rule_description: 'Provider selection is tested only for observed provider disagreement groups.',
      source_scope: 'outcome_ledger_with_convergence',
      source_row: row,
      ledger_idx: ledgerIdx,
      provider_count: providerCount,
      candidate_provider: String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim(),
      candidate_factor: '',
      candidate_factor_weight: '',
      candidate_rule_triggered: 'TRUE',
      baseline: baseline,
      candidate_score: _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score')),
      candidate_bucket: String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '').trim(),
      candidate_pred_dir: String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase(),
      shadow_behavior_note: 'Observed disagreement selector audit only.',
      activation_blocker: 'needs_more_future_blocks'
    }));
  }
  return rowsOut;
}

function buildLowSignalWatchlistRows_(groupRows, ledgerIdx, generatedTs) {
  var rowsOut = [];
  var providerCount = _attentionShadowProviderCount_(groupRows, ledgerIdx);
  for (var i = 0; i < (groupRows || []).length; i++) {
    var row = groupRows[i];
    var lowSignal = _attentionShadowFactorMatch_(row, ledgerIdx, 'low_signal_event');
    if (!lowSignal) continue;
    var bucket = String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '').trim();
    rowsOut.push(_makeAttentionShadowExperimentRow_(generatedTs, {
      experiment_name: 'low_signal_watchlist_shadow',
      experiment_type: 'watchlist_shadow',
      rule_description: 'Selected low-signal factor is audited as a possible watchlist-only tag.',
      source_scope: 'outcome_ledger',
      source_row: row,
      ledger_idx: ledgerIdx,
      provider_count: providerCount,
      candidate_provider: String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim(),
      candidate_factor: lowSignal.factor,
      candidate_factor_weight: lowSignal.weight,
      candidate_rule_triggered: 'TRUE',
      baseline: { method: '', baseline_provider: '', baseline_outcome_score: null, baseline_outcome_bucket: '', baseline_pred_dir: '' },
      candidate_score: _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score')),
      candidate_bucket: bucket,
      candidate_pred_dir: String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase(),
      candidate_vs_baseline_delta: '',
      miss_avoided_flag: (bucket === 'miss' || bucket === 'weak_fit') ? 'TRUE' : 'FALSE',
      severe_miss_created_flag: 'FALSE',
      shadow_signal_mode: 'watchlist_only',
      shadow_behavior_note: 'Shadow watchlist tag would have reduced emphasis without changing direction.',
      activation_blocker: 'shadow_only_needs_more_blocks'
    }));
  }
  return rowsOut;
}

function buildHiddenDetailRiskConfidenceRows_(groupRows, ledgerIdx, generatedTs) {
  var rowsOut = [];
  var providerCount = _attentionShadowProviderCount_(groupRows, ledgerIdx);
  for (var i = 0; i < (groupRows || []).length; i++) {
    var row = groupRows[i];
    var hiddenRisk = _attentionShadowFactorMatch_(row, ledgerIdx, 'hidden_detail_risk');
    if (!hiddenRisk) continue;
    var bucket = String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '').trim();
    var note = 'Hidden-detail risk confidence audit only.';
    if (bucket === 'miss' || bucket === 'weak_fit') note = 'Risk flag may have been useful in a weak or missed outcome.';
    else if (bucket === 'full_hit') note = 'Risk flag would have been conservative despite a strong observed outcome.';
    rowsOut.push(_makeAttentionShadowExperimentRow_(generatedTs, {
      experiment_name: 'hidden_detail_risk_confidence_shadow',
      experiment_type: 'confidence_shadow',
      rule_description: 'Selected hidden-detail risk factor is audited as a possible confidence-reduction tag.',
      source_scope: 'outcome_ledger',
      source_row: row,
      ledger_idx: ledgerIdx,
      provider_count: providerCount,
      candidate_provider: String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim(),
      candidate_factor: hiddenRisk.factor,
      candidate_factor_weight: hiddenRisk.weight,
      candidate_rule_triggered: 'TRUE',
      baseline: { method: '', baseline_provider: '', baseline_outcome_score: null, baseline_outcome_bucket: '', baseline_pred_dir: '' },
      candidate_score: _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score')),
      candidate_bucket: bucket,
      candidate_pred_dir: String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase(),
      candidate_vs_baseline_delta: '',
      shadow_confidence_action: 'reduce_confidence_candidate',
      shadow_behavior_note: note,
      activation_blocker: 'shadow_only_needs_numeric_calibration'
    }));
  }
  return rowsOut;
}

function buildConvergenceNoWeightingRows_(groupRows, ledgerIdx, convergenceInfo, generatedTs) {
  var rowsOut = [];
  var level = String((convergenceInfo && convergenceInfo.convergence_level) || '').trim().toLowerCase();
  if (level !== 'high') return rowsOut;
  var first = (groupRows || [])[0];
  if (!first) return rowsOut;
  rowsOut.push(_makeAttentionShadowExperimentRow_(generatedTs, {
    experiment_name: 'convergence_no_weighting_shadow',
    experiment_type: 'convergence_shadow',
    rule_description: 'High provider convergence is audited as a reason to avoid provider-weighting claims.',
    source_scope: 'outcome_summary_convergence',
    source_row: first,
    ledger_idx: ledgerIdx,
    provider_count: _attentionShadowProviderCount_(groupRows, ledgerIdx),
    candidate_provider: '',
    candidate_factor: '',
    candidate_factor_weight: '',
    candidate_rule_triggered: 'TRUE',
    baseline: { method: '', baseline_provider: '', baseline_outcome_score: null, baseline_outcome_bucket: '', baseline_pred_dir: '' },
    candidate_score: null,
    candidate_bucket: '',
    candidate_pred_dir: '',
    candidate_vs_baseline_delta: '',
    shadow_behavior_note: 'high convergence; weighting likely adds fake precision',
    activation_blocker: 'high_convergence_weighting_not_recommended'
  }));
  return rowsOut;
}

function buildAttentionEvidenceReportRows_(summaryRows, summaryIdx, characterRows, characterIdx, generatedTs) {
  var rowsOut = [];
  var baseline = _attentionEvidenceBaseline_(summaryRows, summaryIdx);
  rowsOut = rowsOut.concat(_buildAttentionEvidenceCoverageRows_(summaryRows, summaryIdx, baseline, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceStrongFactorRows_(summaryRows, summaryIdx, baseline, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceWeakFactorRows_(summaryRows, summaryIdx, baseline, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceComboRows_(summaryRows, summaryIdx, baseline, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceFamilyRows_(summaryRows, summaryIdx, baseline, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceProviderCharacterRows_(characterRows, characterIdx, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionEvidenceReadinessRows_(summaryRows, summaryIdx, characterRows, characterIdx, baseline, generatedTs));
  return rowsOut;
}

function _attentionEvidenceBaseline_(summaryRows, summaryIdx) {
  var baseline = { rows_total: 0, rows_scored: 0, avg_outcome_score: null, overall_hit_rate: null, dir_hit_rate: null };
  for (var i = 0; i < (summaryRows || []).length; i++) {
    var row = summaryRows[i];
    if (String(_predValue_(row, summaryIdx, 'summary_type') || '').trim() !== 'global') continue;
    baseline.rows_total = _numOrNull_(_predValue_(row, summaryIdx, 'rows_total')) || 0;
    baseline.rows_scored = _numOrNull_(_predValue_(row, summaryIdx, 'rows_scored')) || 0;
    baseline.avg_outcome_score = _numOrNull_(_predValue_(row, summaryIdx, 'avg_outcome_score'));
    baseline.overall_hit_rate = _numOrNull_(_predValue_(row, summaryIdx, 'overall_hit_rate'));
    baseline.dir_hit_rate = _numOrNull_(_predValue_(row, summaryIdx, 'dir_hit_rate'));
    break;
  }
  return baseline;
}

function _buildAttentionEvidenceCoverageRows_(summaryRows, summaryIdx, baseline, generatedTs) {
  var rowsOut = [];
  var providerRows = _attentionEvidenceRowsByType_(summaryRows, summaryIdx, 'provider', 1);
  rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
    evidence_type: 'attention_coverage',
    scope: 'global',
    scope_key: 'all',
    sample_size: baseline.rows_total,
    metric_name: 'rows_scored',
    metric_value: baseline.rows_scored,
    baseline_value: '',
    lift_vs_baseline: '',
    evidence_level: baseline.rows_scored >= 1000 ? 'strong_sample' : (baseline.rows_scored >= 300 ? 'usable_sample' : 'thin_sample'),
    evidence_summary: 'Attention-era coverage is sufficient for diagnostic evidence, not automatic behavior changes.',
    recommended_next_step: 'Continue expanding attention-era samples before provider weighting or calibration.'
  }));
  for (var i = 0; i < providerRows.length; i++) {
    var r = providerRows[i];
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'provider_baseline',
      scope: 'provider',
      scope_key: r.ai_name,
      ai_name: r.ai_name,
      sample_size: r.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: r.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: _attentionEvidenceLift_(r.avg_outcome_score, baseline.avg_outcome_score),
      evidence_level: _attentionEvidenceLevel_(r.rows_total, _attentionEvidenceLift_(r.avg_outcome_score, baseline.avg_outcome_score), 0.20),
      evidence_summary: 'Provider baseline from attention-era rows.',
      recommended_next_step: 'Use as diagnostic context only; do not apply automatic provider weighting.'
    }));
  }
  return rowsOut;
}

function _buildAttentionEvidenceStrongFactorRows_(summaryRows, summaryIdx, baseline, generatedTs) {
  var rowsOut = [];
  var candidates = _attentionEvidenceRowsByType_(summaryRows, summaryIdx, 'factor_provider', 20);
  candidates.sort(function(a, b) {
    return _attentionEvidenceSortDesc_(a.avg_outcome_score, b.avg_outcome_score, a.rows_total, b.rows_total);
  });
  for (var i = 0; i < Math.min(12, candidates.length); i++) {
    var c = candidates[i];
    var lift = _attentionEvidenceLift_(c.avg_outcome_score, baseline.avg_outcome_score);
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'strong_factor_provider',
      scope: 'provider_factor',
      scope_key: c.scope_key,
      ai_name: c.ai_name,
      attention_factor: c.attention_factor,
      sample_size: c.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: c.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: lift,
      evidence_level: _attentionEvidenceLevel_(c.rows_total, lift, 0.30),
      evidence_summary: 'This provider-factor slice outperformed the attention-era baseline.',
      recommended_next_step: 'Keep monitoring as candidate evidence; do not turn it into weighting yet.'
    }));
  }
  return rowsOut;
}

function _buildAttentionEvidenceWeakFactorRows_(summaryRows, summaryIdx, baseline, generatedTs) {
  var rowsOut = [];
  var candidates = _attentionEvidenceRowsByType_(summaryRows, summaryIdx, 'factor_provider', 20);
  candidates.sort(function(a, b) {
    return _attentionEvidenceSortAsc_(a.avg_outcome_score, b.avg_outcome_score, a.rows_total, b.rows_total);
  });
  for (var i = 0; i < Math.min(10, candidates.length); i++) {
    var c = candidates[i];
    var lift = _attentionEvidenceLift_(c.avg_outcome_score, baseline.avg_outcome_score);
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'weak_factor_provider',
      scope: 'provider_factor',
      scope_key: c.scope_key,
      ai_name: c.ai_name,
      attention_factor: c.attention_factor,
      sample_size: c.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: c.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: lift,
      evidence_level: _attentionEvidenceLevel_(c.rows_total, lift, 0.30),
      evidence_summary: 'This provider-factor slice underperformed the attention-era baseline.',
      recommended_next_step: 'Use as a monitoring warning only; do not suppress this factor automatically.'
    }));
  }
  return rowsOut;
}

function _buildAttentionEvidenceComboRows_(summaryRows, summaryIdx, baseline, generatedTs) {
  var rowsOut = [];
  var candidates = _attentionEvidenceRowsByType_(summaryRows, summaryIdx, 'factor_combo', 10);
  candidates.sort(function(a, b) {
    return _attentionEvidenceSortDesc_(a.avg_outcome_score, b.avg_outcome_score, a.rows_total, b.rows_total);
  });
  for (var i = 0; i < Math.min(10, candidates.length); i++) {
    var c = candidates[i];
    var lift = _attentionEvidenceLift_(c.avg_outcome_score, baseline.avg_outcome_score);
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'strong_factor_combo',
      scope: 'factor_combo',
      scope_key: c.scope_key,
      factor_combo: c.factor_combo,
      sample_size: c.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: c.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: lift,
      evidence_level: _attentionEvidenceLevel_(c.rows_total, lift, 0.30),
      evidence_summary: 'This attention-factor combination outperformed the attention-era baseline.',
      recommended_next_step: 'Track this combination across more attention-era samples before using it for design decisions.'
    }));
  }
  return rowsOut;
}

function _buildAttentionEvidenceFamilyRows_(summaryRows, summaryIdx, baseline, generatedTs) {
  var rowsOut = [];
  var candidates = _attentionEvidenceRowsByType_(summaryRows, summaryIdx, 'factor_family', 20);
  candidates.sort(function(a, b) {
    return _attentionEvidenceSortDesc_(a.avg_outcome_score, b.avg_outcome_score, a.rows_total, b.rows_total);
  });
  for (var i = 0; i < Math.min(12, candidates.length); i++) {
    var c = candidates[i];
    var lift = _attentionEvidenceLift_(c.avg_outcome_score, baseline.avg_outcome_score);
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'family_factor_strength',
      scope: 'family_factor',
      scope_key: c.scope_key,
      outcome_family: c.outcome_family,
      attention_factor: c.attention_factor,
      sample_size: c.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: c.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: lift,
      evidence_level: _attentionEvidenceLevel_(c.rows_total, lift, 0.30),
      evidence_summary: 'This family-factor slice outperformed the attention-era baseline.',
      recommended_next_step: 'Treat as family-specific evidence for later review, not as a rule.'
    }));
  }
  candidates.sort(function(a, b) {
    return _attentionEvidenceSortAsc_(a.avg_outcome_score, b.avg_outcome_score, a.rows_total, b.rows_total);
  });
  for (var j = 0; j < Math.min(8, candidates.length); j++) {
    var w = candidates[j];
    var wLift = _attentionEvidenceLift_(w.avg_outcome_score, baseline.avg_outcome_score);
    rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'family_factor_weakness',
      scope: 'family_factor',
      scope_key: w.scope_key,
      outcome_family: w.outcome_family,
      attention_factor: w.attention_factor,
      sample_size: w.rows_total,
      metric_name: 'avg_outcome_score',
      metric_value: w.avg_outcome_score,
      baseline_value: baseline.avg_outcome_score,
      lift_vs_baseline: wLift,
      evidence_level: _attentionEvidenceLevel_(w.rows_total, wLift, 0.30),
      evidence_summary: 'This family-factor slice underperformed the attention-era baseline.',
      recommended_next_step: 'Monitor for repeated weakness before changing any process.'
    }));
  }
  return rowsOut;
}

function _buildAttentionEvidenceProviderCharacterRows_(characterRows, characterIdx, generatedTs) {
  var rowsOut = [];
  for (var i = 0; i < (characterRows || []).length; i++) {
    var row = characterRows[i];
    var type = String(_predValue_(row, characterIdx, 'diagnostic_type') || '').trim();
    var aiName = String(_predValue_(row, characterIdx, 'ai_name') || '').trim();
    var metricValue = _predValue_(row, characterIdx, 'metric_value');
    var detail = String(_predValue_(row, characterIdx, 'metric_detail') || '').trim();
    if (type === 'provider_attention_style') {
      rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
        evidence_type: 'provider_attention_style',
        scope: 'provider',
        scope_key: aiName,
        ai_name: aiName,
        attention_factor: metricValue,
        sample_size: _attentionEvidenceRowsTotalFromDetail_(detail),
        metric_name: 'top_attention_factor',
        metric_value: metricValue,
        evidence_level: 'observed',
        evidence_summary: 'Provider shows a repeatable attention-factor style.',
        recommended_next_step: 'Use this to understand provider character, not to assign provider roles.'
      }));
    } else if (type === 'unique_win_pattern') {
      rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
        evidence_type: 'provider_unique_win',
        scope: 'provider',
        scope_key: aiName,
        ai_name: aiName,
        sample_size: _attentionEvidenceDetailNumber_(detail, 'complete_targets'),
        metric_name: 'unique_win_count',
        metric_value: metricValue,
        evidence_level: Number(metricValue || 0) >= 10 ? 'notable' : 'emerging',
        evidence_summary: 'Provider uniquely outperformed peers on some complete target groups.',
        recommended_next_step: 'Study disagreement cases separately before considering later weighting.'
      }));
    } else if (type === 'tie_pattern' || type === 'convergence_character') {
      rowsOut.push(_makeAttentionEvidenceReportRow_(generatedTs, {
        evidence_type: type,
        scope: 'global',
        scope_key: 'all',
        sample_size: _attentionEvidenceDetailNumber_(detail, 'complete_targets'),
        metric_name: String(_predValue_(row, characterIdx, 'metric_name') || '').trim(),
        metric_value: metricValue,
        evidence_level: String(_predValue_(row, characterIdx, 'diagnostic_level') || '').trim(),
        evidence_summary: String(_predValue_(row, characterIdx, 'diagnostic_summary') || '').trim(),
        recommended_next_step: String(_predValue_(row, characterIdx, 'recommended_next_step') || '').trim()
      }));
    }
  }
  return rowsOut;
}

function _buildAttentionEvidenceReadinessRows_(summaryRows, summaryIdx, characterRows, characterIdx, baseline, generatedTs) {
  var mixedTargets = 0;
  var uniqueWins = 0;
  for (var i = 0; i < (characterRows || []).length; i++) {
    var row = characterRows[i];
    var type = String(_predValue_(row, characterIdx, 'diagnostic_type') || '').trim();
    var detail = String(_predValue_(row, characterIdx, 'metric_detail') || '').trim();
    if (type === 'tie_pattern') {
      mixedTargets = _attentionEvidenceDetailNumber_(detail, 'mixed_direction_targets');
      uniqueWins = _attentionEvidenceDetailNumber_(detail, 'unique_wins_on_mixed_direction');
    }
  }
  var readiness = 'not_ready';
  if (baseline.rows_scored >= 1000 && mixedTargets >= 100 && uniqueWins >= 50) readiness = 'ready_for_phase3_review';
  else if (baseline.rows_scored >= 500 && mixedTargets >= 50 && uniqueWins >= 20) readiness = 'partial';
  var nextStep = readiness === 'ready_for_phase3_review'
    ? 'Prepare a Phase 3 design review, but keep weighting and calibration disabled until explicitly approved.'
    : 'Collect more attention-era samples and review disagreement cases before Phase 3 design.';
  return [
    _makeAttentionEvidenceReportRow_(generatedTs, {
      evidence_type: 'phase3_readiness',
      scope: 'global',
      scope_key: 'all',
      sample_size: baseline.rows_scored,
      metric_name: 'readiness',
      metric_value: readiness,
      baseline_value: '',
      lift_vs_baseline: '',
      evidence_level: readiness,
      evidence_summary: 'Attention evidence is useful, but it remains a diagnostic layer and not a control layer.',
      recommended_next_step: nextStep
    })
  ];
}

function _attentionEvidenceRowsByType_(summaryRows, summaryIdx, summaryType, minRows) {
  var out = [];
  for (var i = 0; i < (summaryRows || []).length; i++) {
    var row = summaryRows[i];
    if (String(_predValue_(row, summaryIdx, 'summary_type') || '').trim() !== summaryType) continue;
    var rowsTotal = _numOrNull_(_predValue_(row, summaryIdx, 'rows_total')) || 0;
    if (rowsTotal < (minRows || 0)) continue;
    out.push({
      scope_key: String(_predValue_(row, summaryIdx, 'scope_key') || '').trim(),
      outcome_family: String(_predValue_(row, summaryIdx, 'outcome_family') || '').trim(),
      ai_name: String(_predValue_(row, summaryIdx, 'ai_name') || '').trim(),
      attention_factor: String(_predValue_(row, summaryIdx, 'attention_factor') || '').trim(),
      factor_combo: String(_predValue_(row, summaryIdx, 'factor_combo') || '').trim(),
      rows_total: rowsTotal,
      avg_outcome_score: _numOrNull_(_predValue_(row, summaryIdx, 'avg_outcome_score')),
      overall_hit_rate: _numOrNull_(_predValue_(row, summaryIdx, 'overall_hit_rate')),
      dir_hit_rate: _numOrNull_(_predValue_(row, summaryIdx, 'dir_hit_rate'))
    });
  }
  return out;
}

function _makeAttentionEvidenceReportRow_(generatedTs, attrs) {
  attrs = attrs || {};
  return [
    generatedTs,
    attrs.evidence_type || '',
    attrs.scope || '',
    attrs.scope_key || '',
    attrs.outcome_family || '',
    attrs.ai_name || '',
    attrs.attention_factor || '',
    attrs.factor_combo || '',
    attrs.sample_size === undefined ? '' : attrs.sample_size,
    attrs.metric_name || '',
    attrs.metric_value === undefined ? '' : attrs.metric_value,
    attrs.baseline_value === undefined ? '' : attrs.baseline_value,
    attrs.lift_vs_baseline === undefined ? '' : attrs.lift_vs_baseline,
    attrs.evidence_level || '',
    attrs.evidence_summary || '',
    attrs.recommended_next_step || '',
    'Evidence report only; not trading advice.'
  ];
}

function _attentionEvidenceLift_(value, baseline) {
  if (value === null || value === undefined || baseline === null || baseline === undefined) return '';
  return _roundRate_(Number(value) - Number(baseline));
}

function _attentionEvidenceLevel_(sampleSize, lift, threshold) {
  var n = Number(sampleSize || 0);
  var v = Number(lift || 0);
  if (n < 20) return 'low_sample';
  if (n >= 100 && v >= threshold) return 'strong_positive';
  if (n >= 100 && v <= -threshold) return 'strong_negative';
  if (v >= threshold) return 'emerging_positive';
  if (v <= -threshold) return 'emerging_negative';
  return 'neutral';
}

function _attentionEvidenceSortDesc_(aValue, bValue, aRows, bRows) {
  var a = aValue === null || aValue === undefined ? -999999 : Number(aValue);
  var b = bValue === null || bValue === undefined ? -999999 : Number(bValue);
  if (a !== b) return b - a;
  return Number(bRows || 0) - Number(aRows || 0);
}

function _attentionEvidenceSortAsc_(aValue, bValue, aRows, bRows) {
  var a = aValue === null || aValue === undefined ? 999999 : Number(aValue);
  var b = bValue === null || bValue === undefined ? 999999 : Number(bValue);
  if (a !== b) return a - b;
  return Number(bRows || 0) - Number(aRows || 0);
}

function _attentionEvidenceDetailNumber_(detail, key) {
  var re = new RegExp(String(key).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([0-9.]+)');
  var m = String(detail || '').match(re);
  return m ? Number(m[1]) : 0;
}

function _attentionEvidenceRowsTotalFromDetail_(detail) {
  return _attentionEvidenceDetailNumber_(detail, 'rows_total');
}

function buildAttentionBlockStabilityRows_(ledgerRows, ledgerIdx, generatedTs) {
  var blocks = _attentionBlockDefinitions_();
  var metricGroups = {};
  var targetGroups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    if (!_isAttentionEraLedgerRow_(row, ledgerIdx)) continue;
    var date = _ledgerReleaseDateString_(row, ledgerIdx);
    var block = _attentionBlockForDate_(date, blocks);
    if (!block) continue;

    var family = String(_predValue_(row, ledgerIdx, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim() || 'unknown_provider';
    var factors = _attentionFactorsFromLedgerRow_(row, ledgerIdx);
    var uniqueFactors = _uniqueStrings_(factors.map(function(f){ return f.factor; }));

    _addAttentionBlockMetricSample_(metricGroups, block, 'block_overview', 'block', block.block_id, '', '', '', row, ledgerIdx);
    _addAttentionBlockMetricSample_(metricGroups, block, 'provider_block_performance', 'provider', aiName, '', aiName, '', row, ledgerIdx);
    _addAttentionBlockMetricSample_(metricGroups, block, 'family_block_performance', 'family', family, family, '', '', row, ledgerIdx);
    for (var f = 0; f < uniqueFactors.length; f++) {
      var factor = uniqueFactors[f];
      _addAttentionBlockMetricSample_(metricGroups, block, 'attention_factor_block_performance', 'attention_factor', factor, '', '', factor, row, ledgerIdx);
      _addAttentionBlockMetricSample_(metricGroups, block, 'provider_factor_block_performance', 'provider_factor', aiName + '|' + factor, '', aiName, factor, row, ledgerIdx);
    }

    var targetKey = _providerCharacterTargetKey_(row, ledgerIdx);
    if (targetKey) {
      var fullTargetKey = block.block_id + '|' + targetKey;
      if (!targetGroups[fullTargetKey]) {
        targetGroups[fullTargetKey] = { block: block, rows: [] };
      }
      targetGroups[fullTargetKey].rows.push(row);
    }
  }

  var rowsOut = [];
  var metricSnapshots = {};
  Object.keys(metricGroups).sort().forEach(function(key) {
    var g = metricGroups[key];
    var rowOut = _makeAttentionBlockStabilityMetricRow_(generatedTs, g);
    rowsOut.push(rowOut);
    metricSnapshots[g.diagnostic_type + '|' + g.scope + '|' + g.scope_key + '|' + g.block.block_id] = {
      block: g.block,
      diagnostic_type: g.diagnostic_type,
      scope: g.scope,
      scope_key: g.scope_key,
      outcome_family: g.outcome_family,
      ai_name: g.ai_name,
      attention_factor: g.attention_factor,
      avg_outcome_score: g.score_count ? _roundRate_(g.score_sum / g.score_count) : null,
      overall_hit_rate: g.rows_scored ? _roundRate_(g.overall_hit_count / g.rows_scored) : null,
      rows_scored: g.rows_scored
    };
  });

  var convergenceRows = _buildAttentionBlockConvergenceRows_(targetGroups, ledgerIdx, generatedTs);
  rowsOut = rowsOut.concat(convergenceRows);
  rowsOut = rowsOut.concat(_buildAttentionBlockCrossBlockRows_(metricSnapshots, blocks, generatedTs));
  rowsOut = rowsOut.concat(_buildAttentionBlockReadinessRows_(metricSnapshots, convergenceRows, blocks, generatedTs));
  return rowsOut;
}

function _attentionBlockDefinitions_() {
  return [
    { block_id: 'nov_01_10_2024', label: 'Nov 1-10 2024', start: '2024-11-01', end: '2024-11-10' },
    { block_id: 'nov_11_15_2024', label: 'Nov 11-15 2024', start: '2024-11-11', end: '2024-11-15' },
    { block_id: 'nov_18_22_2024', label: 'Nov 18-22 2024', start: '2024-11-18', end: '2024-11-22' }
  ];
}

function _attentionBlockForDate_(dateString, blocks) {
  if (!dateString) return null;
  for (var i = 0; i < (blocks || []).length; i++) {
    var block = blocks[i];
    if (dateString >= block.start && dateString <= block.end) return block;
  }
  return null;
}

function _ledgerReleaseDateString_(row, idx) {
  var releaseDate = String(_predValue_(row, idx, 'release_date') || '').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(releaseDate)) return releaseDate;
  var releaseTs = _predValue_(row, idx, 'release_ts');
  if (!releaseTs) return '';
  var d = releaseTs instanceof Date ? releaseTs : new Date(releaseTs);
  if (isNaN(d.getTime())) return '';
  return d.toISOString().slice(0, 10);
}

function _addAttentionBlockMetricSample_(groups, block, diagnosticType, scope, scopeKey, family, aiName, factor, row, ledgerIdx) {
  var key = diagnosticType + '|' + block.block_id + '|' + scope + '|' + scopeKey;
  if (!groups[key]) {
    groups[key] = {
      block: block,
      diagnostic_type: diagnosticType,
      scope: scope,
      scope_key: scopeKey,
      outcome_family: family || '',
      ai_name: aiName || '',
      attention_factor: factor || '',
      rows_total: 0,
      rows_scored: 0,
      overall_hit_count: 0,
      score_sum: 0,
      score_count: 0
    };
  }
  var g = groups[key];
  var scored = _isTrueCell_(_predValue_(row, ledgerIdx, 'scored_flag'));
  var score = _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score'));
  g.rows_total += 1;
  if (scored) g.rows_scored += 1;
  if (scored && _isTrueCell_(_predValue_(row, ledgerIdx, 'overall_ok'))) g.overall_hit_count += 1;
  if (scored && score != null) {
    g.score_sum += score;
    g.score_count += 1;
  }
}

function _makeAttentionBlockStabilityMetricRow_(generatedTs, g) {
  var avgScore = g.score_count ? _roundRate_(g.score_sum / g.score_count) : '';
  var hitRate = _rateOrBlank_(g.overall_hit_count, g.rows_scored);
  var level = _attentionBlockMetricLevel_(g.rows_scored, avgScore, hitRate);
  return _makeAttentionBlockStabilityRow_(generatedTs, {
    diagnostic_type: g.diagnostic_type,
    block: g.block,
    scope: g.scope,
    scope_key: g.scope_key,
    outcome_family: g.outcome_family,
    ai_name: g.ai_name,
    attention_factor: g.attention_factor,
    metric_name: 'avg_outcome_score',
    metric_value: avgScore,
    rows_total: g.rows_total,
    rows_scored: g.rows_scored,
    overall_hit_rate: hitRate,
    avg_outcome_score: avgScore,
    stability_level: level,
    diagnostic_summary: 'Block-level observed outcome slice for stability comparison.',
    recommended_next_step: 'Compare this slice across blocks before drawing provider or factor conclusions.'
  });
}

function _attentionBlockMetricLevel_(rowsScored, avgScore, hitRate) {
  rowsScored = Number(rowsScored || 0);
  if (rowsScored < 10) return 'low_sample';
  var score = _numOrNull_(avgScore);
  var hit = _numOrNull_(hitRate);
  if ((score != null && score >= 2.2) || (hit != null && hit >= 0.35)) return 'strong_observed';
  if ((score != null && score <= 1.2) || (hit != null && hit <= 0.15)) return 'weak_observed';
  return 'mixed_observed';
}

function _buildAttentionBlockConvergenceRows_(targetGroups, ledgerIdx, generatedTs) {
  var groups = {};
  Object.keys(targetGroups || {}).forEach(function(key) {
    var target = targetGroups[key];
    var rows = target.rows || [];
    if (rows.length < 2) return;
    var firstFamily = String(_predValue_(rows[0], ledgerIdx, 'outcome_family') || '').trim() || 'other';
    var block = target.block;
    var dirMap = {};
    var strengthMap = {};
    for (var i = 0; i < rows.length; i++) {
      var dir = String(_predValue_(rows[i], ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase() || 'blank';
      var strength = String(_predValue_(rows[i], ledgerIdx, 'mr_pred_strength') || '').trim().toLowerCase() || 'blank';
      dirMap[dir] = (dirMap[dir] || 0) + 1;
      strengthMap[strength] = (strengthMap[strength] || 0) + 1;
    }
    var maxDir = _maxCount_(dirMap);
    var maxStrength = _maxCount_(strengthMap);
    var highConvergence = maxDir >= rows.length && maxStrength >= rows.length;
    _addAttentionBlockConvergenceSample_(groups, block, 'global', 'all', '', rows.length, highConvergence);
    _addAttentionBlockConvergenceSample_(groups, block, 'family', firstFamily, firstFamily, rows.length, highConvergence);
  });

  var rowsOut = [];
  Object.keys(groups).sort().forEach(function(key) {
    var g = groups[key];
    var rate = _rateOrBlank_(g.high_convergence_count, g.target_count);
    var level = 'low';
    if (_numOrZero_(rate) >= 0.70) level = 'high';
    else if (_numOrZero_(rate) >= 0.40) level = 'moderate';
    rowsOut.push(_makeAttentionBlockStabilityRow_(generatedTs, {
      diagnostic_type: 'convergence_block_risk',
      block: g.block,
      scope: g.scope,
      scope_key: g.scope_key,
      outcome_family: g.outcome_family,
      metric_name: 'high_convergence_rate',
      metric_value: rate,
      rows_total: g.target_count,
      rows_scored: g.target_count,
      convergence_rate: rate,
      stability_level: level,
      diagnostic_summary: 'Provider outputs show block-level direction/strength similarity for this scope.',
      recommended_next_step: 'Track whether convergence remains stable before changing provider framing.'
    }));
  });
  return rowsOut;
}

function _addAttentionBlockConvergenceSample_(groups, block, scope, scopeKey, family, providerCount, highConvergence) {
  var key = block.block_id + '|' + scope + '|' + scopeKey;
  if (!groups[key]) {
    groups[key] = {
      block: block,
      scope: scope,
      scope_key: scopeKey,
      outcome_family: family || '',
      target_count: 0,
      provider_row_count: 0,
      high_convergence_count: 0
    };
  }
  groups[key].target_count += 1;
  groups[key].provider_row_count += Number(providerCount || 0);
  if (highConvergence) groups[key].high_convergence_count += 1;
}

function _buildAttentionBlockCrossBlockRows_(metricSnapshots, blocks, generatedTs) {
  var rowsOut = [];
  if (!blocks || blocks.length < 2) return rowsOut;
  var baselineBlock = blocks[0];
  Object.keys(metricSnapshots || {}).sort().forEach(function(key) {
    var snap = metricSnapshots[key];
    if (!snap || !snap.block || snap.block.block_id === baselineBlock.block_id) return;
    var baseKey = snap.diagnostic_type + '|' + snap.scope + '|' + snap.scope_key + '|' + baselineBlock.block_id;
    var base = metricSnapshots[baseKey];
    if (!base) return;
    var delta = (snap.avg_outcome_score != null && base.avg_outcome_score != null)
      ? _roundRate_(snap.avg_outcome_score - base.avg_outcome_score)
      : '';
    var level = _attentionBlockDeltaLevel_(snap.rows_scored, base.rows_scored, delta);
    rowsOut.push(_makeAttentionBlockStabilityRow_(generatedTs, {
      diagnostic_type: 'cross_block_stability',
      block: snap.block,
      scope: snap.scope,
      scope_key: snap.scope_key,
      outcome_family: snap.outcome_family,
      ai_name: snap.ai_name,
      attention_factor: snap.attention_factor,
      metric_name: 'avg_outcome_score_delta',
      metric_value: delta,
      baseline_block_id: baselineBlock.block_id,
      baseline_value: base.avg_outcome_score != null ? base.avg_outcome_score : '',
      delta_vs_baseline: delta,
      rows_scored: snap.rows_scored,
      avg_outcome_score: snap.avg_outcome_score != null ? snap.avg_outcome_score : '',
      stability_level: level,
      diagnostic_summary: 'Cross-block score movement versus the first comparison block.',
      recommended_next_step: 'Treat movement as diagnostic evidence only until a third block confirms the pattern.'
    }));
  });
  return rowsOut;
}

function _attentionBlockDeltaLevel_(rowsScored, baselineRowsScored, delta) {
  if (Number(rowsScored || 0) < 10 || Number(baselineRowsScored || 0) < 10) return 'low_sample';
  var d = _numOrNull_(delta);
  if (d == null) return 'unknown';
  if (Math.abs(d) <= 0.20) return 'stable';
  if (d >= 0.50) return 'improved';
  if (d <= -0.50) return 'weakened';
  return 'shifted';
}

function _buildAttentionBlockReadinessRows_(metricSnapshots, convergenceRows, blocks, generatedTs) {
  var observedBlocks = {};
  Object.keys(metricSnapshots || {}).forEach(function(key) {
    var snap = metricSnapshots[key];
    if (snap && snap.block && Number(snap.rows_scored || 0) > 0) observedBlocks[snap.block.block_id] = true;
  });
  var observedCount = Object.keys(observedBlocks).length;
  var level = observedCount >= 3 ? 'ready' : (observedCount >= 2 ? 'partial' : 'not_ready');
  return [
    _makeAttentionBlockStabilityRow_(generatedTs, {
      diagnostic_type: 'readiness_next_block',
      block: blocks && blocks.length ? blocks[blocks.length - 1] : { block_id: '', label: '', start: '', end: '' },
      scope: 'global',
      scope_key: 'all',
      metric_name: 'observed_block_count',
      metric_value: observedCount,
      rows_total: (convergenceRows || []).length,
      stability_level: level,
      diagnostic_summary: observedCount >= 3
        ? 'Three observed blocks are available for stability review.'
        : 'A third observed block is still needed before treating factor/provider patterns as persistent.',
      recommended_next_step: observedCount >= 3
        ? 'Review repeated provider, family, factor, score, hit-rate, and convergence patterns.'
        : 'Backtest the next planned block, then rebuild this diagnostic.'
    })
  ];
}

function _makeAttentionBlockStabilityRow_(generatedTs, attrs) {
  attrs = attrs || {};
  var block = attrs.block || {};
  return [
    generatedTs,
    attrs.diagnostic_type || '',
    block.block_id || attrs.block_id || '',
    block.label || attrs.block_label || '',
    block.start || attrs.block_start_date || '',
    block.end || attrs.block_end_date || '',
    attrs.scope || '',
    attrs.scope_key || '',
    attrs.outcome_family || '',
    attrs.ai_name || '',
    attrs.attention_factor || '',
    attrs.metric_name || '',
    attrs.metric_value == null ? '' : attrs.metric_value,
    attrs.baseline_block_id || '',
    attrs.baseline_value == null ? '' : attrs.baseline_value,
    attrs.delta_vs_baseline == null ? '' : attrs.delta_vs_baseline,
    attrs.rows_total == null ? '' : attrs.rows_total,
    attrs.rows_scored == null ? '' : attrs.rows_scored,
    attrs.overall_hit_rate == null ? '' : attrs.overall_hit_rate,
    attrs.avg_outcome_score == null ? '' : attrs.avg_outcome_score,
    attrs.convergence_rate == null ? '' : attrs.convergence_rate,
    attrs.stability_level || '',
    attrs.diagnostic_summary || '',
    attrs.recommended_next_step || '',
    'Block stability diagnostic only; not trading advice.'
  ];
}

function buildAttentionDisagreementReviewRows_(ledgerRows, ledgerIdx, generatedTs) {
  var targetGroups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    if (!_isAttentionEraLedgerRow_(row, ledgerIdx)) continue;
    var targetKey = _providerCharacterTargetKey_(row, ledgerIdx);
    if (!targetKey) continue;
    if (!targetGroups[targetKey]) targetGroups[targetKey] = [];
    targetGroups[targetKey].push(row);
  }

  var rowsOut = [];
  Object.keys(targetGroups).sort().forEach(function(targetKey) {
    var rowOut = _makeAttentionDisagreementReviewRow_(generatedTs, targetKey, targetGroups[targetKey], ledgerIdx);
    if (rowOut) rowsOut.push(rowOut);
  });
  return rowsOut;
}

function _makeAttentionDisagreementReviewRow_(generatedTs, targetKey, rows, ledgerIdx) {
  var byProvider = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var aiName = String(_predValue_(rows[i], ledgerIdx, 'ai_name') || '').trim();
    if (aiName) byProvider[aiName] = rows[i];
  }
  var providers = Object.keys(byProvider).sort();
  if (providers.length < 2) return null;

  var first = byProvider[providers[0]];
  var dirMap = {};
  var strengthMap = {};
  var pipsValues = [];
  var scores = [];
  var scoredCount = 0;
  var bestScore = null;
  var winnerProviders = [];

  for (var p = 0; p < providers.length; p++) {
    var provider = providers[p];
    var row = byProvider[provider];
    var dir = String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
    var strength = String(_predValue_(row, ledgerIdx, 'mr_pred_strength') || '').trim().toLowerCase();
    var pips = _numOrNull_(_predValue_(row, ledgerIdx, 'mr_pred_net_pips'));
    var score = _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score'));
    if (dir) dirMap[dir] = true;
    if (strength) strengthMap[strength] = true;
    if (pips != null) pipsValues.push(pips);
    if (_isTrueCell_(_predValue_(row, ledgerIdx, 'scored_flag'))) scoredCount += 1;
    if (score != null) {
      scores.push(score);
      if (bestScore == null || score > bestScore) {
        bestScore = score;
        winnerProviders = [provider];
      } else if (score === bestScore) {
        winnerProviders.push(provider);
      }
    }
  }

  var dirs = Object.keys(dirMap).sort();
  var strengths = Object.keys(strengthMap).sort();
  var pipsMin = pipsValues.length ? Math.min.apply(null, pipsValues) : null;
  var pipsMax = pipsValues.length ? Math.max.apply(null, pipsValues) : null;
  var pipsSpread = (pipsMin != null && pipsMax != null) ? _roundRate_(pipsMax - pipsMin) : null;
  var directionDisagreement = dirs.length > 1;
  var strengthDisagreement = strengths.length > 1;
  var pipsDisagreement = pipsSpread != null && pipsSpread >= 5;
  if (!directionDisagreement && !strengthDisagreement && !pipsDisagreement) return null;

  var scoreSpread = '';
  if (scores.length) {
    scoreSpread = _roundRate_(Math.max.apply(null, scores) - Math.min.apply(null, scores));
  }
  var winnerProvider = winnerProviders.length === 1 ? winnerProviders[0] : (winnerProviders.length ? 'tie' : '');
  var usefulness = _attentionDisagreementUsefulnessLabel_(scoredCount, winnerProvider, scoreSpread);
  var disagreementKind = _attentionDisagreementKind_(directionDisagreement, strengthDisagreement, pipsDisagreement);
  var level = _attentionDisagreementLevel_(directionDisagreement, strengthDisagreement, pipsSpread, scoreSpread);

  return [
    generatedTs,
    'case_review',
    targetKey,
    String(_predValue_(first, ledgerIdx, 'release_date') || ''),
    String(_predValue_(first, ledgerIdx, 'release_ts') || ''),
    String(_predValue_(first, ledgerIdx, 'event_id') || ''),
    String(_predValue_(first, ledgerIdx, 'batch_id') || ''),
    String(_predValue_(first, ledgerIdx, 'type') || ''),
    String(_predValue_(first, ledgerIdx, 'outcome_family') || '') || 'other',
    String(_predValue_(first, ledgerIdx, 'indicator_name') || ''),
    String(_predValue_(first, ledgerIdx, 'country') || ''),
    providers.length,
    providers.join(', '),
    dirs.join(', '),
    strengths.join(', '),
    pipsMin == null ? '' : pipsMin,
    pipsMax == null ? '' : pipsMax,
    pipsSpread == null ? '' : pipsSpread,
    _firstNonBlankProviderValue_(providers, byProvider, ledgerIdx, 'realized_pips'),
    _firstNonBlankProviderValue_(providers, byProvider, ledgerIdx, 'mr_real_dir'),
    winnerProvider,
    bestScore == null ? '' : bestScore,
    scoreSpread,
    disagreementKind,
    level,
    usefulness,
    _attentionProviderScoreDetail_(providers, byProvider, ledgerIdx),
    _attentionProviderPredictionDetail_(providers, byProvider, ledgerIdx),
    _attentionProviderFactorDetail_(providers, byProvider, ledgerIdx),
    _attentionDisagreementRecommendedNextStep_(usefulness),
    'Disagreement review is diagnostic only; not trading advice.'
  ];
}

function _attentionDisagreementKind_(directionDisagreement, strengthDisagreement, pipsDisagreement) {
  var parts = [];
  if (directionDisagreement) parts.push('direction');
  if (strengthDisagreement) parts.push('strength');
  if (pipsDisagreement) parts.push('pips');
  return parts.join('+') || 'none';
}

function _attentionDisagreementLevel_(directionDisagreement, strengthDisagreement, pipsSpread, scoreSpread) {
  var scoreGap = _numOrNull_(scoreSpread);
  if (directionDisagreement && (scoreGap == null || scoreGap >= 2)) return 'high';
  if (directionDisagreement || strengthDisagreement || Number(pipsSpread || 0) >= 10) return 'moderate';
  return 'low';
}

function _attentionDisagreementUsefulnessLabel_(scoredCount, winnerProvider, scoreSpread) {
  if (Number(scoredCount || 0) < 2) return 'unscored_or_thin';
  var gap = _numOrNull_(scoreSpread);
  if (winnerProvider && winnerProvider !== 'tie' && gap != null && gap >= 2) return 'useful_disagreement';
  if (winnerProvider && winnerProvider !== 'tie' && gap != null && gap >= 1) return 'possible_signal';
  if (winnerProvider === 'tie') return 'no_clear_winner';
  return 'noisy_or_small_gap';
}

function _attentionDisagreementRecommendedNextStep_(usefulness) {
  if (usefulness === 'useful_disagreement') {
    return 'Review repeated factor/provider patterns in similar disagreement cases before any later weighting discussion.';
  }
  if (usefulness === 'possible_signal') {
    return 'Keep as candidate evidence and compare against future disagreement cases.';
  }
  if (usefulness === 'unscored_or_thin') {
    return 'Improve scoring coverage before learning from this disagreement case.';
  }
  return 'Treat as audit context only; do not change provider roles or prediction logic.';
}

function _firstNonBlankProviderValue_(providers, byProvider, ledgerIdx, key) {
  for (var i = 0; i < (providers || []).length; i++) {
    var v = _predValue_(byProvider[providers[i]], ledgerIdx, key);
    if (v !== '' && v !== null && v !== undefined) return v;
  }
  return '';
}

function _attentionProviderScoreDetail_(providers, byProvider, ledgerIdx) {
  return (providers || []).map(function(provider) {
    var row = byProvider[provider];
    return provider + ':score=' + String(_predValue_(row, ledgerIdx, 'outcome_score') || '') +
      ',bucket=' + String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '') +
      ',dir_ok=' + String(_predValue_(row, ledgerIdx, 'mr_dir_ok') || '') +
      ',overall_ok=' + String(_predValue_(row, ledgerIdx, 'overall_ok') || '');
  }).join(' | ');
}

function _attentionProviderPredictionDetail_(providers, byProvider, ledgerIdx) {
  return (providers || []).map(function(provider) {
    var row = byProvider[provider];
    return provider + ':dir=' + String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '') +
      ',pips=' + String(_predValue_(row, ledgerIdx, 'mr_pred_net_pips') || '') +
      ',strength=' + String(_predValue_(row, ledgerIdx, 'mr_pred_strength') || '') +
      ',sustain=' + String(_predValue_(row, ledgerIdx, 'mr_pred_sustain_min') || '');
  }).join(' | ');
}

function _attentionProviderFactorDetail_(providers, byProvider, ledgerIdx) {
  return (providers || []).map(function(provider) {
    var factors = _attentionFactorsFromLedgerRow_(byProvider[provider], ledgerIdx).map(function(f) {
      return f.factor;
    });
    return provider + ':' + factors.join('+');
  }).join(' | ');
}

function buildAttentionDisagreementSummaryRows_(reviewRows, reviewIdx, generatedTs) {
  var groups = {};
  for (var i = 0; i < (reviewRows || []).length; i++) {
    var row = reviewRows[i];
    var family = String(_predValue_(row, reviewIdx, 'outcome_family') || '').trim() || 'other';
    var winner = String(_predValue_(row, reviewIdx, 'winner_provider') || '').trim();
    var kind = String(_predValue_(row, reviewIdx, 'disagreement_kind') || '').trim() || 'unknown';
    var usefulness = String(_predValue_(row, reviewIdx, 'usefulness_label') || '').trim() || 'unknown';
    var winnerFactors = _attentionDisagreementWinnerFactors_(row, reviewIdx);

    _addAttentionDisagreementSummarySample_(groups, 'global', 'global', 'all', '', '', '', '', row, reviewIdx);
    _addAttentionDisagreementSummarySample_(groups, 'family', 'family', family, family, '', '', '', row, reviewIdx);
    _addAttentionDisagreementSummarySample_(groups, 'disagreement_kind', 'kind', kind, '', '', '', kind, row, reviewIdx);
    _addAttentionDisagreementSummarySample_(groups, 'usefulness', 'usefulness', usefulness, '', '', '', '', row, reviewIdx);
    if (winner && winner !== 'tie') {
      _addAttentionDisagreementSummarySample_(groups, 'winner_provider', 'provider', winner, '', winner, '', '', row, reviewIdx);
      _addAttentionDisagreementSummarySample_(groups, 'family_winner', 'family_provider', family + '|' + winner, family, winner, '', '', row, reviewIdx);
      for (var f = 0; f < winnerFactors.length; f++) {
        var factor = winnerFactors[f];
        _addAttentionDisagreementSummarySample_(groups, 'winner_factor', 'provider_factor', winner + '|' + factor, '', winner, factor, '', row, reviewIdx);
        _addAttentionDisagreementSummarySample_(groups, 'family_winner_factor', 'family_provider_factor', family + '|' + winner + '|' + factor, family, winner, factor, '', row, reviewIdx);
      }
    }
  }

  var rowsOut = [];
  Object.keys(groups).sort().forEach(function(key) {
    rowsOut.push(_makeAttentionDisagreementSummaryRow_(generatedTs, groups[key]));
  });
  return rowsOut;
}

function _addAttentionDisagreementSummarySample_(groups, summaryType, scope, scopeKey, family, winner, factor, kind, row, reviewIdx) {
  var key = summaryType + '|' + scope + '|' + scopeKey;
  if (!groups[key]) {
    groups[key] = {
      summary_type: summaryType,
      scope: scope,
      scope_key: scopeKey,
      outcome_family: family || '',
      winner_provider: winner || '',
      attention_factor: factor || '',
      disagreement_kind: kind || '',
      rows_total: 0,
      useful_disagreement_count: 0,
      possible_signal_count: 0,
      no_clear_winner_count: 0,
      unscored_or_thin_count: 0,
      high_disagreement_count: 0,
      score_spread_sum: 0,
      score_spread_count: 0,
      pips_spread_sum: 0,
      pips_spread_count: 0,
      winners: {},
      factors: {}
    };
  }
  var g = groups[key];
  var usefulness = String(_predValue_(row, reviewIdx, 'usefulness_label') || '').trim();
  var level = String(_predValue_(row, reviewIdx, 'disagreement_level') || '').trim();
  var rowWinner = String(_predValue_(row, reviewIdx, 'winner_provider') || '').trim();
  var scoreSpread = _numOrNull_(_predValue_(row, reviewIdx, 'score_spread'));
  var pipsSpread = _numOrNull_(_predValue_(row, reviewIdx, 'pips_spread'));
  var winnerFactors = _attentionDisagreementWinnerFactors_(row, reviewIdx);

  g.rows_total += 1;
  if (usefulness === 'useful_disagreement') g.useful_disagreement_count += 1;
  else if (usefulness === 'possible_signal') g.possible_signal_count += 1;
  else if (usefulness === 'no_clear_winner') g.no_clear_winner_count += 1;
  else if (usefulness === 'unscored_or_thin') g.unscored_or_thin_count += 1;
  if (level === 'high') g.high_disagreement_count += 1;
  if (scoreSpread != null) {
    g.score_spread_sum += scoreSpread;
    g.score_spread_count += 1;
  }
  if (pipsSpread != null) {
    g.pips_spread_sum += pipsSpread;
    g.pips_spread_count += 1;
  }
  if (rowWinner) g.winners[rowWinner] = (g.winners[rowWinner] || 0) + 1;
  for (var i = 0; i < winnerFactors.length; i++) {
    var f = winnerFactors[i];
    g.factors[f] = (g.factors[f] || 0) + 1;
  }
}

function _makeAttentionDisagreementSummaryRow_(generatedTs, g) {
  var topWinner = _topCountMapItems_(g.winners, 1);
  var topFactor = _topCountMapItems_(g.factors, 1);
  var usefulRate = _rateRaw_(g.useful_disagreement_count + g.possible_signal_count, g.rows_total);
  var level = 'observed';
  if (g.rows_total < 5) level = 'low_sample';
  else if (usefulRate >= 0.50) level = 'useful_pattern';
  else if (g.no_clear_winner_count >= g.rows_total * 0.50) level = 'mostly_tied';
  else if (g.unscored_or_thin_count >= g.rows_total * 0.50) level = 'thin_scoring';

  return [
    generatedTs,
    g.summary_type,
    g.scope,
    g.scope_key,
    g.outcome_family,
    g.winner_provider,
    g.attention_factor,
    g.disagreement_kind,
    g.rows_total,
    g.useful_disagreement_count,
    g.possible_signal_count,
    g.no_clear_winner_count,
    g.unscored_or_thin_count,
    g.high_disagreement_count,
    g.score_spread_count ? _roundRate_(g.score_spread_sum / g.score_spread_count) : '',
    g.pips_spread_count ? _roundRate_(g.pips_spread_sum / g.pips_spread_count) : '',
    topWinner.length ? topWinner[0].key : '',
    topFactor.length ? topFactor[0].key : '',
    level,
    'Derived summary of provider disagreement review cases.',
    _attentionDisagreementSummaryNextStep_(level),
    'Disagreement summary is diagnostic only; not trading advice.'
  ];
}

function _attentionDisagreementSummaryNextStep_(level) {
  if (level === 'useful_pattern') return 'Review repeated family/provider/factor slices before any later weighting discussion.';
  if (level === 'mostly_tied') return 'Treat as convergence evidence; inspect only cases with clear score separation.';
  if (level === 'thin_scoring') return 'Improve scoring coverage before drawing conclusions from this slice.';
  if (level === 'low_sample') return 'Collect more disagreement cases before interpreting this slice.';
  return 'Use as audit context only; do not change provider roles or prediction logic.';
}

function _attentionDisagreementWinnerFactors_(row, reviewIdx) {
  var winner = String(_predValue_(row, reviewIdx, 'winner_provider') || '').trim();
  if (!winner || winner === 'tie') return [];
  var detail = String(_predValue_(row, reviewIdx, 'provider_attention_detail') || '');
  var parts = detail.split(' | ');
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    var sep = part.indexOf(':');
    if (sep < 0) continue;
    var provider = part.slice(0, sep).trim();
    if (provider !== winner) continue;
    return _uniqueStrings_(part.slice(sep + 1).split('+').map(function(f) {
      return String(f || '').trim();
    }));
  }
  return [];
}

function _maxCount_(map) {
  var best = 0;
  Object.keys(map || {}).forEach(function(key) {
    best = Math.max(best, Number(map[key] || 0));
  });
  return best;
}

function buildAttentionFactorSummaryRows_(ledgerRows, ledgerIdx, generatedTs) {
  var groups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    if (!_isAttentionEraLedgerRow_(row, ledgerIdx)) continue;
    var family = String(_predValue_(row, ledgerIdx, 'outcome_family') || '').trim() || 'other';
    var aiName = String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim();
    var factors = _attentionFactorsFromLedgerRow_(row, ledgerIdx);
    var uniqueFactors = _uniqueStrings_(factors.map(function(f){ return f.factor; }));
    var combo = uniqueFactors.slice().sort().join(' + ');
    var validity = String(_predValue_(row, ledgerIdx, 'attention_validity_flag') || '').trim().toLowerCase();

    _addAttentionFactorSummarySample_(groups, 'global', 'global', 'all', '', '', '', '', '', row, ledgerIdx, validity);
    _addAttentionFactorSummarySample_(groups, 'provider', 'provider', aiName || 'unknown_provider', '', aiName, '', '', '', row, ledgerIdx, validity);
    _addAttentionFactorSummarySample_(groups, 'family', 'family', family, family, '', '', '', '', row, ledgerIdx, validity);
    if (combo) _addAttentionFactorSummarySample_(groups, 'factor_combo', 'combo', combo, '', '', '', '', combo, row, ledgerIdx, validity);

    var countedFactors = {};
    for (var f = 0; f < factors.length; f++) {
      var factor = factors[f].factor;
      var rank = String(factors[f].rank);
      if (!countedFactors[factor]) {
        countedFactors[factor] = true;
        _addAttentionFactorSummarySample_(groups, 'factor_provider', 'provider_factor', aiName + '|' + factor, '', aiName, factor, '', '', row, ledgerIdx, validity);
        _addAttentionFactorSummarySample_(groups, 'factor_family', 'family_factor', family + '|' + factor, family, '', factor, '', '', row, ledgerIdx, validity);
        _addAttentionFactorSummarySample_(groups, 'factor_provider_family', 'provider_family_factor', family + '|' + aiName + '|' + factor, family, aiName, factor, '', '', row, ledgerIdx, validity);
      }
      _addAttentionFactorSummarySample_(groups, 'factor_rank', 'factor_rank', rank + '|' + factor, '', '', factor, rank, '', row, ledgerIdx, validity);
    }
  }

  var rowsOut = [];
  Object.keys(groups).forEach(function(key) {
    var g = groups[key];
    rowsOut.push(_makeAttentionFactorSummaryRow_(generatedTs, g));
  });
  return rowsOut;
}

function _addAttentionFactorSummarySample_(groups, summaryType, scope, scopeKey, family, aiName, factor, factorRank, combo, row, ledgerIdx, validity) {
  var key = summaryType + '|' + scope + '|' + scopeKey;
  if (!groups[key]) {
    groups[key] = {
      summary_type: summaryType,
      scope: scope,
      scope_key: scopeKey,
      outcome_family: family || '',
      ai_name: aiName || '',
      attention_factor: factor || '',
      attention_factor_rank: factorRank || '',
      factor_combo: combo || '',
      rows_total: 0,
      rows_scored: 0,
      full_hit_count: 0,
      partial_hit_count: 0,
      weak_fit_count: 0,
      miss_count: 0,
      overall_hit_count: 0,
      dir_hit_count: 0,
      outcome_score_sum: 0,
      outcome_score_count: 0,
      attention_validity_ok_count: 0,
      attention_partial_count: 0,
      attention_missing_or_invalid_count: 0
    };
  }
  var g = groups[key];
  var scored = _isTrueCell_(_predValue_(row, ledgerIdx, 'scored_flag'));
  var bucket = String(_predValue_(row, ledgerIdx, 'outcome_bucket') || '').trim();
  var score = _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score'));
  g.rows_total += 1;
  if (scored) g.rows_scored += 1;
  if (bucket === 'full_hit') g.full_hit_count += 1;
  else if (bucket === 'partial_hit') g.partial_hit_count += 1;
  else if (bucket === 'weak_fit') g.weak_fit_count += 1;
  else if (bucket === 'miss') g.miss_count += 1;
  if (scored && _isTrueCell_(_predValue_(row, ledgerIdx, 'overall_ok'))) g.overall_hit_count += 1;
  if (scored && _isTrueCell_(_predValue_(row, ledgerIdx, 'mr_dir_ok'))) g.dir_hit_count += 1;
  if (scored && score != null) {
    g.outcome_score_sum += score;
    g.outcome_score_count += 1;
  }
  if (validity === 'ok') g.attention_validity_ok_count += 1;
  else if (validity === 'partial') g.attention_partial_count += 1;
  else g.attention_missing_or_invalid_count += 1;
}

function _makeAttentionFactorSummaryRow_(generatedTs, g) {
  return [
    generatedTs,
    g.summary_type,
    g.scope,
    g.scope_key,
    g.outcome_family,
    g.ai_name,
    g.attention_factor,
    g.attention_factor_rank,
    g.factor_combo,
    g.rows_total,
    g.rows_scored,
    g.full_hit_count,
    g.partial_hit_count,
    g.weak_fit_count,
    g.miss_count,
    g.overall_hit_count,
    _rateOrBlank_(g.overall_hit_count, g.rows_scored),
    g.dir_hit_count,
    _rateOrBlank_(g.dir_hit_count, g.rows_scored),
    g.outcome_score_count ? _roundRate_(g.outcome_score_sum / g.outcome_score_count) : '',
    g.attention_validity_ok_count,
    g.attention_partial_count,
    g.attention_missing_or_invalid_count,
    'Derived attention-factor audit only; does not control prediction outputs.',
    'Attention-factor analysis only; not trading advice.'
  ];
}

function buildProviderCharacterDiagnosticsRows_(ledgerRows, ledgerIdx, generatedTs) {
  var rowsOut = [];
  var providerStats = {};
  var providerFamilyStats = {};
  var targetGroups = {};
  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    if (!_isAttentionEraLedgerRow_(row, ledgerIdx)) continue;
    var aiName = String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim();
    var family = String(_predValue_(row, ledgerIdx, 'outcome_family') || '').trim() || 'other';
    if (!aiName) continue;
    _addProviderCharacterSample_(providerStats, aiName, aiName, '', row, ledgerIdx);
    _addProviderCharacterSample_(providerFamilyStats, family + '|' + aiName, aiName, family, row, ledgerIdx);

    var targetKey = _providerCharacterTargetKey_(row, ledgerIdx);
    if (!targetKey) continue;
    if (!targetGroups[targetKey]) targetGroups[targetKey] = [];
    targetGroups[targetKey].push(row);
  }

  Object.keys(providerStats).sort().forEach(function(key) {
    rowsOut.push(_makeProviderPerformanceDiagnosticRow_(generatedTs, providerStats[key], 'provider_performance_profile', 'provider', key));
    rowsOut.push(_makeProviderAttentionStyleRow_(generatedTs, providerStats[key], 'provider_attention_style', 'provider', key));
  });

  Object.keys(providerFamilyStats).sort().forEach(function(key) {
    rowsOut.push(_makeProviderPerformanceDiagnosticRow_(generatedTs, providerFamilyStats[key], 'provider_family_profile', 'provider_family', key));
  });

  rowsOut = rowsOut.concat(_buildProviderUniqueWinDiagnostics_(targetGroups, ledgerIdx, generatedTs));
  rowsOut = rowsOut.concat(_buildProviderConvergenceCharacterRows_(targetGroups, ledgerIdx, generatedTs));
  return rowsOut;
}

function _addProviderCharacterSample_(groups, key, aiName, family, row, ledgerIdx) {
  if (!groups[key]) {
    groups[key] = {
      ai_name: aiName,
      outcome_family: family || '',
      rows_total: 0,
      rows_scored: 0,
      overall_hit_count: 0,
      dir_hit_count: 0,
      score_sum: 0,
      score_count: 0,
      dirs: {},
      strengths: {},
      factors: {}
    };
  }
  var g = groups[key];
  var scored = _isTrueCell_(_predValue_(row, ledgerIdx, 'scored_flag'));
  var score = _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score'));
  var predDir = String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase() || 'blank';
  var predStrength = String(_predValue_(row, ledgerIdx, 'mr_pred_strength') || '').trim().toLowerCase() || 'blank';
  g.rows_total += 1;
  if (scored) g.rows_scored += 1;
  if (scored && _isTrueCell_(_predValue_(row, ledgerIdx, 'overall_ok'))) g.overall_hit_count += 1;
  if (scored && _isTrueCell_(_predValue_(row, ledgerIdx, 'mr_dir_ok'))) g.dir_hit_count += 1;
  if (scored && score != null) {
    g.score_sum += score;
    g.score_count += 1;
  }
  g.dirs[predDir] = (g.dirs[predDir] || 0) + 1;
  g.strengths[predStrength] = (g.strengths[predStrength] || 0) + 1;
  var factors = _attentionFactorsFromLedgerRow_(row, ledgerIdx);
  for (var i = 0; i < factors.length; i++) {
    var factor = factors[i].factor;
    g.factors[factor] = (g.factors[factor] || 0) + 1;
  }
}

function _makeProviderPerformanceDiagnosticRow_(generatedTs, g, diagnosticType, scope, scopeKey) {
  var flatRate = _rateRaw_(g.dirs.flat || 0, g.rows_total);
  var weakRate = _rateRaw_(g.strengths.weak || 0, g.rows_total);
  var level = 'balanced';
  if (flatRate >= 0.90 && weakRate >= 0.90) level = 'conservative';
  else if ((g.dirs.up || 0) + (g.dirs.down || 0) >= g.rows_total * 0.20) level = 'directional';
  return _makeProviderCharacterDiagnosticRow_(generatedTs, {
    diagnostic_type: diagnosticType,
    scope: scope,
    scope_key: scopeKey,
    outcome_family: g.outcome_family,
    ai_name: g.ai_name,
    metric_name: 'provider_character_profile',
    metric_value: level,
    metric_detail: 'rows_total=' + g.rows_total +
      '; rows_scored=' + g.rows_scored +
      '; overall_hit_rate=' + _fmtDiagMetric_(_rateRaw_(g.overall_hit_count, g.rows_scored)) +
      '; dir_hit_rate=' + _fmtDiagMetric_(_rateRaw_(g.dir_hit_count, g.rows_scored)) +
      '; avg_outcome_score=' + (g.score_count ? _roundRate_(g.score_sum / g.score_count) : '') +
      '; dirs=' + _countMapToString_(g.dirs) +
      '; strengths=' + _countMapToString_(g.strengths),
    diagnostic_level: level,
    diagnostic_summary: 'Provider character profile based on observed prediction style and scored outcomes.',
    recommended_next_step: 'Use as audit context only; do not apply automatic provider weighting yet.'
  });
}

function _makeProviderAttentionStyleRow_(generatedTs, g, diagnosticType, scope, scopeKey) {
  var topFactors = _topCountMapItems_(g.factors, 5);
  return _makeProviderCharacterDiagnosticRow_(generatedTs, {
    diagnostic_type: diagnosticType,
    scope: scope,
    scope_key: scopeKey,
    outcome_family: '',
    ai_name: g.ai_name,
    metric_name: 'top_attention_factors',
    metric_value: topFactors.length ? topFactors[0].key : '',
    metric_detail: topFactors.map(function(item){ return item.key + '=' + item.count; }).join('; '),
    diagnostic_level: topFactors.length ? 'observed' : 'missing',
    diagnostic_summary: 'Provider shows a repeatable attention-factor style in shadow metadata.',
    recommended_next_step: 'Compare factor style with outcomes after more attention-era samples.'
  });
}

function _buildProviderUniqueWinDiagnostics_(targetGroups, ledgerIdx, generatedTs) {
  var wins = {};
  var completeTargets = 0;
  var allTied = 0;
  var mixedDirectionTargets = 0;
  var uniqueWinsOnMixed = 0;
  Object.keys(targetGroups).forEach(function(key) {
    var rows = targetGroups[key];
    var byProvider = {};
    for (var i = 0; i < rows.length; i++) {
      var aiName = String(_predValue_(rows[i], ledgerIdx, 'ai_name') || '').trim();
      if (aiName) byProvider[aiName] = rows[i];
    }
    var providers = Object.keys(byProvider).sort();
    if (providers.length < 3) return;
    completeTargets += 1;
    var dirs = {};
    var bestScore = -1;
    var bestProviders = [];
    for (var p = 0; p < providers.length; p++) {
      var provider = providers[p];
      var row = byProvider[provider];
      var score = _numOrNull_(_predValue_(row, ledgerIdx, 'outcome_score'));
      if (score == null) score = -1;
      var dir = String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
      if (dir) dirs[dir] = true;
      if (score > bestScore) {
        bestScore = score;
        bestProviders = [provider];
      } else if (score === bestScore) {
        bestProviders.push(provider);
      }
    }
    var mixed = Object.keys(dirs).length > 1;
    if (mixed) mixedDirectionTargets += 1;
    if (bestProviders.length === providers.length) allTied += 1;
    if (bestProviders.length === 1) {
      var winner = bestProviders[0];
      if (!wins[winner]) wins[winner] = { total: 0, mixed: 0 };
      wins[winner].total += 1;
      if (mixed) {
        wins[winner].mixed += 1;
        uniqueWinsOnMixed += 1;
      }
    }
  });

  var rowsOut = [];
  Object.keys(wins).sort().forEach(function(aiName) {
    var w = wins[aiName];
    rowsOut.push(_makeProviderCharacterDiagnosticRow_(generatedTs, {
      diagnostic_type: 'unique_win_pattern',
      scope: 'provider',
      scope_key: aiName,
      outcome_family: '',
      ai_name: aiName,
      metric_name: 'unique_win_count',
      metric_value: w.total,
      metric_detail: 'complete_targets=' + completeTargets + '; mixed_direction_unique_wins=' + w.mixed,
      diagnostic_level: w.total >= 10 ? 'notable' : 'emerging',
      diagnostic_summary: 'Provider uniquely outperformed peers on some complete target groups.',
      recommended_next_step: 'Treat as character evidence only until larger samples confirm the pattern.'
    }));
  });

  rowsOut.push(_makeProviderCharacterDiagnosticRow_(generatedTs, {
    diagnostic_type: 'tie_pattern',
    scope: 'global',
    scope_key: 'all',
    outcome_family: '',
    ai_name: '',
    metric_name: 'all_provider_tie_rate',
    metric_value: _rateOrBlank_(allTied, completeTargets),
    metric_detail: 'complete_targets=' + completeTargets +
      '; all_provider_ties=' + allTied +
      '; mixed_direction_targets=' + mixedDirectionTargets +
      '; unique_wins_on_mixed_direction=' + uniqueWinsOnMixed,
    diagnostic_level: completeTargets && allTied / completeTargets >= 0.70 ? 'high_convergence' : 'moderate_convergence',
    diagnostic_summary: 'Many targets still tie across providers, so provider character signals are clearest when predictions diverge.',
    recommended_next_step: 'Keep collecting attention-era rows and monitor mixed-direction cases separately.'
  }));
  return rowsOut;
}

function _buildProviderConvergenceCharacterRows_(targetGroups, ledgerIdx, generatedTs) {
  var completeTargets = 0;
  var sameDirectionTargets = 0;
  Object.keys(targetGroups).forEach(function(key) {
    var rows = targetGroups[key];
    var providers = {};
    var dirs = {};
    for (var i = 0; i < rows.length; i++) {
      var aiName = String(_predValue_(rows[i], ledgerIdx, 'ai_name') || '').trim();
      if (aiName) providers[aiName] = true;
      var dir = String(_predValue_(rows[i], ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
      if (dir) dirs[dir] = true;
    }
    if (Object.keys(providers).length < 3) return;
    completeTargets += 1;
    if (Object.keys(dirs).length === 1) sameDirectionTargets += 1;
  });
  return [
    _makeProviderCharacterDiagnosticRow_(generatedTs, {
      diagnostic_type: 'convergence_character',
      scope: 'global',
      scope_key: 'all',
      outcome_family: '',
      ai_name: '',
      metric_name: 'same_direction_rate',
      metric_value: _rateOrBlank_(sameDirectionTargets, completeTargets),
      metric_detail: 'complete_targets=' + completeTargets + '; same_direction_targets=' + sameDirectionTargets,
      diagnostic_level: completeTargets && sameDirectionTargets / completeTargets >= 0.70 ? 'high' : 'moderate',
      diagnostic_summary: 'Provider character differences are harder to observe when all providers choose the same direction.',
      recommended_next_step: 'Use disagreement slices to evaluate whether attention factors reveal provider diversity.'
    })
  ];
}

function _makeProviderCharacterDiagnosticRow_(generatedTs, attrs) {
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
    'Provider-character diagnostic only; not trading advice.'
  ];
}

function buildAttentionProviderIndividualityRows_(ledgerRows, ledgerIdx, generatedTs) {
  var usableRows = [];
  var providerFactorCounts = {};
  var providerTotals = {};
  var factorTotals = {};
  var providerFamilyFactorCounts = {};
  var providerFamilyTotals = {};
  var providerFamilies = {};
  var targetGroups = {};
  var warnings = [];
  var required = ['ai_name', 'outcome_family', 'attention_factor_1'];
  for (var r = 0; r < required.length; r++) {
    if (ledgerIdx[required[r]] === undefined) {
      warnings.push('missing_required_or_useful_header=' + required[r]);
    }
  }

  for (var i = 0; i < (ledgerRows || []).length; i++) {
    var row = ledgerRows[i];
    if (!_isAttentionEraLedgerRow_(row, ledgerIdx)) continue;
    var provider = String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim();
    if (!provider) continue;
    var family = String(_predValue_(row, ledgerIdx, 'outcome_family') || '').trim() || 'other';
    var factors = _attentionFactorsFromLedgerRow_(row, ledgerIdx);
    if (!factors.length) continue;
    usableRows.push(row);
    providerFamilies[provider + '|' + family] = true;

    for (var f = 0; f < factors.length; f++) {
      var factor = factors[f].factor;
      _incCount_(providerFactorCounts, provider + '|' + factor, 1);
      _incCount_(providerTotals, provider, 1);
      _incCount_(factorTotals, factor, 1);
      _incCount_(providerFamilyFactorCounts, provider + '|' + family + '|' + factor, 1);
      _incCount_(providerFamilyTotals, provider + '|' + family, 1);
    }

    var targetKey = _providerCharacterTargetKey_(row, ledgerIdx);
    if (targetKey) {
      if (!targetGroups[targetKey]) targetGroups[targetKey] = [];
      targetGroups[targetKey].push(row);
    }
  }

  var generatedRows = [];
  generatedRows = generatedRows.concat(_buildAttentionProviderFactorFrequencyRows_(
    generatedTs,
    providerFactorCounts,
    providerTotals,
    factorTotals
  ));
  generatedRows = generatedRows.concat(_buildAttentionProviderFamilyFactorRows_(
    generatedTs,
    providerFamilyFactorCounts,
    providerFamilyTotals
  ));
  var divergenceBundle = _buildAttentionProviderDivergenceRows_(generatedTs, targetGroups, ledgerIdx);
  generatedRows = generatedRows.concat(divergenceBundle.rows);
  generatedRows = generatedRows.concat(_buildAttentionConvergenceVsDivergenceRows_(generatedTs, divergenceBundle.categoryCounts, divergenceBundle.totalGroups));
  generatedRows = generatedRows.concat(_buildAttentionProviderPersonalityRows_(
    generatedTs,
    providerFactorCounts,
    providerTotals,
    providerFamilyFactorCounts,
    providerFamilyTotals,
    providerFamilies
  ));
  generatedRows = generatedRows.concat(_buildAttentionIndividualitySummaryRows_(
    generatedTs,
    usableRows.length,
    divergenceBundle.totalGroups,
    divergenceBundle.divergentGroups,
    divergenceBundle.categoryCounts,
    warnings
  ));
  return generatedRows;
}

function _buildAttentionProviderFactorFrequencyRows_(generatedTs, providerFactorCounts, providerTotals, factorTotals) {
  var rowsOut = [];
  var totalSelections = 0;
  Object.keys(factorTotals || {}).forEach(function(factor) {
    totalSelections += Number(factorTotals[factor] || 0);
  });
  var byProvider = {};
  Object.keys(providerFactorCounts || {}).forEach(function(key) {
    var parts = key.split('|');
    var provider = parts[0] || '';
    var factor = parts.slice(1).join('|') || '';
    if (!byProvider[provider]) byProvider[provider] = [];
    byProvider[provider].push({ provider: provider, factor: factor, count: Number(providerFactorCounts[key] || 0) });
  });
  Object.keys(byProvider).sort().forEach(function(provider) {
    var items = byProvider[provider].sort(function(a, b) {
      if (a.count !== b.count) return b.count - a.count;
      return String(a.factor).localeCompare(String(b.factor));
    });
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
        report_section: 'provider_factor_frequency',
        scope: 'provider_factor',
        scope_key: provider + '|' + item.factor,
        provider: provider,
        attention_factor: item.factor,
        row_count: item.count,
        share_within_provider: _rateOrBlank_(item.count, providerTotals[provider]),
        overall_share: _rateOrBlank_(item.count, totalSelections),
        rank_within_provider: i + 1,
        individuality_evidence: 'Provider attention factor frequency; explainability evidence only.',
        performance_evidence_note: 'No outcome improvement is inferred from this frequency row.'
      }));
    }
  });
  return rowsOut;
}

function _buildAttentionProviderFamilyFactorRows_(generatedTs, providerFamilyFactorCounts, providerFamilyTotals) {
  var rowsOut = [];
  var byProviderFamily = {};
  Object.keys(providerFamilyFactorCounts || {}).forEach(function(key) {
    var parts = key.split('|');
    var provider = parts[0] || '';
    var family = parts[1] || '';
    var factor = parts.slice(2).join('|') || '';
    var pfKey = provider + '|' + family;
    if (!byProviderFamily[pfKey]) byProviderFamily[pfKey] = [];
    byProviderFamily[pfKey].push({
      provider: provider,
      family: family,
      factor: factor,
      count: Number(providerFamilyFactorCounts[key] || 0)
    });
  });
  Object.keys(byProviderFamily).sort().forEach(function(pfKey) {
    var items = byProviderFamily[pfKey].sort(function(a, b) {
      if (a.count !== b.count) return b.count - a.count;
      return String(a.factor).localeCompare(String(b.factor));
    });
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
        report_section: 'provider_family_factor_matrix',
        scope: 'provider_family_factor',
        scope_key: item.provider + '|' + item.family + '|' + item.factor,
        provider: item.provider,
        event_family: item.family,
        attention_factor: item.factor,
        row_count: item.count,
        share_within_provider_family: _rateOrBlank_(item.count, providerFamilyTotals[item.provider + '|' + item.family]),
        rank_within_provider_family: i + 1,
        individuality_evidence: 'Provider attention factor choice within family; explainability evidence only.',
        performance_evidence_note: 'No outcome improvement is inferred from this matrix row.'
      }));
    }
  });
  return rowsOut;
}

function _buildAttentionProviderDivergenceRows_(generatedTs, targetGroups, ledgerIdx) {
  var rowsOut = [];
  var categoryCounts = {
    same_direction_different_factors: 0,
    different_direction_different_factors: 0,
    same_direction_same_factor: 0,
    different_direction_same_factor: 0
  };
  var totalGroups = 0;
  var divergentGroups = 0;
  Object.keys(targetGroups || {}).sort().forEach(function(targetKey) {
    var rows = targetGroups[targetKey] || [];
    var providers = {};
    var dirs = {};
    var primaryFactors = {};
    var qualitative = {};
    var first = rows[0];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var provider = String(_predValue_(row, ledgerIdx, 'ai_name') || '').trim();
      if (provider) providers[provider] = true;
      var dir = String(_predValue_(row, ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
      if (dir) dirs[dir] = true;
      var factors = _attentionFactorsFromLedgerRow_(row, ledgerIdx);
      if (factors.length) primaryFactors[factors[0].factor] = true;
      var qual = String(_predValue_(row, ledgerIdx, 'qualitative_result') || '').trim();
      if (qual) qualitative[qual] = true;
    }
    var providerNames = Object.keys(providers).sort();
    if (providerNames.length < 2) return;
    totalGroups += 1;
    var factorCount = Object.keys(primaryFactors).length;
    var directionCount = Object.keys(dirs).length;
    var sameFactor = factorCount <= 1;
    var directionDiverged = directionCount > 1;
    if (!sameFactor) divergentGroups += 1;
    if (!directionDiverged && !sameFactor) categoryCounts.same_direction_different_factors += 1;
    else if (directionDiverged && !sameFactor) categoryCounts.different_direction_different_factors += 1;
    else if (!directionDiverged && sameFactor) categoryCounts.same_direction_same_factor += 1;
    else categoryCounts.different_direction_same_factor += 1;

    rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
      report_section: 'provider_divergence_summary',
      scope: 'target',
      scope_key: targetKey,
      event_id: String(_predValue_(first, ledgerIdx, 'event_id') || '').trim(),
      batch_id: String(_predValue_(first, ledgerIdx, 'batch_id') || '').trim(),
      type: String(_predValue_(first, ledgerIdx, 'type') || '').trim(),
      release_ts: String(_predValue_(first, ledgerIdx, 'release_ts') || '').trim(),
      release_date: String(_predValue_(first, ledgerIdx, 'release_date') || '').trim(),
      event_family: String(_predValue_(first, ledgerIdx, 'outcome_family') || '').trim() || 'other',
      indicator_name: String(_predValue_(first, ledgerIdx, 'indicator_name') || '').trim(),
      providers_present: providerNames.join(','),
      distinct_attention_factors_count: factorCount,
      all_same_factor: sameFactor ? 'TRUE' : 'FALSE',
      partial_divergence: factorCount > 1 && factorCount < providerNames.length ? 'TRUE' : 'FALSE',
      full_divergence: factorCount >= providerNames.length && providerNames.length >= 2 ? 'TRUE' : 'FALSE',
      prediction_direction_diverged: directionDiverged ? 'TRUE' : 'FALSE',
      qualitative_result_diverged: Object.keys(qualitative).length > 1 ? 'TRUE' : 'FALSE',
      individuality_evidence: sameFactor
        ? 'Providers selected the same primary attention factor.'
        : 'Providers selected different primary attention factors for a comparable target.',
      performance_evidence_note: 'This row measures reasoning diversity only, not forecast quality.'
    }));
  });
  return {
    rows: rowsOut,
    categoryCounts: categoryCounts,
    totalGroups: totalGroups,
    divergentGroups: divergentGroups
  };
}

function _buildAttentionConvergenceVsDivergenceRows_(generatedTs, categoryCounts, totalGroups) {
  var rowsOut = [];
  var mapping = [
    ['same_direction_different_factors', 'cases where providers predicted same direction but chose different factors'],
    ['different_direction_different_factors', 'cases where providers predicted different directions and chose different factors'],
    ['same_direction_same_factor', 'cases where providers predicted same direction and chose same factor'],
    ['different_direction_same_factor', 'cases where providers predicted different direction but chose same factor']
  ];
  for (var i = 0; i < mapping.length; i++) {
    var key = mapping[i][0];
    var count = Number((categoryCounts || {})[key] || 0);
    rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
      report_section: 'convergence_vs_attention_divergence',
      scope: 'global',
      scope_key: key,
      row_count: count,
      same_direction_different_factors_count: key === 'same_direction_different_factors' ? count : '',
      different_direction_different_factors_count: key === 'different_direction_different_factors' ? count : '',
      same_direction_same_factor_count: key === 'same_direction_same_factor' ? count : '',
      different_direction_same_factor_count: key === 'different_direction_same_factor' ? count : '',
      overall_share: _rateOrBlank_(count, totalGroups),
      individuality_evidence: mapping[i][1],
      performance_evidence_note: 'This summary separates attention divergence from performance evidence.'
    }));
  }
  return rowsOut;
}

function _buildAttentionProviderPersonalityRows_(generatedTs, providerFactorCounts, providerTotals, providerFamilyFactorCounts, providerFamilyTotals, providerFamilies) {
  var rowsOut = [];
  var providers = Object.keys(providerTotals || {}).sort();
  for (var i = 0; i < providers.length; i++) {
    var provider = providers[i];
    var factorMap = {};
    Object.keys(providerFactorCounts || {}).forEach(function(key) {
      if (key.indexOf(provider + '|') !== 0) return;
      factorMap[key.substring(provider.length + 1)] = Number(providerFactorCounts[key] || 0);
    });
    var top = _topCountMapItems_(factorMap, 3);
    var topText = top.map(function(item){ return item.key + '=' + item.count; }).join('; ');
    var concentration = top.length ? _rateRaw_(top[0].count, providerTotals[provider]) : 0;
    var familyRows = _attentionProviderFamilyPersonalityTexts_(provider, providerFamilyFactorCounts, providerFamilyTotals, providerFamilies);
    rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
      report_section: 'provider_personality_summary',
      scope: 'provider',
      scope_key: provider,
      provider: provider,
      row_count: providerTotals[provider],
      top_attention_factors: topText,
      top_family_attention_factors: familyRows.join(' | '),
      concentration_score: _roundRate_(concentration),
      individuality_label: _attentionIndividualityLabel_(concentration, familyRows.length),
      individuality_evidence: 'Provider attention-factor habit summary. Label is descriptive and explainability-only.',
      performance_evidence_note: 'No routing, weighting, or calibration decision is inferred from provider personality.'
    }));
  }
  return rowsOut;
}

function _attentionProviderFamilyPersonalityTexts_(provider, providerFamilyFactorCounts, providerFamilyTotals, providerFamilies) {
  var texts = [];
  Object.keys(providerFamilies || {}).sort().forEach(function(pfKey) {
    if (pfKey.indexOf(provider + '|') !== 0) return;
    var family = pfKey.substring(provider.length + 1);
    var factorMap = {};
    Object.keys(providerFamilyFactorCounts || {}).forEach(function(key) {
      if (key.indexOf(provider + '|' + family + '|') !== 0) return;
      factorMap[key.substring((provider + '|' + family + '|').length)] = Number(providerFamilyFactorCounts[key] || 0);
    });
    var top = _topCountMapItems_(factorMap, 3);
    if (!top.length) return;
    texts.push(family + ': ' + top.map(function(item){ return item.key + '=' + item.count; }).join(','));
  });
  return texts.slice(0, 8);
}

function _attentionIndividualityLabel_(concentration, familyCount) {
  if (concentration >= 0.70) return 'factor-concentrated';
  if (concentration <= 0.35 && familyCount >= 3) return 'diversified';
  if (familyCount >= 4) return 'family-sensitive';
  return 'indistinct';
}

function _buildAttentionIndividualitySummaryRows_(generatedTs, usableRowCount, totalGroups, divergentGroups, categoryCounts, warnings) {
  var rowsOut = [];
  var divergenceRate = _rateRaw_(divergentGroups, totalGroups);
  rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
    report_section: 'individuality_summary',
    scope: 'global',
    scope_key: 'all',
    row_count: usableRowCount,
    distinct_attention_factors_count: divergentGroups,
    overall_share: _roundRate_(divergenceRate),
    individuality_label: divergenceRate >= 0.50 ? 'meaningful_reasoning_diversity' : (divergenceRate >= 0.25 ? 'emerging_reasoning_diversity' : 'limited_reasoning_diversity'),
    individuality_evidence: 'Comparable groups with primary attention-factor divergence=' + divergentGroups + '/' + totalGroups + '.',
    performance_evidence_note: 'This report evaluates individuality/explainability before forecast improvement.',
    diagnostic_note: 'Goal 1 report only; Phase 3A promotion rules are unchanged.'
  }));
  if (warnings && warnings.length) {
    rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
      report_section: 'build_warning',
      scope: 'global',
      scope_key: 'missing_optional_or_required_headers',
      diagnostic_note: warnings.join('; '),
      individuality_evidence: 'Some columns were unavailable; affected sections were built with available fields.',
      performance_evidence_note: 'No performance inference is made from warning rows.'
    }));
    if (typeof Logger !== 'undefined') Logger.log('Attention_Provider_Individuality warnings: ' + warnings.join('; '));
  }
  rowsOut.push(_makeAttentionProviderIndividualityRow_(generatedTs, {
    report_section: 'baseline_convergence_comparison',
    scope: 'global',
    scope_key: 'pre_attention_baseline',
    diagnostic_note: 'Skipped: no deterministic pre-attention baseline convergence table is wired into this report yet.',
    individuality_evidence: 'Post-attention attention-factor divergence is reported; pre-attention comparison is deferred.',
    performance_evidence_note: 'Skipped baseline comparison does not affect Phase 3A promotion rules.'
  }));
  return rowsOut;
}

function _makeAttentionProviderIndividualityRow_(generatedTs, attrs) {
  attrs = attrs || {};
  return [
    generatedTs,
    attrs.report_section || '',
    attrs.scope || '',
    attrs.scope_key || '',
    attrs.provider || '',
    attrs.event_family || '',
    attrs.attention_factor || '',
    attrs.row_count === undefined ? '' : attrs.row_count,
    attrs.share_within_provider === undefined ? '' : attrs.share_within_provider,
    attrs.overall_share === undefined ? '' : attrs.overall_share,
    attrs.rank_within_provider === undefined ? '' : attrs.rank_within_provider,
    attrs.share_within_provider_family === undefined ? '' : attrs.share_within_provider_family,
    attrs.rank_within_provider_family === undefined ? '' : attrs.rank_within_provider_family,
    attrs.event_id || '',
    attrs.batch_id || '',
    attrs.type || '',
    attrs.release_ts || '',
    attrs.release_date || '',
    attrs.indicator_name || '',
    attrs.providers_present || '',
    attrs.distinct_attention_factors_count === undefined ? '' : attrs.distinct_attention_factors_count,
    attrs.all_same_factor || '',
    attrs.partial_divergence || '',
    attrs.full_divergence || '',
    attrs.prediction_direction_diverged || '',
    attrs.qualitative_result_diverged || '',
    attrs.same_direction_different_factors_count === undefined ? '' : attrs.same_direction_different_factors_count,
    attrs.different_direction_different_factors_count === undefined ? '' : attrs.different_direction_different_factors_count,
    attrs.same_direction_same_factor_count === undefined ? '' : attrs.same_direction_same_factor_count,
    attrs.different_direction_same_factor_count === undefined ? '' : attrs.different_direction_same_factor_count,
    attrs.top_attention_factors || '',
    attrs.top_family_attention_factors || '',
    attrs.concentration_score === undefined ? '' : attrs.concentration_score,
    attrs.individuality_label || '',
    attrs.individuality_evidence || '',
    attrs.performance_evidence_note || 'Performance evidence is out of scope for this individuality row.',
    attrs.diagnostic_note || '',
    'Provider individuality / explainability report only; not trading advice.'
  ];
}

function _sortAttentionProviderIndividualityRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.report_section,
      idx.provider,
      idx.event_family,
      idx.rank_within_provider,
      idx.rank_within_provider_family,
      idx.release_ts,
      idx.scope_key
    ]);
  });
}

function _incCount_(map, key, amount) {
  if (!key) return;
  map[key] = Number(map[key] || 0) + Number(amount || 1);
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

  var summary = 'Attention Factor Selection v1 monitoring is not ready yet based on current diagnostic coverage.';
  if (readinessLevel === 'ready') summary = 'Attention Factor Selection v1 is implemented in shadow mode and ready for ongoing monitoring.';
  else if (readinessLevel === 'partial') summary = 'Attention Factor Selection v1 is implemented in shadow mode, but monitoring still has sample-depth or data-quality gaps.';

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
        ? 'Collect more scored outcomes and improve unscored coverage before expanding attention analysis.'
        : 'Monitor Attention Factor Summary and Provider Character Diagnostics without provider-specific roles or automatic weighting.'
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
    'attention_schema_version',
    'attention_factor_1',
    'attention_factor_1_weight',
    'attention_factor_2',
    'attention_factor_2_weight',
    'attention_factor_3',
    'attention_factor_3_weight',
    'attention_summary',
    'attention_validity_flag',
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
    _predValue_(src, idx, 'attention_schema_version'),
    _predValue_(src, idx, 'attention_factor_1'),
    _predValue_(src, idx, 'attention_factor_1_weight'),
    _predValue_(src, idx, 'attention_factor_2'),
    _predValue_(src, idx, 'attention_factor_2_weight'),
    _predValue_(src, idx, 'attention_factor_3'),
    _predValue_(src, idx, 'attention_factor_3_weight'),
    _predValue_(src, idx, 'attention_summary'),
    _predValue_(src, idx, 'attention_validity_flag'),
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
    var key = (eventId + '|' + aiName) || predictionId;
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
    var eventId = String(row[ridx.event_id] || '').trim();
    var aiName = String(row[ridx.ai_name] || '').trim();
    var predictionId = String(row[ridx.prediction_id] || '').trim();
    var key = (eventId + '|' + aiName) || predictionId;
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

function _sortAttentionFactorSummaryRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.summary_type,
      idx.outcome_family,
      idx.ai_name,
      idx.attention_factor,
      idx.attention_factor_rank,
      idx.scope_key
    ]);
  });
}

function _sortProviderCharacterDiagnosticsRows_(headers, rows) {
  _sortOutcomeDiagnosticsRows_(headers, rows);
}

function _sortAttentionEvidenceReportRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  var typeOrder = {
    attention_coverage: 1,
    phase3_readiness: 2,
    provider_baseline: 3,
    strong_factor_provider: 4,
    strong_factor_combo: 5,
    family_factor_strength: 6,
    weak_factor_provider: 7,
    family_factor_weakness: 8,
    provider_attention_style: 9,
    provider_unique_win: 10,
    tie_pattern: 11,
    convergence_character: 12
  };
  rows.sort(function(a, b) {
    var aType = String(a[idx.evidence_type] || '');
    var bType = String(b[idx.evidence_type] || '');
    var aOrder = typeOrder[aType] || 999;
    var bOrder = typeOrder[bType] || 999;
    if (aOrder !== bOrder) return aOrder - bOrder;

    if (aType === 'strong_factor_provider' || aType === 'strong_factor_combo' || aType === 'family_factor_strength') {
      var aStrong = _numOrNull_(a[idx.metric_value]);
      var bStrong = _numOrNull_(b[idx.metric_value]);
      if (aStrong !== bStrong) return (bStrong || -999999) - (aStrong || -999999);
    }

    if (aType === 'weak_factor_provider' || aType === 'family_factor_weakness') {
      var aWeak = _numOrNull_(a[idx.metric_value]);
      var bWeak = _numOrNull_(b[idx.metric_value]);
      if (aWeak !== bWeak) return (aWeak == null ? 999999 : aWeak) - (bWeak == null ? 999999 : bWeak);
    }

    return _cmpByColumns_(a, b, [
      idx.scope,
      idx.outcome_family,
      idx.ai_name,
      idx.attention_factor,
      idx.factor_combo,
      idx.scope_key
    ]);
  });
}

function _sortAttentionBlockStabilityRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  var typeOrder = {
    block_overview: 1,
    provider_block_performance: 2,
    family_block_performance: 3,
    attention_factor_block_performance: 4,
    provider_factor_block_performance: 5,
    convergence_block_risk: 6,
    cross_block_stability: 7,
    readiness_next_block: 8
  };
  rows.sort(function(a, b) {
    var aType = String(a[idx.diagnostic_type] || '');
    var bType = String(b[idx.diagnostic_type] || '');
    var aOrder = typeOrder[aType] || 999;
    var bOrder = typeOrder[bType] || 999;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return _cmpByColumns_(a, b, [
      idx.block_id,
      idx.scope,
      idx.outcome_family,
      idx.ai_name,
      idx.attention_factor,
      idx.scope_key
    ]);
  });
}

function _sortAttentionDisagreementReviewRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  var usefulnessOrder = {
    useful_disagreement: 1,
    possible_signal: 2,
    no_clear_winner: 3,
    noisy_or_small_gap: 4,
    unscored_or_thin: 5
  };
  rows.sort(function(a, b) {
    var aOrder = usefulnessOrder[String(a[idx.usefulness_label] || '')] || 999;
    var bOrder = usefulnessOrder[String(b[idx.usefulness_label] || '')] || 999;
    if (aOrder !== bOrder) return aOrder - bOrder;
    var aSpread = _numOrNull_(a[idx.score_spread]);
    var bSpread = _numOrNull_(b[idx.score_spread]);
    if (aSpread !== bSpread) return (bSpread || -999999) - (aSpread || -999999);
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.outcome_family,
      idx.type,
      idx.indicator_name,
      idx.target_key
    ]);
  });
}

function _sortAttentionDisagreementSummaryRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  var typeOrder = {
    global: 1,
    usefulness: 2,
    winner_provider: 3,
    family: 4,
    family_winner: 5,
    winner_factor: 6,
    family_winner_factor: 7,
    disagreement_kind: 8
  };
  rows.sort(function(a, b) {
    var aType = String(a[idx.summary_type] || '');
    var bType = String(b[idx.summary_type] || '');
    var aOrder = typeOrder[aType] || 999;
    var bOrder = typeOrder[bType] || 999;
    if (aOrder !== bOrder) return aOrder - bOrder;
    var aUseful = Number(a[idx.useful_disagreement_count] || 0) + Number(a[idx.possible_signal_count] || 0);
    var bUseful = Number(b[idx.useful_disagreement_count] || 0) + Number(b[idx.possible_signal_count] || 0);
    if (aUseful !== bUseful) return bUseful - aUseful;
    return _cmpByColumns_(a, b, [
      idx.outcome_family,
      idx.winner_provider,
      idx.attention_factor,
      idx.disagreement_kind,
      idx.scope_key
    ]);
  });
}

function _sortAttentionPhase3CandidateRows_(headers, rows) {
  if (!rows || rows.length < 2) return;
  var idx = _headerIndexMap_(headers);
  var usefulOrder = {
    useful_disagreement: 1,
    possible_signal: 2
  };
  rows.sort(function(a, b) {
    var aOrder = usefulOrder[String(a[idx.usefulness_label] || '')] || 999;
    var bOrder = usefulOrder[String(b[idx.usefulness_label] || '')] || 999;
    if (aOrder !== bOrder) return aOrder - bOrder;
    var aUseful = Number(a[idx.useful_rows] || 0);
    var bUseful = Number(b[idx.useful_rows] || 0);
    if (aUseful !== bUseful) return bUseful - aUseful;
    var aScore = _numOrNull_(a[idx.score_spread]);
    var bScore = _numOrNull_(b[idx.score_spread]);
    if (aScore !== bScore) return (bScore || -999999) - (aScore || -999999);
    return _cmpByColumns_(a, b, [
      idx.release_ts,
      idx.outcome_family,
      idx.winner_provider,
      idx.attention_factor,
      idx.target_key
    ]);
  });
}

function _attentionFactorsFromLedgerRow_(row, idx) {
  var out = [];
  for (var i = 1; i <= 3; i++) {
    var factor = String(_predValue_(row, idx, 'attention_factor_' + i) || '').trim();
    if (!factor) continue;
    out.push({ factor: factor, rank: i });
  }
  return out;
}

function _attentionFactorsWithWeightsFromLedgerRow_(row, idx) {
  var out = [];
  for (var i = 1; i <= 3; i++) {
    var factor = String(_predValue_(row, idx, 'attention_factor_' + i) || '').trim();
    if (!factor) continue;
    out.push({
      factor: factor,
      rank: i,
      weight: _numOrNull_(_predValue_(row, idx, 'attention_factor_' + i + '_weight'))
    });
  }
  return out;
}

function _attentionShadowGroupKey_(row, idx) {
  var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
  var batchId = String(_predValue_(row, idx, 'batch_id') || '').trim();
  var rowType = String(_predValue_(row, idx, 'type') || '').trim().toLowerCase();
  if (rowType === 'batch' && batchId) return 'batch|' + batchId;
  if (eventId) return 'event|' + eventId;
  if (batchId) return 'batch|' + batchId;
  return '';
}

function _getConvergenceInfoForShadow_() {
  var sheet = getSheet('Outcome_Summary_Convergence');
  if (!sheet) return {};
  var headers = getHeaderNames(sheet);
  var out = {};
  if (!headers || !headers.length) return out;
  var idx = _headerIndexMap_(headers);
  var rows = _readDataRows_(sheet);
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i];
    var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
    var batchId = String(_predValue_(row, idx, 'batch_id') || '').trim();
    var rowType = String(_predValue_(row, idx, 'type') || '').trim().toLowerCase();
    var key = (rowType === 'batch' && batchId) ? ('batch|' + batchId) : (eventId ? ('event|' + eventId) : (batchId ? ('batch|' + batchId) : ''));
    if (!key) continue;
    out[key] = {
      convergence_level: String(_predValue_(row, idx, 'convergence_level') || '').trim().toLowerCase(),
      unique_pred_dirs: Number(_predValue_(row, idx, 'unique_pred_dirs') || 0),
      provider_count: Number(_predValue_(row, idx, 'provider_count') || 0)
    };
  }
  return out;
}

function _deriveShadowConvergenceInfo_(groupRows, ledgerIdx) {
  var dirs = {};
  var strengths = {};
  for (var i = 0; i < (groupRows || []).length; i++) {
    var dir = String(_predValue_(groupRows[i], ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
    var strength = String(_predValue_(groupRows[i], ledgerIdx, 'mr_pred_strength') || '').trim().toLowerCase();
    if (dir) dirs[dir] = true;
    if (strength) strengths[strength] = true;
  }
  var dirCount = Object.keys(dirs).length;
  var strengthCount = Object.keys(strengths).length;
  var level = (dirCount <= 1 && strengthCount <= 1) ? 'high' : (dirCount > 1 ? 'low' : 'medium');
  return {
    convergence_level: level,
    unique_pred_dirs: dirCount,
    provider_count: _attentionShadowProviderCount_(groupRows, ledgerIdx)
  };
}

function _attentionShadowProviderCount_(groupRows, ledgerIdx) {
  var providers = {};
  for (var i = 0; i < (groupRows || []).length; i++) {
    var provider = String(_predValue_(groupRows[i], ledgerIdx, 'ai_name') || '').trim();
    if (provider) providers[provider] = true;
  }
  return Object.keys(providers).length;
}

function _attentionShadowIsDisagreement_(groupRows, ledgerIdx, convergenceInfo) {
  if (convergenceInfo && String(convergenceInfo.convergence_level || '').toLowerCase() === 'low') return true;
  if (convergenceInfo && Number(convergenceInfo.unique_pred_dirs || 0) > 1) return true;
  var dirs = {};
  for (var i = 0; i < (groupRows || []).length; i++) {
    var dir = String(_predValue_(groupRows[i], ledgerIdx, 'mr_pred_dir') || '').trim().toLowerCase();
    if (dir) dirs[dir] = true;
  }
  return Object.keys(dirs).length > 1;
}

function _attentionShadowFactorMatch_(row, ledgerIdx, factorName) {
  var factors = _attentionFactorsWithWeightsFromLedgerRow_(row, ledgerIdx);
  for (var i = 0; i < factors.length; i++) {
    if (factors[i].factor === factorName) return factors[i];
  }
  return null;
}

function _makeAttentionShadowExperimentRow_(generatedTs, attrs) {
  attrs = attrs || {};
  var row = attrs.source_row || [];
  var idx = attrs.ledger_idx || {};
  var baseline = attrs.baseline || {};
  var candidateScore = attrs.candidate_score;
  var baselineScore = baseline.baseline_outcome_score;
  var delta = attrs.candidate_vs_baseline_delta;
  if (delta === undefined) {
    delta = (candidateScore != null && baselineScore != null) ? _roundRate_(Number(candidateScore) - Number(baselineScore)) : '';
  }
  var won = delta !== '' && Number(delta) > 0;
  var lost = delta !== '' && Number(delta) < 0;
  var tied = delta !== '' && Number(delta) === 0;
  var candidateDir = attrs.candidate_pred_dir || '';
  var directionChanged = candidateDir && baseline.baseline_pred_dir && candidateDir !== baseline.baseline_pred_dir;
  var experimentId = [
    attrs.experiment_name || '',
    String(_predValue_(row, idx, 'event_id') || ''),
    String(_predValue_(row, idx, 'batch_id') || ''),
    attrs.candidate_provider || '',
    attrs.candidate_factor || ''
  ].join('|');
  var severeMissCreated = attrs.severe_miss_created_flag;
  if (severeMissCreated === undefined) {
    severeMissCreated = (attrs.candidate_bucket === 'miss' && baseline.baseline_outcome_bucket && baseline.baseline_outcome_bucket !== 'miss') ? 'TRUE' : 'FALSE';
  }
  return [
    generatedTs,
    experimentId,
    attrs.experiment_name || '',
    '3A.1',
    attrs.experiment_type || '',
    attrs.rule_description || '',
    attrs.source_scope || '',
    String(_predValue_(row, idx, 'event_id') || ''),
    String(_predValue_(row, idx, 'batch_id') || ''),
    String(_predValue_(row, idx, 'type') || ''),
    String(_predValue_(row, idx, 'release_ts') || ''),
    String(_predValue_(row, idx, 'release_date') || ''),
    String(_predValue_(row, idx, 'outcome_family') || '') || 'other',
    String(_predValue_(row, idx, 'indicator_name') || ''),
    String(_predValue_(row, idx, 'country') || ''),
    attrs.provider_count === undefined ? '' : attrs.provider_count,
    attrs.candidate_provider || '',
    attrs.candidate_factor || '',
    attrs.candidate_factor_weight == null ? '' : attrs.candidate_factor_weight,
    attrs.candidate_rule_triggered || '',
    baseline.method || 'best_equal_provider_observed',
    baseline.baseline_provider || '',
    baselineScore == null ? '' : baselineScore,
    baseline.baseline_outcome_bucket || '',
    candidateScore == null ? '' : candidateScore,
    attrs.candidate_bucket || '',
    delta,
    attrs.candidate_won_flag || (won ? 'TRUE' : 'FALSE'),
    attrs.candidate_lost_flag || (lost ? 'TRUE' : 'FALSE'),
    attrs.candidate_tied_flag || (tied ? 'TRUE' : 'FALSE'),
    attrs.direction_changed_flag || (directionChanged ? 'TRUE' : 'FALSE'),
    attrs.miss_avoided_flag || 'FALSE',
    severeMissCreated,
    attrs.shadow_signal_mode || '',
    attrs.shadow_confidence_action || '',
    attrs.shadow_behavior_note || '',
    'shadow_only',
    attrs.activation_blocker || 'needs_more_future_blocks',
    'Shadow experiment only; not trading advice.'
  ];
}

function _buildAttentionShadowSummaryRows_(experimentRows, experimentIdx, generatedTs) {
  var groups = {};
  for (var i = 0; i < (experimentRows || []).length; i++) {
    var row = experimentRows[i];
    var key = [
      String(_predValue_(row, experimentIdx, 'experiment_name') || '').trim(),
      String(_predValue_(row, experimentIdx, 'outcome_family') || '').trim() || 'other',
      String(_predValue_(row, experimentIdx, 'candidate_provider') || '').trim(),
      String(_predValue_(row, experimentIdx, 'candidate_factor') || '').trim()
    ].join('|');
    if (!groups[key]) {
      groups[key] = {
        experiment_name: String(_predValue_(row, experimentIdx, 'experiment_name') || '').trim(),
        outcome_family: String(_predValue_(row, experimentIdx, 'outcome_family') || '').trim() || 'other',
        candidate_provider: String(_predValue_(row, experimentIdx, 'candidate_provider') || '').trim(),
        candidate_factor: String(_predValue_(row, experimentIdx, 'candidate_factor') || '').trim(),
        blockers: {},
        rows_total: 0,
        rows_scored: 0,
        win_count: 0,
        loss_count: 0,
        tie_count: 0,
        delta_sum: 0,
        delta_count: 0,
        miss_avoided_count: 0,
        severe_miss_created_count: 0
      };
    }
    var g = groups[key];
    var delta = _numOrNull_(_predValue_(row, experimentIdx, 'candidate_vs_baseline_delta'));
    var candidateScore = _numOrNull_(_predValue_(row, experimentIdx, 'candidate_outcome_score'));
    var blocker = String(_predValue_(row, experimentIdx, 'activation_blocker') || '').trim();
    g.rows_total += 1;
    if (candidateScore != null) g.rows_scored += 1;
    if (_isTrueCell_(_predValue_(row, experimentIdx, 'candidate_won_flag'))) g.win_count += 1;
    if (_isTrueCell_(_predValue_(row, experimentIdx, 'candidate_lost_flag'))) g.loss_count += 1;
    if (_isTrueCell_(_predValue_(row, experimentIdx, 'candidate_tied_flag'))) g.tie_count += 1;
    if (delta != null) {
      g.delta_sum += delta;
      g.delta_count += 1;
    }
    if (_isTrueCell_(_predValue_(row, experimentIdx, 'miss_avoided_flag'))) g.miss_avoided_count += 1;
    if (_isTrueCell_(_predValue_(row, experimentIdx, 'severe_miss_created_flag'))) g.severe_miss_created_count += 1;
    if (blocker) g.blockers[blocker] = (g.blockers[blocker] || 0) + 1;
  }

  var rowsOut = [];
  Object.keys(groups).sort().forEach(function(key) {
    var g = groups[key];
    var winRate = _rateOrBlank_(g.win_count, g.rows_scored);
    var avgDelta = g.delta_count ? _roundRate_(g.delta_sum / g.delta_count) : '';
    var readiness = _attentionShadowActivationReadiness_(g.rows_scored, winRate, avgDelta);
    rowsOut.push([
      generatedTs,
      g.experiment_name,
      g.outcome_family,
      g.candidate_provider,
      g.candidate_factor,
      g.rows_total,
      g.rows_scored,
      g.win_count,
      g.loss_count,
      g.tie_count,
      winRate,
      avgDelta,
      g.miss_avoided_count,
      g.severe_miss_created_count,
      readiness,
      _attentionShadowSummaryBlocker_(readiness, g.blockers),
      'Shadow summary only; not trading advice.'
    ]);
  });
  return rowsOut;
}

function _attentionShadowActivationReadiness_(rowsScored, winRate, avgDelta) {
  var n = Number(rowsScored || 0);
  var w = _numOrNull_(winRate);
  var d = _numOrNull_(avgDelta);
  if (n < 20) return 'not_ready';
  if (w != null && w <= 0.45) return 'reject_or_monitor';
  if (n >= 40 && w != null && w >= 0.60 && d != null && d > 0.5) return 'strong_shadow_candidate';
  if (w != null && w >= 0.55 && d != null && d > 0) return 'watchlist_candidate';
  return 'inconclusive';
}

function _attentionShadowSummaryBlocker_(readiness, blockers) {
  if (readiness === 'strong_shadow_candidate' || readiness === 'watchlist_candidate') {
    return 'needs_future_block_confirmation';
  }
  var top = _topCountMapItems_(blockers || {}, 1);
  if (top.length) return top[0].key;
  return readiness === 'not_ready' ? 'insufficient_sample_size' : 'needs_more_future_blocks';
}

function _readFamilyStructureSource_(sheetName, warnings) {
  var ss = SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    warnings.push('missing_sheet:' + sheetName);
    return { name: sheetName, headers: [], idx: {}, rows: [] };
  }
  var headers = getHeaderNames(sheet) || [];
  if (!headers.length) {
    warnings.push('missing_headers:' + sheetName);
    return { name: sheetName, headers: [], idx: {}, rows: [] };
  }
  return {
    name: sheetName,
    headers: headers,
    idx: _headerIndexMap_(headers),
    rows: _readDataRows_(sheet)
  };
}

function _makeFamilyStructureReportRow_(generatedTs, attrs) {
  attrs = attrs || {};
  var headers = _familyStructureReportHeaders_();
  var row = [];
  for (var i = 0; i < headers.length; i++) {
    var h = headers[i];
    row.push(attrs[h] === undefined || attrs[h] === null ? '' : attrs[h]);
  }
  row[0] = generatedTs;
  if (!attrs.decision_support_note) {
    row[_headerIndexMap_(headers).decision_support_note] = 'Family Structure Investigation is diagnostic only; not trading advice.';
  }
  return row;
}

function _buildFamilyPerformanceSummaryRows_(generatedTs, sources, warnings) {
  var rowsOut = [];
  var ledger = sources.ledger;
  if (!ledger.rows.length) return rowsOut;
  _familyStructureRequireColumns_(ledger, ['outcome_family', 'ai_name', 'scored_flag'], warnings);

  var groups = {};
  for (var i = 0; i < ledger.rows.length; i++) {
    var row = ledger.rows[i];
    var family = _familyStructureRowFamily_(row, ledger.idx);
    if (!groups[family]) {
      groups[family] = {
        family: family,
        providers: {},
        rows_total: 0,
        rows_scored: 0,
        dir_ok: 0,
        strength_ok: 0,
        sustain_ok: 0,
        overall_ok: 0,
        realized_abs_sum: 0,
        realized_abs_count: 0,
        pred_abs_sum: 0,
        pred_abs_count: 0
      };
    }
    var g = groups[family];
    var provider = String(_predValue_(row, ledger.idx, 'ai_name') || '').trim();
    var scored = _isTrueCell_(_predValue_(row, ledger.idx, 'scored_flag'));
    var realized = _numOrNull_(_predValue_(row, ledger.idx, 'realized_pips'));
    var pred = _numOrNull_(_predValue_(row, ledger.idx, 'mr_pred_net_pips'));
    g.rows_total += 1;
    if (provider) g.providers[provider] = true;
    if (scored) {
      g.rows_scored += 1;
      if (_isTrueCell_(_predValue_(row, ledger.idx, 'mr_dir_ok'))) g.dir_ok += 1;
      if (_isTrueCell_(_predValue_(row, ledger.idx, 'mr_strength_ok'))) g.strength_ok += 1;
      if (_isTrueCell_(_predValue_(row, ledger.idx, 'mr_sustain_ok'))) g.sustain_ok += 1;
      if (_isTrueCell_(_predValue_(row, ledger.idx, 'overall_ok'))) g.overall_ok += 1;
    }
    if (realized != null) {
      g.realized_abs_sum += Math.abs(realized);
      g.realized_abs_count += 1;
    }
    if (pred != null) {
      g.pred_abs_sum += Math.abs(pred);
      g.pred_abs_count += 1;
    }
  }

  var convergenceByFamily = _familyStructureConvergenceByFamily_(sources.convergence);
  Object.keys(groups).sort().forEach(function(family) {
    var g = groups[family];
    var conv = convergenceByFamily[family] || {};
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'family_performance_summary',
      scope: 'family',
      scope_key: family,
      source_sheet: ledger.name,
      source_layer: 'Outcome_Ledger',
      outcome_family: family,
      event_family: family,
      family: family,
      provider_count: Object.keys(g.providers).length,
      row_count: g.rows_total,
      rows_scored: g.rows_scored,
      dir_ok_rate: _rateOrBlank_(g.dir_ok, g.rows_scored),
      mr_strength_ok_rate: _rateOrBlank_(g.strength_ok, g.rows_scored),
      mr_sustain_ok_rate: _rateOrBlank_(g.sustain_ok, g.rows_scored),
      overall_ok_rate: _rateOrBlank_(g.overall_ok, g.rows_scored),
      avg_realized_abs_pips: g.realized_abs_count ? _roundRate_(g.realized_abs_sum / g.realized_abs_count) : '',
      avg_pred_abs_pips: g.pred_abs_count ? _roundRate_(g.pred_abs_sum / g.pred_abs_count) : '',
      convergence_rate: conv.convergence_rate || '',
      disagreement_rate: conv.disagreement_rate || '',
      diagnostic_label: _familyStructurePerformanceLabel_(g),
      evidence_summary: 'Family-level outcome summary for structural investigation only.',
      recommended_next_question: 'Are weak families affected by family classification, batch construction, or evaluation mismatch?'
    }));
  });
  return rowsOut;
}

function _buildBatchCompositionSummaryRows_(generatedTs, composition, batchCompare, warnings) {
  var rowsOut = [];
  Object.keys(composition).sort().forEach(function(batchId) {
    var g = composition[batchId];
    var bc = batchCompare[batchId] || {};
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'batch_composition_summary',
      scope: 'batch',
      scope_key: batchId,
      source_sheet: 'Outcome_Ledger',
      source_layer: 'Outcome_Ledger',
      family_combo_key: g.family_combo_key,
      batch_id: batchId,
      release_ts: g.release_ts,
      release_date: g.release_date,
      country: g.country,
      type: 'batch',
      member_count: g.member_event_ids.length,
      distinct_family_count: g.member_families.length,
      member_event_ids: g.member_event_ids.join('|'),
      member_indicator_names: g.member_indicator_names.join('|'),
      member_families: g.member_families.join('|'),
      is_mixed_family_batch: g.member_families.length > 1 ? 'TRUE' : 'FALSE',
      has_low_signal_family: g.has_low_signal_family ? 'TRUE' : 'FALSE',
      has_clear_anchor: bc.has_clear_anchor || g.has_clear_anchor || '',
      batch_anchor_mode: bc.batch_anchor_mode || g.batch_anchor_mode,
      batch_anchor_confidence: bc.batch_anchor_confidence || g.batch_anchor_confidence,
      batch_anchor_event_id: bc.batch_anchor_event_id || g.batch_anchor_event_id,
      batch_anchor_indicator_name: bc.batch_anchor_indicator_name || g.batch_anchor_indicator_name,
      batch_anchor_margin: bc.batch_anchor_margin || '',
      diagnostic_label: _familyStructureBatchCompositionLabel_(g, bc),
      evidence_summary: 'Batch member composition and anchor trace are reported for structural review only.',
      recommended_next_question: 'Would this batch be clearer if same-minute members were separated by family or anchor relevance?'
    }));
  });
  return rowsOut;
}

function _buildBatchVsMemberComparisonRows_(generatedTs, batchCompare, composition, warnings) {
  var rowsOut = [];
  Object.keys(batchCompare).sort().forEach(function(batchId) {
    var g = batchCompare[batchId];
    var comp = composition[batchId] || {};
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'batch_vs_member_outcome_comparison',
      scope: 'batch',
      scope_key: batchId,
      source_sheet: 'Evaluation_BatchCompare',
      source_layer: 'Evaluation_BatchCompare',
      family_combo_key: comp.family_combo_key || '',
      batch_id: batchId,
      release_ts: g.release_ts,
      release_date: g.release_date,
      member_count: comp.member_event_ids ? comp.member_event_ids.length : '',
      distinct_family_count: comp.member_families ? comp.member_families.length : '',
      batch_prediction_count: g.batch_prediction_count,
      member_prediction_count: g.member_prediction_count,
      batch_dir_ok_rate: _rateOrBlank_(g.batch_dir_ok, g.scored_count),
      best_member_dir_ok_rate: _rateOrBlank_(g.best_member_dir_ok, g.scored_count),
      batch_overall_ok_rate: _rateOrBlank_(g.batch_overall_ok, g.scored_count),
      best_member_overall_ok_rate: _rateOrBlank_(g.best_member_overall_ok, g.scored_count),
      batch_vs_best_member_delta: g.scored_count ? _roundRate_(_rateNumber_(g.batch_overall_ok, g.scored_count) - _rateNumber_(g.best_member_overall_ok, g.scored_count)) : '',
      best_member_event_id: _topCountMapItems_(g.best_member_event_ids, 1).length ? _topCountMapItems_(g.best_member_event_ids, 1)[0].key : '',
      best_member_indicator_name: _topCountMapItems_(g.best_member_indicator_names, 1).length ? _topCountMapItems_(g.best_member_indicator_names, 1)[0].key : '',
      best_member_family: _topCountMapItems_(g.best_member_families, 1).length ? _topCountMapItems_(g.best_member_families, 1)[0].key : '',
      batch_anchor_event_id: g.batch_anchor_event_id,
      batch_anchor_indicator_name: g.batch_anchor_indicator_name,
      anchor_matches_best_member: _familyStructureMixedFlag_(g.anchor_match_values),
      anchor_match_rate: _rateOrBlank_(g.anchor_match_count, g.anchor_match_known_count),
      diagnostic_label: _familyStructureBatchVsMemberLabel_(g),
      evidence_summary: 'Compares current batch-level outcomes against best member outcomes without changing scoring.',
      recommended_next_question: 'Is batch-level prediction losing signal versus a member-level or family-filtered comparison?'
    }));
  });
  return rowsOut;
}

function _buildFamilyMixingRiskRows_(generatedTs, composition, batchCompare, warnings) {
  var combos = {};
  Object.keys(composition).forEach(function(batchId) {
    var comp = composition[batchId];
    var key = comp.family_combo_key || 'unknown';
    if (!combos[key]) {
      combos[key] = {
        key: key,
        batch_count: 0,
        total_member_count: 0,
        distinct_family_sum: 0,
        batch_dir_ok: 0,
        best_member_dir_ok: 0,
        scored_count: 0,
        anchor_match_count: 0,
        anchor_match_known_count: 0,
        problematic_batch_count: 0
      };
    }
    var g = combos[key];
    var bc = batchCompare[batchId] || {};
    var underperformed = _familyStructureBatchUnderperformed_(bc);
    var anchorMismatch = _familyStructureAnchorMismatch_(bc);
    g.batch_count += 1;
    g.total_member_count += comp.member_event_ids.length;
    g.distinct_family_sum += comp.member_families.length;
    g.batch_dir_ok += Number(bc.batch_dir_ok || 0);
    g.best_member_dir_ok += Number(bc.best_member_dir_ok || 0);
    g.scored_count += Number(bc.scored_count || 0);
    g.anchor_match_count += Number(bc.anchor_match_count || 0);
    g.anchor_match_known_count += Number(bc.anchor_match_known_count || 0);
    if ((comp.member_families.length > 1 && underperformed) || anchorMismatch) g.problematic_batch_count += 1;
  });

  var rowsOut = [];
  Object.keys(combos).sort().forEach(function(key) {
    var g = combos[key];
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'family_mixing_risk_summary',
      scope: 'family_combo',
      scope_key: key,
      source_sheet: 'Outcome_Ledger|Evaluation_BatchCompare',
      source_layer: 'derived_join',
      family_combo_key: key,
      batch_count: g.batch_count,
      total_member_count: g.total_member_count,
      distinct_family_count: g.batch_count ? _roundRate_(g.distinct_family_sum / g.batch_count) : '',
      batch_dir_ok_rate: _rateOrBlank_(g.batch_dir_ok, g.scored_count),
      best_member_dir_ok_rate: _rateOrBlank_(g.best_member_dir_ok, g.scored_count),
      anchor_match_rate: _rateOrBlank_(g.anchor_match_count, g.anchor_match_known_count),
      problematic_batch_count: g.problematic_batch_count,
      diagnostic_label: g.problematic_batch_count >= 3 ? 'recurring_mixing_risk' : (g.problematic_batch_count ? 'possible_mixing_risk' : 'no_recurring_mixing_signal'),
      evidence_summary: 'Family-combination summary for recurring mixed-batch risk.',
      recommended_next_question: 'Are repeated mixed-family combinations adding evaluation noise or hiding member-level signal?'
    }));
  });
  return rowsOut;
}

function _buildRecurringFamilyRuleRows_(generatedTs, sources, batchCompare, warnings) {
  var groups = {};
  _addFamilyRuleGroupsFromDiagnostics_(groups, sources.diagnostics);
  _addFamilyRuleGroupsFromAttentionPhase3_(groups, sources.phase3);
  _addFamilyRuleGroupsFromScenario_(groups, sources.scenario);

  var rowsOut = [];
  Object.keys(groups).sort().forEach(function(key) {
    var g = groups[key];
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'recurring_family_rule_findings',
      scope: 'family_rule',
      scope_key: key,
      source_sheet: g.source_sheet,
      source_layer: g.source_layer,
      family: g.family,
      outcome_family: g.family,
      event_family: g.family,
      rule_or_finding: g.rule_or_finding,
      row_count: g.row_count,
      affected_batches: _keysSorted_(g.batches).join('|'),
      affected_events: _keysSorted_(g.events).join('|'),
      evidence_summary: g.evidence_summary,
      recommended_next_question: 'Do repeated family-rule findings point to deterministic structure fixes before provider routing?'
    }));
  });
  return rowsOut;
}

function _buildRecurringBatchSplittingRows_(generatedTs, composition, batchCompare, warnings) {
  var rowsOut = [];
  Object.keys(composition).sort().forEach(function(batchId) {
    var comp = composition[batchId];
    var bc = batchCompare[batchId] || {};
    var underperformed = _familyStructureBatchUnderperformed_(bc);
    var anchorMismatch = _familyStructureAnchorMismatch_(bc);
    if (comp.member_families.length <= 1 && !underperformed && !anchorMismatch) return;
    rowsOut.push(_makeFamilyStructureReportRow_(generatedTs, {
      section: 'recurring_batch_splitting_findings',
      scope: 'batch',
      scope_key: batchId,
      source_sheet: 'Outcome_Ledger|Evaluation_BatchCompare',
      source_layer: 'derived_join',
      batch_id: batchId,
      release_ts: comp.release_ts || bc.release_ts,
      release_date: comp.release_date || bc.release_date,
      member_count: comp.member_event_ids.length,
      distinct_family_count: comp.member_families.length,
      member_event_ids: comp.member_event_ids.join('|'),
      member_indicator_names: comp.member_indicator_names.join('|'),
      member_families: comp.member_families.join('|'),
      why_splitting_may_matter: _familyStructureSplitReason_(comp, bc),
      batch_prediction_result: 'batch_overall_ok_rate=' + (_rateOrBlank_(bc.batch_overall_ok, bc.scored_count) || 'n/a'),
      member_prediction_result: 'best_member_overall_ok_rate=' + (_rateOrBlank_(bc.best_member_overall_ok, bc.scored_count) || 'n/a'),
      evidence_summary: 'Batch is structurally mixed, underperformed best member, or has an anchor/best-member mismatch.',
      recommended_next_question: 'Should a future diagnostic compare same-minute batch prediction against family-split member groups?',
      diagnostic_label: comp.member_families.length > 1 ? 'batch_splitting_candidate' : 'member_outperformance_candidate'
    }));
  });
  return rowsOut;
}

function _buildFamilyInvestigationSummaryRows_(generatedTs, rowsOut, composition, batchCompare, warnings) {
  var families = {};
  var mixedCount = 0;
  var underCount = 0;
  var anchorMismatchCount = 0;
  var familyRuleCounts = {};
  var splittingCounts = {};
  Object.keys(composition).forEach(function(batchId) {
    var comp = composition[batchId];
    for (var i = 0; i < comp.member_families.length; i++) families[comp.member_families[i]] = true;
    if (comp.member_families.length > 1) mixedCount += 1;
    if (_familyStructureBatchUnderperformed_(batchCompare[batchId] || {})) underCount += 1;
    if (_familyStructureAnchorMismatch_(batchCompare[batchId] || {})) anchorMismatchCount += 1;
    if (comp.member_families.length > 1 || _familyStructureBatchUnderperformed_(batchCompare[batchId] || {})) {
      splittingCounts[comp.family_combo_key || 'unknown'] = (splittingCounts[comp.family_combo_key || 'unknown'] || 0) + 1;
    }
  });
  for (var r = 0; r < rowsOut.length; r++) {
    var row = rowsOut[r];
    var idx = _headerIndexMap_(_familyStructureReportHeaders_());
    if (String(row[idx.section] || '') === 'recurring_family_rule_findings') {
      var f = String(row[idx.family] || 'unknown');
      familyRuleCounts[f] = (familyRuleCounts[f] || 0) + Number(row[idx.row_count] || 1);
    }
  }
  var totalBatches = Object.keys(composition).length;
  var familyCandidates = _topCountMapItems_(familyRuleCounts, 5).map(function(item){ return item.key + ':' + item.count; }).join(', ');
  var splitCandidates = _topCountMapItems_(splittingCounts, 5).map(function(item){ return item.key + ':' + item.count; }).join(', ');
  var label = 'no_structural_signal_yet';
  if (underCount >= 3 || anchorMismatchCount >= 3) label = 'batch_splitting_candidate';
  else if (familyCandidates) label = 'family_rule_candidate';
  else if (totalBatches || Object.keys(families).length) label = 'investigate_more';
  return [_makeFamilyStructureReportRow_(generatedTs, {
    section: 'investigation_summary',
    scope: 'global',
    scope_key: 'all',
    source_sheet: 'Outcome_Ledger|Evaluation_BatchCompare|Outcome_Diagnostics|Attention_Phase3_Candidates',
    source_layer: 'derived_summary',
    total_families_reviewed: Object.keys(families).length,
    total_batches_reviewed: totalBatches,
    mixed_family_batch_count: mixedCount,
    mixed_family_batch_rate: _rateOrBlank_(mixedCount, totalBatches),
    batch_underperformance_count: underCount,
    anchor_mismatch_count: anchorMismatchCount,
    strongest_family_rule_candidates: familyCandidates,
    strongest_batch_splitting_candidates: splitCandidates,
    recommendation_label: label,
    summary_note: 'Attention Factor v1 showed provider individuality, but not routing/control evidence. This report checks whether event structure, family classification, or batch construction is the stronger next bottleneck.',
    warnings: _uniqueSortedStrings_(warnings).join(' | ')
  })];
}

function _familyStructureBatchCompositionMap_(source) {
  var map = {};
  if (!source || !source.rows.length) return map;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var batchId = String(_predValue_(row, source.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    var type = String(_predValue_(row, source.idx, 'type') || '').trim().toLowerCase();
    if (!map[batchId]) {
      map[batchId] = {
        batch_id: batchId,
        release_ts: String(_predValue_(row, source.idx, 'release_ts') || '').trim(),
        release_date: String(_predValue_(row, source.idx, 'release_date') || '').trim(),
        country: String(_predValue_(row, source.idx, 'country') || '').trim(),
        member_event_ids_map: {},
        member_indicator_names_map: {},
        member_families_map: {},
        member_event_ids: [],
        member_indicator_names: [],
        member_families: [],
        has_low_signal_family: false,
        has_clear_anchor: '',
        batch_anchor_mode: '',
        batch_anchor_confidence: '',
        batch_anchor_event_id: '',
        batch_anchor_indicator_name: ''
      };
    }
    var g = map[batchId];
    if (!g.release_ts) g.release_ts = String(_predValue_(row, source.idx, 'release_ts') || '').trim();
    if (!g.release_date) g.release_date = String(_predValue_(row, source.idx, 'release_date') || '').trim();
    if (!g.country) g.country = String(_predValue_(row, source.idx, 'country') || '').trim();
    if (type === 'batch') {
      g.batch_anchor_mode = g.batch_anchor_mode || String(_predValue_(row, source.idx, 'batch_anchor_mode') || '').trim();
      g.batch_anchor_confidence = g.batch_anchor_confidence || String(_predValue_(row, source.idx, 'batch_anchor_confidence') || '').trim();
      g.has_clear_anchor = g.batch_anchor_mode && g.batch_anchor_mode !== 'no_clear_anchor' ? 'TRUE' : (g.batch_anchor_mode === 'no_clear_anchor' ? 'FALSE' : g.has_clear_anchor);
    } else {
      var eventId = String(_predValue_(row, source.idx, 'event_id') || '').trim();
      var name = String(_predValue_(row, source.idx, 'indicator_name') || '').trim();
      var family = _familyStructureRowFamily_(row, source.idx);
      if (eventId) g.member_event_ids_map[eventId] = true;
      if (name) g.member_indicator_names_map[name] = true;
      if (family) {
        g.member_families_map[family] = true;
        if (_familyStructureIsLowSignalFamily_(family)) g.has_low_signal_family = true;
      }
    }
  }
  Object.keys(map).forEach(function(batchId) {
    var g = map[batchId];
    g.member_event_ids = _keysSorted_(g.member_event_ids_map);
    g.member_indicator_names = _keysSorted_(g.member_indicator_names_map);
    g.member_families = _keysSorted_(g.member_families_map);
    g.family_combo_key = g.member_families.join('+') || 'unknown';
  });
  return map;
}

function _familyStructureBatchCompareMap_(source) {
  var map = {};
  if (!source || !source.rows.length) return map;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var batchId = String(_predValue_(row, source.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    if (!map[batchId]) {
      map[batchId] = {
        batch_id: batchId,
        release_ts: String(_predValue_(row, source.idx, 'release_ts') || '').trim(),
        release_date: String(_predValue_(row, source.idx, 'release_date') || '').trim(),
        batch_prediction_count: 0,
        member_prediction_count: 0,
        scored_count: 0,
        batch_dir_ok: 0,
        best_member_dir_ok: 0,
        batch_overall_ok: 0,
        best_member_overall_ok: 0,
        anchor_match_count: 0,
        anchor_match_known_count: 0,
        anchor_match_values: {},
        best_member_event_ids: {},
        best_member_indicator_names: {},
        best_member_families: {},
        batch_anchor_mode: '',
        batch_anchor_confidence: '',
        batch_anchor_event_id: '',
        batch_anchor_indicator_name: '',
        batch_anchor_margin: '',
        has_clear_anchor: ''
      };
    }
    var g = map[batchId];
    g.batch_prediction_count += 1;
    g.member_prediction_count += Number(_predValue_(row, source.idx, 'member_count') || 0);
    g.scored_count += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'batch_dir_ok'))) g.batch_dir_ok += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'best_member_dir_ok'))) g.best_member_dir_ok += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'batch_overall_ok'))) g.batch_overall_ok += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'best_member_overall_ok'))) g.best_member_overall_ok += 1;
    var bestEventId = String(_predValue_(row, source.idx, 'best_member_event_id') || '').trim();
    var bestName = String(_predValue_(row, source.idx, 'best_member_indicator_name') || '').trim();
    var bestFamily = deriveOutcomeFamily_(bestName, String(_predValue_(row, source.idx, 'best_member_genre') || ''));
    if (bestEventId) g.best_member_event_ids[bestEventId] = (g.best_member_event_ids[bestEventId] || 0) + 1;
    if (bestName) g.best_member_indicator_names[bestName] = (g.best_member_indicator_names[bestName] || 0) + 1;
    if (bestFamily) g.best_member_families[bestFamily] = (g.best_member_families[bestFamily] || 0) + 1;
    var anchorMatch = String(_predValue_(row, source.idx, 'selected_anchor_matches_best_member') || '').trim();
    if (anchorMatch) g.anchor_match_values[anchorMatch] = true;
    if (anchorMatch === 'TRUE') {
      g.anchor_match_count += 1;
      g.anchor_match_known_count += 1;
    } else if (anchorMatch === 'FALSE') {
      g.anchor_match_known_count += 1;
    }
    g.batch_anchor_mode = g.batch_anchor_mode || String(_predValue_(row, source.idx, 'selected_anchor_mode') || '').trim();
    g.batch_anchor_confidence = g.batch_anchor_confidence || String(_predValue_(row, source.idx, 'selected_anchor_confidence') || '').trim();
    g.batch_anchor_event_id = g.batch_anchor_event_id || String(_predValue_(row, source.idx, 'selected_anchor_event_id') || '').trim();
    g.batch_anchor_indicator_name = g.batch_anchor_indicator_name || String(_predValue_(row, source.idx, 'selected_anchor_indicator_name') || '').trim();
    g.batch_anchor_margin = g.batch_anchor_margin || String(_predValue_(row, source.idx, 'selected_anchor_margin') || '').trim();
    if (g.batch_anchor_mode) g.has_clear_anchor = g.batch_anchor_mode === 'no_clear_anchor' ? 'FALSE' : 'TRUE';
  }
  return map;
}

function _familyStructureConvergenceByFamily_(source) {
  var out = {};
  if (!source || !source.rows.length) return out;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var family = String(_predValue_(row, source.idx, 'outcome_family') || '').trim() || 'other';
    if (!out[family]) out[family] = { total: 0, converged: 0, disagreed: 0 };
    var g = out[family];
    g.total += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'dir_converged_flag'))) g.converged += 1;
    var dirs = _numOrNull_(_predValue_(row, source.idx, 'unique_pred_dirs'));
    if (dirs != null && dirs > 1) g.disagreed += 1;
  }
  Object.keys(out).forEach(function(family) {
    var g = out[family];
    g.convergence_rate = _rateOrBlank_(g.converged, g.total);
    g.disagreement_rate = _rateOrBlank_(g.disagreed, g.total);
  });
  return out;
}

function _addFamilyRuleGroupsFromDiagnostics_(groups, source) {
  if (!source || !source.rows.length) return;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var type = String(_predValue_(row, source.idx, 'diagnostic_type') || '').toLowerCase();
    var summary = String(_predValue_(row, source.idx, 'diagnostic_summary') || '').toLowerCase();
    var next = String(_predValue_(row, source.idx, 'recommended_next_step') || '').toLowerCase();
    if (type.indexOf('family') < 0 && summary.indexOf('family') < 0 && next.indexOf('family') < 0) continue;
    var family = String(_predValue_(row, source.idx, 'outcome_family') || '').trim() || 'other';
    _familyStructureAddFindingGroup_(groups, 'Outcome_Diagnostics|family_rule|' + family, {
      source_sheet: 'Outcome_Diagnostics',
      source_layer: 'Outcome_Diagnostics',
      rule_or_finding: String(_predValue_(row, source.idx, 'metric_name') || type || 'family_rule'),
      family: family,
      evidence_summary: String(_predValue_(row, source.idx, 'diagnostic_summary') || 'Family diagnostic surfaced in Outcome_Diagnostics.')
    }, '', '');
  }
}

function _addFamilyRuleGroupsFromAttentionPhase3_(groups, source) {
  if (!source || !source.rows.length) return;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var family = String(_predValue_(row, source.idx, 'outcome_family') || '').trim() || 'other';
    var type = String(_predValue_(row, source.idx, 'candidate_type') || '').trim() || 'attention_phase3_candidate';
    _familyStructureAddFindingGroup_(groups, 'Attention_Phase3_Candidates|' + type + '|' + family, {
      source_sheet: 'Attention_Phase3_Candidates',
      source_layer: 'Attention_Phase3_Candidates',
      rule_or_finding: type,
      family: family,
      evidence_summary: 'Attention Phase 3 candidate evidence is retained as context, not promotion evidence.'
    }, String(_predValue_(row, source.idx, 'batch_id') || ''), String(_predValue_(row, source.idx, 'event_id') || ''));
  }
}

function _addFamilyRuleGroupsFromScenario_(groups, source) {
  if (!source || !source.rows.length) return;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var result = String(_predValue_(row, source.idx, 'scenario_eval_result') || '').trim();
    if (!result || result === 'watchlist_hit') continue;
    var name = String(_predValue_(row, source.idx, 'best_member_indicator_name') || '').trim();
    var genre = String(_predValue_(row, source.idx, 'best_member_genre') || '').trim();
    var family = deriveOutcomeFamily_(name, genre);
    _familyStructureAddFindingGroup_(groups, 'Evaluation_Scenario|' + result + '|' + family, {
      source_sheet: 'Evaluation_Scenario',
      source_layer: 'Evaluation_Scenario',
      rule_or_finding: result,
      family: family,
      evidence_summary: 'Scenario best-member/watchlist mismatch may indicate family-rule or anchor-selection friction.'
    }, String(_predValue_(row, source.idx, 'batch_id') || ''), String(_predValue_(row, source.idx, 'best_member_event_id') || ''));
  }
}

function _familyStructureAddFindingGroup_(groups, key, attrs, batchId, eventId) {
  if (!groups[key]) {
    groups[key] = {
      source_sheet: attrs.source_sheet || '',
      source_layer: attrs.source_layer || '',
      rule_or_finding: attrs.rule_or_finding || '',
      family: attrs.family || 'other',
      row_count: 0,
      batches: {},
      events: {},
      evidence_summary: attrs.evidence_summary || ''
    };
  }
  groups[key].row_count += 1;
  if (batchId) groups[key].batches[batchId] = true;
  if (eventId) groups[key].events[eventId] = true;
}

function _familyStructureRowFamily_(row, idx) {
  var family = String(_predValue_(row, idx, 'outcome_family') || '').trim();
  if (family) return family;
  return deriveOutcomeFamily_(String(_predValue_(row, idx, 'indicator_name') || ''), String(_predValue_(row, idx, 'genre') || '')) || 'other';
}

function _familyStructureRequireColumns_(source, required, warnings) {
  for (var i = 0; i < (required || []).length; i++) {
    if (source.idx[required[i]] === undefined) warnings.push('missing_column:' + source.name + '.' + required[i]);
  }
}

function _familyStructureIsLowSignalFamily_(family) {
  var f = String(family || '').toLowerCase();
  return f === 'other' || f === 'positioning' || f === 'central_bank';
}

function _familyStructurePerformanceLabel_(g) {
  if (!g.rows_scored) return 'unscored_or_thin';
  var overall = _rateNumber_(g.overall_ok, g.rows_scored);
  if (g.rows_scored < 10) return 'thin_sample';
  if (overall >= 0.60) return 'strong_family_outcomes';
  if (overall <= 0.40) return 'weak_family_outcomes';
  return 'mixed_family_outcomes';
}

function _familyStructureBatchCompositionLabel_(comp, bc) {
  if (comp.member_families.length > 1 && _familyStructureAnchorMismatch_(bc)) return 'mixed_family_anchor_mismatch';
  if (comp.member_families.length > 1) return 'mixed_family_batch';
  if (comp.has_low_signal_family) return 'low_signal_family_present';
  return 'single_family_batch';
}

function _familyStructureBatchVsMemberLabel_(g) {
  if (_familyStructureBatchUnderperformed_(g) && _familyStructureAnchorMismatch_(g)) return 'batch_underperformed_anchor_mismatch';
  if (_familyStructureBatchUnderperformed_(g)) return 'batch_underperformed_best_member';
  if (_familyStructureAnchorMismatch_(g)) return 'anchor_mismatch';
  return 'no_member_advantage_signal';
}

function _familyStructureBatchUnderperformed_(g) {
  if (!g || !g.scored_count) return false;
  return Number(g.best_member_overall_ok || 0) > Number(g.batch_overall_ok || 0);
}

function _familyStructureAnchorMismatch_(g) {
  if (!g || !g.anchor_match_known_count) return false;
  return Number(g.anchor_match_count || 0) < Number(g.anchor_match_known_count || 0);
}

function _familyStructureSplitReason_(comp, bc) {
  var parts = [];
  if (comp.member_families.length > 1) parts.push('mixed_family_batch');
  if (comp.has_low_signal_family) parts.push('low_signal_family_present');
  if (_familyStructureBatchUnderperformed_(bc)) parts.push('best_member_outperformed_batch');
  if (_familyStructureAnchorMismatch_(bc)) parts.push('anchor_did_not_match_best_member');
  return parts.join('|') || 'structural_review';
}

function _familyStructureMixedFlag_(values) {
  var keys = _keysSorted_(values || {});
  if (!keys.length) return '';
  if (keys.length === 1) return keys[0];
  return 'MIXED';
}

function _rateNumber_(count, total) {
  var t = Number(total || 0);
  return t ? Number(count || 0) / t : 0;
}

function _keysSorted_(map) {
  return Object.keys(map || {}).sort();
}

function _uniqueSortedStrings_(values) {
  var seen = {};
  for (var i = 0; i < (values || []).length; i++) {
    var v = String(values[i] || '').trim();
    if (v) seen[v] = true;
  }
  return Object.keys(seen).sort();
}

function _sortFamilyStructureReportRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.section,
      idx.scope,
      idx.scope_key,
      idx.release_ts,
      idx.batch_id,
      idx.family_combo_key,
      idx.family
    ]);
  });
}

function _buildBatchSplittingCandidateRows_(generatedTs, source, warnings) {
  var rows = source.rows || [];
  var idx = source.idx || {};
  var comboStats = {};
  var candidates = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var section = String(_predValue_(row, idx, 'section') || '').trim();
    if (section === 'family_mixing_risk_summary') {
      var combo = String(_predValue_(row, idx, 'scope_key') || _predValue_(row, idx, 'family_combo_key') || '').trim();
      if (combo) {
        comboStats[combo] = {
          batch_count: _numOrNull_(_predValue_(row, idx, 'batch_count')) || 0,
          problematic_batch_count: _numOrNull_(_predValue_(row, idx, 'problematic_batch_count')) || 0,
          batch_dir_ok_rate: _predValue_(row, idx, 'batch_dir_ok_rate'),
          best_member_dir_ok_rate: _predValue_(row, idx, 'best_member_dir_ok_rate')
        };
      }
    }
  }

  for (var r = 0; r < rows.length; r++) {
    var src = rows[r];
    if (String(_predValue_(src, idx, 'section') || '').trim() !== 'recurring_batch_splitting_findings') continue;
    var reason = String(_predValue_(src, idx, 'why_splitting_may_matter') || '').trim();
    var memberFamilies = String(_predValue_(src, idx, 'member_families') || '').trim();
    var comboKey = memberFamilies ? memberFamilies.replace(/\|/g, '+') : String(_predValue_(src, idx, 'family_combo_key') || '').trim();
    var stats = comboStats[comboKey] || {};
    var mixed = reason.indexOf('mixed_family_batch') >= 0 || Number(_predValue_(src, idx, 'distinct_family_count') || 0) > 1;
    var lowSignal = reason.indexOf('low_signal_family_present') >= 0;
    var outperformed = reason.indexOf('best_member_outperformed_batch') >= 0;
    var score = _batchSplittingCandidateScore_(mixed, lowSignal, outperformed, stats);
    candidates.push({
      row: src,
      combo_key: comboKey,
      stats: stats,
      mixed: mixed,
      low_signal: lowSignal,
      outperformed: outperformed,
      score: score,
      priority: _batchSplittingCandidatePriority_(score, outperformed, stats)
    });
  }

  candidates.sort(function(a, b) {
    if (a.score !== b.score) return b.score - a.score;
    var ap = Number(a.stats.problematic_batch_count || 0);
    var bp = Number(b.stats.problematic_batch_count || 0);
    if (ap !== bp) return bp - ap;
    return String(_predValue_(a.row, idx, 'release_ts') || '').localeCompare(String(_predValue_(b.row, idx, 'release_ts') || ''));
  });

  var out = [];
  for (var c = 0; c < candidates.length; c++) {
    var item = candidates[c];
    var srcRow = item.row;
    var batchId = String(_predValue_(srcRow, idx, 'batch_id') || _predValue_(srcRow, idx, 'scope_key') || '').trim();
    out.push([
      generatedTs,
      c + 1,
      item.priority,
      batchId || item.combo_key,
      batchId,
      _predValue_(srcRow, idx, 'release_ts'),
      _predValue_(srcRow, idx, 'release_date'),
      item.combo_key,
      _predValue_(srcRow, idx, 'member_families'),
      _predValue_(srcRow, idx, 'member_count'),
      _predValue_(srcRow, idx, 'distinct_family_count'),
      _predValue_(srcRow, idx, 'member_event_ids'),
      _predValue_(srcRow, idx, 'member_indicator_names'),
      item.mixed ? 'TRUE' : 'FALSE',
      item.low_signal ? 'TRUE' : 'FALSE',
      item.outperformed ? 'TRUE' : 'FALSE',
      _predValue_(srcRow, idx, 'batch_prediction_result'),
      _predValue_(srcRow, idx, 'member_prediction_result'),
      _extractRateFromResultText_(_predValue_(srcRow, idx, 'batch_prediction_result')),
      _extractRateFromResultText_(_predValue_(srcRow, idx, 'member_prediction_result')),
      _batchSplittingCandidateDelta_(_predValue_(srcRow, idx, 'batch_prediction_result'), _predValue_(srcRow, idx, 'member_prediction_result')),
      item.score,
      _predValue_(srcRow, idx, 'why_splitting_may_matter'),
      item.stats.batch_count || '',
      item.stats.problematic_batch_count || '',
      item.stats.batch_dir_ok_rate || '',
      item.stats.best_member_dir_ok_rate || '',
      item.priority === 'high_priority_diagnostic' ? 'focused_split_review' : (item.priority === 'medium_priority_diagnostic' ? 'monitor_split_pattern' : 'low_priority_context'),
      _batchSplittingRecommendedQuestion_(item),
      'Batch splitting candidate is diagnostic only; not trading advice and not a live batching behavior change.'
    ]);
  }
  if (!out.length && warnings) warnings.push('no_batch_splitting_candidates_from:Family_Structure_Report');
  return out;
}

function _batchSplittingCandidateScore_(mixed, lowSignal, outperformed, stats) {
  var score = 0;
  if (mixed) score += 3;
  if (lowSignal) score += 2;
  if (outperformed) score += 4;
  if (Number(stats.problematic_batch_count || 0) >= 5) score += 3;
  else if (Number(stats.problematic_batch_count || 0) >= 2) score += 2;
  if (Number(stats.batch_count || 0) >= 20) score += 1;
  return score;
}

function _batchSplittingCandidatePriority_(score, outperformed, stats) {
  if (score >= 10 || (outperformed && Number(stats.problematic_batch_count || 0) >= 3)) return 'high_priority_diagnostic';
  if (score >= 7) return 'medium_priority_diagnostic';
  return 'low_priority_diagnostic';
}

function _extractRateFromResultText_(value) {
  var text = String(value || '');
  var match = text.match(/=([0-9.]+)/);
  return match ? match[1] : '';
}

function _batchSplittingCandidateDelta_(batchResult, memberResult) {
  var b = _numOrNull_(_extractRateFromResultText_(batchResult));
  var m = _numOrNull_(_extractRateFromResultText_(memberResult));
  if (b == null || m == null) return '';
  return _roundRate_(b - m);
}

function _batchSplittingRecommendedQuestion_(item) {
  if (item.outperformed && item.mixed) {
    return 'Would a family-split diagnostic comparison preserve the best-member signal better than the current batch aggregate?';
  }
  if (item.mixed && item.low_signal) {
    return 'Is a low-signal or other-family member diluting the batch anchor or evaluation target?';
  }
  if (item.outperformed) {
    return 'Why did the best member outperform the batch even without mixed-family evidence?';
  }
  return 'Monitor this batch pattern for repeated structural noise before proposing behavior changes.';
}

function _sortBatchSplittingCandidateRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    var ar = Number(a[idx.candidate_rank] || 0);
    var br = Number(b[idx.candidate_rank] || 0);
    if (ar !== br) return ar - br;
    return _cmpByColumns_(a, b, [idx.release_ts, idx.batch_id]);
  });
}

function _buildBatchSplitCounterfactualRows_(generatedTs, source, warnings, evalCoverageMap) {
  var rowsOut = [];
  var rows = source.rows || [];
  var idx = source.idx || {};
  evalCoverageMap = evalCoverageMap || {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var priority = String(_predValue_(row, idx, 'candidate_priority') || '').trim();
    if (priority !== 'high_priority_diagnostic') continue;

    var batchId = String(_predValue_(row, idx, 'batch_id') || '').trim();
    var batchRate = _numOrNull_(_predValue_(row, idx, 'batch_overall_ok_rate'));
    var baselineSource = 'Batch_Splitting_Candidates.batch_overall_ok_rate';
    if (batchRate == null && evalCoverageMap[batchId] && Number(evalCoverageMap[batchId].scored_count || 0) > 0) {
      batchRate = _rateNumber_(evalCoverageMap[batchId].batch_overall_ok_count, evalCoverageMap[batchId].scored_count);
      baselineSource = 'Evaluation_BatchCompare.batch_overall_ok';
    }
    var splitRate = _numOrNull_(_predValue_(row, idx, 'best_member_overall_ok_rate'));
    var delta = (batchRate != null && splitRate != null) ? _roundRate_(splitRate - batchRate) : '';
    var label = _batchSplitCounterfactualLabel_(batchRate, splitRate, delta);
    var evidenceStrength = _batchSplitCounterfactualEvidenceStrength_(row, idx, label);
    var counterfactualId = [
      'batch_split_counterfactual_v1',
      batchId || String(_predValue_(row, idx, 'candidate_key') || '').trim(),
      String(_predValue_(row, idx, 'family_combo_key') || '').trim()
    ].join('|');

    rowsOut.push([
      generatedTs,
      '',
      counterfactualId,
      _predValue_(row, idx, 'candidate_rank'),
      priority,
      batchId,
      _predValue_(row, idx, 'release_ts'),
      _predValue_(row, idx, 'release_date'),
      _predValue_(row, idx, 'family_combo_key'),
      _predValue_(row, idx, 'member_families'),
      _predValue_(row, idx, 'member_count'),
      _predValue_(row, idx, 'distinct_family_count'),
      _predValue_(row, idx, 'member_event_ids'),
      _predValue_(row, idx, 'member_indicator_names'),
      'current_batch_observed',
      baselineSource,
      batchRate == null ? '' : batchRate,
      batchRate == null ? 'FALSE' : 'TRUE',
      'best_member_proxy_from_existing_scored_rows',
      'Batch_Splitting_Candidates.best_member_overall_ok_rate',
      splitRate == null ? '' : splitRate,
      splitRate == null ? 'FALSE' : 'TRUE',
      delta,
      label,
      label === 'split_proxy_helped' ? 'TRUE' : 'FALSE',
      label === 'split_proxy_hurt' ? 'TRUE' : 'FALSE',
      label === 'inconclusive_missing_baseline' || label === 'inconclusive_no_delta' ? 'TRUE' : 'FALSE',
      _predValue_(row, idx, 'split_reason'),
      _predValue_(row, idx, 'repeated_combo_count'),
      _predValue_(row, idx, 'combo_problematic_count'),
      evidenceStrength,
      'shadow_only',
      _batchSplitCounterfactualBlocker_(label),
      'Shadow-only counterfactual using existing scored rows; not trading advice and not live batch splitting.'
    ]);
  }

  rowsOut.sort(function(a, b) {
    var h = _batchSplitCounterfactualsHeaders_();
    var outIdx = _headerIndexMap_(h);
    var aStrength = _batchSplitEvidenceSortValue_(a[outIdx.evidence_strength]);
    var bStrength = _batchSplitEvidenceSortValue_(b[outIdx.evidence_strength]);
    if (aStrength !== bStrength) return bStrength - aStrength;
    var ad = _numOrNull_(a[outIdx.counterfactual_delta]);
    var bd = _numOrNull_(b[outIdx.counterfactual_delta]);
    if (ad != null && bd != null && ad !== bd) return bd - ad;
    return Number(a[outIdx.source_candidate_rank] || 0) - Number(b[outIdx.source_candidate_rank] || 0);
  });
  for (var r = 0; r < rowsOut.length; r++) {
    rowsOut[r][1] = r + 1;
  }
  if (!rowsOut.length && warnings) warnings.push('no_high_priority_candidates_from:Batch_Splitting_Candidates');
  return rowsOut;
}

function _batchSplitCounterfactualLabel_(batchRate, splitRate, delta) {
  if (batchRate == null || splitRate == null) return 'inconclusive_missing_baseline';
  var d = _numOrNull_(delta);
  if (d == null || d === 0) return 'inconclusive_no_delta';
  if (d > 0) return 'split_proxy_helped';
  return 'split_proxy_hurt';
}

function _batchSplitCounterfactualEvidenceStrength_(row, idx, label) {
  var repeated = Number(_predValue_(row, idx, 'repeated_combo_count') || 0);
  var problematic = Number(_predValue_(row, idx, 'combo_problematic_count') || 0);
  if (label === 'split_proxy_helped' && problematic >= 5 && repeated >= 20) return 'strong_shadow_evidence';
  if (label === 'split_proxy_helped' && problematic >= 2) return 'moderate_shadow_evidence';
  if (label === 'inconclusive_missing_baseline' && problematic >= 4) return 'needs_more_scored_batch_rows';
  return 'thin_or_context_only';
}

function _batchSplitCounterfactualBlocker_(label) {
  if (label === 'split_proxy_helped') return 'needs_true_family_split_counterfactual_not_best_member_proxy';
  if (label === 'split_proxy_hurt') return 'proxy_suggests_possible_damage';
  return 'missing_current_batch_score_or_no_delta';
}

function _batchSplitEvidenceSortValue_(value) {
  var v = String(value || '');
  if (v === 'strong_shadow_evidence') return 4;
  if (v === 'moderate_shadow_evidence') return 3;
  if (v === 'needs_more_scored_batch_rows') return 2;
  return 1;
}

function _sortBatchSplitCounterfactualRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    var ar = Number(a[idx.counterfactual_rank] || 0);
    var br = Number(b[idx.counterfactual_rank] || 0);
    if (ar !== br) return ar - br;
    return _cmpByColumns_(a, b, [idx.release_ts, idx.batch_id]);
  });
}

function _buildBatchBaselineCoverageAuditRows_(generatedTs, sources, warnings) {
  var counter = sources.counterfactuals || { rows: [], idx: {} };
  var ledgerMap = _batchBaselineLedgerCoverageMap_(sources.ledger);
  var evalMap = _batchBaselineEvalCompareCoverageMap_(sources.batchCompare);
  var rowsOut = [];
  var summary = {
    total: 0,
    baseline_available: 0,
    missing_baseline: 0,
    missing_eval_compare: 0,
    ledger_unscored_batch: 0,
    missing_ledger_batch: 0
  };

  for (var i = 0; i < (counter.rows || []).length; i++) {
    var row = counter.rows[i];
    var batchId = String(_predValue_(row, counter.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    var ledger = ledgerMap[batchId] || _emptyBatchBaselineLedgerCoverage_();
    var ev = evalMap[batchId] || _emptyBatchBaselineEvalCoverage_();
    var baselineAvailable = _isTrueCell_(_predValue_(row, counter.idx, 'baseline_batch_result_available'));
    var gap = _batchBaselineCoverageGap_(baselineAvailable, ledger, ev);
    summary.total += 1;
    if (baselineAvailable) summary.baseline_available += 1;
    else summary.missing_baseline += 1;
    if (gap.label === 'missing_evaluation_batch_compare') summary.missing_eval_compare += 1;
    if (gap.label === 'batch_rows_present_but_unscored') summary.ledger_unscored_batch += 1;
    if (gap.label === 'missing_ledger_batch_rows') summary.missing_ledger_batch += 1;

    rowsOut.push([
      generatedTs,
      'batch_baseline_audit',
      _predValue_(row, counter.idx, 'counterfactual_rank'),
      batchId,
      _predValue_(row, counter.idx, 'release_ts'),
      _predValue_(row, counter.idx, 'family_combo_key'),
      _predValue_(row, counter.idx, 'counterfactual_result_label'),
      _predValue_(row, counter.idx, 'evidence_strength'),
      baselineAvailable ? 'TRUE' : 'FALSE',
      ledger.batch_row_count,
      Object.keys(ledger.batch_providers).length,
      ledger.batch_scored_count,
      ledger.batch_overall_ok_count,
      ledger.member_row_count,
      ledger.member_scored_count,
      ev.row_count,
      ev.scored_count,
      ev.batch_overall_ok_count,
      _isTrueCell_(_predValue_(row, counter.idx, 'split_proxy_result_available')) ? 'TRUE' : 'FALSE',
      gap.label,
      gap.detail,
      gap.next_step,
      '',
      '',
      '',
      '',
      '',
      '',
      'Coverage audit only; not trading advice and not a scoring change.'
    ]);
  }

  rowsOut.push([
    generatedTs,
    'coverage_summary',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    _batchBaselineSummaryLabel_(summary),
    'Summarizes why Batch_Split_Counterfactuals is mostly inconclusive.',
    _batchBaselineSummaryNextStep_(summary),
    summary.total,
    summary.baseline_available,
    summary.missing_baseline,
    summary.missing_eval_compare,
    summary.ledger_unscored_batch,
    summary.missing_ledger_batch,
    'Coverage audit only; not trading advice and not a scoring change.'
  ]);
  return rowsOut;
}

function _batchBaselineLedgerCoverageMap_(source) {
  var map = {};
  if (!source || !source.rows) return map;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var batchId = String(_predValue_(row, source.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    if (!map[batchId]) map[batchId] = _emptyBatchBaselineLedgerCoverage_();
    var g = map[batchId];
    var type = String(_predValue_(row, source.idx, 'type') || '').trim().toLowerCase();
    var provider = String(_predValue_(row, source.idx, 'ai_name') || '').trim();
    var scored = _isTrueCell_(_predValue_(row, source.idx, 'scored_flag'));
    if (type === 'batch') {
      g.batch_row_count += 1;
      if (provider) g.batch_providers[provider] = true;
      if (scored) g.batch_scored_count += 1;
      if (_isTrueCell_(_predValue_(row, source.idx, 'overall_ok'))) g.batch_overall_ok_count += 1;
    } else {
      g.member_row_count += 1;
      if (scored) g.member_scored_count += 1;
    }
  }
  return map;
}

function _batchBaselineEvalCompareCoverageMap_(source) {
  var map = {};
  if (!source || !source.rows) return map;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var batchId = String(_predValue_(row, source.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    if (!map[batchId]) map[batchId] = _emptyBatchBaselineEvalCoverage_();
    var g = map[batchId];
    g.row_count += 1;
    var hasBatchResult = _predValue_(row, source.idx, 'batch_overall_ok') !== '';
    if (hasBatchResult) g.scored_count += 1;
    if (_isTrueCell_(_predValue_(row, source.idx, 'batch_overall_ok'))) g.batch_overall_ok_count += 1;
  }
  return map;
}

function _emptyBatchBaselineLedgerCoverage_() {
  return {
    batch_row_count: 0,
    batch_providers: {},
    batch_scored_count: 0,
    batch_overall_ok_count: 0,
    member_row_count: 0,
    member_scored_count: 0
  };
}

function _emptyBatchBaselineEvalCoverage_() {
  return { row_count: 0, scored_count: 0, batch_overall_ok_count: 0 };
}

function _batchBaselineCoverageGap_(baselineAvailable, ledger, ev) {
  if (baselineAvailable) {
    return {
      label: 'baseline_available',
      detail: 'Current batch baseline is available for counterfactual comparison.',
      next_step: 'Keep as usable counterfactual evidence; do not activate behavior from one row.'
    };
  }
  if (!ledger.batch_row_count) {
    return {
      label: 'missing_ledger_batch_rows',
      detail: 'No batch-type Outcome_Ledger rows were found for this batch_id.',
      next_step: 'Audit whether historical batch predictions exist or need a derived rebuild/backfill.'
    };
  }
  if (!ledger.batch_scored_count) {
    return {
      label: 'batch_rows_present_but_unscored',
      detail: 'Batch Outcome_Ledger rows exist, but none are scored.',
      next_step: 'Audit market reaction scoring coverage for batch rows before split-design work.'
    };
  }
  if (!ev.row_count) {
    return {
      label: 'missing_evaluation_batch_compare',
      detail: 'Scored batch rows exist, but Evaluation_BatchCompare has no comparison row.',
      next_step: 'Rebuild or audit evaluation comparison coverage for this batch.'
    };
  }
  if (!ev.scored_count) {
    return {
      label: 'evaluation_batch_compare_unscored',
      detail: 'Evaluation_BatchCompare row exists, but batch_overall_ok is blank.',
      next_step: 'Audit why comparison rows lack batch outcome fields.'
    };
  }
  return {
    label: 'unknown_missing_baseline',
    detail: 'Baseline is missing in counterfactual source despite available coverage signals.',
    next_step: 'Inspect source row mapping between Batch_Splitting_Candidates and Batch_Split_Counterfactuals.'
  };
}

function _batchBaselineSummaryLabel_(summary) {
  if (summary.missing_ledger_batch >= summary.missing_baseline && summary.missing_baseline) return 'missing_ledger_batch_rows_dominant';
  if (summary.ledger_unscored_batch >= summary.missing_baseline && summary.missing_baseline) return 'unscored_batch_rows_dominant';
  if (summary.missing_eval_compare >= summary.missing_baseline && summary.missing_baseline) return 'missing_evaluation_compare_dominant';
  if (summary.missing_baseline) return 'mixed_coverage_gap';
  return 'baseline_coverage_ok';
}

function _batchBaselineSummaryNextStep_(summary) {
  if (!summary.missing_baseline) {
    return 'Baseline coverage is available; evaluate whether split-proxy evidence is stable enough for a future true shadow split-group design.';
  }
  return 'Improve or audit scored batch baseline coverage before live batch-splitting design.';
}

function _sortBatchBaselineCoverageAuditRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    var at = String(a[idx.row_type] || '');
    var bt = String(b[idx.row_type] || '');
    if (at !== bt) return at === 'coverage_summary' ? 1 : (bt === 'coverage_summary' ? -1 : at.localeCompare(bt));
    return Number(a[idx.audit_rank] || 999999) - Number(b[idx.audit_rank] || 999999);
  });
}

function _buildBatchSplitGroupCounterfactualRows_(generatedTs, sources, warnings) {
  var counter = sources.counterfactuals || { rows: [], idx: {} };
  var groupMap = _batchSplitLedgerFamilyGroups_(sources.ledger);
  var rowsOut = [];
  for (var i = 0; i < (counter.rows || []).length; i++) {
    var row = counter.rows[i];
    var batchId = String(_predValue_(row, counter.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    var groups = groupMap[batchId] || {};
    var best = _batchSplitBestFamilyGroup_(groups);
    var batchRate = _numOrNull_(_predValue_(row, counter.idx, 'baseline_batch_overall_ok_rate'));
    var bestMemberRate = _numOrNull_(_predValue_(row, counter.idx, 'split_proxy_overall_ok_rate'));
    var groupRate = best ? best.overall_ok_rate : null;
    var groupDelta = (batchRate != null && groupRate != null) ? _roundRate_(groupRate - batchRate) : '';
    var memberDelta = (bestMemberRate != null && groupRate != null) ? _roundRate_(groupRate - bestMemberRate) : '';
    var label = _batchSplitGroupCounterfactualLabel_(batchRate, groupRate, memberDelta);
    rowsOut.push([
      generatedTs,
      '',
      batchId,
      _predValue_(row, counter.idx, 'release_ts'),
      _predValue_(row, counter.idx, 'family_combo_key'),
      batchRate == null ? '' : batchRate,
      bestMemberRate == null ? '' : bestMemberRate,
      best ? best.family : '',
      best ? best.member_count : '',
      best ? best.scored_count : '',
      groupRate == null ? '' : groupRate,
      best ? _keysSorted_(best.event_ids).join('|') : '',
      best ? _keysSorted_(best.indicator_names).join('|') : '',
      _batchSplitFamilyGroupRatesString_(groups),
      groupDelta,
      memberDelta,
      label,
      label === 'family_group_helped' ? 'TRUE' : 'FALSE',
      label === 'family_group_hurt_vs_best_member' ? 'TRUE' : 'FALSE',
      _batchSplitGroupEvidenceStrength_(label, best, groupDelta),
      'shadow_only',
      _batchSplitGroupActivationBlocker_(label),
      'True shadow family-group counterfactual using existing scored member rows; not trading advice and not live batch splitting.'
    ]);
  }
  rowsOut.sort(function(a, b) {
    var h = _batchSplitGroupCounterfactualsHeaders_();
    var idx = _headerIndexMap_(h);
    var ad = _numOrNull_(a[idx.group_vs_batch_delta]);
    var bd = _numOrNull_(b[idx.group_vs_batch_delta]);
    if (ad != null && bd != null && ad !== bd) return bd - ad;
    return String(a[idx.batch_id] || '').localeCompare(String(b[idx.batch_id] || ''));
  });
  for (var r = 0; r < rowsOut.length; r++) rowsOut[r][1] = r + 1;
  if (!rowsOut.length && warnings) warnings.push('no_counterfactual_rows_from:Batch_Split_Counterfactuals');
  return rowsOut;
}

function _batchSplitLedgerFamilyGroups_(source) {
  var map = {};
  if (!source || !source.rows) return map;
  for (var i = 0; i < source.rows.length; i++) {
    var row = source.rows[i];
    var type = String(_predValue_(row, source.idx, 'type') || '').trim().toLowerCase();
    if (type === 'batch') continue;
    var batchId = String(_predValue_(row, source.idx, 'batch_id') || '').trim();
    if (!batchId) continue;
    var family = _familyStructureRowFamily_(row, source.idx);
    if (!map[batchId]) map[batchId] = {};
    if (!map[batchId][family]) {
      map[batchId][family] = {
        family: family,
        rows_total: 0,
        scored_count: 0,
        overall_ok_count: 0,
        event_ids: {},
        indicator_names: {}
      };
    }
    var g = map[batchId][family];
    var eventId = String(_predValue_(row, source.idx, 'event_id') || '').trim();
    var name = String(_predValue_(row, source.idx, 'indicator_name') || '').trim();
    g.rows_total += 1;
    if (eventId) g.event_ids[eventId] = true;
    if (name) g.indicator_names[name] = true;
    if (_isTrueCell_(_predValue_(row, source.idx, 'scored_flag'))) {
      g.scored_count += 1;
      if (_isTrueCell_(_predValue_(row, source.idx, 'overall_ok'))) g.overall_ok_count += 1;
    }
  }
  Object.keys(map).forEach(function(batchId) {
    Object.keys(map[batchId]).forEach(function(family) {
      var g = map[batchId][family];
      g.member_count = Object.keys(g.event_ids).length;
      g.overall_ok_rate = g.scored_count ? _roundRate_(g.overall_ok_count / g.scored_count) : null;
    });
  });
  return map;
}

function _batchSplitBestFamilyGroup_(groups) {
  var best = null;
  Object.keys(groups || {}).forEach(function(family) {
    var g = groups[family];
    if (g.overall_ok_rate == null) return;
    if (!best || g.overall_ok_rate > best.overall_ok_rate ||
        (g.overall_ok_rate === best.overall_ok_rate && g.scored_count > best.scored_count)) {
      best = g;
    }
  });
  return best;
}

function _batchSplitFamilyGroupRatesString_(groups) {
  return Object.keys(groups || {}).sort().map(function(family) {
    var g = groups[family];
    return family + ':rate=' + (g.overall_ok_rate == null ? 'n/a' : g.overall_ok_rate) +
      ',scored=' + g.scored_count +
      ',members=' + g.member_count;
  }).join(' | ');
}

function _batchSplitGroupCounterfactualLabel_(batchRate, groupRate, memberDelta) {
  if (batchRate == null || groupRate == null) return 'inconclusive_missing_group_or_batch';
  if (groupRate <= batchRate) return 'family_group_not_better_than_batch';
  var md = _numOrNull_(memberDelta);
  if (md != null && md < 0) return 'family_group_hurt_vs_best_member';
  return 'family_group_helped';
}

function _batchSplitGroupEvidenceStrength_(label, best, groupDelta) {
  var d = _numOrNull_(groupDelta);
  if (label === 'family_group_helped' && best && best.scored_count >= 6 && d != null && d >= 0.3) return 'strong_group_shadow_evidence';
  if (label === 'family_group_helped') return 'moderate_group_shadow_evidence';
  if (label === 'family_group_hurt_vs_best_member') return 'possible_proxy_damage';
  return 'inconclusive';
}

function _batchSplitGroupActivationBlocker_(label) {
  if (label === 'family_group_helped') return 'needs_future_block_confirmation_and_design_spec';
  if (label === 'family_group_hurt_vs_best_member') return 'possible_damage_vs_best_member_proxy';
  return 'insufficient_group_or_batch_data';
}

function _sortBatchSplitGroupCounterfactualRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    var ar = Number(a[idx.group_counterfactual_rank] || 0);
    var br = Number(b[idx.group_counterfactual_rank] || 0);
    if (ar !== br) return ar - br;
    return _cmpByColumns_(a, b, [idx.release_ts, idx.batch_id]);
  });
}

function _sortAttentionShadowExperimentRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    return _cmpByColumns_(a, b, [
      idx.experiment_name,
      idx.release_ts,
      idx.outcome_family,
      idx.event_id,
      idx.candidate_provider,
      idx.candidate_factor
    ]);
  });
}

function _sortAttentionShadowSummaryRows_(headers, rows) {
  var idx = _headerIndexMap_(headers);
  rows.sort(function(a, b) {
    var aRows = Number(a[idx.rows_scored] || 0);
    var bRows = Number(b[idx.rows_scored] || 0);
    if (aRows !== bRows) return bRows - aRows;
    return _cmpByColumns_(a, b, [
      idx.experiment_name,
      idx.outcome_family,
      idx.candidate_provider,
      idx.candidate_factor
    ]);
  });
}

function buildAttentionPhase3CandidateRows_(reviewRows, reviewIdx, summaryRows, summaryIdx, generatedTs) {
  var evidenceMap = _buildAttentionPhase3EvidenceMap_(summaryRows, summaryIdx);
  var rowsOut = [];
  var seen = {};

  for (var i = 0; i < (reviewRows || []).length; i++) {
    var reviewRow = reviewRows[i];
    var usefulness = String(_predValue_(reviewRow, reviewIdx, 'usefulness_label') || '').trim();
    if (usefulness !== 'useful_disagreement' && usefulness !== 'possible_signal') continue;

    var winner = String(_predValue_(reviewRow, reviewIdx, 'winner_provider') || '').trim();
    if (!winner || winner === 'tie') continue;

    var family = String(_predValue_(reviewRow, reviewIdx, 'outcome_family') || '').trim() || 'other';
    var targetKey = String(_predValue_(reviewRow, reviewIdx, 'target_key') || '').trim();
    var winnerFactors = _attentionDisagreementWinnerFactors_(reviewRow, reviewIdx);
    var bestEvidence = _selectAttentionPhase3Evidence_(family, winner, winnerFactors, evidenceMap);
    if (!bestEvidence) continue;

    var candidateFactor = bestEvidence.attention_factor || '';
    var candidateKey = targetKey + '|' + winner + '|' + candidateFactor;
    if (seen[candidateKey]) continue;
    seen[candidateKey] = true;

    rowsOut.push([
      generatedTs,
      bestEvidence.summary_type,
      candidateKey,
      targetKey,
      String(_predValue_(reviewRow, reviewIdx, 'release_date') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'release_ts') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'event_id') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'batch_id') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'type') || ''),
      family,
      String(_predValue_(reviewRow, reviewIdx, 'indicator_name') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'country') || ''),
      winner,
      candidateFactor,
      String(_predValue_(reviewRow, reviewIdx, 'disagreement_kind') || ''),
      usefulness,
      String(_predValue_(reviewRow, reviewIdx, 'score_spread') || ''),
      String(_predValue_(reviewRow, reviewIdx, 'pips_spread') || ''),
      bestEvidence.rows_total == null ? '' : bestEvidence.rows_total,
      bestEvidence.useful_rows == null ? '' : bestEvidence.useful_rows,
      bestEvidence.diagnostic_level || '',
      _attentionPhase3CandidateSummary_(family, winner, candidateFactor, bestEvidence),
      _attentionPhase3CandidateHint_(bestEvidence),
      'candidate_only',
      'Phase 3 candidate review only; not trading advice.'
    ]);
  }

  return rowsOut;
}

function _buildAttentionPhase3EvidenceMap_(summaryRows, summaryIdx) {
  var out = {};
  for (var i = 0; i < (summaryRows || []).length; i++) {
    var row = summaryRows[i];
    var summaryType = String(_predValue_(row, summaryIdx, 'summary_type') || '').trim();
    if (summaryType !== 'family_winner_factor' && summaryType !== 'family_winner' && summaryType !== 'winner_factor') {
      continue;
    }

    var level = String(_predValue_(row, summaryIdx, 'diagnostic_level') || '').trim();
    var rowsTotal = Number(_predValue_(row, summaryIdx, 'rows_total') || 0);
    var usefulRows = Number(_predValue_(row, summaryIdx, 'useful_disagreement_count') || 0) +
      Number(_predValue_(row, summaryIdx, 'possible_signal_count') || 0);
    if (level !== 'useful_pattern' || rowsTotal < 5 || usefulRows < 4) continue;

    var family = String(_predValue_(row, summaryIdx, 'outcome_family') || '').trim() || 'other';
    var winner = String(_predValue_(row, summaryIdx, 'winner_provider') || '').trim();
    var factor = String(_predValue_(row, summaryIdx, 'attention_factor') || '').trim();
    var key = summaryType + '|' + family + '|' + winner + '|' + factor;
    out[key] = {
      summary_type: summaryType,
      outcome_family: family,
      winner_provider: winner,
      attention_factor: factor,
      rows_total: rowsTotal,
      useful_rows: usefulRows,
      diagnostic_level: level
    };
  }
  return out;
}

function _selectAttentionPhase3Evidence_(family, winner, winnerFactors, evidenceMap) {
  var factors = (winnerFactors && winnerFactors.length) ? winnerFactors : [''];
  var candidates = [];
  for (var i = 0; i < factors.length; i++) {
    var factor = factors[i] || '';
    _maybePushAttentionPhase3Evidence_(candidates, evidenceMap['family_winner_factor|' + family + '|' + winner + '|' + factor], 1);
    _maybePushAttentionPhase3Evidence_(candidates, evidenceMap['winner_factor|' + 'other' + '|' + winner + '|' + factor], 3);
  }
  _maybePushAttentionPhase3Evidence_(candidates, evidenceMap['family_winner|' + family + '|' + winner + '|'], 2);

  if (!candidates.length) return null;
  candidates.sort(function(a, b) {
    if (a.rank !== b.rank) return a.rank - b.rank;
    if (a.evidence.useful_rows !== b.evidence.useful_rows) return b.evidence.useful_rows - a.evidence.useful_rows;
    return b.evidence.rows_total - a.evidence.rows_total;
  });
  return candidates[0].evidence;
}

function _maybePushAttentionPhase3Evidence_(list, evidence, rank) {
  if (!evidence) return;
  list.push({ evidence: evidence, rank: rank });
}

function _attentionPhase3CandidateSummary_(family, winner, factor, evidence) {
  var parts = [
    'Repeated useful disagreement pattern',
    'family=' + family,
    'winner=' + winner
  ];
  if (factor) parts.push('factor=' + factor);
  if (evidence && evidence.useful_rows != null && evidence.rows_total != null) {
    parts.push('evidence=' + evidence.useful_rows + '/' + evidence.rows_total);
  }
  return parts.join('; ') + '.';
}

function _attentionPhase3CandidateHint_(evidence) {
  var summaryType = evidence && evidence.summary_type ? evidence.summary_type : '';
  if (summaryType === 'family_winner_factor') {
    return 'In a later shadow comparison, inspect whether this family-plus-factor disagreement slice stays consistently useful before any behavior change.';
  }
  if (summaryType === 'family_winner') {
    return 'In a later shadow comparison, inspect whether this provider keeps winning disagreement cases for the same family before any behavior change.';
  }
  return 'In a later shadow comparison, inspect whether this provider-plus-factor disagreement slice persists before any behavior change.';
}

function _uniqueStrings_(items) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (items || []).length; i++) {
    var item = String(items[i] || '').trim();
    if (!item || seen[item]) continue;
    seen[item] = true;
    out.push(item);
  }
  return out;
}

function _rateRaw_(num, den) {
  var numerator = Number(num || 0);
  var denominator = Number(den || 0);
  if (!(denominator > 0)) return 0;
  return numerator / denominator;
}

function _countMapToString_(map) {
  return _topCountMapItems_(map, 20).map(function(item) {
    return item.key + '=' + item.count;
  }).join(', ');
}

function _topCountMapItems_(map, limit) {
  var items = [];
  Object.keys(map || {}).forEach(function(key) {
    items.push({ key: key, count: Number(map[key] || 0) });
  });
  items.sort(function(a, b) {
    if (a.count !== b.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return items.slice(0, limit || items.length);
}

function _providerCharacterTargetKey_(row, idx) {
  var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
  var batchId = String(_predValue_(row, idx, 'batch_id') || '').trim();
  var rowType = String(_predValue_(row, idx, 'type') || '').trim().toLowerCase();
  var releaseTs = String(_predValue_(row, idx, 'release_ts') || '').trim();
  if (rowType === 'batch' && batchId) return 'batch|' + batchId;
  if (eventId) return 'event|' + eventId;
  if (batchId) return 'batch|' + batchId;
  if (releaseTs) return 'release|' + releaseTs;
  return '';
}

function _isAttentionEraLedgerRow_(row, idx) {
  var version = String(_predValue_(row, idx, 'attention_schema_version') || '').trim();
  return version === '1.0' || version === '1';
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
