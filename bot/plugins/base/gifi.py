# bot/plugins/base/gifi.py file :
import random
import asyncio
import logging
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.database import MongoDB  # برای ادغام با DB (افزایش کلیک)
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrotools import HelpCmd

logger = logging.getLogger(__name__)  # لاگ پروژه‌ت

database = MongoDB()  # برای DB

# ذخیره داده‌ها (برای سادگی؛ در مقیاس بزرگ به Redis/DB منتقل کنید)
user_lucky_numbers = {}
user_attempts = {}
user_failed = {}

@Client.on_message(filters.private & filters.command("gifi"))
@RateLimiter.hybrid_limiter(func_count=1)
async def gifi_command(client: Client, message):
    user_id = message.from_user.id
    lucky_number = random.randint(1, 10)

    # ذخیره اطلاعات کاربر
    user_lucky_numbers[user_id] = lucky_number
    user_attempts[user_id] = 3  # هر کاربر ۳ بار می‌تونه تلاش کنه
    user_failed[user_id] = True

    # ساخت دکمه‌ها به همراه شماره و متن
    buttons = []
    for i in range(1, 11):
        buttons.append(InlineKeyboardButton(f"{i}", callback_data=f"gifi:{i}"))

    keyboard = [buttons[i:i + 3] for i in range(0, 10, 3)]

    await message.reply(
        "یکی از دکمه‌ها جایزه داره، پیداش کن! (۳ تلاش داری)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    logger.info(f"Gifi started for user {user_id}, lucky: {lucky_number}")

@Client.on_callback_query(filters.regex(r"gifi:(\d+)"))
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_gifi_click(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        chosen = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        await callback_query.answer("خطا در خواندن دکمه!", show_alert=True)
        logger.error(f"Invalid callback data: {callback_query.data} for user {user_id}")
        return

    lucky = user_lucky_numbers.get(user_id)
    remaining = user_attempts.get(user_id, 0)

    logger.info(f"Gifi click by {user_id}: chosen={chosen}, lucky={lucky}, remaining={remaining}")

    if remaining <= 0:
        await callback_query.answer("تعداد تلاش شما تمام شده!", show_alert=True)
        return

    msg = callback_query.message
    current_text = msg.text or "بازی Gifi"  # متن ثابت

    if chosen == lucky:
        await callback_query.answer("تبریک! شما برنده شدی! ⭐", show_alert=True)
        logger.info(f"User {user_id} won Gifi! Adding +1 daily click")

        # بازسازی کامل markup با جایزه
        new_buttons = []
        for i in range(1, 11):
            if i == lucky:
                new_buttons.append(InlineKeyboardButton(f"{i} ⭐ جایزه!", callback_data=f"gifi:{i}"))
            else:
                new_buttons.append(InlineKeyboardButton(f"{i}", callback_data=f"gifi:{i}"))
        new_keyboard = [new_buttons[i:i + 3] for i in range(0, 10, 3)]

        # Edit markup
        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        # Force edit text to apply markup
        await msg.edit_text(current_text)

        user_attempts[user_id] = 0
        user_failed[user_id] = False

        # جایزه واقعی: +1 به daily_clicks (حداکثر، نه limit)
        await database.increase_daily_clicks(user_id)  # از moderation.py
        await msg.reply("🎉 تبریک! به عنوان جایزه، ۱ کلیک اضافی به پلن روزانه‌ت اضافه شد! چک کن با /myplan")

        return

    # اگر اشتباه زده
    user_attempts[user_id] = remaining - 1
    await callback_query.answer(f"پوچ! ❌ تلاش باقی‌مانده: {remaining - 1}", show_alert=False)

    # بازسازی کامل markup با پوچ
    new_buttons = []
    for i in range(1, 11):
        if i == chosen:
            new_buttons.append(InlineKeyboardButton(f"{i} ❌ پوچ", callback_data=f"gifi:{i}"))
        else:
            # اگر قبلاً پوچ یا جایزه بوده، نگه دار؛ وگرنه عدد ساده
            current_markup = msg.reply_markup.inline_keyboard if msg.reply_markup else []
            found_btn = next((btn for row in current_markup for btn in row if btn.callback_data == f"gifi:{i}"), None)
            if found_btn and (found_btn.text.endswith("پوچ") or found_btn.text.endswith("جایزه!")):
                new_buttons.append(InlineKeyboardButton(found_btn.text, callback_data=f"gifi:{i}"))
            else:
                new_buttons.append(InlineKeyboardButton(f"{i}", callback_data=f"gifi:{i}"))

    new_keyboard = [new_buttons[i:i + 3] for i in range(0, 10, 3)]
    logger.info(f"Updating button {chosen} to پوچ for user {user_id}")

    # Edit markup
    await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
    # Force edit text
    await msg.edit_text(current_text)

    # اگر تلاش تموم شد و نبرده بود
    if user_attempts[user_id] == 0 and user_failed.get(user_id, True):
        await callback_query.message.reply("۳ بار تلاش کردی و موفق نشدی! پاسخ درست تا ۵ ثانیه دیگه نمایش داده می‌شه...")
        await asyncio.sleep(5)

        # نمایش نهایی: همه پوچ + جایزه
        final_buttons = []
        for i in range(1, 11):
            if i == lucky:
                text = f"{i} ⭐ جایزه!"
            else:
                text = f"{i} ❌ پوچ"
            final_buttons.append(InlineKeyboardButton(text, callback_data=f"gifi:{i}"))

        final_keyboard = [final_buttons[i:i + 3] for i in range(0, 10, 3)]

        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(final_keyboard))
        await msg.edit_text(current_text)
        logger.info(f"Gifi ended for {user_id}, lucky was {lucky}")

HelpCmd.set_help(
    command="gifi",
    description="بازی حدس جایزه: یکی از دکمه‌ها جایزه داره، پیداش کن! (۳ تلاش داری)",
    allow_global=True,
    allow_non_admin=True,
)
