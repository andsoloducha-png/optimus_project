# Sorter Monitor

Skrypt do cyklicznego pobierania dziennych plików `alarmlog` z 6 sorterów przez SFTP, filtrowania i analizy alarmów w `pandas`, a następnie eksportu wyników do **Google Sheets** i/lub **PostgreSQL**.

Projekt przygotowany pod **Windows Task Scheduler**.

---

## Co robi skrypt

Przy każdym uruchomieniu:

1. Łączy się z 6 sorterami po SFTP
2. Wyszukuje dzisiejsze pliki `*_alarmlog*`
3. Czyta je **w pamięci** - bez zapisu lokalnego
4. Analizuje dane w `pandas`
5. Buduje agregaty zmianowe `alarm_shifts` oraz pojedyncze zdarzenia `alarm_events`
6. Wysyła dane do Google Sheets - jako jedna z opcji
7. Zapisuje pojedyncze zdarzenia do PostgreSQL - jako jedna z opcji

---

## Struktura projektu

```
sorter_monitor/
├─ requirements.txt
├─ config.py
├─ fetch_sftp.py
├─ schedule_guard.py
├─ analysis.py
├─ google_sheets.py
├─ state_cache.py
├─ postgres_export.py
├─ skrypty_google_sheets/
│  ├─ Kod.gs.txt
│  └─ Czyszczenie.gs.txt
├─ tests/
├─ main.py
└─ README.md
```

---

## Wymagania i instalacja

**Wymagania:**
- Python 3.10+
- Dostęp sieciowy do sorterów po SFTP
- Konto serwisowe Google 
- PostgreSQL (opcjonalnie)

**Instalacja:**

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

**`requirements.txt`:**

```
pandas
paramiko
google-api-python-client
google-auth
psycopg[binary]
```

---

## Konfiguracja

Cała konfiguracja siedzi w `config.py`.

### Główne flagi

| Flaga | Opis |
|---|---|
| `ENABLE_GOOGLE_SHEETS_EXPORT` | `True` - wysyła dane do Google Sheets |
| `ENABLE_POSTGRES_EXPORT` | `True` - zapisuje eventy do PostgreSQL |
| `ENABLE_SCHEDULE_GUARD` | `True` - skrypt sprawdza okno czasu pracy |
| `ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD` | `True` - pomija upload gdy dane się nie zmieniły |

### Sortery

```python
SORTERS = {
    "SO20": "10.21.204.101",
    "SO25": "10.21.204.151",
    "SO30": "10.21.204.121",
    "SO35": "10.21.204.136",
    "SO40": "10.21.204.171",
    "SO45": "10.21.204.186",
}

USERNAME  = os.getenv("SORTER_SFTP_USERNAME", "")
PASSWORD  = os.getenv("SORTER_SFTP_PASSWORD", "")
PORT      = 22
REMOTE_DIR = "."
```

Hasło przez zmienną środowiskową (PowerShell):

```powershell
$env:SORTER_SFTP_PASSWORD="twoje_haslo"
$env:SORTER_SFTP_USERNAME="twoj_login"
```

### Format `sorter_id`

```python
SORTER_ID_FORMAT = "number"   # - 20
# SORTER_ID_FORMAT = "so"     # - SO20
```

### Tryb nazwy alarmu

```python
ALARM_NAME_MODE = "first_word"   # - Whisker
# ALARM_NAME_MODE = "two_words"  # - Whisker activated
# ALARM_NAME_MODE = "full_text"  # - pełny tekst
```

### Filtrowane kody alarmów

```python
NR_LIST = [35, 37, 38, 53, 201]
```

### Godziny zmian

```python
SHIFT_1_START = "06:07:00"
SHIFT_1_END   = "14:15:00"
SHIFT_2_START = "14:20:00"
SHIFT_2_END   = "22:30:00"
```

### Guard czasu pracy

Gdy `ENABLE_SCHEDULE_GUARD = True`, skrypt nie wykona pracy w niedzielę ani między 23:00 a 06:00.

```python
DISABLED_WEEKDAYS = {6}          # 0=Pon, 6=Ndz
DISABLED_HOURS    = [(0, 6), (23, 24)]
```

---

## Google Sheets

```python
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
SCOPES               = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID       = os.getenv("GOOGLE_SPREADSHEET_ID", "")
```

> Arkusz musi być udostępniony e-mailowi konta serwisowego z pliku JSON.

