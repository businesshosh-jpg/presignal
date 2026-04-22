import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BASE_DIR = os.path.dirname(__file__)
CREDENTIALS_PATH = os.path.join(BASE_DIR, "local", "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "local", "token.json")
SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"


def load_or_authorize_credentials():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as token:
        token.write(creds.to_json())

    return creds


def main():
    creds = load_or_authorize_credentials()
    service = build("sheets", "v4", credentials=creds)
    meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        fields="properties(title)",
    ).execute()
    print("Authorized Sheets access for:", meta["properties"]["title"])
    print("Token saved to:", TOKEN_PATH)


if __name__ == "__main__":
    main()
