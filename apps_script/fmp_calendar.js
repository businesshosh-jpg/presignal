/*******************************************************
 * fmp_calendar.gs
 * - Fetch upcoming events from FMP
 * - Normalize rows to your schema
 * - Upsert into Event using fallback key (country+indicator_name+release_ts)
 * - NO sheet auto-creation (throws if Event is missing)
 * - Adds missing columns at the END if the Event tab exists
 *******************************************************/

/** ===== Utilities shared in this file only ===== **/

/**
 * Return the Event sheet or throw (policy: never auto-create tabs).
 */
function getEventSheet() {
  var name = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
  var sh = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sh) throw new Error('Event sheet "' + name + '" not found. Create it first.');
  return sh;
}

/**
 * Ensure headers exist on the Event sheet and add any missing columns AT THE END.
 * Does not create new sheets.
 */
function ensureEventHeaders_(sh) {
  var required = [
    'object','country','indicator_name','genre','importance',
    'type','event_id','batch_id','release_ts',
    'source_cal','consensus_value','prev_revision',
    'released_value','released_ts',
    'source_provider','source_series_id','transform',
    'release_status','notes','resolution_method','confidence_level'
  ];

  var rng = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn()));
  var values = rng.getValues();
  var headers = (values && values[0]) ? values[0].map(function(h){ return String(h); }) : [];

  // If empty sheet, just set headers
  if (headers.length === 1 && headers[0] === '') {
    sh.getRange(1, 1, 1, required.length).setValues([required]);
    return required;
  }

  // Build case-insensitive set of existing headers (trim + lower)
  var haveLC = {};
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i] || '');
    haveLC[h.trim().toLowerCase()] = true;
  }

  // Append only those required that do not already exist (case-insensitive)
  var toAppend = [];
  for (var j = 0; j < required.length; j++) {
    var need = required[j];
    if (!haveLC[need.toLowerCase()]) {
      toAppend.push(need);
    }
  }

  if (toAppend.length > 0) {
    sh.getRange(1, headers.length + 1, 1, toAppend.length).setValues([toAppend]);
    headers = headers.concat(toAppend);
  }

  return headers; // original (possibly mixed-case) names
}


/**
 * Helper: coalesce first non-empty value from a list of candidates.
 */
function _coalesce_() {
  for (var i = 0; i < arguments.length; i++) {
    var v = arguments[i];
    if (v === 0) return v;
    if (v && String(v).trim() !== '') return v;
  }
  return '';
}

/**
 * Helper: parse numeric like "12.3%" or "1,234.56" → Number or null.
 */
function _parseNumber_(v) {
  if (v === null || v === undefined) return null;
  var s = String(v).trim();
  if (s === '') return null;
  s = s.replace(/[%\s,]/g, '');
  if (s === '' || isNaN(Number(s))) return null;
  return Number(s);
}

/**
 * Helper: parse a date/time (ISO string or epoch) and round to nearest minute (UTC).
 * Returns ISO8601 string "YYYY-MM-DDTHH:mm:00Z" or '' if invalid.
 */
function _parseReleaseTsUtcMinute_(input) {
  if (input === null || input === undefined || String(input).trim() === '') return '';
  var d;
  // epoch (ms or s)
  if (typeof input === 'number') {
    d = new Date(input < 1e12 ? input * 1000 : input);
  } else {
    var s = String(input).trim();
    // If numeric string
    if (/^\d{10,13}$/.test(s)) {
      var num = Number(s);
      d = new Date(num < 1e12 ? num * 1000 : num);
    } else {
      // MINIMAL ADD: if no timezone info, treat as UTC by appending 'Z'
      // (FMP times are UTC; this prevents local-TZ interpretation)
      if (!/[zZ]|[+\-]\d{2}:\d{2}$/.test(s)) {
        // allow 'YYYY-MM-DD' or 'YYYY-MM-DD HH:mm[:ss]' formats
        if (/^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$/.test(s)) {
          s = s.replace(' ', 'T') + 'Z';
        }
      }
      // Let Date parse; we will convert to UTC
      d = new Date(s);
    }
  }
  if (String(d) === 'Invalid Date') return '';
  // Round to nearest minute
  var ms = d.getTime();
  var rounded = Math.round(ms / 60000) * 60000;
  var r = new Date(rounded);
  // Convert to UTC ISO (strip ms)
  return r.toISOString().replace(/\.\d{3}Z$/, 'Z').replace(/:\d{2}Z$/, ':00Z');
}


/** ===== Normalization ===== **/

/**
 * Normalize one raw FMP row to our Event schema.
 * - object="econ_event"
 * - indicator_name from indicator_name|title|event|name|category
 * - country from country|ccy|region (uppercased)
 * - genre from genre|category|group
 * - importance from importance|impact|importanceText|importance_level
 * - consensus_value, prev_revision cleaned to Number (or null)
 * - release_ts parsed to UTC ISO minute
 * - source_cal="FMP"
 * - event_id/batch_id/type left blank (post-pass fills these)
 */

function _pickFirst_(obj, keys) {
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    if (obj && Object.prototype.hasOwnProperty.call(obj, k)) {
      var v = obj[k];
      if (v === 0) return v;
      if (v !== null && v !== undefined && String(v).trim() !== '') return v;
    }
  }
  return '';
}

