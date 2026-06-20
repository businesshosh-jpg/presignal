function runMinimalDataAvailabilityAudit_() {
  var replayCutoff = '2024-05-01';
  var rows = [];

  var fredFields = ['FEDFUNDS', 'DFF', 'DGS2', 'DGS10'];
  for (var i = 0; i < fredFields.length; i++) {
    rows.push(_auditFredSeries_(fredFields[i], replayCutoff));
  }

  var eodFields = [
    { field: 'USDJPY', candidates: ['USDJPY.FOREX'] },
    { field: 'DXY', candidates: [] },
    { field: 'VIX', candidates: [] },
    { field: 'SPX', candidates: ['GSPC.INDX'] },
    { field: 'NDX', candidates: [] },
    { field: 'GOLD', candidates: ['GOLD'] },
    { field: 'WTI', candidates: ['WTI'] },
    { field: 'JP10Y', candidates: [] },
    { field: 'JP2Y', candidates: [] }
  ];
  for (var j = 0; j < eodFields.length; j++) {
    rows.push(_auditEodhdSeries_(eodFields[j], replayCutoff));
  }

  var fmpFields = [
    { field: 'Treasury rates', candidates: ['US10Y', 'US02Y'] },
    { field: 'USDJPY', candidates: ['USDJPY'] },
    { field: 'DXY', candidates: ['DX-Y.NYB'] },
    { field: 'VIX', candidates: [] },
    { field: 'S&P500', candidates: [] },
    { field: 'Nasdaq', candidates: [] },
    { field: 'Gold', candidates: ['GCUSD'] },
    { field: 'Oil', candidates: ['CLUSD'] }
  ];
  for (var k = 0; k < fmpFields.length; k++) {
    rows.push(_auditFmpSeries_(fmpFields[k], replayCutoff));
  }

  return {
    status: 'ok',
    replay_cutoff_date: replayCutoff,
    rows: rows
  };
}

function runMinimalDataAvailabilityAudit() {
  return runMinimalDataAvailabilityAudit_();
}

function _auditFredSeries_(seriesId, replayCutoff) {
  var key = (PropertiesService.getScriptProperties().getProperty('FRED_API_KEY') || '').trim();
  if (!key) return _auditFailRow_(seriesId, 'FRED', seriesId, 'missing_api_key');
  try {
    var earliest = _fredBoundaryObservation_(seriesId, key, 'asc');
    var latest = _fredBoundaryObservation_(seriesId, key, 'desc');
    if (!earliest || !latest) return _auditFailRow_(seriesId, 'FRED', seriesId, 'no_observations');
    return _auditOkRow_(seriesId, 'FRED', seriesId, earliest.date, latest.date, replayCutoff);
  } catch (e) {
    return _auditFailRow_(seriesId, 'FRED', seriesId, String(e));
  }
}

function _fredBoundaryObservation_(seriesId, key, sortOrder) {
  var url = 'https://api.stlouisfed.org/fred/series/observations'
    + '?series_id=' + encodeURIComponent(seriesId)
    + '&api_key=' + encodeURIComponent(key)
    + '&file_type=json'
    + '&sort_order=' + encodeURIComponent(sortOrder)
    + '&limit=1';
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '{}');
  var obs = json && json.observations && json.observations[0];
  if (!obs || !obs.date) return null;
  return { date: String(obs.date).slice(0, 10) };
}

function _auditEodhdSeries_(item, replayCutoff) {
  var key = _getEodhdApiKey_();
  if (!key) return _auditFailRow_(item.field, 'EODHD', '', 'missing_api_key');
  var bestErr = 'unresolved_symbol';
  for (var i = 0; i < item.candidates.length; i++) {
    var symbol = item.candidates[i];
    try {
      var latest = _eodhdBoundaryDate_(symbol, key, 'desc');
      if (!latest) {
        bestErr = 'no_recent_data';
        continue;
      }
      var earliest = _eodhdFindEarliestDate_(symbol, key);
      return _auditOkRow_(item.field, 'EODHD', symbol, earliest, latest, replayCutoff);
    } catch (e) {
      bestErr = String(e);
    }
  }
  return _auditFailRow_(item.field, 'EODHD', item.candidates[0] || '', bestErr);
}

