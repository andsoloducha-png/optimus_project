import csv
import io

import pandas as pd

from config import (
    SHIFT_1_START,
    SHIFT_1_END,
    SHIFT_2_START,
    SHIFT_2_END,
    ALARM_NAME_MODE,
    SORTER_ID_FORMAT,
)

SHIFT_RESULT_COLUMNS = ["date", "shift", "sorter_id", "code", "name", "cnt", "duration"]
EVENT_RESULT_COLUMNS = ["event_ts", "sorter_id", "code", "full_name", "duration"]


def _parse_duration_to_seconds(value):
    """
    MM:SS:CC
    MM = minuty, nie godziny
    """
    if pd.isna(value):
        return 0.0

    text = str(value).strip()
    if not text:
        return 0.0

    parts = text.split(":")
    if len(parts) != 3:
        return 0.0

    try:
        minutes = float(parts[0])
        seconds = float(parts[1])
        centiseconds = float(parts[2])
        return (minutes * 60.0) + seconds + (centiseconds / 100.0)
    except ValueError:
        return 0.0


def _format_duration(total_seconds):
    if pd.isna(total_seconds):
        total_seconds = 0.0

    rounded = int(round(float(total_seconds)))
    hours = rounded // 3600
    minutes = (rounded % 3600) // 60
    seconds = rounded % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_alarm_name(text: str, mode: str = ALARM_NAME_MODE) -> str:
    """
    ŁATWA ZMIANA ZWROTNEJ NAZWY BŁĘDU:

    mode = "first_word"  -> tylko pierwsze słowo
    mode = "two_words"   -> dwa pierwsze słowa
    mode = "full_text"   -> cały tekst alarmu

    Najprościej zmienisz to w config.py przez ALARM_NAME_MODE.
    """
    if text is None:
        return ""

    text = str(text).strip()
    if not text:
        return ""

    parts = text.split()

    if mode == "full_text":
        return text

    if mode == "two_words":
        return " ".join(parts[:2])

    return parts[0] if parts else ""


def _extract_date_from_filename(filename: str) -> str:
    return filename.split("_")[0]


def normalize_sorter_id(sorter_name: str) -> str:
    sorter_name = str(sorter_name).strip()

    if SORTER_ID_FORMAT == "so":
        return sorter_name

    return sorter_name.replace("SO", "")


def parse_single_log_to_rows(content: str, sorter_name: str, filename: str):
    date_part = _extract_date_from_filename(filename)
    rows = []

    reader = csv.reader(io.StringIO(content), delimiter=";")
    for raw_row in reader:
        if len(raw_row) < 5:
            continue

        start, status, nr, alarm, duration = raw_row[:5]

        try:
            nr_val = int(str(nr).strip())
        except ValueError:
            continue

        rows.append(
            {
                "sorter_id": normalize_sorter_id(sorter_name),
                "start": str(start).strip(),
                "status": str(status).strip(),
                "nr": nr_val,
                "alarm": str(alarm).strip(),
                "duration": str(duration).strip(),
                "date": date_part,   # YYYY-MM-DD
            }
        )

    return rows


def build_dataframe_from_remote_logs(remote_logs: dict) -> pd.DataFrame:
    all_rows = []

    for sorter_name, payload in remote_logs.items():
        content = payload["content"]
        filename = payload["filename"]
        rows = parse_single_log_to_rows(content=content, sorter_name=sorter_name, filename=filename)
        all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame(columns=["sorter_id", "start", "status", "nr", "alarm", "duration", "date"])

    return pd.DataFrame(all_rows)


