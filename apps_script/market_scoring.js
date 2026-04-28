/**************  Minimal market reaction scorer (USD/JPY)  **************/

function _getMarketReactionHorizonMin_(cfg) {
  var raw = cfg && cfg['MR_HORIZON_MIN'];
  var n = Number(raw);
  if (!isFinite(n)) n = 15;
  n = Math.floor(n);
  if (n < 1) n = 1;
  if (n > 15) n = 15;
  return n;
}

function _getMarketReactionAnchorMinAbsMovePips_(cfg) {
  var raw = cfg && cfg['MR_ANCHOR_MIN_ABS_MOVE_PIPS'];
  var n = Number(raw);
  if (!isFinite(n)) n = 3;
  n = Math.round(n * 100) / 100;
  if (n < 0.5) n = 0.5;
  if (n > 20) n = 20;
  return n;
}

function _getMarketReactionAnchorLookbackMin_(cfg) {
  var raw = cfg && cfg['MR_ANCHOR_LOOKBACK_MIN'];
  var n = Number(raw);
  if (!isFinite(n)) n = 1;
  n = Math.floor(n);
  if (n < 0) n = 0;
  if (n > 15) n = 15;
  return n;
}

function _getMarketReactionAnchorLookaheadMin_(cfg) {
  var raw = cfg && cfg['MR_ANCHOR_LOOKAHEAD_MIN'];
  var n = Number(raw);
  if (!isFinite(n)) n = 5;
  n = Math.floor(n);
  if (n < 0) n = 0;
  if (n > 15) n = 15;
  return n;
}

function _getMarketReactionFlatMaxAbsPips_(cfg) {
  var raw = cfg && cfg['MR_FLAT_MAX_ABS_PIPS'];
  var n = Number(raw);
  if (!isFinite(n)) n = 1;
  n = Math.round(n * 100) / 100;
  if (n < 0) n = 0;
  if (n > 10) n = 10;
  return n;
}

function _getMarketReactionSkipAlreadyScored_(cfg) {
  return _mrConfigBoolean_(cfg && cfg['MR_SKIP_ALREADY_SCORED'], false);
}

function _roundUsdJpyPips_(diff) {
  return Math.round((diff * 100) * 100) / 100;
}

function _detectMarketReactionAnchor_(candles, releaseTsUtc, baselinePrice, cfg) {
  if (!candles || !candles.length || !_validDate_(releaseTsUtc) || !isFinite(baselinePrice)) {
    return { detected: false };
  }

  var releaseMs = releaseTsUtc.getTime();
  var thresholdPips = _getMarketReactionAnchorMinAbsMovePips_(cfg);
  var lookbackMin = _getMarketReactionAnchorLookbackMin_(cfg);
  var lookaheadMin = _getMarketReactionAnchorLookaheadMin_(cfg);
  var windowFromMs = releaseMs - lookbackMin * 60 * 1000;
  var windowToMs = releaseMs + lookaheadMin * 60 * 1000;
  var candidates = [];

  function detectDirForCandle_(c) {
    if (!c) return 0;
    var upPips = isFinite(c.high) ? _roundUsdJpyPips_(c.high - baselinePrice) : -Infinity;
    var downAbsPips = isFinite(c.low) ? _roundUsdJpyPips_(baselinePrice - c.low) : -Infinity;
    var above = upPips >= thresholdPips;
    var below = downAbsPips >= thresholdPips;
    if (above && !below) return 1;
    if (below && !above) return -1;
    if (above && below) {
      var closePips = isFinite(c.close) ? _roundUsdJpyPips_(c.close - baselinePrice) : 0;
      if (closePips >= thresholdPips) return 1;
      if ((-closePips) >= thresholdPips) return -1;
      return 0;
    }
    return 0;
  }

  for (var i = 0; i < candles.length; i++) {
    var c = candles[i];
    var ms = c.ts.getTime();
    if (ms < windowFromMs || ms > windowToMs) continue;
    var dir = detectDirForCandle_(c);
    if (!dir) continue;
    candidates.push({
      ts: c.ts,
      candle: c,
      dir: dir,
      phase: (ms >= releaseMs) ? 'post' : 'pre',
      move_up_pips: isFinite(c.high) ? _roundUsdJpyPips_(c.high - baselinePrice) : '',
      move_down_pips: isFinite(c.low) ? _roundUsdJpyPips_(c.low - baselinePrice) : ''
    });
  }

  if (!candidates.length) {
    return {
      detected: false,
      threshold_pips: thresholdPips,
      lookback_min: lookbackMin,
      lookahead_min: lookaheadMin
    };
  }

  var chosen = null;
  for (var j = 0; j < candidates.length; j++) {
    if (candidates[j].phase === 'post') {
      chosen = candidates[j];
      break;
    }
  }
  if (!chosen) chosen = candidates[0];

  return {
    detected: true,
    ts: chosen.ts,
    candle: chosen.candle,
    dir: chosen.dir,
    phase: chosen.phase,
    threshold_pips: thresholdPips,
    lookback_min: lookbackMin,
    lookahead_min: lookaheadMin,
    move_up_pips: chosen.move_up_pips,
    move_down_pips: chosen.move_down_pips
  };
}

// Utility: fetch candles around event and compute realized move in pips.
function _computeUsdJpyMove_(releaseTsUtc, preMin, postMin, horizonMin, meta, cfg, providerOverride) {
  var out = (typeof getFxCandlesForWindowByProvider_ === 'function')
    ? getFxCandlesForWindowByProvider_(providerOverride || '', 'USD/JPY', releaseTsUtc, preMin||30, postMin||120)
    : getFxCandlesForWindow_('USD/JPY', releaseTsUtc, preMin||30, postMin||120);
  if (!out || !out.candles || !out.candles.length) {
    log_ && log_('scoring', 'no_candles', {
      provider_chain: out && out.provider,
      t0: releaseTsUtc && releaseTsUtc.toISOString(),
      event_id: meta && meta.event_id,
      row_index: meta && meta.row_index,
      source: meta && meta.source
    });
    return {
      status: 'no_candles',
      provider: out && out.provider ? out.provider : '',
      provider_meta_json: (out && out.meta) ? JSON.stringify(out.meta) : '',
      candle_count: 0
    };
  }

  // t0 price = closest candle at/just before release time
  var releaseMs = releaseTsUtc.getTime();
  var base = _nearestAtOrBefore_(out.candles, releaseMs);
  if (!base) return { status: 'no_base' };

  var baselinePrice = base.close;
  if (!isFinite(baselinePrice)) return { status: 'bad_prices' };

  var anchor = _detectMarketReactionAnchor_(out.candles, releaseTsUtc, baselinePrice, cfg || {});
  var horizon = horizonMin || 15;
  var t0ms = anchor && anchor.detected ? anchor.ts.getTime() : releaseMs;
  var t0Candle = anchor && anchor.detected ? anchor.candle : base;
  var p0 = (t0Candle && isFinite(t0Candle.open)) ? t0Candle.open : baselinePrice;
  if (!isFinite(p0)) p0 = baselinePrice;
  var horizonMs = t0ms + horizon*60*1000;
  var h = _nearestAtOrBefore_(out.candles, horizonMs) || out.candles[out.candles.length-1];
  var horizonCandles = out.candles.filter(function(c) {
    var ms = c.ts.getTime();
    return ms >= t0ms && ms <= horizonMs;
  });

  var maxHigh = p0;
  var minLow = p0;
  for (var i = 0; i < horizonCandles.length; i++) {
    var hc = horizonCandles[i];
    if (isFinite(hc.high) && hc.high > maxHigh) maxHigh = hc.high;
    if (isFinite(hc.low) && hc.low < minLow) minLow = hc.low;
  }
  var maxUpPips = _roundUsdJpyPips_(maxHigh - p0);
  var maxDownPips = _roundUsdJpyPips_(minLow - p0);

  var p1 = h && isFinite(h.close) ? h.close : p0;
  if (!isFinite(p1)) return { status: 'bad_prices' };
  var diff = p1 - p0;
  var pips = _roundUsdJpyPips_(diff);
  var flatThresholdPips = _getMarketReactionFlatMaxAbsPips_(cfg || {});
  var dir  = _dirSignForPips_(pips, flatThresholdPips);
  var realizedSustainMin = _computeRealizedSustainMin_(out.candles, t0ms, p0, horizon, maxUpPips, maxDownPips);

  if (!(anchor && anchor.detected)) {
    p1 = p0;
    pips = 0;
    dir = 0;
    realizedSustainMin = 0;
  }

  var res = {
    status: (anchor && anchor.detected) ? 'ok' : 'flat',
    provider: out.provider,
    provider_meta_json: out && out.meta ? JSON.stringify(out.meta) : '',
    candle_count: out && out.candles ? out.candles.length : 0,
    t0_ts: t0Candle && _validDate_(t0Candle.ts) ? t0Candle.ts : releaseTsUtc,
    tH_ts: (anchor && anchor.detected) ? h.ts : (t0Candle && _validDate_(t0Candle.ts) ? t0Candle.ts : releaseTsUtc),
    t0_price: p0,
    tH_price: p1,
    horizon_min: horizon,
    pips: pips,
    dir: dir,
    max_up_pips: maxUpPips,
    max_down_pips: maxDownPips,
    realized_sustain_min: realizedSustainMin,
    flat_threshold_pips: flatThresholdPips,
    anchor_detected: !!(anchor && anchor.detected),
    anchor_phase: anchor && anchor.phase ? anchor.phase : '',
    anchor_threshold_pips: anchor && isFinite(anchor.threshold_pips) ? anchor.threshold_pips : '',
    anchor_lookback_min: anchor && isFinite(anchor.lookback_min) ? anchor.lookback_min : '',
    anchor_lookahead_min: anchor && isFinite(anchor.lookahead_min) ? anchor.lookahead_min : ''
  };

  // Attach event-related metadata if provided
  if (meta && typeof meta === 'object') {
    for (var k in meta) {
      if (meta.hasOwnProperty(k) && res[k] === undefined) {
        res[k] = meta[k];
      }
    }
  }

  log_ && log_('scoring', 'computed_move', res);
  return res;
}

