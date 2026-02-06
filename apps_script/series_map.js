/*********************************************************
 * series_map.gs (PreSignal v1.3.x)
 *
 * Responsibilities
 *  - Load SeriesMap tab (mapping rules)
 *  - Resolve provider/series/transform for an Event row
 *  - Maintain SeriesMap_Suggestions (self-healing suggestions)
 *  - Centralize rounding/precision policy
 *  - Reference period parsing helper (used by backfill)
 *
 * Notes
 *  - Event sheet is canonical (not RawCalendar).
 *  - Menu entrypoint expects buildSeriesMapSuggestionsUsingWindow_().
 **********************************************************/

function _loadSeriesMap_() {
return loadSeriesMap();
}

// --- SeriesMap strict policy (v1.3-tight) ---
var SERIESMAP_POLICY = {
  requireNumericProvider: true,
  requireNumericFreq: true,
  defaultIrregularForUnknown: true,
  forceFREDMoMTransform: true,
  forceWeeklyDiffForChange: true,
  forceFREDSeasonalSA: true
};

// -----------------------------------------------------------------------------
// Small utilities
// -----------------------------------------------------------------------------

function _nowIso_() {
  return _isoMinuteZ_(new Date());
}

function addHoursIso_(isoZ, hours) {
  var d = new Date(String(isoZ || ''));
  if (!isFinite(d)) d = new Date();
  d = new Date(d.getTime() + Number(hours || 0) * 3600 * 1000);
  return _isoMinuteZ_(d);
}

function _isoMinuteZ_(d) {
  var dt = (d instanceof Date) ? d : new Date(d);
  if (!isFinite(dt)) dt = new Date();
  dt = new Date(Date.UTC(
    dt.getUTCFullYear(),
    dt.getUTCMonth(),
    dt.getUTCDate(),
    dt.getUTCHours(),
    dt.getUTCMinutes(),
    0,
    0
  ));
  return dt.toISOString().replace('.000Z', 'Z');
}

function stripDateSuffix_(s) {
  // Remove trailing fragments like "(Oct/04)", "(Jan)", "(Q1)", "(Dec preliminary)" etc.
  var x = String(s || '').trim();
  // common: anything in parentheses at end
  x = x.replace(/\s*\([^)]*\)\s*$/, '').trim();
  // extra: trailing " - Oct" kind of stuff can be handled upstream if needed
  return x;
}

