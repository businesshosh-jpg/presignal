/*********************************************************
 * actuals_direct_resolver.gs
 * Deterministic direct-actual resolver for economic events.
 *
 * Resolution order:
 *   1) Direct provider resolution (FMP calendar, metadata-driven)
 *   2) SeriesMap fallback (delegated to existing pipeline)
 *
 * No AI / fuzzy inference is used here. Matching is deterministic:
 *   - exact country match
 *   - release timestamp within a fixed window
 *   - exact normalized title equivalence via rule-based aliases
 **********************************************************/

var ACTUALS_DIRECT_CFG = {
  PROVIDER: 'FMP',
  WINDOW_DAYS_BEFORE: 1,
  WINDOW_DAYS_AFTER: 1,
  RELEASE_TS_TOLERANCE_MINUTES: 180,
  CACHE_TTL_SEC: 300
};

var __ACTUALS_DIRECT_WINDOW_CACHE__ = {};

var ACTUALS_DIRECT_TITLE_EQUIV = {
  'cb consumer confidence': ['consumer confidence'],
  'consumer confidence': ['cb consumer confidence'],
  'initial jobless claims': ['jobless claims', 'initial claims'],
  'jobless claims': ['initial jobless claims', 'initial claims'],
  'continuing jobless claims': ['continuing claims'],
  'api weekly crude oil stock': ['api weekly crude oil stocks'],
  'michigan 1 year inflation expectations': ['michigan inflation expectations 1 year']
};

function ensureActualsAuditHeaders_(sh) {
  if (!sh) return [];
  var required = ['resolution_method', 'confidence_level'];
  var headers = _getHeaderNames_(sh);
  var have = {};
  for (var i = 0; i < headers.length; i++) {
    have[String(headers[i] || '').trim().toLowerCase()] = true;
  }
  var toAppend = [];
  for (var j = 0; j < required.length; j++) {
    if (!have[required[j]]) toAppend.push(required[j]);
  }
  if (toAppend.length) {
    sh.getRange(1, headers.length + 1, 1, toAppend.length).setValues([toAppend]);
    headers = headers.concat(toAppend);
  }
  return headers;
}

function _resolveActualHybrid_(event, seriesMap, logSheet) {
  var direct = _resolveActualDirect_(event, logSheet);
  if (direct && direct.hasActual) {
    return direct;
  }

  _logActualsAttempt_(logSheet, 'info', 'Actuals: direct path failed, fallback triggered', {
    event_id: event && event.event_id ? event.event_id : '',
    resolution_path: 'direct',
    provider: direct && direct.provider ? direct.provider : ACTUALS_DIRECT_CFG.PROVIDER,
    fallback_triggered: true,
    success: false,
    reason: direct && direct.reason ? direct.reason : 'DIRECT_UNRESOLVED'
  });

  return _resolveActualViaSeriesMapFallback_(event, seriesMap, logSheet, direct);
}

function _resolveActualDirect_(event, logSheet) {
  var rows = _fmpFetchCalendarForEvent_(event);
  if (!rows.length) {
    _logActualsAttempt_(logSheet, 'info', 'Actuals: direct path miss', {
      event_id: event.event_id,
      resolution_path: 'direct',
      provider: ACTUALS_DIRECT_CFG.PROVIDER,
      fallback_triggered: false,
      success: false,
      reason: 'NO_PROVIDER_ROWS'
    });
    return {
      hasActual: false,
      resolution_method: 'direct',
      confidence_level: 'medium',
      provider: ACTUALS_DIRECT_CFG.PROVIDER,
      reason: 'NO_PROVIDER_ROWS'
    };
  }

  var match = _matchDirectActualCandidate_(event, rows);
  if (!match) {
    _logActualsAttempt_(logSheet, 'info', 'Actuals: direct path miss', {
      event_id: event.event_id,
      resolution_path: 'direct',
      provider: ACTUALS_DIRECT_CFG.PROVIDER,
      fallback_triggered: false,
      success: false,
      reason: 'NO_DETERMINISTIC_MATCH'
    });
    return {
      hasActual: false,
      resolution_method: 'direct',
      confidence_level: 'medium',
      provider: ACTUALS_DIRECT_CFG.PROVIDER,
      reason: 'NO_DETERMINISTIC_MATCH'
    };
  }

  _logActualsAttempt_(logSheet, 'info', 'Actuals: direct path resolved', {
    event_id: event.event_id,
    resolution_path: 'direct',
    provider: 'FMP',
    fallback_triggered: false,
    success: true,
    reason: match.match_reason,
    matched_title: match.matched_title
  });

  return {
    hasActual: true,
    value: match.value,
    ts: match.ts,
    provider: 'FMP',
    series_id: match.source_series_id || '',
    transform: '',
    resolution_method: 'direct',
    confidence_level: 'medium',
    match_reason: match.match_reason
  };
}

