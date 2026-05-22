from datetime import datetime

from config import DISABLED_WEEKDAYS, DISABLED_HOURS


def is_now_in_disabled_window(now: datetime | None = None) -> tuple[bool, str]:
    if now is None:
        now = datetime.now()

    weekday = now.weekday()
    hour = now.hour

    if weekday in DISABLED_WEEKDAYS:
        return True, f"Dzisiaj jest wyłączony dzień tygodnia (weekday={weekday})."

    for start_hour, end_hour in DISABLED_HOURS:
        if start_hour <= hour < end_hour:
            return True, f"Godzina {hour:02d}:00 wpada w wyłączone okno {start_hour:02d}:00-{end_hour:02d}:00."

    return False, "OK"