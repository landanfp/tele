# bot/plugins/moderation/ban_list.py

import logging
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter


logger = logging.getLogger(__name__)
database = MongoDB()


@Client.on_message(
    filters.private & filters.command("ban_list"),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def ban_list_handler(client: Client, message: Message) -> Message | None:
    """
    نمایش لیست کاربران بن شده.

    **Usage:**
        /ban_list
    """

    logger.info(f"ban_list command triggered by user {message.from_user.id}")

    # بررسی ادمین بودن (برای اجرای دستور)
    if message.from_user.id not in config.ROOT_ADMINS_ID:
        logger.warning(f"Unauthorized access to ban_list by user {message.from_user.id}")
        return await message.reply(
            text="❌ **شما ادمین نیستید!**",
            quote=True,
        )

    try:
        # این تابع را در مرحله قبل به فایل moderation.py اضافه کردیم
        banned_users = await database.get_banned_users()
        logger.info(f"Found {len(banned_users)} banned users from DB")
    except Exception as e:
        logger.error(f"Error fetching banned users: {e}")
        return await message.reply(
            text="❌ **خطا در خواندن دیتابیس!**\n(مطمئن شوید فایل moderation.py را آپدیت کرده‌اید)",
            quote=True,
        )

    if not banned_users:
        logger.info("No banned users found - sending empty message")
        return await message.reply(
            text="✅ کاربر بن شده ای وجود ندارد!",
            quote=True,
        )

    msg = await message.reply("⏳ **در حال دریافت اطلاعات کاربران...**", quote=True)
    
    ban_list_text = "**🚫 لیست کاربران بن شده:**\n\n"
    
    for idx, user_info in enumerate(banned_users, 1):
        user_id = user_info.get('id')
        if not user_id:
            continue

        try:
            # تلاش برای دریافت اطلاعات تازه کاربر از تلگرام
            user = await client.get_users(user_id)
            # ساخت لینک قابل کلیک با نام کاربر
            user_link = user.mention(style="md")
        except Exception:
            # اگر کاربر پیدا نشد (مثلاً دیلیت اکانت)
            user_link = f"[کاربر {user_id}](tg://user?id={user_id})"

        # فرمت خروجی: شماره. نام (لینک دار) | آیدی عددی
        ban_list_text += f"{idx}. {user_link} | `{user_id}`\n"

    try:
        await msg.edit_text(ban_list_text)
    except Exception as e:
        logger.error(f"Error sending ban list: {e}")
        # اگر متن خیلی طولانی باشد ممکن است ارور بدهد، پس در فایل متنی می‌فرستیم
        if "MESSAGE_TOO_LONG" in str(e):
            with open("ban_list.txt", "w", encoding="utf-8") as f:
                f.write(ban_list_text.replace("*", "").replace("`", ""))
            await message.reply_document("ban_list.txt", caption="📜 لیست کاربران بن شده (متن طولانی بود)")



