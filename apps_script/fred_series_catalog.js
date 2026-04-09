/*********************************************************
 * fred_series_catalog.gs
 *
 * Purpose:
 *   Build and maintain a deterministic local FRED series catalog in
 *   the FRED_Series_ID sheet so SeriesMap fallback work becomes easier.
 *
 * Design:
 *   - Seed search terms from local artifacts only:
 *       Event.indicator_name
 *       SeriesMap.indicator_name_pattern
 *       SeriesMap_Suggestions.indicator_name_pattern
 *   - Query FRED series search deterministically
 *   - Upsert results into FRED_Series_ID by series_id
 *   - Never writes to canonical SeriesMap
 **********************************************************/

var FRED_CATALOG_CFG = {
  SHEET: 'FRED_Series_ID',
  MAX_QUERIES_PER_RUN: 40,
  SEARCH_LIMIT: 25,
  SLEEP_MS_PER_CALL: 400,
  MAX_TERM_LENGTH: 120,
  FILTER_US_MACRO_ONLY: true,
  STATE_KEY_LAST_INDEX: 'FRED_CATALOG_LAST_QUERY_INDEX',
  STATE_KEY_LAST_RUN_TS: 'FRED_CATALOG_LAST_RUN_TS'
};

function menuBuildFredSeriesCatalog_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildFredSeriesCatalogFromLocalArtifacts_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'FRED catalog build finished', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    SpreadsheetApp.getActive().toast(
      'FRED catalog: queries=' + (res.queries_run || 0) +
      ', upserts=' + (res.upserted || 0) +
      ', rows=' + (res.catalog_rows || 0),
      'FRED Catalog',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'FRED catalog build failed', {
        error: String(e && e.message || e),
        stack: String(e && e.stack || '')
      });
    }
    throw e;
  }
}

function buildFredSeriesCatalogFromLocalArtifacts_() {
  var apiKey = (PropertiesService.getScriptProperties().getProperty('FRED_API_KEY') || '').trim();
  if (!apiKey) throw new Error('Missing FRED_API_KEY');

  var sh = _ensureFredCatalogSheet_();
  var allQueries = _collectFredCatalogQueries_();
  var range = _getFredCatalogQueryBatch_(allQueries, FRED_CATALOG_CFG.MAX_QUERIES_PER_RUN);
  var queries = range.queries;
  var existing = _loadExistingFredCatalogIndex_(sh);
  var upserts = 0;
  var skippedFiltered = 0;
  var errors = 0;

  for (var i = 0; i < queries.length; i++) {
    var query = queries[i];
    try {
      var seriess = _fredSeriesSearch_(apiKey, query, FRED_CATALOG_CFG.SEARCH_LIMIT);
      var filtered = _filterFredCatalogSearchResults_(query, seriess || []);
      skippedFiltered += filtered.skipped;
      upserts += _upsertFredCatalogResults_(sh, existing, query, filtered.rows || []);
      if (FRED_CATALOG_CFG.SLEEP_MS_PER_CALL > 0) Utilities.sleep(FRED_CATALOG_CFG.SLEEP_MS_PER_CALL);
    } catch (e) {
      errors++;
      if (typeof appendLog === 'function') {
        appendLog('WARN', 'FRED catalog query failed', {
          module: 'fred_series_catalog',
          query: query,
          error: String(e && e.message || e)
        });
      }
    }
  }

  var pruned = _pruneFredCatalogSheet_(sh);
  _saveFredCatalogBatchState_(allQueries.length, range.nextIndex);

  var result = {
    total_queries: allQueries.length,
    start_index: range.startIndex,
    next_index: range.nextIndex,
    queries_run: queries.length,
    upserted: upserts,
    skipped_filtered: skippedFiltered,
    pruned: pruned,
    errors: errors,
    catalog_rows: Math.max(0, sh.getLastRow() - 1),
    completed: (allQueries.length === 0) ? true : (range.nextIndex === 0)
  };

  if (typeof appendLog === 'function') {
    appendLog('INFO', 'FRED catalog build summary', {
      module: 'fred_series_catalog',
      result: result
    });
  }
  return result;
}

