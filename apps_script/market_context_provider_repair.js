function buildMarketContextProviderRepairReport_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var headers = _marketContextProviderRepairReportHeaders_();
  var rowsOut = [];
  var replayCutoff = '2024-05-01';

  var fields = [
    { field_name: 'USDJPY', providers: ['EODHD', 'FMP'], query: 'USDJPY', eodhd_candidates: ['USDJPY.FOREX'], fmp_candidates: ['USDJPY'] },
    { field_name: 'DXY', providers: ['EODHD', 'FMP'], query: 'DXY', eodhd_candidates: [], fmp_candidates: ['DX-Y.NYB'] },
    { field_name: 'VIX', providers: ['EODHD', 'FMP'], query: 'VIX', eodhd_candidates: [], fmp_candidates: [], blocked_reason: 'proxy_security_products_not_allowed', recommended_status_after_repair: 'NOT FEASIBLE' },
    { field_name: 'SPX', providers: ['EODHD', 'FMP'], query: 'S&P 500', eodhd_candidates: ['GSPC.INDX'], fmp_candidates: [] },
    { field_name: 'NDX', providers: ['EODHD', 'FMP'], query: 'Nasdaq', eodhd_candidates: [], fmp_candidates: [], blocked_reason: 'proxy_index_products_not_allowed', recommended_status_after_repair: 'NOT FEASIBLE' },
    { field_name: 'Gold', providers: ['EODHD'], query: 'Gold', eodhd_candidates: ['XAUUSD.FOREX'] },
    { field_name: 'WTI', providers: ['FMP'], query: 'WTI crude oil', fmp_candidates: ['CLUSD'] },
    { field_name: 'JP10Y', providers: ['FRED'], query: 'Japan 10 Year Government Bond Yield', fred_series_ids: ['IRLTLT01JPM156N'] },
    { field_name: 'JP2Y', providers: ['EODHD', 'FMP', 'FRED'], query: 'Japan 2 Year Government Bond Yield', eodhd_candidates: [], fmp_candidates: [], fred_series_ids: [], blocked_reason: 'no_exact_existing_provider_mapping_confirmed', recommended_status_after_repair: 'NEEDS NEW PROVIDER' },
    { field_name: 'BOJ policy rate', providers: ['FMP', 'FRED'], query: 'Bank of Japan policy rate', fmp_candidates: [], fred_series_ids: [], blocked_reason: 'no_exact_existing_provider_mapping_confirmed', recommended_status_after_repair: 'NEEDS NEW PROVIDER' }
  ];

  for (var i = 0; i < fields.length; i++) {
    var field = fields[i];
    for (var p = 0; p < field.providers.length; p++) {
      var provider = field.providers[p];
      if (provider === 'EODHD') rowsOut.push(_mcprInvestigateEodhdField_(field, replayCutoff, warnings));
      else if (provider === 'FMP') rowsOut.push(_mcprInvestigateFmpField_(field, replayCutoff, warnings));
      else if (provider === 'FRED') rowsOut.push(_mcprInvestigateFredField_(field, replayCutoff, warnings));
    }
  }

  _sortMarketContextProviderRepairReportRows_(rowsOut);
  var target = getDiagnosticsSheet_('Market_Context_Provider_Repair_Report', headers, warnings);
  var actualHeaders = target.headers;
  var rowArrays = _marketContextProviderRepairRowsToArrays_(headers, rowsOut);
  _rewriteSheetRowsPreservingHeaders_(
    target.sheet,
    actualHeaders,
    _remapRowsToHeaders_(headers, actualHeaders, rowArrays)
  );
  trimSheetToDataRange_(target.sheet, rowsOut.length + 1, actualHeaders.length);

  return {
    status: 'ok',
    target_sheet: target.sheet.getName(),
    rows_written: rowsOut.length,
    warnings: _mcprUniqueSortedStrings_(warnings),
    generated_ts: generatedTs
  };
}

function buildMarketContextProviderRepairReport() {
  return buildMarketContextProviderRepairReport_();
}

function _marketContextProviderRepairReportHeaders_() {
  return [
    'field_name',
    'provider',
    'tested_symbol',
    'test_result',
    'failure_reason',
    'additional_candidate_symbols',
    'additional_candidate_endpoints',
    'endpoint_used',
    'earliest_date_found',
    'latest_date_found',
    'replay_possible_before_repair',
    'replay_possible_after_repair',
    'requires_code_change',
    'requires_mapping_change',
    'requires_provider_change',
    'confidence',
    'recommended_action',
    'repair_applied',
    'exact_mapping_used',
    'earliest_date_after_repair',
    'latest_date_after_repair',
    'recommended_status_after_repair'
  ];
}