function _resolveActualViaSeriesMapFallback_(event, seriesMap, logSheet, directAttempt) {
  var map = null;

  if (typeof resolveSeriesForEvent === 'function') {
    map = resolveSeriesForEvent({
      country: event.country,
      indicator_name: event.indicator_name
    }, seriesMap);
  }

  if (!map && typeof _resolveSeriesForEvent_ === 'function') {
    map = _resolveSeriesForEvent_(seriesMap, event.indicator_name, event.country);
  }

  if (!map) {
    _logActualsAttempt_(logSheet, 'warn', 'Actuals: no direct or SeriesMap resolution', {
      event_id: event.event_id,
      resolution_path: 'seriesmap',
      provider: '',
      fallback_triggered: true,
      success: false,
      reason: directAttempt && directAttempt.reason ? directAttempt.reason : 'NO_SERIESMAP_MATCH'
    });
    return {
      hasActual: false,
      resolution_method: 'seriesmap',
      confidence_level: 'high',
      reason: 'NO_SERIESMAP_MATCH'
    };
  }

  if (map && (map.provider === 'FILTER' || /synthetic batch event/i.test(map.notes || ''))) {
    _logActualsAttempt_(logSheet, 'info', 'Actuals: SeriesMap filter skip', {
      event_id: event.event_id,
      resolution_path: 'seriesmap',
      provider: map.provider || '',
      fallback_triggered: true,
      success: false,
      reason: 'FILTERED'
    });
    return {
      hasActual: false,
      resolution_method: 'seriesmap',
      confidence_level: 'high',
      reason: 'FILTERED'
    };
  }

  var ref = (typeof _refMonthEnd_ === 'function') ? _refMonthEnd_(event.release_ts) : new Date(event.release_ts);
  var res = (typeof _fetchActualFromProviders_ === 'function')
    ? _fetchActualFromProviders_({
        provider: map.provider,
        series_id: map.series_id,
        transform: map.transform,
        freq: map.freq || '',
        ref: ref,
        event_id: event.event_id,
        indicator_name: event.indicator_name
      })
    : { hasActual: false, reason: 'FETCHER_UNAVAILABLE' };

  if (!res || !res.hasActual) {
    _logActualsAttempt_(logSheet, 'info', 'Actuals: SeriesMap fetch miss', {
      event_id: event.event_id,
      resolution_path: 'seriesmap',
      provider: map.provider || '',
      fallback_triggered: true,
      success: false,
      reason: (res && res.reason) ? res.reason : 'FETCH_FAILED',
      source_series_id: map.series_id || ''
    });
    return {
      hasActual: false,
      resolution_method: 'seriesmap',
      confidence_level: 'high',
      reason: (res && res.reason) ? res.reason : 'FETCH_FAILED'
    };
  }

  _logActualsAttempt_(logSheet, 'info', 'Actuals: SeriesMap fallback resolved', {
    event_id: event.event_id,
    resolution_path: 'seriesmap',
    provider: res.provider || map.provider || '',
    fallback_triggered: true,
    success: true,
    reason: 'SERIESMAP_FETCH_OK',
    source_series_id: res.series_id || map.series_id || ''
  });

  return {
    hasActual: true,
    value: res.value,
    ts: res.ts,
    provider: res.provider || map.provider || '',
    series_id: res.series_id || map.series_id || '',
    transform: res.transform || map.transform || '',
    unit_type: map.unit_type || '',
    resolution_method: 'seriesmap',
    confidence_level: 'high'
  };
}

function _fmpFetchCalendarForEvent_(event) {
  var releaseDate = _safeActualsDate_(event && event.release_ts);
  if (!releaseDate) return [];

  var from = _actualsDateYmd_(new Date(Date.UTC(
    releaseDate.getUTCFullYear(),
    releaseDate.getUTCMonth(),
    releaseDate.getUTCDate() - ACTUALS_DIRECT_CFG.WINDOW_DAYS_BEFORE
  )));
  var to = _actualsDateYmd_(new Date(Date.UTC(
    releaseDate.getUTCFullYear(),
    releaseDate.getUTCMonth(),
    releaseDate.getUTCDate() + ACTUALS_DIRECT_CFG.WINDOW_DAYS_AFTER
  )));
  var country = String((event && event.country) || '').trim().toUpperCase();
  var cacheKey = [country || 'ALL', from, to].join('|');

  if (__ACTUALS_DIRECT_WINDOW_CACHE__.hasOwnProperty(cacheKey)) {
    return __ACTUALS_DIRECT_WINDOW_CACHE__[cacheKey];
  }

  var cache = null;
  try { cache = CacheService.getScriptCache(); } catch (e) {}
  if (cache) {
    var cached = cache.get('actuals:fmp:' + cacheKey);
    if (cached) {
      var parsed = JSON.parse(cached);
      __ACTUALS_DIRECT_WINDOW_CACHE__[cacheKey] = parsed;
      return parsed;
    }
  }

  var rows = fmpFetchRangeUtc_(from + 'T00:00:00Z', to + 'T23:59:00Z');
  if (country) {
    rows = rows.filter(function(row) {
      var rowCountry = String(row.country || row.countryCode || '').trim().toUpperCase();
      return rowCountry === country;
    });
  }

  __ACTUALS_DIRECT_WINDOW_CACHE__[cacheKey] = rows;
  if (cache) {
    try {
      cache.put('actuals:fmp:' + cacheKey, JSON.stringify(rows), ACTUALS_DIRECT_CFG.CACHE_TTL_SEC);
    } catch (e2) {}
  }
  return rows;
}

