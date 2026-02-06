/** 00_logging_shim.gs — load first so logging is always available **/

// If CFG isn't ready yet, we still log using whatever sheet is passed in.
if (typeof getSheet !== 'function') {
  function getSheet(name) {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    return ss.getSheetByName(name);                            // ✅ no insert
  }
}
if (typeof getHeaderNames !== 'function') {
  function getHeaderNames(sheet) {
    if (!sheet || sheet.getLastRow() < 1) return [];
    return sheet.getRange(1,1,1, sheet.getLastColumn())
                .getValues()[0]
                .map(h => String(h).trim());
  }
}


if (typeof ensureHeaders !== 'function') {
  function ensureHeaders(sheet, headers) {
    const existing = getHeaderNames(sheet);
    if (existing.length === 0) {
      sheet.getRange(1,1,1, headers.length).setValues([headers]);
      return;
    }
    // Fill any missing header cells (left to right) without shifting columns
    const row = sheet.getRange(1,1,1, Math.max(existing.length, headers.length)).getValues()[0];
    let changed = false;
    for (let i = 0; i < headers.length; i++) {
      if (!row[i]) { row[i] = headers[i]; changed = true; }
    }
    if (changed) sheet.getRange(1,1,1, row.length).setValues([row]);
  }
}

// --- Script property helper (shared) ---
// Safe wrapper around PropertiesService.getScriptProperties()
if (typeof getScriptProperty_ !== 'function') {
  function getScriptProperty_(key, defaultValue) {
    if (!key) return defaultValue || null;
    try {
      var props = PropertiesService.getScriptProperties();
      var v = props.getProperty(String(key));
      if (v === null || v === undefined || v === '') {
        return (defaultValue !== undefined) ? defaultValue : null;
      }
      return v;
    } catch (e) {
      // As a fallback, just return defaultValue and log to Logger
      try {
        Logger.log('[getScriptProperty_] error for key %s: %s', key, String(e));
      } catch (_) {}
      return (defaultValue !== undefined) ? defaultValue : null;
    }
  }
}



if (typeof appendLog !== 'function') {
  var LOG_HEADERS = ['ts','level','message','context_json'];

  // ---- FAST buffered logging (drop-in) ----
  var __LOG_BUF__ = [];
  var __LOG_SHEET__ = null;
  var __LOG_HEADERS_OK__ = false;
  var __LOG_MAX_BUF__ = 40; // flush every N rows (tune 20-80)

  function appendLog(a, b, c, d) {
    var sheet, level, message, context;

    // Style 1: appendLog(sheet, level, message, context)
    if (a && typeof a.appendRow === 'function') {
      sheet = a; level = b; message = c; context = d;

    // Style 2: appendLog(level, message, context)
    } else {
      level = a; message = b; context = c;

      // Prefer CFG.LOG_SHEET_NAME if present, else default to "log"
      var ss = SpreadsheetApp.getActiveSpreadsheet();
      var sheetName = (typeof CFG !== 'undefined' && CFG && CFG.LOG_SHEET_NAME) ? CFG.LOG_SHEET_NAME : 'log';
      sheet = ss.getSheetByName(sheetName) || ss.getSheetByName('log');
      if (!sheet) return; // no place to log
    }

    // Cache the sheet we are logging to (most runs use one sheet)
    if (!__LOG_SHEET__) __LOG_SHEET__ = sheet;

    // Ensure headers only once per execution
    if (!__LOG_HEADERS_OK__) {
      try { ensureHeaders(sheet, LOG_HEADERS); } catch (e) { /* best effort */ }
      __LOG_HEADERS_OK__ = true;
    }

    // Safe stringify (avoids circular; truncates)
    var ctx = '';
    try {
      var seen = new WeakSet();
      ctx = JSON.stringify(context || {}, function(k, v) {
        if (v && typeof v === 'object') {
          if (seen.has(v)) return '[circular]';
          seen.add(v);
        }
        if (typeof v === 'string' && v.length > 2000) return v.slice(0, 2000) + '…[truncated]';
        return v;
      });
      if (ctx.length > 8000) ctx = ctx.slice(0, 8000) + '…[truncated]';
    } catch (e) {
      ctx = String(context || '');
    }

    __LOG_BUF__.push([new Date().toISOString(), String(level||''), String(message||''), ctx]);

    // Flush immediately on error to avoid losing critical logs
    if (String(level).toLowerCase() === 'error') {
      flushLogs_();
      return;
    }

    // Flush in batches to avoid appendRow slowdowns
    if (__LOG_BUF__.length >= __LOG_MAX_BUF__) flushLogs_();
  }

  function flushLogs_() {
    if (!__LOG_SHEET__ || __LOG_BUF__.length === 0) return;

    try {
      var sheet = __LOG_SHEET__;
      var startRow = sheet.getLastRow() + 1;
      var numRows = __LOG_BUF__.length;
      var numCols = __LOG_BUF__[0].length;
      sheet.getRange(startRow, 1, numRows, numCols).setValues(__LOG_BUF__);
    } catch (e) {
      // If bulk write fails, drop the buffer (avoid infinite slowdown)
    } finally {
      __LOG_BUF__ = [];
    }
  }
}


// Lightweight wrapper so other modules can call log_(category, label, payload)
if (typeof log_ !== 'function') {
  function log_(category, label, payload) {
    var sheetName = (typeof CFG !== 'undefined' && CFG && CFG.SHEET_LOG)
      ? CFG.SHEET_LOG
      : 'log';

    var sheet = getSheet(sheetName);
    if (!sheet) {
      // As a fallback, just send to Logger so we don't crash.
      try {
        Logger.log('[%s] %s %s', category, label, JSON.stringify(payload || {}));
      } catch (e) {}
      return;
    }

    // Map our usage log_('scoring','computed_move',{...})
    // -> appendLog(logSheet, level='scoring', message='computed_move', context=payload)
    appendLog(sheet, String(category || 'INFO'), String(label || ''), payload || {});
  }
}

