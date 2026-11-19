import unittest
from datetime import datetime

import pandas as pd

from analysis import (
    EVENT_RESULT_COLUMNS,
    build_dataframe_from_remote_logs,
    build_event_records,
    dataframe_for_postgres_events,
    run_query_shifts,
)
from postgres_export import ensure_events_table, replace_today_events


def dataframe_from_log(content: str, filename: str = "2026-02-19_alarmlog.txt"):
    return build_dataframe_from_remote_logs(
        {
            "SO20": {
                "content": content,
                "filename": filename,
            }
        }
    )


class EventTimestampTests(unittest.TestCase):
    def test_event_start_is_end_minus_raw_duration(self):
        raw_df = dataframe_from_log(
            "\n".join(
                [
                    "21:55:21.895;Alarm;0035;Whisker activated: 1: Unknown location.;00:00:00",
                    "21:56:00.714;OK;0035;Whisker activated: 1: Unknown location.;00:38:81",
                ]
            )
        )

        events = build_event_records(raw_df, [35])

        self.assertEqual(list(events.columns), EVENT_RESULT_COLUMNS)
        self.assertEqual(len(events), 1)
        event = events.iloc[0]
        self.assertEqual(event["event_ts"], "2026-02-19 21:56:00")
        self.assertEqual(event["event_start_ts"], "2026-02-19 21:55:21")
        self.assertEqual(event["duration"], "00:00:39")

    def test_shift_is_selected_from_event_start_not_event_end(self):
        raw_df = dataframe_from_log(
            "14:20:10.000;OK;0035;Whisker activated: 1: Unknown location.;05:20:00"
        )

        shifts = run_query_shifts(raw_df, [35])
        events = build_event_records(raw_df, [35])

        self.assertEqual(len(shifts), 1)
        self.assertEqual(int(shifts.iloc[0]["shift"]), 1)
        self.assertEqual(events.iloc[0]["event_start_ts"], "2026-02-19 14:14:50")

    def test_event_started_before_first_shift_is_excluded(self):
        raw_df = dataframe_from_log(
            "06:07:10.000;OK;0035;Whisker activated: 1: Unknown location.;00:20:00"
        )

        self.assertTrue(run_query_shifts(raw_df, [35]).empty)
        self.assertTrue(build_event_records(raw_df, [35]).empty)

    def test_reporting_date_comes_from_event_start(self):
        raw_df = dataframe_from_log(
            "06:08:00.000;OK;0035;Whisker activated: 1: Unknown location.;1440:00:00"
        )

        shifts = run_query_shifts(raw_df, [35])
        events = build_event_records(raw_df, [35])

        self.assertEqual(shifts.iloc[0]["date"], "2026-02-18")
        self.assertEqual(events.iloc[0]["event_ts"], "2026-02-19 06:08:00")
        self.assertEqual(events.iloc[0]["event_start_ts"], "2026-02-18 06:08:00")

    def test_postgres_dataframe_converts_both_timestamps(self):
        raw_df = dataframe_from_log(
            "08:55:00.000;OK;0035;Whisker activated: 1: Unknown location.;00:30:00"
        )
        events = build_event_records(raw_df, [35])

        postgres_events = dataframe_for_postgres_events(events)

        self.assertTrue(pd.api.types.is_datetime64_any_dtype(postgres_events["event_ts"]))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(postgres_events["event_start_ts"]))


class RecordingCursor:
    def __init__(self):
        self.executed = []
        self.executed_many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, rows):
        self.executed_many.append((sql, rows))


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()
        self.commit_count = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1


class PostgresTimestampTests(unittest.TestCase):
    def test_existing_table_migration_adds_start_timestamp(self):
        conn = RecordingConnection()

        ensure_events_table(conn)

        sql = conn.cursor_instance.executed[0][0]
        self.assertIn("ADD COLUMN IF NOT EXISTS event_start_ts timestamp", sql)
        self.assertIn("SET event_start_ts = event_ts - duration::interval", sql)
        self.assertIn("idx_alarm_events_event_start_ts", sql)
        self.assertEqual(conn.commit_count, 1)

    def test_insert_writes_start_and_end_timestamps(self):
        raw_df = dataframe_from_log(
            "08:55:00.000;OK;0035;Whisker activated: 1: Unknown location.;00:30:00"
        )
        events = dataframe_for_postgres_events(build_event_records(raw_df, [35]))
        conn = RecordingConnection()

        inserted = replace_today_events(conn, events)

        self.assertEqual(inserted, 1)
        sql, rows = conn.cursor_instance.executed_many[0]
        self.assertIn("event_ts, event_start_ts", sql)
        self.assertIn("DO UPDATE SET event_start_ts = EXCLUDED.event_start_ts", sql)
        self.assertIn("existing.event_start_ts IS DISTINCT FROM", sql)
        self.assertEqual(rows[0][0], datetime(2026, 2, 19, 8, 55, 0))
        self.assertEqual(rows[0][1], datetime(2026, 2, 19, 8, 54, 30))
        self.assertEqual(rows[0][2], "20")


if __name__ == "__main__":
    unittest.main()
