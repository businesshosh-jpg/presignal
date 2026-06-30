/*******************************************************
 * direct_expression_diagnostics_migration.js
 * - One-time workbook-location repair for Direct Expression diagnostics tabs
 * - Moves misplaced Direct Expression tabs into the diagnostics workbook
 * - No provider calls, no predictions, no methodology changes
 *******************************************************/

function migrateDirectExpressionDiagnosticsSheetsToDiagnostics_(params) {
  params = params || {};
  var warnings = [];
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();

  var mainSs = getMainSpreadsheet_();
  if (!mainSs) {
    throw new Error('Direct Expression diagnostics migration requires main workbook access.');
  }
  var diagnosticsSs = getDiagnosticsSpreadsheet_();
  if (!diagnosticsSs) {
    throw new Error('Direct Expression diagnostics migration requires diagnostics workbook access.');
  }

  var sheetNames = [
    'Provider_Character_Direct_Expression_Capture',
    'Provider_Character_Direct_Expression_Clusters',
    'Provider_Character_Direct_Expression_Summary',
    'Provider_Character_Direct_Expression_Methodology',
    'Provider_Character_Diagnostics'
  ];

  var moved = [];
  var alreadyThere = [];
  var missing = [];

  for (var i = 0; i < sheetNames.length; i++) {
    var sheetName = sheetNames[i];
    var sourceSheet = mainSs.getSheetByName(sheetName);
    var targetSheet = diagnosticsSs.getSheetByName(sheetName);

    if (!sourceSheet && targetSheet) {
      alreadyThere.push(sheetName);
      continue;
    }
    if (!sourceSheet) {
      missing.push(sheetName);
      warnings.push('missing_source_sheet:' + sheetName);
      continue;
    }

    if (targetSheet) {
      diagnosticsSs.deleteSheet(targetSheet);
    }

    var copied = sourceSheet.copyTo(diagnosticsSs);
    copied.setName(sheetName);
    mainSs.deleteSheet(sourceSheet);
    moved.push(sheetName);
  }

  return {
    status: 'ok',
    generated_ts: generatedTs,
    moved_sheets: moved,
    already_in_diagnostics: alreadyThere,
    missing_source_sheets: missing,
    warnings: _uniqueStrings_(warnings)
  };
}

function migrateDirectExpressionDiagnosticsSheetsToDiagnostics(params) {
  return migrateDirectExpressionDiagnosticsSheetsToDiagnostics_(params || {});
}

