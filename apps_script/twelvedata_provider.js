/**************  Twelve Data + FMP FX candle provider (USD/JPY)  **************/

// Public entry for scoring: fetches a window of 1-min candles around an event time.
// pair: 'USD/JPY' (preferred) or 'USDJPY' will both work internally.
// releaseTsUtc: Date in UTC (minute-precision recommended)
// preMinutes / postMinutes: integers (e.g., 30, 120)
/**************  Twelve Data + FMP FX candle provider (USD/JPY)  **************/

function getFxCandlesForWindow_(pair, releaseTsUtc, preMinutes, postMinutes) {
  // Defensive copy and window boundaries
  var t0 = new Date(releaseTsUtc.getTime());
  var pre  = (preMinutes  || 30);
  var post = (postMinutes || 120);

  var startMs = t0.getTime() - pre  * 60 * 1000;
  var endMs   = t0.getTime() + post * 60 * 1000;

  var providerChain = [];

  // --- Twelve Data primary ---
  try {
    var c = fetchTwelveDataFx_(pair, '1min', startMs, endMs);
    providerChain.push('twelvedata');
    c = filterCandlesByWindow_(c, startMs, endMs);
    if (c.length) {
      return { provider: 'twelvedata', candles: c };
    }
  } catch (e) {
    log_ && log_('marketdata', 'twelvedata_error', { message: String(e) });
  }
  // FMP fallback removed — Twelve Data is primary & only source.
  // (We keep providerChain but no fallback.)
  return { provider: providerChain.join('>'), candles: [] };
}


// ---------- Twelve Data (primary) ----------
function fetchTwelveDataFx_(pair, interval, startMs, endMs) {
  var key = getScriptProperty_ && getScriptProperty_('TWELVEDATA_API_KEY');
  if (!key) throw new Error('TWELVEDATA_API_KEY missing');

  var symbol = normalizeSymbolForTwelveData_(pair);

  // Build start / end datetimes in UTC for Twelve Data
  if (!startMs || !endMs) {
    throw new Error('fetchTwelveDataFx_: startMs / endMs not provided');
  }
  var startIso = Utilities.formatDate(new Date(startMs), 'UTC', "yyyy-MM-dd'T'HH:mm:ss");
  var endIso   = Utilities.formatDate(new Date(endMs),   'UTC', "yyyy-MM-dd'T'HH:mm:ss");

  var url = 'https://api.twelvedata.com/time_series'
    + '?symbol=' + encodeURIComponent(symbol)
    + '&interval=' + encodeURIComponent(interval || '1min')
    + '&start_date=' + encodeURIComponent(startIso)
    + '&end_date=' + encodeURIComponent(endIso)
    + '&timezone=UTC'
    + '&apikey=' + encodeURIComponent(key);

  var res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });

  var code = res.getResponseCode();
  var body = res.getContentText();

  if (code !== 200) {
    throw new Error('TwelveData HTTP ' + code + ' ' + body.slice(0, 256));
  }

  var json = JSON.parse(body);

  if (json.status && json.status !== 'ok') {
    // Typical error carriers: { status: "error", message: "..."} or rate limit notes
    throw new Error('TwelveData status: ' + json.status + ' message=' + (json.message || ''));
  }
  if (!json.values || !Array.isArray(json.values)) {
    throw new Error('TwelveData unexpected payload (no values)');
  }

  // API returns newest first → reverse to chronological (oldest → newest)
  var values = json.values.slice().reverse();

  return values.map(function (row) {
    var ts = parseUtc_(row.datetime); // "YYYY-MM-DD HH:mm:ss"
    return {
      ts: ts,
      open: num_(row.open),
      high: num_(row.high),
      low:  num_(row.low),
      close: num_(row.close)
    };
  }).filter(validCandle_);
}


function normalizeSymbolForTwelveData_(pair) {
  const p = String(pair||'').trim().toUpperCase();
  if (p.includes('/')) return p;
  if (p.length === 6) return p.slice(0,3)+'/'+p.slice(3);
  return 'USD/JPY';
}


// ---------- Shared helpers ----------
function filterCandlesByWindow_(candles, startMs, endMs) {
  if (!candles || !candles.length) return [];
  return candles.filter(c => {
    const t = c.ts && c.ts.getTime ? c.ts.getTime() : NaN;
    return isFinite(t) && t >= startMs && t <= endMs;
  });
}
function parseUtc_(s) {
  if (!s) return null;
  const d = new Date((String(s).replace(' ','T')) + 'Z');
  return isNaN(d.getTime()) ? new Date(String(s)) : d;
}
function num_(v) {
  if (v===null || v==='' || v===undefined) return null;
  const n = (typeof v==='number') ? v : Number(String(v).replace(/,/g,''));
  return isFinite(n) ? n : null;
}
function validCandle_(c) {
  return c && c.ts instanceof Date && isFinite(c.ts.getTime()) &&
         isFinite(c.open) && isFinite(c.high) && isFinite(c.low) && isFinite(c.close);
}