function _matchDirectActualCandidate_(event, rows) {
  var targetIso = _parseReleaseTsUtcMinute_(event && event.release_ts);
  if (!targetIso) return null;

  var targetAliases = _buildDirectTitleAliases_(event && event.indicator_name);
  var toleranceMs = Number(ACTUALS_DIRECT_CFG.RELEASE_TS_TOLERANCE_MINUTES || 0) * 60 * 1000;
  var matches = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var actualNum = _parseDirectActualNumber_(row.actual);
    if (actualNum === null) continue;

    var rowIso = _parseReleaseTsUtcMinute_(
      row.release_ts || row.dateUtc || row.date || row.datetime || row.time
    );
    if (!rowIso) continue;

    var deltaMs = Math.abs(new Date(rowIso).getTime() - new Date(targetIso).getTime());
    if (deltaMs > toleranceMs) continue;

    var candidateTitle = _coalesce_(
      row.indicator_name,
      row.event,
      row.title,
      row.name,
      row.category
    );
    var candidateAliases = _buildDirectTitleAliases_(candidateTitle);
    var reason = _deterministicTitleMatchReason_(targetAliases, candidateAliases);
    if (!reason) continue;

    matches.push({
      value: actualNum,
      ts: rowIso,
      matched_title: String(candidateTitle || ''),
      match_reason: reason,
      source_series_id: String(row.symbol || row.series || row.seriesId || row.code || row.id || ''),
      delta_ms: deltaMs
    });
  }

  if (!matches.length) return null;

  matches.sort(function(a, b) {
    if (a.delta_ms !== b.delta_ms) return a.delta_ms - b.delta_ms;
    if (a.match_reason !== b.match_reason) {
      return (a.match_reason === 'exact_normalized' ? -1 : 1);
    }
    return String(a.matched_title).localeCompare(String(b.matched_title));
  });

  return matches[0];
}

function _deterministicTitleMatchReason_(leftAliases, rightAliases) {
  var left = {};
  for (var i = 0; i < leftAliases.length; i++) left[leftAliases[i]] = true;
  for (var j = 0; j < rightAliases.length; j++) {
    if (left[rightAliases[j]]) {
      if (j === 0 && rightAliases[j] === leftAliases[0]) return 'exact_normalized';
      return 'title_equivalence';
    }
  }
  return '';
}

function _buildDirectTitleAliases_(name) {
  var base = _normalizeActualIndicatorName_(name);
  if (!base) return [];
  var out = [base];
  var extra = ACTUALS_DIRECT_TITLE_EQUIV[base] || [];
  for (var i = 0; i < extra.length; i++) {
    var normalized = _normalizeActualIndicatorName_(extra[i]);
    if (normalized && out.indexOf(normalized) === -1) out.push(normalized);
  }
  return out;
}

function _normalizeActualIndicatorName_(name) {
  var s = stripDateSuffix_(String(name || '').trim().toLowerCase());
  s = s.replace(/[%]/g, ' percent ');
  s = s.replace(/\b(preliminary|prelim|final|flash|advance|revised|estimate|est\.?)\b/g, ' ');
  s = s.replace(/[^a-z0-9]+/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

function _parseDirectActualNumber_(value) {
  if (value === null || value === undefined || value === '') return null;
  var n = _parseNumber_(value);
  return (n === null || !isFinite(n)) ? null : Number(n);
}

function _actualsDateYmd_(d) {
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
}

function _safeActualsDate_(input) {
  var d = (input instanceof Date) ? new Date(input.getTime()) : new Date(String(input || ''));
  return isFinite(d.getTime()) ? d : null;
}

function _logActualsAttempt_(logSheet, level, message, ctx) {
  if (!logSheet) return;
  _log_(logSheet, level, message, ctx || {});
}
