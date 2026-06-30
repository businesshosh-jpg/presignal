/*************************************************************
 * config.gs — single source of truth for time/window inputs
 * Reads from the optional Config sheet first, then Script Properties.
 * Exposes resolveWindow_(moduleName) → {fromUtcIso, toUtcIso, tz, windowEnabled, note}
 *
 * Expected keys:
 *  - WINDOW_ENABLED    → TRUE / FALSE
 *  - WINDOW_FROM_LOCAL → "YYYY-MM-DD HH:mm" (local wall clock)
 *  - WINDOW_TO_LOCAL   → "YYYY-MM-DD HH:mm" (local wall clock)
 *  - WINDOW_TZ         → IANA, e.g., "Asia/Tokyo" (default)
 *************************************************************/

/** Sheet name for human-editable settings (optional). */
var CONFIG_SHEET_NAME = 'Config';

/** Fallback workbook ids for non-active execution contexts. */
var CONFIG_WORKBOOK_ID_FALLBACKS = {
  main_spreadsheet_id: '1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q',
  diagnostics_spreadsheet_id: '1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0',
  overview_spreadsheet_id: '1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo',
  archive_spreadsheet_id: '12hi1rugE_F-MhlupgmL13BIagerzA8CZkm1sk_nHPSg',
  archive_01_spreadsheet_id: '12hi1rugE_F-MhlupgmL13BIagerzA8CZkm1sk_nHPSg'
};

function _configWorkbookIdFallback_(key) {
  var normalized = String(key || '').trim().toLowerCase();
  if (!normalized) return '';
  try {
    var props = PropertiesService.getScriptProperties();
    if (props) {
      var candidates = [
        normalized,
        normalized.toUpperCase(),
        normalized.replace(/_01_/g, '_')
      ];
      for (var i = 0; i < candidates.length; i++) {
        var candidate = String(candidates[i] || '').trim();
        if (!candidate) continue;
        var value = String(props.getProperty(candidate) || '').trim();
        if (value) return value;
      }
    }
  } catch (e) {}
  return String(CONFIG_WORKBOOK_ID_FALLBACKS[normalized] || '').trim();
}

/** Read config map from the Config sheet, if present. Lower-cases keys. */
function _readConfigSheetMap_() {
  var mainId = _configWorkbookIdFallback_('MAIN_SPREADSHEET_ID');
  if (!mainId) return null;
  var ss = SpreadsheetApp.openById(mainId);
  var sh = ss.getSheetByName(CONFIG_SHEET_NAME);
  if (!sh) return null;

  var values = sh.getDataRange().getValues();
  var displayValues = sh.getDataRange().getDisplayValues();
  if (!values || values.length < 2) return null;

  var map = {};
  for (var r = 1; r < values.length; r++) {
    var k = String(values[r][0] || '').trim();
    if (!k) continue;
    var v = values[r][1];
    if (v instanceof Date && isFinite(v.getTime())) {
      v = _normalizeConfigDateCell_(v, displayValues && displayValues[r] && displayValues[r][1]);
    } else if (typeof v === 'string') {
      v = _normalizeConfigDateDisplay_(v.trim()) || v.trim();
    }
    map[k.toLowerCase()] = v;
  }
  return map;
}

function _normalizeConfigDateCell_(dateValue, displayValue) {
  var normalizedDisplay = _normalizeConfigDateDisplay_(displayValue);
  if (normalizedDisplay) return normalizedDisplay;
  return Utilities.formatDate(dateValue, 'UTC', 'yyyy-MM-dd HH:mm');
}

function _normalizeConfigDateDisplay_(value) {
  var s = String(value || '').trim();
  if (!s) return '';
  var iso = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::\d{2})?)?$/);
  if (iso) {
    return _configDatePartsToLocalString_(iso[1], iso[2], iso[3], iso[4], iso[5]);
  }
  var slash = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[ T](\d{1,2}):(\d{2})(?::\d{2})?)?$/);
  if (slash) {
    return _configDatePartsToLocalString_(slash[3], slash[1], slash[2], slash[4], slash[5]);
  }
  return '';
}

function _configDatePartsToLocalString_(year, month, day, hour, minute) {
  return [
    String(year).padStart(4, '0'),
    String(month).padStart(2, '0'),
    String(day).padStart(2, '0')
  ].join('-') + ' ' + String(hour || '0').padStart(2, '0') + ':' + String(minute || '0').padStart(2, '0');
}

/** Read Script Properties as a map. Lower-cases keys. */
function _readScriptPropsMap_() {
  var props = PropertiesService.getScriptProperties().getProperties() || {};
  var map = {};
  for (var k in props) {
    if (!props.hasOwnProperty(k)) continue;
    map[k.toLowerCase()] = String(props[k] || '').trim();
  }
  return map;
}

/** Coerce "TRUE"/"FALSE"/boolean to boolean. */
function _asBool_(v) {
  if (typeof v === 'boolean') return v;
  var s = String(v || '').trim().toLowerCase();
  if (!s) return false;
  return (s === 'true' || s === '1' || s === 'yes' || s === 'y');
}