// Parse a TS candidate (ISO / epoch / date+time) to UTC minute ISO or ''.
function _parseToUtcMinuteIso_(v) {
  return _parseReleaseTsUtcMinute_(v); // reuse your existing parser
}



function normalizeFmpRow_(raw) {
  // --- Core coalesced fields ---
  var indicator = _coalesce_(raw.indicator_name, raw.title, raw.event, raw.name, raw.category);
  var country = String(_coalesce_(raw.country, raw.ccy, raw.region)).toUpperCase();
  // Broadened alias search for genre/category
  var genre = _pickFirst_(raw, [
    'genre',
    'category', 'categoryName', 'category_name',
    'group', 'groupName', 'group_name',
    'eventType', 'event_type',
    'section', 'kind'
  ]);

  // Fallback: infer from indicator name if still blank
  if (!genre) {
    genre = _inferGenreFromName_(String(_coalesce_(raw.indicator_name, raw.title, raw.event, raw.name, raw.category) || ''));
  }

  var importance = _coalesce_(raw.importance, raw.impact, raw.importanceText, raw.importance_level);

  // --- Scheduled release time (keep your original logic) ---
  var releaseIso = _parseReleaseTsUtcMinute_(_coalesce_(raw.release_ts, raw.datetime, raw.date, raw.time));

  // --- Consensus & Previous (cover common aliases) ---
  var consensusRaw = _pickFirst_(raw, ['consensus_value','consensus','estimate','forecast','expected']);
  var prevRaw      = _pickFirst_(raw, ['prev_revision','previous','previousValue','prev','prior','revised','revisedPrevious']);
  var consensus    = _parseNumber_(consensusRaw);
  var prevRev      = _parseNumber_(prevRaw);

  // --- Actuals (only if truly present) ---
  // 1) Detect an actual value using common aliases
  var actualRaw = _pickFirst_(raw, ['released_value','actual','actualValue','value','latest']);
  var actualNum = _parseNumber_(actualRaw);
  var hasActual = (actualNum !== null && actualRaw !== '');

  // 2) Only pick an "actual time" if we have an actual value.
  //    IMPORTANT: do NOT include scheduled aliases ('date','datetime','time') here,
  //    otherwise released_ts will mirror release_ts.
  var releasedTsRaw = hasActual ? _pickFirst_(raw, [
    'released_ts','releasedAt','releaseDate','timestamp','actualTime','actual_ts'
  ]) : '';

  var releasedIso = hasActual ? _parseReleaseTsUtcMinute_(releasedTsRaw) : '';

  // 3) Status follows the presence of an actual (not the presence of scheduled time)
  var releaseStatus = hasActual ? 'released' : 'scheduled';
  var resolutionMethod = hasActual ? 'direct' : '';
  var confidenceLevel = hasActual ? 'medium' : '';

  // --- Source lineage (only stamp if the calendar provided an actual) ---
  var sourceProvider = hasActual ? 'FMP' : '';
  var sourceSeriesId = hasActual ? String(_pickFirst_(raw, ['symbol','series','seriesId','code','id']) || '') : '';
  var transform      = hasActual ? String(_pickFirst_(raw, ['transform','calc','aggregation']) || '') : '';
  var notes = '';


  if (releaseStatus === 'released') {
    sourceProvider = 'FMP';
    sourceSeriesId = String(_pickFirst_(raw, ['symbol','series','seriesId','code','id']) || '');
    transform      = String(_pickFirst_(raw, ['transform','calc','aggregation']) || '');
  }

  return {
    object: 'econ_event',
    country: country || '',
    indicator_name: indicator || '',
    genre: genre || '',
    importance: importance || '',

    // IDs filled by post-pass
    type: '',
    event_id: '',
    batch_id: '',

    // Times
    release_ts: releaseIso || '',     // scheduled
    released_ts: releasedIso || '',

    // Source calendar tag
    source_cal: 'FMP',

    // Estimates
    consensus_value: (consensus === null ? '' : consensus),
    prev_revision:   (prevRev   === null ? '' : prevRev),

    // Actuals side (if present in this payload)
    released_value: (hasActual ? actualNum : ''),
    source_provider: sourceProvider,
    source_series_id: sourceSeriesId,
    transform: transform,
    release_status: releaseStatus,
    notes: notes,
    resolution_method: resolutionMethod,
    confidence_level: confidenceLevel
  };
}


/** ===== Writer (Upsert to Event) ===== **/

/**
 * Upsert normalized rows into Event using an in-memory fallback key:
 *   key = country + '|' + indicator_name + '|' + release_ts
 * Skips only if indicator_name or release_ts are missing.
 * Returns { fetched, appended, upserts, skipped, skipped_reasons }
 */
