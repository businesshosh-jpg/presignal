/**
 * SeriesMap → Auto-suggest from FRED
 * - Reads SeriesMap_Suggestions.indicator_name_pattern
 * - Queries FRED series search
 * - Writes top 2 candidates + classification into new columns
 *
 * Safety:
 * - Never edits SeriesMap
 * - Skips rows only when cand_1_series_id already filled (unless forceOverwrite)
 * - Logs to log sheet via appendLog()
 *
 * Prereq:
 * - Script Properties: FRED_API_KEY
 */
function menuSeriesMapAutoSuggestFRED_() {
  var ui = SpreadsheetApp.getUi();
  var ss = SpreadsheetApp.getActive();
  var activeSheet = ss.getActiveSheet();

  if (!activeSheet || activeSheet.getName() !== 'SeriesMap_Suggestions') {
    ui.alert('Select rows on the "SeriesMap_Suggestions" sheet first, then run this action.');
    return;
  }

  // Use RangeList to correctly handle multi-range selections.
  var rangeList = activeSheet.getActiveRangeList();
  var ranges = rangeList ? rangeList.getRanges() : [];

  // Fallback to active range if RangeList is not available for some reason.
  if (!ranges || !ranges.length) {
    var single = activeSheet.getActiveRange();
    if (single) ranges = [single];
  }

  if (!ranges || !ranges.length) {
    ui.alert('No selection detected.\n\nSelect the rows you want to run, then re-run.');
    return;
  }

  // Convert selection to unique sheet row numbers (ignore header row 1)
  var onlyRows = [];
  var seen = {};
  for (var k = 0; k < ranges.length; k++) {
    var rg = ranges[k];
    var startRow = rg.getRow();
    var numRows = rg.getNumRows();

    for (var i = 0; i < numRows; i++) {
      var rowNum = startRow + i;
      if (rowNum < 2) continue; // ignore header
      if (seen[rowNum]) continue;
      seen[rowNum] = true;
      onlyRows.push(rowNum);
    }
  }

  onlyRows.sort(function(a, b) { return a - b; });

  if (!onlyRows.length) {
    ui.alert('Your selection only includes the header row.\n\nSelect one or more data rows and re-run.');
    return;
  }

  var props = PropertiesService.getScriptProperties();
  var apiKey = (props.getProperty('FRED_API_KEY') || '').trim();
  if (!apiKey) {
    appendLog('ERROR', 'Missing Script Property FRED_API_KEY', { module: 'seriesmap_fred_autosuggest' });
    ui.alert('Missing FRED_API_KEY in Script Properties.\n\nAdd it first, then re-run.');
    return;
  }

  var result = runSeriesMapAutoSuggestFromFRED_({
    onlyRows: onlyRows,   // <-- selection-only mode
    maxRows: 3000,
    topN: 2,
    sleepMsPerCall: 800,
    burstSize: 5,
    burstSleepMs: 2500,
    forceOverwrite: true  // <-- selected rows always refresh cand_1
  });

  ui.alert(
    'FRED auto-suggest done.\n\n' +
    'Scanned: ' + result.scanned + '\n' +
    'Updated: ' + result.updated + '\n' +
    'Skipped (cand_1 already filled): ' + result.skipped_has_map + '\n' +
    'Skipped (missing pattern): ' + result.skipped_missing_pattern + '\n' +
    'Errors: ' + result.errors
  );
}

