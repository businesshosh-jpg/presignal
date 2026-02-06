/*********************************************************
 * actuals_fetcher.gs  — Hourly Actuals Harvester
 * - Scans Event within a rolling window
 * - Resolves SeriesMap for each event
 * - Fetches observations (FRED-first), applies transform
 * - Updates released_value, released_ts, source_provider,
 *   source_series_id, transform, release_status
 * - Idempotent; updates by event_id
 **********************************************************/

/** ===== Config ===== **/
var ACTUALS_CFG = {
  LOOKBACK_MINUTES: 14 * 24 * 60,     // scan last 14 days
  LOOKAHEAD_MINUTES: 60,              // 1 hour ahead to catch early postings
  MAX_ROWS_PER_RUN: 400,
  SOURCE_PRIORITY: ['FRED', 'FMP'],   // implement FMP adapter if needed
  DEFAULT_TZ: 'UTC',
  SERIESMAP_SHEET: 'SeriesMap',       // tab holding mappings (indicator → provider/series/transform)
  // Script Properties needed:
  //  - FRED_API_KEY
};

/** ===== Entrypoint: run hourly trigger ===== **/
/**
 * Shared worker used by:
 *  - hourly trigger: runFetchActualsHourly_() → calls this with ACTUALS_CFG defaults
 *  - manual menu actions: pass custom lookback/lookahead/rowCap windows
 */