function _upsertEventsToEvent_(normRows) {
  var sh = getEventSheet();
  var headers = ensureEventHeaders_(sh); // adds any missing columns at end
  // Build case-insensitive column resolver
  function col(name) {
    var target = String(name).trim().toLowerCase();
    for (var c = 0; c < headers.length; c++) {
      if (String(headers[c]).trim().toLowerCase() === target) return c; // 0-based
    }
    return -1;
  }
  // Build header index map
  var idx = {};
  headers.forEach(function(h, i){ idx[h] = i; });

  // Read existing data (from row 2 down)
  var lastRow = sh.getLastRow();
  var lastCol = sh.getLastColumn();
  var body = [];
  if (lastRow > 1 && lastCol > 0) {
    body = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();
  }

  // Index existing rows by fallback key
  var existingByKey = {}; // key -> rowIndex (0-based within body)
  for (var r = 0; r < body.length; r++) {
    var row = body[r];
    var country = String(row[idx['country']] || '').toUpperCase();
    var indicator = String(row[idx['indicator_name']] || '');
    var releaseTs = String(row[idx['release_ts']] || '');
    if (indicator && releaseTs) {
      var k = country + '|' + indicator + '|' + releaseTs;
      existingByKey[k] = r;
    }
  }

  var appended = 0, upserts = 0, skipped = 0;
  var skipped_reasons = { missing_indicator_name: 0, missing_release_ts: 0 };

  var rowsToAppend = [];           // rows to append (as arrays in header order)
  var updates = [];                // {r, values[]} list for in-place updates

  // Prepare normalized rows in header order
  for (var i = 0; i < normRows.length; i++) {
    var n = normRows[i] || {};
    var indicatorName = String(n.indicator_name || '');
    var releaseTs = String(n.release_ts || '');
    if (!indicatorName) { skipped++; skipped_reasons.missing_indicator_name++; continue; }
    if (!releaseTs) { skipped++; skipped_reasons.missing_release_ts++; continue; }

    var country = String(n.country || '').toUpperCase();
    var key = country + '|' + indicatorName + '|' + releaseTs;

    // Build row array aligned to headers (case-insensitive targets)
    var arr = new Array(headers.length).fill('');

    // Core
    var c;
    if ((c = col('object'))         >= 0) arr[c] = 'econ_event';
    if ((c = col('country'))        >= 0) arr[c] = country;
    if ((c = col('indicator_name')) >= 0) arr[c] = indicatorName;
    if ((c = col('genre'))          >= 0) arr[c] = String(n.genre || '');
    if ((c = col('importance'))     >= 0) arr[c] = String(n.importance || '');

    // IDs (left blank; post-pass fills)
    if ((c = col('type'))     >= 0) arr[c] = String(n.type || '');
    if ((c = col('event_id')) >= 0) arr[c] = String(n.event_id || '');
    if ((c = col('batch_id')) >= 0) arr[c] = String(n.batch_id || '');

    // Timing + source
    if ((c = col('release_ts')) >= 0) arr[c] = String(n.release_ts || '');
    if ((c = col('source_cal')) >= 0) arr[c] = 'FMP';

    // Numeric (zero-safe)
    if ((c = col('consensus_value')) >= 0) {
      arr[c] = (n.consensus_value === '' || n.consensus_value === null || n.consensus_value === undefined)
        ? '' : Number(n.consensus_value);
    }
    if ((c = col('prev_revision')) >= 0) {
      arr[c] = (n.prev_revision === '' || n.prev_revision === null || n.prev_revision === undefined)
        ? '' : Number(n.prev_revision);
    }
    if ((c = col('released_value')) >= 0) {
      arr[c] = (n.released_value === '' || n.released_value === null || n.released_value === undefined)
        ? '' : Number(n.released_value);
    }

    // Released-side strings/timestamps
    if ((c = col('released_ts'))      >= 0) arr[c] = String(n.released_ts || '');
    if ((c = col('source_provider'))  >= 0) arr[c] = String(n.source_provider || '');
    if ((c = col('source_series_id')) >= 0) arr[c] = String(n.source_series_id || '');
    if ((c = col('transform'))        >= 0) arr[c] = String(n.transform || '');
    if ((c = col('release_status'))   >= 0) arr[c] = String(n.release_status || 'scheduled');
    if ((c = col('notes'))            >= 0) arr[c] = String(n.notes || '');
    if ((c = col('resolution_method')) >= 0) arr[c] = String(n.resolution_method || '');
    if ((c = col('confidence_level'))  >= 0) arr[c] = String(n.confidence_level || '');

    if (Object.prototype.hasOwnProperty.call(existingByKey, key)) {
      // Update in place
      var rindex = existingByKey[key];
      // Merge vs overwrite: we overwrite normalized columns, leave id fields untouched for now;
      // BUT our spec says event_id/batch_id/type are filled later by post-pass anyway.
      updates.push({ r: rindex, values: arr });
      upserts++;
    } else {
      rowsToAppend.push(arr);
      appended++;
    }
  }

  // Apply updates
  if (updates.length > 0) {
    // Batch update by writing the entire region back (simpler + consistent)
    // 1) Merge updates into `body`
    updates.forEach(function(u){
      body[u.r] = u.values;
    });
    // 2) Write back full body range once (if there were existing rows)
    if (body.length > 0) {
      sh.getRange(2, 1, body.length, headers.length).setValues(body);
    }
  }

  // Apply appends
  if (rowsToAppend.length > 0) {
    var startRow = sh.getLastRow() + 1;
    sh.getRange(startRow, 1, rowsToAppend.length, headers.length).setValues(rowsToAppend);
  }

  SpreadsheetApp.flush();

  // NEW: keep the Event sheet sorted by release_ts ascending (rows 2..last)
  try {
    var headers2 = ensureEventHeaders_(sh);
    var relIdx = headers2.indexOf('release_ts');
    if (relIdx >= 0) {
      var lastRow2 = sh.getLastRow();
      var lastCol2 = sh.getLastColumn();
      if (lastRow2 > 1 && lastCol2 > 0) {
        sh.getRange(2, 1, lastRow2 - 1, lastCol2).sort([{ column: relIdx + 1, ascending: true }]);
      }
    }
  } catch (e) {
    // don't block the run on a sort error
  }

  return {
    fetched: normRows.length,
    appended: appended,
    upserts: upserts,
    skipped: skipped,
    skipped_reasons: skipped_reasons
  };
}

