function _featurePackV2BEnabled_() {
  return !!((typeof CFG !== 'undefined') && CFG && CFG.FEATURE_PACK_V2B_ENABLED);
}

function _v2bDateOnly_(value) {
  return String(value || '').slice(0, 10);
}

function _v2bParseDate_(value) {
  var d = (value instanceof Date) ? value : new Date(String(value || ''));
  return (d instanceof Date && isFinite(d.getTime())) ? d : null;
}

function _v2bReleaseDateOnly_(ev) {
  var d = _v2bParseDate_(ev && ev.release_ts);
  if (!d) return '';
  return Utilities.formatDate(d, 'UTC', 'yyyy-MM-dd');
}

function _v2bReleaseDateTime_(ev) {
  var d = _v2bParseDate_(ev && ev.release_ts);
  return d ? d.toISOString() : '';
}

function _v2bOffsetDateIso_(dateIso, offsetDays) {
  var base = _v2bParseDate_(String(dateIso || '') + 'T00:00:00Z');
  if (!base) return String(dateIso || '').slice(0, 10);
  var shifted = new Date(base.getTime() + (Number(offsetDays || 0) * 24 * 60 * 60 * 1000));
  return Utilities.formatDate(shifted, 'UTC', 'yyyy-MM-dd');
}

function _v2bRowDate_(row) {
  return String((row && (row.date || row.date_iso || row.datetime || row.timestamp || row.dateUtc || row.date_utc)) || '').slice(0, 10);
}

function _v2bRowValue_(row) {
  if (!row) return null;
  var candidates = [row.value, row.close, row.c, row.price, row.level, row.actual, row.observation_value];
  for (var i = 0; i < candidates.length; i++) {
    var n = Number(candidates[i]);
    if (isFinite(n)) return n;
  }
  return null;
}

function _v2bSortRowsAsc_(rows) {
  return (rows || []).slice().sort(function(a, b) {
    return _cmpText_(_v2bRowDate_(a), _v2bRowDate_(b));
  });
}

function _v2bSnapshotAtOrBefore_(rows, targetDate) {
  var sorted = _v2bSortRowsAsc_(rows);
  var chosen = null;
  for (var i = 0; i < sorted.length; i++) {
    var d = _v2bRowDate_(sorted[i]);
    if (!d) continue;
    if (d <= targetDate) chosen = sorted[i];
    else break;
  }
  return chosen;
}

function _v2bObservationWindow_(rows, targetDate) {
  var sorted = _v2bSortRowsAsc_(rows).filter(function(row) {
    return !!_v2bRowDate_(row);
  });
  var idx = -1;
  for (var i = 0; i < sorted.length; i++) {
    if (_v2bRowDate_(sorted[i]) <= targetDate) idx = i;
    else break;
  }
  if (idx < 0) return { current: null, previous: null, previous5: null, sorted: [] };
  return {
    current: sorted[idx],
    previous: idx > 0 ? sorted[idx - 1] : null,
    previous5: idx > 4 ? sorted[idx - 5] : null,
    sorted: sorted
  };
}

function _v2bPctChange_(current, prior) {
  if (!isFinite(current) || !isFinite(prior) || prior === 0) return null;
  return Number((((current - prior) / prior) * 100).toFixed(4));
}

function _v2bPipChange_(current, prior) {
  if (!isFinite(current) || !isFinite(prior)) return null;
  return Number((((current - prior) * 100)).toFixed(2));
}

function _v2bSeriesHistoryKey_(provider, symbol, startIso, endIso) {
  return [provider, symbol, startIso, endIso].join('|');
}

