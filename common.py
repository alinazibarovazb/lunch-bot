from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from handlers.admin import cmd_confirm_payment


async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # ── User orders a menu item ────────────────────────────────────────────────
    if data.startswith("order:"):
        menu_item_id = int(data.split(":")[1])
        user = update.effective_user

        # Get menu item
        menu = db.get_menu()
        item = next((m for m in menu if m["id"] == menu_item_id), None)
        if not item:
            await query.answer("Позиция не найдена.", show_alert=True)
            return

        order_id = db.create_order(
            user_id=user.id,
            username=user.username or "",
            full_name=user.full_name,
            menu_item_id=item["id"],
            item_name=item["item_name"],
            price=item["price"]
        )

        phone = db.get_setting("payment_phone") or "уточни у офис-менеджера"

        await query.edit_message_text(
            f"✅ Заказ принят!\n\n"
            f"🍱 {item['item_name']} — {item['price']} руб\n\n"
            f"💳 Переведи {item['price']} руб по номеру на Озон Банк:\n"
            f"📱 {phone}\n\n"
            f"После перевода отправь сюда фото чека — это подтвердит оплату автоматически!"
        )

    # ── Admin confirms payment ─────────────────────────────────────────────────
    elif data.startswith("confirm:"):
        user = update.effective_user
        if not db.is_admin(user.id):
            await query.answer("⛔ Нет доступа.", show_alert=True)
            return
        await cmd_confirm_payment(update, ctx)

    # ── Admin rejects payment ──────────────────────────────────────────────────
    elif data.startswith("reject:"):
        user = update.effective_user
        if not db.is_admin(user.id):
            await query.answer("⛔ Нет доступа.", show_alert=True)
            return

        await query.answer()
        order_id = int(data.split(":")[1])
        order = db.get_order_by_id(order_id)
        if not order:
            return await query.edit_message_caption(caption="❌ Заказ не найден.")

        db.update_order_status(order_id, "ordered")

        phone = db.get_setting("payment_phone") or "уточни у офис-менеджера"

        try:
            await ctx.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"❌ Чек не принят — возможно, сумма или реквизиты не совпали.\n\n"
                    f"🍱 {order['item_name']} — {order['price']} руб\n"
                    f"📱 Номер для перевода: {phone}\n\n"
                    f"Пожалуйста, отправь новый чек командой /paid"
                )
            )
        except Exception:
            pass

        await query.edit_message_caption(
            caption=f"❌ Оплата отклонена\n👤 {order['full_name']}\n🍱 {order['item_name']} — {order['price']} руб"
        )
