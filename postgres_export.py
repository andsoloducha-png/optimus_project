import pandas as pd
from psycopg import connect
from psycopg.rows import dict_row

from config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SCHEMA,
    POSTGRES_TABLE_EVENTS,
    POSTGRES_REPLACE_TODAY,
)


def get_pg_conn():
    return connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        row_factory=dict_row,
    )


def ensure_events_table(conn):
    full_table = f'"{POSTGRES_SCHEMA}"."{POSTGRES_TABLE_EVENTS}"'

    sql = f"""
    CREATE SCHEMA IF NOT EXISTS "{POSTGRES_SCHEMA}";

    CREATE TABLE IF NOT EXISTS {full_table} (
        event_ts timestamp not null,
        sorter_id text not null,
        code integer,
        full_name text,
        duration text,
        created_at timestamp not null default now(),
        CONSTRAINT uq_{POSTGRES_TABLE_EVENTS}_event
            UNIQUE (event_ts, sorter_id, code, full_name, duration)
    );

    CREATE INDEX IF NOT EXISTS idx_{POSTGRES_TABLE_EVENTS}_event_ts
        ON {full_table}(event_ts);

    CREATE INDEX IF NOT EXISTS idx_{POSTGRES_TABLE_EVENTS}_sorter_code
        ON {full_table}(sorter_id, code);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def replace_today_events(conn, events_df):
    if events_df.empty:
        return 0

    full_table = f'"{POSTGRES_SCHEMA}"."{POSTGRES_TABLE_EVENTS}"'

    event_dates = sorted({
        ts.date()
        for ts in events_df["event_ts"].dropna().tolist()
        if pd.notna(ts)
    })

    rows = []
    for _, row in events_df.iterrows():
        event_ts = row["event_ts"]
        if pd.isna(event_ts):
            continue

        code_val = row["code"]
        code_out = None if pd.isna(code_val) else int(code_val)

        rows.append(
            (
                event_ts.to_pydatetime(),
                str(row["sorter_id"]),
                code_out,
                str(row["full_name"]),
                str(row["duration"]),
            )
        )

    if not rows:
        return 0

    with conn.cursor() as cur:
        if POSTGRES_REPLACE_TODAY and event_dates:
            for event_date in event_dates:
                cur.execute(
                    f"DELETE FROM {full_table} WHERE event_ts::date = %s",
                    (event_date,)
                )

        cur.executemany(
            f"""
            INSERT INTO {full_table}
                (event_ts, sorter_id, code, full_name, duration)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_ts, sorter_id, code, full_name, duration)
            DO NOTHING
            """,
            rows
        )

    conn.commit()
    return len(rows)


def export_events_to_postgres(events_df):
    if events_df.empty:
        return 0

    with get_pg_conn() as conn:
        ensure_events_table(conn)
        inserted = replace_today_events(conn, events_df)

    return inserted