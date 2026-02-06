/*********************************************************
 * Batching / ID Rules (Authoritative)
 * - Key: country + minute-level release_ts (UTC)
 * - single  → type='single',  batch_id=''
 * - member  → type='member',  shared batch_id (reused if present)
 * - batch   → synthetic (Predictions only): type='batch', event_id==batch_id
 **********************************************************/

/*******************************************************
 * runner_rules_patch.gs — authoritative post-pass
 *******************************************************/
function applyBatchingForKeys_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event');
  if (!sh) throw new Error('Event sheet missing');

  // Read headers
  var lastRow = sh.getLastRow(), lastCol = sh.getLastColumn();
  if (lastRow < 2 || lastCol < 1) return { scanned: 0, singles: 0, members: 0, assigned: 0 };
  var headers = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(function(h){return String(h).trim();});
  function col(name){ return headers.indexOf(name) + 1; } // 1-based
  var cCountry = col('country'), cInd = col('indicator_name'), cTs = col('release_ts'),
      cEvent = col('event_id'), cBatch = col('batch_id'), cType = col('type');
  if (cCountry < 1 || cInd < 1 || cTs < 1 || cEvent < 1 || cBatch < 1 || cType < 1) {
    throw new Error('Missing required columns for post-pass (need country, indicator_name, release_ts, event_id, batch_id, type)');
  }

  // Load body
  var body = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();
  var rowCount = body.length;

  // Build minute-key groups: (country, minuteUTC)
  var groups = {}; // key => [rowIdx0-based]
  for (var r = 0; r < rowCount; r++) {
    var country = String(body[r][cCountry-1] || '').toUpperCase();
    var ts = String(body[r][cTs-1] || '');
    if (!country || !ts) continue;
    // Minute key is ts to minute already; if seconds present, clamp:
    var minuteIso = ts.replace(/:\d{2}Z$/, ':00Z');
    var key = country + '|' + minuteIso;
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }

  // Deterministic UUID helpers
  function _hash_(s) {
    // Simple FNV-1a 32-bit
    var h = 0x811c9dc5;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return ('00000000' + h.toString(16)).slice(-8);
  }
  function _uuidFrom_(seed) {
    // Pseudo UUIDv4 style from hash; deterministic for same seed
    var h1 = _hash_(seed);
    var h2 = _hash_(seed + '|b');
    var h3 = _hash_(seed + '|c');
    var h4 = _hash_(seed + '|d');
    return h1.slice(0,8) + '-' + h2.slice(0,4) + '-' + h3.slice(0,4) + '-' + h4.slice(0,4) + '-' + h1.slice(0,12);
  }

  var singles = 0, members = 0, assigned = 0;

  // Assign per group
  Object.keys(groups).forEach(function(key){
    var rows = groups[key]; // indexes into body
    var batchId = (rows.length > 1) ? _uuidFrom_('batch|' + key) : '';
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var country = String(body[r][cCountry-1] || '').toUpperCase();
      var ts = String(body[r][cTs-1] || '').replace(/:\d{2}Z$/, ':00Z');
      var ind = String(body[r][cInd-1] || '');
      var evSeed = 'event|' + country + '|' + ts + '|' + ind;
      var evId = _uuidFrom_(evSeed);

      body[r][cEvent-1] = evId;
      body[r][cBatch-1] = batchId;
      if (rows.length > 1) {
        body[r][cType-1] = 'member';
        members++;
      } else {
        body[r][cType-1] = 'single';
        singles++;
      }
      assigned++;
    }
  });

  // Write back
  sh.getRange(2, 1, rowCount, lastCol).setValues(body);
  SpreadsheetApp.flush();
  return { scanned: rowCount, singles: singles, members: members, assigned: assigned };
}




/** ISO minute key in UTC: 'YYYY-MM-DDTHH:MMZ' */
function minuteKey(ts) {
  if (!ts) return '';
  var d = (ts instanceof Date) ? ts : new Date(ts);
  if (isNaN(d)) return '';
  return Utilities.formatDate(d, 'UTC', "yyyy-MM-dd'T'HH:mm'Z'");
}

/** Deterministic UUID-ish from string (for stable seeds) */
function _uuidFromString_(s) {
  s = String(s || '');
  var h = 0;
  for (var i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; }
  function seg(x){ return ('0000' + (x >>> 0).toString(16)).slice(-4); }
  return [seg(h), seg(h*13), seg(h*37), seg(h*73)].join('-');
}

