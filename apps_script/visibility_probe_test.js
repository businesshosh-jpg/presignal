/*******************************************************
 * visibility_probe_test.js
 * - Harmless probe file to verify Apps Script project sync
 *******************************************************/

function testVisibilityProbe_() {
  return {
    status: 'ok',
    generated_ts: new Date().toISOString(),
    note: 'local-only change not pushed',
    probe_version: 'v4-local',
    probe_message: 'This should not appear in Apps Script yet'
  };
}
