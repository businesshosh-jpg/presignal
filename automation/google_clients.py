import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httplib2
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = ROOT / "local"
CREDENTIALS_PATH = LOCAL_DIR / "credentials.json"
TOKEN_PATH = LOCAL_DIR / "token.json"
CLASP_PATH = ROOT / "apps_script" / ".clasp.json"

DEFAULT_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_SPREADSHEET_ID",
    "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q",
)
DEFAULT_HTTP_TIMEOUT_SEC = int(os.environ.get("PRESIGNAL_HTTP_TIMEOUT_SEC", "300"))
DEFAULT_SHEETS_HTTP_TIMEOUT_SEC = int(os.environ.get("PRESIGNAL_SHEETS_HTTP_TIMEOUT_SEC", str(DEFAULT_HTTP_TIMEOUT_SEC)))
DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC = int(os.environ.get("PRESIGNAL_SCRIPT_HTTP_TIMEOUT_SEC", "180"))
DEFAULT_API_RETRY_COUNT = int(os.environ.get("PRESIGNAL_API_RETRY_COUNT", "4"))
DEFAULT_API_RETRY_SLEEP_SEC = float(os.environ.get("PRESIGNAL_API_RETRY_SLEEP_SEC", "2"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.scriptapp",
]


def default_script_id() -> str:
    data = json.loads(CLASP_PATH.read_text())
    return str(data["scriptId"])


def _missing_scopes(creds: Credentials) -> List[str]:
    existing = set(creds.scopes or [])
    return [scope for scope in SCOPES if scope not in existing]


def load_credentials(interactive: bool = False) -> Credentials:
    creds: Optional[Credentials] = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid and not _missing_scopes(creds):
        return creds

    if creds and creds.expired and creds.refresh_token and not _missing_scopes(creds):
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
            return creds
        except RefreshError:
            creds = None

    if not interactive:
        raise RuntimeError(
            "Missing or insufficient Google API token. "
            "Run `python3 auth_sheets.py` once to bootstrap persistent auth."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def bootstrap_credentials() -> Credentials:
    return load_credentials(interactive=True)


def build_sheets_service(creds: Credentials):
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=DEFAULT_SHEETS_HTTP_TIMEOUT_SEC))
    return build("sheets", "v4", http=http, cache_discovery=False)


def build_script_service(creds: Credentials):
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC))
    return build("script", "v1", http=http, cache_discovery=False)


def run_script_function(
    script_service,
    script_id: str,
    function_name: str,
    parameters: Optional[Iterable[Any]] = None,
    dev_mode: bool = True,
) -> Any:
    body: Dict[str, Any] = {
        "function": function_name,
        "parameters": list(parameters or []),
        "devMode": dev_mode,
    }
    resp = script_service.scripts().run(scriptId=script_id, body=body).execute()
    if "error" in resp:
        err = resp["error"].get("details", [{}])[0]
        raise RuntimeError(
            f"Apps Script error in {function_name}: "
            f"{err.get('errorMessage') or resp['error']}"
        )
    return resp.get("response", {}).get("result")


def get_sheet_values(
    sheets_service,
    spreadsheet_id: str,
    range_a1: str,
) -> List[List[Any]]:
    last_err = None
    for attempt in range(max(1, DEFAULT_API_RETRY_COUNT)):
        try:
            return (
                sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_a1)
                .execute()
                .get("values", [])
            )
        except Exception as exc:
            last_err = exc
            if attempt >= max(1, DEFAULT_API_RETRY_COUNT) - 1:
                break
            time.sleep(DEFAULT_API_RETRY_SLEEP_SEC * (attempt + 1))
    raise last_err


def batch_update_values(
    sheets_service,
    spreadsheet_id: str,
    data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    last_err = None
    for attempt in range(max(1, DEFAULT_API_RETRY_COUNT)):
        try:
            return (
                sheets_service.spreadsheets()
                .values()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"valueInputOption": "RAW", "data": data},
                )
                .execute()
            )
        except Exception as exc:
            last_err = exc
            if attempt >= max(1, DEFAULT_API_RETRY_COUNT) - 1:
                break
            time.sleep(DEFAULT_API_RETRY_SLEEP_SEC * (attempt + 1))
    raise last_err
