import uuid
import logging
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message
from bot.config import config, DAILY_LINK_LIMITS
from bot.database import MongoDB
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd
from bot.utilities.helpers.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
database = MongoDB()
db = database
VIP_PLAN_NAME = "vip_15days"  # 10 لینک روزانه، 15 روز
LOG_CHANNEL = config.BACKUP_CHANNEL  # Assuming backup as log

async def generate_vip_code():
    """تولید کد VIP منحصر به فرد."""
    return str(uuid.uuid4()).replace('-', '')[:8].upper()  # کد 8 حرفی

async def save_vip_code(code: str):
    """ذخیره کد VIP در دیتابیس."""
    collection = db.db["VIPCodes"]
    result = await collection.update_one(
        {"code": code},
        {"$set": {"code": code, "used": False, "created_at": datetime.datetime.now().isoformat()}},
        upsert=True
    )
    return result.acknowledged

async def redeem_vip_code(user_id: int, code: str):
    """استفاده از کد VIP و اعمال پلن."""
    collection = db.db["VIPCodes"]
    vip_doc = await collection.find_one({"code": code, "used": False})
    if not vip_doc:
        return False, "کد نامعتبر یا استفاده‌شده است."

    # اعمال پلن VIP
    days = 15
    expiry_date = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    await db.set_user_plan(user_id, VIP_PLAN_NAME, expiry_date)
    
    # علامت‌گذاری کد به عنوان استفاده‌شده
    await collection.update_one(
        {"code": code},
        {"$set": {"used": True, "used_by": user_id, "used_at": datetime.datetime.now().isoformat()}}
    )
    
    return True, f"✅ کد VIP با موفقیت اعمال شد!\n\nپلن {VIP_PLAN_NAME.replace('_', ' ')} (10 لینک روزانه، {days} روز) فعال شد.\nبررسی کنید: /myplan"

@Client.on_message(filters.private & filters.command("vip_code"))
@RateLimiter.hybrid_limiter(func_count=1)
async def vip_code_handler(client: Client, message: Message):
    """تولید یا فعال‌سازی کد VIP."""
    user_id = message.from_user.id
    if len(message.command) == 1:  # بدون آرگومان: تولید کد (فقط ادمین)
        if user_id not in config.ROOT_ADMINS_ID:
            await message.reply("❌ فقط ادمین‌ها می‌تونن کد VIP تولید کنن.")
            return
        code = await generate_vip_code()
        saved = await save_vip_code(code)
        if saved:
            await message.reply(f"✅ کد VIP تولید شد: `{code}`\n\nاین کد را به کاربر بدهید تا با `/vip_code {code}` فعال کند.")
            try:
                await client.send_message(LOG_CHANNEL, f"🆔 کد VIP جدید تولید شد: `{code}`\nتوسط ادمین: {user_id}")
            except Exception as e:
                logger.warning(f"Failed to log VIP code: {e}")
        else:
            await message.reply("❌ خطا در ذخیره کد VIP. دوباره امتحان کنید.")
    else:  # با آرگومان: redeem کد
        code = message.command[1].upper()
        success, msg = await redeem_vip_code(user_id, code)
        await message.reply(msg, quote=True)
        if success:
            try:
                await client.send_message(LOG_CHANNEL, f"🆔 کد VIP `{code}` توسط کاربر {user_id} استفاده شد.\nپلن: {VIP_PLAN_NAME}")
            except Exception as e:
                logger.warning(f"Failed to log VIP redemption: {e}")

HelpCmd.set_help(
    command="vip_code",
    description="تولید یا فعال‌سازی کد VIP برای پلن 10 لینک روزانه (15 روز). ادمین: `/vip_code` | کاربر: `/vip_code [کد]`",
    allow_global=True,
    allow_non_admin=True,
)