function runFetchActualsWindow_(lookbackMinutes, lookaheadMinutes, rowCap) {
  var ss = SpreadsheetApp.getActive();
  var EVENT = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
  var LOG   = (typeof CFG !== 'undefined' && CFG.SHEET_LOG)   ? CFG.SHEET_LOG   : 'log';

  var shEvent = ss.getSheetByName(EVENT);
  var shLog   = ss.getSheetByName(LOG);
  if (!shEvent || !shLog) throw new Error('Missing required sheet: Event or log');

  var started = new Date();
  _log_(shLog, 'info', 'Actuals: scan start (window)', {
    lookbackMinutes: lookbackMinutes,
    lookaheadMinutes: lookaheadMinutes,
    rowCap: rowCap
  });
  
  // Headers + body
  var headers = _getHeaderNames_(shEvent);
  var H = _buildHeaderIndex_(headers);
  var lastRow = shEvent.getLastRow(), lastCol = shEvent.getLastColumn();
  if (lastRow < 2 || lastCol < 1) {
    _log_(shLog, 'info', 'Actuals: Event empty', {});
    return;
  }
  var data = shEvent.getRange(2, 1, lastRow - 1, lastCol).getValues();

  // Time window
  var now = new Date();
  var lo  = new Date(now.getTime() - (Number(lookbackMinutes) || 0) * 60 * 1000);
  var hi  = new Date(now.getTime() + (Number(lookaheadMinutes) || 0) * 60 * 1000);

  // Load SeriesMap (ok if missing; we just skip those rows and log a warn)
  var seriesMap = (typeof _loadSeriesMap_ === 'function') ? _loadSeriesMap_() : [];

  // Select candidates (skip qualitative / non-numeric upfront)
  var candIdx = [];
  for (var i = 0; i < data.length; i++) {
    var row = data[i];

    // Pull key fields (safely even if header is missing)
    var indicator_name = H('indicator_name') >= 0 ? String(row[H('indicator_name')] || '') : '';
    var status =
      (H('release_status') >= 0 && row[H('release_status')] !== '') ? String(row[H('release_status')] || '').toLowerCase() :
      (H('status') >= 0) ? String(row[H('status')] || '').toLowerCase() :
      '';
    var rel    = H('release_ts')     >= 0 ? row[H('release_ts')] : '';

    // 1) Skip invalid dates
    var relDate = (rel instanceof Date) ? rel : new Date(String(rel || ''));
    if (String(relDate) === 'Invalid Date') continue;

    // 2) Skip qualitative items (log INFO so it’s visible but not noisy)
    if (_shouldSkipActuals_(indicator_name)) {
      try {
        _log_(shLog, 'info', 'Actuals: skipped qualitative', {
          event_id: (H('event_id') >= 0 ? String(row[H('event_id')] || '') : ''),
          indicator_name: indicator_name,
          country: (H('country') >= 0 ? String(row[H('country')] || '') : '')
        });
      } catch (e) {}
      continue;
    }

    // 3) Window selection:
    // - scheduled in [lo, hi]
    // - OR scheduled but already past release time (common: upstream never flips status)
    // - released/revised within lookback (to catch revisions)
    if (status === 'scheduled') {
    if (relDate >= lo && relDate <= hi) candIdx.push(i);
    else if (relDate >= lo && relDate <= now) candIdx.push(i); // scheduled-but-past
    } else if (status === 'released' || status === 'revised') {
    if (relDate >= lo) candIdx.push(i);
    }
  }


  // Cap rows per run
  var cap = Number(rowCap || 0);
  if (cap > 0 && candIdx.length > cap) candIdx = candIdx.slice(0, cap);

  var updated = 0, released = 0, revised = 0;
  var pending = {}; // i -> updates
  var _suggestedKeys = Object.create(null);
  // Process candidates
  for (var k = 0; k < candIdx.length; k++) {
    var idx = candIdx[k];
    var r = data[idx];

    var event_id       = String(r[H('event_id')] || '');
    var indicator_name = String(r[H('indicator_name')] || '');
    var country        = String(r[H('country')] || '').toUpperCase();
    var release_ts     = r[H('release_ts')];
    if (!event_id || !indicator_name || !release_ts) continue;

    // Resolve provider/series/transform
    var map = null;

    // Preferred: canonical resolver signature (eventObj, seriesMap)
    if (typeof resolveSeriesForEvent === 'function') {
    map = resolveSeriesForEvent({ country: country, indicator_name: indicator_name }, seriesMap);
    }

    // Backward-compat: some builds use _resolveSeriesForEvent_(indicator_name, country, seriesMap)
    if (!map && typeof _resolveSeriesForEvent_ === 'function') {
    map = _resolveSeriesForEvent_(seriesMap, indicator_name, country);
    }

    // Last resort: try the legacy order you currently have (in case your _resolveSeriesForEvent_ expects it)
    _log_(shLog, 'info', 'Actuals: SeriesMap inputs', {
    event_id: event_id,
    country: country,
    indicator_name: indicator_name,
    has_resolveSeriesForEvent: (typeof resolveSeriesForEvent === 'function'),
    has__resolveSeriesForEvent_: (typeof _resolveSeriesForEvent_ === 'function'),
    seriesMap_rows: (seriesMap && seriesMap.length) ? seriesMap.length : 0,
    map_resolved: !!map,
    map_provider: map ? map.provider : '',
    map_series_id: map ? map.series_id : ''
    });

    if (!map) {
    _log_(shLog, 'warn', 'Actuals: No SeriesMap match', {
    event_id: event_id,
    indicator_name: indicator_name,
    country: country
    });

    var _k = (country + '|' + indicator_name).toUpperCase();
    if (!_suggestedKeys[_k] && typeof appendSeriesMapSuggestion_ === 'function') {
    appendSeriesMapSuggestion_(country, indicator_name, relDate);
    _suggestedKeys[_k] = true;
    }
    continue;
    }
    
    if (map && (map.provider === 'FILTER' || /synthetic batch event/i.test(map.notes || ''))) {
      _log_(shLog, 'info', 'Actuals: skipped by SeriesMap filter', { indicator_name: indicator_name, event_id: event_id });
      continue;
    }

    // Reference period (month end heuristic)
    var ref = (typeof _refMonthEnd_ === 'function') ? _refMonthEnd_(release_ts) : new Date(release_ts);

    // Fetch from providers (FRED-first, then FMP, etc.)
    var res = (typeof _fetchActualFromProviders_ === 'function')
      ? _fetchActualFromProviders_({
          provider: map.provider,
          series_id: map.series_id,
          transform: map.transform,
          freq: map.freq || '',
          ref: ref,
          event_id: event_id,
          indicator_name: indicator_name
        })
      : { hasActual: false };

    if (!res || !res.hasActual) {
      _log_(shLog, 'info', 'Actuals: fetch skipped', {
        event_id: event_id,
        indicator_name: indicator_name,
        country: country,
        map_provider: map ? map.provider : '',
        map_series_id: map ? map.series_id : '',
        map_transform: map ? map.transform : '',
        reason: (res && res.reason) ? res.reason : 'UNKNOWN',
        provider_tried: (res && res.provider) ? res.provider : (map ? map.provider : '')
      });
      continue;
    }

    // Current state
    var currentStatus = String(r[H('release_status')] || '').toLowerCase();
    var newStatus = (currentStatus === 'scheduled') ? 'released' : currentStatus;

    // Revision detection
    var previousVal = r[H('released_value')];
    var prevNum = (previousVal === '' || previousVal === null || previousVal === undefined) ? null : Number(previousVal);
    var isDiff = (prevNum === null && (res.value === 0 || res.value)) ||
                 (prevNum !== null && (Number(prevNum).toFixed(10) !== Number(res.value || '').toFixed(10)));
    if (currentStatus === 'released' || currentStatus === 'revised') {
      if (isDiff) newStatus = 'revised';
    }

    // Stage updates (apply consistent rounding if available)
    var rounded = (typeof roundByUnit === 'function')
      ? roundByUnit(res.value, map.unit_type, (map.transform || 'level').toUpperCase())
      : ((res.value === 0 || res.value) ? Number(res.value) : '');

    pending[idx] = {
      released_value: (rounded === 0 || rounded) ? rounded : '',
      released_ts: res.ts ? _parseReleaseTsUtcMinute_(res.ts) : (r[H('released_ts')] || ''),
      source_provider: res.provider || map.provider || '',
      source_series_id: res.series_id || map.series_id || '',
      transform: res.transform || map.transform || '',
      release_status: newStatus
    };


    updated++;
    if (newStatus === 'released') released++;
    if (newStatus === 'revised')  revised++;
  }

  // Apply updates
  var keys = Object.keys(pending);
  if (keys.length) {
    for (var x = 0; x < keys.length; x++) {
      var i = Number(keys[x]);
      var upd = pending[i];
      if (H.has('released_value'))  data[i][H('released_value')]  = upd.released_value;
      if (H.has('released_ts'))     data[i][H('released_ts')]     = upd.released_ts;
      if (H.has('source_provider')) data[i][H('source_provider')] = upd.source_provider;
      if (H.has('source_series_id'))data[i][H('source_series_id')]= upd.source_series_id;
      if (H.has('transform'))       data[i][H('transform')]       = upd.transform;
      if (H.has('release_status'))  data[i][H('release_status')]  = upd.release_status;
    }
    shEvent.getRange(2, 1, data.length, lastCol).setValues(data);
    SpreadsheetApp.flush();
  }

  _log_(shLog, 'info', 'Actuals: scan done (window)', {
    inspected: candIdx.length, updated: updated, released: released, revised: revised,
    window_from: lo.toISOString(), window_to: hi.toISOString(), duration_ms: (new Date()) - started
  });
  return {
  inspected: candIdx.length,
  updated:   updated,
  released:  released,
  revised:   revised,
  window_from: lo.toISOString(),
  window_to:   hi.toISOString()
  };
}