function _v2bFetchFredHistory_(seriesId, startIso, endIso) {
  var key = (PropertiesService.getScriptProperties().getProperty('FRED_API_KEY') || '').trim();
  if (!key) return [];
  var url = 'https://api.stlouisfed.org/fred/series/observations'
    + '?series_id=' + encodeURIComponent(seriesId)
    + '&api_key=' + encodeURIComponent(key)
    + '&file_type=json'
    + '&observation_start=' + encodeURIComponent(startIso)
    + '&observation_end=' + encodeURIComponent(endIso)
    + '&sort_order=asc'
    + '&limit=5000';
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('FRED HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '{}');
  var obs = json && json.observations;
  if (!Array.isArray(obs)) throw new Error('FRED unexpected payload');
  return obs.map(function(row) {
    var v = row && row.value;
    var n = Number(v);
    return {
      date: String(row.date || '').slice(0, 10),
      value: isFinite(n) ? n : null
    };
  }).filter(function(row) { return row.date && isFinite(row.value); });
}

function _v2bFetchEodhdHistory_(symbol, startIso, endIso) {
  var key = _getEodhdApiKey_();
  if (!key) return [];
  var rows = _eodhdFetchEodWindow_(symbol, key, startIso, endIso, 'a');
  return (rows || []).map(function(row) {
    var n = Number(row && row.close);
    return {
      date: _v2bRowDate_(row),
      value: isFinite(n) ? n : null
    };
  }).filter(function(row) { return row.date && isFinite(row.value); });
}

function _v2bFetchFmpHistory_(symbol, startIso, endIso) {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  if (!apiKey) return [];
  var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, startIso, endIso);
  return (rows || []).map(function(row) {
    var n = Number(row && row.close);
    return {
      date: _v2bRowDate_(row),
      value: isFinite(n) ? n : null
    };
  }).filter(function(row) { return row.date && isFinite(row.value); });
}

function _v2bBuildSeriesCache_(startIso, endIso) {
  var cache = { meta: { startIso: startIso, endIso: endIso }, series: {} };
  cache.series['FRED:FEDFUNDS'] = _v2bFetchFredHistory_('FEDFUNDS', startIso, endIso);
  cache.series['FRED:DFF'] = _v2bFetchFredHistory_('DFF', startIso, endIso);
  cache.series['FRED:DGS2'] = _v2bFetchFredHistory_('DGS2', startIso, endIso);
  cache.series['FRED:DGS10'] = _v2bFetchFredHistory_('DGS10', startIso, endIso);
  cache.series['FRED:IRLTLT01JPM156N'] = _v2bFetchFredHistory_('IRLTLT01JPM156N', startIso, endIso);
  cache.series['EODHD:USDJPY.FOREX'] = _v2bFetchEodhdHistory_('USDJPY.FOREX', startIso, endIso);
  cache.series['EODHD:GSPC.INDX'] = _v2bFetchEodhdHistory_('GSPC.INDX', startIso, endIso);
  cache.series['EODHD:XAUUSD.FOREX'] = _v2bFetchEodhdHistory_('XAUUSD.FOREX', startIso, endIso);
  cache.series['FMP:CLUSD'] = _v2bFetchFmpHistory_('CLUSD', startIso, endIso);
  cache.series['FMP:USDJPY'] = _v2bFetchFmpHistory_('USDJPY', startIso, endIso);
  cache.series['FMP:DX-Y.NYB'] = _v2bFetchFmpHistory_('DX-Y.NYB', startIso, endIso);
  cache.series['FMP:GCUSD'] = _v2bFetchFmpHistory_('GCUSD', startIso, endIso);
  return cache;
}

function _v2bResolveSeriesEntry_(cache, provider, symbol) {
  var key = provider + ':' + symbol;
  return (cache && cache.series) ? (cache.series[key] || []) : [];
}

function _v2bSeriesSnapshot_(cache, provider, symbol, targetDate) {
  var rows = _v2bResolveSeriesEntry_(cache, provider, symbol);
  return _v2bObservationWindow_(rows, targetDate);
}

function _v2bLatestIntradayUsdJpy_(ev) {
  try {
    if (typeof getFxCandlesForWindowByProvider_ !== 'function') return null;
    var releaseTs = _v2bParseDate_(ev && ev.release_ts);
    if (!releaseTs) return null;
    var out = getFxCandlesForWindowByProvider_('eodhd', 'USD/JPY', releaseTs, 3 * 24 * 60, 0);
    if (!out || !out.candles || !out.candles.length) return null;
    var chosen = null;
    for (var i = 0; i < out.candles.length; i++) {
      var candle = out.candles[i];
      if (!candle || !candle.ts) continue;
      if (candle.ts.getTime() <= releaseTs.getTime()) chosen = candle;
      else break;
    }
    return chosen;
  } catch (e) {
    return null;
  }
}

