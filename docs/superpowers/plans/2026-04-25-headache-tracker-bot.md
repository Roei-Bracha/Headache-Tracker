# Headache Tracker Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal Telegram bot for daily headache tracking using python-telegram-bot v21, SQLite, and OpenWeatherMap, producing structured data for neurologist review.

**Architecture:** Two ConversationHandlers (`log_conv` for `/log`, `checkin_conv` for daily check-in) share state functions from `handlers.py`. A standalone `CallbackQueryHandler` handles the "no headache" path. PTB's JobQueue fires a daily check-in at 18:00 Asia/Jerusalem. All DB writes for one log are atomic (single `with conn:` block).

**Tech Stack:** Python 3.11, python-telegram-bot 21.3 (with JobQueue/APScheduler), SQLite (stdlib), httpx, python-dotenv, zoneinfo

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | Env loading, fail-fast validation, constants, enums, Hebrew label maps |
| `auth.py` | `authorized` decorator — silently drops non-AUTHORIZED_USER_ID updates |
| `database.py` | Schema init, atomic CRUD: insert log+coffees, query, delete, export CSV |
| `weather.py` | Async OWM client, 5s timeout, returns dict or None |
| `handlers.py` | All ConversationHandler state functions, command handlers, scheduler callback |
| `bot.py` | Application init, handler registration, JobQueue setup, entry point |
| `tests/test_config.py` | Env validation fail-fast tests |
| `tests/test_auth.py` | Auth decorator tests |
| `tests/test_database.py` | All CRUD tests with temp SQLite |
| `tests/test_weather.py` | Weather fetch tests with mocked httpx |
| `tests/test_handlers.py` | Handler helper function tests (parse_hhmm, log data building) |
| `requirements.txt` | Pinned dependencies |
| `pytest.ini` | asyncio_mode = auto |
| `Dockerfile` | python:3.11-slim, non-root user, tzdata |
| `docker-compose.yml` | headache-bot service, ./data volume, env_file |
| `.env.example` | Template with all required keys |
| `.gitignore` | Excludes .env, data/, __pycache__/ |
| `data/.gitkeep` | Placeholder for bind-mounted data dir |
| `README.md` | Proxmox + Portainer deployment guide |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
python-telegram-bot[job-queue]==21.3
httpx==0.27.2
python-dotenv==1.0.1
pytest==8.3.2
pytest-asyncio==0.23.8
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: Create .env.example**

```
TELEGRAM_BOT_TOKEN=
OWM_API_KEY=
AUTHORIZED_USER_ID=
TZ=Asia/Jerusalem
DB_PATH=/app/data/headaches.db
```

- [ ] **Step 4: Create .gitignore**

```
.env
data/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 5: Create data/.gitkeep and tests/__init__.py**

```bash
mkdir -p data tests
touch data/.gitkeep tests/__init__.py
```

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt pytest.ini .env.example .gitignore data/.gitkeep tests/__init__.py
git commit -m "feat: project scaffold"
```

---

## Task 2: config.py

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import os
import pytest

def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OWM_API_KEY", raising=False)
    monkeypatch.delenv("AUTHORIZED_USER_ID", raising=False)
    import importlib
    import config as cfg_module
    # Reload to re-execute module-level code
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        importlib.reload(cfg_module)

