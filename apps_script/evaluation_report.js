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
    if (!evalTs && !realDir) continue;
    rowsOut.push(_buildEvaluationRow_(src, predIdx, generatedTs));
  }

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
    if (!_evaluationRowIsScored_(g.batch)) continue;

    var mode = String(g.batch[ridx.pre_signal_mode] || '').trim().toLowerCase();
    if (mode !== 'scenario') continue;
    var watchIds = _splitEvaluationPipeList_(g.batch[ridx.watch_member_event_ids]);
    var watchNames = _splitEvaluationPipeList_(g.batch[ridx.watch_member_indicator_names]);

    var scenarioMembers = _evaluationRelevantMembers_(g.batch, g.members, ridx);
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

function _isTrueCell_(v) {
  return String(v || '').trim().toUpperCase() === 'TRUE';
}

function _numOrZero_(v) {
  var n = Number(v);
  return isFinite(n) ? n : 0;
}

function _boolScore_(v) {
  return _isTrueCell_(v) ? 1 : 0;
}

function _roundRate_(v) {
  return Math.round(v * 10000) / 10000;
}

function _round2_(v) {
  return Math.round(v * 100) / 100;
}