/** True v4 UUID (for fresh ids) */
function _uuidv4_() {
  return String(Utilities.getUuid());
}

/** Column resolver (case-insensitive, returns 1-based col or -1) */
function _col_(headers /*lowercased*/, /*...names*/) {
  for (var i = 1; i < arguments.length; i++) {
    var n = String(arguments[i] || '').trim().toLowerCase();
    var idx = headers.indexOf(n);
    if (idx >= 0) return idx + 1;
  }
  return -1;
}

/**
 * Apply batching rules on Event for a set of affected keys:
 * keys: array of "COUNTRY|YYYY-MM-DDTHH:MMZ"
 * - Ensures event_id
 * - Sets type & batch_id per spec
 * Returns {updatedKeys:[], memberGroups:[{key,batch_id,rows:[rowNums]}]}
 */
function applyBatchingForKeys_(eventSheet, keys) {
  // 1) Resolve Event sheet if not provided (compat with Code.gs calling with no args)
  if (!eventSheet) {
    var name = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
    eventSheet = SpreadsheetApp.getActive().getSheetByName(name);
    if (!eventSheet) throw new Error('Event sheet "' + name + '" missing');
  }

  var lastRow = eventSheet.getLastRow();
  var lastCol = eventSheet.getLastColumn();
  if (lastRow < 2 || lastCol < 1) return { updatedKeys: [], memberGroups: [], scanned: 0, assigned: 0, singles: 0, members: 0 };

  // Read headers/body; use trimmed, lowercased headers for robust col lookup
  var headersRaw = eventSheet.getRange(1, 1, 1, lastCol).getValues()[0] || [];
  var headers = headersRaw.map(function(h){ return String(h || '').trim().toLowerCase(); });
  var values  = eventSheet.getRange(1, 1, lastRow, lastCol).getValues();

  // Column resolver (mirror-compatible)
  function _col_(/*headers, ...names*/) {
    for (var i = 1; i < arguments.length; i++) {
      var n = String(arguments[i] || '').trim().toLowerCase();
      var idx = headers.indexOf(n);
      if (idx >= 0) return idx + 1; // 1-based
    }
    return -1;
  }

  var C_COUNTRY   = _col_(headers, 'country');
  var C_RELEASETS = _col_(headers, 'release_ts','release_time','datetime');
  var C_TYPE      = _col_(headers, 'type','event_type');
  var C_EVENT_ID  = _col_(headers, 'event_id','id');
  var C_BATCH_ID  = _col_(headers, 'batch_id');

  if (C_COUNTRY < 1 || C_RELEASETS < 1 || C_TYPE < 1 || C_EVENT_ID < 1 || C_BATCH_ID < 1) {
    throw new Error('Post-pass missing columns (need country, release_ts, type, event_id, batch_id)');
  }

  // minuteKey helper (use your mirror’s version if already present)
  function minuteKey(ts) {
    if (!ts) return '';
    var d = (ts instanceof Date) ? ts : new Date(ts);
    if (isNaN(d)) return '';
    return Utilities.formatDate(d, 'UTC', "yyyy-MM-dd'T'HH:mm'Z'");
  }

  // Deterministic UUID helpers (use your mirror’s originals if they exist)
  function _uuidFromString_(s) {
    s = String(s || '');
    var h = 0;
    for (var i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; }
    function seg(x){ return ('0000' + (x >>> 0).toString(16)).slice(-4); }
    return [seg(h), seg(h*13), seg(h*37), seg(h*73)].join('-');
  }

  // 2) If no keys were passed, build ALL minute keys from the sheet (compat mode)
  if (!keys || !keys.length) {
    var keySet = {};
    for (var r = 2; r <= lastRow; r++) {
      var ctry = String(values[r-1][C_COUNTRY-1] || '').toUpperCase();
      var mk   = minuteKey(values[r-1][C_RELEASETS-1]);
      if (ctry && mk) keySet[ctry + '|' + mk] = true;
    }
    keys = Object.keys(keySet);
  }

  // 3) Group rows by requested keys
  var keyLookup = {};
  keys.forEach(function(k){ keyLookup[k] = true; });

  var groups = {};     // key -> [sheetRow]
  for (var i = 2; i <= lastRow; i++) {
    var row = values[i-1] || [];
    var ctry = String(row[C_COUNTRY-1] || '').toUpperCase();
    var mk   = minuteKey(row[C_RELEASETS-1]);
    var key  = ctry + '|' + mk;
    if (!keyLookup[key]) continue;
    (groups[key] = groups[key] || []).push(i);
  }

  var updates = [];
  var memberGroups = [];
  var singles = 0, members = 0, assigned = 0;

  Object.keys(groups).forEach(function(key){
    var rows = groups[key];

    // Ensure event_id exists on each row (stable per country|minute|indicator)
    rows.forEach(function(r){
      var ev = values[r-1];
      var indicator = String(ev[headers.indexOf('indicator_name')] || '');
      var evSeed = 'event|' + key + '|' + indicator;
      var currentId = String(ev[C_EVENT_ID-1] || '');
      if (!currentId) {
        updates.push({ r: r, c: C_EVENT_ID, v: _uuidFromString_(evSeed) });
        assigned++;
      }
    });

    if (rows.length === 1) {
      var r1 = rows[0];
      updates.push({ r: r1, c: C_TYPE,     v: 'single' });
      updates.push({ r: r1, c: C_BATCH_ID, v: '' });
      singles++;
    } else {
      // Shared batch_id for this minute-key
      var batchId = _uuidFromString_('batch|' + key);
      rows.forEach(function(r){
        updates.push({ r: r, c: C_TYPE,     v: 'member' });
        updates.push({ r: r, c: C_BATCH_ID, v: batchId });
        members++;
      });
      memberGroups.push({ key: key, batch_id: batchId, rows: rows.slice() });
    }
  });

  // 4) Write updates to sheet
  if (updates.length) {
    var byRow = {};
    updates.forEach(function(u){ (byRow[u.r] = byRow[u.r] || []).push(u); });
    Object.keys(byRow).forEach(function(rStr){
      var r = Number(rStr);
      byRow[r].sort(function(a,b){ return a.c - b.c; }).forEach(function(u){
        eventSheet.getRange(u.r, u.c).setValue(u.v);
      });
    });
  }

  SpreadsheetApp.flush();

  // 5) Return summary (mirror-compatible)
  return {
    updatedKeys: Object.keys(groups),
    memberGroups: memberGroups,
    scanned: lastRow - 1,
    assigned: assigned,
    singles: singles,
    members: members
  };
}


