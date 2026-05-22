from google.oauth2 import service_account
from googleapiclient.discovery import build


def get_sheets_service(service_account_file: str, scopes: list):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=scopes,
    )
    return build("sheets", "v4", credentials=credentials)


def get_spreadsheet(spreadsheets_service, spreadsheet_id: str):
    return spreadsheets_service.get(spreadsheetId=spreadsheet_id).execute()


def ensure_worksheet_exists(spreadsheets_service, spreadsheet_id: str, sheet_name: str):
    spreadsheet = get_spreadsheet(spreadsheets_service, spreadsheet_id)
    existing_titles = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

    if sheet_name in existing_titles:
        return

    body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": sheet_name
                    }
                }
            }
        ]
    }
    spreadsheets_service.batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()


def clear_sheet(values_service, spreadsheet_id: str, sheet_name: str):
    values_service.clear(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        body={}
    ).execute()


def write_values(values_service, spreadsheet_id: str, sheet_name: str, values: list):
    if not values:
        values = [["Brak danych"]]

    body = {"values": values}
    values_service.update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body=body
    ).execute()


def dataframe_to_values(df):
    header = list(df.columns)
    rows = df.values.tolist()
    return [header] + rows


def upload_result_sets(
    service_account_file: str,
    scopes: list,
    spreadsheet_id: str,
    shifts_sheet_name: str,
    events_sheet_name: str,
    meta_sheet_name: str,
    shifts_df,
    events_df,
    meta_rows,
):
    service = get_sheets_service(service_account_file, scopes)
    spreadsheets_service = service.spreadsheets()
    values_service = spreadsheets_service.values()

    for sheet_name in [shifts_sheet_name, events_sheet_name, meta_sheet_name]:
        ensure_worksheet_exists(spreadsheets_service, spreadsheet_id, sheet_name)

    clear_sheet(values_service, spreadsheet_id, shifts_sheet_name)
    clear_sheet(values_service, spreadsheet_id, events_sheet_name)
    clear_sheet(values_service, spreadsheet_id, meta_sheet_name)

    write_values(values_service, spreadsheet_id, shifts_sheet_name, dataframe_to_values(shifts_df))
    write_values(values_service, spreadsheet_id, events_sheet_name, dataframe_to_values(events_df))
    write_values(values_service, spreadsheet_id, meta_sheet_name, meta_rows)