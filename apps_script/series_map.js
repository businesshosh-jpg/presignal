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
    'cand_1_provider','cand_1_series_id','cand_1_title','cand_1_score','cand_1_freq'
  ];

  if (sh.getLastRow() === 0) {
    sh.appendRow(baseHeaders.concat(candHeaders));
    return sh;
  }

  // Ensure headers exist (append missing to the right, do not reorder)
  var lastCol = Math.max(1, sh.getLastColumn());
  var headerRow = sh.getRange(1, 1, 1, lastCol).getValues()[0];
  _repairSuggestionsHeaders_(sh, headerRow);
  lastCol = Math.max(1, sh.getLastColumn());
  headerRow = sh.getRange(1, 1, 1, lastCol).getValues()[0];
  var have = {};
  for (var i = 0; i < headerRow.length; i++) have[String(headerRow[i] || '').trim()] = true;

  var requiredHeaders = baseHeaders.concat(candHeaders);
  var toAdd = [];
  for (var j = 0; j < requiredHeaders.length; j++) {
    if (!have[requiredHeaders[j]]) toAdd.push(requiredHeaders[j]);
  }
  if (toAdd.length) {
    sh.getRange(1, lastCol + 1, 1, toAdd.length).setValues([toAdd]);
  }

  return sh;
}

function _repairSuggestionsHeaders_(sh, headerRow) {
  var headers = (headerRow || []).map(function(h){ return String(h || '').trim(); });
  if (!headers.length) return;

  var seen = {};
  var renamed = false;
  var hasPrecision = false;

  for (var i = 0; i < headers.length; i++) {
    var key = String(headers[i] || '').trim().toLowerCase();
    if (key === 'precision_dp') hasPrecision = true;
  }

  for (var j = 0; j < headers.length; j++) {
    var name = String(headers[j] || '').trim();
    var low = name.toLowerCase();
    seen[low] = (seen[low] || 0) + 1;

    // Self-heal the known bad schema where precision_dp was accidentally duplicated
    // as a second seasonal_adjustment header.
    if (low === 'seasonal_adjustment' && seen[low] >= 2 && !hasPrecision) {
      headers[j] = 'precision_dp';
      hasPrecision = true;
      renamed = true;
    }
  }

  if (renamed) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
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

  // Must run while user has a selection. Support non-contiguous multi-select.
  var rangeList = ss.getActiveRangeList();
  var ranges = rangeList ? rangeList.getRanges() : null;
  if (!ranges || !ranges.length) {
    var fallbackRange = ss.getActiveRange();
    if (fallbackRange) ranges = [fallbackRange];
  }
  if (!ranges || !ranges.length) return { promoted: 0, skipped: 0, reason: 'no_active_range' };

  var selectedRows = [];
  var seenRows = {};
  for (var rg = 0; rg < ranges.length; rg++) {
    var range = ranges[rg];
    if (!range || range.getSheet().getName() !== 'SeriesMap_Suggestions') {
      return { promoted: 0, skipped: 0, reason: 'active_range_not_on_suggestions' };
    }

    var rowStart = range.getRow();
    var rowEnd = rowStart + range.getNumRows() - 1;
    for (var rowNum = rowStart; rowNum <= rowEnd; rowNum++) {
      if (rowNum < 2) continue; // skip header row
      if (seenRows[rowNum]) continue;
      seenRows[rowNum] = true;
      selectedRows.push(rowNum);
    }
  }
  selectedRows.sort(function(a, b) { return a - b; });
  if (!selectedRows.length) return { promoted: 0, skipped: 0, reason: 'header_selected' };

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

  var toAppend = [];
  var promoted = 0;
  var skipped = 0;

  for (var r = 0; r < selectedRows.length; r++) {
    var sheetRow = selectedRows[r];
    var row = sug.getRange(sheetRow, 1, 1, sug.getLastColumn()).getValues()[0];

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

function rebuildSeriesMapSuggestionsFromFmpCatalog_(opt) {
  opt = opt || {};
  var clearExisting = (opt.clearExisting !== false);
  var notesPrefix = String(opt.notesPrefix || 'FMP_CATALOG_V1').trim();
  var aiReviewer = _resolveSeriesMapAiReviewer_();
  var maxAiReviews = Number(opt.maxAiReviews);
  if (!isFinite(maxAiReviews) || maxAiReviews < 0) maxAiReviews = 0;
  var aiBudget = { enabled: !!aiReviewer, remaining: maxAiReviews, attempted: 0 };

  var sh = _ensureSuggestionsSheet_();
  var extraHeaders = [
    'indicator_name',
    'source_observations_count',
    'source_unit',
    'source_frequency',
    'source_impact',
    'source_first_release_ts',
    'source_last_release_ts',
    'source_avg_actual',
    'source_avg_estimate',
    'suggested_provider',
    'suggested_series_id',
    'suggested_title',
    'suggested_confidence',
    'suggested_reasoning',
    'review_status',
    'review_method',
    'auto_classification',
    'auto_notes',
    'auto_run_ts'
  ];
  var outIndexMap = _ensureHeaders_(sh, sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0], extraHeaders);
  if (outIndexMap._headersChanged) {
    outIndexMap = _indexMapFromHeaders_(
      sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(function(h){ return String(h || '').trim(); }),
      extraHeaders
    );
  }

  var existingRowsCleared = 0;
  if (clearExisting && sh.getLastRow() >= 2) {
    existingRowsCleared = sh.getLastRow() - 1;
    sh.getRange(2, 1, existingRowsCleared, sh.getLastColumn()).clearContent();
  }

  var catalogRows = _loadFmpCatalogRowsForSeriesMapSuggestions_();
  var fredCatalog = _loadFredCatalogRowsForSeriesMapRebuild_();
  if (!fredCatalog.length) throw new Error('FRED_Series_ID is empty or missing required headers');

  var rows = [];
  var rebuilt = 0;
  var reviewOnly = 0;
  var filteredOut = 0;
  var filteredReasons = {};
  var aiReviewed = 0;
  var aiSuggested = 0;

  for (var i = 0; i < catalogRows.length; i++) {
    var item = catalogRows[i];
    var skipReason = _fmpCatalogSuggestionSkipReason_(item);
    if (skipReason) {
      filteredOut++;
      filteredReasons[skipReason] = (filteredReasons[skipReason] || 0) + 1;
      continue;
    }

    var row = _buildSeriesMapSuggestionRowFromFmpCatalog_(item, fredCatalog, outIndexMap, notesPrefix, aiBudget);
    if (!row) continue;

    if (outIndexMap['review_method'] != null && String(row[outIndexMap['review_method']] || '') === 'ai') aiReviewed++;
    if (outIndexMap['suggested_series_id'] != null && String(row[outIndexMap['suggested_series_id']] || '').trim()) aiSuggested++;
    rows.push(row);
    rebuilt++;
    reviewOnly++;
  }

  if (rows.length) {
    sh.getRange(2, 1, rows.length, sh.getLastColumn()).setValues(rows);
  }

  var result = {
    cleared_existing_rows: existingRowsCleared,
    scanned_catalog_rows: catalogRows.length,
    catalog_rows_after_filter: rows.length,
    fred_catalog_rows: fredCatalog.length,
    rebuilt: rebuilt,
    review_only: reviewOnly,
    filtered_out: filteredOut,
    filtered_reasons: filteredReasons,
    ai_reviewer_enabled: !!aiReviewer,
    ai_review_budget: maxAiReviews,
    ai_reviewed: aiReviewed,
    ai_suggested: aiSuggested,
    clear_existing: clearExisting,
    notes_prefix: notesPrefix
  };

  if (typeof appendLog === 'function') {
    appendLog('INFO', 'SeriesMap suggestions rebuilt from FMP catalog', {
      module: 'series_map',
      step: 'rebuild_from_fmp_catalog',
      result: result
    });
  }

  return result;
}

function reviewSeriesMapSuggestionsBatch_(opt) {
  opt = opt || {};
  var batchSize = Number(opt.batchSize);
  if (!isFinite(batchSize) || batchSize < 1) batchSize = 12;

  var aiReviewer = _resolveSeriesMapAiReviewer_();
  if (!aiReviewer) throw new Error('Missing OPENAI_API_KEY for SeriesMap AI review');

  var ss = SpreadsheetApp.getActive();
  var sh = _ensureSuggestionsSheet_();
  var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(function(h){ return String(h || '').trim(); });
  var outIndexMap = _indexMapFromHeaders_(headers, [
    'indicator_name',
    'suggested_provider',
    'suggested_series_id',
    'suggested_title',
    'suggested_confidence',
    'suggested_reasoning',
    'review_status',
    'review_method',
    'auto_classification',
    'auto_notes',
    'auto_run_ts',
    'cand_1_provider',
    'cand_1_series_id',
    'cand_1_title',
    'cand_1_score',
    'cand_1_freq'
  ]);

  if (sh.getLastRow() < 2) return { reviewed: 0, suggested: 0, remaining_uncertain: 0, batch_size: batchSize };

  var values = sh.getDataRange().getValues();
  var idx = _hdrIndex_(values[0]);
  var catalogRows = _loadFmpCatalogRowsForSeriesMapSuggestions_();
  var fredCatalog = _loadFredCatalogRowsForSeriesMapRebuild_();
  var fmpByName = {};
  for (var i = 0; i < catalogRows.length; i++) {
    var item = catalogRows[i];
    fmpByName[_normalizeSeriesMapRebuildText_(item.indicator_name_sample || item.indicator_name_norm || '')] = item;
  }

  var toProcess = [];
  var remainingUncertain = 0;
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    var classification = String(row[idx('auto_classification')] || '').trim().toUpperCase();
    var reviewMethod = String(row[idx('review_method')] || '').trim().toLowerCase();
    var reviewStatus = String(row[idx('review_status')] || '').trim().toUpperCase();
    if (classification !== 'UNCERTAIN') continue;
    if (reviewMethod === 'ai') continue;
    if (reviewStatus && reviewStatus !== 'NEEDS_HUMAN_REVIEW') continue;
    remainingUncertain++;
    if (toProcess.length < batchSize) toProcess.push(r);
  }

  if (!toProcess.length) {
    return { reviewed: 0, suggested: 0, remaining_uncertain: remainingUncertain, batch_size: batchSize };
  }

  var writes = [];
  var reviewed = 0;
  var suggested = 0;
  var aiBudget = { enabled: true, remaining: batchSize, attempted: 0 };

  for (var j = 0; j < toProcess.length; j++) {
    var rIdx = toProcess[j];
    var rowVals = values[rIdx];
    var indicatorName = String(rowVals[idx('indicator_name')] || rowVals[idx('indicator_name_pattern')] || '').trim();
    var itemKey = _normalizeSeriesMapRebuildText_(indicatorName);
    var item = fmpByName[itemKey];
    if (!item) continue;

    var ranked = _rankFredCatalogCandidatesForFmpCatalog_(item, fredCatalog).slice(0, 3);
    var decision = _reviewSeriesMapSuggestionWithAi_(item, ranked, aiBudget);
    if (!decision) continue;

    reviewed++;
    if (decision.series_id) suggested++;

    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'suggested_provider', decision.provider || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'suggested_series_id', decision.series_id || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'suggested_title', decision.title || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'suggested_confidence', decision.confidence || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'suggested_reasoning', decision.reasoning || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'review_status', decision.review_status || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'review_method', 'ai');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'auto_notes', _buildFredCatalogAutoNotesForFmp_(item, decision, 'UNCERTAIN'));
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'auto_run_ts', _nowIso_());

    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'cand_1_provider', decision.series_id ? 'FRED' : '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'cand_1_series_id', decision.series_id || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'cand_1_title', decision.title || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'cand_1_score', decision.score || '');
    _queueSuggestionBatchWrite_(writes, rIdx + 1, outIndexMap, 'cand_1_freq', decision.freq || '');
  }

  if (writes.length) _applyWrites_(sh, writes);

  return {
    reviewed: reviewed,
    suggested: suggested,
    remaining_uncertain: Math.max(0, remainingUncertain - reviewed),
    batch_size: batchSize
  };
}