function _buildMarketContextPack_(historyIndex, ev, options) {
  options = options || {};
  var releaseTs = _v2bReleaseDateTime_(ev);
  var releaseDate = _v2bReleaseDateOnly_(ev);
  var cache = options.seriesCache || _v2bBuildSeriesCache_(releaseDate, releaseDate);
  var useIntradayUsdJpy = options.useIntradayUsdJpy !== false;

  var fedfundsSnap = _v2bSeriesSnapshot_(cache, 'FRED', 'FEDFUNDS', releaseDate);
  var dffSnap = _v2bSeriesSnapshot_(cache, 'FRED', 'DFF', releaseDate);
  var dgs2Snap = _v2bSeriesSnapshot_(cache, 'FRED', 'DGS2', releaseDate);
  var dgs10Snap = _v2bSeriesSnapshot_(cache, 'FRED', 'DGS10', releaseDate);
  var jp10Snap = _v2bSeriesSnapshot_(cache, 'FRED', 'IRLTLT01JPM156N', releaseDate);

  var usdDaily = _v2bSeriesSnapshot_(cache, 'EODHD', 'USDJPY.FOREX', releaseDate);
  var dxySnap = _v2bSeriesSnapshot_(cache, 'FMP', 'DX-Y.NYB', releaseDate);
  var spxSnap = _v2bSeriesSnapshot_(cache, 'EODHD', 'GSPC.INDX', releaseDate);
  var goldSnap = _v2bSeriesSnapshot_(cache, 'EODHD', 'XAUUSD.FOREX', releaseDate);
  var wtiSnap = _v2bSeriesSnapshot_(cache, 'FMP', 'CLUSD', releaseDate);

  var usdCurrent = useIntradayUsdJpy ? _v2bLatestIntradayUsdJpy_(ev) : null;
  var usdLevel = usdCurrent && isFinite(usdCurrent.close) ? usdCurrent.close :
    (usdDaily.current && isFinite(usdDaily.current.value) ? usdDaily.current.value : null);
  var usdPrev = usdDaily.previous && isFinite(usdDaily.previous.value) ? usdDaily.previous.value : null;
  var usdPrev5 = usdDaily.previous5 && isFinite(usdDaily.previous5.value) ? usdDaily.previous5.value : null;

  var dxyLevel = dxySnap.current && isFinite(dxySnap.current.value) ? dxySnap.current.value : null;
  var dxyPrev = dxySnap.previous && isFinite(dxySnap.previous.value) ? dxySnap.previous.value : null;
  var dxyPrev5 = dxySnap.previous5 && isFinite(dxySnap.previous5.value) ? dxySnap.previous5.value : null;

  var spxLevel = spxSnap.current && isFinite(spxSnap.current.value) ? spxSnap.current.value : null;
  var spxPrev = spxSnap.previous && isFinite(spxSnap.previous.value) ? spxSnap.previous.value : null;
  var spxPrev5 = spxSnap.previous5 && isFinite(spxSnap.previous5.value) ? spxSnap.previous5.value : null;

  var goldLevel = goldSnap.current && isFinite(goldSnap.current.value) ? goldSnap.current.value : null;
  var goldPrev = goldSnap.previous && isFinite(goldSnap.previous.value) ? goldSnap.previous.value : null;
  var goldPrev5 = goldSnap.previous5 && isFinite(goldSnap.previous5.value) ? goldSnap.previous5.value : null;

  var wtiLevel = wtiSnap.current && isFinite(wtiSnap.current.value) ? wtiSnap.current.value : null;
  var wtiPrev = wtiSnap.previous && isFinite(wtiSnap.previous.value) ? wtiSnap.previous.value : null;
  var wtiPrev5 = wtiSnap.previous5 && isFinite(wtiSnap.previous5.value) ? wtiSnap.previous5.value : null;

  var fedfundsLevel = fedfundsSnap.current && isFinite(fedfundsSnap.current.value) ? fedfundsSnap.current.value : null;
  var dffLevel = dffSnap.current && isFinite(dffSnap.current.value) ? dffSnap.current.value : null;
  var us2y = dgs2Snap.current && isFinite(dgs2Snap.current.value) ? dgs2Snap.current.value : null;
  var us10y = dgs10Snap.current && isFinite(dgs10Snap.current.value) ? dgs10Snap.current.value : null;
  var jp10y = jp10Snap.current && isFinite(jp10Snap.current.value) ? jp10Snap.current.value : null;

  var marketFields = {
    fedfunds_level: fedfundsLevel,
    dff_level: dffLevel,
    us2y_yield: us2y,
    us10y_yield: us10y,
    us_2s10s_curve: (isFinite(us10y) && isFinite(us2y)) ? Number((us10y - us2y).toFixed(4)) : null,
    jp10y_yield: jp10y,
    us_jp_10y_spread: (isFinite(us10y) && isFinite(jp10y)) ? Number((us10y - jp10y).toFixed(4)) : null,
    fx_pair: ev && ev.fx_pair ? ev.fx_pair : (typeof CFG !== 'undefined' && CFG.DEFAULT_FX ? CFG.DEFAULT_FX : 'USDJPY'),
    usdjpy_level: usdLevel,
    usdjpy_24h_change_pips: (isFinite(usdLevel) && isFinite(usdPrev)) ? _v2bPipChange_(usdLevel, usdPrev) : null,
    usdjpy_5d_change_pips: (isFinite(usdLevel) && isFinite(usdPrev5)) ? _v2bPipChange_(usdLevel, usdPrev5) : null,
    dxy_level: dxyLevel,
    dxy_24h_change_pct: (isFinite(dxyLevel) && isFinite(dxyPrev)) ? _v2bPctChange_(dxyLevel, dxyPrev) : null,
    dxy_5d_change_pct: (isFinite(dxyLevel) && isFinite(dxyPrev5)) ? _v2bPctChange_(dxyLevel, dxyPrev5) : null,
    spx_level: spxLevel,
    spx_24h_change_pct: (isFinite(spxLevel) && isFinite(spxPrev)) ? _v2bPctChange_(spxLevel, spxPrev) : null,
    spx_5d_change_pct: (isFinite(spxLevel) && isFinite(spxPrev5)) ? _v2bPctChange_(spxLevel, spxPrev5) : null,
    gold_level: goldLevel,
    gold_24h_change_pct: (isFinite(goldLevel) && isFinite(goldPrev)) ? _v2bPctChange_(goldLevel, goldPrev) : null,
    gold_5d_change_pct: (isFinite(goldLevel) && isFinite(goldPrev5)) ? _v2bPctChange_(goldLevel, goldPrev5) : null,
    wti_level: wtiLevel,
    wti_24h_change_pct: (isFinite(wtiLevel) && isFinite(wtiPrev)) ? _v2bPctChange_(wtiLevel, wtiPrev) : null,
    wti_5d_change_pct: (isFinite(wtiLevel) && isFinite(wtiPrev5)) ? _v2bPctChange_(wtiLevel, wtiPrev5) : null
  };

  var missing = [];
  Object.keys(marketFields).forEach(function(key) {
    if (marketFields[key] === null || marketFields[key] === '' || marketFields[key] === undefined) missing.push(key);
  });
  var coreReady = !!(isFinite(us2y) && isFinite(us10y) && (isFinite(fedfundsLevel) || isFinite(dffLevel)) && isFinite(usdLevel));
  var marketContextAvailable = coreReady && (!!(isFinite(dxyLevel) || isFinite(spxLevel) || isFinite(goldLevel) || isFinite(wtiLevel)));
  var allRequiredPopulated = missing.length === 0;
  var marketContextQuality = marketContextAvailable
    ? (allRequiredPopulated ? 'full' : 'partial')
    : 'missing';

  var providerSources = [
    'FRED:FEDFUNDS',
    'FRED:DFF',
    'FRED:DGS2',
    'FRED:DGS10',
    'FRED:IRLTLT01JPM156N',
    useIntradayUsdJpy ? 'EODHD:USDJPY.FOREX intraday' : 'EODHD:USDJPY.FOREX daily',
    'EODHD:GSPC.INDX',
    'EODHD:XAUUSD.FOREX',
    'FMP:CLUSD',
    'FMP:DX-Y.NYB',
    'FMP:GCUSD',
    'FMP:CLUSD'
  ];

  return {
    market_context_pack_version: 'v2b_core_market_context',
    snapshot_ts: releaseTs,
    market_context_available: marketContextAvailable,
    market_context_quality: marketContextQuality,
    missing_market_context_fields: missing,
    lookback_windows: {
      current: 'latest observation <= release_ts',
      change_24h: 'previous available observation',
      change_5d: '5 observations back where available',
      usdjpy_snapshot: useIntradayUsdJpy ? 'latest intraday candle <= release_ts; fallback to daily close' : 'daily close <= release_ts'
    },
    fedfunds_level: fedfundsLevel,
    dff_level: dffLevel,
    us2y_yield: us2y,
    us10y_yield: us10y,
    us_2s10s_curve: marketFields.us_2s10s_curve,
    jp10y_yield: jp10y,
    us_jp_10y_spread: marketFields.us_jp_10y_spread,
    fx_pair: marketFields.fx_pair,
    usdjpy_level: usdLevel,
    usdjpy_24h_change_pips: marketFields.usdjpy_24h_change_pips,
    usdjpy_5d_change_pips: marketFields.usdjpy_5d_change_pips,
    dxy_level: dxyLevel,
    dxy_24h_change_pct: marketFields.dxy_24h_change_pct,
    dxy_5d_change_pct: marketFields.dxy_5d_change_pct,
    spx_level: spxLevel,
    spx_24h_change_pct: marketFields.spx_24h_change_pct,
    spx_5d_change_pct: marketFields.spx_5d_change_pct,
    gold_level: goldLevel,
    gold_24h_change_pct: marketFields.gold_24h_change_pct,
    gold_5d_change_pct: marketFields.gold_5d_change_pct,
    wti_level: wtiLevel,
    wti_24h_change_pct: marketFields.wti_24h_change_pct,
    wti_5d_change_pct: marketFields.wti_5d_change_pct,
    provider_sources_used: providerSources,
    source_symbol_map: {
      fedfunds_level: 'FRED:FEDFUNDS',
      dff_level: 'FRED:DFF',
      us2y_yield: 'FRED:DGS2',
      us10y_yield: 'FRED:DGS10',
      jp10y_yield: 'FRED:IRLTLT01JPM156N',
      usdjpy_level: useIntradayUsdJpy ? 'EODHD:USDJPY.FOREX intraday' : 'EODHD:USDJPY.FOREX daily',
      dxy_level: 'FMP:DX-Y.NYB',
      spx_level: 'EODHD:GSPC.INDX',
      gold_level: 'EODHD:XAUUSD.FOREX',
      wti_level: 'FMP:CLUSD'
    },
    market_context_notes: 'Deterministic pre-release snapshot: latest observation at or before release_ts; 24h and 5d changes use prior available observations; EODHD rows are explicitly sorted before snapshot selection; intraday USDJPY is used only when enabled and available.',
    market_context_available_flag_reason: marketContextAvailable ? 'core rate fields and USDJPY available' : 'core minimum missing'
  };
}

