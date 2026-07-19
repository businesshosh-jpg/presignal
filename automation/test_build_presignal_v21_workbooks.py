#!/usr/bin/env python3
"""Targeted package-level checks for PreSignal v2.1 foundation workbooks."""

from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from automation.build_presignal_v21_workbooks import (
    MAIN_SHEETS,
    MAIN_TARGET,
    OUTPUT_DIR,
    PROHIBITED_MAIN_SHEETS,
    RESEARCH_SHEETS,
    RESEARCH_TARGET,
    inspect_xlsx,
)

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def cell_column(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for letter in letters:
        result = result * 26 + ord(letter.upper()) - 64
    return result


def shared_strings(archive: zipfile.ZipFile):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//main:t", NS)) for item in root.findall("main:si", NS)]


def header_rows(path: Path):
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        result = {}
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            xml_path = targets[relation_id].lstrip("/")
            if not xml_path.startswith("xl/"):
                xml_path = "xl/" + xml_path
            root = ET.fromstring(archive.read(xml_path))
            first_row = root.find("main:sheetData/main:row", NS)
            values = {}
            for cell in first_row.findall("main:c", NS):
                kind = cell.attrib.get("t")
                raw = cell.findtext("main:v", default="", namespaces=NS)
                if kind == "s":
                    value = strings[int(raw)]
                elif kind == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//main:t", NS))
                else:
                    value = raw
                values[cell_column(cell.attrib["r"])] = value
            result[sheet.attrib["name"]] = [values[index] for index in range(1, max(values, default=0) + 1)]
        return result


def worksheet_text(path: Path, sheet_name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        sheet = next(item for item in workbook.findall("main:sheets/main:sheet", NS) if item.attrib["name"] == sheet_name)
        relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        xml_path = targets[relation_id].lstrip("/")
        if not xml_path.startswith("xl/"):
            xml_path = "xl/" + xml_path
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8", "replace") if "xl/sharedStrings.xml" in archive.namelist() else ""
        return shared + "\n" + archive.read(xml_path).decode("utf-8", "replace")


class PreSignalV21WorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MAIN_TARGET.exists() or not RESEARCH_TARGET.exists():
            raise unittest.SkipTest("Run automation/build_presignal_v21_workbooks.py before package checks.")
        cls.main = inspect_xlsx(MAIN_TARGET)
        cls.research = inspect_xlsx(RESEARCH_TARGET)
        cls.headers = {**header_rows(MAIN_TARGET), **header_rows(RESEARCH_TARGET)}
        cls.manifest = __import__("json").loads((OUTPUT_DIR / "migration_manifest.json").read_text())

    def test_exact_sheet_inventory_and_order(self):
        self.assertEqual([sheet["name"] for sheet in self.main["sheets"]], MAIN_SHEETS)
        self.assertEqual([sheet["name"] for sheet in self.research["sheets"]], RESEARCH_SHEETS)

    def test_no_prohibited_or_hidden_sheets(self):
        self.assertFalse(set(sheet["name"] for sheet in self.main["sheets"]) & PROHIBITED_MAIN_SHEETS)
        self.assertFalse(any(sheet["hidden"] for sheet in self.main["sheets"] + self.research["sheets"]))

    def test_no_formulas_external_links_connections_or_named_ranges(self):
        for workbook in (self.main, self.research):
            self.assertEqual(workbook["external_links"], 0)
            self.assertEqual(workbook["workbook_connections"], 0)
            self.assertEqual(workbook["named_ranges"], [])
            self.assertFalse(any(sheet["formula_count"] for sheet in workbook["sheets"]))

    def test_headers_are_unique(self):
        for name, header in self.headers.items():
            self.assertEqual(len(header), len(set(header)), name)
            self.assertTrue(all(header), name)

    def test_fresh_tables_have_headers_only(self):
        fresh = {"SeriesMap_Suggestions", "Information", "Prediction", "Prediction_Path", "Evaluation", "Session_Map", "Run_Log"}
        for sheet in self.main["sheets"]:
            if sheet["name"] in fresh:
                self.assertEqual(sheet["row_count"], 1, sheet["name"])
        populated = {sheet["name"]: sheet["row_count"] for sheet in self.main["sheets"] if sheet["name"] in {"Episode", "Outcome"}}
        self.assertEqual(populated, {"Episode": 1683, "Outcome": 1683})
        self.assertTrue(all(sheet["row_count"] == 1 for sheet in self.research["sheets"]))

    def test_reusable_row_counts_reconcile(self):
        for details in self.manifest["migration"]["reusable_row_counts"].values():
            self.assertEqual(details["source_rows"], details["target_rows"])

    def test_schema_records_inheritance(self):
        schema_sheet = next(sheet for sheet in self.main["sheets"] if sheet["name"] == "Schema")
        self.assertGreater(schema_sheet["row_count"], 20)
        self.assertEqual(self.headers["Schema"][:5], ["schema_version", "parent_schema_version", "schema_section", "schema_item", "change_status"])
        schema_text = worksheet_text(MAIN_TARGET, "Schema")
        for marker in ("INHERITED", "MODIFIED", "NEW", "RETIRED", "EPISODE_REACTION_DIRECTION_15M"):
            self.assertIn(marker, schema_text)


if __name__ == "__main__":
    unittest.main()