function _loadFmpCatalogRowsForSeriesMapSuggestions_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName('FMP_EventCatalog');
  if (!sh || sh.getLastRow() < 2) throw new Error('FMP_EventCatalog is empty or missing');

  var values = sh.getDataRange().getValues();
  var headers = values[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = _hdrIndex_(headers);

  var cCountry = idx('country');
  var cNorm = idx('indicator_name_norm');
  var cSample = idx('indicator_name_sample');
  if (cCountry < 0 || cNorm < 0 || cSample < 0) {
    throw new Error('FMP_EventCatalog missing required headers: country, indicator_name_norm, indicator_name_sample');
  }

  var out = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    var country = String(row[cCountry] || '').trim().toUpperCase();
    var indicatorNameNorm = String(row[cNorm] || '').trim();
    var indicatorNameSample = String(row[cSample] || '').trim();
    if (!country || !indicatorNameNorm || !indicatorNameSample) continue;

    out.push({
      country: country,
      indicator_name_norm: indicatorNameNorm,
      indicator_name_sample: indicatorNameSample,
      unit: (idx('unit') >= 0) ? String(row[idx('unit')] || '').trim() : '',
      inferred_frequency: (idx('inferred_frequency') >= 0) ? String(row[idx('inferred_frequency')] || '').trim().toUpperCase() : '',
      impact: (idx('impact') >= 0) ? String(row[idx('impact')] || '').trim() : '',
      observations_count: (idx('observations_count') >= 0) ? Number(row[idx('observations_count')] || 0) : 0,
      first_release_ts: (idx('first_release_ts') >= 0) ? String(row[idx('first_release_ts')] || '').trim() : '',
      last_release_ts: (idx('last_release_ts') >= 0) ? String(row[idx('last_release_ts')] || '').trim() : '',
      avg_actual: (idx('avg_actual') >= 0) ? row[idx('avg_actual')] : '',
      avg_estimate: (idx('avg_estimate') >= 0) ? row[idx('avg_estimate')] : ''
    });
  }

  out.sort(function(a, b) {
    var ka = a.country + '|' + a.indicator_name_norm;
    var kb = b.country + '|' + b.indicator_name_norm;
    return ka < kb ? -1 : (ka > kb ? 1 : 0);
  });
  return out;
}

