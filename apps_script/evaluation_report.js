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
      'Evaluation rows=' + (res.rows_written || 0) + ' | summary=' + (res.summary_written || 0),
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

  var rowHeaders = _evaluationRowHeaders_();
  var summaryHeaders = _evaluationSummaryHeaders_();
  var batchCompareHeaders = _evaluationBatchCompareHeaders_();

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

  _rewriteSheet_(rowSheet, rowHeaders, rowsOut);
  _rewriteSheet_(summarySheet, summaryHeaders, summaryOut);
  _rewriteSheet_(batchCompareSheet, batchCompareHeaders, batchCompareOut);

  return {
    row_sheet: rowSheet.getName(),
    summary_sheet: summarySheet.getName(),
    batch_compare_sheet: batchCompareSheet.getName(),
    rows_written: rowsOut.length,
    summary_written: summaryOut.length,
    batch_compare_written: batchCompareOut.length
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
    'mr_compare_status',
    'mr_compare_note',
    'eval_ts',
    'trace_prediction_key'
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
    'realized_pips'
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
    _predValue_(src, idx, 'mr_compare_status'),
    _predValue_(src, idx, 'mr_compare_note'),
    _predValue_(src, idx, 'eval_ts'),
    eventId + '|' + aiName + '|' + predictionId
  ];
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

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var type = String(row[7] || '').toLowerCase();
    var batchId = String(row[4] || '').trim();
    var aiName = String(row[13] || '').trim();
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

    var best = g.members[0];
    var bestScore = _evaluationCompareScore_(best);
    for (var m = 1; m < g.members.length; m++) {
      var candidate = g.members[m];
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

    out.push([
      generatedTs,
      g.batch[1],
      g.batch[2],
      g.batch[4],
      g.batch[13],
      g.members.length,
      g.batch[8],
      g.batch[22],
      g.batch[23],
      g.batch[24],
      g.batch[25],
      g.batch[29],
      g.batch[30],
      g.batch[31],
      g.batch[32],
      best[3],
      best[8],
      best[10],
      best[11],
      best[22],
      best[23],
      best[24],
      best[25],
      best[29],
      best[30],
      best[31],
      best[32],
      winner,
      winnerReason,
      g.batch[26],
      g.batch[27],
      g.batch[33]
    ]);
  }

  return out;
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