function runSeriesMapAutoSuggestFromFRED_(opt) {
  opt = opt || {};
  var ss = SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName('SeriesMap_Suggestions');

  var maxRows = opt.maxRows || 3000;
  var topN = opt.topN || 2;
  var sleepMsPerCall = opt.sleepMsPerCall || 250;
  var burstSize = opt.burstSize || 10;
  var burstSleepMs = opt.burstSleepMs || 1200;
  var forceOverwrite = !!opt.forceOverwrite;

  var props = PropertiesService.getScriptProperties();
  var apiKey = (props.getProperty('FRED_API_KEY') || '').trim();

  var range = sheet.getDataRange();
  var values = range.getValues();
  if (values.length < 2) {
    return { scanned: 0, updated: 0, skipped_has_map: 0, skipped_missing_pattern: 0, errors: 0 };
  }

  var headers = values[0].map(function(h){ return String(h || '').trim(); });
  var idx = _hdrIndex_(headers);

  // Required input
  var colPattern = idx('indicator_name_pattern');
  // Optional input (preferred for FRED search; pattern is often regex-like)
  var colIndicatorName = idx('indicator_name');
  if (colPattern < 0) {
    appendLog('ERROR', 'Missing header indicator_name_pattern in SeriesMap_Suggestions', { module: 'seriesmap_fred_autosuggest' });
    SpreadsheetApp.getUi().alert('SeriesMap_Suggestions must have header: indicator_name_pattern');
    return { scanned: 0, updated: 0, skipped_has_map: 0, skipped_missing_pattern: 0, errors: 1 };
  }

  // Ensure output columns exist (append if missing)
  var outCols = [
    'cand_1_provider','cand_1_series_id','cand_1_title','cand_1_score','cand_1_freq',
    'auto_classification','auto_notes','auto_run_ts'
  ];
  var outIndexMap = _ensureHeaders_(sheet, headers, outCols);
  // Reload values if headers changed (so indices line up)
  if (outIndexMap._headersChanged) {
    range = sheet.getDataRange();
    values = range.getValues();
    headers = values[0].map(function(h){ return String(h || '').trim(); });
    idx = _hdrIndex_(headers);
    colPattern = idx('indicator_name_pattern');
    colIndicatorName = idx('indicator_name');
    outIndexMap = _indexMapFromHeaders_(headers, outCols);
  }
  // --- Hard validation: cand_1_series_id must exist (prevents silent mis-indexing)
  // Precompute cand_1 column indices (sheet columns are 1-based)
  var cand1Cols = {
    provider: (outIndexMap['cand_1_provider'] != null) ? outIndexMap['cand_1_provider'] + 1 : null,
    series_id: (outIndexMap['cand_1_series_id'] != null) ? outIndexMap['cand_1_series_id'] + 1 : null,
    title: (outIndexMap['cand_1_title'] != null) ? outIndexMap['cand_1_title'] + 1 : null,
    score: (outIndexMap['cand_1_score'] != null) ? outIndexMap['cand_1_score'] + 1 : null,
    freq: (outIndexMap['cand_1_freq'] != null) ? outIndexMap['cand_1_freq'] + 1 : null
  };

  var scanned = 0, updated = 0, skippedHasMap = 0, skippedMissingPattern = 0, errors = 0;
  var writes = []; // {rowIndex, colIndex, value}
  var callsInBurst = 0;

  // Selection-only mode: opt.onlyRows must be provided (sheet row numbers, 1-based)
  var onlyRows = opt.onlyRows || [];
  if (!onlyRows || !onlyRows.length) {
    SpreadsheetApp.getUi().alert('No selected rows were provided.\n\nSelect rows in SeriesMap_Suggestions and run again.');
    return { scanned: 0, updated: 0, skipped_has_map: 0, skipped_missing_pattern: 0, errors: 0 };
  }

  // Normalize to unique, valid sheet row numbers within current data range
  var maxSheetRow = Math.min(values.length, maxRows); // values.length is last sheet row in DataRange
  var seen = {};
  var rowList = [];
  for (var i = 0; i < onlyRows.length; i++) {
    var rowNum = Number(onlyRows[i]);
    if (!rowNum || rowNum < 2) continue;                 // ignore header / invalid
    if (rowNum > maxSheetRow) continue;                  // outside loaded range
    if (seen[rowNum]) continue;
    seen[rowNum] = true;
    rowList.push(rowNum);
  }
  rowList.sort(function(a, b) { return a - b; });

  for (var ii = 0; ii < rowList.length; ii++) {
    var r = rowList[ii] - 1; // convert sheet row number -> values[] index
    scanned++;

    var patternRaw = String(values[r][colPattern] || '').trim();
    if (!patternRaw) { skippedMissingPattern++; continue; }

    // If overwriting, clear cand_1_* first so stale values don't persist when no candidates are found.
    if (forceOverwrite) {
      if (cand1Cols.provider) _queueWrite_(writes, r + 1, cand1Cols.provider, '');
      if (cand1Cols.series_id) _queueWrite_(writes, r + 1, cand1Cols.series_id, '');
      if (cand1Cols.title) _queueWrite_(writes, r + 1, cand1Cols.title, '');
      if (cand1Cols.score) _queueWrite_(writes, r + 1, cand1Cols.score, '');
      if (cand1Cols.freq) _queueWrite_(writes, r + 1, cand1Cols.freq, '');
    } else {
      // Skip if cand_1 already filled (no overwrite)
      var cand1 = String(values[r][cand1Idx0] || '').trim();
      if (cand1) {
        skippedHasMap++;
        continue;
      }
    }



    var indicatorNameRaw = (colIndicatorName >= 0) ? String(values[r][colIndicatorName] || '').trim() : '';
    var query = _normalizeIndicatorForFREDQuery_(indicatorNameRaw || patternRaw);
    try {
      // Rate limiting
      if (callsInBurst >= burstSize) {
        Utilities.sleep(burstSleepMs);
        callsInBurst = 0;
      }

      var search = _fredSeriesSearch_(apiKey, query, 12);

      // Retry once with a simpler query if nothing came back
      if (!search || !search.length) {
        var q2 = query
          .replace(/\b(flash|prelim|preliminary|final|revised|revision)\b/gi, ' ')
          .replace(/\s+/g, ' ')
          .trim();
        if (q2 && q2 !== query) {
          search = _fredSeriesSearch_(apiKey, q2, 12);
        }
      }
      callsInBurst++;
      Utilities.sleep(sleepMsPerCall);

      var ranked = _rankFredSeriesResults_(query, patternRaw, search || []);

      // Keep up to 3 candidates (do NOT overwrite topN numeric option)
      var topList = ranked.slice(0, 3);

      var classification = _classifyFredCandidates_(topList);
      var notes = _buildNotes_(query, topList, classification);

      function _getCandSlotForWrite_() {
        // Reserve cand_1 for FRED only.
        // If cand_1 is already filled and we're not forcing overwrite, do not write.
        var sidKey = 'cand_1_series_id';
        var sidIdx = outIndexMap[sidKey];
        if (sidIdx == null) return 0;

        var existingSid = String(values[r][sidIdx] || '').trim();
        if (forceOverwrite || !existingSid) return 1;

        return 0;
      }

      function _writeCandSlot_(slot, cand) {
        if (!slot) return;

        // Keys for this slot
        var pKey = 'cand_' + slot + '_provider';
        var sKey = 'cand_' + slot + '_series_id';
        var tKey = 'cand_' + slot + '_title';
        var scKey = 'cand_' + slot + '_score';
        var fKey = 'cand_' + slot + '_freq';

        // Indices (0-based in outIndexMap, +1 for sheet col)
        var pCol = outIndexMap[pKey] != null ? outIndexMap[pKey] + 1 : null;
        var sCol = outIndexMap[sKey] != null ? outIndexMap[sKey] + 1 : null;
        var tCol = outIndexMap[tKey] != null ? outIndexMap[tKey] + 1 : null;
        var scCol = outIndexMap[scKey] != null ? outIndexMap[scKey] + 1 : null;
        var fCol = outIndexMap[fKey] != null ? outIndexMap[fKey] + 1 : null;

        // Values
        var seriesId = cand ? (cand.id || '') : '';
        var title = cand ? (cand.title || '') : '';
        var freq = cand ? (cand.frequency_short || cand.frequency || '') : '';
        // Use whatever score you have; if none, leave blank
        var score = cand && (cand.score != null) ? cand.score : '';

        if (pCol) _queueWrite_(writes, r + 1, pCol, cand ? 'FRED' : '');
        if (sCol) _queueWrite_(writes, r + 1, sCol, seriesId);
        if (tCol) _queueWrite_(writes, r + 1, tCol, title);
        if (scCol) _queueWrite_(writes, r + 1, scCol, score);
        if (fCol) _queueWrite_(writes, r + 1, fCol, freq);
      }

      // Write only the best match into cand_1 (reserved for FRED)
      var slot = _getCandSlotForWrite_();
      if (slot && topList && topList.length) {
        _writeCandSlot_(slot, topList[0]);
      }

      var hasAnyCandidate = (topList && topList.length > 0);

      // Only write auto_* if we found candidates (optional but recommended to avoid "fake updates")
      if (hasAnyCandidate) {
        _queueWrite_(writes, r + 1, outIndexMap['auto_classification'] + 1, classification);
        _queueWrite_(writes, r + 1, outIndexMap['auto_notes'] + 1, notes);
        _queueWrite_(writes, r + 1, outIndexMap['auto_run_ts'] + 1, new Date());
        updated++;
      } else {
        // Optional: keep a breadcrumb without counting as updated
        // _queueWrite_(writes, r + 1, outIndexMap['auto_notes'] + 1, 'NO_FRED_MATCH: ' + query);
        // _queueWrite_(writes, r + 1, outIndexMap['auto_run_ts'] + 1, new Date());
      }

      // Flush in chunks to avoid slow cell-by-cell
      if (writes.length >= 200) {
        _applyWrites_(sheet, writes);
        writes = [];
      }
    } catch (e) {
      errors++;
      appendLog('WARN', 'FRED auto-suggest failed for row', {
        module: 'seriesmap_fred_autosuggest',
        row: r+1,
        query: query,
        indicator_name_pattern: patternRaw,
        error: String(e && e.message ? e.message : e)
      });
    }
  }

  if (writes.length) _applyWrites_(sheet, writes);

  appendLog('INFO', 'FRED auto-suggest summary', {
    module: 'seriesmap_fred_autosuggest',
    scanned: scanned,
    updated: updated,
    skipped_has_map: skippedHasMap,
    skipped_missing_pattern: skippedMissingPattern,
    errors: errors
  });

  return {
    scanned: scanned,
    updated: updated,
    skipped_has_map: skippedHasMap,
    skipped_missing_pattern: skippedMissingPattern,
    errors: errors
  };
}