function escapeRegex_(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function _normalizePatternText_(pattern) {
var p = String(pattern || '');


// Trim and remove invisible unicode spaces (common copy/paste artifacts)
p = p.replace(/[\u200B-\u200D\uFEFF]/g, '').trim(); // zero-width + BOM


// Sheets sometimes stores leading apostrophe to force "text"
if (p.charAt(0) === "'") p = p.slice(1).trim();


// Remove wrapping quotes if present
if ((p.charAt(0) === '"' && p.charAt(p.length - 1) === '"') ||
(p.charAt(0) === "'" && p.charAt(p.length - 1) === "'")) {
p = p.slice(1, -1).trim();
}


return p;
}


function _isRegexPattern_(pattern) {
var p = _normalizePatternText_(pattern);
return /^\/.*\/[gimsuy]*$/.test(p);
}


function _compilePattern_(pattern) {
var p = _normalizePatternText_(pattern);
if (!p) return null;


if (_isRegexPattern_(p)) {
var lastSlash = p.lastIndexOf('/');
var body = p.slice(1, lastSlash);
var flags = p.slice(lastSlash + 1) || 'i';
if (flags.indexOf('i') < 0) flags += 'i';
return { kind: 'regex', re: new RegExp(body, flags), raw: p };
}


return { kind: 'text', text: p.toLowerCase(), raw: p };
}

// -----------------------------------------------------------------------------
// SeriesMap: load + resolve
// -----------------------------------------------------------------------------

var SERIES_MAP = {
  SHEET: 'SeriesMap',
  COLS: [
    'country',
    'indicator_name_pattern',
    'provider',
    'series_id',
    'freq',
    'unit_type',
    'transform',
    'notes'
  ]
};

function loadSeriesMap() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(SERIES_MAP.SHEET);
  if (!sh) return [];

  var rng = sh.getDataRange().getValues();
  if (!rng || rng.length < 2) return [];

  var headers = rng[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;

  function col(name) {
    var c = idx[String(name).toLowerCase()];
    return (typeof c === 'number') ? c : -1;
  }

  var cCountry = col('country');
  var cPattern = col('indicator_name_pattern');
  var cProvider = col('provider');
  var cSeriesId = col('series_id');
  var cFreq = col('freq');
  var cUnit = col('unit_type');
  var cTransform = col('transform');
  var cNotes = col('notes');

  var out = [];
  for (var r = 1; r < rng.length; r++) {
    var row = rng[r];
    var country = (cCountry >= 0) ? String(row[cCountry] || '').trim().toUpperCase() : '';
    var pattern = (cPattern >= 0) ? String(row[cPattern] || '').trim() : '';
    var provider = (cProvider >= 0) ? String(row[cProvider] || '').trim() : '';
    var seriesId = (cSeriesId >= 0) ? String(row[cSeriesId] || '').trim() : '';
    var freq = (cFreq >= 0) ? String(row[cFreq] || '').trim().toUpperCase() : '';
    var unitType = (cUnit >= 0) ? String(row[cUnit] || '').trim() : '';
    var transform = (cTransform >= 0) ? String(row[cTransform] || '').trim() : '';
    var notes = (cNotes >= 0) ? String(row[cNotes] || '').trim() : '';

    if (!country || !pattern || !provider) continue;

    // Keep FILTER rows too (resolver will skip them)
    var compiled = _compilePattern_(pattern);

    out.push({
      country: country,
      pattern: pattern,
      compiled: compiled,
      provider: provider,
      series_id: seriesId,
      freq: freq || '',
      unit_type: unitType || '',
      transform: transform || '',
      notes: notes || ''
    });
  }

  return out;
}

/**
 * Resolve SeriesMap rule for an Event:
 *   ev.country, ev.indicator_name
 *
 * Matching behavior:
 *  - country must match
 *  - indicator_name normalized by stripping trailing date suffix
 *  - pattern supports:
 *      1) /regex/flags
 *      2) substring match (case-insensitive)
 *  - chooses "best" match by:
 *      regex > text, then longer pattern length
 *  - rows with provider='FILTER' are skipped
 */
function resolveSeriesForEvent(ev, seriesMap) {
  var event = ev; // alias: some code below expects `event`
  var ctry = String((ev && ev.country) || '').trim().toUpperCase();
  if (!ctry) return null;

  var nameRaw = String((ev && ev.indicator_name) || '').trim();
  if (!nameRaw) return null;

  var rawName =
    (event && event.indicator_name) ? event.indicator_name :
    (event && event.indicatorName) ? event.indicatorName :
    (event && event.indicator) ? event.indicator :
    '';

    var name = stripDateSuffix_(rawName).toLowerCase();

  var map = seriesMap;
  if (!map || !Array.isArray(map)) map = loadSeriesMap();

  var best = null;
  var bestScore = -1;

  for (var i = 0; i < map.length; i++) {
    var row = map[i];
    if (!row || row.country !== ctry) continue;

    // skip FILTER
    var prov = String(row.provider || '').trim().toUpperCase();
    if (prov === 'FILTER') continue;

    var compiled = row.compiled || _compilePattern_(row.pattern);
    if (!compiled) continue;

    var hit = false;
    var score = 0;

    if (compiled.kind === 'regex') {
      compiled.re.lastIndex = 0; // safety if regex ever has 'g' flag
      hit = compiled.re.test(name);
      if (hit) score = 2000 + String(row.pattern || '').length;
    } else {
      var pat = String(compiled.text || '').toLowerCase();
      hit = (pat && name.indexOf(pat) >= 0);
      if (hit) score = 1000 + String(row.pattern || '').length;
    }

    if (hit && score > bestScore) {
      bestScore = score;
      best = row;
    }
  }

  // must have series_id for actuals
  if (best && best.provider && best.series_id) return best;
  return null;
}

// -----------------------------------------------------------------------------
// Rounding policy
// -----------------------------------------------------------------------------

function roundByUnit(value, unitType, transform) {
  var v = Number(value);
  if (!isFinite(v)) return null;

  var u = String(unitType || '').trim().toLowerCase();
  var t = String(transform || '').trim().toLowerCase();

  // Heuristic defaults
  var dp = 2;

  // Unit-based precision
  if (/percent_1dp/.test(u)) dp = 1;
  else if (/percent_2dp/.test(u)) dp = 2;
  else if (/index_1dp/.test(u)) dp = 1;
  else if (/thousands_0dp/.test(u)) dp = 0;
  else if (/count_0dp/.test(u)) dp = 0;
  else if (/raw/.test(u)) dp = 2;

  // Transform may imply percent-ish display
  if (dp === 2 && (t === 'mom' || t === 'yoy' || /pct/.test(t))) dp = 1;

  return _round_(v, dp);
}

function _round_(v, dp) {
  var p = Math.pow(10, Number(dp || 0));
  return Math.round(v * p) / p;
}

// -----------------------------------------------------------------------------
// SeriesMap Suggestions (self-healing)
// -----------------------------------------------------------------------------

function _ensureSuggestionsSheet_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName('SeriesMap_Suggestions') || ss.insertSheet('SeriesMap_Suggestions');

  var baseHeaders = [
    'country','indicator_name_pattern','provider','series_id',
    'freq','unit_type','transform','seasonal_adjustment',
    'precision_dp','lag_rule','notes','created_ts'
  ];

  var candHeaders = [
    'cand_1_provider','cand_1_series_id','cand_1_title','cand_1_score','cand_1_freq',
    'cand_2_provider','cand_2_series_id','cand_2_title','cand_2_score','cand_2_freq',
    'cand_3_provider','cand_3_series_id','cand_3_title','cand_3_score','cand_3_freq'
  ];

  if (sh.getLastRow() === 0) {
    sh.appendRow(baseHeaders.concat(candHeaders));
    return sh;
  }

  // Ensure headers exist (append missing to the right, do not reorder)
  var lastCol = Math.max(1, sh.getLastColumn());
  var headerRow = sh.getRange(1, 1, 1, lastCol).getValues()[0];
  var have = {};
  for (var i = 0; i < headerRow.length; i++) have[String(headerRow[i] || '').trim()] = true;

  var toAdd = [];
  for (var j = 0; j < candHeaders.length; j++) {
    if (!have[candHeaders[j]]) toAdd.push(candHeaders[j]);
  }
  if (toAdd.length) {
    sh.getRange(1, lastCol + 1, 1, toAdd.length).setValues([toAdd]);
  }

  return sh;
}