function resetFredSeriesCatalogProgress_() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_INDEX);
  props.deleteProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_RUN_TS);
  return { ok: true };
}

function _ensureFredCatalogSheet_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(FRED_CATALOG_CFG.SHEET);
  if (!sh) throw new Error('Sheet "' + FRED_CATALOG_CFG.SHEET + '" not found. Create it first.');

  var headers = [
    'series_id',
    'title',
    'search_query',
    'frequency',
    'frequency_short',
    'units',
    'units_short',
    'seasonal_adjustment',
    'seasonal_adjustment_short',
    'popularity',
    'notes',
    'last_updated',
    'observation_start',
    'observation_end',
    'source_provider',
    'catalog_updated_ts'
  ];

  var lastCol = Math.max(1, sh.getLastColumn());
  var current = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(function(h){ return String(h || '').trim(); });
  if (current.length === 1 && current[0] === '') {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    return sh;
  }

  var have = {};
  for (var i = 0; i < current.length; i++) have[String(current[i] || '').trim().toLowerCase()] = true;
  var toAdd = [];
  for (var j = 0; j < headers.length; j++) {
    if (!have[String(headers[j]).toLowerCase()]) toAdd.push(headers[j]);
  }
  if (toAdd.length) {
    sh.getRange(1, current.length + 1, 1, toAdd.length).setValues([toAdd]);
  }
  return sh;
}

function _collectFredCatalogQueries_() {
  var seen = {};
  var out = [];

  function addTerm_(term) {
    var normalized = _normalizeFredCatalogQuery_(term);
    if (!normalized) return;
    if (seen[normalized]) return;
    seen[normalized] = true;
    out.push(normalized);
  }

  _scanSheetTerms_('Event', 'indicator_name', addTerm_);
  _scanSheetTerms_('SeriesMap', 'indicator_name_pattern', addTerm_);
  _scanSheetTerms_('SeriesMap_Suggestions', 'indicator_name_pattern', addTerm_);

  out.sort();
  return out;
}

function _getFredCatalogQueryBatch_(allQueries, maxQueries) {
  var total = allQueries.length;
  var props = PropertiesService.getScriptProperties();
  var raw = props.getProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_INDEX);
  var startIndex = raw ? Number(raw) : 0;
  if (!isFinite(startIndex) || startIndex < 0 || startIndex >= total) startIndex = 0;

  var endIndex = Math.min(total, startIndex + Math.max(1, Number(maxQueries || 1)));
  var queries = allQueries.slice(startIndex, endIndex);
  var nextIndex = (endIndex >= total) ? 0 : endIndex;

  return {
    startIndex: startIndex,
    endIndex: endIndex,
    nextIndex: nextIndex,
    queries: queries
  };
}

function _saveFredCatalogBatchState_(totalQueries, nextIndex) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_INDEX, String(nextIndex || 0));
  props.setProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_RUN_TS, new Date().toISOString());
  if (Number(totalQueries || 0) === 0) {
    props.setProperty(FRED_CATALOG_CFG.STATE_KEY_LAST_INDEX, '0');
  }
}

function _scanSheetTerms_(sheetName, headerName, addFn) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(sheetName);
  if (!sh || sh.getLastRow() < 2) return;

  var values = sh.getDataRange().getValues();
  var headers = values[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = headers.indexOf(String(headerName || '').trim().toLowerCase());
  if (idx < 0) return;

  for (var r = 1; r < values.length; r++) {
    addFn(values[r][idx]);
  }
}

