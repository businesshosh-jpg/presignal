from automation.google_clients import (
    DEFAULT_SPREADSHEET_ID,
    TOKEN_PATH,
    bootstrap_credentials,
    build_script_service,
    build_sheets_service,
)


def main():
    creds = bootstrap_credentials()
    sheets = build_sheets_service(creds)
    build_script_service(creds)
    meta = sheets.spreadsheets().get(
        spreadsheetId=DEFAULT_SPREADSHEET_ID,
        fields="properties(title)",
    ).execute()
    print("Authorized persistent Google access for:", meta["properties"]["title"])
    print("Token saved to:", TOKEN_PATH)
    print("Scopes include Sheets + Apps Script Execution API. Future automation runs should not prompt again.")


if __name__ == "__main__":
    main()