function _loadFredCatalogRowsForSeriesMapRebuild_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName('FRED_Series_ID');
  if (!sh || sh.getLastRow() < 2) return [];

  var values = sh.getDataRange().getValues();
  var headers = values[0].map(function(h){ return String(h || '').trim().toLowerCase(); });
  var idx = _hdrIndex_(headers);

  var cId = idx('series_id');
  var cTitle = idx('title');
  if (cId < 0 || cTitle < 0) return [];

  var out = [];
  for (var r = 1; r < values.length; r++) {
    var seriesId = String(values[r][cId] || '').trim();
    var title = String(values[r][cTitle] || '').trim();
    if (!seriesId || !title) continue;

    out.push({
      id: seriesId,
      title: title,
      search_query: (idx('search_query') >= 0) ? String(values[r][idx('search_query')] || '') : '',
      frequency: (idx('frequency') >= 0) ? String(values[r][idx('frequency')] || '') : '',
      frequency_short: (idx('frequency_short') >= 0) ? String(values[r][idx('frequency_short')] || '') : '',
      units: (idx('units') >= 0) ? String(values[r][idx('units')] || '') : '',
      units_short: (idx('units_short') >= 0) ? String(values[r][idx('units_short')] || '') : '',
      seasonal_adjustment: (idx('seasonal_adjustment') >= 0) ? String(values[r][idx('seasonal_adjustment')] || '') : '',
      seasonal_adjustment_short: (idx('seasonal_adjustment_short') >= 0) ? String(values[r][idx('seasonal_adjustment_short')] || '') : '',
      notes: (idx('notes') >= 0) ? String(values[r][idx('notes')] || '') : ''
    });
  }
  return out;
}

function _buildSeriesMapSuggestionRowFromFmpCatalog_(item, catalog, outIndexMap, notesPrefix, aiBudget) {
  var country = String(item && item.country || '').trim().toUpperCase();
  var indicatorName = String(item && item.indicator_name_sample || '').trim();
  if (!country || !indicatorName) return null;

  var query = (typeof _normalizeIndicatorForFREDQuery_ === 'function')
    ? _normalizeIndicatorForFREDQuery_(String(item.indicator_name_norm || indicatorName))
    : buildDefaultPattern_(indicatorName);
  var ranked = _rankFredCatalogCandidatesForFmpCatalog_(item, catalog).slice(0, 3);
  var classification = _classifyFredCandidatesForFmpCatalog_(item, ranked);
  var decision = _buildSeriesMapSuggestionDecision_(item, ranked, classification, aiBudget);

  var row = suggestFromName_(country, indicatorName, null);
  row = _fillSeriesMapDefaults_(row);
  row[2] = '';
  row[3] = '';
  row[7] = '';
  row[10] = 'REVIEW: human approval required';

  var noteParts = [];
  if (notesPrefix) noteParts.push(notesPrefix);
  noteParts.push('classification=' + classification);
  noteParts.push('query=' + query);
  noteParts.push('source_freq=' + String(item.inferred_frequency || ''));
  noteParts.push('source_unit=' + String(item.unit || ''));
  noteParts.push('source_impact=' + String(item.impact || ''));
  if (decision.series_id) noteParts.push('suggested=' + decision.series_id);
  row[10] = noteParts.join(' | ') + (row[10] ? ' | ' + row[10] : '');

  if (item.inferred_frequency) row[4] = String(item.inferred_frequency || '').trim().toUpperCase();

  _clearFredCandidateSlots_(row);
  if (decision.series_id) {
    _writeFredCandidateIntoSuggestionRow_(row, 1, {
      id: decision.series_id,
      title: decision.title,
      score: decision.score,
      frequency_short: decision.freq
    });
  }

  if (outIndexMap['indicator_name'] != null) row[outIndexMap['indicator_name']] = indicatorName;
  if (outIndexMap['source_observations_count'] != null) row[outIndexMap['source_observations_count']] = item.observations_count || '';
  if (outIndexMap['source_unit'] != null) row[outIndexMap['source_unit']] = item.unit || '';
  if (outIndexMap['source_frequency'] != null) row[outIndexMap['source_frequency']] = item.inferred_frequency || '';
  if (outIndexMap['source_impact'] != null) row[outIndexMap['source_impact']] = item.impact || '';
  if (outIndexMap['source_first_release_ts'] != null) row[outIndexMap['source_first_release_ts']] = item.first_release_ts || '';
  if (outIndexMap['source_last_release_ts'] != null) row[outIndexMap['source_last_release_ts']] = item.last_release_ts || '';
  if (outIndexMap['source_avg_actual'] != null) row[outIndexMap['source_avg_actual']] = item.avg_actual;
  if (outIndexMap['source_avg_estimate'] != null) row[outIndexMap['source_avg_estimate']] = item.avg_estimate;
  if (outIndexMap['suggested_provider'] != null) row[outIndexMap['suggested_provider']] = decision.provider || '';
  if (outIndexMap['suggested_series_id'] != null) row[outIndexMap['suggested_series_id']] = decision.series_id || '';
  if (outIndexMap['suggested_title'] != null) row[outIndexMap['suggested_title']] = decision.title || '';
  if (outIndexMap['suggested_confidence'] != null) row[outIndexMap['suggested_confidence']] = decision.confidence || '';
  if (outIndexMap['suggested_reasoning'] != null) row[outIndexMap['suggested_reasoning']] = decision.reasoning || '';
  if (outIndexMap['review_status'] != null) row[outIndexMap['review_status']] = decision.review_status || '';
  if (outIndexMap['review_method'] != null) row[outIndexMap['review_method']] = decision.review_method || '';
  if (outIndexMap['auto_classification'] != null) row[outIndexMap['auto_classification']] = classification;
  if (outIndexMap['auto_notes'] != null) row[outIndexMap['auto_notes']] = _buildFredCatalogAutoNotesForFmp_(item, decision, classification);
  if (outIndexMap['auto_run_ts'] != null) row[outIndexMap['auto_run_ts']] = _nowIso_();

  return _normalizeSuggestionRowWidth_(row, _suggestionsSheetWidth_());
}