/** Format a Date → ISO minute string in Z (UTC), like "2025-10-15T14:59Z". */
function _toIsoMinuteZ_(d) {
  var s = new Date(d.getTime());
  // strip seconds/millis
  s.setUTCSeconds(0); s.setUTCMilliseconds(0);
  var iso = s.toISOString(); // "YYYY-MM-DDTHH:MM:SS.mmmZ"
  return iso.slice(0, 16) + 'Z'; // keep minute precision
}

/**
 * Parse "YYYY-MM-DD HH:mm" in a given IANA TZ (local wall time) and return ISO minute in UTC.
 * Works across DST by deriving the offset at that instant.
 */
/**
 * Accepts:
 *  - Date object (from a Sheets datetime cell)
 *  - "YYYY-MM-DD HH:mm"
 * Returns ISO minute (UTC), e.g., "2025-07-01T00:00Z".
 */
function _parseLocalToUtcIsoMinute_(localInput, tz) {
  // 1) If it's already a Date, format it to the canonical local pattern
  if (localInput instanceof Date && isFinite(localInput.getTime())) {
    var localStr = Utilities.formatDate(localInput, tz, 'yyyy-MM-dd HH:mm');
    return _parseLocalToUtcIsoMinute_(localStr, tz); // recurse with normalized string
  }

  var s = String(localInput || '').trim();

  // 2) If it's in the canonical "YYYY-MM-DD HH:mm", parse directly
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$/);
  if (m) {
    var y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]), h = Number(m[4]), mi = Number(m[5]);

    // Construct a UTC instant for those local wall components, then derive the TZ offset at that moment
    var tentativeUtcMs = Date.UTC(y, mo - 1, d, h, mi, 0, 0);
    var tentativeDate = new Date(tentativeUtcMs);

    // Offset like +0900 / -0700 for that tz at that moment
    var z = Utilities.formatDate(tentativeDate, tz, 'Z');
    var sign = (z[0] === '-') ? -1 : 1;
    var oh = Number(z.slice(1, 3));
    var om = Number(z.slice(3, 5));
    var offsetMinutes = sign * (oh * 60 + om);

    var trueUtcMs = tentativeUtcMs - offsetMinutes * 60000;
    return _toIsoMinuteZ_(new Date(trueUtcMs));
  }

  throw new Error('Invalid local datetime format (expected YYYY-MM-DD HH:mm or Date cell): ' + s);
}


/**
 * Resolve time window for any module.
 * Priority: Config sheet → Script Properties → disabled (caller uses fallback).
 *
 * @param {string} moduleName Just for logging/toast notes
 * @returns {{fromUtcIso:string, toUtcIso:string, tz:string, windowEnabled:boolean, note:string}}
 */
function resolveWindow_(moduleName) {
  var sheetMap = _readConfigSheetMap_();
  var propMap  = _readScriptPropsMap_();

  // Prefer sheet if present and has values; else props.
  var src = (sheetMap && Object.keys(sheetMap).length) ? sheetMap : propMap;

  var enabled = _asBool_(src['window_enabled']);
  var tz = String(src['window_tz'] || 'Asia/Tokyo').trim();

  var fromLocal = src['window_from_local'];
  var toLocal   = src['window_to_local'];

  // If disabled or missing FROM, we return windowEnabled=false so callers use their fallback.
  if (!enabled || !fromLocal) {
    return {
      fromUtcIso: null,
      toUtcIso: null,
      tz: tz,
      windowEnabled: false,
      note: 'window:disabled or missing FROM'
    };
  }
  if (!toLocal) {
    throw new Error('Config: WINDOW_TO_LOCAL is required when WINDOW_ENABLED is TRUE.');
  }

  var fromIso = _parseLocalToUtcIsoMinute_(fromLocal, tz);
  var toIso   = _parseLocalToUtcIsoMinute_(toLocal, tz);

  if (fromIso >= toIso) {
    throw new Error('Config: FROM must be earlier than TO. Got FROM=' + fromIso + ' TO=' + toIso);
  }

  var note = 'module=' + String(moduleName || '') + ' local=[' + fromLocal + ' → ' + toLocal + ' ' + tz + '] ' +
             'utc=[' + fromIso + ' → ' + toIso + ']';

  // Optional toast so you can see what was applied at run-time.
  try {
    SpreadsheetApp.getActive().toast('Window set ' + note, 'Window', 5);
  } catch (_) {
    // ignore if no UI (e.g., trigger)
  }

  return {
    fromUtcIso: fromIso,
    toUtcIso: toIso,
    tz: tz,
    windowEnabled: true,
    note: note
  };
}

/** (Optional) helper to save props if you later add a "Set Window…" UI. */
function saveWindowConfigToProps_(enabled, fromLocal, toLocal, tz) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty('WINDOW_ENABLED', String(!!enabled));
  if (fromLocal != null) props.setProperty('WINDOW_FROM_LOCAL', String(fromLocal));
  if (toLocal   != null) props.setProperty('WINDOW_TO_LOCAL',   String(toLocal));
  if (tz        != null) props.setProperty('WINDOW_TZ',         String(tz));
}
