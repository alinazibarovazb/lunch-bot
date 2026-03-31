import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db


async def cmd_lunch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    menu = db.get_menu()

    if not menu:
        return await update.message.reply_text(
            "😕 Меню на сегодня ещё не добавлено.\nОжидай, офис-менеджер скоро добавит!"
        )

    keyboard = []
    for item in menu:
        keyboard.append([
            InlineKeyboardButton(
                f"🍽 {item['item_name']} — {item['price']} руб",
                callback_data=f"order:{item['id']}"
            )
        ])

    await update.message.reply_text(
        "🍱 Меню на сегодня:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order = db.get_user_order_today(user.id)

    if not order:
        return await update.message.reply_text(
            "😕 У тебя нет заказа на сегодня. Сначала выбери обед: /lunch"
        )

    if order["status"] == "confirmed":
        return await update.message.reply_text("✅ Твоя последняя оплата уже подтверждена!")

    if order["status"] == "pending_confirm":
        return await update.message.reply_text("🟡 Чек уже отправлен, ожидай подтверждения.")

    phone = db.get_setting("payment_phone") or "уточни у офис-менеджера"

    all_orders = db.get_orders_today()
    unpaid = [o for o in all_orders if o["user_id"] == user.id and o["status"] == "ordered"]
    total = sum(o["price"] for o in unpaid)

    if len(unpaid) > 1:
        items_text = "\n".join(f"  • {o['item_name']} — {o['price']} руб" for o in unpaid)
        await update.message.reply_text(
            f"💳 У тебя {len(unpaid)} неоплаченных заказа на сумму {total} руб:\n{items_text}\n\n"
            f"Переведи {total} руб по номеру на Озон Банк:\n"
            f"📱 {phone}\n\n"
            f"После перевода отправь сюда скриншот или фото чека."
        )
    else:
        await update.message.reply_text(
            f"💳 Для оплаты переведи {order['price']} руб по номеру на Озон Банк:\n"
            f"📱 {phone}\n\n"
            f"После перевода отправь сюда скриншот или фото чека — "
            f"и я автоматически передам его офис-менеджеру на подтверждение."
        )


async def handle_receipt_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order = db.get_user_order_today(user.id)

    if not order:
        return await update.message.reply_text(
            "😕 У тебя нет заказа на сегодня. Сначала выбери обед: /lunch"
        )

    if order["status"] == "confirmed":
        return await update.message.reply_text("✅ Твоя оплата уже подтверждена!")

    photo = update.message.photo[-1]
    file_id = photo.file_id

    db.update_order_status(order["id"], "pending_confirm", receipt_file_id=file_id)

    await update.message.reply_text(
        f"📨 Чек получен! Передаю офис-менеджеру на проверку.\n"
        f"🟡 Статус: ожидает подтверждения"
    )

    admin_id = os.environ.get("ADMIN_ID")
    if admin_id:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm:{order['id']}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{order['id']}")
        ]])
        caption = (
            f"💳 Новый чек об оплате!\n"
            f"👤 {user.full_name} (@{user.username or '-'})\n"
            f"🍱 {order['item_name']} — {order['price']} руб"
        )
        try:
            await ctx.bot.send_photo(
                chat_id=int(admin_id),
                photo=file_id,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception:
            pass