def test_authorized_user_id_is_int(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWM_API_KEY", "test-key")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "12345")
    import importlib
    import config as cfg_module
    importlib.reload(cfg_module)
    assert cfg_module.AUTHORIZED_USER_ID == 12345
    assert isinstance(cfg_module.AUTHORIZED_USER_ID, int)
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError` or `RuntimeError` (config.py doesn't exist yet).

- [ ] **Step 3: Create config.py**

```python
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


def _fail(key: str):
    raise RuntimeError(f"Missing required environment variable: {key}")


TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") or _fail("TELEGRAM_BOT_TOKEN")
OWM_API_KEY: str = os.getenv("OWM_API_KEY") or _fail("OWM_API_KEY")
AUTHORIZED_USER_ID: int = int(os.getenv("AUTHORIZED_USER_ID") or _fail("AUTHORIZED_USER_ID"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Jerusalem"))
DB_PATH: str = os.getenv("DB_PATH", "/app/data/headaches.db")
OWM_LAT: float = 32.0556
OWM_LON: float = 34.8550
HEAD_MAP_PATH: str = "./data/head_map.png"
CHECKIN_HOUR: int = 18
CHECKIN_MINUTE: int = 0

# Enum values stored in DB / used as callback_data (English only)
LOCATIONS = ["frontal", "temporal", "behind_eye", "occipital", "top", "band", "one_side"]
PAIN_TYPES = ["throbbing", "sharp", "dull"]
MEDICATIONS = ["none", "ibuprofen_200", "ibuprofen_512", "optalgin_1", "optalgin_2"]
HYDRATION_UNITS = ["liters", "cups"]
LITERS_OPTIONS = ["1", "1.5", "2", "2.5", "3", "3.5", "4"]
COFFEE_OPTIONS = ["0", "1", "2", "3", "4", "5"]

# Hebrew label maps: callback_data -> Hebrew button text
LOCATION_LABELS = {
    "frontal": "מצח",
    "temporal": "רקות",
    "behind_eye": "מאחורי העין",
    "occipital": "עורף",
    "top": "קדקוד",
    "band": "כטבעת הראש",
    "one_side": "צד אחד",
}

PAIN_TYPE_LABELS = {
    "throbbing": "פועם",
    "sharp": "חד",
    "dull": "לחץ עמום",
}

MEDICATION_LABELS = {
    "none": "לא",
    "ibuprofen_200": "איבופרופן 200",
    "ibuprofen_512": "איבופרופן 512",
    "optalgin_1": "אופטלגין 1",
    "optalgin_2": "אופטלגין 2",
}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config with fail-fast env validation"
```

---

## Task 3: auth.py

**Files:**
- Create: `auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auth.py
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

from auth import authorized


async def test_authorized_user_passes_through():
    handler_called = False

    @authorized
    async def handler(update, context):
        nonlocal handler_called
        handler_called = True

    update = MagicMock()
    update.effective_user.id = 42
    await handler(update, MagicMock())
    assert handler_called


async def test_unauthorized_user_is_silently_dropped():
    handler_called = False

    @authorized
    async def handler(update, context):
        nonlocal handler_called
        handler_called = True

    update = MagicMock()
    update.effective_user.id = 999
    result = await handler(update, MagicMock())
    assert not handler_called
    assert result is None
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_auth.py -v
```

Expected: `ModuleNotFoundError` (auth.py doesn't exist).

- [ ] **Step 3: Create auth.py**

```python
import functools
import logging

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


def authorized(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != config.AUTHORIZED_USER_ID:
            logger.warning(
                "Unauthorized access attempt from user %s", update.effective_user.id
            )
            return
        return await func(update, context)

    return wrapper
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_auth.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: authorized decorator with silent drop for unknown users"
```

---

## Task 4: database.py

**Files:**
- Create: `database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_database.py
import os
import tempfile
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

import database
import config


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    database.init_db()
    yield db_file


def _sample_log(had_headache=1, **kwargs):
    base = {
        "logged_at_utc": "2026-01-01T12:00:00+00:00",
        "logged_at_local": "2026-01-01T14:00:00+02:00",
        "log_date_local": "2026-01-01",
        "had_headache": had_headache,
        "location": "frontal" if had_headache else None,
        "pain_type": "throbbing" if had_headache else None,
        "intensity": 7 if had_headache else None,
        "onset_time_local": "10:00" if had_headache else None,
        "hydration_unit": "liters" if had_headache else None,
        "hydration_liters": 2.0 if had_headache else None,
        "hydration_raw_amount": 2.0 if had_headache else None,
        "coffee_count": 2 if had_headache else None,
        "medication": "none" if had_headache else None,
        "weather_temp_c": 22.5,
        "weather_humidity_pct": 60,
        "weather_pressure_hpa": 1013,
        "weather_fetch_ok": 1,
    }
    base.update(kwargs)
    return base


def test_init_db_creates_tables(tmp_path, monkeypatch):
    db_file = str(tmp_path / "fresh.db")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    database.init_db()
    import sqlite3
    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "headache_logs" in tables
    assert "coffee_times" in tables


def test_insert_log_returns_id():
    log_id = database.insert_log_with_coffees(_sample_log(), [])
    assert isinstance(log_id, int)
    assert log_id > 0


def test_insert_log_with_coffee_times():
    log_id = database.insert_log_with_coffees(_sample_log(), ["08:30", "14:00"])
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    rows = conn.execute("SELECT cup_number, drunk_at_local FROM coffee_times WHERE headache_log_id=?", (log_id,)).fetchall()
    assert len(rows) == 2
    assert rows[0] == (1, "08:30")
    assert rows[1] == (2, "14:00")


def test_get_today_log_true():
    database.insert_log_with_coffees(_sample_log(log_date_local="2026-01-01"), [])
    assert database.get_today_log("2026-01-01") is True


def test_get_today_log_false():
    assert database.get_today_log("2099-01-01") is False


def test_get_recent_logs():
    for i in range(6):
        database.insert_log_with_coffees(_sample_log(log_date_local=f"2026-01-{i+1:02d}"), [])
    logs = database.get_recent_logs(5)
    assert len(logs) == 5


def test_delete_log_cascades():
    log_id = database.insert_log_with_coffees(_sample_log(), ["09:00"])
    database.delete_log(log_id)
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    assert conn.execute("SELECT 1 FROM headache_logs WHERE id=?", (log_id,)).fetchone() is None
    assert conn.execute("SELECT 1 FROM coffee_times WHERE headache_log_id=?", (log_id,)).fetchone() is None


def test_export_to_csv():
    database.insert_log_with_coffees(_sample_log(), ["08:30", "14:00"])
    path = database.export_to_csv()
    import csv, os
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["had_headache"] == "1"
    assert rows[0]["coffee_times_csv"] == "08:30;14:00"
    os.unlink(path)


def test_negative_log_has_null_clinical_fields():
    log_id = database.insert_log_with_coffees(_sample_log(had_headache=0), [])
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    row = conn.execute("SELECT location, intensity FROM headache_logs WHERE id=?", (log_id,)).fetchone()
    assert row[0] is None
    assert row[1] is None
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError` (database.py doesn't exist).

- [ ] **Step 3: Create database.py**

```python
import csv
import logging
import sqlite3
import tempfile

import config

logger = logging.getLogger(__name__)

_CREATE_HEADACHE_LOGS = """
CREATE TABLE IF NOT EXISTS headache_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at_utc TEXT NOT NULL,
    logged_at_local TEXT NOT NULL,
    log_date_local TEXT NOT NULL,
    had_headache INTEGER NOT NULL,
    location TEXT,
    pain_type TEXT,
    intensity INTEGER,
    onset_time_local TEXT,
    hydration_unit TEXT,
    hydration_liters REAL,
    hydration_raw_amount REAL,
    coffee_count INTEGER,
    medication TEXT,
    weather_temp_c REAL,
    weather_humidity_pct INTEGER,
    weather_pressure_hpa INTEGER,
    weather_fetch_ok INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_COFFEE_TIMES = """
CREATE TABLE IF NOT EXISTS coffee_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    headache_log_id INTEGER NOT NULL,
    cup_number INTEGER NOT NULL,
    drunk_at_local TEXT NOT NULL,
    FOREIGN KEY (headache_log_id) REFERENCES headache_logs(id) ON DELETE CASCADE
)
"""

_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_log_date ON headache_logs(log_date_local)"

_INSERT_LOG = """
INSERT INTO headache_logs (
    logged_at_utc, logged_at_local, log_date_local, had_headache,
    location, pain_type, intensity, onset_time_local,
    hydration_unit, hydration_liters, hydration_raw_amount, coffee_count,
    medication,
    weather_temp_c, weather_humidity_pct, weather_pressure_hpa, weather_fetch_ok
) VALUES (
    :logged_at_utc, :logged_at_local, :log_date_local, :had_headache,
    :location, :pain_type, :intensity, :onset_time_local,
    :hydration_unit, :hydration_liters, :hydration_raw_amount, :coffee_count,
    :medication,
    :weather_temp_c, :weather_humidity_pct, :weather_pressure_hpa, :weather_fetch_ok
)
"""

_INSERT_COFFEE = (
    "INSERT INTO coffee_times (headache_log_id, cup_number, drunk_at_local) VALUES (?, ?, ?)"
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_CREATE_HEADACHE_LOGS)
        conn.execute(_CREATE_COFFEE_TIMES)
        conn.execute(_CREATE_INDEX)


def insert_log_with_coffees(data: dict, coffee_times: list[str]) -> int:
    """Insert headache_logs row and all coffee_times rows in one transaction."""
    with _connect() as conn:
        cursor = conn.execute(_INSERT_LOG, data)
        log_id = cursor.lastrowid
        for i, t in enumerate(coffee_times, start=1):
            conn.execute(_INSERT_COFFEE, (log_id, i, t))
    return log_id


def get_today_log(date_str: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM headache_logs WHERE log_date_local = ? LIMIT 1", (date_str,)
        ).fetchone()
    return row is not None


def get_recent_logs(n: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, log_date_local, onset_time_local FROM headache_logs ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_log(log_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM headache_logs WHERE id = ?", (log_id,))


def export_to_csv() -> str:
    sql = """
    SELECT
        h.id, h.logged_at_local, h.had_headache, h.location, h.pain_type,
        h.intensity, h.onset_time_local, h.hydration_unit, h.hydration_liters,
        h.hydration_raw_amount, h.coffee_count,
        GROUP_CONCAT(c.drunk_at_local, ';') AS coffee_times_csv,
        h.medication, h.weather_temp_c, h.weather_humidity_pct,
        h.weather_pressure_hpa, h.weather_fetch_ok
    FROM headache_logs h
    LEFT JOIN coffee_times c ON c.headache_log_id = h.id
    GROUP BY h.id
    ORDER BY h.id
    """
    fieldnames = [
        "id", "logged_at_local", "had_headache", "location", "pain_type",
        "intensity", "onset_time_local", "hydration_unit", "hydration_liters",
        "hydration_raw_amount", "coffee_count", "coffee_times_csv",
        "medication", "weather_temp_c", "weather_humidity_pct",
        "weather_pressure_hpa", "weather_fetch_ok",
    ]
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    )
    writer = csv.DictWriter(tmp, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))
    tmp.close()
    return tmp.name
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_database.py -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_database.py
git commit -m "feat: database layer with atomic log insertion and CSV export"
```

---

## Task 5: weather.py

**Files:**
- Create: `weather.py`
- Create: `tests/test_weather.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_weather.py
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test-owm")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

import weather


async def test_fetch_weather_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "main": {"temp": 22.5, "humidity": 60, "pressure": 1013}
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result == {"temp_c": 22.5, "humidity_pct": 60, "pressure_hpa": 1013}


async def test_fetch_weather_network_error_returns_none():
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result is None


async def test_fetch_weather_non_200_returns_none():
    import httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result is None
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_weather.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create weather.py**

```python
import logging

import httpx

import config

logger = logging.getLogger(__name__)

_OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_weather() -> dict | None:
    """Fetch current weather for Kiryat Ono. Returns dict or None on any failure."""
    params = {
        "lat": config.OWM_LAT,
        "lon": config.OWM_LON,
        "units": "metric",
        "appid": config.OWM_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(_OWM_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "temp_c": data["main"]["temp"],
                "humidity_pct": data["main"]["humidity"],
                "pressure_hpa": data["main"]["pressure"],
            }
    except Exception as exc:
        logger.error("Weather fetch failed: %s", exc)
        return None
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_weather.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add weather.py tests/test_weather.py
git commit -m "feat: async OWM weather client with graceful failure"
```

---

## Task 6: handlers.py — Foundation, /start, /cancel, parse_hhmm

**Files:**
- Create: `handlers.py`
- Create: `tests/test_handlers.py`

- [ ] **Step 1: Write failing tests for parse_hhmm**

```python
# tests/test_handlers.py
import os
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

from handlers import parse_hhmm


def test_valid_hhmm():
    assert parse_hhmm("14:30") == "14:30"
    assert parse_hhmm("00:00") == "00:00"
    assert parse_hhmm("23:59") == "23:59"


def test_invalid_hhmm_format():
    assert parse_hhmm("25:00") is None
    assert parse_hhmm("14:60") is None
    assert parse_hhmm("1430") is None
    assert parse_hhmm("14:3") is None
    assert parse_hhmm("abc") is None
    assert parse_hhmm("") is None


def test_hhmm_strips_whitespace():
    assert parse_hhmm("  14:30  ") == "14:30"
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_handlers.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create handlers.py with foundation, parse_hhmm, /start, /cancel**

```python
import logging
import os
import re
from datetime import datetime, timezone
from datetime import time as dt_time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import config
import database
from auth import authorized
from weather import fetch_weather

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation state constants — log flow
# ---------------------------------------------------------------------------
LOCATION, PAIN_TYPE, INTENSITY, ONSET = range(4)
HYDRATION_UNIT, HYDRATION_AMOUNT = range(4, 6)
COFFEE_COUNT, COFFEE_TIME_LOOP = range(6, 8)
MEDICATION = 8

# Delete flow
CHOOSE_RECORD, CONFIRM_DELETE = range(2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_hhmm(text: str) -> str | None:
    """Return HH:MM if valid 24-hour time, else None."""
    text = text.strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        return None
    try:
        h, m = text.split(":")
        dt_time(int(h), int(m))
        return text
    except ValueError:
        return None


async def _send_message(update: Update, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> None:
    """Send a message to the effective chat, works for both command and callback contexts."""
    await context.bot.send_message(chat_id=update.effective_chat.id, **kwargs)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@authorized
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "שלום! זהו הבוט למעקב כאבי ראש.\n\n"
        "פקודות זמינות:\n"
        "/log — תיעוד כאב ראש\n"
        "/export — ייצוא נתונים כ-CSV\n"
        "/delete — מחיקת רשומה\n"
        "/cancel — ביטול"
    )


@authorized
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_handlers.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add handlers.py tests/test_handlers.py
git commit -m "feat: handlers foundation with parse_hhmm, /start, /cancel"
```

---

## Task 7: handlers.py — LOCATION, PAIN_TYPE, INTENSITY states

**Files:**
- Modify: `handlers.py`

- [ ] **Step 1: Add ask_location (entry for /log), ask_location_from_checkin (entry for check-in), handle_location, handle_pain_type, handle_intensity to handlers.py**

Append after the `cancel` function:

```python
# ---------------------------------------------------------------------------
# Log flow — entry points
# ---------------------------------------------------------------------------

def _location_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(config.LOCATION_LABELS["frontal"], callback_data="frontal"),
            InlineKeyboardButton(config.LOCATION_LABELS["temporal"], callback_data="temporal"),
        ],
        [
            InlineKeyboardButton(config.LOCATION_LABELS["behind_eye"], callback_data="behind_eye"),
            InlineKeyboardButton(config.LOCATION_LABELS["occipital"], callback_data="occipital"),
        ],
        [
            InlineKeyboardButton(config.LOCATION_LABELS["top"], callback_data="top"),
            InlineKeyboardButton(config.LOCATION_LABELS["band"], callback_data="band"),
        ],
        [
            InlineKeyboardButton(config.LOCATION_LABELS["one_side"], callback_data="one_side"),
        ],
    ])


async def _send_location_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    head_map = Path(config.HEAD_MAP_PATH)
    markup = _location_keyboard()
    if head_map.exists():
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=head_map.open("rb"),
            caption="איפה כואב לך?",
            reply_markup=markup,
        )
    else:
        logger.warning("Head map image not found at %s", config.HEAD_MAP_PATH)
        await _send_message(update, context, text="איפה כואב לך?", reply_markup=markup)


@authorized
async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /log command."""
    await _send_location_question(update, context)
    return LOCATION


@authorized
async def ask_location_from_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for yes_headache callback from daily check-in."""
    query = update.callback_query
    await query.answer()
    await _send_location_question(update, context)
    return LOCATION


# ---------------------------------------------------------------------------
# Log flow — states
# ---------------------------------------------------------------------------

@authorized
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["location"] = query.data
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(config.PAIN_TYPE_LABELS["throbbing"], callback_data="throbbing"),
        InlineKeyboardButton(config.PAIN_TYPE_LABELS["sharp"], callback_data="sharp"),
        InlineKeyboardButton(config.PAIN_TYPE_LABELS["dull"], callback_data="dull"),
    ]])
    await _send_message(update, context, text="מה סוג הכאב?", reply_markup=keyboard)
    return PAIN_TYPE


@authorized
async def handle_pain_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["pain_type"] = query.data
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6, 11)],
    ])
    await _send_message(update, context, text="מה עוצמת הכאב?", reply_markup=keyboard)
    return INTENSITY


@authorized
async def handle_intensity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["intensity"] = int(query.data)
    context.user_data["onset_retries"] = 0
    await _send_message(
        update, context,
        text="באיזו שעה זה התחיל? (פורמט: HH:MM, למשל 14:30)",
    )
    return ONSET
```

- [ ] **Step 2: Run full test suite — expect all pass**

```bash
pytest -v
```

Expected: all existing tests pass (no regression).

- [ ] **Step 3: Commit**

```bash
git add handlers.py
git commit -m "feat: location, pain type, intensity states"
```

---

## Task 8: handlers.py — ONSET state with retry logic

**Files:**
- Modify: `handlers.py`
- Modify: `tests/test_handlers.py`

- [ ] **Step 1: Add test for onset retry logic**

Append to `tests/test_handlers.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from handlers import handle_onset, HYDRATION_UNIT
from telegram.ext import ConversationHandler


async def _make_message_update(text: str, user_id: int = 42) -> tuple:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 100
    update.message.text = text
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.user_data = {"onset_retries": 0}
    context.bot.send_message = AsyncMock()
    return update, context


async def test_onset_valid_time_advances():
    update, context = await _make_message_update("14:30")
    result = await handle_onset(update, context)
    assert result == HYDRATION_UNIT
    assert context.user_data["onset_time_local"] == "14:30"


async def test_onset_invalid_increments_retry():
    update, context = await _make_message_update("bad")
    result = await handle_onset(update, context)
    from handlers import ONSET
    assert result == ONSET
    assert context.user_data["onset_retries"] == 1


async def test_onset_three_failures_cancels():
    update, context = await _make_message_update("bad")
    context.user_data["onset_retries"] = 2
    result = await handle_onset(update, context)
    assert result == ConversationHandler.END
```

- [ ] **Step 2: Run new tests — expect failure**

```bash
pytest tests/test_handlers.py::test_onset_valid_time_advances tests/test_handlers.py::test_onset_invalid_increments_retry tests/test_handlers.py::test_onset_three_failures_cancels -v
```

Expected: `AttributeError` (handle_onset not defined yet).

- [ ] **Step 3: Add handle_onset to handlers.py**

Append after `handle_intensity`:

```python
@authorized
async def handle_onset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    retries = context.user_data.get("onset_retries", 0)
    parsed = parse_hhmm(update.message.text)

    if parsed is None:
        retries += 1
        context.user_data["onset_retries"] = retries
        if retries >= 3:
            context.user_data.clear()
            await update.message.reply_text("נסיון לא תקין שלוש פעמים. בוטל.")
            return ConversationHandler.END
        await update.message.reply_text("פורמט לא תקין. נסה שוב (HH:MM)")
        return ONSET

    context.user_data["onset_time_local"] = parsed
    context.user_data["hydration_retries"] = 0
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("ליטרים", callback_data="liters"),
        InlineKeyboardButton("כוסות", callback_data="cups"),
    ]])
    await _send_message(
        update, context,
        text="איך תרצה למדוד את המים ששתית היום?",
        reply_markup=keyboard,
    )
    return HYDRATION_UNIT
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_handlers.py -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add handlers.py tests/test_handlers.py
git commit -m "feat: onset state with 3-retry limit"
```

---

## Task 9: handlers.py — HYDRATION states

**Files:**
- Modify: `handlers.py`
- Modify: `tests/test_handlers.py`

- [ ] **Step 1: Add hydration tests**

Append to `tests/test_handlers.py`:

```python
from handlers import handle_hydration_unit, handle_hydration_amount_inline, handle_hydration_amount_text, HYDRATION_AMOUNT, COFFEE_COUNT


async def _make_callback_update(data: str, user_id: int = 42) -> tuple:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 100
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    context = MagicMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    return update, context


async def test_hydration_unit_liters_sends_buttons():
    update, context = await _make_callback_update("liters")
    result = await handle_hydration_unit(update, context)
    assert result == HYDRATION_AMOUNT
    assert context.user_data["hydration_unit"] == "liters"


async def test_hydration_unit_cups_sends_text():
    update, context = await _make_callback_update("cups")
    result = await handle_hydration_unit(update, context)
    assert result == HYDRATION_AMOUNT
    assert context.user_data["hydration_unit"] == "cups"


async def test_hydration_amount_inline_liters():
    update, context = await _make_callback_update("2.5")
    context.user_data["hydration_unit"] = "liters"
    # handle_hydration_amount_inline calls ask_coffee_count which sends a message
    result = await handle_hydration_amount_inline(update, context)
    assert result == COFFEE_COUNT
    assert context.user_data["hydration_liters"] == 2.5
    assert context.user_data["hydration_raw_amount"] == 2.5


async def test_hydration_amount_text_cups_converts():
    update, context = await _make_message_update("8")
    context.user_data["hydration_unit"] = "cups"
    context.user_data["hydration_retries"] = 0
    result = await handle_hydration_amount_text(update, context)
    assert result == COFFEE_COUNT
    assert context.user_data["hydration_raw_amount"] == 8
    assert context.user_data["hydration_liters"] == pytest.approx(2.0)


async def test_hydration_amount_text_invalid_cups():
    update, context = await _make_message_update("99")
    context.user_data["hydration_unit"] = "cups"
    context.user_data["hydration_retries"] = 0
    result = await handle_hydration_amount_text(update, context)
    assert result == HYDRATION_AMOUNT
    assert context.user_data["hydration_retries"] == 1
```

- [ ] **Step 2: Run new tests — expect failure**

```bash
pytest tests/test_handlers.py -k "hydration" -v
```

Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Add hydration handlers to handlers.py**

Append after `handle_onset`:

```python
@authorized
async def handle_hydration_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    unit = query.data  # 'liters' or 'cups'
    context.user_data["hydration_unit"] = unit
    context.user_data["hydration_retries"] = 0

    if unit == "liters":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(v, callback_data=v) for v in ["1", "1.5", "2", "2.5"]],
            [InlineKeyboardButton(v, callback_data=v) for v in ["3", "3.5", "4"]],
        ])
        await _send_message(
            update, context, text="כמה ליטרים שתית?", reply_markup=keyboard
        )
    else:
        await _send_message(
            update, context, text="כמה כוסות שתית? (מספר בלבד, 0–20)"
        )
    return HYDRATION_AMOUNT


@authorized
async def handle_hydration_amount_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles liter selection via inline button."""
    query = update.callback_query
    await query.answer()
    amount = float(query.data)
    context.user_data["hydration_raw_amount"] = amount
    context.user_data["hydration_liters"] = amount
    return await _ask_coffee_count(update, context)


@authorized
async def handle_hydration_amount_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles cups count via text input."""
    retries = context.user_data.get("hydration_retries", 0)
    text = update.message.text.strip()

    try:
        cups = int(text)
        if not (0 <= cups <= 20):
            raise ValueError("out of range")
    except ValueError:
        retries += 1
        context.user_data["hydration_retries"] = retries
        if retries >= 3:
            context.user_data.clear()
            await update.message.reply_text("נסיון לא תקין שלוש פעמים. בוטל.")
            return ConversationHandler.END
        await update.message.reply_text("מספר לא תקין. נסה שוב (0–20)")
        return HYDRATION_AMOUNT

    context.user_data["hydration_raw_amount"] = cups
    context.user_data["hydration_liters"] = cups * 0.25
    return await _ask_coffee_count(update, context)


async def _ask_coffee_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6)
    ]])
    await _send_message(
        update, context,
        text="כמה כוסות קפה שתית היום?",
        reply_markup=keyboard,
    )
    return COFFEE_COUNT
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add handlers.py tests/test_handlers.py
git commit -m "feat: hydration states (liters inline + cups text with retry)"
```

---

## Task 10: handlers.py — COFFEE states

**Files:**
- Modify: `handlers.py`
- Modify: `tests/test_handlers.py`

- [ ] **Step 1: Add coffee tests**

Append to `tests/test_handlers.py`:

```python
from handlers import handle_coffee_count, handle_coffee_time_loop, COFFEE_TIME_LOOP, MEDICATION


async def test_coffee_count_zero_skips_to_medication():
    update, context = await _make_callback_update("0")
    context.user_data = {}
    result = await handle_coffee_count(update, context)
    assert result == MEDICATION
    assert context.user_data["coffee_count"] == 0
    assert context.user_data["coffee_times"] == []


async def test_coffee_count_nonzero_enters_loop():
    update, context = await _make_callback_update("2")
    context.user_data = {}
    result = await handle_coffee_count(update, context)
    assert result == COFFEE_TIME_LOOP
    assert context.user_data["coffee_count"] == 2
    assert context.user_data["cup_index"] == 1


async def test_coffee_time_loop_valid_advances_cup():
    update, context = await _make_message_update("08:30")
    context.user_data = {
        "coffee_count": 2, "cup_index": 1,
        "coffee_times": [], "coffee_time_retries": 0,
    }
    result = await handle_coffee_time_loop(update, context)
    assert result == COFFEE_TIME_LOOP
    assert context.user_data["coffee_times"] == ["08:30"]
    assert context.user_data["cup_index"] == 2


async def test_coffee_time_loop_last_cup_advances_to_medication():
    update, context = await _make_message_update("14:00")
    context.user_data = {
        "coffee_count": 2, "cup_index": 2,
        "coffee_times": ["08:30"], "coffee_time_retries": 0,
    }
    result = await handle_coffee_time_loop(update, context)
    assert result == MEDICATION
    assert context.user_data["coffee_times"] == ["08:30", "14:00"]


async def test_coffee_time_loop_invalid_retries():
    update, context = await _make_message_update("bad")
    context.user_data = {
        "coffee_count": 2, "cup_index": 1,
        "coffee_times": [], "coffee_time_retries": 0,
    }
    result = await handle_coffee_time_loop(update, context)
    assert result == COFFEE_TIME_LOOP
    assert context.user_data["coffee_time_retries"] == 1


async def test_coffee_time_loop_three_failures_cancels():
    update, context = await _make_message_update("bad")
    context.user_data = {
        "coffee_count": 2, "cup_index": 1,
        "coffee_times": [], "coffee_time_retries": 2,
    }
    result = await handle_coffee_time_loop(update, context)
    assert result == ConversationHandler.END
```

- [ ] **Step 2: Run new tests — expect failure**

```bash
pytest tests/test_handlers.py -k "coffee" -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add coffee handlers to handlers.py**

Append after `_ask_coffee_count`:

```python
@authorized
async def handle_coffee_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    count = int(query.data)
    context.user_data["coffee_count"] = count
    context.user_data["coffee_times"] = []

    if count == 0:
        return await _ask_medication(update, context)

    context.user_data["cup_index"] = 1
    context.user_data["coffee_time_retries"] = 0
    await _send_message(update, context, text="באיזו שעה שתית את כוס 1? (HH:MM)")
    return COFFEE_TIME_LOOP


@authorized
async def handle_coffee_time_loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    cup_index = user_data["cup_index"]
    coffee_count = user_data["coffee_count"]
    retries = user_data.get("coffee_time_retries", 0)

    parsed = parse_hhmm(update.message.text)

    if parsed is None:
        retries += 1
        user_data["coffee_time_retries"] = retries
        if retries >= 3:
            user_data.clear()
            await update.message.reply_text("נסיון לא תקין שלוש פעמים. בוטל.")
            return ConversationHandler.END
        await update.message.reply_text("פורמט לא תקין. נסה שוב (HH:MM)")
        return COFFEE_TIME_LOOP

    user_data["coffee_times"].append(parsed)
    user_data["coffee_time_retries"] = 0

    if cup_index >= coffee_count:
        return await _ask_medication(update, context)

    user_data["cup_index"] = cup_index + 1
    await update.message.reply_text(f"באיזו שעה שתית את כוס {cup_index + 1}? (HH:MM)")
    return COFFEE_TIME_LOOP


async def _ask_medication(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(config.MEDICATION_LABELS["none"], callback_data="none"),
            InlineKeyboardButton(config.MEDICATION_LABELS["ibuprofen_200"], callback_data="ibuprofen_200"),
            InlineKeyboardButton(config.MEDICATION_LABELS["ibuprofen_512"], callback_data="ibuprofen_512"),
        ],
        [
            InlineKeyboardButton(config.MEDICATION_LABELS["optalgin_1"], callback_data="optalgin_1"),
            InlineKeyboardButton(config.MEDICATION_LABELS["optalgin_2"], callback_data="optalgin_2"),
        ],
    ])
    await _send_message(update, context, text="האם לקחת תרופה?", reply_markup=keyboard)
    return MEDICATION
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add handlers.py tests/test_handlers.py
git commit -m "feat: coffee count and time loop states with per-cup retry"
```

---

## Task 11: handlers.py — MEDICATION state + save logic

**Files:**
- Modify: `handlers.py`
- Modify: `tests/test_handlers.py`

- [ ] **Step 1: Add save logic test**

Append to `tests/test_handlers.py`:

```python
from handlers import _build_log_data


def test_build_log_data_positive():
    user_data = {
        "location": "frontal",
        "pain_type": "throbbing",
        "intensity": 7,
        "onset_time_local": "10:00",
        "hydration_unit": "liters",
        "hydration_liters": 2.0,
        "hydration_raw_amount": 2.0,
        "coffee_count": 1,
        "medication": "none",
    }
    weather = {"temp_c": 22.5, "humidity_pct": 60, "pressure_hpa": 1013}
    data = _build_log_data(user_data, weather, had_headache=True)
    assert data["had_headache"] == 1
    assert data["location"] == "frontal"
    assert data["weather_temp_c"] == 22.5
    assert data["weather_fetch_ok"] == 1
    assert "logged_at_utc" in data
    assert "log_date_local" in data


def test_build_log_data_no_weather():
    data = _build_log_data({}, None, had_headache=False)
    assert data["had_headache"] == 0
    assert data["weather_temp_c"] is None
    assert data["weather_fetch_ok"] == 0
```

- [ ] **Step 2: Run new tests — expect failure**

```bash
pytest tests/test_handlers.py -k "build_log" -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add _build_log_data and handle_medication to handlers.py**

Append after `_ask_medication`:

```python
def _build_log_data(user_data: dict, weather: dict | None, had_headache: bool) -> dict:
    """Build the dict for insert_log_with_coffees from conversation user_data."""
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(config.TZ)
    return {
        "logged_at_utc": now_utc.isoformat(),
        "logged_at_local": now_local.isoformat(),
        "log_date_local": now_local.date().isoformat(),
        "had_headache": 1 if had_headache else 0,
        "location": user_data.get("location"),
        "pain_type": user_data.get("pain_type"),
        "intensity": user_data.get("intensity"),
        "onset_time_local": user_data.get("onset_time_local"),
        "hydration_unit": user_data.get("hydration_unit"),
        "hydration_liters": user_data.get("hydration_liters"),
        "hydration_raw_amount": user_data.get("hydration_raw_amount"),
        "coffee_count": user_data.get("coffee_count"),
        "medication": user_data.get("medication"),
        "weather_temp_c": weather["temp_c"] if weather else None,
        "weather_humidity_pct": weather["humidity_pct"] if weather else None,
        "weather_pressure_hpa": weather["pressure_hpa"] if weather else None,
        "weather_fetch_ok": 1 if weather else 0,
    }


@authorized
async def handle_medication(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["medication"] = query.data

    weather = await fetch_weather()
    data = _build_log_data(context.user_data, weather, had_headache=True)
    coffee_times = context.user_data.get("coffee_times", [])
    log_id = database.insert_log_with_coffees(data, coffee_times)
    logger.info("Saved headache log #%d", log_id)

    await _send_message(
        update, context,
        text=f"תודה, תרגיש טוב! הנתונים נשמרו. (#{log_id})",
    )
    context.user_data.clear()
    return ConversationHandler.END
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add handlers.py tests/test_handlers.py
git commit -m "feat: medication state with atomic DB save and weather"
```

---

## Task 12: handlers.py — Daily check-in and no_headache handler

**Files:**
- Modify: `handlers.py`

- [ ] **Step 1: Add send_daily_checkin and handle_no_headache to handlers.py**

Append after `handle_medication`:

```python
# ---------------------------------------------------------------------------
# Daily check-in (scheduler callback — not a user handler, no @authorized)
# ---------------------------------------------------------------------------

async def send_daily_checkin(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called by PTB JobQueue at 18:00 Asia/Jerusalem. Sends check-in if not yet logged."""
    today = datetime.now(config.TZ).date().isoformat()
    if database.get_today_log(today):
        logger.info("Daily check-in: already logged for %s, skipping", today)
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("כן", callback_data="yes_headache"),
        InlineKeyboardButton("לא", callback_data="no_headache"),
    ]])
    await context.bot.send_message(
        chat_id=config.AUTHORIZED_USER_ID,
        text="האם היה לך כאב ראש היום?",
        reply_markup=keyboard,
    )
    logger.info("Daily check-in sent for %s", today)