/** ===== FMP fetch (upcoming) ===== **/

/**
 * Fetch upcoming FMP calendar for N days ahead.
 * - Requires CFG.FMP_API_KEY (or Script Property "FMP_API_KEY")
 * - Returns an array of raw rows (objects)
 *
 * You can filter by country/etc. in the URL if desired.
 */
function fmpFetchUpcoming(daysAhead) {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  if (!apiKey) throw new Error('Missing FMP API key. Set CFG.FMP_API_KEY or Script Property "FMP_API_KEY".');

  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  var days = Math.max(1, Number(daysAhead || 7));

  // FMP economic calendar endpoint (adjust if you use a different one)
    // Build base URL (attempt server-side country filter if provided)
  var from = _yyyy_mm_dd_(new Date());
  var to = _yyyy_mm_dd_(new Date(Date.now() + days*24*3600*1000));

  var url = base + '/economic_calendar'
          + '?from=' + from
          + '&to=' + to
          + '&apikey=' + encodeURIComponent(apiKey);

  // ↓ If configured, add a server-side country filter (FMP may accept this on stable/legacy).
  if (typeof CFG !== 'undefined' && CFG.FMP_COUNTRY && String(CFG.FMP_COUNTRY).trim() !== '') {
    url += '&country=' + encodeURIComponent(String(CFG.FMP_COUNTRY).trim());
  }

  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    throw new Error('FMP fetch failed: HTTP ' + res.getResponseCode() + ' — ' + res.getContentText());
  }
  var json = JSON.parse(res.getContentText() || '[]');
  if (!Array.isArray(json)) return [];

  return json; // raw rows
}

/** Helpers for fmpFetchUpcoming **/
function _yyyy_mm_dd_(d) {
  var y = d.getUTCFullYear();
  var m = String(d.getUTCMonth() + 1).padStart(2, '0');
  var dd = String(d.getUTCDate()).padStart(2, '0');
  return y + '-' + m + '-' + dd;
}
function _getScriptProp_(key) {
  try {
    return PropertiesService.getScriptProperties().getProperty(key);
  } catch (e) { return ''; }
}




function _inferGenreFromName_(name) {
  var s = String(name || '').toLowerCase();
  if (!s) return '';

  if (/(cpi|inflation|pce|deflator|ppi|core)/.test(s)) return 'Inflation';
  if (/(payroll|nfp|employment|jobless|claims|unemployment|participation|ahe|earnings|hours)/.test(s)) return 'Labor';
  if (/(gdp|nowcast)/.test(s)) return 'Growth';
  if (/(retail|sales|consum|umich|sentiment|confidence)/.test(s)) return 'Consumption';
  if (/(housing|mortgage|starts|permits|case[-\s]*shiller)/.test(s)) return 'Housing';
  if (/(manufactur|is[m|m]|factory|industrial production|capacity)/.test(s)) return 'Manufacturing';
  if (/(trade|inventor(y|ies)|wholesale)/.test(s)) return 'Trade';
  if (/(energy|eia|oil|gas|natural gas|stocks)/.test(s)) return 'Energy';
  if (/(budget|deficit|treasury|auction|bill|bond|balance sheet)/.test(s)) return 'Fiscal/Markets';
  return 'Other';
}


/** ===== Add explicit window support (from/to) 2025-10-15 13:00 ===== **/

/**
 * Fetch FMP economic calendar for an explicit UTC ISO window.
 * fromUtcIso / toUtcIso can be ISO strings or Date objects.
 * Returns raw JSON rows from FMP.
 */
function fmpFetchRangeUtc_(fromUtcIso, toUtcIso) {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  if (!apiKey) throw new Error('Missing FMP API key. Set CFG.FMP_API_KEY or Script Property "FMP_API_KEY".');

  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';

  var fromD = (fromUtcIso instanceof Date) ? fromUtcIso : new Date(String(fromUtcIso||''));
  var toD   = (toUtcIso   instanceof Date) ? toUtcIso   : new Date(String(toUtcIso||''));
  if (!fromD || !isFinite(fromD.getTime()) || !toD || !isFinite(toD.getTime())) {
    throw new Error('fmpFetchRangeUtc_: invalid from/to');
  }

  var from = _yyyy_mm_dd_(fromD);
  var to   = _yyyy_mm_dd_(toD);

  var url = base + '/economic_calendar'
          + '?from=' + from
          + '&to=' + to
          + (CFG && CFG.FMP_COUNTRY ? ('&country=' + encodeURIComponent(CFG.FMP_COUNTRY)) : '')
          + '&apikey=' + encodeURIComponent(apiKey);

  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    throw new Error('FMP fetch failed: HTTP ' + res.getResponseCode() + ' — ' + res.getContentText());
  }
  var json = JSON.parse(res.getContentText() || '[]');
  if (!Array.isArray(json)) return [];
  return json;
}

/**
 * Upsert events for an explicit UTC ISO window.
 * Mirrors runFmpUpcomingToEvent_ but uses fmpFetchRangeUtc_.
 * Returns the same shape as _upsertEventsToEvent_().
 */