// ------------------------
// FRED API
// ------------------------
function _fredSeriesSearch_(apiKey, query, limit) {
  limit = limit || 10;

  var base = 'https://api.stlouisfed.org/fred/series/search';
  var url = base
    + '?api_key=' + encodeURIComponent(apiKey)
    + '&file_type=json'
    + '&search_text=' + encodeURIComponent(query)
    + '&limit=' + encodeURIComponent(limit)
    + '&order_by=popularity'
    + '&sort_order=desc';

  var attempts = 3;
  var backoffMs = 1500;

  for (var a = 1; a <= attempts; a++) {
    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    var code = resp.getResponseCode();
    var text = resp.getContentText();

    if (code === 200) {
      var json = JSON.parse(text);
      return (json && json.seriess) ? json.seriess : [];
    }

    // Retry on common transient / rate-limit codes
    if (code === 429 || code === 503 || code === 502 || code === 504) {
      // Exponential-ish backoff
      Utilities.sleep(backoffMs);
      backoffMs *= 2;
      continue;
    }

    // Non-retryable error
    throw new Error('FRED search HTTP ' + code + ' :: ' + text.slice(0, 200));
  }

  // If we exhausted retries, throw with last seen payload
  throw new Error('FRED search failed after retries (likely rate-limited). Query=' + query);
}

