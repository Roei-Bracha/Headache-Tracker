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