function _normalizeFredCatalogQuery_(term) {
  var s = String(term || '').trim();
  if (!s) return '';

  s = _normalizeIndicatorForFREDQuery_(s);
  s = s.replace(/\b(sa|nsa|mom|yoy|qoq|m m|y y)\b/gi, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  if (!s) return '';

  if (s.length > FRED_CATALOG_CFG.MAX_TERM_LENGTH) {
    s = s.slice(0, FRED_CATALOG_CFG.MAX_TERM_LENGTH).trim();
  }
  return s;
}

function _loadExistingFredCatalogIndex_(sh) {
  var out = {};
  var lastRow = sh.getLastRow();
  if (lastRow < 2) return out;

  var values = sh.getDataRange().getValues();
  var headers = values[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idIdx = headers.indexOf('series_id');
  if (idIdx < 0) return out;

  for (var r = 1; r < values.length; r++) {
    var id = String(values[r][idIdx] || '').trim();
    if (id) out[id] = r + 1;
  }
  return out;
}

function _upsertFredCatalogResults_(sh, existing, query, seriess) {
  if (!seriess || !seriess.length) return 0;

  var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;

  function setField_(row, name, value) {
    var pos = idx[String(name).toLowerCase()];
    if (typeof pos === 'number' && pos >= 0) row[pos] = value;
  }

  var upserts = 0;
  for (var j = 0; j < seriess.length; j++) {
    var s = seriess[j] || {};
    var seriesId = String(s.id || '').trim();
    if (!seriesId) continue;

    var row = new Array(headers.length).fill('');
    setField_(row, 'series_id', seriesId);
    setField_(row, 'title', String(s.title || ''));
    setField_(row, 'search_query', query);
    setField_(row, 'frequency', String(s.frequency || ''));
    setField_(row, 'frequency_short', String(s.frequency_short || ''));
    setField_(row, 'units', String(s.units || ''));
    setField_(row, 'units_short', String(s.units_short || ''));
    setField_(row, 'seasonal_adjustment', String(s.seasonal_adjustment || ''));
    setField_(row, 'seasonal_adjustment_short', String(s.seasonal_adjustment_short || ''));
    setField_(row, 'popularity', String(s.popularity || ''));
    setField_(row, 'notes', String(s.notes || ''));
    setField_(row, 'last_updated', String(s.last_updated || ''));
    setField_(row, 'observation_start', String(s.observation_start || ''));
    setField_(row, 'observation_end', String(s.observation_end || ''));
    setField_(row, 'source_provider', 'FRED');
    setField_(row, 'catalog_updated_ts', new Date().toISOString());

    if (existing[seriesId]) {
      sh.getRange(existing[seriesId], 1, 1, row.length).setValues([row]);
    } else {
      sh.getRange(sh.getLastRow() + 1, 1, 1, row.length).setValues([row]);
      existing[seriesId] = sh.getLastRow();
    }
    upserts++;
  }
  return upserts;
}

function _filterFredCatalogSearchResults_(query, seriess) {
  var out = [];
  var skipped = 0;
  for (var i = 0; i < (seriess || []).length; i++) {
    var s = seriess[i] || {};
    if (_isAllowedFredCatalogSeries_(query, s)) out.push(s);
    else skipped++;
  }
  return { rows: out, skipped: skipped };
}

function _isAllowedFredCatalogSeries_(query, seriesRow) {
  if (!FRED_CATALOG_CFG.FILTER_US_MACRO_ONLY) return true;

  var title = String(seriesRow && seriesRow.title || '').trim();
  var notes = String(seriesRow && seriesRow.notes || '').trim();
  var units = String(seriesRow && (seriesRow.units_short || seriesRow.units) || '').trim();
  var freq = String(seriesRow && (seriesRow.frequency_short || seriesRow.frequency) || '').trim().toUpperCase();
  var hay = (title + ' ' + notes + ' ' + units).toLowerCase();
  var q = String(query || '').trim().toLowerCase();

  if (!title) return false;

  if (/\b(germany|berlin|euro area|europe|france|italy|spain|united kingdom|uk\b|england|scotland|wales|japan|tokyo|china|beijing|canada|australia|new zealand|sweden|norway|switzerland|korea|singapore|india|brazil|mexico|argentina|russia|moscow|south africa)\b/.test(hay)) {
    return false;
  }

  if (/\b(state|county|parish|borough|city of|metropolitan|msa|micropolitan|census division|school district)\b/.test(hay)) {
    return false;
  }

  if (/\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(hay)) {
    return false;
  }

  if (/\b(federal reserve bank of|commercial bank|bank prime loan|deposit|loans to|real estate loan|delinquency)\b/.test(hay) &&
      !/\b(treasury|yield|mortgage|fed funds|policy rate|interest rate)\b/.test(hay)) {
    return false;
  }

  if (/\b(pandemic unemployment assistance|pua|continued claims|insured unemployment)\b/.test(hay)) {
    return false;
  }

  if (/\bnew private housing units authorized by building permits for\b/.test(hay) &&
      !/\bunited states\b/.test(hay)) {
    return false;
  }

  if (/\bconsumer price index\b/.test(q) && !/\bcore\b|\bnon food non energy\b|\bexcluding food and energy\b/.test(q) &&
      /\bnon food non energy\b|\bexcluding food and energy\b|\bcore\b/.test(hay)) {
    return false;
  }

  if (/\bheadline\b|\bcpi\b/.test(q) && /\bresearch consumer price index\b/.test(hay)) {
    return false;
  }

  if (/\bmanufacturing production\b/.test(q) && /\baverage hourly earnings\b/.test(hay)) {
    return false;
  }

  if (/\b(discontinued)\b/.test(hay) && !/\bmortgage\b/.test(hay)) {
    return false;
  }

  if (freq && ['D', 'W', 'M', 'Q', 'A'].indexOf(freq) === -1) {
    return false;
  }

  if (/\b(us\b|u\.s\.|united states|national)\b/.test(hay)) return true;
  if (/\b(gdpnow|gross domestic product|consumer price index|producer price index|personal consumption expenditures|payroll|employment|unemployment|jobless claims|retail sales|housing starts|building permits|mortgage|treasury|yield|federal funds|industrial production|capacity utilization|consumer confidence|sentiment|trade balance|crude petroleum|oil|inventories|factory orders|durable goods|house price index|adp)\b/.test(hay)) {
    return true;
  }

  if (/\b(percent|index|billions of dollars|millions of dollars|thousands of persons|thousand persons)\b/.test(hay) &&
      /\b(cpi|ppi|pce|gdp|employment|unemployment|sales|hours|earnings|claims|permits|starts|orders|inventories|yield|rate)\b/.test(q + ' ' + hay)) {
    return true;
  }

  return false;
}

function _pruneFredCatalogSheet_(sh) {
  if (!FRED_CATALOG_CFG.FILTER_US_MACRO_ONLY) return 0;
  if (!sh || sh.getLastRow() < 2) return 0;

  var values = sh.getDataRange().getValues();
  var headers = values[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;

  var kept = [values[0]];
  var removed = 0;

  for (var r = 1; r < values.length; r++) {
    var row = values[r] || [];
    var seriesRow = {
      title: (typeof idx.title === 'number' && idx.title < row.length) ? row[idx.title] : '',
      notes: (typeof idx.notes === 'number' && idx.notes < row.length) ? row[idx.notes] : '',
      units: (typeof idx.units === 'number' && idx.units < row.length) ? row[idx.units] : '',
      units_short: (typeof idx.units_short === 'number' && idx.units_short < row.length) ? row[idx.units_short] : '',
      frequency: (typeof idx.frequency === 'number' && idx.frequency < row.length) ? row[idx.frequency] : '',
      frequency_short: (typeof idx.frequency_short === 'number' && idx.frequency_short < row.length) ? row[idx.frequency_short] : ''
    };
    var query = (typeof idx.search_query === 'number' && idx.search_query < row.length) ? row[idx.search_query] : '';
    if (_isAllowedFredCatalogSeries_(query, seriesRow)) kept.push(row);
    else removed++;
  }

  if (!removed) return 0;

  sh.clearContents();
  sh.getRange(1, 1, kept.length, kept[0].length).setValues(kept);
  return removed;
}