function appendSeriesMapSuggestion_(country, indicatorName, releaseTs) {
  country = String(country || '').trim().toUpperCase();
  var name = String(indicatorName || '').trim();
  if (!country || !name) return;

  var sh = _ensureSuggestionsSheet_();
  var keyCountry = country;
  var keyPattern = buildDefaultPattern_(name);

  // De-dupe (country|pattern) in suggestions sheet
  var last = sh.getLastRow();
  if (last >= 2) {
    var vals = sh.getRange(2, 1, last - 1, 2).getValues(); // country + pattern
    for (var i = 0; i < vals.length; i++) {
      var c = String(vals[i][0] || '').trim().toUpperCase();
      var p = String(vals[i][1] || '').trim();
      if (c === keyCountry && p === keyPattern) return;
    }
  }

  // Use name heuristics (minimal, safe)
  var guessed = suggestFromName_(country, name, null);
  guessed = _fillSeriesMapDefaults_(guessed);

  // Option C: FMP calendar auto-suggest (stores candidates in notes; may auto-fill on high confidence)
  guessed = _augmentSuggestionWithFmp_(guessed, country, name, releaseTs);

  sh.appendRow(guessed);

  // Optional logging
  if (typeof appendLog === 'function') {
    appendLog('info', 'SeriesMap suggestion appended', JSON.stringify({
      module: 'series_map',
      step: 'append_suggestion',
      country: country,
      indicator_name: name,
      pattern: guessed[1],
      provider: guessed[2] || '',
      series_id: guessed[3] || ''
    }));
  }
}

