import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from database import init_db
from handlers.admin import (
    cmd_start, cmd_set_menu, cmd_report, cmd_confirm_payment,
    cmd_remind_all, cmd_set_phone, cmd_close_day
)
from handlers.user import cmd_lunch, cmd_paid, handle_receipt_photo
from handlers.common import button_callback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")

    init_db()

    app = Application.builder().token(token).build()

    # Common
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Admin commands
    app.add_handler(CommandHandler("setmenu", cmd_set_menu))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("remindall", cmd_remind_all))
    app.add_handler(CommandHandler("setphone", cmd_set_phone))
    app.add_handler(CommandHandler("closeday", cmd_close_day))

    # User commands
    app.add_handler(CommandHandler("lunch", cmd_lunch))
    app.add_handler(CommandHandler("paid", cmd_paid))

    # Photo handler for receipts
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_receipt_photo))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