# ---------------------------------------------------------------------------
# Standalone handler — no headache path
# ---------------------------------------------------------------------------

@authorized
async def handle_no_headache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    weather = await fetch_weather()
    data = _build_log_data({}, weather, had_headache=False)
    log_id = database.insert_log_with_coffees(data, [])
    logger.info("Saved negative log #%d", log_id)

    await query.edit_message_text("נשמר. תרגיש טוב.")
```

- [ ] **Step 2: Run full test suite — expect all pass**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 3: Commit**

```bash
git add handlers.py
git commit -m "feat: daily check-in scheduler callback and no_headache handler"
```

---

## Task 13: handlers.py — /export command

**Files:**
- Modify: `handlers.py`

- [ ] **Step 1: Add export_handler to handlers.py**

Append after `handle_no_headache`:

```python
# ---------------------------------------------------------------------------
# /export command
# ---------------------------------------------------------------------------

@authorized
async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from datetime import date as _date
    import os

    filename = f"headache_logs_{_date.today().strftime('%Y%m%d')}.csv"
    csv_path = database.export_to_csv()
    try:
        with open(csv_path, "rb") as f:
            await update.message.reply_document(document=f, filename=filename)
    finally:
        os.unlink(csv_path)
```

- [ ] **Step 2: Run full test suite — no regression**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 3: Commit**

```bash
git add handlers.py
git commit -m "feat: /export command sends CSV attachment"
```

---

## Task 14: handlers.py — /delete ConversationHandler

**Files:**
- Modify: `handlers.py`

- [ ] **Step 1: Add delete handlers to handlers.py**

Append after `export_handler`:

```python
# ---------------------------------------------------------------------------
# /delete ConversationHandler
# ---------------------------------------------------------------------------

