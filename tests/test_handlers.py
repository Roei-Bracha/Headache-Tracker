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