/** ===== Provider adapters ===== **/

function _fetchActualFromProviders_(args) {
  // Build provider order: explicit map provider first, then configured priority
  var order = [];
  if (args && args.provider) order.push(String(args.provider).toUpperCase());
  for (var i = 0; i < ACTUALS_CFG.SOURCE_PRIORITY.length; i++) {
    var p = ACTUALS_CFG.SOURCE_PRIORITY[i];
    if (order.indexOf(p) === -1) order.push(p);
  }

  // Resolve window bounds once for all providers
  var windowStartIso = String(args && (args.windowStartIso || args.window_start || args.refStart || args.ref || '')).trim();
  var windowEndIso   = String(args && (args.windowEndIso   || args.window_end   || args.refEnd   || args.ref || '')).trim();

  var lastFail = null;

  // Loop providers by priority
  for (var j = 0; j < order.length; j++) {
    var provider = order[j];

    // ------------------------------
    // FRED
    // ------------------------------
    if (provider === 'FRED') {
      // Validate/normalize series_id
      var seriesId = String((args && args.series_id) || '').trim();
      if (!seriesId) {
        try { if (typeof _logWarn === 'function') _logWarn('Actuals:FRED', 'Skipped — empty series_id', args); } catch (e) {}
        Logger.log('[Actuals:FRED] Skipped — empty series_id: ' + JSON.stringify(args));
                lastFail = { reason: 'EMPTY_SERIES_ID', provider: 'FRED' };
        continue;
      }

      // Try to fetch observations within the window
      try {
        var fredObs = _fredFetchObservations_(seriesId, args.ref);
        if (!fredObs || !fredObs.latest) {
          try { if (typeof _logWarn === 'function') _logWarn('Actuals:FRED', 'No observations in window — skipped', { seriesId: seriesId, windowStartIso: windowStartIso, windowEndIso: windowEndIso }); } catch (e) {}
          Logger.log('[Actuals:FRED] No observations in window — skipped: ' + seriesId);
                    lastFail = { reason: 'NO_OBSERVATIONS', provider: 'FRED', series_id: seriesId };
          continue;
        }

        // Base value from latest observation
        var rawValue = (fredObs.latest.value !== undefined && fredObs.latest.value !== null)
          ? Number(fredObs.latest.value)
          : null;

        // Optional transform support: if your transform expects an observations array,
        // provide fredObs.observations when available; otherwise fall back to the single latest point.
        var value = rawValue;
        if (args && args.transform && typeof _computeTransform_ === 'function') {
          var seriesForTransform = (fredObs.observations && fredObs.observations.length)
            ? fredObs.observations
            : [{ date_iso: fredObs.latest.date_iso, value: rawValue }];
          value = _computeTransform_(args.transform, seriesForTransform);
        }

        if (value === null || value === undefined || value === '') {
          try { if (typeof _logWarn === 'function') _logWarn('Actuals:FRED', 'Transform produced empty value — skipped', { seriesId: seriesId, transform: args.transform || '' }); } catch (e) {}
          Logger.log('[Actuals:FRED] Transform produced empty value — skipped: ' + seriesId);
                    lastFail = { reason: 'TRANSFORM_EMPTY', provider: 'FRED', series_id: seriesId, transform: (args && args.transform) ? String(args.transform) : '' };
          continue;
        }

        // Success: return immediately
        return {
          hasActual: true,
          value: value,
          ts: fredObs.latest.date_iso,            // ISO UTC of the observation
          provider: 'FRED',
          series_id: seriesId,
          transform: args.transform || '',
          meta: fredObs.meta || {}
        };

      } catch (fredErr) {
        try { if (typeof _logWarn === 'function') _logWarn('Actuals:FRED', 'Fetch failed — skipped', { seriesId: seriesId, error: String(fredErr) }); } catch (e) {}
        Logger.log('[Actuals:FRED] Fetch failed — skipped: ' + seriesId + ' :: ' + fredErr);
                lastFail = { reason: 'FETCH_ERROR', provider: 'FRED', series_id: seriesId, error: String(fredErr) };
        continue;
      }
    }

    // ------------------------------
    // FMP (placeholder adapter; keep behavior consistent with your existing implementation)
    // ------------------------------
    if (provider === 'FMP') {
      try {
        // Keep current call signature if your _fmpFetchActual_ expects (series_id, ref)
        var fmpRes = _fmpFetchActual_(String((args && args.series_id) || '').trim(), windowEndIso || (args && args.ref) || '');
        if (fmpRes && fmpRes.hasActual) {
          return fmpRes; // expected shape: { hasActual, value, ts, provider:'FMP', series_id, transform? }
        }
      } catch (fmpErr) {
        try { if (typeof _logWarn === 'function') _logWarn('Actuals:FMP', 'Fetch failed — skipped', { series_id: args && args.series_id, error: String(fmpErr) }); } catch (e) {}
        Logger.log('[Actuals:FMP] Fetch failed — skipped: ' + (args && args.series_id) + ' :: ' + fmpErr);
                lastFail = { reason: 'FETCH_ERROR', provider: 'FMP', series_id: String((args && args.series_id) || '').trim(), error: String(fmpErr) };
        continue;
      }
    }
  }

  // Nothing resolved from any provider
  return { hasActual: false, reason: (lastFail && lastFail.reason) ? lastFail.reason : 'NO_PROVIDER_MATCH', provider: (lastFail && lastFail.provider) ? lastFail.provider : '' };
}


