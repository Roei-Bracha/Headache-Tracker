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