function _nearestAtOrBefore_(candles, targetMs) {
  var best=null, bestDt=-Infinity;
  for (var i=0;i<candles.length;i++){
    var c=candles[i]; var ms=c.ts.getTime();
    if (ms<=targetMs && ms>bestDt){ best=c; bestDt=ms; }
  }
  return best;
}

function _computeRealizedSustainMin_(candles, t0ms, startPrice, horizonMin, maxUpPips, maxDownPips) {
  if (!candles || !candles.length || !isFinite(startPrice)) return '';

  var dominantPips = 0;
  if (Math.abs(maxUpPips) > Math.abs(maxDownPips)) dominantPips = maxUpPips;
  else if (Math.abs(maxDownPips) > Math.abs(maxUpPips)) dominantPips = maxDownPips;
  var dominantDir = _dirSign_(dominantPips);
  var dominantAbs = Math.abs(Number(dominantPips));
  if (dominantDir === 0 || dominantAbs < 1) return 0;

  var analysisMaxMin = Math.max(Number(horizonMin || 0), 60);
  var cutoffMs = t0ms + analysisMaxMin * 60 * 1000;
  // Event reactions often retrace sharply; sustain should reflect whether the
  // direction stayed valid, not whether most of the opening spike was retained.
  var directionalFloorPips = 1;
  var maxGraceBreaks = 2;
  var lastValidMin = 0;
  var sawValid = false;
  var consecutiveInvalid = 0;

  for (var i = 0; i < candles.length; i++) {
    var c = candles[i];
    var ms = c.ts.getTime();
    if (ms < t0ms || ms > cutoffMs || !isFinite(c.close)) continue;

    var movePips = Math.round((c.close - startPrice) * 100 * 100) / 100;
    var sameDirPips = movePips * dominantDir;
    if (sameDirPips >= directionalFloorPips) {
      lastValidMin = Math.round((ms - t0ms) / 60000);
      sawValid = true;
      consecutiveInvalid = 0;
    } else if (sawValid) {
      consecutiveInvalid++;
      if (consecutiveInvalid >= maxGraceBreaks) break;
    }
  }

  return sawValid ? lastValidMin : 0;
}

// Menu worker: compute move for last 24h released events (dry-run; logs only).
function scoreMarketReactionPast24h_() {
  var ss = SpreadsheetApp.getActive();
  var EVENT = ss.getSheetByName(CFG && CFG.SHEET_EVENT ? CFG.SHEET_EVENT : 'Event');
  if (!EVENT) throw new Error('Event sheet missing');
  var headers = getHeaderNames(EVENT);
  var idx = {};
  headers.forEach(function(h,i){ idx[h]=i; });
  var eventIdCol = ('event_id' in idx) ? idx['event_id'] : null;

  var data = EVENT.getRange(2,1, Math.max(0, EVENT.getLastRow()-1), EVENT.getLastColumn()).getValues();
  var now = new Date();
  var since = new Date(now.getTime() - 24*60*60*1000);

  var releaseTsCol = ('released_ts' in idx) ? idx['released_ts'] : ('release_ts' in idx ? idx['release_ts'] : null);
  if (releaseTsCol === null) { throw new Error('Event sheet missing released_ts / release_ts'); }
  var predCtx = _preparePredictionEvalContext_();
  var auditCtx = _prepareMarketReactionAuditContext_();
  var cfg = _readConfigMap_('Config');
  var horizonMin = _getMarketReactionHorizonMin_(cfg);
  var anchorMinAbsMovePips = _getMarketReactionAnchorMinAbsMovePips_(cfg);
  var anchorLookbackMin = _getMarketReactionAnchorLookbackMin_(cfg);
  var anchorLookaheadMin = _getMarketReactionAnchorLookaheadMin_(cfg);
  var flatMaxAbsPips = _getMarketReactionFlatMaxAbsPips_(cfg);
  var skipAlreadyScored = _getMarketReactionSkipAlreadyScored_(cfg);

  var count = 0, skippedAlreadyScored = 0;
  for (var r=0; r<data.length; r++){
    var row = data[r];
    var ts = row[releaseTsCol];
    if (!(ts instanceof Date)) continue;
    if (ts < since || ts > now) continue;

    var eventId = (eventIdCol !== null) ? row[eventIdCol] : null;
    var eventMeta = _buildEventEvalMeta_(row, idx, ts);
    if (skipAlreadyScored && _predictionEventHasMarketReaction_(predCtx, eventId)) {
      skippedAlreadyScored++;
      continue;
    }

    var scoring = _computeMarketReactionWithFallbacks_(ts, horizonMin, {
      event_id: eventId,
      row_index: r + 2,           // +2 because row 1 = headers, we started at row 2
      source: 'past24h'
    }, cfg, eventMeta, auditCtx);
    var reaction = scoring.reaction;
    var compareReactions = scoring.compareReactions || [];
    var finalSelection = scoring.finalSelection;
    _applyEvaluationToPredictions_(predCtx, eventMeta, finalSelection.reaction || reaction);
    if (compareReactions.length) {
      _applyComparisonToPredictions_(predCtx, eventMeta, reaction, compareReactions, finalSelection);
    }
    count++;
  }

  _flushPredictionEvalContext_(predCtx);
  _flushMarketReactionAuditContext_(auditCtx);
  appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(past24h)', {
    checked_events: count,
    horizon_min: horizonMin,
    anchor_min_abs_move_pips: anchorMinAbsMovePips,
    anchor_lookback_min: anchorLookbackMin,
    anchor_lookahead_min: anchorLookaheadMin,
    flat_max_abs_pips: flatMaxAbsPips,
    skip_already_scored: skipAlreadyScored,
    skipped_already_scored: skippedAlreadyScored
  });
  if (typeof flushLogs_ === 'function') flushLogs_();
}


/**************  tiny helper  **************/