function _eodhdBoundaryDate_(symbol, key, order) {
  var range = order === 'desc'
    ? { from: '2024-01-01', to: Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd') }
    : { from: '1900-01-01', to: '1901-12-31' };
  var rows = _eodhdFetchEodWindow_(symbol, key, range.from, range.to, order);
  if (!rows.length && order === 'asc') return null;
  if (!rows.length && order === 'desc') {
    rows = _eodhdFetchEodWindow_(symbol, key, '2010-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), 'desc');
  }
  if (!rows.length) return null;
  var sorted = _eodhdSortRowsByDate_(rows, 'asc');
  var row = order === 'desc' ? sorted[sorted.length - 1] : sorted[0];
  return String(row.date || row.datetime || '').slice(0, 10);
}

function _eodhdSortRowsByDate_(rows, direction) {
  var copy = (rows || []).slice();
  copy.sort(function(a, b) {
    var da = String((a && (a.date || a.datetime || a.timestamp)) || '').slice(0, 10);
    var db = String((b && (b.date || b.datetime || b.timestamp)) || '').slice(0, 10);
    return direction === 'desc' ? _cmpText_(db, da) : _cmpText_(da, db);
  });
  return copy;
}

function _eodhdLatestRowAtOrBefore_(rows, targetDate) {
  var sorted = _eodhdSortRowsByDate_(rows, 'asc');
  var chosen = null;
  for (var i = 0; i < sorted.length; i++) {
    var d = String((sorted[i] && (sorted[i].date || sorted[i].datetime || sorted[i].timestamp)) || '').slice(0, 10);
    if (!d) continue;
    if (d <= targetDate) chosen = sorted[i];
    else break;
  }
  return chosen;
}

function _eodhdFetchEodWindow_(symbol, key, fromDate, toDate, order) {
  var url = 'https://eodhd.com/api/eod/' + encodeURIComponent(symbol)
    + '?api_token=' + encodeURIComponent(key)
    + '&fmt=json'
    + '&from=' + encodeURIComponent(fromDate)
    + '&to=' + encodeURIComponent(toDate)
    + '&order=' + encodeURIComponent(order || 'a');
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '[]');
  if (!Array.isArray(json)) throw new Error((json && (json.error || json.message)) || 'unexpected_payload');
  return json;
}

function _eodhdFindEarliestDate_(symbol, key) {
  var checkpoints = [1900, 1950, 1970, 1980, 1990, 2000, 2010, 2020];
  var firstYearWithData = null;
  var prevYear = 1900;
  for (var i = 0; i < checkpoints.length; i++) {
    var y = checkpoints[i];
    var rows = _eodhdFetchEodWindow_(symbol, key, y + '-01-01', Math.min(y + 1, 2026) + '-01-01', 'a');
    if (rows.length) {
      firstYearWithData = y;
      break;
    }
    prevYear = y;
  }
  if (firstYearWithData == null) {
    var recent = _eodhdFetchEodWindow_(symbol, key, '2024-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), 'a');
    var recentSorted = _eodhdSortRowsByDate_(recent, 'asc');
    return recentSorted.length ? String(recentSorted[0].date || recentSorted[0].datetime || '').slice(0, 10) : '';
  }
  var low = prevYear;
  var high = firstYearWithData;
  while (high - low > 1) {
    var mid = Math.floor((low + high) / 2);
    var midRows = _eodhdFetchEodWindow_(symbol, key, mid + '-01-01', (mid + 1) + '-01-01', 'a');
    if (midRows.length) high = mid;
    else low = mid;
  }
  var firstRows = _eodhdFetchEodWindow_(symbol, key, high + '-01-01', (high + 1) + '-01-01', 'a');
  var firstSorted = _eodhdSortRowsByDate_(firstRows, 'asc');
  return firstSorted.length ? String(firstSorted[0].date || firstSorted[0].datetime || '').slice(0, 10) : '';
}

function _auditFmpSeries_(item, replayCutoff) {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  if (!apiKey) return _auditFailRow_(item.field, 'FMP', '', 'missing_api_key');
  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  var bestErr = 'unresolved_symbol';
  for (var i = 0; i < item.candidates.length; i++) {
    var symbol = item.candidates[i];
    try {
      var latest = _fmpBoundaryDate_(base, apiKey, symbol, '2024-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'));
      if (!latest) {
        bestErr = 'no_recent_data';
        continue;
      }
      var earliest = _fmpFindEarliestDate_(base, apiKey, symbol);
      return _auditOkRow_(item.field, 'FMP', symbol, earliest, latest, replayCutoff);
    } catch (e) {
      bestErr = String(e);
    }
  }
  return _auditFailRow_(item.field, 'FMP', item.candidates[0] || '', bestErr);
}

function _fmpFetchHistoricalWindow_(base, apiKey, symbol, fromDate, toDate) {
  var url = base + '/historical-price-full/' + encodeURIComponent(symbol)
    + '?apikey=' + encodeURIComponent(apiKey)
    + '&from=' + encodeURIComponent(fromDate)
    + '&to=' + encodeURIComponent(toDate);
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '{}');
  var rows = json && json.historical;
  if (!Array.isArray(rows)) throw new Error((json && (json['Error Message'] || json.error || json.message)) || 'unexpected_payload');
  return rows;
}

