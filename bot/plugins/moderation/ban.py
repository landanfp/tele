# bot/plugins/moderation/ban.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.errors import PeerIdInvalid
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import config
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import ConvoMessage
from bot.utilities.pyrofilters import PyroFilters

database = MongoDB()


@Client.on_message(
    filters.private & PyroFilters.admin() & filters.command("ban"),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def ban_user(client: Client, message: ConvoMessage) -> Message | None:
    """کاربر را از استفاده ربات بن می‌کند."""

    # 1. بررسی ادمین بودن (برای اجرای دستور)
    if message.from_user.id not in config.ROOT_ADMINS_ID:
        return await message.reply(
            text="❌ **شما ادمین نیستید!**",
            quote=True,
        )

    # 2. اعتبارسنجی ورودی
    if len(message.command) != 2:
        return await message.reply(
            text="⚠️ **دستور اشتباه!**\n\n**روش استفاده:** `/ban {user_id}`",
            quote=True,
        )
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply(
            text="⚠️ **آیدی کاربر باید یک عدد باشد.**",
            quote=True,
        )

    # 3. بررسی بن قبلی
    if await database.is_user_banned(user_id):
        return await message.reply(
            text=f"⚠️ کاربر با آیدی `{user_id}` قبلاً بن شده است.",
            quote=True,
        )

    # 4. دریافت نام کاربر برای نمایش
    try:
        user = await client.get_users(user_id)
        user_name = user.first_name if user.first_name else f"کاربر {user_id}"
    except Exception:
        user_name = f"کاربر {user_id}"

    # 5. ارسال پیام تایید با دکمه‌ها
    keyboard = InlineKeyboardMarkup(
        [
            [
                # دیتا را به فرمت CONFIRM_BAN|ID می‌فرستیم
                InlineKeyboardButton("✅ بله", callback_data=f"CONFIRM_BAN|{user_id}"),
                InlineKeyboardButton("✖️ لغو", callback_data=f"CANCEL_BAN|{user_id}"),
            ],
        ],
    )

    return await message.reply(
        text=f"آیا دسترسی کاربر **{user_name}** با آیدی `{user_id}` به ربات مسدود شود؟",
        reply_markup=keyboard,
        quote=True,
    )


@Client.on_callback_query(filters.regex(r"^(CONFIRM_BAN|CANCEL_BAN)\|(\d+)$"))
async def ban_callback_handler(client: Client, callback_query: CallbackQuery):
    """هندلر کلیک‌های تأیید و لغو برای دستور /ban"""

    # --- کد بررسی ادمین حذف شد ---

    # 2. جداسازی اکشن و آیدی کاربر هدف
    action, user_id_str = callback_query.data.split("|")
    user_id = int(user_id_str)
    message = callback_query.message  # پیام اصلی که دکمه‌ها زیر آن هستند

    if action == "CANCEL_BAN":
        # 3. عملیات لغو
        await message.delete()  # پیام را پاک می‌کند
        await callback_query.answer("✖️ لغو شود", show_alert=False)  # پیام answer را نمایش می‌دهد
        return

    elif action == "CONFIRM_BAN":
        # 4. عملیات تایید (بن کردن)
        await database.ban_user(user_id)
        
        # ارسال پیام به کاربر بن‌شده
        try:
            await client.send_message(
                chat_id=user_id,
                text="⛔ دسترسی شما به ربات مسدود شد.",
            )
        except Exception:
            # نادیده گرفتن خطا اگر کاربر ربات را بلاک کرده باشد
            pass

        # دریافت نام کاربر برای پیام نهایی
        try:
            user = await client.get_users(user_id)
            user_name = user.first_name if user.first_name else f"کاربر {user_id}"
        except Exception:
            user_name = f"کاربر {user_id}"

        # ویرایش پیام اصلی برای نمایش نتیجه نهایی
        await message.edit_text(
            f"✅ کاربر **{user_name}** با آیدی `{user_id}` با موفقیت بن شد.",
            reply_markup=None,  # دکمه‌ها حذف می‌شوند
        )

        await callback_query.answer("✅ باموفقیت انجام شد.", show_alert=False)
        return


