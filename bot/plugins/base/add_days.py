import logging
import asyncio
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.config import config
from bot.database import MongoDB
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd
from bot.utilities.helpers.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
database = MongoDB()
db = database
LOG_CHANNEL = config.BACKUP_CHANNEL  # Assuming backup as log

# حالت‌های مختلف برای مدیریت تعاملات
ADMIN_ADDING_DAYS = {}

@Client.on_message(filters.private & PyroFilters.admin() & filters.command("add_day"))
@RateLimiter.hybrid_limiter(func_count=1)
async def add_day_command(client: Client, message: Message):
    """
    دریافت تعداد روز برای اضافه کردن به پلن کاربران پرمیوم از ادمین.
    """
    user_id = message.from_user.id
    ADMIN_ADDING_DAYS[user_id] = "waiting_for_days"
    await message.reply_text("حالا تعداد روزی که می‌خواهید اضافه شود وارد کنید. (از 1 تا 30)")

@Client.on_message(
    filters.private 
    & PyroFilters.admin() 
    & filters.text 
    & ~filters.command(["start", "myplan", "addpremium", "delete_premium"])  # جلوگیری از تداخل با کامندها
)
@RateLimiter.hybrid_limiter(func_count=1)
async def get_days_to_add(client: Client, message: Message):
    """
    دریافت تعداد روز از ادمین و نمایش پیام تایید.
    """
    user_id = message.from_user.id
    if user_id in ADMIN_ADDING_DAYS and ADMIN_ADDING_DAYS[user_id] == "waiting_for_days":
        try:
            days_to_add = int(message.text)
            if 1 <= days_to_add <= 30:
                ADMIN_ADDING_DAYS[user_id] = {"status": "confirming", "days": days_to_add}
                markup = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("✅ بله", callback_data=f"adddays_yes_{days_to_add}"),
                            InlineKeyboardButton("❌ لغو", callback_data="adddays_no")
                        ]
                    ]
                )
                await message.reply_text(
                    f"مطمئن هستید می‌خواهید {days_to_add} روز به پلن کاربران پرمیوم اضافه شود؟",
                    reply_markup=markup,
                    quote=True
                )
            else:
                await message.reply_text("تعداد روز وارد شده نامعتبر است. لطفاً عددی بین 1 تا 30 وارد کنید.")
                ADMIN_ADDING_DAYS.pop(user_id, None)
        except ValueError:
            await message.reply_text("مقدار وارد شده عدد نیست. لطفاً یک عدد وارد کنید.")
            ADMIN_ADDING_DAYS.pop(user_id, None)
    else:
        return message.continue_propagation()

@Client.on_callback_query(filters.regex(r"^adddays_yes_(\d+)$"))
async def confirm_add_days(client: Client, callback_query: CallbackQuery):
    """
    دریافت تایید ادمین برای اضافه کردن روزها به پلن کاربران پرمیوم و اطلاع رسانی در کانال لاگ.
    """
    user_id = callback_query.from_user.id
    if user_id in ADMIN_ADDING_DAYS and ADMIN_ADDING_DAYS[user_id].get("status") == "confirming":
        days_to_add = ADMIN_ADDING_DAYS[user_id]["days"]
        await callback_query.answer("با موفقیت انجام شد.", show_alert=False)
        msg = await callback_query.message.edit_text("در حال بررسی و به‌روزرسانی...")
        await asyncio.sleep(2)  # اضافه کردن تأخیر 2 ثانیه‌ای

        updated_count = 0
        successful_users = []
        premium_plans = ["daily_5", "daily_10", "daily_20", "weekly_5", "weekly_10", "weekly_15", "weekly_20", "monthly_5", "monthly_10", "monthly_15", "monthly_20"]  # لیست پلن‌های پرمیوم
        async for user in db.db["Users"].find({"plan": {"$in": premium_plans}}):
            if user.get('plan_expiry'):
                try:
                    expiry_date = datetime.datetime.strptime(user['plan_expiry'], "%Y-%m-%d").date()
                    new_expiry_date = expiry_date + datetime.timedelta(days=days_to_add)
                    await db.db["Users"].update_one(
                        {"_id": user["_id"]},
                        {"$set": {"plan_expiry": new_expiry_date.isoformat()}}
                    )
                    updated_count += 1
                    successful_users.append(user["_id"])
                except ValueError:
                    # اگر فرمت تاریخ اشتباه بود، از این کاربر رد می‌شویم
                    pass
            else:
                # برای کاربرانی که پلن پرمیوم دارند ولی تاریخ انقضا ندارند، یک تاریخ انقضا تعیین می‌کنیم
                new_expiry_date = datetime.date.today() + datetime.timedelta(days=30 + days_to_add)  # مثلا 30 روز + روزهای اضافه شده
                await db.db["Users"].update_one(
                    {"_id": user["_id"]},
                    {"$set": {"plan_expiry": new_expiry_date.isoformat()}}
                )
                updated_count += 1
                successful_users.append(user["_id"])

        await msg.edit_text(f"با موفقیت {days_to_add} روز به پلن {updated_count} کاربر پرمیوم اضافه شد.")
        ADMIN_ADDING_DAYS.pop(user_id, None)

        # ارسال پیام به کاربران به‌روزرسانی شده
        notification_message = f"{days_to_add} روز به پلن شما اضافه شد.\nهم اکنون بررسی کنید 👈 /myplan"
        for user_id_to_notify in successful_users:
            try:
                await client.send_message(user_id_to_notify, notification_message)
                await asyncio.sleep(0.1)  # برای جلوگیری از محدودیت‌های اسپم
            except Exception as e:
                logger.warning(f"Failed to send notification to user {user_id_to_notify}: {e}")

        # ارسال پیام به کانال لاگ
        if LOG_CHANNEL:
            log_message = f"🗓 {days_to_add} روز به پلن کاربران ویژه اضافه شد.\nتعداد کاربران : {updated_count}"
            try:
                await client.send_message(LOG_CHANNEL, log_message)
            except Exception as e:
                logger.warning(f"Failed to send log message to channel {LOG_CHANNEL}: {e}")
        else:
            logger.warning("LOG_CHANNEL is not defined in config.")

    else:
        await callback_query.answer("این درخواست منقضی شده است.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^adddays_no$"))
async def cancel_add_days(client: Client, callback_query: CallbackQuery):
    """
    لغو عملیات اضافه کردن روزها توسط ادمین.
    """
    user_id = callback_query.from_user.id
    if user_id in ADMIN_ADDING_DAYS and ADMIN_ADDING_DAYS[user_id].get("status") == "confirming":
        await callback_query.answer("لغو شد. 👍", show_alert=False)
        await callback_query.message.delete()
        ADMIN_ADDING_DAYS.pop(user_id, None)
    else:
        await callback_query.answer("این درخواست منقضی شده است.", show_alert=True)

HelpCmd.set_help(
    command="add_day",
    description="اضافه کردن تعداد روز به پلن‌های کاربران پرمیوم.",
    allow_global=False,
    allow_non_admin=False,
)