// FRED observations around ref month end (18-month window)
function _fredFetchObservations_(seriesId, refDate) {
  // Guard — empty ID returns null, do not throw
  seriesId = String(seriesId || '').trim();
  if (!seriesId) {
    Logger.log('[FRED] Empty seriesId => return null');
    return null;
  }

  var key = (PropertiesService.getScriptProperties().getProperty('FRED_API_KEY') || '').trim();
  if (!key) return null;
  var end = new Date(Date.UTC(refDate.getUTCFullYear(), refDate.getUTCMonth() + 1, 0)); // end of ref month
  var start = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - 18, 1));

  var cache = CacheService.getScriptCache();
  var cacheKey = 'fred:' + seriesId + ':' + _ym_(start) + ':' + _ym_(end);
  var cached = cache.get(cacheKey);
  if (cached) return JSON.parse(cached);

  var params = {
    series_id: seriesId,
    api_key: key,
    file_type: 'json',
    observation_start: start.getUTCFullYear() + '-' + String(start.getUTCMonth() + 1).padStart(2, '0') + '-01',
    // IMPORTANT: use the actual end-of-month day, not "-01"
    observation_end: end.getUTCFullYear() + '-' + String(end.getUTCMonth() + 1).padStart(2, '0') + '-' + String(end.getUTCDate()).padStart(2, '0')
  };
  var url = 'https://api.stlouisfed.org/fred/series/observations?' +
      Object.keys(params).map(function(k){ return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); }).join('&');

  try {
    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    var code = resp && resp.getResponseCode ? resp.getResponseCode() : 0;
    if (code < 200 || code >= 300) {
      Logger.log('[FRED] Non-2xx (' + code + ') for ' + seriesId + ' — returning null');
      return null;
    }
    var payload = resp.getContentText();
    var json = payload ? JSON.parse(payload) : null;
    if (!json || !json.observations || !json.observations.length) {
      Logger.log('[FRED] No observations for ' + seriesId + ' — returning null');
      return null;
    }

    // Your existing logic to select latest in [windowStartIso, windowEndIso]
    // Compute local window bounds from the refDate-derived request range.
    // (This removes reliance on undefined outer variables.)
    var localWindowStartIso = params.observation_start;
    var localWindowEndIso   = params.observation_end;

    var latest = _pickLatestObservationInWindow_(json.observations, localWindowStartIso, localWindowEndIso);
    if (!latest) return null;

    // build normalized observations for transforms
    var observations = (json.observations || []).map(function(o){
    var dt = String(o.date || o.date_iso || o.dateUtc || o.date_utc || '').slice(0, 10);
    var raw = o.value;
    if (raw === null || raw === undefined || raw === '' || raw === '.') return null;
    var v = Number(raw);
    if (!isFinite(v)) return null;
    return { date_iso: dt, value: v };
    }).filter(function(x){ return !!x; });


    return {
    latest: {
    date_iso: latest.date_iso || latest.date || latest.dateUtc || latest.date_utc,
    value: (latest.value !== undefined && latest.value !== null) ? Number(latest.value) : null
    },
    observations: observations,
    meta: {
    units: json.units || null,
    realtime_start: json.realtime_start || null,
    realtime_end: json.realtime_end || null
    }
    };
  } catch (e) {
    Logger.log('[FRED] Exception fetching ' + seriesId + ' — returning null: ' + e);
    return null;
  }
}

