/**************  Tiingo + Twelve Data + Massive FX candle provider (USD/JPY)  **************/

var __FX_CANDLE_MEMO__ = (typeof __FX_CANDLE_MEMO__ !== 'undefined' && __FX_CANDLE_MEMO__) ? __FX_CANDLE_MEMO__ : {};

// Public entry for scoring: fetches a window of 1-min candles around an event time.
// pair: 'USD/JPY' (preferred) or 'USDJPY' will both work internally.
// releaseTsUtc: Date in UTC (minute-precision recommended)
// preMinutes / postMinutes: integers (e.g., 30, 120)
function getFxCandlesForWindow_(pair, releaseTsUtc, preMinutes, postMinutes) {
  return getFxCandlesForWindowByProvider_(null, pair, releaseTsUtc, preMinutes, postMinutes);
}

function getFxCandlesForWindowByProvider_(provider, pair, releaseTsUtc, preMinutes, postMinutes) {
  var t0 = new Date(releaseTsUtc.getTime());
  var pre = preMinutes || 30;
  var post = postMinutes || 120;
  var startMs = t0.getTime() - pre * 60 * 1000;
  var endMs = t0.getTime() + post * 60 * 1000;

  var wanted = _normalizeFxProviderName_(provider);
  var providerChain = [];

  function tryProvider_(name) {
    if (wanted && wanted !== name) return null;

    if (name === 'tiingo') {
      var tiingoOut = fetchTiingoFx_(pair, '1min', startMs, endMs);
      providerChain.push('tiingo');
      var tiingoCandles = filterCandlesByWindow_(tiingoOut.candles, startMs, endMs);
      if (tiingoCandles.length) {
        return { provider: 'tiingo', candles: tiingoCandles, meta: tiingoOut.meta || null, cache_hit: !!tiingoOut.cache_hit };
      }
      return null;
    }

    if (name === 'twelvedata') {
      var out = fetchTwelveDataFx_(pair, '1min', startMs, endMs);
      providerChain.push('twelvedata');
      var c = filterCandlesByWindow_(out.candles, startMs, endMs);
      if (c.length) {
        return { provider: 'twelvedata', candles: c, meta: out.meta || null, cache_hit: !!out.cache_hit };
      }
      return null;
    }

    if (name === 'massive') {
      var massiveOut = fetchMassiveFx_(pair, '1min', startMs, endMs);
      providerChain.push('massive');
      var massiveCandles = filterCandlesByWindow_(massiveOut.candles, startMs, endMs);
      if (massiveCandles.length) {
        return { provider: 'massive', candles: massiveCandles, meta: massiveOut.meta || null, cache_hit: !!massiveOut.cache_hit };
      }
      return null;
    }

    throw new Error('Unsupported FX provider: ' + String(name));
  }

  var order = wanted ? [wanted] : ['tiingo', 'twelvedata', 'massive'];
  for (var i = 0; i < order.length; i++) {
    try {
      var result = tryProvider_(order[i]);
      if (result) return result;
    } catch (e) {
      log_ && log_('marketdata', order[i] + '_error', { message: String(e) });
    }
  }

  return { provider: providerChain.join('>'), candles: [] };
}


