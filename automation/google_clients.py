import json
import os
import socket
import time
import fcntl
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httplib2
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


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
DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC = int(os.environ.get("PRESIGNAL_SCRIPT_HTTP_TIMEOUT_SEC", "300"))
DEFAULT_API_RETRY_COUNT = int(os.environ.get("PRESIGNAL_API_RETRY_COUNT", "4"))
DEFAULT_API_RETRY_SLEEP_SEC = float(os.environ.get("PRESIGNAL_API_RETRY_SLEEP_SEC", "2"))
FORCE_GOOGLE_API_IPV4 = os.environ.get("PRESIGNAL_FORCE_GOOGLE_API_IPV4", "1") == "1"
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/script.deployments",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.scriptapp",
    "https://www.googleapis.com/auth/script.container.ui",
]


GOOGLE_API_HOST_SUFFIXES = (
    ".googleapis.com",
    ".googleusercontent.com",
)


class GoogleCredentialError(RuntimeError):
    """Credential failure with a stable, non-secret classification."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def atomic_write_json(path: Path, value: str) -> None:
    """Persist a token without exposing readers to a partial JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    os.replace(temporary, path)


class CredentialRefreshLock:
    """An OS-backed lock scoped only to the shared OAuth token refresh."""

    def __init__(self, path: Path = TOKEN_PATH):
        self.path = path.with_suffix(path.suffix + ".refresh.lock")
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()


def classify_google_exception(exc: Exception) -> dict[str, Any]:
    """Classify shared Google/App Script transport errors without provider labels."""
    message = str(exc)
    lower = message.lower()
    result: dict[str, Any] = {"exception_type": type(exc).__name__, "message": message, "http_status": None, "google_reason": None, "retry_eligible": False, "dispatch_certainty": "UNKNOWN"}
    if isinstance(exc, GoogleCredentialError):
        result.update({"category": exc.code, "dispatch_certainty": "CONFIRMED_NOT_SENT"})
        return result
    if isinstance(exc, RefreshError):
        result.update({"category": "GOOGLE_OAUTH_INVALID_GRANT" if "invalid_grant" in lower else "GOOGLE_OAUTH_REFRESH_FAILED", "dispatch_certainty": "CONFIRMED_NOT_SENT"})
        return result
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None)
        result["http_status"] = status
        try:
            body = json.loads(exc.content.decode("utf-8"))
            errors = body.get("error", {}).get("errors", [])
            result["google_reason"] = errors[0].get("reason") if errors else body.get("error", {}).get("status")
        except Exception:
            pass
        if status in {403, 429} and str(result["google_reason"]).lower() in {"quotaexceeded", "ratelimitexceeded"}:
            result["category"] = "GOOGLE_API_QUOTA"; result["retry_eligible"] = True
        elif status == 429:
            result["category"] = "GOOGLE_API_RATE_LIMIT"; result["retry_eligible"] = True
        elif status in {408, 504}:
            result["category"] = "GOOGLE_API_TIMEOUT"; result["retry_eligible"] = True
        else:
            result["category"] = "APPS_SCRIPT_EXECUTION_ERROR"
        return result
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in lower:
        result.update({"category": "GOOGLE_API_TIMEOUT", "retry_eligible": True, "dispatch_certainty": "UNKNOWN"})
    elif any(marker in lower for marker in ("nodename", "connection", "name or service not known", "network is unreachable")):
        result.update({"category": "GOOGLE_API_CONNECTION_ERROR", "retry_eligible": True, "dispatch_certainty": "CONFIRMED_NOT_SENT"})
    else:
        result["category"] = "UNKNOWN_SHARED_TRANSPORT_ERROR"
    return result


class _GoogleApiIPv4Only:
    def __enter__(self):
        if not FORCE_GOOGLE_API_IPV4:
            self._original_getaddrinfo = None
            return self

        self._original_getaddrinfo = socket.getaddrinfo

        def _ipv4_first_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            host_text = str(host or "")
            if host_text.endswith(GOOGLE_API_HOST_SUFFIXES) and family in (0, socket.AF_UNSPEC):
                return self._original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            return self._original_getaddrinfo(host, port, family, type, proto, flags)

        socket.getaddrinfo = _ipv4_first_getaddrinfo
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._original_getaddrinfo is not None:
            socket.getaddrinfo = self._original_getaddrinfo


def default_script_id() -> str:
    override = (
        os.environ.get("PRESIGNAL_SCRIPT_ID")
        or os.environ.get("PRESIGNAL_DEPLOYMENT_ID")
        or os.environ.get("PRESIGNAL_EXECUTION_ID")
    )
    if override:
        return str(override).strip()
    data = json.loads(CLASP_PATH.read_text())
    return str(data["scriptId"])


def _missing_scopes(creds: Credentials) -> List[str]:
    existing = set(creds.scopes or [])
    return [scope for scope in SCOPES if scope not in existing]