def prepare_dataframe_for_analysis(df: pd.DataFrame, nr_list: list[int]) -> pd.DataFrame:
    columns = [
        "date",
        "start",
        "sorter_id",
        "shift",
        "nr",
        "name",
        "full_name",
        "duration_raw",
        "dur_sec",
        "event_ts",
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    work["start"] = work["start"].astype(str).str.slice(0, 8)

    work["shift"] = pd.NA
    shift1_mask = work["start"].between(SHIFT_1_START, SHIFT_1_END)
    shift2_mask = work["start"].between(SHIFT_2_START, SHIFT_2_END)

    work.loc[shift1_mask, "shift"] = 1
    work.loc[shift2_mask, "shift"] = 2

    work = work[
        (work["status"] == "OK")
        & (work["nr"].isin(nr_list))
        & (work["shift"].notna())
    ].copy()

    if work.empty:
        return pd.DataFrame(columns=columns)

    work["name"] = work["alarm"].map(lambda x: build_alarm_name(x, ALARM_NAME_MODE))
    work["full_name"] = work["alarm"].astype(str)
    work["duration_raw"] = work["duration"].astype(str)
    work["dur_sec"] = work["duration"].map(_parse_duration_to_seconds)

    # timestamp pod bazę / BI
    work["event_ts"] = work["date"].astype(str) + " " + work["start"].astype(str)

    work["nr"] = work["nr"].astype(int)
    work["shift"] = work["shift"].astype(int)

    return work[columns]


def run_query_shifts(df: pd.DataFrame, nr_list: list[int]) -> pd.DataFrame:
    durations = prepare_dataframe_for_analysis(df, nr_list)
    if durations.empty:
        return pd.DataFrame(columns=SHIFT_RESULT_COLUMNS)

    # agregacja po code, nie po name
    result = (
        durations.groupby(["date", "shift", "sorter_id", "nr"], as_index=False)
        .agg(
            name=("name", "first"),
            cnt=("nr", "size"),
            dur_sec=("dur_sec", "sum"),
        )
        .rename(columns={"nr": "code"})
        .sort_values(by=["date", "shift", "sorter_id", "code"], ascending=[True, True, True, True])
    )

    result["duration"] = result["dur_sec"].map(_format_duration)

    return result[SHIFT_RESULT_COLUMNS].copy()


def build_event_records(df: pd.DataFrame, nr_list: list[int]) -> pd.DataFrame:
    """
    Pojedyncze rekordy zdarzeń:
    - timestamp zamiast osobno date/start
    - bez kolumny name
    - bez kolumny shift
    - duration w formacie HH:MM:SS
    """
    events = prepare_dataframe_for_analysis(df, nr_list)
    if events.empty:
        return pd.DataFrame(columns=EVENT_RESULT_COLUMNS)

    result = events.copy()
    result = result.rename(columns={"nr": "code"})
    result["duration"] = result["dur_sec"].map(_format_duration)

    result = result.sort_values(
        by=["event_ts", "sorter_id", "code"],
        ascending=[True, True, True]
    )

    return result[EVENT_RESULT_COLUMNS].copy()


def dataframe_for_sheet(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()

    for col in out.columns:
        if col == "cnt":
            out[col] = out[col].astype(int)
        else:
            out[col] = out[col].astype(str)

    return out


def dataframe_for_postgres_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Przygotowanie eventów do bazy:
    - event_ts jako datetime
    - code jako liczba
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    out["event_ts"] = pd.to_datetime(out["event_ts"], errors="coerce")
    out["sorter_id"] = out["sorter_id"].astype(str)
    out["code"] = pd.to_numeric(out["code"], errors="coerce").astype("Int64")
    out["full_name"] = out["full_name"].astype(str)
    out["duration"] = out["duration"].astype(str)

    return out


def build_meta_rows(remote_logs: dict, errors: dict):
    rows = [["sorter_id", "host", "filename", "remote_path", "size_bytes", "status"]]

    seen = set()

    for sorter_name, payload in remote_logs.items():
        rows.append([
            normalize_sorter_id(sorter_name),
            payload.get("host", ""),
            payload.get("filename", ""),
            payload.get("remote_path", ""),
            str(payload.get("size", "")),
            "OK",
        ])
        seen.add(sorter_name)

    for sorter_name, err in errors.items():
        if sorter_name in seen:
            continue
        rows.append([normalize_sorter_id(sorter_name), "", "", "", "", f"ERROR: {err}"])

    return rows