function promoteSelectedSeriesMapSuggestions_() {
  var ss = SpreadsheetApp.getActive();
  var sug = ss.getSheetByName('SeriesMap_Suggestions');
  var map = ss.getSheetByName('SeriesMap');

  if (!sug) throw new Error('SeriesMap_Suggestions sheet not found');
  if (!map) throw new Error('SeriesMap sheet not found');

  // Must run while user has a selection
  var range = ss.getActiveRange();
  if (!range) return { promoted: 0, skipped: 0, reason: 'no_active_range' };
  if (range.getSheet().getName() !== 'SeriesMap_Suggestions') {
    return { promoted: 0, skipped: 0, reason: 'active_range_not_on_suggestions' };
  }

  var r0 = range.getRow();
  var nRows = range.getNumRows();

  // Do not allow header-only selection
  if (r0 === 1) {
    if (nRows <= 1) return { promoted: 0, skipped: 0, reason: 'header_selected' };
    r0 = 2;
    nRows = nRows - 1;
  }

  // Read suggestion headers (expects your 12-col schema but handles extra cols)
  var sugHeaders = sug.getRange(1, 1, 1, sug.getLastColumn()).getValues()[0]
    .map(function(h){ return String(h || '').trim().toLowerCase(); });

  function sugCol(name) {
    var idx = sugHeaders.indexOf(String(name).toLowerCase());
    return idx >= 0 ? (idx + 1) : -1; // 1-based
  }

  var cCountry = sugCol('country');
  var cPattern = sugCol('indicator_name_pattern');
  var cProvider = sugCol('provider');
  var cSeries = sugCol('series_id');
  var cFreq = sugCol('freq');
  var cUnit = sugCol('unit_type');
  var cTransform = sugCol('transform');
  var cNotes = sugCol('notes');

  // minimal required to be promotable
  if (cCountry < 0 || cPattern < 0 || cProvider < 0 || cSeries < 0) {
    throw new Error('SeriesMap_Suggestions missing required columns (country, indicator_name_pattern, provider, series_id)');
  }

  // Ensure SeriesMap has required headers (append missing at end, never reorder)
  var mapHeaders = map.getRange(1, 1, 1, map.getLastColumn()).getValues()[0]
    .map(function(h){ return String(h || '').trim(); });

  function ensureMapHeader_(name) {
    for (var i = 0; i < mapHeaders.length; i++) {
      if (String(mapHeaders[i]).trim().toLowerCase() === String(name).toLowerCase()) return (i + 1);
    }
    // append
    mapHeaders.push(name);
    map.getRange(1, mapHeaders.length).setValue(name);
    return mapHeaders.length;
  }

  var mCountry = ensureMapHeader_('country');
  var mPattern = ensureMapHeader_('indicator_name_pattern');
  var mProvider = ensureMapHeader_('provider');
  var mSeries = ensureMapHeader_('series_id');
  var mFreq = ensureMapHeader_('freq');
  var mUnit = ensureMapHeader_('unit_type');
  var mTransform = ensureMapHeader_('transform');
  var mNotes = ensureMapHeader_('notes');

  // Load existing map keys for de-dupe
  var existing = {};
  var lastMapRow = map.getLastRow();
  if (lastMapRow >= 2) {
    var mapVals = map.getRange(2, 1, lastMapRow - 1, map.getLastColumn()).getValues();
    // Build header index for map
    var mapIdx = {};
    for (var h = 0; h < mapHeaders.length; h++) mapIdx[String(mapHeaders[h]).trim().toLowerCase()] = h;

    function mv(row, colName) {
      var j = mapIdx[String(colName).toLowerCase()];
      return (typeof j === 'number') ? row[j] : '';
    }

    for (var i2 = 0; i2 < mapVals.length; i2++) {
      var row2 = mapVals[i2];
      var k = [
        String(mv(row2, 'country') || '').trim().toUpperCase(),
        String(mv(row2, 'indicator_name_pattern') || '').trim(),
        String(mv(row2, 'provider') || '').trim().toUpperCase(),
        String(mv(row2, 'series_id') || '').trim(),
        String(mv(row2, 'transform') || '').trim().toLowerCase()
      ].join('|');
      if (k !== '||||') existing[k] = true;
    }
  }

  // Pull selected suggestion rows (read full row width)
  var values = sug.getRange(r0, 1, nRows, sug.getLastColumn()).getValues();

  var toAppend = [];
  var promoted = 0;
  var skipped = 0;

  for (var r = 0; r < values.length; r++) {
    var row = values[r];

    var country = String(row[cCountry - 1] || '').trim().toUpperCase();
    var pattern = String(row[cPattern - 1] || '').trim();
    var provider = String(row[cProvider - 1] || '').trim();
    var seriesId = String(row[cSeries - 1] || '').trim();

    // Optional fields
    var freq = (cFreq > 0) ? String(row[cFreq - 1] || '').trim() : '';
    var unitType = (cUnit > 0) ? String(row[cUnit - 1] || '').trim() : '';
    var transform = (cTransform > 0) ? String(row[cTransform - 1] || '').trim() : '';
    var notes = (cNotes > 0) ? String(row[cNotes - 1] || '').trim() : '';

    // Guard: require provider + series_id (FILTER not allowed as promotion)
    if (!country || !pattern || !provider || !seriesId) { skipped++; continue; }
    if (String(provider).trim().toUpperCase() === 'FILTER') { skipped++; continue; }

    var key = [country, pattern, String(provider).trim().toUpperCase(), seriesId, String(transform || '').trim().toLowerCase()].join('|');
    if (existing[key]) { skipped++; continue; }
    existing[key] = true;

    // Build a SeriesMap row aligned to current SeriesMap headers
    var outRow = [];
    outRow[mCountry - 1] = country;
    outRow[mPattern - 1] = pattern;
    outRow[mProvider - 1] = provider;
    outRow[mSeries - 1] = seriesId;
    outRow[mFreq - 1] = freq;
    outRow[mUnit - 1] = unitType;
    outRow[mTransform - 1] = transform;
    outRow[mNotes - 1] = notes;

    toAppend.push(outRow);
  }

  if (toAppend.length > 0) {
    // Normalize row width to map.getLastColumn()
    var width = map.getLastColumn();
    for (var k2 = 0; k2 < toAppend.length; k2++) {
      var rr = toAppend[k2];
      for (var c = 0; c < width; c++) if (typeof rr[c] === 'undefined') rr[c] = '';
    }

    map.getRange(map.getLastRow() + 1, 1, toAppend.length, width).setValues(toAppend);
    promoted = toAppend.length;
  }

  if (typeof appendLog === 'function') {
    appendLog('info', 'SeriesMap suggestions promoted', JSON.stringify({
      module: 'series_map',
      step: 'promote_selected',
      promoted: promoted,
      skipped: skipped
    }));
  }

  return { promoted: promoted, skipped: skipped, reason: 'ok' };
}