// ---------- Tiingo (primary) ----------
function fetchTiingoFx_(pair, interval, startMs, endMs) {
  var key = _getTiingoApiKey_();
  if (!key) throw new Error('TIINGO_API_KEY missing');
  if (!startMs || !endMs) throw new Error('fetchTiingoFx_: startMs / endMs not provided');

  var ticker = normalizeSymbolForTiingo_(pair);
  var normalizedInterval = normalizeTiingoInterval_(interval || '1min');
  var cacheKey = _tiingoCacheKey_(ticker, normalizedInterval, startMs, endMs);

  var memoHit = _getMemoizedFxCandles_(cacheKey);
  if (memoHit) {
    return { candles: memoHit.candles || [], meta: memoHit.meta || null, cache_hit: true };
  }

  var cached = _getCachedTiingoCandles_(cacheKey);
  if (cached) {
    _setMemoizedFxCandles_(cacheKey, cached);
    return { candles: cached.candles || [], meta: cached.meta || null, cache_hit: true };
  }

  var startIso = Utilities.formatDate(new Date(startMs), 'UTC', "yyyy-MM-dd'T'HH:mm:ss'Z'");
  var endIso = Utilities.formatDate(new Date(endMs), 'UTC', "yyyy-MM-dd'T'HH:mm:ss'Z'");
  var url = 'https://api.tiingo.com/tiingo/fx/' + encodeURIComponent(ticker) + '/prices'
    + '?startDate=' + encodeURIComponent(startIso)
    + '&endDate=' + encodeURIComponent(endIso)
    + '&resampleFreq=' + encodeURIComponent(normalizedInterval)
    + '&token=' + encodeURIComponent(key);

  var res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });

  var code = res.getResponseCode();
  var body = res.getContentText();
  if (code !== 200) throw new Error('Tiingo HTTP ' + code + ' ' + body.slice(0, 256));

  var json = JSON.parse(body);
  if (!Array.isArray(json)) {
    if (json && json.detail) throw new Error('Tiingo error: ' + json.detail);
    if (json && json.message) throw new Error('Tiingo error: ' + json.message);
    throw new Error('Tiingo unexpected payload (not an array)');
  }

  var candles = json.map(function(row) {
    var midOpen = _midFromBidAsk_(row.openBidPrice, row.openAskPrice);
    var midHigh = _midFromBidAsk_(row.highBidPrice, row.highAskPrice);
    var midLow = _midFromBidAsk_(row.lowBidPrice, row.lowAskPrice);
    var midClose = _midFromBidAsk_(row.closeBidPrice, row.closeAskPrice);
    return {
      ts: parseUtc_(row.date || row.datetime || row.timestamp),
      open: _firstFiniteNumber_([row.open, row.openMid, midOpen]),
      high: _firstFiniteNumber_([row.high, row.highMid, midHigh]),
      low: _firstFiniteNumber_([row.low, row.lowMid, midLow]),
      close: _firstFiniteNumber_([row.close, row.closeMid, midClose])
    };
  }).filter(validCandle_);

  candles = _aggregateCandlesToMinute_(candles);

  var out = {
    candles: candles,
    meta: {
      ticker: ticker,
      interval: normalizedInterval,
      startDate: startIso,
      endDate: endIso
    },
    cache_hit: false
  };

  _setMemoizedFxCandles_(cacheKey, out);
  _cacheTiingoCandles_(cacheKey, out);
  log_ && log_('marketdata', 'tiingo_fetch_ok', {
    ticker: ticker,
    interval: normalizedInterval,
    startDate: startIso,
    endDate: endIso,
    candle_count: candles.length,
    meta: out.meta
  });
  return out;
}


