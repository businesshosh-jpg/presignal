/**************  Minimal market reaction scorer (USD/JPY)  **************/

// Utility: fetch candles around event and compute realized move in pips.
function _computeUsdJpyMove_(releaseTsUtc, preMin, postMin, horizonMin, meta) {
  var out = getFxCandlesForWindow_('USD/JPY', releaseTsUtc, preMin||30, postMin||120);
  if (!out || !out.candles || !out.candles.length) {
    log_ && log_('scoring', 'no_candles', {
      provider_chain: out && out.provider,
      t0: releaseTsUtc && releaseTsUtc.toISOString(),
      event_id: meta && meta.event_id,
      row_index: meta && meta.row_index,
      source: meta && meta.source
    });
    return { status: 'no_candles' };
  }

  // t0 price = closest candle at/just before release time
  var t0ms = releaseTsUtc.getTime();
  var base = _nearestAtOrBefore_(out.candles, t0ms);
  if (!base) return { status: 'no_base' };

  var horizonMs = t0ms + (horizonMin||30)*60*1000;
  var h = _nearestAtOrBefore_(out.candles, horizonMs) || out.candles[out.candles.length-1];

  var p0 = base.close;
  var p1 = h.close;
  if (!isFinite(p0) || !isFinite(p1)) return { status: 'bad_prices' };

  var diff = p1 - p0;
  // USD/JPY pips → 0.01 JPY
  var pips = Math.round((diff * 100) * 100) / 100; // 1.00 = 1 pip
  var dir  = (pips > 0) ? 1 : (pips < 0 ? -1 : 0);

  var res = {
    status: 'ok',
    provider: out.provider,
    t0_price: p0,
    tH_price: p1,
    horizon_min: horizonMin || 30,
    pips: pips,
    dir: dir
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

  var count = 0;
  for (var r=0; r<data.length; r++){
    var row = data[r];
    var ts = row[releaseTsCol];
    if (!(ts instanceof Date)) continue;
    if (ts < since || ts > now) continue;

    var eventId = (eventIdCol !== null) ? row[eventIdCol] : null;

    _computeUsdJpyMove_(ts, 30, 120, 30, {
      event_id: eventId,
      row_index: r + 2,           // +2 because row 1 = headers, we started at row 2
      source: 'past24h'
    });
  }

  appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(past24h)', { checked_events: count });
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
  if (!cfg || String(cfg['WINDOW_ENABLED']).toUpperCase() !== 'TRUE') {
    appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(config)', { status: 'skipped', reason: 'WINDOW_ENABLED != TRUE' });
    return;
  }

  var tz  = String(cfg['WINDOW_TZ'] || 'UTC').trim();
  var fromLocal = cfg['WINDOW_FROM_LOCAL'];
  var toLocal   = cfg['WINDOW_TO_LOCAL'];

  var fromUtc = _parseLocalToUtc_(fromLocal, tz);
  var toUtc   = _parseLocalToUtc_(toLocal, tz);
  if (!(fromUtc instanceof Date) || isNaN(fromUtc.getTime()) || !(toUtc instanceof Date) || isNaN(toUtc.getTime())) {
    appendLog(getSheet(CFG.SHEET_LOG), 'ERROR', 'ScoreMarketReaction(config)', { status: 'parse_error', fromLocal: String(fromLocal), toLocal: String(toLocal), tz: tz });
    return;
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

  var checked = 0, totalRows = values.length, inWindow = 0, parsedOk = 0;
  for (var r = 0; r < values.length; r++) {
    var ts = _getEventReleaseTs_(values[r], idxMap, tz);
    if (!(ts instanceof Date) || isNaN(ts.getTime())) continue;
    parsedOk++;

    if (ts < fromUtc || ts > toUtc) continue;
    inWindow++;

    var eventId = (eventIdCol !== undefined) ? values[r][eventIdCol] : null;

    _computeUsdJpyMove_(ts, 30, 120, 30, {
      event_id: eventId,
      row_index: r + 2,           // again: +2 for header row + 1-based index
      source: 'config_window'
    });

    if (checked >= 300) break; // safety cap
  }

  appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(config)', {
    window_from_utc: fromUtc.toISOString(),
    window_to_utc: toUtc.toISOString(),
    total_rows: totalRows,
    parsed_ts_rows: parsedOk,
    rows_in_window: inWindow,
    checked_events: checked
  });
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

// Accepts a Date object OR any parseable string (e.g. "Wed Jan 01 2025 09:00:00 GMT+0900",
// "2025-01-01 09:00", etc.). Returns a UTC Date (same absolute instant).
function _parseLocalToUtc_(val, tz) {
  // Case A: Already a Date -> it's an absolute instant; return a copy.
  if (val instanceof Date && isFinite(val.getTime())) {
    return new Date(val.getTime());
  }

  // Case B: Try native Date parsing for strings like "Wed Jan 01 2025 09:00:00 GMT+0900 (JST)"
  var s = String(val || '').trim();
  var d = new Date(s);
  if (isFinite(d.getTime())) {
    return d; // already an absolute instant
  }

  // Case C: Try strict "YYYY-MM-DD HH:mm" in a specific timezone
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

  // If all parsing failed, return an invalid date to trigger error handling upstream.
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



/**************  debug  **************/

function debugEventTimestampSample_() {
  var EVENT = _getEventSheet_();
  var headers = getHeaderNames(EVENT);
  var idx = _indexByHeaderInsensitive_(headers);
  var last = Math.max(0, EVENT.getLastRow()-1);
  var n = Math.min(5, last);
  var vals = n ? EVENT.getRange(2,1,n,EVENT.getLastColumn()).getValues() : [];
  log_ && log_('debug', 'event_ts_sample', {
    headers: headers,
    idx_map: idx,
    sample_rows: vals.map(function(row){
      return {
        direct_pick: _getEventReleaseTs_(row, idx, String(Session.getScriptTimeZone()||'UTC')).toISOString ? _getEventReleaseTs_(row, idx, 'UTC').toISOString() : 'invalid',
        raw_candidates: {
          release_ts: row[idx['release_ts']],
          released_ts: row[idx['released_ts']],
          release_date: row[idx['release_date']],
          release_time: row[idx['release_time']] || row[idx['release_time_local']]
        }
      };
    })
  });
}

