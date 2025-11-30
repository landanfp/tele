from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.utilities.helpers import RateLimiter



@Client.on_message(
    filters.private & filters.command("privacy"),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def privacy(_: Client, message: Message) -> Message:
    """Display bot privacy"""

    return await message.reply(
        text="Created by: @zawsq\nSource Code: [Teleshare](https://github.com/zawsq/Teleshare)",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="PRIVACY POLICY",
                        web_app=WebAppInfo(url="https://github.com/zawsq/Teleshare/blob/main/PRIVACY.md"),
                    ),
                ],
            ],
        ),
    )