function runFmpRangeToEvent_(fromUtcIso, toUtcIso) {
  var raw = fmpFetchRangeUtc_(fromUtcIso, toUtcIso);

  // Normalize
  var normAll = raw.map(normalizeFmpRow_);

  // Local country filter (always applied if configured)
  var norm = normAll.filter(function(r){
    if (!CFG || !CFG.COUNTRY_FILTER || !Array.isArray(CFG.COUNTRY_FILTER) || CFG.COUNTRY_FILTER.length === 0) {
      return true;
    }
    var c = String(r.country || '').toUpperCase();
    return CFG.COUNTRY_FILTER.map(function(x){return String(x).toUpperCase();}).indexOf(c) !== -1;
  });

  // Sort ascending by release_ts (ISO minute compare)
  norm.sort(function(a, b){
    var A = String(a.release_ts || ''), B = String(b.release_ts || '');
    if (A < B) return -1;
    if (A > B) return 1;
    return 0;
  });

  return _upsertEventsToEvent_(norm);
}

/** ===== FMP Event Catalog (for SeriesMap suggestion workflows) ===== **/

function _getOrCreateSheet_(name) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(name);
  if (sh) return sh;
  return ss.insertSheet(name);
}

function _ensureHeadersExact_(sh, headers) {
  var existing = sh.getLastColumn() ? sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0] : [];
  var isEmpty = !existing || existing.length === 0 || (existing.length === 1 && String(existing[0] || '') === '');
  if (isEmpty) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    return headers;
  }
  // If the sheet already exists, do not reorder; only append missing headers.
  var have = {};
  for (var i = 0; i < existing.length; i++) have[String(existing[i] || '').trim().toLowerCase()] = true;
  var toAppend = [];
  for (var j = 0; j < headers.length; j++) {
    var h = String(headers[j] || '').trim();
    if (!have[h.toLowerCase()]) toAppend.push(h);
  }
  if (toAppend.length) {
    sh.getRange(1, existing.length + 1, 1, toAppend.length).setValues([toAppend]);
  }
  return headers;
}

function _normalizeIndicatorForCatalog_(name) {
  var s = String(name || '').trim().toLowerCase();
  if (!s) return '';
  try { if (typeof stripDateSuffix_ === 'function') s = stripDateSuffix_(s); } catch (e) {}
  s = s.replace(/[%]/g, ' percent ');
  s = s.replace(/\b(preliminary|prelim|final|flash|advance|revised|estimate|est\.?)\b/g, ' ');
  s = s.replace(/[^a-z0-9]+/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

function _median_(arr) {
  if (!arr || !arr.length) return null;
  var a = arr.slice().sort(function(x, y){ return x - y; });
  var mid = Math.floor(a.length / 2);
  return (a.length % 2) ? a[mid] : (a[mid - 1] + a[mid]) / 2;
}

function _inferFreqFromMedianDays_(medianDays) {
  if (medianDays === null || medianDays === undefined) return '';
  var d = Number(medianDays);
  if (!isFinite(d) || d <= 0) return '';
  if (d >= 5 && d <= 9) return 'W';
  if (d >= 25 && d <= 35) return 'M';
  if (d >= 80 && d <= 100) return 'Q';
  if (d >= 330 && d <= 400) return 'A';
  return 'IRREGULAR';
}

function _filterFmpRowsToUtcWindow_(rows, fromDate, toDate) {
  var fromMs = fromDate.getTime();
  var toMs = toDate.getTime();
  return (rows || []).filter(function(row) {
    var iso = _parseReleaseTsUtcMinute_(_coalesce_(
      row && row.release_ts,
      row && row.datetime,
      row && row.date,
      row && row.time
    ));
    if (!iso) return false;
    var t = new Date(iso).getTime();
    return isFinite(t) && t >= fromMs && t <= toMs;
  });
}

function _filterFmpRowsForCatalog_(rows) {
  return (rows || []).filter(function(row) {
    var country = String(_coalesce_(row && row.country, row && row.ccy, row && row.region) || '').trim().toUpperCase();
    var currency = String(_pickFirst_(row || {}, ['currency', 'ccy']) || '').trim().toUpperCase();
    return country === 'US' && currency === 'USD';
  });
}

function _fmpRawRowKey_(row) {
  row = row || {};
  return [
    String(row.date || row.datetime || row.time || row.release_ts || ''),
    String(row.country || row.ccy || row.region || ''),
    String(row.event || row.indicator_name || row.title || row.name || row.category || ''),
    String(row.currency || ''),
    String(row.unit || '')
  ].join('|');
}

function fmpFetchRangeUtcChunked_(fromUtcIso, toUtcIso) {
  var fromDate = (fromUtcIso instanceof Date) ? new Date(fromUtcIso.getTime()) : new Date(String(fromUtcIso || ''));
  var toDate = (toUtcIso instanceof Date) ? new Date(toUtcIso.getTime()) : new Date(String(toUtcIso || ''));
  if (!isFinite(fromDate.getTime()) || !isFinite(toDate.getTime())) {
    throw new Error('fmpFetchRangeUtcChunked_: invalid from/to');
  }
  if (toDate.getTime() < fromDate.getTime()) return [];

  var out = [];
  var seen = Object.create(null);
  var cursor = new Date(Date.UTC(fromDate.getUTCFullYear(), fromDate.getUTCMonth(), fromDate.getUTCDate()));
  var endMs = toDate.getTime();

  while (cursor.getTime() <= endMs) {
    var chunkStart = new Date(cursor.getTime());
    var chunkEnd = new Date(Date.UTC(chunkStart.getUTCFullYear(), chunkStart.getUTCMonth() + 1, 0, 23, 59, 59));
    if (chunkEnd.getTime() > endMs) chunkEnd = new Date(endMs);

    var rows = fmpFetchRangeUtc_(chunkStart, chunkEnd);
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i] || {};
      var key = _fmpRawRowKey_(row);
      if (seen[key]) continue;
      seen[key] = true;
      out.push(row);
    }

    cursor = new Date(Date.UTC(chunkStart.getUTCFullYear(), chunkStart.getUTCMonth() + 1, 1));
  }

  return out;
}