// ---------- Twelve Data (fallback) ----------
function fetchTwelveDataFx_(pair, interval, startMs, endMs) {
  var key = getScriptProperty_ && getScriptProperty_('TWELVEDATA_API_KEY');
  if (!key) throw new Error('TWELVEDATA_API_KEY missing');
  if (!startMs || !endMs) throw new Error('fetchTwelveDataFx_: startMs / endMs not provided');

  var symbol = normalizeSymbolForTwelveData_(pair);
  var cacheKey = _twelveDataCacheKey_(symbol, interval, startMs, endMs);

  var memoHit = _getMemoizedFxCandles_(cacheKey);
  if (memoHit) {
    return { candles: memoHit.candles || [], meta: memoHit.meta || null, cache_hit: true };
  }

  var cached = _getCachedTwelveDataCandles_(cacheKey);
  if (cached) {
    _setMemoizedFxCandles_(cacheKey, cached);
    return { candles: cached.candles || [], meta: cached.meta || null, cache_hit: true };
  }

  var startIso = Utilities.formatDate(new Date(startMs), 'UTC', "yyyy-MM-dd'T'HH:mm:ss");
  var endIso = Utilities.formatDate(new Date(endMs), 'UTC', "yyyy-MM-dd'T'HH:mm:ss");

  var url = 'https://api.twelvedata.com/time_series'
    + '?symbol=' + encodeURIComponent(symbol)
    + '&interval=' + encodeURIComponent(interval || '1min')
    + '&start_date=' + encodeURIComponent(startIso)
    + '&end_date=' + encodeURIComponent(endIso)
    + '&timezone=UTC'
    + '&order=asc'
    + '&apikey=' + encodeURIComponent(key);

  var res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });

  var code = res.getResponseCode();
  var body = res.getContentText();
  if (code !== 200) throw new Error('TwelveData HTTP ' + code + ' ' + body.slice(0, 256));

  var json = JSON.parse(body);
  if (json.status && json.status !== 'ok') {
    throw new Error('TwelveData status: ' + json.status + ' message=' + (json.message || ''));
  }
  if (!json.values || !Array.isArray(json.values)) {
    throw new Error('TwelveData unexpected payload (no values)');
  }

  _validateTwelveDataMeta_(json.meta, symbol, interval);

  var values = json.values.slice();
  if (_isTwelveDataDescending_(values)) values.reverse();

  var candles = values.map(function(row) {
    return {
      ts: parseUtc_(row.datetime),
      open: num_(row.open),
      high: num_(row.high),
      low: num_(row.low),
      close: num_(row.close)
    };
  }).filter(validCandle_);

  var out = {
    candles: candles,
    meta: json.meta || null,
    cache_hit: false
  };

  _setMemoizedFxCandles_(cacheKey, out);
  _cacheTwelveDataCandles_(cacheKey, out);
  log_ && log_('marketdata', 'twelvedata_fetch_ok', {
    symbol: symbol,
    interval: interval || '1min',
    start_date: startIso,
    end_date: endIso,
    candle_count: candles.length,
    meta: json.meta || null
  });
  return out;
}


// ---------- Massive (comparison option) ----------
function fetchMassiveFx_(pair, interval, startMs, endMs) {
  var key = _getMassiveApiKey_();
  if (!key) throw new Error('MASSIVE_API_KEY missing');
  if (!startMs || !endMs) throw new Error('fetchMassiveFx_: startMs / endMs not provided');

  var ticker = normalizeSymbolForMassive_(pair);
  var normalized = normalizeMassiveInterval_(interval || '1min');
  var cacheKey = _massiveCacheKey_(ticker, normalized.interval, startMs, endMs);

  var memoHit = _getMemoizedFxCandles_(cacheKey);
  if (memoHit) {
    return { candles: memoHit.candles || [], meta: memoHit.meta || null, cache_hit: true };
  }

  var cached = _getCachedMassiveCandles_(cacheKey);
  if (cached) {
    _setMemoizedFxCandles_(cacheKey, cached);
    return { candles: cached.candles || [], meta: cached.meta || null, cache_hit: true };
  }

  var fromDate = Utilities.formatDate(new Date(startMs), 'UTC', 'yyyy-MM-dd');
  var toDate = Utilities.formatDate(new Date(endMs), 'UTC', 'yyyy-MM-dd');
  var url = 'https://api.massive.com/v2/aggs/ticker/' + encodeURIComponent(ticker)
    + '/range/' + encodeURIComponent(String(normalized.multiplier))
    + '/' + encodeURIComponent(normalized.timespan)
    + '/' + encodeURIComponent(fromDate)
    + '/' + encodeURIComponent(toDate)
    + '?sort=asc'
    + '&limit=50000'
    + '&apiKey=' + encodeURIComponent(key);

  var res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });

  var code = res.getResponseCode();
  var body = res.getContentText();
  if (code !== 200) throw new Error('Massive HTTP ' + code + ' ' + body.slice(0, 256));

  var json = JSON.parse(body);
  if (json && json.status && String(json.status).toUpperCase() === 'ERROR') {
    throw new Error('Massive error: ' + (json.error || json.message || body.slice(0, 256)));
  }

  var rows = (json && json.results && Array.isArray(json.results)) ? json.results : [];
  var candles = rows.map(function(row) {
    return {
      ts: _parseEpochMsToDate_(row.t),
      open: num_(row.o),
      high: num_(row.h),
      low: num_(row.l),
      close: num_(row.c)
    };
  }).filter(validCandle_);

  var out = {
    candles: candles,
    meta: {
      ticker: ticker,
      interval: normalized.interval,
      from: fromDate,
      to: toDate,
      queryCount: json && json.queryCount != null ? json.queryCount : '',
      resultsCount: json && json.resultsCount != null ? json.resultsCount : rows.length
    },
    cache_hit: false
  };

  _setMemoizedFxCandles_(cacheKey, out);
  _cacheMassiveCandles_(cacheKey, out);
  log_ && log_('marketdata', 'massive_fetch_ok', {
    ticker: ticker,
    interval: normalized.interval,
    from: fromDate,
    to: toDate,
    candle_count: candles.length,
    meta: out.meta
  });
  return out;
}