function _fmpBoundaryDate_(base, apiKey, symbol, fromDate, toDate) {
  var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, fromDate, toDate);
  if (!rows.length) return '';
  var best = rows[0];
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i].date || '') > String(best.date || '')) best = rows[i];
  }
  return String(best.date || '').slice(0, 10);
}

function _fmpFindEarliestDate_(base, apiKey, symbol) {
  var checkpoints = [1900, 1950, 1970, 1980, 1990, 2000, 2010, 2020];
  var firstYearWithData = null;
  var prevYear = 1900;
  for (var i = 0; i < checkpoints.length; i++) {
    var y = checkpoints[i];
    var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, y + '-01-01', (Math.min(y + 1, 2026)) + '-01-01');
    if (rows.length) {
      firstYearWithData = y;
      break;
    }
    prevYear = y;
  }
  if (firstYearWithData == null) return '';
  var low = prevYear;
  var high = firstYearWithData;
  while (high - low > 1) {
    var mid = Math.floor((low + high) / 2);
    var midRows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, mid + '-01-01', (mid + 1) + '-01-01');
    if (midRows.length) high = mid;
    else low = mid;
  }
  var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, high + '-01-01', (high + 1) + '-01-01');
  if (!rows.length) return '';
  var best = rows[0];
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i].date || '') < String(best.date || '')) best = rows[i];
  }
  return String(best.date || '').slice(0, 10);
}

function _auditOkRow_(field, provider, symbol, earliestDate, latestDate, replayCutoff) {
  var replayPossible = !!(earliestDate && latestDate && String(earliestDate) <= String(replayCutoff) && String(latestDate) >= String(replayCutoff));
  return {
    field: field,
    provider: provider,
    symbol: symbol,
    success_fail: 'success',
    earliest_date: earliestDate || '',
    latest_date: latestDate || '',
    historical_replay_possible: replayPossible ? 'yes' : 'no'
  };
}

function _auditFailRow_(field, provider, symbol, reason) {
  return {
    field: field,
    provider: provider,
    symbol: symbol || '',
    success_fail: 'fail',
    earliest_date: '',
    latest_date: '',
    historical_replay_possible: 'no',
    note: reason || ''
  };
}