function _buildSeriesMapSuggestionDecision_(item, ranked, classification, aiBudget) {
  var top = ranked && ranked.length ? ranked[0] : null;
  if (classification === 'LIKELY_FRED' && top) {
    return {
      provider: 'FRED',
      series_id: String(top.id || ''),
      title: String(top.title || ''),
      freq: String(top.frequency_short || top.frequency || ''),
      score: top.score,
      confidence: 'HIGH',
      reasoning: 'System high-confidence match based on title, frequency, unit, and domain checks.',
      review_status: 'READY_FOR_HUMAN_CHECK',
      review_method: 'system'
    };
  }

  if (classification === 'UNCERTAIN') {
    var aiDecision = _reviewSeriesMapSuggestionWithAi_(item, ranked || [], aiBudget);
    if (aiDecision) return aiDecision;
  }

  return {
    provider: '',
    series_id: '',
    title: '',
    freq: '',
    score: '',
    confidence: (classification === 'NOT_FRED') ? 'LOW' : 'UNSURE',
    reasoning: (classification === 'NOT_FRED')
      ? 'No acceptable FRED match surfaced. Leave this for human review.'
      : ((aiBudget && aiBudget.enabled && aiBudget.remaining <= 0)
          ? 'AI review budget was exhausted for this run. Leave this for human review or rerun.'
          : 'System found no safe single match. Leave this for human review.'),
    review_status: 'NEEDS_HUMAN_REVIEW',
    review_method: 'system'
  };
}

function _rankFredCatalogCandidatesForFmpCatalog_(item, catalogRows) {
  var query = (typeof _normalizeIndicatorForFREDQuery_ === 'function')
    ? _normalizeIndicatorForFREDQuery_(String(item && (item.indicator_name_norm || item.indicator_name_sample) || ''))
    : buildDefaultPattern_(String(item && item.indicator_name_sample || ''));
  var baseRanked = _rankFredCatalogCandidates_(item.country, query, item.indicator_name_sample || item.indicator_name_norm, catalogRows);
  var targetFreq = _normalizeFmpSuggestionFreq_(item.inferred_frequency);
  var targetUnit = _normalizeFmpSuggestionUnit_(item.unit);
  var impact = String(item && item.impact || '').trim().toLowerCase();

  for (var i = 0; i < baseRanked.length; i++) {
    var cand = baseRanked[i];
    var score = Number(cand.score || 0);
    var candFreq = _normalizeFmpSuggestionFreq_(cand.frequency_short || cand.frequency);
    var candUnit = _normalizeFmpSuggestionUnit_(cand.units_short || cand.units);
    var candTitle = _normalizeSeriesMapRebuildText_(cand.title || '');
    var pattern = _normalizeSeriesMapRebuildText_(item.indicator_name_norm || item.indicator_name_sample || '');

    if (targetFreq && candFreq === targetFreq) score += 8;
    else if (targetFreq && candFreq) score -= 3;

    if (targetUnit && candUnit === targetUnit) score += 8;
    else if (targetUnit && candUnit && targetUnit !== candUnit) score -= 2;

    if (impact && impact !== 'none') score += 1;
    if (_tokenOverlap_(_tokens_(pattern), candTitle) >= 3) score += 4;

    cand.score = score;
  }

  baseRanked.sort(function(a, b) { return Number(b.score || 0) - Number(a.score || 0); });
  return baseRanked;
}

function _rankFredCatalogCandidates_(country, query, indicatorName, catalogRows) {
  var cc = String(country || '').trim().toUpperCase();
  var q = String(query || '').toLowerCase();
  var p = String(indicatorName || '').toLowerCase();
  var qTokens = _tokens_(q);
  var pTokens = _tokens_(p);
  var normalizedQuery = _normalizeSeriesMapRebuildText_(query);
  var normalizedPattern = _normalizeSeriesMapRebuildText_(indicatorName);

  var scored = [];
  for (var i = 0; i < catalogRows.length; i++) {
    var s = catalogRows[i] || {};
    var title = String(s.title || '');
    var id = String(s.id || '');
    if (!title || !id) continue;

    var freq = String(s.frequency_short || s.frequency || '');
    var units = String(s.units_short || s.units || '');
    var notes = String(s.notes || '');
    var searchQuery = String(s.search_query || '');
    var seasonal = String(s.seasonal_adjustment_short || s.seasonal_adjustment || '');
    var hay = (title + ' ' + id + ' ' + freq + ' ' + units + ' ' + notes + ' ' + searchQuery + ' ' + seasonal).toLowerCase();

    var score = 0;
    score += 3 * _tokenOverlap_(qTokens, hay);
    score += 2 * _tokenOverlap_(pTokens, hay);

    var normalizedTitle = _normalizeSeriesMapRebuildText_(title);
    if (normalizedTitle === normalizedPattern || normalizedTitle === normalizedQuery) score += 12;
    if (normalizedTitle.indexOf(normalizedQuery) >= 0) score += 6;
    if (normalizedTitle.indexOf(normalizedPattern) >= 0) score += 4;
    if (_normalizeSeriesMapRebuildText_(searchQuery) === normalizedQuery && normalizedQuery) score += 8;

    if (/\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(hay)) score -= 6;
    if (/\b(county|msa|metropolitan|city of|saint |st\. )\b/.test(hay)) score -= 5;
    if (/\b(bank|federal reserve bank of|commercial bank|deposit|loans)\b/.test(hay) && !/\b(rate|yield|treasury|fed funds|policy)\b/.test(hay)) score -= 3;
    if (/\b(d|w|m|q)\b/i.test(freq)) score += 1;
    if (/daily/i.test(freq)) score -= 1;
    if (/weekly|monthly|quarterly/i.test(freq)) score += 1;
    if (id && qTokens.indexOf(id.toLowerCase()) >= 0) score += 10;

    score += _countrySpecificFredScore_(cc, hay);
    score += _domainSpecificFredScore_(normalizedPattern, normalizedTitle, hay);

    scored.push({
      id: id,
      title: title,
      frequency: s.frequency || '',
      frequency_short: s.frequency_short || '',
      units: s.units || '',
      units_short: s.units_short || '',
      seasonal_adjustment: s.seasonal_adjustment || '',
      seasonal_adjustment_short: s.seasonal_adjustment_short || '',
      score: score
    });
  }

  scored.sort(function(a, b) { return b.score - a.score; });
  return scored;
}

function _classifyFredCatalogCandidatesFallback_(top) {
  if (!top || !top.length) return 'NOT_FRED';
  var s1 = Number(top[0].score || 0);
  var s2 = Number(top[1] ? top[1].score : -999);
  if (s1 >= 18 && (s1 - s2) >= 4) return 'LIKELY_FRED';
  if (s1 >= 12) return 'UNCERTAIN';
  return 'NOT_FRED';
}