function _getTiingoApiKey_() {
  if (typeof CFG !== 'undefined' && CFG && CFG.TIINGO_API_KEY) return CFG.TIINGO_API_KEY;
  if (typeof getScriptProperty_ === 'function') return getScriptProperty_('TIINGO_API_KEY');
  if (typeof _getScriptProp_ === 'function') return _getScriptProp_('TIINGO_API_KEY');
  return '';
}

function _getMassiveApiKey_() {
  if (typeof CFG !== 'undefined' && CFG && CFG.MASSIVE_API_KEY) return CFG.MASSIVE_API_KEY;
  if (typeof getScriptProperty_ === 'function') return getScriptProperty_('MASSIVE_API_KEY');
  if (typeof _getScriptProp_ === 'function') return _getScriptProp_('MASSIVE_API_KEY');
  return '';
}

function normalizeSymbolForTiingo_(pair) {
  var p = String(pair || '').trim().toUpperCase().replace('/', '');
  if (p.length === 6) return p;
  return 'USDJPY';
}

function normalizeTiingoInterval_(interval) {
  var raw = String(interval || '1min').trim().toLowerCase();
  if (['1min', '5min', '10min', '15min', '30min', '1hour'].indexOf(raw) >= 0) return raw;
  if (raw === '60min') return '1hour';
  return '1min';
}

function normalizeSymbolForTwelveData_(pair) {
  var p = String(pair || '').trim().toUpperCase();
  if (p.indexOf('/') >= 0) return p;
  if (p.length === 6) return p.slice(0, 3) + '/' + p.slice(3);
  return 'USD/JPY';
}

function normalizeSymbolForMassive_(pair) {
  var p = String(pair || '').trim().toUpperCase().replace('/', '');
  if (p.length === 6) return 'C:' + p;
  return 'C:USDJPY';
}

function normalizeMassiveInterval_(interval) {
  var raw = String(interval || '1min').trim().toLowerCase();
  if (raw === '1min') return { interval: '1min', multiplier: 1, timespan: 'minute' };
  if (raw === '5min') return { interval: '5min', multiplier: 5, timespan: 'minute' };
  if (raw === '15min') return { interval: '15min', multiplier: 15, timespan: 'minute' };
  if (raw === '30min') return { interval: '30min', multiplier: 30, timespan: 'minute' };
  if (raw === '1hour' || raw === '60min') return { interval: '1hour', multiplier: 1, timespan: 'hour' };
  return { interval: '1min', multiplier: 1, timespan: 'minute' };
}

