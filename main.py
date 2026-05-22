from datetime import datetime

from config import (
    USERNAME,
    PASSWORD,
    PORT,
    SORTERS,
    REMOTE_DIR,
    NR_LIST,
    SERVICE_ACCOUNT_FILE,
    SCOPES,
    SPREADSHEET_ID,
    SHEET_SHIFTS,
    SHEET_EVENTS,
    SHEET_META,
    LOG_PREFIX,
    ENABLE_GOOGLE_SHEETS_EXPORT,
    ENABLE_POSTGRES_EXPORT,
    ENABLE_SCHEDULE_GUARD,
    ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD,
)
from fetch_sftp import fetch_today_logs_from_all_sorters
from analysis import (
    build_dataframe_from_remote_logs,
    run_query_shifts,
    build_event_records,
    dataframe_for_sheet,
    dataframe_for_postgres_events,
    build_meta_rows,
)
from schedule_guard import is_now_in_disabled_window


def log(message: str):
    print(f"{LOG_PREFIX} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {message}")


def main():
    if ENABLE_SCHEDULE_GUARD:
        blocked, reason = is_now_in_disabled_window()
        if blocked:
            log(f"Pominięto uruchomienie: {reason}")
            return

    if not USERNAME:
        raise ValueError("Brak loginu SFTP. Ustaw zmienną środowiskową SORTER_SFTP_USERNAME.")

    if not PASSWORD:
        raise ValueError(
            "Brak hasła SFTP. Ustaw zmienną środowiskową SORTER_SFTP_PASSWORD "
        )

    log("Start")

    remote_logs, errors = fetch_today_logs_from_all_sorters(
        sorters=SORTERS,
        username=USERNAME,
        password=PASSWORD,
        port=PORT,
        remote_dir=REMOTE_DIR,
    )

    if not remote_logs:
        log("Nie udało się pobrać żadnego pliku.")
        for sorter_name, err in errors.items():
            log(f"{sorter_name}: {err}")
        raise RuntimeError("Brak danych z sorterów.")

    log(f"Pobrano dane z {len(remote_logs)} sorterów.")
    for sorter_name, payload in remote_logs.items():
        log(f"{sorter_name}: {payload['filename']} ({payload['size']} B)")

    if errors:
        for sorter_name, err in errors.items():
            log(f"{sorter_name}: ERROR: {err}")

    raw_df = build_dataframe_from_remote_logs(remote_logs)
    log(f"Wczytane rekordy: {len(raw_df)}")

    shifts_df = run_query_shifts(raw_df, NR_LIST)
    events_df = build_event_records(raw_df, NR_LIST)

    shifts_sheet_df = dataframe_for_sheet(shifts_df)
    events_sheet_df = dataframe_for_sheet(events_df)
    events_pg_df = dataframe_for_postgres_events(events_df)
    meta_rows = build_meta_rows(remote_logs, errors)

    # Google Sheets
    if ENABLE_GOOGLE_SHEETS_EXPORT:
        from google_sheets import upload_result_sets, dataframe_to_values

        should_upload = True

        if ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD:
            from state_cache import calculate_payload_hash, load_last_hash, save_last_hash

            shifts_values = dataframe_to_values(shifts_sheet_df)
            events_values = dataframe_to_values(events_sheet_df)

            current_hash = calculate_payload_hash(
                shifts_values=shifts_values,
                events_values=events_values,
            )
            last_hash = load_last_hash()

            if current_hash == last_hash:
                should_upload = False
                log("Brak zmian — pominięto aktualizację Google Sheets.")

        if should_upload:
            upload_result_sets(
                service_account_file=SERVICE_ACCOUNT_FILE,
                scopes=SCOPES,
                spreadsheet_id=SPREADSHEET_ID,
                shifts_sheet_name=SHEET_SHIFTS,
                events_sheet_name=SHEET_EVENTS,
                meta_sheet_name=SHEET_META,
                shifts_df=shifts_sheet_df,
                events_df=events_sheet_df,
                meta_rows=meta_rows,
            )
            log(f"Wysłano do Google Sheets: {SPREADSHEET_ID}")

            if ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD:
                from state_cache import calculate_payload_hash, save_last_hash
                shifts_values = dataframe_to_values(shifts_sheet_df)
                events_values = dataframe_to_values(events_sheet_df)
                current_hash = calculate_payload_hash(shifts_values, events_values)
                save_last_hash(current_hash)

        log(f"Wiersze shifts: {len(shifts_sheet_df)}")
        log(f"Wiersze events: {len(events_sheet_df)}")

    else:
        log("Eksport do Google Sheets: WYŁĄCZONY")

    # PostgreSQL – tylko eventy
    if ENABLE_POSTGRES_EXPORT:
        from postgres_export import export_events_to_postgres

        inserted = export_events_to_postgres(events_pg_df)
        log(f"PostgreSQL: zapisano {inserted} rekordów eventów.")
    else:
        log("Eksport do PostgreSQL: WYŁĄCZONY")

    log("Koniec")


if __name__ == "__main__":
    main()
