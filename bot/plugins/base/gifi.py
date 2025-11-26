# bot/plugins/base/gifi.py file :
import random
import asyncio
import time
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.database import MongoDB
from bot.config import config  # برای LOG_CHANNEL
from bot.utilities.pyrotools import HelpCmd

database = MongoDB()

# ذخیره داده‌ها
user_lucky_numbers = {}
user_attempts = {}
user_failed = {}
user_last_use = {}  # برای cooldown: {user_id: timestamp}

COOLDOWN_SECONDS = 30  # 12 ساعت 43200
VIP_PLAN_NAME = "vip_15days"  # از vip_code.py
LOG_CHANNEL = config.BACKUP_CHANNEL  # کانال لاگ

def is_markup_different(old_markup, new_markup):
    """چک اگر markup جدید متفاوت باشه (برای جلوگیری از MESSAGE_NOT_MODIFIED)."""
    if not old_markup:
        return True
    old_keyboard = old_markup.inline_keyboard
    new_keyboard = new_markup.inline_keyboard
    if len(old_keyboard) != len(new_keyboard):
        return True
    for old_row, new_row in zip(old_keyboard, new_keyboard):
        if len(old_row) != len(new_row):
            return True
        for old_btn, new_btn in zip(old_row, new_row):
            if old_btn.text != new_btn.text or old_btn.callback_data != new_btn.callback_data:
                return True
    return False

@Client.on_message(filters.private & filters.command("gifi"))
async def gifi_command(client: Client, message):
    user_id = message.from_user.id
    current_time = time.time()

    # چک cooldown
    if user_id in user_last_use:
        time_since_last = current_time - user_last_use[user_id]
        if time_since_last < COOLDOWN_SECONDS:
            remaining = COOLDOWN_SECONDS - time_since_last
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            seconds = int(remaining % 60)
            await message.reply(
                f"⏰ صبر کن! می‌تونی هر 12 ساعت یکبار بازی کنی.\n"
                f"زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه و {seconds} ثانیه."
            )
            return

    lucky_number = random.randint(1, 10)

    # ذخیره اطلاعات کاربر
    user_lucky_numbers[user_id] = lucky_number
    user_attempts[user_id] = 8  # ۱ تلاش
    user_failed[user_id] = True
    user_last_use[user_id] = current_time  # آپدیت cooldown

    # ساخت دکمه‌ها به همراه شماره و متن
    buttons = []
    for i in range(1, 11):
        buttons.append(InlineKeyboardButton(f"{i}", callback_data=f"gifi:{i}"))

    keyboard = [buttons[i:i + 3] for i in range(0, 10, 3)]

    await message.reply(
        "یکی از دکمه‌ها جایزه داره، پیداش کن! (۱ تلاش داری)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"gifi:(\d+)"))
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

    # چک اگر این دکمه قبلاً انتخاب شده (پوچ)
    is_already_chosen = False
    for row in keyboard:
        for btn in row:
            if btn.callback_data == f"gifi:{chosen}" and btn.text.endswith(". پوچ"):
                is_already_chosen = True
                break
        if is_already_chosen:
            break

    if is_already_chosen:
        await callback_query.answer("این عدد قبلا انتخاب شده است!", show_alert=True)
        return

    if chosen == lucky:
        await callback_query.answer("تبریک! شما برنده شدی!", show_alert=True)

        # آپدیت دکمه جایزه
        new_keyboard = []
        for row in keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data == f"gifi:{lucky}":
                    new_row.append(InlineKeyboardButton(f"{lucky}. جایزه!", callback_data=btn.callback_data))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)

        new_markup = InlineKeyboardMarkup(new_keyboard)
        if is_markup_different(msg.reply_markup, new_markup):
            await msg.edit_reply_markup(reply_markup=new_markup)

        user_attempts[user_id] = 0
        user_failed[user_id] = False  # چون برده

        # جایزه: ارسال کد VIP
        collection = database.db["VIPCodes"]
        unused_codes = await collection.find({"used": False}).to_list(length=None)
        if unused_codes:
            # انتخاب random
            vip_code = random.choice(unused_codes)
            code_str = vip_code["code"]
            # حذف یا mark used
            await collection.update_one(
                {"_id": vip_code["_id"]},
                {"$set": {"used": True, "used_by": user_id, "used_at": time.strftime("%Y-%m-%d %H:%M:%S")}}
            )
            await callback_query.message.reply(
                f"تبریک شما برنده شدید! 🪅\nکد جایزه: `{code_str}`\n\n(این کد رو با /vip استفاده کن!)"
            )

            # لاگ در کانال LOG_CHANNEL
            user_name = callback_query.from_user.first_name or "نامشخص"
            log_text = f"""✅ جایزه واریز شد.

👤 نام کاربر: {user_name}
🆔 آیدی عددی: {user_id}
🪅 نوع پلن: {VIP_PLAN_NAME}"""
            try:
                await client.send_message(LOG_CHANNEL, log_text)
            except Exception as e:
                print(f"Failed to send log to channel {LOG_CHANNEL}: {e}")  # ساده لاگ
        else:
            await callback_query.message.reply("تبریک برنده شدی! 🪅 (متأسفانه کد جایزه موجود نیست. بعداً امتحان کن.)")
        return

    # اگر اشتباه زده
    user_attempts[user_id] = remaining - 1
    await callback_query.answer(f"پوچ! تلاش باقی‌مانده: {remaining - 1}", show_alert=False)

    # دکمه‌ای که کلیک شده رو پوچ کن
    new_keyboard = []
    for row in keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data == f"gifi:{chosen}" and not btn.text.endswith(".پوچ"):
                new_row.append(InlineKeyboardButton(f"{chosen}. پوچ", callback_data=btn.callback_data))
            else:
                new_row.append(btn)
        new_keyboard.append(new_row)

    new_markup = InlineKeyboardMarkup(new_keyboard)
    if is_markup_different(msg.reply_markup, new_markup):
        await msg.edit_reply_markup(reply_markup=new_markup)

    # اگر تلاش تموم شد و نبرده بود
    if user_attempts[user_id] == 0 and user_failed.get(user_id, True):
        await callback_query.message.reply("۱ بار تلاش کردی و موفق نشدی! پاسخ درست تا ۵ ثانیه دیگه نمایش داده می‌شه...")
        await asyncio.sleep(5)

        # نمایش نهایی دکمه‌ها
        final_keyboard = []
        for i in range(1, 11):
            if i == lucky:
                text = f"{i}. جایزه!"
            else:
                text = f"{i}. پوچ"
            final_keyboard.append(InlineKeyboardButton(text, callback_data=f"gifi:{i}"))

        final_layout = [final_keyboard[i:i + 3] for i in range(0, 10, 3)]

        final_markup = InlineKeyboardMarkup(final_layout)
        if is_markup_different(msg.reply_markup, final_markup):
            await msg.edit_reply_markup(reply_markup=final_markup)

HelpCmd.set_help(
    command="gifi",
    description="بازی حدس جایزه: یکی از دکمه‌ها جایزه داره، پیداش کن! (۱ تلاش داری، هر ۱۲ ساعت یکبار)",
    allow_global=True,
    allow_non_admin=True,
)
