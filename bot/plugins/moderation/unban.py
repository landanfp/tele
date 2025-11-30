# bot/plugins/moderation/unban.py file :
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


database = MongoDB()


@Client.on_message(
    filters.private & filters.command("unban"),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def unban_user(client: Client, message: ConvoMessage) -> Message | None:
    """کاربر بن‌شده را از حالت بن خارج می‌کند."""

    # 1. بررسی ادمین بودن (برای اجرای دستور)
    if message.from_user.id not in config.ROOT_ADMINS_ID:
        return await message.reply(
            text="❌ **شما ادمین نیستید!**",
            quote=True,
        )

    # 2. اعتبارسنجی ورودی
    if len(message.command) != 2:
        return await message.reply(
            text="⚠️ **دستور اشتباه!**\n\n**روش استفاده:** `/unban {user_id}`",
            quote=True,
        )
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply(
            text="⚠️ **آیدی کاربر باید یک عدد باشد.**",
            quote=True,
        )

    # 3. بررسی بن نبودن
    if not await database.is_user_banned(user_id):
        return await message.reply(
            text=f"⚠️ کاربر با آیدی `{user_id}` قبلاً بن نشده یا در دیتابیس نیست.",
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
                # دیتا را به فرمت CONFIRM_UNBAN|ID می‌فرستیم
                InlineKeyboardButton("✅ بله", callback_data=f"CONFIRM_UNBAN|{user_id}"),
                InlineKeyboardButton("✖️ لغو", callback_data=f"CANCEL_UNBAN|{user_id}"),
            ],
        ],
    )

    return await message.reply(
        text=f"آیا دسترسی کاربر **{user_name}** با آیدی `{user_id}` به ربات باز شود؟",
        reply_markup=keyboard,
        quote=True,
    )


@Client.on_callback_query(filters.regex(r"^(CONFIRM_UNBAN|CANCEL_UNBAN)\|(\d+)$"))
async def unban_callback_handler(client: Client, callback_query: CallbackQuery):
    """هندلر کلیک‌های تأیید و لغو برای دستور /unban"""

    # --- کد بررسی ادمین حذف شد ---

    # 2. جداسازی اکشن و آیدی کاربر هدف
    action, user_id_str = callback_query.data.split("|")
    user_id = int(user_id_str)
    message = callback_query.message  # پیام اصلی که دکمه‌ها زیر آن هستند

    if action == "CANCEL_UNBAN":
        # 3. عملیات لغو
        await message.delete()
        await callback_query.answer("✖️ لغو شود", show_alert=False)
        return

    elif action == "CONFIRM_UNBAN":
        # 4. عملیات تایید (آنبن کردن)
        unban_result = await database.unban_user(user_id)

        # دریافت نام کاربر برای پیام نهایی
        try:
            user = await client.get_users(user_id)
            user_name = user.first_name if user.first_name else f"کاربر {user_id}"
        except Exception:
            user_name = f"کاربر {user_id}"

        if unban_result:
            # ارسال پیام به کاربر آنبن شده
            try:
                await client.send_message(
                    chat_id=user_id,
                    text="✅ مسدودیت شما رفع شد.",
                )
            except Exception:
                pass
            
            # ویرایش پیام اصلی برای نمایش نتیجه نهایی
            await message.edit_text(
                f"✅ کاربر **{user_name}** با آیدی `{user_id}` با موفقیت از بن خارج شد.",
                reply_markup=None,
            )
        else:
            await message.edit_text(
                f"⚠️ آنبن کاربر **{user_name}** با آیدی `{user_id}` موفق نبود. شاید قبلا بن نشده بود.",
                reply_markup=None,
            )

        await callback_query.answer("✅ باموفقیت انجام شد.", show_alert=False)
        return


HelpCmd.set_help(
    command="unban",
    description=unban_user.__doc__,
    allow_global=False,
    allow_non_admin=False,
)
