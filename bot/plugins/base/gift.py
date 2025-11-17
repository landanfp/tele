# bot/plugins/base/gift.py file :
import asyncio
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from bot.config import config, DAILY_LINK_LIMITS
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

database = MongoDB()
db = database
LOG_CHANNEL = config.BACKUP_CHANNEL
GIFT_PLAN_NAME = "gift_7days"
GIFT_PLAN_DURATION = 7

async def is_gift_plan_used(user_id: int) -> bool:
    """چک می‌کند آیا کاربر قبلاً از پلن هدیه استفاده کرده است."""
    user = await db.db["Users"].find_one({'_id': user_id, 'plan': GIFT_PLAN_NAME})
    return True if user and user.get('plan_expiry') is not None else False

@Client.on_message(filters.command("gift") & filters.private & PyroFilters.subscription())
@RateLimiter.hybrid_limiter(func_count=1)
async def activate_gift_plan(client: Client, message: Message) -> None:
    """فعال‌سازی پلن هدیه 7 روزه برای کاربران با پلن رایگان."""
    user_id = message.from_user.id
    user_info = await db.db["Users"].find_one({'_id': user_id})

    if user_info:
        current_plan = user_info.get('plan', 'free')
        # رد کردن کاربران با پلن‌های غیررایگان (پرمیوم)
        if current_plan != 'free':
            await message.reply_text("⚠️ شما به دلیل داشتن پلن ویژه قادر به دریافت این هدیه نیستید.")
            return

    if await is_gift_plan_used(user_id):
        await message.reply_text("⚠️ شما قبلاً از این هدیه استفاده کرده‌اید.")
        return

    expiry_date = datetime.date.today() + datetime.timedelta(days=GIFT_PLAN_DURATION)
    await db.set_user_plan(user_id, GIFT_PLAN_NAME, expiry_date.isoformat())

    try:
        daily_limit = DAILY_LINK_LIMITS.get(GIFT_PLAN_NAME, 5)  # فرض بر 5 کلیک روزانه
        await message.reply_text(
            f"🎁 پلن هدیه 7 روزه با موفقیت برای شما فعال شد!\n\n"
            f"⏳ این پلن تا تاریخ {expiry_date.strftime('%Y/%m/%d')} معتبر است.\n"
            f"💾 محدودیت کلیک روزانه این پلن: {daily_limit} کلیک\n\n"
            f"برای بررسی وضعیت پلن خود از دستور /myplan استفاده کنید."
        )
        user_mention = f"[{message.from_user.first_name}](tg://user?id={user_id})"
        await client.send_message(
            LOG_CHANNEL,
            f"🎉 پلن هدیه فعال شد!\n\n"
            f"👤 کاربر: {user_mention}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"نوع پلن: {GIFT_PLAN_NAME}\n"
            f"🗓️ تاریخ انقضا: {expiry_date.strftime('%Y/%m/%d')}"
        )
    except FloodWait as e:
        print(f"Sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        await message.reply_text("⚠️ به دلیل شلوغی سرور، فعال سازی با تاخیر انجام شد. لطفاً مجدداً بررسی کنید.")
    except Exception as e:
        await message.reply_text(f"❌ خطایی در فعال سازی پلن هدیه رخ داد: {e}")


HelpCmd.set_help(
    command="gift",
    description="فعال‌سازی پلن هدیه 7 روزه (فقط برای کاربران رایگان).",
    allow_global=True,
    allow_non_admin=True,
)