// Placeholder for FMP actuals (implement later if needed)
function _fmpFetchActual_(seriesId, refDate) {
  try {
    seriesId = String(seriesId || '').trim();
    if (!seriesId) return { hasActual: false };

    // Expecting "calendar:<Event Name>" from SeriesMap for FMP mappings
    var m = seriesId.match(/^calendar:(.+)$/i);
    if (!m) return { hasActual: false };
    var targetName = m[1].trim().toLowerCase();

    // API base & key (same convention as fmp_calendar.gs)
    var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
    if (!apiKey) return { hasActual: false };
    var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';

    // Build a ±1 day window around the refDate (date-only)
    var ref = (refDate && String(refDate).trim()) ? new Date(refDate) : new Date();
    var d0 = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), ref.getUTCDate() - 1));
    var d1 = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), ref.getUTCDate() + 1));
    function _ymd(d){ return d.getUTCFullYear() + '-' + String(d.getUTCMonth()+1).padStart(2,'0') + '-' + String(d.getUTCDate()).padStart(2,'0'); }

    var url = base + '/economic_calendar'
      + '?from=' + _ymd(d0)
      + '&to='   + _ymd(d1)
      + '&apikey=' + encodeURIComponent(apiKey);

    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    var code = resp && resp.getResponseCode ? resp.getResponseCode() : 0;
    if (code < 200 || code >= 300) return { hasActual: false };

    var json = JSON.parse(resp.getContentText() || '[]');
    if (!Array.isArray(json) || !json.length) return { hasActual: false };

    // Find the matching event by name (case-insensitive exact match on 'event')
    var match = json.find(function(row){
      var ev = String(row.event || '').trim().toLowerCase();
      return ev === targetName && (row.actual !== undefined && row.actual !== null && row.actual !== '');
    });
    if (!match) return { hasActual: false };

    // Normalize value and timestamp
    var val = Number(match.actual);
    if (!isFinite(val)) return { hasActual: false };

    var ts = (match.dateUtc || match.date || match.time || '').trim();
    // Fall back to refDate if FMP doesn’t provide a clean ISO
    var iso = ts ? ts : (ref.toISOString());

    return {
      hasActual: true,
      value: val,
      ts: iso,
      provider: 'FMP',
      series_id: seriesId
      // transform: (optional) let the caller apply map.transform as you already do
    };
  } catch (e) {
    try { if (typeof _logWarn === 'function') _logWarn('Actuals:FMP exception', { seriesId: seriesId, error: String(e) }); } catch (_){}
    return { hasActual: false };
  }
}


