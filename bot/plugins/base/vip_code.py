import uuid
import logging
import datetime
import random
import string
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
VIP_PLAN_DURATION = 15  # روز
LOG_CHANNEL = config.BACKUP_CHANNEL  # Assuming backup as log

# فرض بر این که admin_filter از pyrofilters تعریف شده یا مشابه config.ROOT_ADMINS_ID
admin_filter = PyroFilters.admin_filter  # یا تعریف کن: filters.user(config.ROOT_ADMINS_ID)

async def generate_vip_code():
    """تولید کد VIP منحصر به فرد."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def add_vip_code_to_db(code: str):
    """ذخیره کد VIP در دیتابیس."""
    collection = db.db["VIPCodes"]
    result = await collection.update_one(
        {"code": code},
        {"$set": {"code": code, "used": False, "created_at": datetime.datetime.now().isoformat()}},
        upsert=True
    )
    return result.acknowledged

async def is_vip_code_valid(code: str):
    """بررسی اعتبار کد VIP."""
    collection = db.db["VIPCodes"]
    vip_doc = await collection.find_one({"code": code, "used": False})
    return vip_doc is not None

async def mark_vip_code_as_used(code: str, user_id: int):
    """علامت‌گذاری کد VIP به عنوان استفاده‌شده."""
    collection = db.db["VIPCodes"]
    result = await collection.update_one(
        {"code": code, "used": False},
        {"$set": {"used": True, "used_by": user_id, "used_at": datetime.datetime.now().isoformat()}}
    )
    return result.modified_count > 0

@Client.on_message(filters.private & admin_filter & filters.command("create_vip"))
@RateLimiter.hybrid_limiter(func_count=1)
async def create_vip_code(client: Client, message: Message):
    """تولید کد VIP برای ادمین."""
    if message.from_user.id not in config.ROOT_ADMINS_ID:
        logger.warning(f"Unauthorized access to create_vip by user {message.from_user.id}")
        return await message.reply(
            text="❌ **شما ادمین نیستید!**",
            quote=True,
        )
    # Update ADMIN list before processing (اگر تابعی داری، اضافه کن)
    # update_admin_list()  # کامنت‌شده اگر وجود نداره

    code = await generate_vip_code()
    saved = await add_vip_code_to_db(code)
    if saved:
        await message.reply(f"کد VIP با موفقیت ساخته شد و در دیتابیس ذخیره شد:\n\n`{code}`\n\nاین کد فقط یک‌بار قابل استفاده است.")
        try:
            await client.send_message(LOG_CHANNEL, f"🆔 کد VIP جدید تولید شد: `{code}`\nتوسط ادمین: {message.from_user.id}")
        except Exception as e:
            logger.warning(f"Failed to log VIP code: {e}")
    else:
        await message.reply("❌ خطا در ذخیره کد VIP. دوباره امتحان کنید.")

@Client.on_message(filters.private & filters.command("vip"))
@RateLimiter.hybrid_limiter(func_count=1)
async def redeem_vip_code(client: Client, message: Message):
    """فعال‌سازی کد VIP برای کاربر."""
    user_id = message.from_user.id
    user_info = await db.col.find_one({'id': user_id})  # فرض بر col برای users

    if not user_info:
        await message.reply("ابتدا /start را ارسال کنید.")
        return

    current_plan = user_info.get('plan', 'free')
    if current_plan in ["silver", "gold", "diamond"]:  # تطبیق با کد جدید، اگر پلن‌های دیگه داری تنظیم کن
        await message.reply("کاربرانی که پلن فعال دارند نمی‌توانند از کد VIP استفاده کنند.")
        return

    if len(message.command) < 2:
        await message.reply("لطفاً کد VIP را به صورت زیر وارد کنید:\n`/vip CODE`")
        return

    code = message.command[1].strip().upper()
    if len(code) != 8 or not code.isalnum():
        await message.reply("❌ کد VIP باید ۸ کاراکتر معتبر (حروف و اعداد) باشد.")
        return

    if await is_vip_code_valid(code):
        if await mark_vip_code_as_used(code, user_id):
            expiry_date = datetime.date.today() + datetime.timedelta(days=VIP_PLAN_DURATION)
            await db.set_user_plan(user_id, VIP_PLAN_NAME, expiry_date.isoformat())
            await message.reply(f"✅ پلن {VIP_PLAN_NAME.replace('_', ' ')} با موفقیت برای شما فعال شد به مدت {VIP_PLAN_DURATION} روز (10 لینک روزانه).")
            try:
                user = message.from_user
                user_info_log = f"{user.first_name} (@{user.username or 'no_username'})" if user.username else user.first_name
                await client.send_message(LOG_CHANNEL, f"🆔 کد VIP `{code}` توسط {user_info_log} (ID: {user_id}) استفاده شد.\nپلن: {VIP_PLAN_NAME}")
            except Exception as e:
                logger.warning(f"Failed to log VIP redemption: {e}")
        else:
            await message.reply("کد وارد شده قبلاً استفاده شده است.")
    else:
        await message.reply("کد وارد شده نامعتبر است.")

# HelpCmd برای هر دو
HelpCmd.set_help(
    command="create_vip",
    description="تولید کد VIP برای ادمین.",
    allow_global=True,
    allow_non_admin=False,
)
HelpCmd.set_help(
    command="vip",
    description="فعال‌سازی کد VIP برای کاربر: `/vip [کد]`",
    allow_global=True,
    allow_non_admin=True,
)