function _normalizeFxProviderName_(provider) {
  var raw = String(provider || '').trim().toLowerCase();
  if (!raw) return '';
  if (raw === 'twelve' || raw === '12data') return 'twelvedata';
  if (raw === 'polygon') return 'massive';
  if (raw === 'tiingo') return 'tiingo';
  if (raw === 'twelvedata') return 'twelvedata';
  if (raw === 'massive') return 'massive';
  return raw;
}


// ---------- Shared helpers ----------
function filterCandlesByWindow_(candles, startMs, endMs) {
  if (!candles || !candles.length) return [];
  return candles.filter(function(c) {
    var t = c.ts && c.ts.getTime ? c.ts.getTime() : NaN;
    return isFinite(t) && t >= startMs && t <= endMs;
  });
}

function parseUtc_(s) {
  if (!s) return null;
  var raw = String(s).trim();
  if (/Z$/.test(raw) || /[+-]\d{2}:\d{2}$/.test(raw) || /[+-]\d{4}$/.test(raw)) {
    var zoned = new Date(raw);
    if (!isNaN(zoned.getTime())) return zoned;
  }
  var d = new Date(raw.replace(' ', 'T') + 'Z');
  return isNaN(d.getTime()) ? new Date(raw) : d;
}

function num_(v) {
  if (v === null || v === '' || v === undefined) return null;
  var n = (typeof v === 'number') ? v : Number(String(v).replace(/,/g, ''));
  return isFinite(n) ? n : null;
}

function validCandle_(c) {
  return c && c.ts instanceof Date && isFinite(c.ts.getTime()) &&
    isFinite(c.open) && isFinite(c.high) && isFinite(c.low) && isFinite(c.close);
}

function _getMemoizedFxCandles_(cacheKey) {
  if (!cacheKey || !__FX_CANDLE_MEMO__) return null;
  return __FX_CANDLE_MEMO__[cacheKey] || null;
}

function _setMemoizedFxCandles_(cacheKey, payload) {
  if (!cacheKey || !payload) return;
  __FX_CANDLE_MEMO__[cacheKey] = payload;
}

function _tiingoCacheKey_(ticker, interval, startMs, endMs) {
  return ['tiingo', ticker, interval || '1min', String(startMs || ''), String(endMs || '')].join(':');
}

function _twelveDataCacheKey_(symbol, interval, startMs, endMs) {
  return ['twelvedata', symbol, interval || '1min', String(startMs || ''), String(endMs || '')].join(':');
}

function _massiveCacheKey_(ticker, interval, startMs, endMs) {
  return ['massive', ticker, interval || '1min', String(startMs || ''), String(endMs || '')].join(':');
}

function _getCachedTiingoCandles_(cacheKey) {
  return _getCachedCandlesGeneric_(cacheKey);
}

function _getCachedTwelveDataCandles_(cacheKey) {
  return _getCachedCandlesGeneric_(cacheKey);
}

function _getCachedMassiveCandles_(cacheKey) {
  return _getCachedCandlesGeneric_(cacheKey);
}

function _getCachedCandlesGeneric_(cacheKey) {
  var cache = null;
  try { cache = CacheService.getScriptCache(); } catch (e) {}
  if (!cache) return null;

  var raw = cache.get(cacheKey);
  if (!raw) return null;

  try {
    var parsed = JSON.parse(raw);
    if (!parsed || !parsed.candles || !Array.isArray(parsed.candles)) return null;
    parsed.candles = parsed.candles.map(function(c) {
      return {
        ts: parseUtc_(c.ts),
        open: num_(c.open),
        high: num_(c.high),
        low: num_(c.low),
        close: num_(c.close)
      };
    }).filter(validCandle_);
    return parsed;
  } catch (e2) {
    return null;
  }
}

function _cacheTiingoCandles_(cacheKey, payload) {
  _cacheCandlesGeneric_(cacheKey, payload);
}