function debugFeaturePackForEvent_(eventId) {
  var audit = _readV2BCoreAuditPackByEventId_(eventId);
  if (!audit) {
    throw new Error('Feature_Pack_v2B_Core_Audit does not contain event_id=' + eventId + '. Rebuild the v2B-Core audit first.');
  }
  return JSON.parse(audit.raw_payload_preview);
}

function debugFeaturePackForEvent(eventId) {
  return debugFeaturePackForEvent_(eventId);
}

function _readV2BCoreAuditPackByEventId_(eventId) {
  var targetSheetName = 'Feature_Pack_v2B_Core_Audit';
  var resolved = null;
  try {
    resolved = (typeof getSheetForRead_ === 'function') ? getSheetForRead_(targetSheetName) : null;
  } catch (e) {}
  var sh = resolved && resolved.sheet ? resolved.sheet : null;
  if (!sh) return null;
  var headers = getHeaderNames(sh);
  if (!headers || !headers.length) return null;
  var idx = _headerIndexMap_(headers);
  var last = sh.getLastRow();
  if (last < 2) return null;
  var values = sh.getRange(2, 1, last - 1, headers.length).getValues();
  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    if (String(_cell(row, idx['event_id']) || '').trim() !== String(eventId || '').trim()) continue;
    return {
      generated_ts: String(_cell(row, idx['generated_ts']) || ''),
      raw_payload_preview: String(_cell(row, idx['raw_payload_preview']) || '')
    };
  }
  return null;
}