function buildDefaultPattern_(indicatorName) {
  return stripDateSuffix_(String(indicatorName || '').trim());
}

/**
 * Build suggestions for Event rows in [startIso, endIso)
 * startIso/endIso must be ISO-8601 Z and minute precision (recommended).
 */
function buildSeriesMapSuggestionsWindow_(startIso, endIso) {
  var ss = SpreadsheetApp.getActive();
  var shEvent = ss.getSheetByName('Event');
  if (!shEvent) throw new Error('Event sheet not found');

  var start = String(startIso || '').trim();
  var end = String(endIso || '').trim();
  if (!start || !end) throw new Error('buildSeriesMapSuggestionsWindow_ requires (startIso, endIso)');

  var rng = shEvent.getDataRange().getValues();
  if (!rng || rng.length < 2) return { scanned: 0, built: 0, skipped: 0 };

  var headers = rng[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[headers[i]] = i;

  function col(name) {
    var c = idx[String(name).toLowerCase()];
    return (typeof c === 'number') ? c : -1;
  }

  var cCountry = col('country');
  var cName = col('indicator_name');
  var cTs = col('release_ts');

  if (cCountry < 0 || cName < 0 || cTs < 0) {
    throw new Error('Event missing required headers: country, indicator_name, release_ts');
  }

  var seen = {};
  var scanned = 0, built = 0, skipped = 0;

  for (var r = 1; r < rng.length; r++) {
    var row = rng[r];
    var ts = String(row[cTs] || '').trim();
    if (!ts) continue;

    // ISO string compare works for Z timestamps
    if (!(ts >= start && ts < end)) continue;

    scanned++;

    var country = String(row[cCountry] || '').trim().toUpperCase();
    var name = String(row[cName] || '').trim();
    if (!country || !name) { skipped++; continue; }

    var key = country + '|' + name;
    if (seen[key]) { skipped++; continue; }
    seen[key] = true;

    try {
      appendSeriesMapSuggestion_(country, name, ts);
      built++;
    } catch (e) {
      skipped++;
      if (typeof appendLog === 'function') {
        appendLog('warn', 'SeriesMap suggestion build failed (row)', JSON.stringify({
          module: 'series_map',
          step: 'build_window',
          country: country,
          indicator_name: name,
          error: String(e && e.message || e)
        }));
      }
    }
  }

  if (typeof appendLog === 'function') {
    appendLog('info', 'SeriesMap suggestions built (window)', JSON.stringify({
      module: 'series_map',
      step: 'build_window_done',
      startIso: start,
      endIso: end,
      scanned: scanned,
      built: built,
      skipped: skipped
    }));
  }

  return { scanned: scanned, built: built, skipped: skipped, startIso: start, endIso: end };
}

/**
 * Canonical menu entrypoint (Code.gs calls this)
 *
 * Window resolution:
 *  - If resolveWindow_ exists and is enabled: use it
 *  - Else default: NOW .. NOW+72h (UTC)  ← focuses on upcoming events
 */
function buildSeriesMapSuggestionsUsingWindow_() {
  var fromIso = null, toIso = null, note = '';

  var win = (typeof resolveWindow_ === 'function') ? resolveWindow_('seriesmap_suggest') : null;
  if (win && win.windowEnabled && win.fromUtcIso && win.toUtcIso) {
    fromIso = String(win.fromUtcIso);
    toIso = String(win.toUtcIso);
    note = win.note || 'cfg_window';
  } else {
    var nowIso = _nowIso_();
    fromIso = nowIso;
    toIso = addHoursIso_(nowIso, 72);
    note = 'fallback:next72h';
  }

  var res = buildSeriesMapSuggestionsWindow_(fromIso, toIso);

  SpreadsheetApp.getActive().toast(
    'SeriesMap suggestions: scanned=' + res.scanned + ', built=' + res.built + ', skipped=' + res.skipped + ' [' + note + ']',
    'SeriesMap',
    8
  );

  res.note = note;
  return res;
}

// -----------------------------------------------------------------------------
// Legacy wrappers (kept for operators / compatibility)
// -----------------------------------------------------------------------------

function buildSeriesMapSuggestionsLast31d_() {
  var nowIso = _nowIso_();
  var fromIso = addHoursIso_(nowIso, -24 * 31);
  return buildSeriesMapSuggestionsWindow_(fromIso, nowIso);
}

function buildSeriesMapSuggestions3moFixed_() {
  var nowIso = _nowIso_();
  var fromIso = addHoursIso_(nowIso, -24 * 90);
  return buildSeriesMapSuggestionsWindow_(fromIso, nowIso);
}

function buildSeriesMapSuggestionsLastYear_(opts) {
  var nowIso = _nowIso_();
  var fromIso = addHoursIso_(nowIso, -24 * 365);
  return buildSeriesMapSuggestionsWindow_(fromIso, nowIso);
}

/**
 * DEPRECATED: older Raw-based builder. v1.3 uses Event as canonical.
 * Kept as alias to avoid breaking older calls.
 */
function buildSeriesMapSuggestions31d_() {
  return buildSeriesMapSuggestionsLast31d_();
}


// -----------------------------------------------------------------------------
// FMP calendar auto-suggest (Option C)
// - Suggests exact FMP `event` strings to use with series_id = "calendar:<event>"
// - Stores top candidates into notes, and can auto-fill provider/series_id on high confidence
// -----------------------------------------------------------------------------

function _fmpGetBaseAndKey_() {
  var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY :
               (typeof _getScriptProp_ === 'function' ? _getScriptProp_('FMP_API_KEY') : '');
  var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  return { base: base, apiKey: apiKey };
}

function _fmpYmdUtc_(d) {
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
}

function _fmpFetchCalendarAround_(releaseTs) {
  try {
    var cfg = _fmpGetBaseAndKey_();
    if (!cfg.apiKey) return [];

    var ref = null;
    if (releaseTs instanceof Date) ref = releaseTs;
    else if (releaseTs) ref = new Date(releaseTs);
    else ref = new Date();

    // ±1 day window around the release date (UTC date)
    var d0 = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), ref.getUTCDate() - 1));
    var d1 = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), ref.getUTCDate() + 1));

    var url = cfg.base + '/economic_calendar'
      + '?from=' + _fmpYmdUtc_(d0)
      + '&to='   + _fmpYmdUtc_(d1)
      + '&apikey=' + encodeURIComponent(cfg.apiKey);

    // Optional server-side country filter if configured
    if (typeof CFG !== 'undefined' && CFG.FMP_COUNTRY && String(CFG.FMP_COUNTRY).trim() !== '') {
      url += '&country=' + encodeURIComponent(String(CFG.FMP_COUNTRY).trim());
    }

    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true, validateHttpsCertificates: true });
    var code = resp && resp.getResponseCode ? resp.getResponseCode() : 0;
    if (code < 200 || code >= 300) return [];

    var json = JSON.parse(resp.getContentText() || '[]');
    return Array.isArray(json) ? json : [];
  } catch (e) {
    return [];
  }
}