// Finds the event sheet by config or common fallbacks.
function _getEventSheet_() {
  var ss = SpreadsheetApp.getActive();
  var nameFromCfg = (CFG && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : null;
  var candidates = [];
  if (nameFromCfg) candidates.push(String(nameFromCfg));
  candidates.push('Event', 'Events', 'RawCalendar', 'RawCaldendar'); // common variants

  for (var i = 0; i < candidates.length; i++) {
    var sh = ss.getSheetByName(candidates[i]);
    if (!sh) continue;
    // quick sanity: must have headers row and at least one col
    if (sh.getLastRow() >= 1 && sh.getLastColumn() >= 1) return sh;
  }
  return null;
}

// Case-insensitive header index map (e.g., m['release_ts'] -> 7).
function _indexByHeaderInsensitive_(headers) {
  var m = {};
  for (var i = 0; i < headers.length; i++) {
    var k = String(headers[i] || '').trim().toLowerCase();
    if (!k) continue;
    m[k] = i;
  }
  return m;
}

// Accepts Date OR string (ISO, "YYYY-MM-DD HH:mm", or locale string with GMT offset).
// If plain "YYYY-MM-DD HH:mm" without zone, interpret in given tz and convert to UTC.
function _parseEventTsFlexible_(val, tz) {
  if (val instanceof Date && isFinite(val.getTime())) return new Date(val.getTime());
  var s = String(val || '').trim();
  if (!s) return new Date(NaN);

  // Try native Date (handles "Wed Jan 01 2025 09:00:00 GMT+0900" etc.)
  var d = new Date(s);
  if (isFinite(d.getTime())) return d;

  // Try strict local wall-clock form
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (m) {
    var wall = m[1] + '-' + m[2] + '-' + m[3] + ' ' + m[4] + ':' + m[5]; // drop seconds to match parser
    return _parseLocalToUtc_(wall, tz || 'UTC');
  }

  return new Date(NaN);
}


/**************  Config-driven window scoring (USD/JPY)  **************/

function scoreMarketReactionByConfigWindow_() {
  var cfg = _readConfigMap_('Config');
  if (!cfg || String(cfg['MR_WINDOW_ENABLED']).toUpperCase() !== 'TRUE') {
    appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(config)', { status: 'skipped', reason: 'MR_WINDOW_ENABLED != TRUE' });
    return;
  }

  var tz  = String(cfg['MR_WINDOW_TZ'] || '').trim();
  var fromLocal = cfg['MR_WINDOW_FROM_LOCAL'];
  var toLocal   = cfg['MR_WINDOW_TO_LOCAL'];

  if (!tz || fromLocal == null || toLocal == null || String(fromLocal).trim() === '' || String(toLocal).trim() === '') {
    appendLog(getSheet(CFG.SHEET_LOG), 'ERROR', 'ScoreMarketReaction(config)', {
      status: 'missing_mr_window_config',
      required_keys: ['MR_WINDOW_ENABLED', 'MR_WINDOW_FROM_LOCAL', 'MR_WINDOW_TO_LOCAL', 'MR_WINDOW_TZ']
    });
    throw new Error('Missing required Market Reaction config. Set MR_WINDOW_ENABLED, MR_WINDOW_FROM_LOCAL, MR_WINDOW_TO_LOCAL, and MR_WINDOW_TZ.');
  }

  var fromUtc = _parseLocalToUtc_(fromLocal, tz);
  var toUtc   = _parseLocalToUtc_(toLocal, tz);
  if (!(fromUtc instanceof Date) || isNaN(fromUtc.getTime()) || !(toUtc instanceof Date) || isNaN(toUtc.getTime())) {
    appendLog(getSheet(CFG.SHEET_LOG), 'ERROR', 'ScoreMarketReaction(config)', {
      status: 'parse_error',
      fromLocal: String(fromLocal),
      toLocal: String(toLocal),
      tz: tz,
      expected_format: 'YYYY-MM-DD HH:mm'
    });
    throw new Error('Invalid Market Reaction window config. Use MR_WINDOW_FROM_LOCAL / MR_WINDOW_TO_LOCAL in YYYY-MM-DD HH:mm format.');
  }

  var EVENT = _getEventSheet_();
  if (!EVENT) throw new Error('Event/RawCalendar sheet not found');
  var headers = getHeaderNames(EVENT);
  var idxMap = _indexByHeaderInsensitive_(headers);
  var eventIdCol = idxMap['event_id'];

  // accept 'released_ts' or 'release_ts' (case-insensitive)
  var releaseTsCol = idxMap['released_ts'];
  if (releaseTsCol === undefined) releaseTsCol = idxMap['release_ts'];
  if (releaseTsCol === undefined) throw new Error('No released_ts / release_ts column on Event sheet');

  var values = EVENT.getRange(2, 1, Math.max(0, EVENT.getLastRow()-1), EVENT.getLastColumn()).getValues();
  var predCtx = _preparePredictionEvalContext_();
  var auditCtx = _prepareMarketReactionAuditContext_();
  var horizonMin = _getMarketReactionHorizonMin_(cfg);
  var anchorMinAbsMovePips = _getMarketReactionAnchorMinAbsMovePips_(cfg);
  var anchorLookbackMin = _getMarketReactionAnchorLookbackMin_(cfg);
  var anchorLookaheadMin = _getMarketReactionAnchorLookaheadMin_(cfg);
  var flatMaxAbsPips = _getMarketReactionFlatMaxAbsPips_(cfg);
  var skipAlreadyScored = _getMarketReactionSkipAlreadyScored_(cfg);

  var checked = 0, totalRows = values.length, inWindow = 0, parsedOk = 0, skippedAlreadyScored = 0;
  for (var r = 0; r < values.length; r++) {
    var ts = _getEventReleaseTs_(values[r], idxMap, tz);
    if (!(ts instanceof Date) || isNaN(ts.getTime())) continue;
    parsedOk++;

    if (ts < fromUtc || ts > toUtc) continue;
    inWindow++;

    var eventId = (eventIdCol !== undefined) ? values[r][eventIdCol] : null;
    var eventMeta = _buildEventEvalMeta_(values[r], idxMap, ts);
    if (skipAlreadyScored && _predictionEventHasMarketReaction_(predCtx, eventId)) {
      skippedAlreadyScored++;
      continue;
    }

    var scoring = _computeMarketReactionWithFallbacks_(ts, horizonMin, {
      event_id: eventId,
      row_index: r + 2,           // again: +2 for header row + 1-based index
      source: 'config_window'
    }, cfg, eventMeta, auditCtx);
    var reaction = scoring.reaction;
    var compareReactions = scoring.compareReactions || [];
    var finalSelection = scoring.finalSelection;
    _applyEvaluationToPredictions_(predCtx, eventMeta, finalSelection.reaction || reaction);
    if (compareReactions.length) {
      _applyComparisonToPredictions_(predCtx, eventMeta, reaction, compareReactions, finalSelection);
    }
    checked++;

    if (checked >= 300) break; // safety cap
  }

  _flushPredictionEvalContext_(predCtx);
  _flushMarketReactionAuditContext_(auditCtx);
  appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(config)', {
    window_from_utc: fromUtc.toISOString(),
    window_to_utc: toUtc.toISOString(),
    horizon_min: horizonMin,
    anchor_min_abs_move_pips: anchorMinAbsMovePips,
    anchor_lookback_min: anchorLookbackMin,
    anchor_lookahead_min: anchorLookaheadMin,
    flat_max_abs_pips: flatMaxAbsPips,
    total_rows: totalRows,
    parsed_ts_rows: parsedOk,
    rows_in_window: inWindow,
    checked_events: checked,
    skip_already_scored: skipAlreadyScored,
    skipped_already_scored: skippedAlreadyScored
  });
  if (typeof flushLogs_ === 'function') flushLogs_();
}


/**************  Config + timezone helpers  **************/

function _readConfigMap_(sheetName) {
  var sh = getSheet(sheetName || 'Config');
  if (!sh) throw new Error('Config sheet not found');
  var last = sh.getLastRow();
  if (last < 2) return {};
  var rng = sh.getRange(2,1,last-1,2).getValues(); // key | value
  var m = {};
  for (var i=0;i<rng.length;i++){
    var k = String(rng[i][0]||'').trim();
    if (!k) continue;
    m[k] = rng[i][1];
  }
  return m;
}

// Accepts a Date object OR a strict local wall-clock string "YYYY-MM-DD HH:mm".
// Returns a UTC Date (same absolute instant).
function _parseLocalToUtc_(val, tz) {
  // Case A: Already a Date -> it's an absolute instant; return a copy.
  if (val instanceof Date && isFinite(val.getTime())) {
    return new Date(val.getTime());
  }

  var s = String(val || '').trim();

  // Strict "YYYY-MM-DD HH:mm" in a specific timezone
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})$/);
  if (m) {
    var y  = Number(m[1]), mo = Number(m[2]) - 1, day = Number(m[3]);
    var hh = Number(m[4]), mi = Number(m[5]);
    // Build a wall-clock in the given TZ, then translate to UTC using the zone offset at that instant.
    var pseudoUtc = new Date(Date.UTC(y, mo, day, hh, mi, 0));
    var z = Utilities.formatDate(pseudoUtc, tz || 'UTC', 'Z'); // e.g., "+0900"
    var sign = z[0] === '-' ? -1 : 1;
    var offMin = sign * (Number(z.substr(1,2)) * 60 + Number(z.substr(3,2)));
    return new Date(pseudoUtc.getTime() - offMin * 60 * 1000);
  }

  // If parsing failed, return an invalid date to trigger error handling upstream.
  return new Date(NaN);
}


// Try many common layouts to produce a UTC Date for each event row.
function _getEventReleaseTs_(row, idx, tz) {
  // 1) Direct timestamp columns (case-insensitive names)
  var directCols = ['released_ts','release_ts','release_ts_utc','released_at','release_time_utc'];
  for (var i=0;i<directCols.length;i++){
    var c = directCols[i], j = idx[c];
    if (j !== undefined) {
      var ts = _coerceAnyToUtcDate_(row[j], tz);
      if (_validDate_(ts)) return ts;
    }
  }

  // 2) Combine date + time columns (e.g., 'release_date' + 'release_time' or 'release_time_local')
  var dateCol = idx['release_date'];
  if (dateCol === undefined) dateCol = idx['date'];
  var timeCol = idx['release_time_local'];
  if (timeCol === undefined) timeCol = idx['release_time'];
  if (dateCol !== undefined && timeCol !== undefined) {
    var dVal = row[dateCol], tVal = row[timeCol];
    var combo = _coerceDateAndTimeToUtc_(dVal, tVal, tz);
    if (_validDate_(combo)) return combo;
  }

  // 3) Fallback: look for any column with 'ts' in the name
  for (var k in idx) {
    if (!idx.hasOwnProperty(k)) continue;
    if (k.indexOf('ts') >= 0 || k.indexOf('time') >= 0) {
      var v = row[idx[k]];
      var t = _coerceAnyToUtcDate_(v, tz);
      if (_validDate_(t)) return t;
    }
  }

  return new Date(NaN);
}

