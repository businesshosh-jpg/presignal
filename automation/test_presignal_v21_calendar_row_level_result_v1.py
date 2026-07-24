import unittest

from automation import presignal_v21_calendar_row_level_result_v1 as contract


def event(index: int, disposition: str = "UPDATED"):
    release = "2026-07-%02dT12:30:00Z" % (24 + index // 20)
    country, indicator = "US", "Event %03d" % index
    identity = country + "|" + indicator + "|" + release
    return {"event_identity": identity, "country": country, "indicator_name": indicator, "release_ts": release, "source_identity": "FMP", "content_checksum": "sha256:%064x" % index, "write_disposition": disposition}


class CalendarRowLevelResultTest(unittest.TestCase):
    def test_ninety_one_events_are_complete_sorted_and_checksum_stable(self):
        rows = sorted([event(index) for index in range(91)], key=contract.ordering_key)
        value = {"canonical_events": rows, "canonical_event_count": 91, "inserted_count": 0, "updated_count": 91, "unchanged_count": 0, "failed_count": 0, "canonical_event_set_checksum": contract.sha(rows)}
        self.assertEqual(len(contract.validate_result(value)), 91)
        self.assertEqual(value["canonical_event_set_checksum"], contract.sha(rows))

    def test_transport_key_reordering_does_not_change_declared_checksum(self):
        row = event(1)
        transported = {"country": row["country"], "source_identity": row["source_identity"], "content_checksum": row["content_checksum"], "release_ts": row["release_ts"], "indicator_name": row["indicator_name"], "event_identity": row["event_identity"], "write_disposition": row["write_disposition"]}
        expected = [contract.ordered_row(row)]
        value = {"canonical_events": [transported], "canonical_event_count": 1, "inserted_count": 0, "updated_count": 1, "unchanged_count": 0, "failed_count": 0, "canonical_event_set_checksum": contract.sha(expected)}
        self.assertEqual(contract.validate_result(value), expected)

    def test_same_time_events_remain_distinct_and_reconciliation_detects_deltas(self):
        first, second = event(1), event(2)
        second["release_ts"] = first["release_ts"]
        second["event_identity"] = contract.identity(second)
        result = contract.reconcile([first, second], [first])
        self.assertEqual(len(result["adapter_only"]), 1)
        self.assertFalse(result["passed"])

    def test_checksum_or_duplicate_identity_fails_closed(self):
        row = event(1)
        value = {"canonical_events": [row, dict(row)], "canonical_event_count": 2, "inserted_count": 0, "updated_count": 2, "unchanged_count": 0, "failed_count": 0, "canonical_event_set_checksum": contract.sha([row, dict(row)])}
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            contract.validate_result(value)
