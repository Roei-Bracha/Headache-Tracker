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
