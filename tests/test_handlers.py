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