function buildFeaturePackV2BCoreAudit_(eventIds) {
  eventIds = _v2bNormalizeEventIdList_(eventIds);
  var eventSheet = getSheet('Event');
  var headers = getHeaderNames(eventSheet);
  var idx = {};
  headers.forEach(function(h, i){ idx[String(h || '').toLowerCase()] = i; });
  var values = _readDataRows_(eventSheet);
  var wanted = eventIds.length ? eventIds.reduce(function(m, id){ m[String(id)] = true; return m; }, {}) : null;
  var rows = [];
  var filtered = [];
  var minDate = '';
  var maxDate = '';
  var historyIndex = _buildHistoricalIndicatorIndex_(eventSheet);

  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    var eventId = String(_cell(row, idx['event_id']) || '').trim();
    var releaseTs = _toIsoOrNull_(_cell(row, idx['release_ts']));
    if (!eventId || !releaseTs) continue;
    if (wanted && !wanted[eventId]) continue;
    filtered.push(row);
    var d = _v2bDateOnly_(releaseTs);
    if (!minDate || d < minDate) minDate = d;
    if (!maxDate || d > maxDate) maxDate = d;
  }

  var cacheStart = _v2bOffsetDateIso_(minDate || '2024-05-01', -120);
  var cacheEnd = maxDate || Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var seriesCache = _v2bBuildSeriesCache_(cacheStart, cacheEnd);
  for (var j = 0; j < filtered.length; j++) {
    var row = filtered[j];
    var ev = {
      event_id: String(_cell(row, idx['event_id']) || '').trim(),
      batch_id: _cell(row, idx['batch_id']) || '',
      type: _cell(row, idx['type']) || '',
      country: _cell(row, idx['country']) || '',
      indicator_name: _cell(row, idx['indicator_name']) || '',
      genre: _cell(row, idx['genre']) || '',
      importance: (_cell(row, idx['importance']) || '').toString().toLowerCase(),
      release_ts: _toIsoOrNull_(_cell(row, idx['release_ts'])),
      source_cal: _cell(row, idx['source_cal']) || '',
      consensus_value: _numOrNull_(_cell(row, idx['consensus_value'])),
      prev_revision: _numOrNull_(_cell(row, idx['prev_revision'])),
      fx_pair: _cell(row, idx['fx_pair']) || ((typeof CFG !== 'undefined' && CFG.DEFAULT_FX) ? CFG.DEFAULT_FX : 'USDJPY')
    };
    var v2aPack = _buildHistoricalFeaturePackForEvent_(historyIndex, ev, { includeMarketContext: false });
    var marketContextPack = _buildMarketContextPack_(historyIndex, ev, {
      seriesCache: seriesCache,
      useIntradayUsdJpy: true
    });
    var fullPack = {
      feature_pack_version: 'v2b_core_market_context',
      historical_context: v2aPack.historical_context,
      surprise_pack: v2aPack.surprise_pack,
      revision_pack: v2aPack.revision_pack,
      family_pack: v2aPack.family_pack,
      signal_quality_pack: v2aPack.signal_quality_pack,
      market_context_pack: marketContextPack
    };
    rows.push({
      generated_ts: new Date().toISOString(),
      event_id: ev.event_id,
      indicator_name: ev.indicator_name,
      country: ev.country,
      release_ts: ev.release_ts,
      outcome_family: _featurePackFamilyKey_(ev),
      feature_pack_version: fullPack.feature_pack_version,
      has_market_context_pack: 'TRUE',
      market_context_available: marketContextPack.market_context_available ? 'TRUE' : 'FALSE',
      market_context_quality: marketContextPack.market_context_quality || '',
      missing_market_context_fields: (marketContextPack.missing_market_context_fields || []).join('|'),
      snapshot_ts: marketContextPack.snapshot_ts || '',
      provider_sources_used: (marketContextPack.provider_sources_used || []).join('|'),
      fedfunds_level: _v2bAuditNum_(marketContextPack.fedfunds_level),
      dff_level: _v2bAuditNum_(marketContextPack.dff_level),
      us2y_yield: _v2bAuditNum_(marketContextPack.us2y_yield),
      us10y_yield: _v2bAuditNum_(marketContextPack.us10y_yield),
      us_2s10s_curve: _v2bAuditNum_(marketContextPack.us_2s10s_curve),
      jp10y_yield: _v2bAuditNum_(marketContextPack.jp10y_yield),
      us_jp_10y_spread: _v2bAuditNum_(marketContextPack.us_jp_10y_spread),
      usdjpy_level: _v2bAuditNum_(marketContextPack.usdjpy_level),
      usdjpy_24h_change_pips: _v2bAuditNum_(marketContextPack.usdjpy_24h_change_pips),
      usdjpy_5d_change_pips: _v2bAuditNum_(marketContextPack.usdjpy_5d_change_pips),
      dxy_level: _v2bAuditNum_(marketContextPack.dxy_level),
      dxy_24h_change_pct: _v2bAuditNum_(marketContextPack.dxy_24h_change_pct),
      dxy_5d_change_pct: _v2bAuditNum_(marketContextPack.dxy_5d_change_pct),
      spx_level: _v2bAuditNum_(marketContextPack.spx_level),
      spx_24h_change_pct: _v2bAuditNum_(marketContextPack.spx_24h_change_pct),
      spx_5d_change_pct: _v2bAuditNum_(marketContextPack.spx_5d_change_pct),
      gold_level: _v2bAuditNum_(marketContextPack.gold_level),
      gold_24h_change_pct: _v2bAuditNum_(marketContextPack.gold_24h_change_pct),
      gold_5d_change_pct: _v2bAuditNum_(marketContextPack.gold_5d_change_pct),
      wti_level: _v2bAuditNum_(marketContextPack.wti_level),
      wti_24h_change_pct: _v2bAuditNum_(marketContextPack.wti_24h_change_pct),
      wti_5d_change_pct: _v2bAuditNum_(marketContextPack.wti_5d_change_pct),
      market_context_notes: marketContextPack.market_context_notes || '',
      raw_payload_preview: JSON.stringify(fullPack)
    });
  }

  var sheet = getDiagnosticsSheet_('Feature_Pack_v2B_Core_Audit', _v2bCoreAuditHeaders_()).sheet;
  var actualHeaders = _ensureHeadersAppendOnlyForSheet_(sheet, _v2bCoreAuditHeaders_());
  _rewriteSheetRowsPreservingHeaders_(sheet, actualHeaders, _remapRowsToHeaders_(_v2bCoreAuditHeaders_(), actualHeaders, _featurePackV2BCoreAuditRowsToArrays_(_v2bCoreAuditHeaders_(), rows)));
  return {
    status: 'ok',
    rows_written: rows.length,
    event_ids: eventIds
  };
}