function _classifyFredCandidatesForFmpCatalog_(item, top) {
  if (!top || !top.length) return 'NOT_FRED';

  var first = top[0];
  var second = top[1] || null;
  var s1 = Number(first.score || 0);
  var s2 = Number(second ? second.score : -999);
  var normalizedPattern = _normalizeSeriesMapRebuildText_(item.indicator_name_norm || item.indicator_name_sample || '');
  var normalizedTitle = _normalizeSeriesMapRebuildText_(first.title || '');
  var requiredHit = _hasRequiredDomainHit_(normalizedPattern, normalizedTitle);
  var targetFreq = _normalizeFmpSuggestionFreq_(item.inferred_frequency);
  var candFreq = _normalizeFmpSuggestionFreq_(first.frequency_short || first.frequency);

  if (_shouldForceNotFredForRebuild_(normalizedPattern)) return 'NOT_FRED';
  if (String(item.country || '').toUpperCase() === 'US' && !_looksUsMacroSeries_(first.title || '')) return 'UNCERTAIN';

  if (s1 >= 28 && (s1 - s2) >= 5 && requiredHit && (!targetFreq || !candFreq || targetFreq === candFreq)) return 'LIKELY_FRED';
  if (s1 >= 18) return 'UNCERTAIN';
  return 'NOT_FRED';
}

function _normalizeFredSeasonalAdjustment_(cand) {
  var raw = String((cand && (cand.seasonal_adjustment_short || cand.seasonal_adjustment)) || '').trim().toUpperCase();
  if (!raw) return '';
  if (raw === 'SA') return 'SA';
  if (raw === 'NSA') return 'NSA';
  if (raw.indexOf('SEASONALLY ADJUSTED') >= 0) return 'SA';
  if (raw.indexOf('NOT SEASONALLY ADJUSTED') >= 0) return 'NSA';
  return '';
}

function _countrySpecificFredScore_(country, hay) {
  var score = 0;
  var cc = String(country || '').toUpperCase();
  if (cc === 'US') {
    if (/\b(united states|u\.s\.|us\b|national)\b/.test(hay)) score += 10;
    if (/\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(hay)) score -= 35;
    if (/\b(germany|berlin|euro area|europe|france|italy|spain|united kingdom|uk\b|japan|china|canada|australia|new zealand|sweden|norway|switzerland|korea|singapore|india|brazil|mexico)\b/.test(hay)) score -= 18;
  }
  return score;
}