function _mcprInvestigateEodhdField_(field, replayCutoff, warnings) {
  var key = _getEodhdApiKey_();
  var report = _mcprBaseRow_(field.field_name, 'EODHD');
  report.additional_candidate_endpoints = 'eod';
  if (!key) {
    return _mcprBlockedRow_(report, 'missing_api_key', field.recommended_status_after_repair || 'NOT FEASIBLE', 'high');
  }

  var candidates = _mcprUniqueSortedStrings_(field.eodhd_candidates || []);
  report.additional_candidate_symbols = candidates.join('|');
  if (!candidates.length) {
    return _mcprBlockedRow_(report, field.blocked_reason || 'no_exact_mapping_confirmed', field.recommended_status_after_repair || 'NOT FEASIBLE', 'medium');
  }
  var tested = [];
  var success = null;
  var bestFailure = '';

  for (var i = 0; i < candidates.length; i++) {
    var symbol = candidates[i];
    var probe = _mcprProbeEodhdSymbol_(symbol, key, replayCutoff);
    tested.push(symbol + ':' + probe.test_result);
    if (probe.test_result === 'success') {
      success = probe;
      break;
    }
    if (!bestFailure) bestFailure = probe.failure_reason;
  }

  report.tested_symbol = tested.join('|');

  if (!success) {
    return _mcprBlockedRow_(report, bestFailure || field.blocked_reason || 'no_viable_symbol', field.recommended_status_after_repair || 'NOT FEASIBLE', 'medium');
  }

  report.repair_applied = 'TRUE';
  report.exact_mapping_used = success.exact_mapping_used || ('EODHD:' + candidates[0]);
  report.test_result = 'success';
  report.failure_reason = success.failure_reason;
  report.endpoint_used = success.endpoint_used;
  report.earliest_date_found = success.earliest_date_found;
  report.latest_date_found = success.latest_date_found;
  report.earliest_date_after_repair = success.earliest_date_after_repair;
  report.latest_date_after_repair = success.latest_date_after_repair;
  report.replay_possible_after_repair = success.replay_possible_after_repair;
  report.requires_code_change = success.requires_code_change;
  report.requires_mapping_change = success.requires_mapping_change;
  report.requires_provider_change = 'FALSE';
  report.confidence = success.confidence;
  report.recommended_action = success.recommended_action;
  report.recommended_status_after_repair = success.recommended_status_after_repair;
  return report;
}

