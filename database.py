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
