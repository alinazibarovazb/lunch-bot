import logging
import os
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

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


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


def self_ping():
    """Пингует сам себя каждые 10 минут чтобы Render не усыплял сервис"""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        logger.info("RENDER_EXTERNAL_URL не задан, self-ping отключён")
        return
    while True:
        time.sleep(600)  # 10 минут
        try:
            urllib.request.urlopen(url, timeout=10)
            logger.info("Self-ping OK")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")

    init_db()

    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("setmenu", cmd_set_menu))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("remindall", cmd_remind_all))
    app.add_handler(CommandHandler("setphone", cmd_set_phone))
    app.add_handler(CommandHandler("closeday", cmd_close_day))
    app.add_handler(CommandHandler("lunch", cmd_lunch))
    app.add_handler(CommandHandler("paid", cmd_paid))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_receipt_photo))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
