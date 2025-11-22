# bot/plugins/base/gift.py file :
import asyncio
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
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

# Simple state manager using a dictionary (in production, consider using Redis or DB for persistence)
user_states = {}  # {user_id: {'step': str, 'phone': str}}

async def is_gift_plan_used(user_id: int) -> bool:
    """چک می‌کند آیا کاربر قبلاً از پلن هدیه استفاده کرده است."""
    print(f"DEBUG: Checking gift plan used for user {user_id}")
    user = await db.db["Users"].find_one({'_id': user_id, 'plan': GIFT_PLAN_NAME})
    used = True if user and user.get('plan_expiry') is not None else False
    print(f"DEBUG: Gift plan used? {used}")
    return used

def get_user_state(user_id: int):
    """دریافت state کاربر."""
    state = user_states.get(user_id, {})
    print(f"DEBUG: Current state for user {user_id}: {state}")
    return state

def set_user_state(user_id: int, state: dict):
    """تنظیم state کاربر."""
    user_states[user_id] = state
    print(f"DEBUG: Set state for user {user_id}: {state}")

def clear_user_state(user_id: int):
    """پاک کردن state کاربر."""
    user_states.pop(user_id, None)
    print(f"DEBUG: Cleared state for user {user_id}")

@Client.on_message(filters.command("gift") & filters.private & PyroFilters.subscription())
@RateLimiter.hybrid_limiter(func_count=1)
async def activate_gift_plan(client: Client, message: Message) -> None:
    """فعال‌سازی پلن هدیه 7 روزه برای کاربران با پلن رایگان (با تأیید اطلاعات)."""
    print(f"DEBUG: Gift command triggered for user {message.from_user.id}")
    user_id = message.from_user.id
    try:
        user_info = await db.db["Users"].find_one({'_id': user_id})
        print(f"DEBUG: User info fetched: {user_info}")
    except Exception as e:
        print(f"DEBUG: Error fetching user info: {e}")
        await message.reply_text("❌ خطا در خواندن اطلاعات کاربر.")
        return

    if user_info:
        current_plan = user_info.get('plan', 'free')
        print(f"DEBUG: Current plan: {current_plan}")
        # رد کردن کاربران با پلن‌های غیررایگان (پرمیوم)
        if current_plan != 'free':
            await message.reply_text("⚠️ شما به دلیل داشتن پلن ویژه قادر به دریافت این هدیه نیستید.")
            return

    if await is_gift_plan_used(user_id):
        await message.reply_text("⚠️ شما قبلاً از این هدیه استفاده کرده‌اید.")
        return

    # تنظیم state اولیه
    set_user_state(user_id, {'step': 'waiting_phone'})
    
    # کیبورد با دکمه Share Contact
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True  # فقط یک بار نمایش داده بشه
    )
    
    await message.reply_text(
        "🎁 برای فعال‌سازی پلن هدیه، ابتدا اطلاعات خود را تأیید کنید.\n\n"
        "📱 لطفاً دکمه 'Share Contact' را بزنید و شماره تلفن واقعی خود را به اشتراک بگذارید.",
        reply_markup=markup
    )
    print(f"DEBUG: Waiting for phone from user {user_id}")

