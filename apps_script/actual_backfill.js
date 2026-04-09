/**
 * One-off backfill: fetch actuals for all eligible events, ignoring the time window.
 * - Skips rows that already have released_value
 * - Skips batch rows and MANUAL/FILTER providers
 * - Uses SeriesMap to resolve provider/series, then fetches via FRED or FMP_CAL
 */
function fetchActualsIgnoreWindowOnce() {
  const log = getSheet(CFG.SHEET_LOG);
  appendLog(log, 'INFO', 'Actuals(ignore window): start', { mode: 'hybrid_delegate' });

  const tenYearsMinutes = 10 * 365 * 24 * 60;
  const cap = 20000;
  const result = runFetchActualsWindow_(tenYearsMinutes, 0, cap);

  appendLog(log, 'INFO', 'Actuals(ignore window): end', {
    mode: 'hybrid_delegate',
    result: result || {}
  });
  return result;
}

// ===== FRED helper (place at file scope) =====
function _fredFetchObservation(seriesId, refDateUtc, transform) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('FRED_API_KEY');
  if (!apiKey) throw new Error('Missing FRED_API_KEY');

  // Build URL WITHOUT a frequency override (let FRED use native freq)
  const base = 'https://api.stlouisfed.org/fred/series/observations';
  const params = {
    series_id: seriesId,
    api_key: apiKey,
    file_type: 'json',
    // narrow date window around release date (UTC)
    observation_start: _fmtDateISO(addDays(refDateUtc, -15)).slice(0,10),
    observation_end:   _fmtDateISO(addDays(refDateUtc, +15)).slice(0,10)
  };

  // Transform → FRED "units"
  // MoM % = 'pch'; raw level = 'lin'
  params.units = (transform === 'MOM_PCT') ? 'pch' : 'lin';

  const url = base + '?' + Object.keys(params)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k]))
    .join('&');

  const res  = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  const code = res.getResponseCode();
  if (code !== 200) {
    throw new Error('FRED HTTP ' + code + ': ' + String(res.getContentText()).slice(0, 300));
  }

  const json = JSON.parse(res.getContentText());
  const obs  = json.observations || [];
  if (!obs.length) throw new Error('FRED: no observations');

  // choose latest non-empty value on/after ref date (else closest prior)
  const refYmd = _fmtDateISO(refDateUtc).slice(0,10);
  let best = null;
  for (let i = obs.length - 1; i >= 0; i--) {
    const v = obs[i];
    if (!v || v.value == null || v.value === '.') continue;
    best = v;
    if (v.date && v.date.slice(0,10) >= refYmd) break;
  }
  if (!best) throw new Error('FRED: no valid value');



  return {
    value: Number(best.value),
    when: (best.date ? best.date.slice(0,19).replace('T',' ') : null)
  };
}

function _fredFetchObservation(seriesId, refDateUtc, transform) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('FRED_API_KEY');
  if (!apiKey) throw new Error('Missing FRED_API_KEY');

  const base = 'https://api.stlouisfed.org/fred/series/observations';
  const params = {
    series_id: seriesId,
    api_key: apiKey,
    file_type: 'json',
    observation_start: _fmtDateISO(addDays(refDateUtc, -15)).slice(0,10),
    observation_end:   _fmtDateISO(addDays(refDateUtc, +15)).slice(0,10),
    units: (transform === 'MOM_PCT') ? 'pch' : 'lin'
  };

  const url = base + '?' + Object.keys(params)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k]))
    .join('&');

  const res  = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  const code = res.getResponseCode();
  if (code !== 200) throw new Error('FRED HTTP ' + code + ': ' + String(res.getContentText()).slice(0, 300));

  const json = JSON.parse(res.getContentText());
  const obs  = json.observations || [];
  if (!obs.length) throw new Error('FRED: no observations');

  const refYmd = _fmtDateISO(refDateUtc).slice(0,10);
  let best = null;
  for (let i = obs.length - 1; i >= 0; i--) {
    const v = obs[i];
    if (!v || v.value == null || v.value === '.') continue;
    best = v;
    if (v.date && v.date.slice(0,10) >= refYmd) break;
  }
  if (!best) throw new Error('FRED: no valid value');

  return { value: Number(best.value), when: (best.date ? best.date.slice(0,19).replace('T',' ') : null) };
}

function _fmtDateISO(d) { return new Date(d).toISOString(); }
function addDays(d, n) { const t = new Date(d); t.setUTCDate(t.getUTCDate()+n); return t; }



function _autoMapIndicator(ev) {
  const name = String(ev.indicator_name || '').toLowerCase();

  // —— FRED fallbacks ——
  // PCE price index (MoM)
  if (/pce price index.*\(mom\)/i.test(ev.indicator_name || '')) {
    return { provider: 'FRED', series_id: 'PCEPI', freq: 'M', unit_type: 'PCT', transform: 'MOM_PCT' };
  }

  // —— FMP calendar fallbacks ——
  if (/chicago pmi/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CHICAGO_PMI', freq: 'M', unit_type: 'INDEX', transform: 'LEVEL' };
  }
  if (/^cb consumer confidence/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CONSUMER_CONFIDENCE', freq: 'M', unit_type: 'INDEX', transform: 'LEVEL' };
  }
  if (/api weekly crude oil stock/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CRUDE_STOCKS', freq: 'W', unit_type: 'MILLION_BBL', transform: 'LEVEL' };
  }
  if (/michigan.*1[- ]?year.*inflation expectations/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'MICHIGAN_1Y_INFL', freq: 'M', unit_type: 'PCT', transform: 'LEVEL' };
  }
  if (/michigan.*5[- ]?year.*inflation expectations/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'MICHIGAN_5Y_INFL', freq: 'M', unit_type: 'PCT', transform: 'LEVEL' };
  }
  if (/baker hughes.*oil rig count/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'BAKER_HUGHES_OIL_RIGS', freq: 'W', unit_type: 'COUNT', transform: 'LEVEL' };
  }
  if (/baker hughes.*total rig count/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'BAKER_HUGHES_TOTAL_RIGS', freq: 'W', unit_type: 'COUNT', transform: 'LEVEL' };
  }
  if (/cftc.*crude.*net positions/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CFTC_CRUDE_NET', freq: 'W', unit_type: 'CONTRACTS', transform: 'LEVEL' };
  }
  if (/cftc.*gold.*net positions/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CFTC_GOLD_NET', freq: 'W', unit_type: 'CONTRACTS', transform: 'LEVEL' };
  }
  if (/cftc.*nasdaq.*100.*net positions/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CFTC_NASDAQ100_NET', freq: 'W', unit_type: 'CONTRACTS', transform: 'LEVEL' };
  }
  if (/cftc.*s.?&.?p.*500.*net positions/i.test(ev.indicator_name || '')) {
    return { provider: 'FMP_CAL', series_id: 'CFTC_SP500_NET', freq: 'W', unit_type: 'CONTRACTS', transform: 'LEVEL' };
  }
  // Michigan Expectations (index)
  if (/michigan.*consumer.*expect/i.test(String(ev.indicator_name || ''))) {
    return { provider: 'FMP_CAL', series_id: 'MICHIGAN_EXPECTATIONS', freq: 'M', unit_type: 'INDEX', transform: 'LEVEL' };
  }
  // Michigan Sentiment (index)
  if (/michigan.*consumer.*sentiment/i.test(String(ev.indicator_name || ''))) {
    return { provider: 'FMP_CAL', series_id: 'MICHIGAN_SENTIMENT', freq: 'M', unit_type: 'INDEX', transform: 'LEVEL' };
  }

  return null; // no guess
}
