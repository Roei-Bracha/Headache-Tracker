# Headache Tracker Telegram Bot — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

A personal Telegram bot for daily headache tracking, producing clean structured data for neurologist review. Strict deterministic state machine — no LLM components. All flows are hardcoded ConversationHandler states.

---

## Stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| Telegram framework | python-telegram-bot v20+ (async) |
| Scheduler | PTB built-in JobQueue (backed by APScheduler) |
| Database | SQLite via stdlib `sqlite3` |
| HTTP client | httpx (async) |
| Config | python-dotenv |
| Timezone | `zoneinfo`, Asia/Jerusalem |
| Deployment | Docker + docker-compose, Proxmox LXC |

---

## Configuration & Secrets

Loaded from `.env` via python-dotenv. Bot fails fast at startup if any required var is missing.

```
TELEGRAM_BOT_TOKEN=
OWM_API_KEY=
AUTHORIZED_USER_ID=
TZ=Asia/Jerusalem
```

`.env` is excluded from git via `.gitignore`. `.env.example` is committed.

---

## Language Rule

- All **user-facing strings** (messages, button labels): **Hebrew**
- All **internal identifiers** (variables, function names, DB columns, `callback_data`, DB enum values): **English**
- Every `InlineKeyboardButton`: `text` = Hebrew, `callback_data` = English enum value stored in DB

---

## Authorization

`auth.py` exports an `authorized` decorator applied to every handler function. If `update.effective_user.id != AUTHORIZED_USER_ID`, the update is silently ignored (no reply). Unauthorized attempts are logged at `WARNING` level with the user ID.

---

## File Structure

```
headache-tracker/
├── bot.py              # Entrypoint: app init, handler registration, JobQueue setup
├── handlers.py         # All ConversationHandler state functions (shared between both handlers)
│                       # + /start, /export, /delete, daily check-in sender, no_headache callback
├── database.py         # Schema init + all CRUD functions
├── weather.py          # async fetch_weather() -> dict | None
├── config.py           # Env loading + fail-fast validation, enums, Hebrew label maps, constants
├── auth.py             # authorized(func) decorator
├── requirements.txt    # Pinned versions
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── data/
    └── .gitkeep        # head_map.png placed here at deploy time; headaches.db lives here too
```

---

## Architecture: Two ConversationHandlers + Shared State Functions

All state functions live in `handlers.py` and are imported by `bot.py` for wiring.

**`log_conv`** — entry point: `/log` command
**`checkin_conv`** — entry point: `yes_headache` callback (from daily check-in message)

Both handlers share the same state functions from `LOCATION` onward. No code duplication.

`no_headache` is a standalone `CallbackQueryHandler` (fire-and-forget, not a conversation): inserts negative log with weather, replies, done.

`/delete` is its own small ConversationHandler with two states: `CHOOSE_RECORD` and `CONFIRM_DELETE`.

---

## State Machine

State functions store results in `context.user_data[<db_column_name>]`. Retry counters (`onset_retries`, `hydration_retries`, `coffee_time_retries`) also stored in `user_data`, reset on state advance.

```
/log or yes_headache
    → LOCATION          inline keyboard (7 options, 2 cols) + head_map.png if present
    → PAIN_TYPE         inline keyboard (3 options, 1 row)
    → INTENSITY         inline keyboard 1–10 (2 rows of 5)
    → ONSET             free text HH:MM, max 3 retries, then cancel
    → HYDRATION_UNIT    inline keyboard: liters | cups
    → HYDRATION_AMOUNT
        liters → inline buttons [1, 1.5, 2, 2.5, 3, 3.5, 4]
        cups   → free text 0–20 integer, max 3 retries, then cancel
    → COFFEE_COUNT      inline keyboard 0–5
        0 → skip to MEDICATION
       >0 → COFFEE_TIME_LOOP
    → COFFEE_TIME_LOOP  single state; cup_index counter in user_data
        asks for cup N time (HH:MM), validates, appends to coffee_times list
        when cup_index == coffee_count → advance to MEDICATION
        max 3 retries per cup, then cancel whole conversation
    → MEDICATION        inline keyboard (2 rows: none + 4 medication options)
                        handler stores medication, then directly executes save:
                        fetch weather → DB write (one transaction) → reply with row id
                        returns ConversationHandler.END (no separate SAVE state)
```

`/cancel` registered as a fallback in both ConversationHandlers: clears `user_data`, replies "בוטל.", returns `END`.

---

## Daily Scheduled Check-in

- Runs daily at **18:00 Asia/Jerusalem** via PTB JobQueue
- Checks `headache_logs` for any row where `log_date_local` = today (Asia/Jerusalem)
- If found: skip silently
- If not found: send message with two inline buttons:
  - "כן" / `yes_headache` → triggers `checkin_conv` at LOCATION state
  - "לא" / `no_headache` → standalone handler: insert negative log + weather, reply "נשמר. תרגיש טוב."

---

## Database Schema