/**
 * Ensure a synthetic batch row exists in Predictions for each member group:
 * - type='batch', event_id==batch_id, batch_id=''
 * - numeric forecast fields left null
 */
function ensureBatchRowsInPredictions_(memberGroups) {
  if (!memberGroups || !memberGroups.length) return;
  var ps = (typeof getPredictionsSheet === 'function')
    ? getPredictionsSheet()
    : SpreadsheetApp.getActive().getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions');
  if (!ps) return;

  var last = ps.getLastRow();
  var vals = last >= 1 ? ps.getRange(1,1,last,ps.getLastColumn()).getValues() : [];
  var headers = (vals[0] || []).map(function(h){ return String(h||'').trim().toLowerCase(); });

  var C_TYPE      = _col_(headers, 'type','event_type');
  var C_EVENT_ID  = _col_(headers, 'event_id','id');
  var C_BATCH_ID  = _col_(headers, 'batch_id');
  var C_SOURCECAL = _col_(headers, 'source_cal','source');

  var have = {};
  if (last >= 2 && C_EVENT_ID > 0) {
    for (var r = 2; r <= last; r++) {
      var id = String(vals[r-1][C_EVENT_ID-1] || '');
      if (id) have[id] = r;
    }
  }

  var appends = [];
  (memberGroups || []).forEach(function(g){
    var bid = g.batch_id;
    if (!bid || have[bid]) return; // already present
    var row = new Array(headers.length).fill('');
    if (C_TYPE      > 0) row[C_TYPE-1]      = 'batch';
    if (C_EVENT_ID  > 0) row[C_EVENT_ID-1]  = bid;      // event_id == batch_id
    if (C_BATCH_ID  > 0) row[C_BATCH_ID-1]  = '';       // null by spec
    if (C_SOURCECAL > 0) row[C_SOURCECAL-1] = 'synthetic';
    appends.push(row);
    have[bid] = true;
  });

  if (appends.length) {
    ps.getRange(ps.getLastRow()+1, 1, appends.length, headers.length).setValues(appends);
  }
}