@authorized
async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logs = database.get_recent_logs(5)
    if not logs:
        await update.message.reply_text("אין רשומות למחיקה.")
        return ConversationHandler.END

    keyboard = []
    for log in logs:
        onset = log["onset_time_local"] or "—"
        label = f"{log['log_date_local']} {onset} (#{log['id']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"delete_select_{log['id']}")])

    await update.message.reply_text(
        "בחר רשומה למחיקה:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSE_RECORD


@authorized
async def handle_delete_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    log_id = int(query.data.split("_")[-1])
    context.user_data["delete_log_id"] = log_id

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("כן", callback_data=f"delete_confirm_{log_id}"),
        InlineKeyboardButton("לא", callback_data="delete_cancel"),
    ]])
    await query.edit_message_text(
        f"למחוק רשומה #{log_id}?",
        reply_markup=keyboard,
    )
    return CONFIRM_DELETE


@authorized
async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "delete_cancel":
        await query.edit_message_text("בוטל.")
        return ConversationHandler.END

    log_id = int(query.data.split("_")[-1])
    database.delete_log(log_id)
    logger.info("Deleted headache log #%d", log_id)
    await query.edit_message_text("נמחק.")
    return ConversationHandler.END
```

- [ ] **Step 2: Run full test suite — no regression**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 3: Commit**

```bash
git add handlers.py
git commit -m "feat: /delete ConversationHandler with confirmation"
```

---

## Task 15: bot.py — Application wiring and entry point

**Files:**
- Create: `bot.py`

- [ ] **Step 1: Create bot.py**

```python
import logging
import sys
from datetime import time

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database
import handlers

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _build_log_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("log", handlers.ask_location)],
        states={
            handlers.LOCATION: [CallbackQueryHandler(handlers.handle_location)],
            handlers.PAIN_TYPE: [CallbackQueryHandler(handlers.handle_pain_type)],
            handlers.INTENSITY: [CallbackQueryHandler(handlers.handle_intensity)],
            handlers.ONSET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_onset)
            ],
            handlers.HYDRATION_UNIT: [CallbackQueryHandler(handlers.handle_hydration_unit)],
            handlers.HYDRATION_AMOUNT: [
                CallbackQueryHandler(handlers.handle_hydration_amount_inline),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handlers.handle_hydration_amount_text
                ),
            ],
            handlers.COFFEE_COUNT: [CallbackQueryHandler(handlers.handle_coffee_count)],
            handlers.COFFEE_TIME_LOOP: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handlers.handle_coffee_time_loop
                )
            ],
            handlers.MEDICATION: [CallbackQueryHandler(handlers.handle_medication)],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )


def _build_checkin_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                handlers.ask_location_from_checkin, pattern="^yes_headache$"
            )
        ],
        states={
            handlers.LOCATION: [CallbackQueryHandler(handlers.handle_location)],
            handlers.PAIN_TYPE: [CallbackQueryHandler(handlers.handle_pain_type)],
            handlers.INTENSITY: [CallbackQueryHandler(handlers.handle_intensity)],
            handlers.ONSET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_onset)
            ],
            handlers.HYDRATION_UNIT: [CallbackQueryHandler(handlers.handle_hydration_unit)],
            handlers.HYDRATION_AMOUNT: [
                CallbackQueryHandler(handlers.handle_hydration_amount_inline),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handlers.handle_hydration_amount_text
                ),
            ],
            handlers.COFFEE_COUNT: [CallbackQueryHandler(handlers.handle_coffee_count)],
            handlers.COFFEE_TIME_LOOP: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handlers.handle_coffee_time_loop
                )
            ],
            handlers.MEDICATION: [CallbackQueryHandler(handlers.handle_medication)],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )


def _build_delete_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("delete", handlers.delete_handler)],
        states={
            handlers.CHOOSE_RECORD: [
                CallbackQueryHandler(
                    handlers.handle_delete_choice, pattern=r"^delete_select_\d+$"
                )
            ],
            handlers.CONFIRM_DELETE: [
                CallbackQueryHandler(
                    handlers.handle_delete_confirm,
                    pattern=r"^delete_(confirm_\d+|cancel)$",
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )


def main() -> None:
    database.init_db()
    logger.info("Database initialized at %s", config.DB_PATH)

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Conversation handlers (order: most specific first)
    app.add_handler(_build_log_conv())
    app.add_handler(_build_checkin_conv())
    app.add_handler(_build_delete_conv())

    # Standalone handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("export", handlers.export_handler))
    app.add_handler(
        CallbackQueryHandler(handlers.handle_no_headache, pattern="^no_headache$")
    )

    # Daily check-in job at 18:00 Asia/Jerusalem
    app.job_queue.run_daily(
        handlers.send_daily_checkin,
        time=time(hour=config.CHECKIN_HOUR, minute=config.CHECKIN_MINUTE, tzinfo=config.TZ),
    )
    logger.info(
        "Daily check-in scheduled at %02d:%02d (%s)",
        config.CHECKIN_HOUR,
        config.CHECKIN_MINUTE,
        config.TZ,
    )

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite — no regression**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "feat: bot.py wires both ConversationHandlers and daily JobQueue"
```

---

## Task 16: Docker, docker-compose, .env, README

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Jerusalem

RUN useradd -m -u 1000 botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth.py bot.py config.py database.py handlers.py weather.py ./

RUN mkdir -p /app/data && chown botuser:botuser /app/data

USER botuser

CMD ["python", "bot.py"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  headache-bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
```

- [ ] **Step 3: Create README.md**

The README must contain these sections with full detail:

```markdown
# Headache Tracker Telegram Bot

Personal Telegram bot for daily headache tracking. Produces structured SQLite data for neurologist review.

## Prerequisites

1. **Telegram Bot Token** — Message [@BotFather](https://t.me/BotFather) on Telegram. Send `/newbot`, follow the prompts. Copy the token (looks like `123456789:ABCdef...`).
2. **OpenWeatherMap API Key** — Register at [openweathermap.org](https://openweathermap.org/api). Subscribe to the free "Current Weather Data" plan. Your API key appears in your account dashboard.
3. **Your Telegram User ID** — Message [@userinfobot](https://t.me/userinfobot). It replies with your numeric user ID. This is what goes in `AUTHORIZED_USER_ID`.

## Proxmox LXC Setup

### 1. Create the LXC container

In Proxmox, go to **Create CT**:
- Template: Debian 12 (bookworm)
- CPU: 1 core
- Memory: 512 MB
- Disk: 4 GB
- Network: DHCP or static IP

After creation, go to **Options → Features** and enable:
- `nesting=1`
- `keyctl=1`

These are required for Docker to run inside an LXC container.

### 2. Install Docker inside the LXC

Start the container and open a console:

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
newgrp docker
docker run hello-world
```

### 3. Install Portainer CE

```bash
docker volume create portainer_data
docker run -d -p 9000:9000 --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

Access Portainer at `http://<LXC_IP>:9000`.

## Deployment via Portainer

### Option A: Git repository (recommended)

1. In Portainer: **Stacks → Add stack → Git repository**
2. Repository URL: your fork/clone of this repo
3. Under **Environment variables**, add:
   - `TELEGRAM_BOT_TOKEN` = your token
   - `OWM_API_KEY` = your OWM key
   - `AUTHORIZED_USER_ID` = your Telegram numeric ID
   - `TZ` = `Asia/Jerusalem`
4. Click **Deploy the stack**

### Option B: Web editor

1. In Portainer: **Stacks → Add stack → Web editor**
2. Paste the contents of `docker-compose.yml`
3. Add the same environment variables as Option A
4. Click **Deploy the stack**

## Place the Head Map Image

Upload the labeled head illustration to the data directory on the LXC:

```bash
scp head_map.png root@<LXC_IP>:/path/to/project/data/head_map.png
```

The bot loads it from `/app/data/head_map.png` inside the container (bind-mounted from `./data`). If the file is missing, the bot sends text only and logs a warning — it will not crash.

## Verify Deployment

```bash
docker logs headache-bot --tail 50
```

Expected output:
```
... INFO database: Database initialized at /app/data/headaches.db
... INFO bot: Daily check-in scheduled at 18:00 (Asia/Jerusalem)
... INFO bot: Bot starting (polling)...
```

Send `/start` to your bot in Telegram. You should receive the Hebrew welcome message.

## Backups

**Export DB manually:**
```bash
docker cp headache-bot:/app/data/headaches.db ./headaches_backup_$(date +%Y%m%d).db
```

**LXC snapshots in Proxmox** cover the entire container filesystem including the bind-mounted `./data` directory. Take a snapshot before updates.

## Updating

```bash
git pull
```

Then in Portainer: open the stack → **Pull and redeploy**.

## Troubleshooting

| Symptom | Check |
|---|---|
| Timezone wrong in logs | Verify `TZ=Asia/Jerusalem` in your `.env` or Portainer env vars |
| Daily check-in not firing at 18:00 | Run `docker logs headache-bot` at 18:05 and look for "Daily check-in" entries |
| Weather always NULL | Test your OWM key: `curl "https://api.openweathermap.org/data/2.5/weather?lat=32.0556&lon=34.8550&units=metric&appid=YOUR_KEY"` |
| Bot not responding | Confirm `AUTHORIZED_USER_ID` matches your actual Telegram ID (get it from @userinfobot) |
| Docker won't start in LXC | Ensure `nesting=1` and `keyctl=1` are set in Proxmox LXC Options → Features |
```

- [ ] **Step 4: Run full test suite — final check**

```bash
pytest -v
```

Expected: all passed.

- [ ] **Step 5: Final commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "feat: Dockerfile, docker-compose, and Proxmox deployment README"
```

---

## Verification Checklist (run before closing)

- [ ] Every user-facing string is Hebrew; every `callback_data` and DB value is English
- [ ] Every ConversationHandler state has `/cancel` in its `fallbacks`
- [ ] Coffee loop uses `cup_index` in `user_data`; bounded by `coffee_count` (max 5)
- [ ] Weather failure sets fields to NULL and continues — does not block `insert_log_with_coffees`
- [ ] `@authorized` wraps every handler that processes incoming updates
- [ ] `insert_log_with_coffees` uses a single `with conn:` block — atomic
- [ ] `.env` in `.gitignore`
- [ ] `requirements.txt` has pinned versions
- [ ] `pytest -v` passes with zero failures