/** ===== Transform engine (levels → MoM/YoY, SAAR, etc.) ===== **/
function _computeTransform_(transform, observations) {
  // observations: [{date: 'YYYY-MM-DD', value: Number|null}, ...] monthly frequency assumed
  var t = String(transform || '').toLowerCase().trim();
  if (!observations || !observations.length) return null;

  // find last non-null (ref) and previous values
  var last = null, prev = null, prev12 = null;
  for (var i = observations.length - 1; i >= 0; i--) {
    var v = observations[i].value;
    if (v !== null && v !== undefined && v !== '') {
      if (!last) { last = { idx: i, value: v }; continue; }
      if (!prev) { prev = { idx: i, value: v }; }
      if (!prev12 && (i <= last.idx - 12)) { prev12 = { idx: i, value: v }; }
      if (last && prev && prev12) break;
    }
  }
  if (!last) return null;
  if (t === '' || t === 'level' || t === 'lin') {
    return Number(last.value);
  }
  if (t === 'mom' || t === 'pct_change' || t === 'pct_mom') {
    if (!prev) return null;
    return ((last.value / prev.value) - 1) * 100;
  }
  if (t === 'yoy' || t === 'pct_yoy') {
    if (!prev12) return null;
    return ((last.value / prev12.value) - 1) * 100;
  }
  if (t === 'saar') {
    if (!prev) return null;
    var mom = ((last.value / prev.value) - 1);
    return (Math.pow(1 + mom, 12) - 1) * 100;
  }
  if (t === 'diff' || t === 'delta' || t === 'chg') {
    if (!prev) return null;
    return Number(last.value) - Number(prev.value);
  }
  // Unknown transform → return level
  return Number(last.value);
}

/** ===== SeriesMap loader & resolver ===== **/
function _loadSeriesMap_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName('SeriesMap');
  if (!sh) return [];
  var lastRow = sh.getLastRow(), lastCol = sh.getLastColumn();
  if (lastRow < 2 || lastCol < 1) return [];
  var headers = _getHeaderNames_(sh);
  var H = _buildHeaderIndex_(headers);

  // Expect: indicator_name_pattern (not indicator_name)
  var rows = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    out.push({
    indicator_name_pattern: String(r[H('indicator_name_pattern')] || ''),
    country: String(r[H('country')] || '').toUpperCase(),
    provider: _normProvider_(r[H('provider')]),
    series_id: String(r[H('series_id')] || '').trim(),
    transform: _normTransform_(r[H('transform')]),
    freq: _normFreq_(r[H('freq')]),
    unit_type: _normUnitAndPrecision_(r[H('unit_type')]).unit_type,
    seasonal_adjustment: _normSeasonal_(r[H('seasonal_adjustment')]),
    precision_dp: String(_normUnitAndPrecision_(r[H('unit_type')]).precision_dp || r[H('precision_dp')] || ''),
    lag_rule: String(r[H('lag_rule')] || ''),
    notes: String(r[H('notes')] || '')
  });

  }
  return out;
}

function _normalizeIndicatorKey_(name) {
  var s = String(name || '').trim();
  s = s.replace(/\s*\([^)]*\)\s*$/, '');   // remove trailing "(Oct/04)" etc.
  s = s.replace(/\s+/g, ' ').toLowerCase();
  return s;
}

function _resolveSeriesForEvent_(mapRows, indicator_name, country) {
  var target = _normalizeIndicatorKey_(indicator_name);
  var cc = String(country || '').toUpperCase();
  for (var i = 0; i < mapRows.length; i++) {
    var m = mapRows[i];
    if (String(m.country || '').toUpperCase() !== cc) continue;

    var pat = String(m.indicator_name_pattern || '');
    if (!pat) continue;

    // Support simple substring patterns and regex (if pattern is /.../)
    var hit = false;
    if (pat.startsWith('/') && pat.endsWith('/')) {
      try {
        var rx = new RegExp(pat.slice(1, -1), 'i');
        hit = rx.test(indicator_name);
      } catch (e) { hit = false; }
    } else {
      hit = _normalizeIndicatorKey_(pat) === target || target.indexOf(_normalizeIndicatorKey_(pat)) >= 0;
    }
    if (hit && m.provider && m.series_id) return m;
  }
  return null;
}



