from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

database = MongoDB()


@Client.on_message(
    filters.private & PyroFilters.admin() & filters.command("ban_list"),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def ban_list_handler(client: Client, message: Message) -> Message | None:
    """
    نمایش لیست کاربران بن شده.

    **Usage:**
        /ban_list
    """

    # بررسی ادمین بودن (برای اجرای دستور)
    if message.from_user.id not in config.ROOT_ADMINS_ID:
        return await message.reply(
            text="❌ **شما ادمین نیستید!**",
            quote=True,
        )

    banned_users = await database.get_banned_users()
    if not banned_users:
        return await message.reply(
            text="✅ کاربر بن شده ای وجود ندارد!",
            quote=True,
        )

    ban_list_text = "**لیست کاربران بن شده:**\n\n"
    for user_info in banned_users:
        try:
            user = await client.get_users(user_info["_id"])  # _id رو استفاده کردم چون در get_banned_users، فیلد _id هست
            user_name = user.first_name if user.first_name else f"کاربر {user_info['_id']}"
        except Exception:
            user_name = f"کاربر {user_info['_id']}"  # اگر get_users fail شد

        ban_list_text += f"`{user_name}` | `{user_info['_id']}`\n"

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
