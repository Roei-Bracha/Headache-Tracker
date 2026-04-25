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