Przykład zmiennych środowiskowych (PowerShell):

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_FILE="C:\sciezka\do\service-account.json"
$env:GOOGLE_SPREADSHEET_ID="id_arkusza"
```

Zakładki tworzone automatycznie (nie trzeba ich tworzyć ręcznie):

| Zakładka | Zawartość |
|---|---|
| `alarm_shifts` | Agregaty zmianowe: `date, shift, sorter_id, code, name, cnt, duration` |
| `alarm_events` | Pojedyncze zdarzenia: `event_ts, sorter_id, code, full_name, duration, event_start_ts` |
| `alarm_meta` | Metadane SFTP: `sorter_id, host, filename, remote_path, size_bytes, status` |

### Skrypty Apps Script

Folder `skrypty_google_sheets` zawiera skrypty uruchamiane po stronie arkusza:

- `Kod.gs.txt` archiwizuje dane do `alarm_shift_db` i `alarm_events_db`, synchronizuje nagłówki, dodaje brakującą kolumnę `event_start_ts` i uzupełnia ją w historycznych wierszach.
- `Czyszczenie.gs.txt` usuwa dane starsze niż skonfigurowany okres. Dla zdarzeń używa `event_start_ts`, a w starszych wierszach bez tej wartości korzysta z `event_ts`.

Składnię i funkcje pomocnicze można sprawdzić lokalnie:

```powershell
node tests/test_google_sheets_scripts.js
```

### Pomijanie uploadu gdy brak zmian

Gdy `ENABLE_SKIP_UNCHANGED_SHEETS_UPLOAD = True`, skrypt liczy hash danych i porównuje z poprzednim stanem zapisanym w `last_upload_state.json`. Jeśli nic się nie zmieniło — Sheets nie jest aktualizowany.

Aby wymusić pełny upload, usuń plik `last_upload_state.json`.

---

## PostgreSQL

```python
POSTGRES_HOST     = os.getenv("SORTER_PG_HOST", "")
POSTGRES_PORT     = int(os.getenv("SORTER_PG_PORT", "5432"))
POSTGRES_DB       = os.getenv("SORTER_PG_DB", "postgres")
POSTGRES_USER     = os.getenv("SORTER_PG_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("SORTER_PG_PASSWORD", "")
POSTGRES_SCHEMA   = os.getenv("SORTER_PG_SCHEMA", "public")
POSTGRES_TABLE_EVENTS = os.getenv("SORTER_PG_TABLE_EVENTS", "alarm_events")
```

Do PostgreSQL trafiają tylko pojedyncze eventy (`alarm_shifts` nie są zapisywane).

Kolumna `event_start_ts` jest dodawana automatycznie także do istniejącej tabeli.

### Tryby historii

| Ustawienie | Zachowanie |
|---|---|
| `POSTGRES_REPLACE_TODAY = False` | Dopisuje eventy; dla duplikatów aktualizuje `event_start_ts` |
| `POSTGRES_REPLACE_TODAY = True` | Usuwa i wstawia rekordy z bieżącego dnia od nowa |

Jeśli istniała stara tabela `alarm_events` z inną strukturą (np. z kolumną `shift`):

```sql
DROP TABLE IF EXISTS public.alarm_events;
```

Tabela zostanie odtworzona automatycznie przy następnym uruchomieniu.

---

## Logika czasu i nazw

### Format `duration`

Format wejściowy w logach: `MM:SS:CC` (minuty : sekundy : centysekundy).

```
52:44:85  →  52 minuty, 44.85 sekundy
```

Wynik końcowy formatowany do `HH:MM:SS`.

### Czas rozpoczęcia i zakończenia

W rekordzie o statusie `OK` pole czasu oznacza zakończenie zdarzenia i trafia do
`event_ts`. Czas rozpoczęcia jest obliczany z pełną precyzją jako
`event_start_ts = event_ts - duration`. Data raportowa i przypisanie do zmiany
wynikają z `event_start_ts`.

### Grupowanie w `alarm_shifts`

Grupowanie idzie po `code`, nie po `name`. Ten sam kod może mieć różne pełne treści (np. z różnymi numerami tacek). Pole `name` w agregacie jest jedynie uproszczoną reprezentacją tekstową.

---

## Obsługa błędów połączeń

Jeśli połączenie do jednego sortera się nie uda, skrypt kontynuuje pracę na danych z pozostałych. Błąd trafia do rejestru `errors`. Skrypt zatrzymuje się dopiero gdy **żaden** sorter nie zwróci danych.

---

## Uruchamianie

**Lokalnie:**

```bash
python main.py
```

**Windows Task Scheduler:**

| Pole | Wartość |
|---|---|
| Program | `C:\ścieżka\do\.venv\Scripts\python.exe` |
| Argumenty | `C:\ścieżka\do\main.py` |
| Start in | `C:\ścieżka\do\sorter_monitor` |

**Plik `.bat`:**

```bat
@echo off
cd /d C:\sciezka\do\sorter_monitor
call .venv\Scripts\activate.bat
python main.py
pause
```

---

## Tryby pracy

```python
# Tylko Google Sheets
ENABLE_GOOGLE_SHEETS_EXPORT = True
ENABLE_POSTGRES_EXPORT      = False

# Tylko PostgreSQL
ENABLE_GOOGLE_SHEETS_EXPORT = False
ENABLE_POSTGRES_EXPORT      = True

# Oba naraz
ENABLE_GOOGLE_SHEETS_EXPORT = True
ENABLE_POSTGRES_EXPORT      = True

# PostgreSQL
ENABLE_POSTGRES_EXPORT      = True
POSTGRES_REPLACE_TODAY      = False
```

---

## Przykładowe logi

```
[SORTER-MONITOR] 2026-03-23 20:46:45 | Start
[SORTER-MONITOR] 2026-03-23 20:46:48 | Pobrano dane z 6 sorterów.
[SORTER-MONITOR] 2026-03-23 20:46:48 | Wczytane rekordy: 10483
[SORTER-MONITOR] 2026-03-23 20:46:50 | Wysłano do Google Sheets: ...
[SORTER-MONITOR] 2026-03-23 20:46:50 | PostgreSQL: przetworzono 145 rekordów eventów.
[SORTER-MONITOR] 2026-03-23 20:46:50 | Koniec

[SORTER-MONITOR] ... | Brak zmian — pominięto aktualizację Google Sheets.
[SORTER-MONITOR] ... | Pominięto uruchomienie: Godzina 23:00 wpada w wyłączone okno 23:00-24:00.
```

---

## Planowana rozbudowa

- Dashboard w Grafanie na PostgreSQL