### `headache_logs`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| logged_at_utc | TEXT NOT NULL | ISO 8601 UTC |
| logged_at_local | TEXT NOT NULL | ISO 8601 Asia/Jerusalem |
| log_date_local | TEXT NOT NULL | YYYY-MM-DD, used for "logged today" check |
| had_headache | INTEGER NOT NULL | 0 or 1 |
| location | TEXT | enum: frontal, temporal, behind_eye, occipital, top, band, one_side |
| pain_type | TEXT | enum: throbbing, sharp, dull |
| intensity | INTEGER | 1–10 |
| onset_time_local | TEXT | HH:MM 24-hour |
| hydration_unit | TEXT | enum: liters, cups |
| hydration_liters | REAL | always normalized; cups × 0.25 |
| hydration_raw_amount | REAL | original value entered |
| coffee_count | INTEGER | 0–5 |
| medication | TEXT | enum: none, ibuprofen_200, ibuprofen_512, optalgin_1, optalgin_2 |
| weather_temp_c | REAL | NULL if fetch failed |
| weather_humidity_pct | INTEGER | NULL if fetch failed |
| weather_pressure_hpa | INTEGER | NULL if fetch failed |
| weather_fetch_ok | INTEGER NOT NULL DEFAULT 0 | 0 or 1 |

### `coffee_times`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| headache_log_id | INTEGER NOT NULL | FK → headache_logs.id ON DELETE CASCADE |
| cup_number | INTEGER NOT NULL | 1, 2, 3… |
| drunk_at_local | TEXT NOT NULL | HH:MM |

Index: `CREATE INDEX idx_log_date ON headache_logs(log_date_local)`

Negative logs: `had_headache=0`, all clinical fields NULL. Weather still captured.

### `database.py` Public API

```python
init_db()                           # creates tables if not exist; called at startup
insert_log(data: dict) -> int       # inserts headache_logs row, returns id
insert_coffee_times(log_id, times)  # inserts coffee_times rows
get_today_log(date_str) -> bool     # True if a row exists for this date
get_recent_logs(n=5) -> list        # for /delete flow
delete_log(log_id)                  # cascades to coffee_times
export_to_csv() -> str              # writes CSV to temp file, returns path
```

`insert_log` + `insert_coffee_times` are called inside a single `with conn:` block — atomic.

---

## Weather (`weather.py`)

```python
async def fetch_weather() -> dict | None
```

- Kiryat Ono coords hardcoded: `lat=32.0556, lon=34.8550`
- OpenWeatherMap Current Weather API, `units=metric`
- 5-second `httpx` timeout
- Returns `{temp_c, humidity_pct, pressure_hpa}` on success
- Returns `None` on any failure (network error, non-200, JSON parse error)
- Logs `ERROR` on failure
- Caller sets `weather_fetch_ok=0` and NULLs weather fields — never blocks DB save

---

## Commands

| Command | Behavior |
|---|---|
| `/start` | Hebrew welcome message listing available commands |
| `/log` | Starts full tracking ConversationHandler |
| `/cancel` | Available in every state; clears user_data, replies "בוטל.", ends conversation |
| `/export` | Generates and sends `headache_logs_YYYYMMDD.csv` as file attachment |
| `/delete` | Shows 5 most recent logs as inline buttons; tap → confirm → delete or cancel |

### `/export` CSV columns
`id, logged_at_local, had_headache, location, pain_type, intensity, onset_time_local, hydration_unit, hydration_liters, hydration_raw_amount, coffee_count, coffee_times_csv, medication, weather_temp_c, weather_humidity_pct, weather_pressure_hpa, weather_fetch_ok`

`coffee_times_csv`: semicolon-separated HH:MM strings (e.g. `08:30;14:00`).

---

## `config.py`

```python
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or _fail("TELEGRAM_BOT_TOKEN")
OWM_API_KEY        = os.getenv("OWM_API_KEY")        or _fail("OWM_API_KEY")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID") or _fail("AUTHORIZED_USER_ID"))
TZ                 = ZoneInfo(os.getenv("TZ", "Asia/Jerusalem"))
DB_PATH            = "/app/data/headaches.db"
OWM_LAT, OWM_LON   = 32.0556, 34.8550
HEAD_MAP_PATH      = "./data/head_map.png"
CHECKIN_HOUR       = 18
CHECKIN_MINUTE     = 0
```

Also contains: enum value lists, Hebrew label maps for building `InlineKeyboardButton` grids.

---

## Logging

Configured once in `bot.py`:

```
format:  %(asctime)s %(levelname)s %(name)s: %(message)s
level:   INFO
handler: stdout (StreamHandler)
```

- `ERROR`: weather fetch failures, unexpected DB errors
- `WARNING`: unauthorized access attempts (with user ID), missing head_map.png
- `INFO`: startup, scheduler fires, log saved (with row id)

---

## Docker

**`Dockerfile`:**
- Base: `python:3.11-slim`
- Non-root user
- Install `tzdata`, set `ENV TZ=Asia/Jerusalem`
- Copy + install `requirements.txt`
- `CMD ["python", "bot.py"]`

**`docker-compose.yml`:**
- Service: `headache-bot`
- `restart: unless-stopped`
- `env_file: .env`
- Volume: `./data:/app/data` (DB + head_map.png)
- No exposed ports (outbound long polling only)

---

## Verification Checklist

- [ ] Every user-facing string is Hebrew; every `callback_data` and DB value is English
- [ ] Every ConversationHandler state has a `/cancel` fallback exit
- [ ] Coffee time loop uses `cup_index` counter in `user_data`; bounded by `coffee_count` (max 5)
- [ ] Weather failure sets fields to NULL and continues — never blocks DB save
- [ ] `authorized` decorator wraps every handler including scheduler callback
- [ ] All DB writes for one log (parent + coffee_times) are in one transaction
- [ ] `.env` excluded by `.gitignore`
- [ ] `requirements.txt` uses pinned versions
