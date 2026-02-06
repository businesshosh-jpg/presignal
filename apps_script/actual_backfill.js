/**
 * One-off backfill: fetch actuals for all eligible events, ignoring the time window.
 * - Skips rows that already have released_value
 * - Skips batch rows and MANUAL/FILTER providers
 * - Uses SeriesMap to resolve provider/series, then fetches via FRED or FMP_CAL
 */
function fetchActualsIgnoreWindowOnce() {
  const log = getSheet(CFG.SHEET_LOG);
  appendLog(log, 'INFO', 'Actuals(ignore window): start', {});

  const eventSh   = getEventSheet();
  const evHeaders = getHeaderNames(eventSh).map(h => String(h).trim());
  const H         = Object.fromEntries(evHeaders.map((h,i)=>[h,i]));
  const last      = eventSh.getLastRow();

  if (last < 2) {
    appendLog(log, 'INFO', 'Actuals(ignore window): Event empty', {});
    return;
  }

  const width = eventSh.getLastColumn();
  const rows  = eventSh.getRange(2,1,last-1,width).getValues();

  const mapRows = loadSeriesMap(); // your existing helper
  let updated = 0, skipped = 0, errors = 0;

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];

    // Basic fields
    const event_id       = r[H['event_id']];
    const indicator_name = r[H['indicator_name']];
    const country        = r[H['country']];
    const release_ts     = r[H['release_ts']];
    const release_status = (r[H['release_status']] || '').toString().toLowerCase();
    const released_val   = r[H['released_value']];

    // Row-level guards
    if (!event_id || !indicator_name || !country || !release_ts) { skipped++; continue; }
    if (released_val !== '' && released_val !== null)            { skipped++; continue; }
    if (release_status === 'error')                               { skipped++; continue; }

    const relDate = _safeDate(release_ts);
    if (!relDate) { skipped++; continue; }

    // Resolve SeriesMap
    const evObj = { event_id, indicator_name, country, release_ts };

    // use your existing SeriesMap loader
    let m = resolveSeriesForEvent(evObj, mapRows);  // instead of resolveSeriesMapMatch

    if (!m) {
      // Try a small auto-map so old FRED paths & common FMP items still work
      m = _autoMapIndicator(evObj);
      if (!m) {
        appendLog(log, 'INFO', 'Actuals(ignore window): No SeriesMap match', { event_id, indicator_name, country });
        continue;
      } 
    }



    // Skip unsupported provider types explicitly here (batch handled below too)
    const provider = String(m.provider || '').toUpperCase();
    if (provider === 'MANUAL' || provider === 'FILTER' || String(r[H['type']] || '').toLowerCase() === 'batch') {
      _writeEventStatus(eventSh, H, i + 2, { release_status: 'pending', notes: 'Manual/Filter/Batch: skipping' });
      appendLog(log, 'INFO', 'Actuals(ignore window): skipped non-auto provider/type', { event_id, provider });
      skipped++;
      continue;
    }

    // Compute reference period and fetch
    const ref = getRefPeriodForEvent(evObj); // your existing helper

    // ------------------ Provider routing ------------------
    try {
      let value = null;
      let info  = {};

      appendLog(log, 'INFO', 'Fetch route', {
        event_id,
        indicator: indicator_name,
        country,
        provider,
        series: m.series_id
      });

      if (provider === 'FRED') {
        // ---- FRED route (no frequency override) ----
        const fred = _fredFetchObservation(m.series_id, ref.refDate, m.transform);
        value = roundByUnit(fred.value, m.unit_type, m.transform);
        info  = { when: fred.when };

        // Commit (common checks below)
        if (value == null || !isFinite(value)) {
          _writeEventStatus(eventSh, H, i + 2, { release_status: 'pending', notes: `No obs for ref ${ref.refKey}` });
          appendLog(log, 'INFO', 'Actuals(ignore window): observation not yet available', { event_id, ref: ref.refKey });
          continue;
        }

        // Light sanity check
        if (m.transform === 'YOY_PCT' && (value < -10 || value > 50)) {
          _writeEventStatus(eventSh, H, i + 2, { release_status: 'error', notes: `Value out of range: ${value}` });
          appendLog(log, 'ERROR', 'Actuals(ignore window): sanity fail', { event_id, value });
          errors++;
          continue;
        }

        _writeEventActuals(eventSh, H, i + 2, {
          released_value: value,
          released_ts: new Date().toISOString(),
          source_provider: m.provider,
          source_series_id: m.series_id,
          transform: m.transform,
          release_status: 'fetched'
        });

        appendLog(log, 'INFO', 'Actuals(ignore window): fetched (FRED)', {
          event_id, series_id: m.series_id, provider: m.provider, ref: ref.refKey, value, ...info
        });
        updated++;

        if (ACTUALS_CFG.COPY_ACTUALS_TO_PREDICTIONS) {
          _copyActualsToPredictions(event_id, value);
        }
        continue; // next row

      } else if (provider === 'FMP_CAL') {
        // ---- FMP calendar route ----
        const base = new Date(Date.UTC(relDate.getUTCFullYear(), relDate.getUTCMonth(), relDate.getUTCDate()));
        const from = new Date(base.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
        const to   = new Date(base.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);


        try {
          const cal   = _fmpFetchCalendarWindow(from, to);   // your FMP helper
          const calUS = cal.filter(x => x.country === 'US'); // keep US only

          const match = _fmpPickMatchForEvent(
            { country, indicator_name, release_ts },
            m.series_id,
            calUS
          );

          if (!match) {
            _writeEventStatus(eventSh, H, i + 2, { release_status: 'pending', notes: `FMP: no US match ${from}..${to}` });
            appendLog(log, 'INFO', 'Actuals(ignore window/FMP): no match', { event_id, series_key: m.series_id, from, to });
            continue;
          }

          if (match.actual == null || !isFinite(match.actual)) {
            _writeEventStatus(eventSh, H, i + 2, { release_status: 'pending', notes: 'FMP: actual not yet' });
            appendLog(log, 'INFO', 'Actuals(ignore window/FMP): waiting actual', { event_id, event: match.event, when: match.date });
            continue;
          }

          _writeEventActuals(eventSh, H, i + 2, {
            released_value: match.actual,
            released_ts: new Date(match.date || new Date()).toISOString(),
            source_provider: 'FMP_CAL',
            source_series_id: m.series_id, // your semantic key, e.g., CRUDE_STOCKS
            transform: m.transform || 'LEVEL',
            release_status: 'fetched'
          });

          // Optional: mirror prev/forecast into Event
          // _writeEventPrevForecast(eventSh, H, i + 2, match.previous, match.forecast);

          appendLog(log, 'INFO', 'Actuals(ignore window): fetched (FMP)', {
            event_id, event: match.event, value: match.actual, when: match.date
          });
          updated++;
          continue; // next row

        } catch (e) {
          const em = String(e);
          _writeEventStatus(eventSh, H, i + 2, { release_status: 'error', notes: em.slice(0, 200) });
          appendLog(log, 'ERROR', 'Actuals(ignore window/FMP): failed', { event_id, err: em.slice(0, 500) });
          errors++;
          continue;
        }


      } else {
        // Unknown provider (shouldn't happen if SeriesMap is clean)
        _writeEventStatus(eventSh, H, i + 2, { release_status: 'error', notes: `Provider ${m.provider} not implemented` });
        appendLog(log, 'WARN', 'Actuals(ignore window): provider not implemented', { event_id, provider: m.provider });
        errors++;
        continue;
      }
    } catch (e) {
      const em = String(e);
      _writeEventStatus(eventSh, H, i + 2, { release_status: 'error', notes: em.slice(0, 200) });
      appendLog(log, 'ERROR', 'Actuals(ignore window/FMP): failed', { event_id, err: em.slice(0, 500) });
      errors++;
      continue;
    }

  } // end for

  appendLog(log, 'INFO', 'Actuals(ignore window): end', { updated, skipped, errors });
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

