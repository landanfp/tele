# bot/plugins/moderation/ban_list.py

import logging
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

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
        banned_users = await database.get_banned_users()
        logger.info(f"Found {len(banned_users)} banned users from DB")
    except Exception as e:
        logger.error(f"Error fetching banned users: {e}")
        return await message.reply(
            text="❌ **خطا در خواندن دیتابیس!**",
            quote=True,
        )

    if not banned_users:
        logger.info("No banned users found - sending empty message")
        return await message.reply(
            text="✅ کاربر بن شده ای وجود ندارد!",
            quote=True,
        )

    ban_list_text = "**لیست کاربران بن شده:**\n\n"
    for idx, user_info in enumerate(banned_users, 1):
        user_id = user_info.get('id')
        if not user_id:
            logger.warning(f"Invalid user_info in banned_users: {user_info}")
            continue

        logger.info(f"Processing banned user {idx}: ID {user_id}")
        try:
            user = await client.get_users(user_id)
            user_name = (user.first_name or "") + (" " + user.last_name if user.last_name else "")
            if not user_name.strip():
                user_name = f"کاربر {user_id}"
            logger.info(f"Successfully fetched user {user_id}: {user_name}")
        except Exception as e:
            logger.warning(f"Failed to get user {user_id}: {e}")
            user_name = f"کاربر {user_id} (نامشخص)"

        ban_list_text += f"`{user_name}` | `{user_id}`\n"

    if len(ban_list_text.strip()) <= len("**لیست کاربران بن شده:**\n\n"):  # اگر فقط عنوان باشه
        logger.warning("Ban list text is empty after processing")
        return await message.reply(
            text="✅ هیچ کاربر بن‌شده‌ای با جزئیات معتبر یافت نشد!",
            quote=True,
        )

    logger.info(f"Sending ban list with {len(banned_users)} users")
    return await message.reply(
        text=ban_list_text,
        quote=True,
    )


HelpCmd.set_help(
    command="ban_list",
    description=ban_list_handler.__doc__,
    allow_global=False,
    allow_non_admin=False,
)
