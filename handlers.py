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
