import re
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_admin(user.id):
        text = (
            f"👋 Привет, {user.first_name}! Ты офис-менеджер.\n\n"
            "📋 Команды:\n"
            "/setmenu — задать меню дня\n"
            "/report — отчёт по оплатам\n"
            "/remindall — напомнить всем должникам\n"
            "/setphone — задать номер для переводов\n"
            "/closeday — закрыть день\n"
        )
    else:
        text = (
            f"👋 Привет, {user.first_name}!\n\n"
            "🍱 Команды:\n"
            "/lunch — выбрать обед\n"
            "/paid — подтвердить оплату (отправь чек)\n"
        )
    await update.message.reply_text(text)


async def cmd_set_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    if not ctx.args:
        phone = db.get_setting("payment_phone")
        return await update.message.reply_text(
            f"Текущий номер: {phone or 'не задан'}\n\nИспользуй: /setphone +79001234567"
        )
    phone = ctx.args[0]
    db.set_setting("payment_phone", phone)
    await update.message.reply_text(f"✅ Номер для оплаты сохранён: {phone}")


async def cmd_set_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    if not ctx.args:
        return await update.message.reply_text(
            "Формат (название - цена - количество, количество опционально):\n"
            "/setmenu\nСуп - 300 - 10\nПлов - 500 - 8\nСалат - 400"
        )

    raw = " ".join(ctx.args)
    raw = raw.replace("\n", " ")
    raw = re.sub(r'(\d+)\s+(?=[^\d\s])', r'\1\n', raw)
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    items = []
    for line in lines:
        # Парсим строку: название - цена - (опционально) количество
        m = re.match(r"^(.+?)\s*[-–—]\s*(\d+)\s*(?:[-–—]\s*(\d+))?\s*$", line)
        if m:
            items.append({
                "name": m.group(1).strip(),
                "price": int(m.group(2)),
                "quantity": int(m.group(3)) if m.group(3) else 99
            })

    if not items:
        return await update.message.reply_text(
            "❌ Не удалось распознать меню.\n\n"
            "Формат:\n/setmenu\nСуп - 300 - 10\nПлов - 500 - 8"
        )

    db.set_menu(items)

    lines_out = "\n".join(
        f"• {i['name']} — {i['price']} руб × {i['quantity']} шт"
        for i in items
    )
    await update.message.reply_text(
        f"✅ Меню на сегодня сохранено:\n\n{lines_out}\n\n"
        f"Сотрудники могут выбрать обед командой /lunch"
    )


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    orders = db.get_orders_today()
    menu = db.get_menu()

    if not orders and not menu:
        return await update.message.reply_text("📭 Сегодня заказов нет.")

    confirmed = [o for o in orders if o["status"] == "confirmed"]
    pending = [o for o in orders if o["status"] == "pending_confirm"]
    unpaid = [o for o in orders if o["status"] == "ordered"]

    total_confirmed = sum(o["price"] for o in confirmed)
    total_pending = sum(o["price"] for o in pending)
    total_unpaid = sum(o["price"] for o in unpaid)

    text = f"📊 Отчёт за {date.today().strftime('%d.%m.%Y')}\n\n"

    if confirmed:
        text += f"✅ Оплачено ({len(confirmed)} чел.) — {total_confirmed} руб:\n"
        for o in confirmed:
            text += f"  • {o['full_name']} — {o['item_name']} ({o['price']} руб)\n"
        text += "\n"

    if pending:
        text += f"🟡 Ожидает подтверждения ({len(pending)} чел.) — {total_pending} руб:\n"
        for o in pending:
            text += f"  • {o['full_name']} — {o['item_name']} ({o['price']} руб)\n"
        text += "\n"

    if unpaid:
        text += f"❌ Не оплатили ({len(unpaid)} чел.) — {total_unpaid} руб:\n"
        for o in unpaid:
            text += f"  • {o['full_name']} — {o['item_name']} ({o['price']} руб)\n"
        text += "\n"

    total = total_confirmed + total_pending + total_unpaid
    text += f"💰 Итого заказов: {total} руб\n"
    text += f"💵 Получено: {total_confirmed} руб\n"
    text += f"⏳ Ожидается: {total_pending + total_unpaid} руб\n\n"

    # Остатки по позициям
    if menu:
        text += "📦 Остатки:\n"
        for item in menu:
            remaining = db.get_menu_item_remaining(item["id"])
            sold = item["quantity"] - remaining
            text += f"  • {item['item_name']}: привезли {item['quantity']} шт, продано {sold}, осталось {remaining}\n"

    await update.message.reply_text(text)

async def cmd_remind_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    unpaid = db.get_unpaid_orders_today()
    phone = db.get_setting("payment_phone") or "номер не задан"
    if not unpaid:
        return await update.message.reply_text("🎉 Все оплатили!")
    sent = 0
    for order in unpaid:
        try:
            await ctx.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"🔔 Напоминание об оплате обеда!\n\n"
                    f"🍱 {order['item_name']} — {order['price']} руб\n"
                    f"📱 Переведи на номер на Озон Банк: {phone}\n\n"
                    f"После оплаты отправь чек командой /paid"
                )
            )
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"📨 Напоминания отправлены: {sent} из {len(unpaid)}")


async def cmd_confirm_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    order = db.get_order_by_id(order_id)
    if not order:
        return await query.edit_message_text("❌ Заказ не найден.")
    db.update_order_status(order_id, "confirmed")
    try:
        await ctx.bot.send_message(
            chat_id=order["user_id"],
            text=f"✅ Твоя оплата подтверждена!\n🍱 {order['item_name']} — {order['price']} руб\nСпасибо!"
        )
    except Exception:
        pass
    await query.edit_message_caption(
        caption=f"✅ Оплата подтверждена\n👤 {order['full_name']}\n🍱 {order['item_name']} — {order['price']} руб"
    )


async def cmd_close_day(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.is_admin(user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    orders = db.get_orders_today()
    confirmed = [o for o in orders if o["status"] == "confirmed"]
    not_paid = [o for o in orders if o["status"] != "confirmed"]
    total = sum(o["price"] for o in confirmed)
    text = f"📅 День закрыт — {date.today().strftime('%d.%m.%Y')}\n\n"
    text += f"✅ Оплачено: {len(confirmed)} чел. / {total} руб\n"
    if not_paid:
        text += f"❌ Не оплатили: {len(not_paid)} чел.\n"
        for o in not_paid:
            text += f"  • {o['full_name']} — {o['price']} руб\n"
    await update.message.reply_text(text)