@Client.on_message(filters.contact & filters.private & PyroFilters.subscription())
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_phone_share(client: Client, message: Message) -> None:
    """دریافت شماره تلفن و فعال‌سازی مستقیم پلن."""
    print(f"DEBUG: Contact message received from user {message.from_user.id}")
    user_id = message.from_user.id
    state = get_user_state(user_id)

    if state.get('step') != 'waiting_phone':
        print(f"DEBUG: Ignoring contact - wrong state: {state.get('step')}")
        return  # اگر state مناسب نیست، نادیده بگیر

    if not hasattr(message, 'contact') or not message.contact:
        print("DEBUG: No contact in message!")
        return

    phone_number = message.contact.phone_number
    print(f"DEBUG: Phone received: {phone_number}")
    
    # ارسال استیکر loading
    print(f"DEBUG: About to send loading sticker for user {user_id}")
    loading_sticker_message = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
    print(f"DEBUG: Loading sticker sent for user {user_id}")
    
    # صبر 4 ثانیه
    print(f"DEBUG: Starting sleep for user {user_id}")
    await asyncio.sleep(4)
    print(f"DEBUG: Sleep finished for user {user_id}")
    
    # حذف استیکر loading
    print(f"DEBUG: About to delete sticker for user {user_id}")
    try:
        await loading_sticker_message.delete()
        print(f"DEBUG: Sticker deleted for user {user_id}")
    except Exception as delete_e:
        print(f"DEBUG: Error deleting sticker: {delete_e}")
    
    # پاک کردن state و کیبورد
    clear_user_state(user_id)
    remove_markup = ReplyKeyboardMarkup([], resize_keyboard=True)
    
    # فعال‌سازی پلن مستقیم (بدون درخواست نام)
    expiry_date = datetime.date.today() + datetime.timedelta(days=GIFT_PLAN_DURATION)
    print(f"DEBUG: About to set plan for user {user_id}")
    try:
        await db.set_user_plan(user_id, GIFT_PLAN_NAME, expiry_date.isoformat())
        print(f"DEBUG: Plan set successfully for user {user_id}")
    except Exception as e:
        print(f"DEBUG: Error setting plan: {e}")
        try:
            await message.reply_text(f"❌ خطا در فعال‌سازی پلن: {e}", reply_markup=remove_markup)
            print(f"DEBUG: Error message sent for user {user_id}")
        except Exception as reply_e:
            print(f"DEBUG: Error sending error message: {reply_e}")
        return

    try:
        daily_limit = DAILY_LINK_LIMITS.get(GIFT_PLAN_NAME, 5)  # فرض بر 5 کلیک روزانه
        user_name = message.from_user.first_name or "نامشخص"  # استفاده از first_name
        
        print(f"DEBUG: About to send success message for user {user_id}")
        await message.reply_text(
            f"🎁 پلن هدیه 7 روزه با موفقیت برای شما فعال شد!\n\n"
            f"👤 نام: {user_name}\n"
            f"📱 شماره: {phone_number}\n"
            f"⏳ این پلن تا تاریخ {expiry_date.strftime('%Y/%m/%d')} معتبر است.\n"
            f"💾 محدودیت کلیک روزانه این پلن: {daily_limit} کلیک\n\n"
            f"برای بررسی وضعیت پلن خود از دستور /myplan استفاده کنید.",
            reply_markup=remove_markup
        )
        print(f"DEBUG: Success message sent for user {user_id}")

        # لاگ با فرمت جدید
        print(f"DEBUG: About to send log for user {user_id}")
        await client.send_message(
            LOG_CHANNEL,
            f"🎉 پلن هدیه فعال شد!\n\n"
            f"👤 نام کاربر: {user_name}\n"
            f"🆔 آیدی عددی: {user_id}\n"
            f"📲 شماره کاربر: {phone_number}\n"
            f"🪅 نوع پلن: {GIFT_PLAN_NAME}\n"
            f"🗓️ تاریخ انقضا: {expiry_date.strftime('%Y/%m/%d')}"
        )
        print(f"DEBUG: Log sent for user {user_id}")

    except FloodWait as e:
        print(f"DEBUG: FloodWait caught: {e.value}s")
        await asyncio.sleep(e.value)
        try:
            await message.reply_text("⚠️ به دلیل شلوغی سرور، فعال سازی با تاخیر انجام شد. لطفاً مجدداً بررسی کنید.", reply_markup=remove_markup)
            print(f"DEBUG: Flood message sent for user {user_id}")
        except Exception as flood_reply_e:
            print(f"DEBUG: Error sending flood message: {flood_reply_e}")
    except Exception as e:
        print(f"DEBUG: Error in final steps: {e}")
        try:
            await message.reply_text(f"❌ خطایی در فعال سازی پلن هدیه رخ داد: {e}", reply_markup=remove_markup)
            print(f"DEBUG: Final error message sent for user {user_id}")
        except Exception as final_reply_e:
            print(f"DEBUG: Error sending final error message: {final_reply_e}")


HelpCmd.set_help(
    command="gift",
    description="فعال‌سازی پلن هدیه 7 روزه (فقط برای کاربران رایگان، با تأیید شماره).",
    allow_global=True,
    allow_non_admin=True,
)