function buildFeaturePackV2BCoreAudit(eventIds) {
  return buildFeaturePackV2BCoreAudit_(eventIds);
}

function _v2bAuditNum_(value) {
  return (value === null || value === undefined || value === '') ? '' : value;
}

function _v2bNormalizeEventIdList_(eventIds) {
  if (!eventIds) return [];
  if (Array.isArray(eventIds)) return eventIds.map(function(v){ return String(v || '').trim(); }).filter(Boolean);
  var text = String(eventIds || '').trim();
  if (!text) return [];
  return text.split(/[|,]/).map(function(v){ return String(v || '').trim(); }).filter(Boolean);
}

function _v2bCoreAuditHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'indicator_name',
    'country',
    'release_ts',
    'outcome_family',
    'feature_pack_version',
    'has_market_context_pack',
    'market_context_available',
    'market_context_quality',
    'missing_market_context_fields',
    'snapshot_ts',
    'provider_sources_used',
    'fedfunds_level',
    'dff_level',
    'us2y_yield',
    'us10y_yield',
    'us_2s10s_curve',
    'jp10y_yield',
    'us_jp_10y_spread',
    'usdjpy_level',
    'usdjpy_24h_change_pips',
    'usdjpy_5d_change_pips',
    'dxy_level',
    'dxy_24h_change_pct',
    'dxy_5d_change_pct',
    'spx_level',
    'spx_24h_change_pct',
    'spx_5d_change_pct',
    'gold_level',
    'gold_24h_change_pct',
    'gold_5d_change_pct',
    'wti_level',
    'wti_24h_change_pct',
    'wti_5d_change_pct',
    'market_context_notes',
    'raw_payload_preview'
  ];
}

function _featurePackV2BCoreAuditRowsToArrays_(headers, rows) {
  return (rows || []).map(function(row) {
    return headers.map(function(header) {
      return row && row.hasOwnProperty(header) ? row[header] : '';
    });
  });
}