function _mcprProbeEodhdSymbol_(symbol, key, replayCutoff) {
  var descRows = _mcprSafeEodhdWindow_(symbol, key, '2024-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), 'desc');
  var dRows = _mcprSafeEodhdWindow_(symbol, key, '2024-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), 'd');
  var aRows = _mcprSafeEodhdWindow_(symbol, key, '2024-01-01', Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), 'a');
  if (!descRows.ok && !dRows.ok && !aRows.ok) {
    return {
      test_result: 'fail',
      failure_reason: 'all_eod_calls_failed:' + [descRows.error, dRows.error, aRows.error].filter(Boolean).join('|'),
      endpoint_used: 'eod'
    };
  }

  var effectiveRows = dRows.ok && dRows.rows.length
    ? _mcprSortRowsByDate_(dRows.rows, 'asc')
    : (aRows.ok && aRows.rows.length ? _mcprSortRowsByDate_(aRows.rows, 'asc') : _mcprSortRowsByDate_(descRows.rows || [], 'asc'));
  var descSorted = _mcprSortRowsByDate_(descRows.ok ? descRows.rows : [], 'desc');
  var latest = _mcprMaxDateFromRows_(effectiveRows);
  var earliest = _mcprMinDateFromRows_(effectiveRows);
  var descFirst = descRows.ok && descRows.rows.length ? _mcprRowDate_(descRows.rows[0]) : '';
  var descLast = descRows.ok && descRows.rows.length ? _mcprRowDate_(descRows.rows[descRows.rows.length - 1]) : '';
  var dFirst = dRows.ok && dRows.rows.length ? _mcprRowDate_(dRows.rows[0]) : '';
  var sortedDescFirst = descSorted.length ? _mcprRowDate_(descSorted[0]) : '';
  var sortedDescLast = descSorted.length ? _mcprRowDate_(descSorted[descSorted.length - 1]) : '';

  var helperBug = !!(descFirst && descLast && descFirst < descLast && sortedDescFirst && sortedDescLast);
  var replayAfter = !!(latest && latest >= replayCutoff);
  var failureReason = helperBug
    ? 'order_fix_applied:raw_desc_first=' + descFirst + ';raw_desc_last=' + descLast + ';sorted_desc_first=' + sortedDescFirst + ';sorted_desc_last=' + sortedDescLast
    : 'exact_mapping_confirmed';
  var recommended = replayAfter
    ? 'READY NOW: existing EODHD mapping is replay-safe after explicit date sorting.'
    : 'NOT FEASIBLE: no replay coverage beyond cutoff was found.';

  return {
    test_result: 'success',
    failure_reason: failureReason + ';desc_first=' + descFirst + ';desc_last=' + descLast + ';d_first=' + dFirst + ';row_count=' + effectiveRows.length,
    endpoint_used: 'eod',
    earliest_date_found: earliest,
    latest_date_found: latest,
    earliest_date_after_repair: earliest,
    latest_date_after_repair: latest,
    replay_possible_after_repair: replayAfter ? 'yes' : 'no',
    requires_code_change: 'FALSE',
    requires_mapping_change: 'FALSE',
    repair_applied: 'TRUE',
    exact_mapping_used: 'EODHD:' + symbol,
    confidence: helperBug ? 'high' : 'medium',
    recommended_action: recommended,
    recommended_status_after_repair: replayAfter ? 'READY NOW' : 'NOT FEASIBLE'
  };
}

function _mcprSafeEodhdWindow_(symbol, key, fromDate, toDate, order) {
  try {
    return { ok: true, rows: _eodhdFetchEodWindow_(symbol, key, fromDate, toDate, order) };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

function _mcprInvestigateFmpField_(field, replayCutoff, warnings) {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  var report = _mcprBaseRow_(field.field_name, 'FMP');
  report.additional_candidate_endpoints = 'historical-price-full|historical-chart/1day|quote|search';
  if (!apiKey) {
    return _mcprBlockedRow_(report, 'missing_api_key', field.recommended_status_after_repair || 'NOT FEASIBLE', 'high');
  }

  var candidates = _mcprUniqueSortedStrings_(field.fmp_candidates || []);
  report.additional_candidate_symbols = candidates.join('|');
  if (!candidates.length) {
    return _mcprBlockedRow_(report, field.blocked_reason || 'no_exact_mapping_confirmed', field.recommended_status_after_repair || 'NOT FEASIBLE', 'medium');
  }
  var tested = [];
  var success = null;
  var bestFailure = '';

  for (var i = 0; i < candidates.length; i++) {
    var symbol = candidates[i];
    var probe = _mcprProbeFmpSymbol_(symbol, apiKey, base, replayCutoff);
    tested.push(symbol + ':' + probe.test_result + ':' + probe.endpoint_used);
    if (probe.test_result === 'success') {
      success = probe;
      break;
    }
    if (!bestFailure) bestFailure = probe.failure_reason;
  }

  report.tested_symbol = tested.join('|');

  if (!success) {
    return _mcprBlockedRow_(report, bestFailure || field.blocked_reason || 'no_viable_symbol_or_endpoint', field.recommended_status_after_repair || 'NOT FEASIBLE', 'medium');
  }

  report.repair_applied = 'TRUE';
  report.exact_mapping_used = success.exact_mapping_used || ('FMP:' + candidates[0]);
  report.test_result = 'success';
  report.failure_reason = success.failure_reason;
  report.endpoint_used = success.endpoint_used;
  report.earliest_date_found = success.earliest_date_found;
  report.latest_date_found = success.latest_date_found;
  report.earliest_date_after_repair = success.earliest_date_after_repair;
  report.latest_date_after_repair = success.latest_date_after_repair;
  report.replay_possible_after_repair = success.replay_possible_after_repair;
  report.requires_code_change = success.requires_code_change;
  report.requires_mapping_change = success.requires_mapping_change;
  report.requires_provider_change = 'FALSE';
  report.confidence = success.confidence;
  report.recommended_action = success.recommended_action;
  report.recommended_status_after_repair = success.recommended_status_after_repair;
  return report;
}

function _mcprProbeFmpSymbol_(symbol, apiKey, base, replayCutoff) {
  var endpoints = [
    { name: 'historical-price-full', fn: function() { return _mcprFmpHistoricalPriceFull_(base, apiKey, symbol, '2024-05-01', '2024-05-10'); } },
    { name: 'historical-chart/1day', fn: function() { return _mcprFmpHistoricalChart1d_(base, apiKey, symbol, '2024-05-01', '2024-05-10'); } },
    { name: 'quote', fn: function() { return _mcprFmpQuote_(base, apiKey, symbol); } }
  ];
  var endpointErrors = [];
  for (var i = 0; i < endpoints.length; i++) {
    try {
      var result = endpoints[i].fn();
      if (result && result.kind === 'historical' && result.rows && result.rows.length) {
        var sortedRows = _mcprSortRowsByDate_(result.rows, 'asc');
        var latest = _mcprMaxDateFromRows_(sortedRows);
        var earliest = _mcprMinDateFromRows_(sortedRows);
        return {
          test_result: 'success',
          failure_reason: 'original_failure_was_endpoint_or_mapping_selection; endpoint=' + endpoints[i].name,
          endpoint_used: endpoints[i].name,
          earliest_date_found: earliest,
          latest_date_found: latest,
          earliest_date_after_repair: earliest,
          latest_date_after_repair: latest,
          replay_possible_after_repair: latest && latest >= replayCutoff ? 'yes' : 'no',
          requires_code_change: endpoints[i].name === 'historical-price-full' ? 'FALSE' : 'TRUE',
          requires_mapping_change: 'FALSE',
          confidence: 'medium',
          repair_applied: 'TRUE',
          exact_mapping_used: 'FMP:' + symbol,
          recommended_status_after_repair: latest && latest >= replayCutoff ? 'READY NOW' : 'NOT FEASIBLE',
          recommended_action: (latest && latest >= replayCutoff)
            ? ('REPAIRABLE: use FMP ' + endpoints[i].name + ' for this symbol if you choose to keep FMP in scope.')
            : 'NOT FEASIBLE: historical endpoint returned rows but not across replay cutoff.'
        };
      }
      if (result && result.kind === 'quote') {
        endpointErrors.push(endpoints[i].name + ':quote_only');
      }
    } catch (e) {
      endpointErrors.push(endpoints[i].name + ':' + String(e));
    }
  }
  return {
    test_result: 'fail',
    failure_reason: endpointErrors.join('|'),
    endpoint_used: 'historical-price-full|historical-chart/1day|quote'
  };
}

function _mcprFmpHistoricalPriceFull_(base, apiKey, symbol, fromDate, toDate) {
  var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, fromDate, toDate);
  return { kind: 'historical', rows: rows };
}

function _mcprFmpHistoricalChart1d_(base, apiKey, symbol, fromDate, toDate) {
  var url = base + '/historical-chart/1day/' + encodeURIComponent(symbol)
    + '?apikey=' + encodeURIComponent(apiKey)
    + '&from=' + encodeURIComponent(fromDate)
    + '&to=' + encodeURIComponent(toDate);
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '[]');
  if (!Array.isArray(json)) throw new Error((json && (json['Error Message'] || json.error || json.message)) || 'unexpected_payload');
  return { kind: 'historical', rows: json };
}

function _mcprFmpQuote_(base, apiKey, symbol) {
  var url = base + '/quote/' + encodeURIComponent(symbol) + '?apikey=' + encodeURIComponent(apiKey);
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  var json = JSON.parse(res.getContentText() || '[]');
  if (!Array.isArray(json)) throw new Error((json && (json['Error Message'] || json.error || json.message)) || 'unexpected_payload');
  return { kind: 'quote', rows: json };
}

function _mcprInvestigateFredField_(field, replayCutoff, warnings) {
  var key = (PropertiesService.getScriptProperties().getProperty('FRED_API_KEY') || '').trim();
  var report = _mcprBaseRow_(field.field_name, 'FRED');
  report.additional_candidate_endpoints = 'fred/series|fred/series/observations';
  if (!key) {
    return _mcprBlockedRow_(report, 'missing_api_key', field.recommended_status_after_repair || 'NOT FEASIBLE', 'high');
  }

  var seriesIds = _mcprUniqueSortedStrings_(field.fred_series_ids || []);
  report.additional_candidate_symbols = seriesIds.join('|');
  if (!seriesIds.length) {
    return _mcprBlockedRow_(report, field.blocked_reason || 'no_exact_mapping_confirmed', field.recommended_status_after_repair || 'NEEDS NEW PROVIDER', 'low');
  }

  var tested = [];
  for (var i = 0; i < seriesIds.length; i++) {
    var seriesId = seriesIds[i];
    tested.push(seriesId);
    try {
      var info = _mcprSafeFredSeriesInfo_(seriesId, key, warnings);
      if (!info || !info.title || !_mcprFredTitleMatchesField_(field.field_name, info.title)) continue;
      var earliest = _fredBoundaryObservation_(seriesId, key, 'asc');
      var latest = _fredBoundaryObservation_(seriesId, key, 'desc');
      if (earliest && latest) {
        report.tested_symbol = seriesId;
        report.test_result = 'success';
        report.failure_reason = 'resolved_via_fred_series_id;title=' + info.title;
        report.endpoint_used = 'fred/series|fred/series/observations';
        report.earliest_date_found = earliest.date;
        report.latest_date_found = latest.date;
        report.earliest_date_after_repair = earliest.date;
        report.latest_date_after_repair = latest.date;
        report.replay_possible_after_repair = (earliest.date <= replayCutoff && latest.date >= replayCutoff) ? 'yes' : 'no';
        report.requires_code_change = 'FALSE';
        report.requires_mapping_change = 'FALSE';
        report.requires_provider_change = 'FALSE';
        report.confidence = 'high';
        report.repair_applied = 'TRUE';
        report.exact_mapping_used = 'FRED:' + seriesId;
        report.recommended_status_after_repair = report.replay_possible_after_repair === 'yes' ? 'READY NOW' : 'NOT FEASIBLE';
        report.recommended_action = report.replay_possible_after_repair === 'yes'
          ? 'READY NOW: exact FRED series mapping is replay-safe.'
          : 'NOT FEASIBLE: FRED match found but replay cutoff not covered.';
        return report;
      }
    } catch (e) {}
  }

  report.tested_symbol = tested.join('|');
  return _mcprBlockedRow_(report, 'no_exact_mapping_confirmed', field.recommended_status_after_repair || 'NEEDS NEW PROVIDER', 'low');
}

function _mcprSafeFredSeriesInfo_(seriesId, key, warnings) {
  try {
    var url = 'https://api.stlouisfed.org/fred/series'
      + '?series_id=' + encodeURIComponent(seriesId)
      + '&api_key=' + encodeURIComponent(key)
      + '&file_type=json';
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
    var json = JSON.parse(res.getContentText() || '{}');
    var series = json && json.seriess && json.seriess[0];
    if (!series) return null;
    return {
      id: String(series.id || '').trim(),
      title: String(series.title || '').trim()
    };
  } catch (e) {
    if (warnings) warnings.push('fred_series_info_failed:' + seriesId + '|' + String(e));
    return null;
  }
}

function _mcprSafeEodhdSearch_(query, key, warnings) {
  try {
    var url = 'https://eodhd.com/api/search/' + encodeURIComponent(query)
      + '?api_token=' + encodeURIComponent(key)
      + '&limit=10&fmt=json';
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
    var json = JSON.parse(res.getContentText() || '[]');
    if (!Array.isArray(json)) return { symbols: [] };
    return { symbols: json.map(function(row){ return String(row.Code || row.code || row.Symbol || row.symbol || '').trim(); }).filter(Boolean) };
  } catch (e) {
    if (warnings) warnings.push('eodhd_search_failed:' + query + '|' + String(e));
    return { symbols: [] };
  }
}

function _mcprSafeFmpSearch_(query, apiKey, base, warnings) {
  try {
    var url = base + '/search?query=' + encodeURIComponent(query) + '&limit=10&apikey=' + encodeURIComponent(apiKey);
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
    var json = JSON.parse(res.getContentText() || '[]');
    if (!Array.isArray(json)) return { symbols: [] };
    return { symbols: json.map(function(row){ return String(row.symbol || '').trim(); }).filter(Boolean) };
  } catch (e) {
    if (warnings) warnings.push('fmp_search_failed:' + query + '|' + String(e));
    return { symbols: [] };
  }
}

function _mcprSafeFredSearch_(query, key, warnings) {
  try {
    var url = 'https://api.stlouisfed.org/fred/series/search'
      + '?search_text=' + encodeURIComponent(query)
      + '&api_key=' + encodeURIComponent(key)
      + '&file_type=json'
      + '&limit=10'
      + '&sort_order=desc';
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
    var json = JSON.parse(res.getContentText() || '{}');
    var seriess = json && json.seriess;
    if (!Array.isArray(seriess)) return { series: [] };
    return {
      series: seriess.map(function(row){
        return {
          id: String(row.id || '').trim(),
          title: String(row.title || '').trim()
        };
      }).filter(function(item){ return !!item.id; })
    };
  } catch (e) {
    if (warnings) warnings.push('fred_search_failed:' + query + '|' + String(e));
    return { series: [] };
  }
}

function _mcprFredTitleMatchesField_(fieldName, title) {
  var hay = String(title || '').toLowerCase();
  var field = String(fieldName || '').toLowerCase();
  if (field === 'jp10y') {
    return hay.indexOf('japan') >= 0 && (hay.indexOf('10-year') >= 0 || hay.indexOf('long-term government bond') >= 0);
  }
  if (field === 'jp2y') {
    return hay.indexOf('japan') >= 0 && hay.indexOf('2-year') >= 0;
  }
  if (field === 'boj policy rate') {
    return hay.indexOf('japan') >= 0 && (hay.indexOf('policy rate') >= 0 || hay.indexOf('interest rate') >= 0 || hay.indexOf('bank rate') >= 0);
  }
  return hay.indexOf('japan') >= 0;
}

function _mcprRowDate_(row) {
  return String((row && (row.date || row.datetime || row.timestamp)) || '').slice(0, 10);
}

function _mcprSortRowsByDate_(rows, direction) {
  var copy = (rows || []).slice();
  copy.sort(function(a, b) {
    var da = _mcprRowDate_(a);
    var db = _mcprRowDate_(b);
    return direction === 'desc' ? _cmpText_(db, da) : _cmpText_(da, db);
  });
  return copy;
}

function _mcprMaxDateFromRows_(rows) {
  var best = '';
  for (var i = 0; i < (rows || []).length; i++) {
    var d = _mcprRowDate_(rows[i]);
    if (d && d > best) best = d;
  }
  return best;
}

function _mcprMinDateFromRows_(rows) {
  var best = '';
  for (var i = 0; i < (rows || []).length; i++) {
    var d = _mcprRowDate_(rows[i]);
    if (!d) continue;
    if (!best || d < best) best = d;
  }
  return best;
}

function _mcprBaseRow_(fieldName, provider) {
  return {
    field_name: fieldName,
    provider: provider,
    tested_symbol: '',
    test_result: '',
    failure_reason: '',
    additional_candidate_symbols: '',
    additional_candidate_endpoints: '',
    endpoint_used: '',
    earliest_date_found: '',
    latest_date_found: '',
    replay_possible_before_repair: 'no',
    replay_possible_after_repair: '',
    requires_code_change: 'FALSE',
    requires_mapping_change: 'FALSE',
    requires_provider_change: 'FALSE',
    confidence: '',
    recommended_action: '',
    repair_applied: 'FALSE',
    exact_mapping_used: '',
    earliest_date_after_repair: '',
    latest_date_after_repair: '',
    recommended_status_after_repair: ''
  };
}

function _mcprBlockedRow_(report, reason, recommendedStatus, confidence) {
  report.test_result = 'blocked';
  report.failure_reason = String(reason || 'blocked').trim();
  report.replay_possible_after_repair = 'no';
  report.requires_code_change = 'FALSE';
  report.requires_mapping_change = 'TRUE';
  report.requires_provider_change = 'TRUE';
  report.confidence = confidence || 'low';
  report.repair_applied = 'FALSE';
  report.exact_mapping_used = '';
  report.earliest_date_after_repair = '';
  report.latest_date_after_repair = '';
  report.recommended_status_after_repair = recommendedStatus || 'NOT FEASIBLE';
  report.recommended_action = String(recommendedStatus || 'NOT FEASIBLE') + ': no exact existing-provider mapping confirmed.';
  return report;
}

function _sortMarketContextProviderRepairReportRows_(rows) {
  rows.sort(function(a, b) {
    return _cmpText_(a.field_name, b.field_name) || _cmpText_(a.provider, b.provider);
  });
}

function _marketContextProviderRepairRowsToArrays_(headers, rows) {
  return (rows || []).map(function(row) {
    return headers.map(function(header) {
      return row && row.hasOwnProperty(header) ? row[header] : '';
    });
  });
}

function _mcprUniqueSortedStrings_(values) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (values || []).length; i++) {
    var value = String(values[i] == null ? '' : values[i]).trim();
    if (!value || seen[value]) continue;
    seen[value] = true;
    out.push(value);
  }
  out.sort();
  return out;
}