/** ===== Helpers - 31days training  - ===== **/




/** ===== Helpers ===== **/
function _getHeaderNames_(sh) {
  var lastCol = sh.getLastColumn();
  var headers = sh.getRange(1, 1, 1, Math.max(1, lastCol)).getValues()[0] || [];
  return headers.map(function(h){ return String(h || ''); });
}
function _buildHeaderIndex_(headers) {
  var map = {};
  for (var i = 0; i < headers.length; i++) {
    var k = String(headers[i]).trim().toLowerCase();
    if (!map.hasOwnProperty(k)) map[k] = i;
  }
  function H(name) {
    var key = String(name).trim().toLowerCase();
    if (!map.hasOwnProperty(key)) return -1;
    return map[key];
  }
  H.has = function(name){ return H(name) >= 0; };
  return H;
}
function _ym_(d) {
  var y = d.getUTCFullYear();
  var m = String(d.getUTCMonth() + 1).padStart(2, '0');
  return y + '-' + m;
}
function _refMonthEnd_(release_ts) {
  var d = (release_ts instanceof Date) ? new Date(release_ts.getTime()) : new Date(String(release_ts || ''));
  if (String(d) === 'Invalid Date') d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0, 0, 0, 0, 0));
}
function _log_(logSheet, level, msg, ctx) {
  try {
    if (typeof appendLog === 'function') appendLog(logSheet, level, msg, ctx || {});
    else logSheet.appendRow([new Date().toISOString(), level, msg, JSON.stringify(ctx || {})]);
  } catch (e) {}
}


function _pickLatestObservationInWindow_(observations, windowStartIso, windowEndIso) {
  observations = observations || [];
  var start = String(windowStartIso || '').slice(0, 10);
  var end   = String(windowEndIso   || '').slice(0, 10);

  var best = null;
  for (var i = 0; i < observations.length; i++) {
    var o = observations[i] || {};
    var dt = String(o.date || o.date_iso || o.dateUtc || o.date_utc || '').slice(0, 10);
    if (!dt) continue;

    // date window (inclusive)
    if (start && dt < start) continue;
    if (end   && dt > end)   continue;

    var raw = o.value;
    if (raw === null || raw === undefined || raw === '' || raw === '.') continue;

    var v = Number(raw);
    if (!isFinite(v)) continue;

    // pick the latest date
    if (!best || dt > best.date_iso) {
      best = { date_iso: dt, value: v };
    }
  }
  return best;
}


/** ===== Normalize indicator names before map lookup ===== **/
function _normalizeIndicatorKey_(name) {
  var s = String(name || '').trim();
  // drop trailing parenthetical like " (Oct/04)" or "(Sep/27)"
  s = s.replace(/\s*\([^)]*\)\s*$/, '');
  // collapse spaces, lowercase
  s = s.replace(/\s+/g, ' ').toLowerCase();
  return s;
}

// ===== Normalizers =====
function _normFreq_(s) {
  var v = String(s || '').trim().toLowerCase();
  if (!v) return '';
  // weekly
  if (v === 'w' || v === 'wk' || v === 'wkly' || v.indexOf('week') >= 0) return 'weekly';
  // monthly
  if (v === 'm' || v === 'mo' || v === 'mnth' || v === 'mth' || v.indexOf('month') >= 0) return 'monthly';
  // quarterly
  if (v === 'q' || v === 'qtr' || v.indexOf('quarter') >= 0) return 'quarterly';
  // daily
  if (v === 'd' || v.indexOf('day') >= 0) return 'daily';
  // annual / yearly
  if (v === 'a' || v === 'y' || v === 'yr' || v.indexOf('year') >= 0 || v.indexOf('annual') >= 0) return 'annual';
  return v;
}


function _normProvider_(s) {
  var v = String(s || '').trim().toUpperCase();
  if (!v) return '';
  if (v === 'FRED') return 'FRED';
  if (v === 'FMP' || v === 'FMP_CAL' || v === 'FMP_CALENDAR') return 'FMP';
  if (v === 'FILTER' || v === 'SKIP') return 'FILTER'; // special "skip" provider
  return v;
}

