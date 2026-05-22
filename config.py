import os

# Główne flagi funkcjonalne
ENABLE_GOOGLE_SHEETS_EXPORT = False
ENABLE_POSTGRES_EXPORT = True
ENABLE_SCHEDULE_GUARD = True

# Jeśli True, to przy braku zmian nie wysyłamy ponownie do Google Sheets
ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD = True


# Okno pracy produkcji
# Produkcja nie idzie:
# - w niedzielę
# - między 23:00 a 06:00
#
# Python weekday():
# Monday=0 ... Sunday=6
DISABLED_WEEKDAYS = {6}  # niedziela
DISABLED_HOURS = [
    (0, 6),   # 00:00-05:59
    (23, 24), # 23:00-23:59
]


# SFTP / sortery
USERNAME = os.getenv("SORTER_SFTP_USERNAME", "")
PASSWORD = os.getenv("SORTER_SFTP_PASSWORD", "")
PORT = 22
REMOTE_DIR = "."

SORTERS = {
    "SO20": "10.21.204.101",
    "SO25": "10.21.204.151",
    "SO30": "10.21.204.121",
    "SO35": "10.21.204.136",
    "SO40": "10.21.204.171",
    "SO45": "10.21.204.186",
}

# Analiza
NR_LIST = [35, 37, 38, 53, 201]

SHIFT_1_START = "06:07:00"
SHIFT_1_END = "14:15:00"
SHIFT_2_START = "14:20:00"
SHIFT_2_END = "22:30:00"

# Jak budować nazwę błędu:
# "first_word"  -> tylko pierwsze słowo
# "two_words"   -> dwa pierwsze słowa
# "full_text"   -> cały alarm
ALARM_NAME_MODE = "first_word"

# Jak ma wyglądać sorter_id w wynikach:
# "number" -> 20
# "so"     -> SO20
SORTER_ID_FORMAT = "number"

# Google Sheets
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")

SHEET_SHIFTS = "alarm_shifts"
SHEET_EVENTS = "alarm_events"
SHEET_META = "alarm_meta"


# PostgreSQL
POSTGRES_HOST = os.getenv("SORTER_PG_HOST", "")
POSTGRES_PORT = int(os.getenv("SORTER_PG_PORT", "5432"))
POSTGRES_DB = os.getenv("SORTER_PG_DB", "postgres")
POSTGRES_USER = os.getenv("SORTER_PG_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("SORTER_PG_PASSWORD", "")
POSTGRES_SCHEMA = os.getenv("SORTER_PG_SCHEMA", "public")
POSTGRES_TABLE_EVENTS = os.getenv("SORTER_PG_TABLE_EVENTS", "alarm_events")

# usunąć dzisiejsze rekordy i wstawić aktualny stan na nowo.
POSTGRES_REPLACE_TODAY = False


# Dodatkowe
TIMEOUT_SEC = 20
LOG_PREFIX = "[SORTER-MONITOR]"
