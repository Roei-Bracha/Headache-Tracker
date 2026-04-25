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
