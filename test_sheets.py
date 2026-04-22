import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# If modifying scopes, delete token.json
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

BASE_DIR = os.path.dirname(__file__)
CREDENTIALS_PATH = os.path.join(BASE_DIR, "local", "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "local", "token.json")

def main():
    creds = None

    # Load token if exists
    if os.path.exists(TOKEN_PATH):
        import json
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If no valid creds, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    # Connect to Sheets API
    service = build('sheets', 'v4', credentials=creds)

    # 👉 PUT YOUR SHEET ID HERE
    SPREADSHEET_ID = '1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q'
    RANGE = 'Config!B2'

    # Read value
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE
    ).execute()

    print("Read from sheet:", result.get('values'))

    # Write value
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE,
        valueInputOption='RAW',
        body={'values': [['Hello from Python 🚀']]}
    ).execute()

    print("Write complete!")

if __name__ == '__main__':
    main()