function _normTransform_(s) {
  var v = String(s || '').trim().toLowerCase();
  if (!v) return 'level';
  // canonical
  if (v === 'level' || v === 'lin') return 'level';
  if (v === 'mom' || v === 'mom_pct' || v === 'pct_change' || v === 'pct_mom') return 'mom';
  if (v === 'yoy' || v === 'yoy_pct' || v === 'pct_yoy') return 'yoy';
  if (v === 'diff' || v === 'delta' || v === 'chg') return 'diff';
  if (v === 'saar') return 'saar';
  // fix common misplacements (e.g., uppercased tokens)
  if (v === 'mom_pct'.toUpperCase().toLowerCase()) return 'mom';
  if (v === 'yoy_pct'.toUpperCase().toLowerCase()) return 'yoy';
  if (v === 'level'.toUpperCase().toLowerCase())   return 'level';
  // fallback to level
  return 'level';
}

// Parses combined tokens like "thousands_0dp", "index_1dp", "percent_1dp"
function _normUnitAndPrecision_(s) {
  var raw = String(s || '').trim().toLowerCase();
  var unit = '', dp = '';
  if (!raw) return { unit_type: '', precision_dp: '' };

  // structured tokens
  var m = raw.match(/^([a-z]+)_([0-9]+)dp$/i);
  if (m) {
    var base = m[1].toLowerCase();
    dp = String(parseInt(m[2], 10));
    if (base === 'percent' || base === 'pct') unit = 'pct';
    else if (base === 'index') unit = 'index';
    else if (base === 'thousands' || base === 'k') unit = 'thousands';
    else unit = base; // raw, persons, etc.
    return { unit_type: unit, precision_dp: dp };
  }

  // simple tokens
  if (raw === 'raw' || raw === 'level') unit = 'raw';
  if (raw === 'k' || raw === 'thousands') unit = 'thousands';
  if (raw === 'pct' || raw === 'percent') unit = 'pct';
  if (raw === 'index') unit = 'index';
  if (raw === 'persons') unit = 'persons';
  if (raw === 'hours') unit = 'hours';

  // one-off misfile (e.g., "M" ended up in unit_type column)
  if (_normFreq_(raw) !== raw) {
    // treat as no unit, leave precision blank
    return { unit_type: '', precision_dp: '' };
  }

  return { unit_type: unit || raw, precision_dp: dp };
}

// Map lots of phrasing to SA/NSA or leave blank if it's just guidance text
function _normSeasonal_(s) {
  var v = String(s || '').trim();
  if (!v) return '';
  var low = v.toLowerCase();

  // clear SA / NSA cues
  if (low === 'sa' || low.indexOf('seasonally adjusted') >= 0 || low.indexOf('use sa series') >= 0) return 'SA';
  if (low === 'nsa' || low.indexOf('not seasonally') >= 0 || low.indexOf('(nsa)') >= 0) return 'NSA';

  // common “guidance” phrases — don’t force SA/NSA, just normalize away
  var guidance = [
    'compute mom%', 'compute yoy', 'headline', 'case-shiller', 'pce',
    'core', 'index', 'calendar', 'synthetic batch event'
  ];
  if (guidance.some(function(k){ return low.indexOf(k) >= 0; })) return '';

  // accidental values like LEVEL/MOM_PCT/YOY_PCT appearing here → ignore
  if (low === 'level' || low === 'mom_pct' || low === 'yoy_pct') return '';

  return v.toUpperCase(); // pass through any other explicit small flags
}

// Qualitative / non-numeric things we should skip in actuals
function _shouldSkipActuals_(name) {
  var s = _normalizeIndicatorKey_(name);
  var patterns = [
    /speech/,                      // Fed Chair Powell Speech, Fed Bowman Speech
    /auction/,                     // 4-Week Bill Auction, 30-Year Bond Auction
    /wasde/,                       // WASDE Report
    ///gdpnow/,                      // Atlanta Fed GDPNow
    ///balance\s*sheet/,             // Fed Balance Sheet
    /employment\s*trends\s*index/  // CB Employment Trends Index (composite; skip unless mapped)
  ];
  return patterns.some(function(rx){ return rx.test(s); });
}

/** ===== Refactor the hourly entrypoint to call a shared worker ===== **/
function runFetchActualsHourly_() {
  return runFetchActualsWindow_(ACTUALS_CFG.LOOKBACK_MINUTES, ACTUALS_CFG.LOOKAHEAD_MINUTES, ACTUALS_CFG.MAX_ROWS_PER_RUN);
}






