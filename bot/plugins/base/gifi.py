# bot/plugins/base/gifi.py file :
import random
import asyncio
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrotools import HelpCmd

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

@Client.on_callback_query(filters.regex(r"gifi:(\d+)"))
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_gifi_click(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    chosen = int(callback_query.data.split(":")[1])
    lucky = user_lucky_numbers.get(user_id)
    remaining = user_attempts.get(user_id, 0)

    if remaining <= 0:
        await callback_query.answer("تعداد تلاش شما تمام شده!", show_alert=True)
        return

    msg = callback_query.message
    keyboard = msg.reply_markup.inline_keyboard

    if chosen == lucky:
        await callback_query.answer("تبریک! شما برنده شدی!", show_alert=True)

        # آپدیت دکمه جایزه
        new_keyboard = []
        for row in keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data == f"gifi:{lucky}":
                    new_row.append(InlineKeyboardButton(f"{lucky} ⭐ جایزه!", callback_data=btn.callback_data))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)

        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        user_attempts[user_id] = 0
        user_failed[user_id] = False  # چون برده
        # TODO: اینجا می‌تونی جایزه واقعی اضافه کنی، مثل افزایش کلیک روزانه یا پیام خاص
        await msg.reply("🎉 تبریک! به عنوان جایزه، ۱ کلیک اضافی به پلن روزانه‌ت اضافه شد! (فعلاً شبیه‌سازی؛ برای ادغام واقعی با DB، moderation.py رو تغییر بده)")
        return

    # اگر اشتباه زده
    user_attempts[user_id] = remaining - 1
    await callback_query.answer(f"پوچ! تلاش باقی‌مانده: {remaining - 1}", show_alert=False)

    # دکمه‌ای که کلیک شده رو پوچ کن
    new_keyboard = []
    for row in keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data == f"gifi:{chosen}" and not btn.text.endswith("پوچ"):
                new_row.append(InlineKeyboardButton(f"{chosen} ❌ پوچ", callback_data=btn.callback_data))
            else:
                new_row.append(btn)
        new_keyboard.append(new_row)

    await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))

    # اگر تلاش تموم شد و نبرده بود
    if user_attempts[user_id] == 0 and user_failed.get(user_id, True):
        await callback_query.message.reply("۳ بار تلاش کردی و موفق نشدی! پاسخ درست تا ۵ ثانیه دیگه نمایش داده می‌شه...")
        await asyncio.sleep(5)

        # نمایش نهایی دکمه‌ها
        final_keyboard = []
        for i in range(1, 11):
            if i == lucky:
                text = f"{i} ⭐ جایزه!"
            else:
                text = f"{i} ❌ پوچ"
            final_keyboard.append(InlineKeyboardButton(text, callback_data=f"gifi:{i}"))

        final_layout = [final_keyboard[i:i + 3] for i in range(0, 10, 3)]

        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(final_layout))

HelpCmd.set_help(
    command="gifi",
    description="بازی حدس جایزه: یکی از دکمه‌ها جایزه داره، پیداش کن! (۳ تلاش داری)",
    allow_global=True,
    allow_non_admin=True,
)