def load_credentials(interactive: bool = False) -> Credentials:
    creds: Optional[Credentials] = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as exc:
            raise GoogleCredentialError("CREDENTIAL_FILE_CORRUPTION", "Google token file cannot be read: " + type(exc).__name__) from exc

    if creds and creds.valid and not _missing_scopes(creds):
        return creds

    if creds and _missing_scopes(creds):
        raise GoogleCredentialError("GOOGLE_OAUTH_WRONG_SCOPES", "Google token is missing required scopes.")

    if creds and creds.expired and not creds.refresh_token:
        raise GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "Google access token is expired and no refresh token is available.")

    if creds and creds.expired and creds.refresh_token and not _missing_scopes(creds):
        try:
            with CredentialRefreshLock():
                # A waiting process must reload rather than overwrite a newer refresh.
                current = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
                if current.valid and not _missing_scopes(current):
                    return current
                with _GoogleApiIPv4Only():
                    current.refresh(Request())
                if not current.valid:
                    raise GoogleCredentialError("GOOGLE_OAUTH_REFRESH_FAILED", "Google refresh returned an invalid credential.")
                atomic_write_json(TOKEN_PATH, current.to_json())
                persisted = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
                if not persisted.valid or _missing_scopes(persisted):
                    raise GoogleCredentialError("TOKEN_PERSISTENCE_FAILURE", "Refreshed Google token did not persist as a valid credential.")
                return persisted
        except GoogleCredentialError:
            raise
        except RefreshError as exc:
            code = "GOOGLE_OAUTH_INVALID_GRANT" if "invalid_grant" in str(exc).lower() else "GOOGLE_OAUTH_REFRESH_FAILED"
            raise GoogleCredentialError(code, "Google credential refresh failed: " + str(exc)) from exc
        except Exception as exc:
            classified = classify_google_exception(exc)
            raise GoogleCredentialError(classified["category"], "Google credential refresh transport failed: " + type(exc).__name__) from exc

    if not interactive:
        raise GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING",
            "Missing or insufficient Google API token. "
            "Run `python3 auth_sheets.py` once to bootstrap persistent auth.")

    return _run_interactive_authorization()


def _run_interactive_authorization() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", include_granted_scopes="true")
    atomic_write_json(TOKEN_PATH, creds.to_json())
    return creds


def bootstrap_credentials() -> Credentials:
    """Acquire credentials interactively when a saved refresh grant is revoked.

    Noninteractive callers retain their strict invalid-grant failure.  The
    operator-only bootstrap command is the sole path permitted to replace a
    revoked persistent token with a newly consented one.
    """
    try:
        return load_credentials(interactive=True)
    except GoogleCredentialError as exc:
        if exc.code != "GOOGLE_OAUTH_INVALID_GRANT":
            raise
        return _run_interactive_authorization()


def build_sheets_service(creds: Credentials):
    with _GoogleApiIPv4Only():
        http = AuthorizedHttp(creds, http=httplib2.Http(timeout=DEFAULT_SHEETS_HTTP_TIMEOUT_SEC))
        return build("sheets", "v4", http=http, cache_discovery=False)


def build_script_service(creds: Credentials, timeout_seconds: Optional[int] = None):
    """Build an Apps Script client with an explicit request-layer timeout."""
    timeout = DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC if timeout_seconds is None else int(timeout_seconds)
    if timeout <= 0:
        raise ValueError("Script HTTP timeout must be positive")
    with _GoogleApiIPv4Only():
        http = AuthorizedHttp(creds, http=httplib2.Http(timeout=timeout))
        return build("script", "v1", http=http, cache_discovery=False)


def run_script_function(
    script_service,
    script_id: str,
    function_name: str,
    parameters: Optional[Iterable[Any]] = None,
    dev_mode: bool = True,
) -> Any:
    # Apps Script API executable deployment ids (AKfy...) cannot run in devMode.
    if str(script_id or "").startswith("AKfy"):
        dev_mode = False
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


def run_script_function_with_metadata(script_service, script_id: str, function_name: str, parameters: Optional[Iterable[Any]] = None, dev_mode: bool = True) -> dict[str, Any]:
    """Execute an idempotent function with non-secret request/response metadata."""
    request = {"function": function_name, "parameters": list(parameters or []), "devMode": bool(dev_mode and not str(script_id or "").startswith("AKfy"))}
    started = time.time()
    try:
        response = script_service.scripts().run(scriptId=script_id, body=request).execute()
    except Exception as exc:
        return {"ok": False, "request": request, "elapsed_ms": int((time.time() - started) * 1000), "classification": classify_google_exception(exc), "response": None}
    if "error" in response:
        details = response["error"].get("details", [{}])[0]
        return {"ok": False, "request": request, "elapsed_ms": int((time.time() - started) * 1000), "classification": {"category": "APPS_SCRIPT_EXECUTION_ERROR", "exception_type": "APPS_SCRIPT_ERROR", "message": details.get("errorMessage") or str(response["error"]), "http_status": None, "google_reason": None, "retry_eligible": False, "dispatch_certainty": "CONFIRMED_RESPONSE"}, "response": response}
    return {"ok": True, "request": request, "elapsed_ms": int((time.time() - started) * 1000), "classification": {"category": "READY", "dispatch_certainty": "CONFIRMED_RESPONSE"}, "response": response, "result": response.get("response", {}).get("result")}


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