/**
 * Build/update `FMP_EventCatalog` by fetching FMP economic calendar rows and aggregating.
 *
 * - Pulls a window of events from FMP (past + future) so we can capture recent history and upcoming schedule.
 * - Aggregates by (country, normalized indicator_name).
 * - Captures `unit` if present in the FMP payload (field assumed: `unit`).
 * - Computes simple cadence stats from release timestamps.
 *
 * This is an operator tool for SeriesMap suggestion workflows; it does not change Event rows.
 */
function buildFmpEventCatalog(lookbackDays, lookaheadDays) {
  var minFrom = new Date(Date.UTC(2025, 0, 1, 0, 0, 0));
  var maxTo   = new Date(Date.UTC(2025, 11, 31, 23, 59, 59));
  var from = new Date(minFrom.getTime());
  var to = new Date(maxTo.getTime());

  if (lookbackDays === 0 || lookbackDays) {
    var lb = Number(lookbackDays);
    if (isFinite(lb) && lb >= 1) {
      var now = new Date();
      from = new Date(now.getTime() - lb * 24 * 60 * 60 * 1000);
    }
  }
  if (lookaheadDays === 0 || lookaheadDays) {
    var lf = Number(lookaheadDays);
    if (isFinite(lf) && lf >= 0) {
      var now2 = new Date();
      to = new Date(now2.getTime() + lf * 24 * 60 * 60 * 1000);
    }
  }

  if (from.getTime() < minFrom.getTime()) from = minFrom;
  if (to.getTime() > maxTo.getTime()) to = maxTo;
  if (to.getTime() < from.getTime()) {
    to = new Date(from.getTime());
  }

  var rawAll = fmpFetchRangeUtcChunked_(from, to);
  var rawWindow = _filterFmpRowsToUtcWindow_(rawAll, from, to);
  var raw = _filterFmpRowsForCatalog_(rawWindow);
  var updatedIso = new Date().toISOString();

  var groups = Object.create(null); // key -> catalog aggregate
  for (var i = 0; i < raw.length; i++) {
    var row = raw[i] || {};
    var country = String(_coalesce_(row.country, row.ccy, row.region) || '').trim().toUpperCase();
    var name = String(_coalesce_(row.indicator_name, row.title, row.event, row.name, row.category) || '').trim();
    var norm = _normalizeIndicatorForCatalog_(name);
    if (!country || !norm) continue;

    var iso = _parseReleaseTsUtcMinute_(_coalesce_(row.release_ts, row.datetime, row.date, row.time));
    if (!iso) continue;

    var unit = String(_pickFirst_(row, ['unit', 'units', 'unitName', 'unit_name']) || '').trim();
    var currency = String(_pickFirst_(row, ['currency', 'ccy']) || '').trim().toUpperCase();
    var impact = String(_pickFirst_(row, ['impact', 'importance', 'importanceText', 'importance_level']) || '').trim();
    var actual = _parseNumber_(_pickFirst_(row, ['actual']));
    var estimate = _parseNumber_(_pickFirst_(row, ['estimate', 'consensus', 'forecast', 'expected']));
    var previous = _parseNumber_(_pickFirst_(row, ['previous', 'prev', 'prior']));
    var change = _parseNumber_(_pickFirst_(row, ['change']));
    var changePct = _parseNumber_(_pickFirst_(row, ['changePercentage', 'change_percentage']));

    var key = country + '|' + norm;
    if (!groups[key]) {
      groups[key] = {
        country: country,
        indicator_name_norm: norm,
        namesCount: Object.create(null),
        units: Object.create(null),
        currencies: Object.create(null),
        impacts: Object.create(null),
        dates: [],
        actualCount: 0,
        estimateCount: 0,
        previousCount: 0,
        changeCount: 0,
        changePctCount: 0,
        actualSum: 0,
        estimateSum: 0,
        previousSum: 0,
        changeSum: 0,
        changePctSum: 0
      };
    }
    groups[key].dates.push(iso);
    groups[key].namesCount[name] = (groups[key].namesCount[name] || 0) + 1;
    if (unit) groups[key].units[unit] = (groups[key].units[unit] || 0) + 1;
    if (currency) groups[key].currencies[currency] = (groups[key].currencies[currency] || 0) + 1;
    if (impact) groups[key].impacts[impact] = (groups[key].impacts[impact] || 0) + 1;
    if (actual !== null) { groups[key].actualCount++; groups[key].actualSum += actual; }
    if (estimate !== null) { groups[key].estimateCount++; groups[key].estimateSum += estimate; }
    if (previous !== null) { groups[key].previousCount++; groups[key].previousSum += previous; }
    if (change !== null) { groups[key].changeCount++; groups[key].changeSum += change; }
    if (changePct !== null) { groups[key].changePctCount++; groups[key].changePctSum += changePct; }
  }

  var rowsOut = [];
  var nowMs = (new Date()).getTime();
  var keys = Object.keys(groups);
  for (var k = 0; k < keys.length; k++) {
    var g = groups[keys[k]];
    var dates = g.dates.slice().sort(); // ISO UTC minutes sorts lexicographically
    if (!dates.length) continue;

    // Most common raw indicator name
    var sampleName = '';
    var bestCount = -1;
    var nameKeys = Object.keys(g.namesCount);
    for (var n = 0; n < nameKeys.length; n++) {
      var nm = nameKeys[n];
      var c = g.namesCount[nm] || 0;
      if (c > bestCount) { bestCount = c; sampleName = nm; }
    }

    // Unit: pick most common if present, and keep distinct examples
    var unitBest = '';
    var unitExamples = '';
    var unitKeys = Object.keys(g.units);
    if (unitKeys.length) {
      unitKeys.sort(function(a, b){ return (g.units[b] || 0) - (g.units[a] || 0); });
      unitBest = unitKeys[0];
      unitExamples = unitKeys.slice(0, 5).join(' | ');
    }

    var currencyBest = '';
    var currencyKeys = Object.keys(g.currencies);
    if (currencyKeys.length) {
      currencyKeys.sort(function(a, b){ return (g.currencies[b] || 0) - (g.currencies[a] || 0); });
      currencyBest = currencyKeys[0];
    }

    var impactBest = '';
    var impactExamples = '';
    var impactKeys = Object.keys(g.impacts);
    if (impactKeys.length) {
      impactKeys.sort(function(a, b){ return (g.impacts[b] || 0) - (g.impacts[a] || 0); });
      impactBest = impactKeys[0];
      impactExamples = impactKeys.slice(0, 5).join(' | ');
    }

    // Cadence stats (median gap in days)
    var gaps = [];
    for (var d = 1; d < dates.length; d++) {
      var prev = new Date(dates[d - 1]).getTime();
      var cur  = new Date(dates[d]).getTime();
      var gapDays = (cur - prev) / (24 * 60 * 60 * 1000);
      if (isFinite(gapDays) && gapDays > 0.5 && gapDays < 800) gaps.push(gapDays);
    }
    var medianGap = _median_(gaps);
    var freq = _inferFreqFromMedianDays_(medianGap);

    // Last and next release relative to now
    var lastRelease = '';
    var nextRelease = '';
    for (var z = dates.length - 1; z >= 0; z--) {
      if (new Date(dates[z]).getTime() <= nowMs) { lastRelease = dates[z]; break; }
    }
    for (var y = 0; y < dates.length; y++) {
      if (new Date(dates[y]).getTime() >= nowMs) { nextRelease = dates[y]; break; }
    }

    rowsOut.push([
      updatedIso,
      g.country,
      g.indicator_name_norm,
      sampleName,
      unitBest,
      unitExamples,
      freq,
      (medianGap === null ? '' : Number(medianGap.toFixed(2))),
      dates.length,
      lastRelease,
      nextRelease,
      currencyBest,
      impactBest,
      impactExamples,
      g.actualCount,
      g.estimateCount,
      g.previousCount,
      g.changeCount,
      g.changePctCount,
      g.actualCount ? Number((g.actualSum / g.actualCount).toFixed(6)) : '',
      g.estimateCount ? Number((g.estimateSum / g.estimateCount).toFixed(6)) : '',
      g.previousCount ? Number((g.previousSum / g.previousCount).toFixed(6)) : '',
      g.changeCount ? Number((g.changeSum / g.changeCount).toFixed(6)) : '',
      g.changePctCount ? Number((g.changePctSum / g.changePctCount).toFixed(6)) : '',
      dates[0]
    ]);
  }

  // Sort for stable output (country, indicator_name_norm)
  rowsOut.sort(function(a, b){
    if (a[1] !== b[1]) return String(a[1]).localeCompare(String(b[1]));
    return String(a[2]).localeCompare(String(b[2]));
  });

  var sh = _getOrCreateSheet_('FMP_EventCatalog');
  var headers = [
    'catalog_updated_ts',
    'country',
    'indicator_name_norm',
    'indicator_name_sample',
    'unit',
    'unit_examples',
    'inferred_frequency',
    'median_gap_days',
    'observations_count',
    'last_release_ts',
    'next_release_ts',
    'currency',
    'impact',
    'impact_examples',
    'actual_observations_count',
    'estimate_observations_count',
    'previous_observations_count',
    'change_observations_count',
    'change_percentage_observations_count',
    'avg_actual',
    'avg_estimate',
    'avg_previous',
    'avg_change',
    'avg_change_percentage',
    'first_release_ts'
  ];
  _ensureHeadersExact_(sh, headers);

  // Clear existing body (keep headers)
  var lastRow = sh.getLastRow();
  if (lastRow > 1) {
    sh.getRange(2, 1, lastRow - 1, sh.getLastColumn()).clearContent();
  }
  if (rowsOut.length) {
    sh.getRange(2, 1, rowsOut.length, headers.length).setValues(rowsOut);
  }
  SpreadsheetApp.flush();

  // Log (prefer the repo-standard appendLog shim when available).
  try {
    var payload = {
      fromUtcIso: from.toISOString(),
      toUtcIso: to.toISOString(),
      groups: rowsOut.length,
      rows_fetched: rawAll.length,
      rows_kept: rawWindow.length,
      rows_catalog_kept: raw.length,
      updated_ts: updatedIso
    };
    if (typeof appendLog === 'function') {
      appendLog('INFO', 'FMP EventCatalog: rebuilt', payload);
      try { if (typeof flushLogs_ === 'function') flushLogs_(); } catch (_) {}
    } else {
      Logger.log('[FMP EventCatalog] rebuilt ' + JSON.stringify(payload));
    }
  } catch (e) {}

  return { sheet: 'FMP_EventCatalog', groups: rowsOut.length, rows_fetched: rawAll.length, rows_kept: rawWindow.length, rows_catalog_kept: raw.length, fromUtcIso: from.toISOString(), toUtcIso: to.toISOString() };
}