function _domainSpecificFredScore_(normalizedPattern, normalizedTitle, hay) {
  var score = 0;

  if (/\bmortgage\b/.test(normalizedPattern)) {
    if (/\bmortgage\b/.test(normalizedTitle)) score += 12;
    else score -= 10;
    if (/\b15 year\b/.test(normalizedPattern) && /\b15 year\b/.test(normalizedTitle)) score += 10;
    if (/\bfixed rate mortgage\b/.test(hay)) score += 8;
  }

  if (/\bfactory orders\b/.test(normalizedPattern)) {
    if (/\bfactory orders\b/.test(normalizedTitle)) score += 10;
  }

  if (/\bcpi\b|\bconsumer price index\b/.test(normalizedPattern)) {
    if (/\bconsumer price index\b|\bcpi\b/.test(normalizedTitle)) score += 8;
    if (/\bcore\b|\bexcluding food and energy\b/.test(normalizedPattern) && /\bexcluding food and energy\b|\bcore\b/.test(normalizedTitle)) score += 10;
    if (!/\bcore\b|\bexcluding food and energy\b/.test(normalizedPattern) && /\bexcluding food and energy\b|\bcore\b/.test(normalizedTitle)) score -= 8;
    if (!/\bcore\b|\bexcluding food and energy\b|\bnon food non energy\b/.test(normalizedPattern) && /\bnon food non energy\b/.test(normalizedTitle)) score -= 18;
    if (/\bresearch consumer price index\b/.test(hay)) score -= 16;
  }

  if (/\bppi\b|\bproducer price index\b/.test(normalizedPattern)) {
    if (/\bproducer price index\b|\bppi\b/.test(normalizedTitle)) score += 10;
    if (/\bfinal demand\b/.test(normalizedTitle)) score += 4;
    if (/\bexcluding food and energy\b|\bcore\b/.test(normalizedTitle) && !/\bcore\b|\bexcluding food and energy\b/.test(normalizedPattern)) score -= 8;
  }

  if (/\bjobless claims\b|\binitial claims\b/.test(normalizedPattern)) {
    if (/\bjobless claims\b|\binitial claims\b/.test(normalizedTitle)) score += 8;
    if (/\binitial claims\b/.test(normalizedTitle)) score += 12;
    if (/\bcontinued claims\b|\binsured unemployment\b/.test(normalizedTitle)) score -= 18;
  }

  if (/\bhousing starts\b/.test(normalizedPattern)) {
    if (/\bhousing starts\b/.test(normalizedTitle)) score += 14;
    if (!/\bhousing starts\b/.test(normalizedTitle)) score -= 12;
    if (/\bsquare feet|floor area|one family units\b/.test(hay)) score -= 40;
  }

  if (/\bimports\b/.test(normalizedPattern)) {
    if (/\bimports\b/.test(normalizedTitle)) score += 8;
    if (/\btrade balance|excess of total exports over general imports|contributions to percent change in gdpnow\b/.test(hay)) score -= 16;
    if (/\bbalance of payments basis\b/.test(hay)) score += 3;
  }

  if (/\bhouse price index\b/.test(normalizedPattern)) {
    if (/\bhouse price index\b/.test(normalizedTitle)) score += 10;
    if (/\bpurchase only\b/.test(hay)) score -= 5;
    if (/\ball transactions\b/.test(hay)) score += 2;
    if (/\breal residential property prices\b/.test(hay)) score -= 8;
  }

  if (/\bbuilding permits\b|\bbuild permits\b/.test(normalizedPattern)) {
    if (/\bbuilding permits\b/.test(normalizedTitle)) score += 16;
    else score -= 12;
    if (/\bauthorized\b/.test(normalizedTitle)) score += 4;
    if (/\bsingle family\b|\bprivately owned housing units authorized\b/.test(normalizedTitle) && !/\bsingle family\b/.test(normalizedPattern)) score -= 8;
    if (/\bfor (alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(hay)) score -= 40;
  }

  if (/\bretail sales\b/.test(normalizedPattern)) {
    if (/\bretail sales\b|\bretail and food services\b/.test(normalizedTitle)) score += 16;
    else score -= 12;
    if (/\badvance retail sales\b/.test(normalizedTitle)) score += 6;
    if (/\bexcluding autos\b|\bex autos\b/.test(normalizedTitle) && !/\bexcluding autos\b|\bex autos\b/.test(normalizedPattern)) score -= 10;
    if (/\bfood services\b/.test(normalizedTitle) && !/\bfood services\b/.test(normalizedPattern)) score += 1;
  }

  if (/\bpayroll\b|\bnonfarm payroll\b|\bnfp\b/.test(normalizedPattern)) {
    if (/\bnonfarm payroll\b|\btotal nonfarm payroll employment\b/.test(normalizedTitle)) score += 18;
    if (/\bprivate payroll\b|\btotal nonfarm private payroll employment\b/.test(normalizedTitle)) score += 10;
    if (/\bleisure and hospitality\b|\bdurable goods\b|\bmanufacturing\b|\bconstruction\b|\bgovernment\b/.test(normalizedTitle)) score -= 14;
    if (/\breal\b/.test(normalizedTitle)) score -= 10;
  }

  if (/\badp\b/.test(normalizedPattern)) {
    if (/\bprivate payroll\b|\btotal nonfarm private payroll employment\b/.test(normalizedTitle)) score += 18;
    if (/\bnonfarm payroll\b|\btotal nonfarm payroll employment\b/.test(normalizedTitle)) score += 4;
    if (/\bleisure and hospitality\b|\bdurable goods\b|\bmanufacturing\b|\bconstruction\b|\bgovernment\b/.test(normalizedTitle)) score -= 16;
  }

  if (/\baverage hourly earnings\b/.test(normalizedPattern)) {
    if (/\baverage hourly earnings\b/.test(normalizedTitle)) score += 16;
    else score -= 12;
    if (/\ball employees\b|\btotal private\b/.test(normalizedTitle)) score += 10;
    if (/\bproduction and nonsupervisory employees\b/.test(normalizedTitle) && !/\bproduction\b|\bnonsupervisory\b/.test(normalizedPattern)) score -= 8;
    if (/\bleisure and hospitality\b|\bdurable goods\b|\bmanufacturing\b|\bconstruction\b|\bgovernment\b/.test(normalizedTitle) && !/\bmanufacturing\b|\bconstruction\b|\bgovernment\b/.test(normalizedPattern)) score -= 14;
    if (/\breal\b/.test(normalizedTitle)) score -= 16;
  }

  if (/\bconsumer confidence\b|\bconsumer sentiment\b/.test(normalizedPattern)) {
    if (/\bconsumer confidence\b|\bconsumer sentiment\b/.test(normalizedTitle)) score += 12;
    if (/\bmichigan\b|\bconference board\b/.test(normalizedTitle)) score += 4;
    if (/\bstate\b|\bregional\b/.test(normalizedTitle)) score -= 10;
  }

  if (/\bcrude oil\b|\bcrude petroleum\b/.test(normalizedPattern)) {
    if (/\bcrude petroleum\b|\bcrude oil\b/.test(normalizedTitle)) score += 10;
    if (/\bfinished gasoline\b/.test(hay)) score -= 14;
    if (/\bstocks change\b|\bstock change\b|\binventories change\b|\binventory change\b/.test(normalizedPattern) && !/\bchange\b|\bchanges\b/.test(normalizedTitle)) score -= 10;
  }

  if (/\bmanufacturing production\b/.test(normalizedPattern)) {
    if (/\bindustrial production\b/.test(normalizedTitle)) score += 12;
    if (/\bmanufacturing\b/.test(normalizedTitle)) score += 6;
    if (/\baverage hourly earnings\b/.test(normalizedTitle)) score -= 30;
    if (/\bcement stocks\b|\bstocks for united states\b/.test(hay)) score -= 24;
  }

  if (/\bretail inventories\b/.test(normalizedPattern)) {
    if (/\bretail trade inventories\b/.test(normalizedTitle)) score += 12;
    if (/\bex autos\b|\bexcluding autos\b/.test(normalizedPattern) && /\bex autos\b|\bexcluding autos\b/.test(normalizedTitle)) score += 12;
    if (/\bex autos\b|\bexcluding autos\b/.test(normalizedPattern) && !/\bex autos\b|\bexcluding autos\b/.test(normalizedTitle)) score -= 34;
    if (/\brefined copper\b|\bcopper stocks\b/.test(normalizedTitle)) score -= 30;
  }

  if (/\bcushing\b/.test(normalizedPattern)) {
    if (/\bcushing\b/.test(normalizedTitle)) score += 14;
    else score -= 20;
  }

  if (/\bstocks change\b|\binventories change\b/.test(normalizedPattern)) {
    if (/\bstocks\b|\binventories\b/.test(normalizedTitle)) score += 3;
    if (/\bchange\b|\bchanges\b/.test(normalizedTitle)) score += 6;
  }

  if (/\bauction\b/.test(normalizedPattern)) {
    if (/\bauction\b/.test(normalizedTitle)) score += 8;
    else score -= 30;
    if (/\bmortgage\b/.test(normalizedTitle)) score -= 20;
    if (/\bdiscontinued\b/.test(hay)) score -= 10;
  }

  if (/\bdiscontinued\b/.test(hay)) score -= 8;

  return score;
}

function _hasRequiredDomainHit_(normalizedPattern, normalizedTitle) {
  if (!normalizedPattern || !normalizedTitle) return false;
  if (/\bmortgage\b/.test(normalizedPattern)) return /\bmortgage\b/.test(normalizedTitle);
  if (/\bfactory orders\b/.test(normalizedPattern)) return /\bfactory orders\b/.test(normalizedTitle);
  if (/\bcpi\b|\bconsumer price index\b/.test(normalizedPattern)) return /\bcpi\b|\bconsumer price index\b/.test(normalizedTitle);
  if (/\bppi\b|\bproducer price index\b/.test(normalizedPattern)) return /\bppi\b|\bproducer price index\b/.test(normalizedTitle);
  if (/\bbuilding permits\b|\bbuild permits\b/.test(normalizedPattern)) return /\bbuilding permits\b/.test(normalizedTitle);
  if (/\bretail sales\b/.test(normalizedPattern)) return /\bretail sales\b|\bretail and food services\b/.test(normalizedTitle);
  if (/\bretail inventories\b/.test(normalizedPattern)) {
    if (!/\bretail trade inventories\b/.test(normalizedTitle)) return false;
    if (/\bexcluding autos\b|\bex autos\b/.test(normalizedPattern)) {
      return /\bexcluding autos\b|\bex autos\b/.test(normalizedTitle);
    }
    return true;
  }
  if (/\bpayroll\b|\bnonfarm payroll\b|\bnfp\b/.test(normalizedPattern)) return /\bpayroll\b/.test(normalizedTitle);
  if (/\badp\b/.test(normalizedPattern)) return /\bprivate payroll\b|\btotal nonfarm private payroll employment\b/.test(normalizedTitle);
  if (/\baverage hourly earnings\b/.test(normalizedPattern)) return /\baverage hourly earnings\b/.test(normalizedTitle);
  if (/\bjobless claims\b|\binitial claims\b/.test(normalizedPattern)) return /\bjobless claims\b|\binitial claims\b/.test(normalizedTitle);
  if (/\bmanufacturing production\b/.test(normalizedPattern)) return /\bindustrial production\b/.test(normalizedTitle) && /\bmanufacturing\b/.test(normalizedTitle);
  if (/\bhousing starts\b/.test(normalizedPattern)) return /\bhousing starts\b/.test(normalizedTitle) && !/\bsquare feet|floor area|one family units\b/.test(normalizedTitle);
  if (/\bimports\b/.test(normalizedPattern)) return /\bimports\b/.test(normalizedTitle) && !/\btrade balance\b/.test(normalizedTitle);
  if (/\bhouse price index\b/.test(normalizedPattern)) return /\bhouse price index\b/.test(normalizedTitle);
  if (/\bcushing\b/.test(normalizedPattern)) return /\bcushing\b/.test(normalizedTitle);
  if (/\bcrude oil\b|\bcrude petroleum\b/.test(normalizedPattern)) return /\bcrude petroleum\b|\bcrude oil\b/.test(normalizedTitle);
  return normalizedTitle.indexOf(normalizedPattern) >= 0 || normalizedPattern.indexOf(normalizedTitle) >= 0 || _tokenOverlap_(_tokens_(normalizedPattern), normalizedTitle) >= 2;
}

function _shouldForceNotFredForRebuild_(normalizedPattern) {
  return /\bauction\b/.test(normalizedPattern);
}

function _shouldForceReviewForRebuild_(normalizedPattern, cand) {
  var title = _normalizeSeriesMapRebuildText_((cand && cand.title) || '');
  var freq = String((cand && (cand.frequency_short || cand.frequency)) || '').trim().toUpperCase();

  if (/\bhousing starts\b/.test(normalizedPattern) && /\bsquare feet|floor area|one family units\b/.test(title)) return true;
  if (/\bstocks change\b|\bstock change\b|\binventories change\b|\binventory change\b/.test(normalizedPattern) && !/\bchange\b|\bchanges\b/.test(title)) return true;
  if (/\bhouse price index\b/.test(normalizedPattern) && freq === 'Q') return true;
  if (/\baverage hourly earnings\b/.test(normalizedPattern) && /\breal\b|\bleisure and hospitality\b|\bdurable goods\b|\bmanufacturing\b/.test(title)) return true;
  if (/\badp\b/.test(normalizedPattern) && !/\bprivate payroll\b|\btotal nonfarm private payroll employment\b/.test(title)) return true;
  if (/\bjobless claims\b|\binitial claims\b/.test(normalizedPattern) && /\bcontinued claims\b|\binsured unemployment\b/.test(title)) return true;
  if (/\bretail sales\b/.test(normalizedPattern) && /\bexcluding autos\b|\bex autos\b/.test(title) && !/\bexcluding autos\b|\bex autos\b/.test(normalizedPattern)) return true;
  if (/\bretail inventories\b/.test(normalizedPattern) && /\bexcluding autos\b|\bex autos\b/.test(normalizedPattern) && !/\bexcluding autos\b|\bex autos\b/.test(title)) return true;
  if (/\bbuilding permits\b/.test(normalizedPattern) && /\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(title)) return true;
  if (/\bcpi\b|\bconsumer price index\b/.test(normalizedPattern) && !/\bcore\b|\bexcluding food and energy\b|\bnon food non energy\b/.test(normalizedPattern) && /\bnon food non energy\b|\bexcluding food and energy\b|\bcore\b/.test(title)) return true;
  if (/\bmanufacturing production\b/.test(normalizedPattern) && !/\bindustrial production\b/.test(title)) return true;
  if (/\bretail inventories\b/.test(normalizedPattern) && /\bcopper stocks\b/.test(title)) return true;

  return false;
}

function _looksUsMacroSeries_(title) {
  var s = String(title || '').toLowerCase();
  if (!s) return false;
  if (/\b(germany|berlin|euro area|france|italy|spain|united kingdom|japan|china|canada|australia|sweden|norway|switzerland|korea|singapore|india|brazil|mexico)\b/.test(s)) return false;
  if (/\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(s)) return false;
  if (/\b(united states|u\.s\.|us\b|national)\b/.test(s)) return true;
  if (/\bmortgage\b/.test(s)) return true;
  if (/\bhousing starts\b|\bimports\b|\bhouse price index\b|\bcrude petroleum\b|\bcrude oil\b|\bbuilding permits\b|\bretail sales\b|\bconsumer price index\b|\bproducer price index\b|\baverage hourly earnings\b|\bjobless claims\b|\binitial claims\b|\bpayroll employment\b|\bprivate payroll employment\b|\bindustrial production\b|\bretail trade inventories\b/.test(s)) return true;
  return false;
}

function _writeFredCandidateIntoSuggestionRow_(row, slot, cand) {
  var base = 12 + (slot - 1) * 5;
  row[base + 0] = cand ? 'FRED' : '';
  row[base + 1] = cand ? String(cand.id || '') : '';
  row[base + 2] = cand ? String(cand.title || '') : '';
  row[base + 3] = cand && cand.score != null ? cand.score : '';
  row[base + 4] = cand ? String(cand.frequency_short || cand.frequency || '') : '';
}

function _clearFredCandidateSlots_(row) {
  _writeFredCandidateIntoSuggestionRow_(row, 1, null);
}

function _buildFredCatalogAutoNotesForFmp_(item, decision, classification) {
  var label = String(item && (item.indicator_name_sample || item.indicator_name_norm) || '').trim();
  if (decision && decision.series_id && decision.review_method === 'system') return 'FMP_CATALOG_V1: system found a strong single FRED suggestion for ' + label;
  if (decision && decision.series_id && decision.review_method === 'ai') return 'FMP_CATALOG_V1: AI suggested one FRED row for human review for ' + label;
  if (classification === 'UNCERTAIN') return 'FMP_CATALOG_V1: no safe single match; leave this row to human review for ' + label;
  return 'FMP_CATALOG_V1: FRED catalog hits exist but look mismatched for ' + label;
}

function _resolveSeriesMapAiReviewer_() {
  var key = (typeof _getKey_ === 'function') ? _getKey_(['OPENAI_API_KEY']) : '';
  if (!key) return null;
  var model = (typeof CFG !== 'undefined' && CFG.OPENAI_MODEL && String(CFG.OPENAI_MODEL).trim())
    ? String(CFG.OPENAI_MODEL).trim()
    : 'gpt-4o-mini';
  return { provider: 'OpenAI', key: key, model: model };
}

function _reviewSeriesMapSuggestionWithAi_(item, ranked, aiBudget) {
  var ai = _resolveSeriesMapAiReviewer_();
  if (!ai || !ranked || !ranked.length) return null;
  if (aiBudget && (!aiBudget.enabled || aiBudget.remaining <= 0)) return null;

  try {
    if (aiBudget) {
      aiBudget.remaining--;
      aiBudget.attempted++;
    }
    var payload = {
      task: 'review_seriesmap_suggestion',
      country: item.country || '',
      indicator_name_sample: item.indicator_name_sample || '',
      indicator_name_norm: item.indicator_name_norm || '',
      unit: item.unit || '',
      inferred_frequency: item.inferred_frequency || '',
      impact: item.impact || '',
      candidates: ranked.slice(0, 3).map(function(c) {
        return {
          provider: 'FRED',
          series_id: c.id || '',
          title: c.title || '',
          frequency: c.frequency_short || c.frequency || '',
          units: c.units_short || c.units || '',
          score: c.score || ''
        };
      })
    };
    var prompt = _buildSeriesMapAiPrompt_(payload);
    var reviewed = _callSeriesMapOpenAIReviewer_(ai, prompt);
    return _normalizeSeriesMapAiDecision_(reviewed, ranked);
  } catch (e) {
    if (typeof appendLog === 'function') {
      appendLog('WARN', 'SeriesMap AI review failed', {
        module: 'series_map',
        step: 'ai_review',
        indicator_name: item.indicator_name_sample || '',
        error: String(e && e.message || e)
      });
    }
    return null;
  }
}

function _buildSeriesMapAiPrompt_(payload) {
  return {
    system: 'You review macroeconomic indicator mapping suggestions. Pick at most one candidate only if the match is conceptually strong. If uncertain, choose no suggestion.',
    user: JSON.stringify(payload),
    instruction: 'Return strict JSON only with keys: decision, series_id, confidence, reasoning. decision must be one of SUGGEST or HUMAN_REVIEW. confidence must be one of HIGH, MEDIUM, LOW. If decision is HUMAN_REVIEW, series_id must be an empty string.'
  };
}

function _callSeriesMapOpenAIReviewer_(prov, prompt) {
  var url = 'https://api.openai.com/v1/chat/completions';
  var body = {
    model: prov.model,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: prompt.system },
      { role: 'user', content: prompt.user + '\n\n' + prompt.instruction }
    ]
  };

  var runner = (typeof _withRetries_ === 'function')
    ? _withRetries_
    : function(fn) { return fn(); };

  return runner(function() {
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + prov.key },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    if (code === 429) throw new Error('quota_exceeded: OpenAI 429');
    if (code >= 500) throw new Error('provider_error: OpenAI ' + code);
    if (code < 200 || code > 299) throw new Error('provider_error: OpenAI ' + code + ': ' + resp.getContentText());
    var j = JSON.parse(resp.getContentText());
    var c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    if (!c) throw new Error('provider_error: OpenAI empty content');
    return JSON.parse(c);
  }, { provider: 'OpenAI' });
}