// ------------------------
// Ranking / heuristics
// ------------------------
function _rankFredSeriesResults_(query, patternRaw, seriess) {
  var q = (query || '').toLowerCase();
  var p = (patternRaw || '').toLowerCase();

  var qTokens = _tokens_(q);
  var pTokens = _tokens_(p);

  var scored = (seriess || []).map(function(s) {
    var title = String(s.title || '');
    var id = String(s.id || '');
    var freq = String(s.frequency_short || s.frequency || '');
    var units = String(s.units_short || s.units || '');
    var notes = String(s.notes || '');

    var hay = (title + ' ' + id + ' ' + freq + ' ' + units + ' ' + notes).toLowerCase();

    var score = 0;

    // Token overlap (query & pattern)
    score += 3 * _tokenOverlap_(qTokens, hay);
    score += 2 * _tokenOverlap_(pTokens, hay);

    // Prefer nationwide over regional/state (penalize obvious region)
    if (/(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b/.test(hay)) {
      score -= 6;
    }
    if (/\b(county|msa|metropolitan|city of|saint |st\. )\b/.test(hay)) score -= 5;

    // Penalize bank/obscure finance series unless clearly requested
    if (/\b(bank|federal reserve bank of|commercial bank|deposit|loans)\b/.test(hay) && !/\b(rate|yield|treasury|fed funds|policy)\b/.test(hay)) {
      score -= 3;
    }

    // Prefer common macro frequencies
    if (/\b(d|w|m|q)\b/i.test(freq)) score += 1;
    if (/daily/i.test(freq)) score -= 1; // daily macro is often niche
    if (/weekly|monthly|quarterly/i.test(freq)) score += 1;

    // Boost exact-ish matches on famous IDs
    if (id && qTokens.indexOf(id.toLowerCase()) >= 0) score += 10;

    return {
      id: id,
      title: title,
      frequency: s.frequency || '',
      frequency_short: s.frequency_short || '',
      units: s.units || '',
      units_short: s.units_short || '',
      score: score
    };
  });

  scored.sort(function(a,b){ return b.score - a.score; });
  return scored;
}

function _classifyFredCandidates_(top) {
  if (!top || !top.length) return 'NOT_FRED';
  var s1 = top[0].score;
  var s2 = (top[1] ? top[1].score : -999);

  // Strong top hit, clear gap → LIKELY_FRED
  if (s1 >= 18 && (s1 - s2) >= 4) return 'LIKELY_FRED';

  // Decent hits but ambiguous → UNCERTAIN
  if (s1 >= 12) return 'UNCERTAIN';

  return 'NOT_FRED';
}

function _buildNotes_(query, top, classification) {
  if (!top || !top.length) return 'No good FRED hits for: ' + query;
  if (classification === 'LIKELY_FRED') return 'Top hit looks strong for: ' + query;
  if (classification === 'UNCERTAIN') return 'Multiple/weak hits; review titles for: ' + query;
  return 'Hits exist but look mismatched; consider non-FRED provider. Query=' + query;
}

// ------------------------
// Normalization helpers
// ------------------------
function _normalizeIndicatorForFREDQuery_(text) {
  var s = String(text || '').trim();

  // If the pattern contains regex anchors / escapes, de-regex it hard
  // Remove anchors and common regex constructs
  s = s.replace(/^\^+|\$+$/g, '');
  s = s.replace(/\\b/g, ' ');
  s = s.replace(/\\s\+/g, ' ');
  s = s.replace(/\\s\*/g, ' ');
  s = s.replace(/\.\*/g, ' ');

  // Remove remaining regex metacharacters and backslashes
  s = s.replace(/[\\^$.*+?()[\]{}|]/g, ' ');

  // Strip trailing date fragments like "(Oct/04)" or "(Jan/16)" etc.
  s = s.replace(/\(\s*[A-Za-z]{3}\s*\/\s*\d{1,2}\s*\)\s*$/g, '').trim();

  // Remove extra punctuation that hurts search
  s = s.replace(/[(){}\[\]]/g, ' ');
  s = s.replace(/[\-_/]+/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();

  // Light expansions for common terms
  s = s.replace(/\bNFP\b/gi, 'nonfarm payroll');
  s = s.replace(/\bCPI\b/gi, 'consumer price index');
  s = s.replace(/\bPPI\b/gi, 'producer price index');
  s = s.replace(/\bPMI\b/gi, 'pmi');
  s = s.replace(/\bMoM\b/gi, 'month over month');
  s = s.replace(/\bYoY\b/gi, 'year over year');

  return s;
}

function _tokens_(s) {
  return String(s || '')
    .toLowerCase()
    .split(/[^a-z0-9%]+/g)
    .filter(function(t){ return t && t.length >= 3; })
    .slice(0, 20);
}

function _tokenOverlap_(tokens, hay) {
  if (!tokens || !tokens.length) return 0;
  var count = 0;
  for (var i=0; i<tokens.length; i++) {
    if (hay.indexOf(tokens[i]) >= 0) count++;
  }
  return count;
}

// ------------------------
// Header / write utilities
// ------------------------
function _hdrIndex_(headers) {
  var map = {};
  for (var i=0; i<headers.length; i++) {
    var k = String(headers[i] || '').trim().toLowerCase();
    if (k) map[k] = i;
  }
  return function(name) {
    return map[String(name || '').trim().toLowerCase()] != null ? map[String(name || '').trim().toLowerCase()] : -1;
  };
}

function _ensureHeaders_(sheet, headers, need) {
  var existing = {};
  headers.forEach(function(h, i){
    existing[String(h || '').trim().toLowerCase()] = i;
  });

  var changed = false;
  var add = [];
  need.forEach(function(h){
    var key = String(h).trim().toLowerCase();
    if (existing[key] == null) {
      add.push(h);
      changed = true;
    }
  });

  if (changed) {
    sheet.getRange(1, headers.length + 1, 1, add.length).setValues([add]);
    headers = headers.concat(add);
  }

  var out = _indexMapFromHeaders_(headers, need);
  out._headersChanged = changed;
  return out;
}

function _indexMapFromHeaders_(headers, need) {
  var map = {};
  var lower = headers.map(function(h){ return String(h || '').trim().toLowerCase(); });
  need.forEach(function(h){
    var key = String(h).trim().toLowerCase();
    map[h] = lower.indexOf(key);
  });
  return map;
}

function _queueWrite_(writes, row1, col1, value) {
  writes.push({ r: row1, c: col1, v: value });
}

function _applyWrites_(sheet, writes) {
  // Group writes by row to reduce calls
  var byRow = {};
  writes.forEach(function(w){
    byRow[w.r] = byRow[w.r] || [];
    byRow[w.r].push(w);
  });

  Object.keys(byRow).forEach(function(rStr){
    var r = Number(rStr);
    var rowWrites = byRow[r].sort(function(a,b){ return a.c - b.c; });

    var minC = rowWrites[0].c;
    var maxC = rowWrites[rowWrites.length - 1].c;
    var width = maxC - minC + 1;

    // Read existing cells so we don't wipe unrelated columns.
    var existing = sheet.getRange(r, minC, 1, width).getValues()[0];

    // Apply only the queued writes
    rowWrites.forEach(function(w){
      existing[w.c - minC] = w.v;
    });

    sheet.getRange(r, minC, 1, width).setValues([existing]);
  });
}