function _tok_(s) {
  s = String(s || '').toLowerCase();
  s = s.replace(/\(.*?\)/g, ' ');
  s = s.replace(/[^a-z0-9]+/g, ' ');
  s = s.replace(/\b(preliminary|final|flash|advance|revised|estimate|est\.?|mom|yoy|qoq|sa|nsa)\b/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  if (!s) return [];
  return s.split(' ');
}

function _jaccard_(a, b) {
  var A = {};
  for (var i = 0; i < a.length; i++) A[a[i]] = 1;
  var inter = 0, uni = 0;
  for (var k in A) if (A.hasOwnProperty(k)) uni++;
  var B = {};
  for (var j = 0; j < b.length; j++) B[b[j]] = 1;
  for (var k2 in B) if (B.hasOwnProperty(k2)) {
    if (!A[k2]) uni++;
    else inter++;
  }
  return uni ? (inter / uni) : 0;
}

function _fmpSuggestCalendarCandidates_(country, indicatorName, releaseTs) {
  var target = stripDateSuffix_(String(indicatorName || '').trim());
  var targetTok = _tok_(target);
  if (!targetTok.length) return [];

  var rows = _fmpFetchCalendarAround_(releaseTs);
  if (!rows.length) return [];

  // Optional country match (best-effort; FMP may use 'country' or 'countryCode')
  var ctry = String(country || '').trim().toUpperCase();

  var scored = [];
  for (var i = 0; i < rows.length; i++) {
    var ev = String(rows[i].event || '').trim();
    if (!ev) continue;

    var rowC = String(rows[i].country || rows[i].countryCode || '').trim().toUpperCase();
    if (ctry && rowC && rowC !== ctry) continue;

    var score = _jaccard_(targetTok, _tok_(ev));
    if (score <= 0) continue;

    scored.push({ event: ev, score: score });
  }

  scored.sort(function(a, b){ return b.score - a.score; });
  return scored.slice(0, 3);
}

function _augmentSuggestionWithFmp_(row, country, indicatorName, releaseTs) {
  // row is [country, pattern, provider, series_id, freq, unit_type, transform, seasonal, precision, lag, notes, created_ts, ...cand slots...]
  var notes = String(row[10] || '').trim();

  var cands = _fmpSuggestCalendarCandidates_(country, indicatorName, releaseTs);
  if (!cands.length) return row;

  // Also keep the notes breadcrumb (optional)
  var candStr = cands.map(function(x){
    return 'calendar:' + x.event + ' (' + (Math.round(x.score * 100) / 100) + ')';
  }).join(' | ');
  notes = (notes ? notes + ' | ' : '') + 'FMP_CANDIDATES: ' + candStr;
  row[10] = notes;

  // Write candidates into the first available empty cand_* slots (do NOT touch provider/series_id)
  // Cand slots start after created_ts, i.e. at row[12] if you appended headers as instructed.
  function _findNextCandSlot_() {
    // POLICY: FMP must NOT write to cand_1 (reserved for FRED primary).
    // Use cand_2 first, then cand_3.
    var order = [2, 3];
    for (var k = 0; k < order.length; k++) {
      var s = order[k];
      var sidIdx = 12 + (s - 1) * 5 + 1; // cand_n_series_id index
      var existing = String(row[sidIdx] || '').trim();
      if (!existing) return s;
    }
    return 0;
  }

  function _writeCand_(slot, ev, score) {
    var base = 12 + (slot - 1) * 5;
    row[base + 0] = 'FMP';                 // cand_n_provider
    row[base + 1] = 'calendar:' + ev;      // cand_n_series_id
    row[base + 2] = ev;                    // cand_n_title
    row[base + 3] = score;                 // cand_n_score
    row[base + 4] = '';                    // cand_n_freq (calendar has no stable freq)
  }

  for (var i = 0; i < Math.min(3, cands.length); i++) {
    var slot = _findNextCandSlot_();
    if (!slot) break;
    _writeCand_(slot, cands[i].event, cands[i].score);
  }

  return row;
}


// -----------------------------------------------------------------------------
// Suggestion heuristics (minimal + safe)
// -----------------------------------------------------------------------------

function suggestFromName_(country, indicatorName, known) {
  var c = String(country || '').trim().toUpperCase();
  var name = String(indicatorName || '').trim();

  // known: {provider, series_id, freq, unit_type, transform, ...}
  var provider = known && known.provider ? String(known.provider) : '';
  var seriesId = known && known.series_id ? String(known.series_id) : '';

  var freq = _guessFreqFromName_(name);
  var unitAndTransform = _guessUnitAndTransform_(name);

  var unitType = (known && known.unit_type) ? String(known.unit_type) : unitAndTransform.unit_type;
  var transform = (known && known.transform) ? String(known.transform) : unitAndTransform.transform;

  var precisionDp = _guessPrecisionDp_(unitType, transform);

  return [
    c,
    buildDefaultPattern_(name),
    provider,
    seriesId,
    freq,
    unitType,
    transform,
    '',                 // seasonal_adjustment
    precisionDp,
    '',                 // lag_rule
    provider && seriesId ? '' : 'REVIEW: missing provider/series_id',
    _nowIso_()
  ];
}

function _fillSeriesMapDefaults_(row) {
  // row is [country, pattern, provider, series_id, freq, unit_type, transform, seasonal, precision, lag, notes, created_ts]
  var provider = String(row[2] || '').trim();
  var seriesId = String(row[3] || '').trim();
  var freq = String(row[4] || '').trim().toUpperCase();
  var unitType = String(row[5] || '').trim();
  var transform = String(row[6] || '').trim();

  if (!freq && SERIESMAP_POLICY.defaultIrregularForUnknown) freq = 'IRREGULAR';

  row[2] = provider;
  row[3] = seriesId;
  row[4] = freq;
  row[5] = unitType || 'raw';
  row[6] = transform || 'level';

  // precision
  row[8] = (row[8] === '' || row[8] == null) ? _guessPrecisionDp_(row[5], row[6]) : row[8];

  // notes if missing required mapping for numeric candidates
  if (SERIESMAP_POLICY.requireNumericProvider) {
    var notes = String(row[10] || '').trim();
    if ((!provider || !seriesId) && notes.indexOf('REVIEW') < 0) row[10] = (notes ? notes + ' | ' : '') + 'REVIEW: missing provider/series_id';
  }

  // created_ts
  row[11] = row[11] || _nowIso_();

  return row;
}

function _guessFreqFromName_(name) {
  var s = String(name || '').toLowerCase();
  if (/\bweekly\b|\bjobless\b|\bclaims\b/.test(s)) return 'W';
  if (/\bquarter\b|\bgdp\b|\bq[1-4]\b/.test(s)) return 'Q';
  if (/\bmonth\b|\bcpi\b|\bpce\b|\bpayroll\b|\bppi\b|\bretail\b/.test(s)) return 'M';
  return SERIESMAP_POLICY.defaultIrregularForUnknown ? 'IRREGULAR' : 'M';
}

function _guessUnitAndTransform_(name) {
  var s = String(name || '').toLowerCase();

  // Qual-like
  if (/\bspeech\b|\bminutes\b|\bstatement\b|\btestimony\b/.test(s)) {
    return { unit_type: 'qualitative', transform: 'skip' };
  }

  // Percent-ish
  if (/\byoy\b|\by\/y\b|\byear[- ]over[- ]year\b/.test(s)) {
    return { unit_type: 'percent_1dp', transform: 'yoy' };
  }
  if (/\bmom\b|\bm\/m\b|\bmonth[- ]over[- ]month\b/.test(s)) {
    return { unit_type: 'percent_1dp', transform: 'mom' };
  }

  // "Change" often diff
  if (/\bchange\b|\bdiff\b/.test(s)) {
    return { unit_type: 'raw', transform: 'diff' };
  }

  // default level
  return { unit_type: 'raw', transform: 'level' };
}

function _guessPrecisionDp_(unitType, transform) {
  var u = String(unitType || '').toLowerCase();
  var t = String(transform || '').toLowerCase();

  if (/qualitative/.test(u) || t === 'skip') return '';
  if (/percent_1dp/.test(u)) return 1;
  if (/percent_2dp/.test(u)) return 2;
  if (/index_1dp/.test(u)) return 1;
  if (/thousands_0dp/.test(u) || /count_0dp/.test(u)) return 0;
  if (t === 'mom' || t === 'yoy') return 1;
  return 2;
}

// -----------------------------------------------------------------------------
// Reference period parsing (used by actual_backfill.gs)
// -----------------------------------------------------------------------------

function getRefPeriodForEvent(ev) {
  var name = String((ev && ev.indicator_name) || '');
  var rel = new Date((ev && ev.release_ts) || '');

  // Try explicit month in parentheses
  var monthKey = _extractMonthFromName(name);
  if (monthKey) {
    var y = _inferYearFromRelease(rel, monthKey.month); // month 1..12
    var lastDay = new Date(Date.UTC(y, monthKey.month, 0));
    return { refDate: lastDay, refKey: _ym(lastDay) };
  }

  // Try quarter in parentheses (Q1..Q4)
  var q = _extractQuarterFromName(name);
  if (q) {
    var y2 = _inferYearFromRelease(rel, q.endMonth);
    var lastDay2 = new Date(Date.UTC(y2, q.endMonth, 0));
    return { refDate: lastDay2, refKey: _ym(lastDay2) };
  }

  // Fallback: last day of previous month relative to release
  if (isFinite(rel)) {
    var fallback = new Date(Date.UTC(rel.getUTCFullYear(), rel.getUTCMonth(), 0));
    return { refDate: fallback, refKey: _ym(fallback) };
  }

  // ultimate fallback: last day of previous month relative to now
  var now = new Date();
  var fb = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 0));
  return { refDate: fb, refKey: _ym(fb) };
}