function _normalizeSeriesMapAiDecision_(raw, ranked) {
  if (!raw || typeof raw !== 'object') return null;
  var decision = String(raw.decision || '').trim().toUpperCase();
  var seriesId = String(raw.series_id || '').trim();
  var confidence = String(raw.confidence || '').trim().toUpperCase();
  var reasoning = String(raw.reasoning || '').trim();

  if (decision !== 'SUGGEST' || !seriesId) {
    return {
      provider: '',
      series_id: '',
      title: '',
      freq: '',
      score: '',
      confidence: confidence || 'LOW',
      reasoning: reasoning || 'AI could not make a safe single suggestion. Leave this for human review.',
      review_status: 'NEEDS_HUMAN_REVIEW',
      review_method: 'ai'
    };
  }

  var chosen = null;
  for (var i = 0; i < ranked.length; i++) {
    if (String(ranked[i].id || '').trim() === seriesId) {
      chosen = ranked[i];
      break;
    }
  }
  if (!chosen) {
    return {
      provider: '',
      series_id: '',
      title: '',
      freq: '',
      score: '',
      confidence: confidence || 'LOW',
      reasoning: 'AI selected a series outside the reviewed shortlist. Leave this for human review.',
      review_status: 'NEEDS_HUMAN_REVIEW',
      review_method: 'ai'
    };
  }

  return {
    provider: 'FRED',
    series_id: String(chosen.id || ''),
    title: String(chosen.title || ''),
    freq: String(chosen.frequency_short || chosen.frequency || ''),
    score: chosen.score,
    confidence: confidence || 'MEDIUM',
    reasoning: reasoning || 'AI suggested this as the best available single match from the shortlist.',
    review_status: 'READY_FOR_HUMAN_CHECK',
    review_method: 'ai'
  };
}