// Backward-compat wrapper (older internal callers may reference the underscore name).
function buildFmpEventCatalog_(lookbackDays, lookaheadDays) {
  return buildFmpEventCatalog(lookbackDays, lookaheadDays);
}

/**
 * Write a small raw FMP economic-calendar sample for inspecting available payload fields.
 *
 * This is intentionally separate from Event/FMP_EventCatalog so schema exploration does
 * not mutate operational tabs.
 */
function inspectFmpEconomicCalendarSample(fromUtcIso, toUtcIso, rowLimit) {
  var from = fromUtcIso || '2025-01-01T00:00:00Z';
  var to = toUtcIso || '2025-12-31T23:59:59Z';
  var limit = Number(rowLimit || 25);
  if (!isFinite(limit) || limit < 1) limit = 25;
  if (limit > 200) limit = 200;

  var fromDate = new Date(String(from));
  var toDate = new Date(String(to));
  var rawAll = fmpFetchRangeUtcChunked_(from, to);
  var raw = _filterFmpRowsToUtcWindow_(rawAll, fromDate, toDate);
  var sample = raw.slice(0, limit);
  var keySet = {};
  for (var i = 0; i < sample.length; i++) {
    var row = sample[i] || {};
    Object.keys(row).forEach(function(k){ keySet[k] = true; });
  }
  var keys = Object.keys(keySet).sort();

  var sh = _getOrCreateSheet_('FMP_RawCalendarSample');
  var headers = ['sample_updated_ts', 'fromUtcIso', 'toUtcIso', 'row_number', 'raw_keys', 'raw_json'];
  _ensureHeadersExact_(sh, headers);

  var lastRow = sh.getLastRow();
  if (lastRow > 1) {
    sh.getRange(2, 1, lastRow - 1, sh.getLastColumn()).clearContent();
  }

  var updatedIso = new Date().toISOString();
  var rowsOut = [];
  for (var j = 0; j < sample.length; j++) {
    rowsOut.push([
      updatedIso,
      from,
      to,
      j + 1,
      keys.join(', '),
      JSON.stringify(sample[j] || {})
    ]);
  }
  if (rowsOut.length) {
    sh.getRange(2, 1, rowsOut.length, headers.length).setValues(rowsOut);
  }
  SpreadsheetApp.flush();

  try {
    var payload = { fromUtcIso: from, toUtcIso: to, rows_fetched: rawAll.length, rows_kept: raw.length, rows_written: rowsOut.length, raw_keys: keys };
    if (typeof appendLog === 'function') {
      appendLog('INFO', 'FMP RawCalendarSample: rebuilt', payload);
      try { if (typeof flushLogs_ === 'function') flushLogs_(); } catch (_) {}
    } else {
      Logger.log('[FMP RawCalendarSample] rebuilt ' + JSON.stringify(payload));
    }
  } catch (e) {}

  return { sheet: 'FMP_RawCalendarSample', rows_fetched: rawAll.length, rows_kept: raw.length, rows_written: rowsOut.length, raw_keys: keys };
}


/** ===== Orchestrator used by menu handlers (in Code.gs) ===== **/

/**
 * Core worker used by menu: fetch → normalize → upsert → return summary.
 * (Batching post-pass is called by the menu function in Code.gs after this returns.)
 */
function runFmpUpcomingToEvent_(daysAhead) {
  var raw = fmpFetchUpcoming(daysAhead);

  // Normalize first
  var normAll = raw.map(normalizeFmpRow_);

  // Enforce local country filter (if you added CFG.COUNTRY_FILTER earlier)
  var norm = normAll.filter(function(r){
    if (!CFG || !CFG.COUNTRY_FILTER || !Array.isArray(CFG.COUNTRY_FILTER) || CFG.COUNTRY_FILTER.length === 0) {
      return true;
    }
    var c = String(r.country || '').toUpperCase();
    return CFG.COUNTRY_FILTER.map(function(x){return String(x).toUpperCase();}).indexOf(c) !== -1;
  });

  // NEW: sort by release_ts ascending (ISO minutes sort lexicographically)
  norm.sort(function(a, b){
    var A = String(a.release_ts || ''), B = String(b.release_ts || '');
    if (A < B) return -1;
    if (A > B) return 1;
    return 0;
  });
  return _upsertEventsToEvent_(norm);
}