function _ym(d) {
  var y = d.getUTCFullYear();
  var m = d.getUTCMonth() + 1;
  return y + '-' + (m < 10 ? '0' + m : String(m));
}

function _extractMonthFromName(name) {
  var s = String(name || '');
  // matches "(Jan)" "(January)" "(Jan/2025)" "(Oct/04)" etc.
  var m = s.match(/\((Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)(?:[^)]*)\)/i);
  if (!m) return null;

  var key = String(m[1]).slice(0,3).toLowerCase();
  var map = { jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12 };
  return map[key] ? { month: map[key] } : null;
}

function _extractQuarterFromName(name) {
  var s = String(name || '');
  var m = s.match(/\((Q[1-4])(?:[^)]*)\)/i);
  if (!m) return null;

  var q = String(m[1]).toUpperCase();
  var endMonth = (q === 'Q1') ? 3 : (q === 'Q2') ? 6 : (q === 'Q3') ? 9 : 12;
  return { quarter: q, endMonth: endMonth };
}

function _inferYearFromRelease(releaseDate, month) {
  // If release is early in year and reference month is late, assume previous year
  var d = (releaseDate instanceof Date) ? releaseDate : new Date(releaseDate);
  if (!isFinite(d)) return new Date().getUTCFullYear();

  var y = d.getUTCFullYear();
  var relMonth = d.getUTCMonth() + 1;

  if (month > relMonth + 2) return y - 1;
  return y;
}