function _normalizeSeriesMapRebuildText_(text) {
  var s = String(text || '').trim().toLowerCase();
  if (!s) return '';
  s = s.replace(/\b(month over month)\b/g, 'mom');
  s = s.replace(/\b(year over year)\b/g, 'yoy');
  s = s.replace(/\b(m\/m)\b/g, 'mom');
  s = s.replace(/\b(y\/y)\b/g, 'yoy');
  s = s.replace(/[^a-z0-9]+/g, ' ');
  s = s.replace(/\b(preliminary|final|flash|advance|revised|estimate|est)\b/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

function _suggestionsSheetWidth_() {
  var sh = _ensureSuggestionsSheet_();
  return sh.getLastColumn();
}

function _normalizeSuggestionRowWidth_(row, width) {
  var out = row.slice(0);
  for (var i = out.length; i < width; i++) out[i] = '';
  if (out.length > width) out = out.slice(0, width);
  return out;
}

function _fmpCatalogSuggestionSkipReason_(item) {
  var impact = String(item && item.impact || '').trim().toLowerCase();
  var name = _normalizeSeriesMapRebuildText_(item && (item.indicator_name_sample || item.indicator_name_norm) || '');
  if (!name) return 'blank_name';
  if (impact === 'none') return 'impact_none';
  if (/\bauction\b/.test(name)) return 'auction';
  if (/\bcftc\b/.test(name)) return 'cftc';
  if (/\bholiday\b|\bbank holiday\b|\bmarket holiday\b|\bclosed\b/.test(name)) return 'holiday';
  return '';
}

function _normalizeFmpSuggestionFreq_(freq) {
  var s = String(freq || '').trim().toUpperCase();
  if (!s) return '';
  if (s === 'WEEKLY' || s === 'W') return 'W';
  if (s === 'MONTHLY' || s === 'M') return 'M';
  if (s === 'QUARTERLY' || s === 'Q') return 'Q';
  if (s === 'SEMIANNUAL' || s === 'SA') return 'SA';
  if (s === 'ANNUAL' || s === 'A' || s === 'YEARLY') return 'A';
  if (s === 'DAILY' || s === 'D') return 'D';
  if (s === 'IRREGULAR') return 'IRREGULAR';
  return s;
}

function _normalizeFmpSuggestionUnit_(unit) {
  var s = _normalizeSeriesMapRebuildText_(unit);
  if (!s) return '';
  if (/\bpercent(age)?\b|\bpercent change\b|\bchange percentage\b|\b%\b/.test(s)) return 'percent';
  if (/\bindex\b/.test(s)) return 'index';
  if (/\bdollar\b|\busd\b/.test(s)) return 'usd';
  if (/\bthousand\b/.test(s)) return 'thousands';
  if (/\bmillion\b/.test(s)) return 'millions';
  if (/\bbillion\b/.test(s)) return 'billions';
  if (/\bpersons\b|\bpeople\b|\bemployees\b|\bjobs\b/.test(s)) return 'count';
  return s;
}

function _queueSuggestionBatchWrite_(writes, row1, outIndexMap, key, value) {
  if (typeof _queueWrite_ !== 'function') throw new Error('_queueWrite_ not found');
  if (outIndexMap[key] == null || outIndexMap[key] < 0) return;
  _queueWrite_(writes, row1, outIndexMap[key] + 1, value);
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