function _coerceAnyToUtcDate_(val, tz) {
  // Already a Date?
  if (val instanceof Date && isFinite(val.getTime())) return new Date(val.getTime());

  // Numbers: could be Unix seconds, ms, or Excel/Sheets serial days.
  if (typeof val === 'number' && isFinite(val)) {
    // Heuristics:
    //  - >= 1e12   → ms since epoch
    //  - >= 1e9    → seconds since epoch
    //  - otherwise → Excel/Sheets serial (days since 1899-12-30)
    if (val >= 1e12) return new Date(val);
    if (val >= 1e9)  return new Date(val * 1000);
    // Excel/Sheets serial to ms
    var ms = (val - 25569) * 86400 * 1000;
    return new Date(ms);
  }

  // Strings
  var s = (val == null) ? '' : String(val).trim();
  if (!s) return new Date(NaN);

  // If the string contains an explicit zone (e.g., +0900, Z, JST), try native parse first.
  var d = new Date(s);
  if (isFinite(d.getTime())) return d;

  // Common “local wall-clock” patterns → interpret in tz, then convert to UTC.
  // 1) YYYY-MM-DD HH:mm(:ss)?
  var m = s.match(/^(\d{4})[-\/](\d{2})[-\/](\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (m) {
    var y  = Number(m[1]), mo = Number(m[2])-1, day = Number(m[3]);
    var hh = Number(m[4]), mi = Number(m[5]), ss = Number(m[6]||0);
    return _localPartsToUtc_(y, mo, day, hh, mi, ss, tz);
  }

  // 2) YYYY/MM/DD (no time) → assume 00:00 in tz
  var m2 = s.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
  if (m2) {
    var y2  = Number(m2[1]), mo2 = Number(m2[2])-1, d2 = Number(m2[3]);
    return _localPartsToUtc_(y2, mo2, d2, 0, 0, 0, tz);
  }

  // 3) Last resort: try Date again (covers some locale strings)
  var d2b = new Date(s);
  if (isFinite(d2b.getTime())) return d2b;

  return new Date(NaN);
}

function _coerceDateAndTimeToUtc_(dateVal, timeVal, tz) {
  // Date part
  var d = _coerceAnyToUtcDate_(dateVal, tz);
  if (!_validDate_(d)) return new Date(NaN);

  // Extract Y/M/D from that date in tz
  var y  = Number(Utilities.formatDate(d, tz || 'UTC', 'yyyy'));
  var mo = Number(Utilities.formatDate(d, tz || 'UTC', 'MM')) - 1;
  var day= Number(Utilities.formatDate(d, tz || 'UTC', 'dd'));

  // Time part → try number (e.g., Excel time fraction) or string like "09:30"
  var hh=0, mi=0, ss=0;

  if (typeof timeVal === 'number' && isFinite(timeVal)) {
    // Excel/Sheets time fraction of a day
    var totalSec = Math.round(timeVal * 86400);
    hh = Math.floor(totalSec / 3600);
    mi = Math.floor((totalSec % 3600) / 60);
    ss = totalSec % 60;
  } else if (timeVal instanceof Date && isFinite(timeVal.getTime())) {
    hh = Number(Utilities.formatDate(timeVal, tz || 'UTC', 'HH'));
    mi = Number(Utilities.formatDate(timeVal, tz || 'UTC', 'mm'));
    ss = Number(Utilities.formatDate(timeVal, tz || 'UTC', 'ss'));
  } else {
    var s = String(timeVal || '').trim();
    var m = s.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (m) {
      hh = Number(m[1]); mi = Number(m[2]); ss = Number(m[3]||0);
    } else {
      // If we can't parse time, assume midnight
      hh=0; mi=0; ss=0;
    }
  }

  return _localPartsToUtc_(y, mo, day, hh, mi, ss, tz);
}

function _localPartsToUtc_(y, mo, d, hh, mi, ss, tz) {
  var pseudoUtc = new Date(Date.UTC(y, mo, d, hh, mi, ss));
  var z = Utilities.formatDate(pseudoUtc, tz || 'UTC', 'Z'); // e.g., +0900
  var sign = z[0] === '-' ? -1 : 1;
  var offMin = sign * (Number(z.substr(1,2))*60 + Number(z.substr(3,2)));
  return new Date(pseudoUtc.getTime() - offMin*60*1000);
}

function _validDate_(dt) {
  return dt instanceof Date && isFinite(dt.getTime());
}

function _preparePredictionEvalContext_() {
  var predSheet = getSheet((CFG && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions');
  if (!predSheet) return null;

  var headers = (typeof _ensurePredHeaders_ === 'function') ? _ensurePredHeaders_(predSheet) : getHeaderNames(predSheet);
  var idx = (typeof _getPredHeaderIndex_ === 'function') ? _getPredHeaderIndex_(headers) : _indexByHeaderInsensitive_(headers);
  var lastRow = predSheet.getLastRow();
  var data = (lastRow >= 2) ? predSheet.getRange(2, 1, lastRow - 1, headers.length).getValues() : [];
  return {
    sheet: predSheet,
    headers: headers,
    idx: idx,
    data: data,
    dirty: {}
  };
}

function _predictionEventHasMarketReaction_(ctx, eventId) {
  if (!ctx || !ctx.data || !ctx.idx || !eventId) return false;
  var eventCol = ctx.idx['event_id'];
  if (eventCol == null) return false;

  var evalTsCol = ctx.idx['eval_ts'];
  var evalNoteCol = ctx.idx['eval_note'];
  var realizedPipsCol = ctx.idx['realized_pips'];
  var finalProviderCol = ctx.idx['mr_final_provider'];

  for (var r = 0; r < ctx.data.length; r++) {
    var row = ctx.data[r];
    if (String(row[eventCol] || '').trim() !== String(eventId || '').trim()) continue;

    var evalTs = evalTsCol == null ? '' : row[evalTsCol];
    var evalNote = evalNoteCol == null ? '' : row[evalNoteCol];
    var realizedPips = realizedPipsCol == null ? '' : row[realizedPipsCol];
    var finalProvider = finalProviderCol == null ? '' : row[finalProviderCol];

    if (String(finalProvider || '').trim()) return true;
    if (String(realizedPips || '').trim() !== '') return true;
    if (String(evalNote || '').indexOf('market_reaction') === 0) return true;
    if (evalTs && String(evalNote || '').trim()) return true;
  }
  return false;
}

function _getMarketReactionAuditSheetName_() {
  return 'MR_ProviderRuns';
}

function _ensureMarketReactionAuditHeaders_(sheet) {
  var required = [
    'score_run_ts','score_source','event_id','indicator_name','country','release_ts',
    'provider','status','anchor_detected','anchor_phase','anchor_ts',
    'start_ts','end_ts','start_price','end_price',
    'realized_pips','real_dir','real_strength','realized_sustain_min',
    'max_up_pips','max_down_pips',
    'candle_count','provider_meta_json','compare_status','compare_confidence','error_note'
  ];
  var headers = getHeaderNames(sheet);
  var lower = headers.map(function(h){ return String(h).toLowerCase(); });
  var toAdd = [];
  required.forEach(function(k) {
    if (lower.indexOf(String(k).toLowerCase()) < 0) toAdd.push(k);
  });
  if (headers.length === 0) {
    sheet.getRange(1, 1, 1, required.length).setValues([required]);
    return getHeaderNames(sheet);
  }
  if (toAdd.length > 0) {
    sheet.getRange(1, headers.length + 1, 1, toAdd.length).setValues([toAdd]);
  }
  return getHeaderNames(sheet);
}

function _prepareMarketReactionAuditContext_() {
  var ss = SpreadsheetApp.getActive();
  if (!ss) return null;
  var name = _getMarketReactionAuditSheetName_();
  var sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);

  var headers = _ensureMarketReactionAuditHeaders_(sheet);
  var idx = _indexByHeaderInsensitive_(headers);
  return {
    sheet: sheet,
    headers: headers,
    idx: idx,
    rows: []
  };
}

function _appendMarketReactionAuditRow_(ctx, eventMeta, reaction) {
  if (!ctx || !ctx.sheet || !ctx.headers || !ctx.idx) return;

  var row = new Array(ctx.headers.length);
  for (var i = 0; i < row.length; i++) row[i] = '';

  function set(name, value) {
    var col = ctx.idx[String(name || '').toLowerCase()];
    if (col == null) return;
    row[col] = value;
  }

  var status = reaction && reaction.status ? String(reaction.status) : 'not_scored';
  var provider = reaction && reaction.provider ? String(reaction.provider) : '';
  var realPips = (reaction && reaction.pips != null) ? _numOrBlank_(reaction.pips) : '';

  set('score_run_ts', new Date().toISOString());
  set('score_source', reaction && reaction.source ? reaction.source : '');
  set('event_id', eventMeta && eventMeta.event_id ? eventMeta.event_id : '');
  set('indicator_name', eventMeta && eventMeta.indicator_name ? eventMeta.indicator_name : '');
  set('country', eventMeta && eventMeta.country ? eventMeta.country : '');
  set('release_ts', eventMeta && eventMeta.release_ts ? eventMeta.release_ts : '');
  set('provider', provider);
  set('status', status);
  set('anchor_detected', reaction && reaction.anchor_detected != null ? String(!!reaction.anchor_detected) : '');
  set('anchor_phase', reaction && reaction.anchor_phase ? reaction.anchor_phase : '');
  set('anchor_ts', reaction && _validDate_(reaction.t0_ts) ? reaction.t0_ts.toISOString() : '');
  set('start_ts', reaction && _validDate_(reaction.t0_ts) ? reaction.t0_ts.toISOString() : '');
  set('end_ts', reaction && _validDate_(reaction.tH_ts) ? reaction.tH_ts.toISOString() : '');
  set('start_price', reaction ? _numOrBlank_(reaction.t0_price) : '');
  set('end_price', reaction ? _numOrBlank_(reaction.tH_price) : '');
  set('realized_pips', realPips);
  set('real_dir', _dirLabelFromReaction_(reaction || { pips: realPips }));
  set('real_strength', _mrStrengthFromRealizedPips_(realPips));
  set('realized_sustain_min', reaction ? _numOrBlank_(reaction.realized_sustain_min) : '');
  set('max_up_pips', reaction ? _numOrBlank_(reaction.max_up_pips) : '');
  set('max_down_pips', reaction ? _numOrBlank_(reaction.max_down_pips) : '');
  set('candle_count', reaction ? _numOrBlank_(reaction.candle_count) : '');
  set('provider_meta_json', reaction && reaction.provider_meta_json ? reaction.provider_meta_json : '');
  var scoreSource = reaction && reaction.source ? String(reaction.source) : '';
  var auditCompareStatus = 'single_provider';
  var auditCompareConfidence = 'single_source';
  if (/_compare$/.test(scoreSource)) {
    auditCompareStatus = 'compare_provider';
    auditCompareConfidence = 'comparison_run';
  }
  set('compare_status', auditCompareStatus);
  set('compare_confidence', auditCompareConfidence);
  set('error_note', (status === 'ok' || status === 'flat') ? '' : status);

  ctx.rows.push(row);
}

function _flushMarketReactionAuditContext_(ctx) {
  if (!ctx || !ctx.sheet || !ctx.rows || !ctx.rows.length || CFG.DRY_RUN_PREDICT) return;
  ctx.sheet.getRange(ctx.sheet.getLastRow() + 1, 1, ctx.rows.length, ctx.headers.length).setValues(ctx.rows);
}

function _flushPredictionEvalContext_(ctx) {
  if (!ctx || !ctx.sheet || !ctx.dirty || CFG.DRY_RUN_PREDICT) return;
  var keys = Object.keys(ctx.dirty);
  for (var i = 0; i < keys.length; i++) {
    var rowNo = Number(keys[i]);
    if (!(rowNo >= 2)) continue;
    ctx.sheet.getRange(rowNo, 1, 1, ctx.headers.length).setValues([ctx.data[rowNo - 2]]);
  }
}

function _buildEventEvalMeta_(row, idx, ts) {
  function pick(name) {
    var col = idx[name];
    return (col === undefined || col === null) ? '' : row[col];
  }
  return {
    event_id: pick('event_id'),
    batch_id: pick('batch_id'),
    type: pick('type'),
    indicator_name: pick('indicator_name'),
    country: pick('country'),
    release_ts: _validDate_(ts) ? ts.toISOString() : String(pick('release_ts') || ''),
    released_value: _numOrBlank_(pick('released_value'))
  };
}

function _getMarketReactionPrimaryProvider_(cfg) {
  var raw = cfg && cfg['MR_PRIMARY_PROVIDER'];
  var wanted = (typeof _normalizeFxProviderName_ === 'function')
    ? _normalizeFxProviderName_(raw)
    : String(raw || '').trim().toLowerCase();
  return wanted || 'tiingo';
}

function _getMarketReactionCompareProvider_(cfg, primaryProvider) {
  var list = _getMarketReactionCompareProviders_(cfg, primaryProvider);
  return list.length ? list[0] : '';
}

function _getMarketReactionCompareProviders_(cfg, primaryProvider) {
  var out = [];
  var seen = {};
  var primary = String(primaryProvider || '').trim().toLowerCase();
  var rawValues = [
    cfg && cfg['MR_COMPARE_PROVIDER'],
    cfg && cfg['MR_COMPARE_PROVIDER_2'],
    cfg && cfg['MR_COMPARE_PROVIDER_3']
  ];

  for (var i = 0; i < rawValues.length; i++) {
    var raw = rawValues[i];
    var wanted = (typeof _normalizeFxProviderName_ === 'function')
      ? _normalizeFxProviderName_(raw)
      : String(raw || '').trim().toLowerCase();
    if (!wanted || wanted === primary || seen[wanted]) continue;
    seen[wanted] = true;
    out.push(wanted);
  }
  return out;
}

function _isHighConfidenceReactionAgreement_(cmp) {
  if (!cmp || cmp.status !== 'compared') return false;
  if (String(cmp.dir_agree || '').toLowerCase() !== 'true') return false;
  var anchorDelta = Number(cmp.anchor_delta_min);
  var pipsDelta = Number(cmp.pips_delta);
  if (!isFinite(anchorDelta) || !isFinite(pipsDelta)) return false;
  return anchorDelta <= 1 && pipsDelta <= 3;
}

function _shouldEscalateMarketReactionFallbacks_(primaryReaction, firstCompareReaction) {
  if (!_isComparableReaction_(primaryReaction) || !_isComparableReaction_(firstCompareReaction)) return true;
  var cmp = _compareMarketReactionResults_(primaryReaction, firstCompareReaction);
  return !_isHighConfidenceReactionAgreement_(cmp);
}

function _computeMarketReactionWithFallbacks_(releaseTsUtc, horizonMin, meta, cfg, eventMeta, auditCtx) {
  var primaryProvider = _getMarketReactionPrimaryProvider_(cfg);
  var reaction = _computeUsdJpyMove_(releaseTsUtc, 30, 120, horizonMin, meta, cfg, primaryProvider);
  if (auditCtx && eventMeta) _appendMarketReactionAuditRow_(auditCtx, eventMeta, reaction);

  var compareProviders = _getMarketReactionCompareProviders_(cfg, primaryProvider);
  var compareReactions = [];
  var compareSource = String(meta && meta.source || '') + '_compare';

  if (compareProviders.length) {
    var firstProvider = compareProviders[0];
    var firstReaction = _computeUsdJpyMove_(releaseTsUtc, 30, 120, horizonMin, {
      event_id: meta && meta.event_id,
      row_index: meta && meta.row_index,
      source: compareSource
    }, cfg, firstProvider);
    compareReactions.push(firstReaction);
    if (auditCtx && eventMeta) _appendMarketReactionAuditRow_(auditCtx, eventMeta, firstReaction);

    if (_shouldEscalateMarketReactionFallbacks_(reaction, firstReaction)) {
      if (compareProviders.length >= 2) {
        var thirdProvider = compareProviders[1];
        var thirdReaction = _computeUsdJpyMove_(releaseTsUtc, 30, 120, horizonMin, {
          event_id: meta && meta.event_id,
          row_index: meta && meta.row_index,
          source: compareSource
        }, cfg, thirdProvider);
        compareReactions.push(thirdReaction);
        if (auditCtx && eventMeta) _appendMarketReactionAuditRow_(auditCtx, eventMeta, thirdReaction);

        if (!_isComparableReaction_(thirdReaction) && compareProviders.length >= 3) {
          var fourthProvider = compareProviders[2];
          var fourthReaction = _computeUsdJpyMove_(releaseTsUtc, 30, 120, horizonMin, {
            event_id: meta && meta.event_id,
            row_index: meta && meta.row_index,
            source: compareSource
          }, cfg, fourthProvider);
          compareReactions.push(fourthReaction);
          if (auditCtx && eventMeta) _appendMarketReactionAuditRow_(auditCtx, eventMeta, fourthReaction);
        }
      }
    }
  }

  var finalSelection = _selectFinalMarketReaction_(reaction, compareReactions);
  return {
    reaction: reaction,
    compareReactions: compareReactions,
    finalSelection: finalSelection
  };
}

function _compareMarketReactionResults_(primary, secondary) {
  if (!primary || !secondary) {
    return {
      status: 'single_provider',
      dir_agree: '',
      anchor_delta_min: '',
      pips_delta: '',
      confidence: 'single_source',
      note: 'single provider'
    };
  }

  var primaryOk = primary.status === 'ok' || primary.status === 'flat';
  var secondaryOk = secondary.status === 'ok' || secondary.status === 'flat';
  if (!primaryOk || !secondaryOk) {
    return {
      status: 'provider_error',
      dir_agree: '',
      anchor_delta_min: '',
      pips_delta: '',
      confidence: 'low',
      note: 'comparison unavailable due to provider error'
    };
  }

  var primaryDir = _dirLabelFromReaction_(primary);
  var secondaryDir = _dirLabelFromReaction_(secondary);
  var dirAgree = primaryDir === secondaryDir;
  var anchorDeltaMin = '';
  if (_validDate_(primary.t0_ts) && _validDate_(secondary.t0_ts)) {
    anchorDeltaMin = Math.round(Math.abs(primary.t0_ts.getTime() - secondary.t0_ts.getTime()) / 60000 * 100) / 100;
  }
  var pipsDelta = '';
  if (isFinite(Number(primary.pips)) && isFinite(Number(secondary.pips))) {
    pipsDelta = Math.round(Math.abs(Number(primary.pips) - Number(secondary.pips)) * 100) / 100;
  }

  var confidence = 'low';
  if (dirAgree && anchorDeltaMin !== '' && pipsDelta !== '' && anchorDeltaMin <= 1 && pipsDelta <= 3) confidence = 'high';
  else if (dirAgree) confidence = 'medium';

  return {
    status: 'compared',
    dir_agree: String(dirAgree),
    anchor_delta_min: anchorDeltaMin,
    pips_delta: pipsDelta,
    confidence: confidence,
    note: 'primary=' + String(primary.provider || '') + ' compare=' + String(secondary.provider || '')
  };
}

function _compareMarketReactionResultsMulti_(primary, secondaryReactions) {
  var list = Array.isArray(secondaryReactions) ? secondaryReactions.filter(function(item) { return !!item; }) : [];
  if (!list.length) {
    return _compareMarketReactionResults_(primary, null);
  }

  if (list.length === 1) {
    return _compareMarketReactionResults_(primary, list[0]);
  }

  var comparisons = list.map(function(item) {
    return _compareMarketReactionResults_(primary, item);
  });
  var valid = comparisons.filter(function(item) {
    return item && item.status === 'compared';
  });
  if (!valid.length) {
    return {
      status: 'provider_error',
      dir_agree: '',
      anchor_delta_min: '',
      pips_delta: '',
      confidence: 'low',
      note: 'comparison unavailable due to provider error'
    };
  }

  var allDirAgree = valid.every(function(item) { return String(item.dir_agree) === 'true'; });
  var maxAnchorDelta = '';
  var maxPipsDelta = '';
  for (var i = 0; i < valid.length; i++) {
    var anchorDelta = Number(valid[i].anchor_delta_min);
    if (isFinite(anchorDelta)) {
      maxAnchorDelta = (maxAnchorDelta === '') ? anchorDelta : Math.max(maxAnchorDelta, anchorDelta);
    }
    var pipsDelta = Number(valid[i].pips_delta);
    if (isFinite(pipsDelta)) {
      maxPipsDelta = (maxPipsDelta === '') ? pipsDelta : Math.max(maxPipsDelta, pipsDelta);
    }
  }

  var confidence = 'low';
  if (allDirAgree && maxAnchorDelta !== '' && maxPipsDelta !== '' && maxAnchorDelta <= 1 && maxPipsDelta <= 3) confidence = 'high';
  else if (allDirAgree) confidence = 'medium';

  var compareNames = list.map(function(item) { return String(item.provider || ''); }).filter(Boolean);
  return {
    status: 'compared_multi',
    dir_agree: String(allDirAgree),
    anchor_delta_min: maxAnchorDelta,
    pips_delta: maxPipsDelta,
    confidence: confidence,
    note: 'primary=' + String(primary && primary.provider || '') + ' compare=' + compareNames.join('|')
  };
}

function _isComparableReaction_(reaction) {
  return !!(reaction && (reaction.status === 'ok' || reaction.status === 'flat'));
}

function _computeReactionDistance_(left, right) {
  var anchorDelta = '';
  if (_validDate_(left && left.t0_ts) && _validDate_(right && right.t0_ts)) {
    anchorDelta = Math.abs(left.t0_ts.getTime() - right.t0_ts.getTime()) / 60000;
  }
  var pipsDelta = '';
  if (isFinite(Number(left && left.pips)) && isFinite(Number(right && right.pips))) {
    pipsDelta = Math.abs(Number(left.pips) - Number(right.pips));
  }
  return {
    anchor_delta_min: anchorDelta,
    pips_delta: pipsDelta
  };
}

function _pickRepresentativeReaction_(reactions) {
  var list = Array.isArray(reactions) ? reactions.filter(function(item) { return !!item; }) : [];
  if (!list.length) return null;
  if (list.length === 1) return list[0];

  var best = list[0];
  var bestScore = Infinity;
  for (var i = 0; i < list.length; i++) {
    var score = 0;
    for (var j = 0; j < list.length; j++) {
      if (i === j) continue;
      var dist = _computeReactionDistance_(list[i], list[j]);
      var anchorPart = isFinite(Number(dist.anchor_delta_min)) ? Number(dist.anchor_delta_min) : 999;
      var pipsPart = isFinite(Number(dist.pips_delta)) ? Number(dist.pips_delta) : 999;
      score += (anchorPart * 10) + pipsPart;
    }
    if (score < bestScore) {
      bestScore = score;
      best = list[i];
    }
  }
  return best;
}

function _findClusteredReactionSubset_(reactions) {
  var list = Array.isArray(reactions) ? reactions.filter(function(item) { return !!item; }) : [];
  if (list.length < 2) return [];

  var best = [];
  var bestScore = Infinity;
  for (var i = 0; i < list.length; i++) {
    for (var j = i + 1; j < list.length; j++) {
      var left = list[i];
      var right = list[j];
      if (_dirLabelFromReaction_(left) !== _dirLabelFromReaction_(right)) continue;
      var pairDist = _computeReactionDistance_(left, right);
      var anchorDelta = Number(pairDist.anchor_delta_min);
      var pipsDelta = Number(pairDist.pips_delta);
      if (!isFinite(anchorDelta) || !isFinite(pipsDelta)) continue;
      if (anchorDelta > 1 || pipsDelta > 3) continue;

      var cluster = [left, right];
      for (var k = 0; k < list.length; k++) {
        if (k === i || k === j) continue;
        var candidate = list[k];
        if (_dirLabelFromReaction_(candidate) !== _dirLabelFromReaction_(left)) continue;
        var fitsAll = true;
        for (var c = 0; c < cluster.length; c++) {
          var dist = _computeReactionDistance_(candidate, cluster[c]);
          var candAnchorDelta = Number(dist.anchor_delta_min);
          var candPipsDelta = Number(dist.pips_delta);
          if (!isFinite(candAnchorDelta) || !isFinite(candPipsDelta) || candAnchorDelta > 1 || candPipsDelta > 3) {
            fitsAll = false;
            break;
          }
        }
        if (fitsAll) cluster.push(candidate);
      }

      var clusterScore = 0;
      for (var a = 0; a < cluster.length; a++) {
        for (var b = a + 1; b < cluster.length; b++) {
          var clusterDist = _computeReactionDistance_(cluster[a], cluster[b]);
          clusterScore += (Number(clusterDist.anchor_delta_min) * 10) + Number(clusterDist.pips_delta);
        }
      }

      if (
        cluster.length > best.length ||
        (cluster.length === best.length && clusterScore < bestScore)
      ) {
        best = cluster;
        bestScore = clusterScore;
      }
    }
  }

  return best;
}

function _selectFinalMarketReaction_(primaryReaction, secondaryReactions) {
  var primary = primaryReaction || null;
  var secondaries = Array.isArray(secondaryReactions) ? secondaryReactions.filter(function(item) {
    return _isComparableReaction_(item);
  }) : [];

  if (!_isComparableReaction_(primary)) {
    var fallback = _pickRepresentativeReaction_(secondaries);
    return {
      reaction: fallback || primary,
      source: fallback ? 'compare_failover' : 'primary_only',
      note: fallback ? ('primary unavailable; selected=' + String(fallback.provider || '')) : 'primary unavailable'
    };
  }

  if (secondaries.length < 2) {
    return {
      reaction: primary,
      source: 'primary_only',
      note: 'primary retained'
    };
  }

  var clusteredSecondaries = _findClusteredReactionSubset_(secondaries);
  if (clusteredSecondaries.length < 2) {
    return {
      reaction: primary,
      source: 'primary_only',
      note: 'compare providers did not cluster'
    };
  }

  var primaryDistances = clusteredSecondaries.map(function(item) {
    return _computeReactionDistance_(primary, item);
  });
  var primaryIsOutlier = primaryDistances.every(function(dist) {
    var anchorOutlier = isFinite(Number(dist.anchor_delta_min)) && Number(dist.anchor_delta_min) >= 1;
    var pipsOutlier = isFinite(Number(dist.pips_delta)) && Number(dist.pips_delta) >= 5;
    return anchorOutlier || pipsOutlier;
  });

  if (!primaryIsOutlier) {
    return {
      reaction: primary,
      source: 'primary_only',
      note: 'primary stayed within compare tolerance'
    };
  }

  var representative = _pickRepresentativeReaction_(clusteredSecondaries);
  var compareNames = clusteredSecondaries.map(function(item) { return String(item.provider || ''); }).filter(Boolean);
  return {
    reaction: representative || primary,
    source: 'compare_cluster_override',
    note: 'selected=' + String(representative && representative.provider || '') + ' clustered=' + compareNames.join('|')
  };
}

function _writePredictionComparisonFields_(row, idx, finalReaction, cmp) {
  function set(name, value) {
    var col = idx[name];
    if (col == null) return;
    row[col] = value;
  }
  set('mr_final_provider', finalReaction && finalReaction.provider ? String(finalReaction.provider) : '');
  set('mr_compare_status', cmp && cmp.status ? cmp.status : 'single_provider');
  set('mr_compare_dir_agree', cmp && cmp.dir_agree !== undefined ? cmp.dir_agree : '');
  set('mr_compare_anchor_delta_min', cmp && cmp.anchor_delta_min !== undefined ? cmp.anchor_delta_min : '');
  set('mr_compare_pips_delta', cmp && cmp.pips_delta !== undefined ? cmp.pips_delta : '');
  set('mr_compare_confidence', cmp && cmp.confidence ? cmp.confidence : 'single_source');
  set('mr_compare_note', cmp && cmp.note ? cmp.note : 'single provider');
}

function _mergeComparisonWithSelection_(cmp, finalSelection, primaryReaction) {
  var out = {
    status: cmp && cmp.status ? cmp.status : 'single_provider',
    dir_agree: cmp && cmp.dir_agree !== undefined ? cmp.dir_agree : '',
    anchor_delta_min: cmp && cmp.anchor_delta_min !== undefined ? cmp.anchor_delta_min : '',
    pips_delta: cmp && cmp.pips_delta !== undefined ? cmp.pips_delta : '',
    confidence: cmp && cmp.confidence ? cmp.confidence : 'single_source',
    note: cmp && cmp.note ? cmp.note : 'single provider'
  };
  if (!finalSelection || !finalSelection.reaction || !primaryReaction) return out;
  if (String(finalSelection.reaction.provider || '') === String(primaryReaction.provider || '')) return out;

  out.status = (out.status === 'compared_multi') ? 'compared_multi_override' : 'compared_override';
  var selectionNote = finalSelection.note ? String(finalSelection.note) : ('final=' + String(finalSelection.reaction.provider || ''));
  out.note = out.note + ' ' + selectionNote;
  return out;
}

function _applyComparisonToPredictions_(ctx, eventMeta, primaryReaction, secondaryReaction, finalSelection) {
  if (!ctx || !eventMeta || !eventMeta.event_id) return;
  var cmp = Array.isArray(secondaryReaction)
    ? _compareMarketReactionResultsMulti_(primaryReaction, secondaryReaction)
    : _compareMarketReactionResults_(primaryReaction, secondaryReaction);
  cmp = _mergeComparisonWithSelection_(cmp, finalSelection, primaryReaction);

  for (var r = 0; r < ctx.data.length; r++) {
    var row = ctx.data[r];
    if (!_predictionRowMatchesEvalTarget_(ctx, row, eventMeta)) continue;
    _writePredictionComparisonFields_(row, ctx.idx, (finalSelection && finalSelection.reaction) ? finalSelection.reaction : primaryReaction, cmp);
    ctx.dirty[r + 2] = true;
  }
}

function _applyEvaluationToPredictions_(ctx, eventMeta, reaction) {
  if (!ctx || !eventMeta || !eventMeta.event_id) return;

  for (var r = 0; r < ctx.data.length; r++) {
    var row = ctx.data[r];
    if (!_predictionRowMatchesEvalTarget_(ctx, row, eventMeta)) continue;
    _writePredictionEvalFields_(row, ctx.idx, eventMeta, reaction);
    ctx.dirty[r + 2] = true;
  }
}

function _predictionRowMatchesEvalTarget_(ctx, row, eventMeta) {
  if (!ctx || !row || !eventMeta) return false;
  var eventCol = ctx.idx['event_id'];
  if (eventCol == null) return false;
  var typeCol = ctx.idx['type'];

  var rowEventId = String(row[eventCol] || '').trim();
  var targetEventId = String(eventMeta.event_id || '').trim();
  if (rowEventId === targetEventId) return true;

  if (!eventMeta.batch_id) return false;
  var rowType = (typeCol == null) ? '' : String(row[typeCol] || '').trim().toLowerCase();
  return rowType === 'batch' && rowEventId === String(eventMeta.batch_id || '').trim();
}

function _writePredictionEvalFields_(row, idx, eventMeta, reaction) {
  function set(name, value) {
    var col = idx[name];
    if (col == null) return;
    row[col] = value;
  }
  function get(name) {
    var col = idx[name];
    return col == null ? '' : row[col];
  }

  var releasedValue = _numOrBlank_(eventMeta.released_value);
  var forecastValue = _numOrBlank_(get('ai_forecast_value'));
  var consensusValue = _numOrBlank_(get('consensus_value'));
  var prevRevision = _numOrBlank_(get('prev_revision'));
  var rowType = String(get('type') || '').trim().toLowerCase();
  var preserveIdentity = (rowType === 'batch');
  var baseline = (releasedValue !== '' && consensusValue !== '') ? consensusValue :
    ((releasedValue !== '' && prevRevision !== '') ? prevRevision :
    ((forecastValue !== '' && consensusValue !== '') ? consensusValue :
    ((forecastValue !== '' && prevRevision !== '') ? prevRevision : '')));

  set('released_value', releasedValue);
  if (!preserveIdentity) {
    set('indicator_name', eventMeta.indicator_name || '');
    set('country', eventMeta.country || '');
    set('release_ts', eventMeta.release_ts || '');
  }
  set('eval_ts', new Date().toISOString());
  _writePredictionComparisonFields_(row, idx, reaction, {
    status: 'single_provider',
    dir_agree: '',
    anchor_delta_min: '',
    pips_delta: '',
    confidence: 'single_source',
    note: reaction && reaction.provider ? ('single provider: ' + String(reaction.provider)) : 'single provider'
  });

  if (reaction && (reaction.status === 'ok' || reaction.status === 'flat')) {
    var realizedAbs = Math.abs(Number(reaction.pips));
    var realizedDir = _dirLabelFromReaction_(reaction);
    var realizedStrength = _mrStrengthFromRealizedPips_(reaction.pips);
    var expectedDir = String(get('expected_move_dir') || '').trim().toLowerCase();
    var minPips = _numOrBlank_(get('expected_move_pips_min'));
    var maxPips = _numOrBlank_(get('expected_move_pips_max'));

    var dirOk = (expectedDir === '') ? '' : (expectedDir === realizedDir);
    var bandOk = (minPips === '' || maxPips === '') ? '' : (realizedAbs >= Number(minPips) && realizedAbs <= Number(maxPips));
    var overallOk = (typeof dirOk === 'boolean' && typeof bandOk === 'boolean') ? (dirOk && bandOk) : '';

    set('eval_interval', String(reaction.horizon_min) + 'm');
    set('start_ts', _validDate_(reaction.t0_ts) ? reaction.t0_ts.toISOString() : '');
    set('end_ts', _validDate_(reaction.tH_ts) ? reaction.tH_ts.toISOString() : '');
    set('start_price', _numOrBlank_(reaction.t0_price));
    set('end_price', _numOrBlank_(reaction.tH_price));
    set('realized_pips', _numOrBlank_(reaction.pips));
    set('dir_ok', dirOk === '' ? '' : String(dirOk));
    set('band_ok', bandOk === '' ? '' : String(bandOk));
    set('overall_ok', overallOk === '' ? '' : String(overallOk));
    set('mr_real_dir', realizedDir);
    set('mr_real_strength', realizedStrength);
    set('mr_dir_ok', _computeMrDirOk_(get('mr_pred_dir'), realizedDir));
    set('mr_strength_ok', _computeMrStrengthOk_(get('mr_pred_strength'), reaction.pips, get('mr_pred_dir'), realizedDir));
    set('mr_real_sustain_min', _numOrBlank_(reaction.realized_sustain_min));
    set('mr_sustain_error_min', _computeMrSustainErrorMin_(get('mr_pred_sustain_min'), reaction.realized_sustain_min));
    set('mr_sustain_grade', _computeMrSustainGrade_(get('mr_pred_sustain_min'), reaction.realized_sustain_min));
    set('mr_sustain_ok', _computeMrSustainOk_(get('mr_pred_sustain_min'), reaction.realized_sustain_min));
    set('mr_real_max_up_pips', _numOrBlank_(reaction.max_up_pips));
    set('mr_real_max_down_pips', _numOrBlank_(reaction.max_down_pips));
    var note = reaction.provider ? ('market_reaction:' + reaction.provider) : 'market_reaction';
    if (reaction.status === 'flat' || reaction.anchor_detected === false) note += ':no_reaction_detected';
    else if (realizedDir === 'flat' && realizedAbs > 0) note += ':below_flat_threshold';
    set('eval_note', note);
  } else {
    set('eval_interval', '');
    set('start_ts', '');
    set('end_ts', '');
    set('start_price', '');
    set('end_price', '');
    set('realized_pips', '');
    set('dir_ok', '');
    set('band_ok', '');
    set('overall_ok', '');
    set('mr_real_dir', '');
    set('mr_real_strength', '');
    set('mr_dir_ok', '');
    set('mr_strength_ok', '');
    set('mr_real_sustain_min', '');
    set('mr_sustain_error_min', '');
    set('mr_sustain_grade', '');
    set('mr_sustain_ok', '');
    set('mr_real_max_up_pips', '');
    set('mr_real_max_down_pips', '');
    _writePredictionComparisonFields_(row, idx, reaction, {
      status: 'single_provider',
      dir_agree: '',
      anchor_delta_min: '',
      pips_delta: '',
      confidence: 'single_source',
      note: reaction && reaction.status ? ('single provider: ' + String(reaction.status)) : 'single provider'
    });
    set('eval_note', reaction && reaction.status ? String(reaction.status) : 'not_scored');
  }

  var forecastEval = _computeForecastEval_(forecastValue, releasedValue, baseline);
  set('forecast_error_abs', forecastEval.abs_error);
  set('forecast_error_pct', forecastEval.pct_error);
  set('forecast_dir_ok', forecastEval.dir_ok === '' ? '' : String(forecastEval.dir_ok));
}

function _mrStrengthFromRealizedPips_(pips) {
  var n = Math.abs(Number(pips));
  if (!isFinite(n)) return '';
  if (n < 5) return 'weak';
  if (n < 15) return 'medium';
  return 'strong';
}

function _computeMrDirOk_(predDir, realizedDir) {
  var pred = String(predDir || '').trim().toLowerCase();
  if (!pred) return '';
  return pred === String(realizedDir || '').trim().toLowerCase();
}

function _computeMrStrengthOk_(predStrength, realizedPips, predDir, realizedDir) {
  var pred = String(predStrength || '').trim().toLowerCase();
  if (!pred) return '';
  var dirOk = _computeMrDirOk_(predDir, realizedDir);
  if (dirOk !== true) return false;
  var real = _mrStrengthFromRealizedPips_(realizedPips);
  if (!real) return '';
  return pred === real;
}

function _computeMrSustainErrorMin_(predMin, realMin) {
  var pred = Number(predMin);
  var real = Number(realMin);
  if (!isFinite(pred) || pred <= 0 || !isFinite(real) || real < 0) return '';
  return Math.abs(real - pred);
}

function _computeMrSustainGrade_(predMin, realMin) {
  var err = _computeMrSustainErrorMin_(predMin, realMin);
  if (err === '') return '';
  if (err <= 2) return 'excellent';
  if (err <= 5) return 'acceptable';
  return 'weak';
}

function _computeMrSustainOk_(predMin, realMin) {
  var grade = _computeMrSustainGrade_(predMin, realMin);
  if (!grade) return '';
  return grade === 'excellent' || grade === 'acceptable';
}

function _computeForecastEval_(forecastValue, releasedValue, baseline) {
  if (forecastValue === '' || releasedValue === '') {
    return { abs_error: '', pct_error: '', dir_ok: '' };
  }

  var absErr = Math.abs(Number(forecastValue) - Number(releasedValue));
  var pctErr = (Number(releasedValue) === 0) ? '' : Math.round((absErr / Math.abs(Number(releasedValue))) * 10000) / 100;
  var dirOk = '';

  if (baseline !== '') {
    var forecastDelta = Number(forecastValue) - Number(baseline);
    var actualDelta = Number(releasedValue) - Number(baseline);
    dirOk = _dirSign_(forecastDelta) === _dirSign_(actualDelta);
  }

  return { abs_error: absErr, pct_error: pctErr, dir_ok: dirOk };
}

function _getReactionFlatThresholdPips_(reaction) {
  var n = Number(reaction && reaction.flat_threshold_pips);
  return isFinite(n) ? n : _getMarketReactionFlatMaxAbsPips_(null);
}

function _dirLabelFromReaction_(reaction) {
  return _dirLabelFromPips_(reaction && reaction.pips, _getReactionFlatThresholdPips_(reaction));
}

function _dirLabelFromPips_(pips, flatThresholdPips) {
  var s = _dirSignForPips_(pips, flatThresholdPips);
  if (s > 0) return 'up';
  if (s < 0) return 'down';
  return 'flat';
}

function _dirSignForPips_(pips, flatThresholdPips) {
  var x = Number(pips);
  if (!isFinite(x)) return 0;
  var threshold = Number(flatThresholdPips);
  if (!isFinite(threshold)) threshold = _getMarketReactionFlatMaxAbsPips_(null);
  if (Math.abs(x) < threshold) return 0;
  return x > 0 ? 1 : (x < 0 ? -1 : 0);
}

function _dirSign_(n) {
  var x = Number(n);
  if (!isFinite(x) || Math.abs(x) < 1e-9) return 0;
  return x > 0 ? 1 : -1;
}

function _numOrBlank_(v) {
  if (v === '' || v === null || v === undefined) return '';
  var n = (typeof v === 'number') ? v : Number(String(v).replace(/,/g, ''));
  return isFinite(n) ? n : '';
}

function _mrConfigBoolean_(value, fallback) {
  if (typeof value === 'boolean') return value;
  if (value === null || value === undefined || value === '') return !!fallback;
  var s = String(value).trim().toLowerCase();
  if (s === 'true' || s === 'yes' || s === 'y' || s === '1') return true;
  if (s === 'false' || s === 'no' || s === 'n' || s === '0') return false;
  return !!fallback;
}



/**************  debug  **************/

function debugEventTimestampSample_() {
  var EVENT = _getEventSheet_();
  if (!EVENT) throw new Error('Event/RawCalendar sheet not found');
  var headers = getHeaderNames(EVENT);
  var idx = _indexByHeaderInsensitive_(headers);
  var last = Math.max(0, EVENT.getLastRow()-1);
  var n = Math.min(5, last);
  var vals = n ? EVENT.getRange(2,1,n,EVENT.getLastColumn()).getValues() : [];
  log_ && log_('debug', 'event_ts_sample', {
    headers: headers,
    idx_map: idx,
    sample_rows: vals.map(function(row){
      var ts = _getEventReleaseTs_(row, idx, String(Session.getScriptTimeZone() || 'UTC'));
      return {
        direct_pick: _validDate_(ts) ? ts.toISOString() : 'invalid',
        raw_candidates: {
          release_ts: row[idx['release_ts']],
          released_ts: row[idx['released_ts']],
          release_date: row[idx['release_date']],
          release_time: row[idx['release_time']] || row[idx['release_time_local']]
        }
      };
    })
  });
  if (typeof flushLogs_ === 'function') flushLogs_();
}

function debugMarketReactionCandlesForEvent_(eventId) {
  var targetEventId = String(eventId || '').trim();
  if (!targetEventId) throw new Error('eventId is required');

  var EVENT = _getEventSheet_();
  if (!EVENT) throw new Error('Event/RawCalendar sheet not found');

  var headers = getHeaderNames(EVENT);
  var idx = _indexByHeaderInsensitive_(headers);
  var eventIdCol = idx['event_id'];
  if (eventIdCol === undefined) throw new Error('Event sheet missing event_id');

  var values = EVENT.getRange(2, 1, Math.max(0, EVENT.getLastRow() - 1), EVENT.getLastColumn()).getValues();
  var row = null;
  var rowNo = null;
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][eventIdCol] || '').trim() === targetEventId) {
      row = values[r];
      rowNo = r + 2;
      break;
    }
  }
  if (!row) throw new Error('Event not found: ' + targetEventId);

  var ts = _getEventReleaseTs_(row, idx, 'UTC');
  if (!_validDate_(ts)) throw new Error('Invalid event timestamp for ' + targetEventId);

  var cfg = _readConfigMap_('Config');
  var out = getFxCandlesForWindow_('USD/JPY', ts, 30, 120);
  var candles = (out && out.candles) ? out.candles : [];
  var t0 = ts.getTime();
  var horizonMin = _getMarketReactionHorizonMin_(cfg);
  var base = _nearestAtOrBefore_(candles, t0);
  var baselinePrice = base && isFinite(base.close) ? base.close : null;
  var anchor = (baselinePrice != null) ? _detectMarketReactionAnchor_(candles, ts, baselinePrice, cfg) : { detected: false };
  var reaction = _computeUsdJpyMove_(ts, 30, 120, horizonMin, {
    event_id: targetEventId,
    row_index: rowNo,
    source: 'debug_event'
  }, cfg);
  var anchorTs = (anchor && anchor.detected && _validDate_(anchor.ts)) ? anchor.ts.getTime() : t0;
  var horizonMs = anchorTs + horizonMin * 60 * 1000;
  var horizon = _nearestAtOrBefore_(candles, horizonMs) || (candles.length ? candles[candles.length - 1] : null);
  var p0 = reaction && isFinite(reaction.t0_price) ? reaction.t0_price : null;
  var p1 = reaction && isFinite(reaction.tH_price) ? reaction.tH_price : null;
  var pips = reaction && isFinite(reaction.pips) ? reaction.pips : null;
  var dir = reaction && isFinite(reaction.dir) ? reaction.dir : null;

  var baselinePoint = base ? {
    ts: base.ts.toISOString(),
    open: base.open,
    high: base.high,
    low: base.low,
    close: base.close
  } : null;

  var startPoint = reaction && _validDate_(reaction.t0_ts) ? {
    ts: reaction.t0_ts.toISOString(),
    open: anchor && anchor.detected && anchor.candle ? anchor.candle.open : (base ? base.open : null),
    high: anchor && anchor.detected && anchor.candle ? anchor.candle.high : (base ? base.high : null),
    low: anchor && anchor.detected && anchor.candle ? anchor.candle.low : (base ? base.low : null),
    close: anchor && anchor.detected && anchor.candle ? anchor.candle.close : (base ? base.close : null)
  } : null;

  var endPoint = horizon ? {
    ts: ((reaction && reaction.status === 'flat') && startPoint) ? startPoint.ts : horizon.ts.toISOString(),
    open: ((reaction && reaction.status === 'flat') && startPoint) ? startPoint.open : horizon.open,
    high: ((reaction && reaction.status === 'flat') && startPoint) ? startPoint.high : horizon.high,
    low: ((reaction && reaction.status === 'flat') && startPoint) ? startPoint.low : horizon.low,
    close: ((reaction && reaction.status === 'flat') && startPoint) ? startPoint.close : horizon.close
  } : null;

  log_ && log_('debug', 'market_reaction_candles', {
    event_id: targetEventId,
    row_index: rowNo,
    indicator_name: (idx['indicator_name'] !== undefined) ? row[idx['indicator_name']] : '',
    release_ts: ts.toISOString(),
    provider: out && out.provider ? out.provider : '',
    meta: out && out.meta ? out.meta : null,
    cache_hit: !!(out && out.cache_hit),
    candle_count_total: candles.length,
    baseline_point: baselinePoint,
    anchor_detected: !!(anchor && anchor.detected),
    anchor_phase: anchor && anchor.phase ? anchor.phase : '',
    anchor_threshold_pips: anchor && isFinite(anchor.threshold_pips) ? anchor.threshold_pips : '',
    anchor_lookback_min: anchor && isFinite(anchor.lookback_min) ? anchor.lookback_min : '',
    anchor_lookahead_min: anchor && isFinite(anchor.lookahead_min) ? anchor.lookahead_min : '',
    start_point: startPoint,
    end_point: endPoint,
    horizon_min: horizonMin,
    pips: pips,
    dir: dir,
    status: reaction && reaction.status ? reaction.status : ''
  });
  if (typeof flushLogs_ === 'function') flushLogs_();

  return {
    event_id: targetEventId,
    row_index: rowNo,
    indicator_name: (idx['indicator_name'] !== undefined) ? row[idx['indicator_name']] : '',
    release_ts: ts.toISOString(),
    provider: out && out.provider ? out.provider : '',
    meta: out && out.meta ? out.meta : null,
    cache_hit: !!(out && out.cache_hit),
    candle_count_total: candles.length,
    baseline_point: baselinePoint,
    anchor_detected: !!(anchor && anchor.detected),
    anchor_phase: anchor && anchor.phase ? anchor.phase : '',
    anchor_threshold_pips: anchor && isFinite(anchor.threshold_pips) ? anchor.threshold_pips : '',
    anchor_lookback_min: anchor && isFinite(anchor.lookback_min) ? anchor.lookback_min : '',
    anchor_lookahead_min: anchor && isFinite(anchor.lookahead_min) ? anchor.lookahead_min : '',
    start_point: startPoint,
    end_point: endPoint,
    horizon_min: horizonMin,
    pips: pips,
    dir: dir,
    status: reaction && reaction.status ? reaction.status : ''
  };
}