function _cacheMassiveCandles_(cacheKey, payload) {
  _cacheCandlesGeneric_(cacheKey, payload);
}

function _midFromBidAsk_(bid, ask) {
  var b = num_(bid);
  var a = num_(ask);
  if (!isFinite(b) || !isFinite(a)) return null;
  return Math.round((((b + a) / 2) * 1000000)) / 1000000;
}

function _firstFiniteNumber_(values) {
  if (!values || !values.length) return null;
  for (var i = 0; i < values.length; i++) {
    var n = num_(values[i]);
    if (isFinite(n)) return n;
  }
  return null;
}

function _aggregateCandlesToMinute_(candles) {
  if (!candles || !candles.length) return [];

  var sorted = candles.slice().sort(function(a, b) {
    return a.ts.getTime() - b.ts.getTime();
  });

  var out = [];
  var current = null;
  var currentKey = '';

  for (var i = 0; i < sorted.length; i++) {
    var c = sorted[i];
    if (!validCandle_(c)) continue;

    var minuteMs = Math.floor(c.ts.getTime() / 60000) * 60000;
    var minuteTs = new Date(minuteMs);
    var key = minuteTs.toISOString();

    if (key !== currentKey) {
      if (current) out.push(current);
      currentKey = key;
      current = {
        ts: minuteTs,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      };
      continue;
    }

    if (isFinite(c.high) && c.high > current.high) current.high = c.high;
    if (isFinite(c.low) && c.low < current.low) current.low = c.low;
    if (isFinite(c.close)) current.close = c.close;
  }

  if (current) out.push(current);
  return out.filter(validCandle_);
}

function _cacheTwelveDataCandles_(cacheKey, payload) {
  _cacheCandlesGeneric_(cacheKey, payload);
}

function _parseEpochMsToDate_(value) {
  var n = num_(value);
  if (!isFinite(n)) return null;
  if (n < 1e11) n = n * 1000;
  var dt = new Date(n);
  return isNaN(dt.getTime()) ? null : dt;
}

function _cacheCandlesGeneric_(cacheKey, payload) {
  var cache = null;
  try { cache = CacheService.getScriptCache(); } catch (e) {}
  if (!cache || !payload || !payload.candles) return;

  try {
    var serializable = {
      meta: payload.meta || null,
      candles: payload.candles.map(function(c) {
        return {
          ts: c.ts && c.ts.toISOString ? c.ts.toISOString() : '',
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close
        };
      })
    };
    cache.put(cacheKey, JSON.stringify(serializable), 300);
  } catch (e2) {}
}

function _validateTwelveDataMeta_(meta, expectedSymbol, expectedInterval) {
  if (!meta) return;

  var symbol = String(meta.symbol || '').trim().toUpperCase();
  var expected = String(expectedSymbol || '').trim().toUpperCase();
  if (symbol && expected && symbol !== expected) {
    throw new Error('TwelveData meta symbol mismatch. expected=' + expected + ' actual=' + symbol);
  }

  var interval = String(meta.interval || '').trim().toLowerCase();
  var wanted = String(expectedInterval || '').trim().toLowerCase();
  if (interval && wanted && interval !== wanted) {
    throw new Error('TwelveData meta interval mismatch. expected=' + wanted + ' actual=' + interval);
  }

  var timezone = String(meta.timezone || '').trim().toUpperCase();
  if (timezone && timezone !== 'UTC') {
    throw new Error('TwelveData meta timezone mismatch. expected=UTC actual=' + timezone);
  }
}

function _isTwelveDataDescending_(values) {
  if (!values || values.length < 2) return false;
  var first = parseUtc_(values[0] && values[0].datetime);
  var second = parseUtc_(values[1] && values[1].datetime);
  if (!first || !second || isNaN(first.getTime()) || isNaN(second.getTime())) return false;
  return first.getTime() > second.getTime();
}
