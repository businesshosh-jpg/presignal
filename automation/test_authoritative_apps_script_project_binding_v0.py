#!/usr/bin/env python3
"""Focused live regression check for the authoritative Apps Script binding."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_script_service, default_script_id, load_credentials
from automation.run_phase9_authoritative_historical_replay_v0 import (
    APPS_SCRIPT_PROJECT_FINGERPRINT,
    _apps_script_project_fingerprint,
)


PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
VERSION = 74
BRIDGE_SHA256 = "8a4666579ede317075c8df1ce51210793d265e5abc1cb3e246d1b7cec0060142"


def main() -> None:
    if default_script_id() != PROJECT_ID:
        raise RuntimeError("AUTHORITATIVE_APPS_SCRIPT_PROJECT_ID_MISMATCH")
    service = build_script_service(load_credentials(interactive=False), timeout_seconds=300)
    version_files = service.projects().getContent(scriptId=PROJECT_ID, versionNumber=VERSION).execute().get("files", [])
    head_files = service.projects().getContent(scriptId=PROJECT_ID).execute().get("files", [])
    version_fingerprint, version_records = _apps_script_project_fingerprint(version_files)
    head_fingerprint, head_records = _apps_script_project_fingerprint(head_files)
    if version_fingerprint != APPS_SCRIPT_PROJECT_FINGERPRINT:
        raise RuntimeError("IMMUTABLE_VERSION74_PROJECT_FINGERPRINT_MISMATCH")
    if head_fingerprint != version_fingerprint or head_records != version_records:
        raise RuntimeError("CURRENT_PROJECT_HEAD_DIFFERS_FROM_IMMUTABLE_VERSION74")
    bridge = next((row for row in version_records if row["name"] == "authoritative_provider_bridge" and row["type"] == "SERVER_JS"), None)
    if not bridge or bridge["sha256"] != BRIDGE_SHA256:
        raise RuntimeError("IMMUTABLE_VERSION74_BRIDGE_FINGERPRINT_MISMATCH")
    print("AUTHORITATIVE_APPS_SCRIPT_PROJECT_BINDING_PASS")


if __name__ == "__main__":
    main()
