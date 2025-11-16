import logging
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from bot.config import config, DAILY_LINK_LIMITS
from bot.database import MongoDB
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd
from bot.utilities.helpers.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
database = MongoDB()
db = database
LOG_CHANNEL = config.BACKUP_CHANNEL  # Assuming backup as log

async def get_user_stats(user_id, client=None):
    await db.check_and_update_expired_plan(user_id, client)
    await db.check_and_reset_daily_usage(user_id)
    user = await db.db["Users"].find_one({'id': user_id})
    if user:
        plan = user.get('plan', 'free')
        daily_clicks = user.get('daily_clicks', 0)
        daily_limit = DAILY_LINK_LIMITS.get(plan, 2)
        remaining = daily_limit - daily_clicks
        expiry_date = user.get('plan_expiry')
        return plan, daily_clicks, daily_limit, remaining, expiry_date
    return 'free', 0, 2, 2, None

@Client.on_message(filters.private & filters.command(["myplan"]))
@RateLimiter.hybrid_limiter(func_count=1)
async def my_plan_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if await db.is_user_banned(user_id):
        await message.reply("⚠️ شما بن شده‌اید و اجازه استفاده از ربات را ندارید!!")
        return
    plan, daily_clicks, daily_limit, remaining, expiry_date = await get_user_stats(user_id, client)
    usage_percent = (daily_clicks / daily_limit) * 100 if daily_limit > 0 else 0
    bar = '█' * int(usage_percent / 10) + '░' * (10 - int(usage_percent / 10))

    if plan == "free":
        text = f"""**📊 وضعیت پلن شما (رایگان)**

👤 نام کاربر: {message.from_user.first_name}
🆔 آیدی عددی شما: `{user_id}`
⚙️ پلن شما: رایگان
🔢 محدودیت کلیک روزانه: {daily_limit}
⬆️ تعداد کلیک استفاده شده: {daily_clicks}
⬇️ تعداد کلیک باقی مانده: {remaining}
🚦 درصد استفاده شده: {int(usage_percent)}% [{bar}]"""
    else:
        expiry_str = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").strftime("%Y/%m/%d") if expiry_date else "نامشخص"
        today = datetime.date.today()
        expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None
        remaining_days = (expiry - today).days if expiry else "نامشخص"

        text = f"""**💎 وضعیت پلن شما ({plan.replace('_', ' ').title()})**

👤 نام کاربر: {message.from_user.first_name}
🆔 آیدی عددی شما: `{user_id}`
⚙️ پلن شما: {plan.replace('_', ' ').title()}
🔢 محدودیت کلیک روزانه: {daily_limit}
⬆️ تعداد کلیک استفاده شده: {daily_clicks}
⬇️ تعداد کلیک باقی مانده: {remaining}
🚦 درصد استفاده شده: {int(usage_percent)}% [{bar}]
🗓️ روزهای باقی مانده: {remaining_days}
⏳ تاریخ اتمام پلن: {expiry_str}"""
    await message.reply(text, quote=True)

@Client.on_message(filters.private & PyroFilters.admin() & filters.command(["addpremium"]))
@RateLimiter.hybrid_limiter(func_count=1)
async def addpremium(client: Client, message: Message):
    if len(message.command) != 2:
        await message.reply("⚠️ برای ارتقا پلن، آیدی عددی کاربر را بعد از دستور وارد کنید.\n\nمثال: `/addpremium 123456789`", quote=True)
        return
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply("⚠️ آیدی کاربر باید یک عدد باشد.", quote=True)
        return

    # کیبورد با همه پلن‌ها (بدون دسته‌بندی)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("روزانه 5 کلیک", callback_data=f"daily5_{user_id}")],
        [InlineKeyboardButton("روزانه 10 کلیک", callback_data=f"daily10_{user_id}")],
        [InlineKeyboardButton("روزانه 20 کلیک", callback_data=f"daily20_{user_id}")],
        [InlineKeyboardButton("هفتگی 5 کلیک", callback_data=f"weekly5_{user_id}")],
        [InlineKeyboardButton("هفتگی 10 کلیک", callback_data=f"weekly10_{user_id}")],
        [InlineKeyboardButton("هفتگی 15 کلیک", callback_data=f"weekly15_{user_id}")],
        [InlineKeyboardButton("هفتگی 20 کلیک", callback_data=f"weekly20_{user_id}")],
        [InlineKeyboardButton("ماهانه 5 کلیک", callback_data=f"monthly5_{user_id}")],
        [InlineKeyboardButton("ماهانه 10 کلیک", callback_data=f"monthly10_{user_id}")],
        [InlineKeyboardButton("ماهانه 15 کلیک", callback_data=f"monthly15_{user_id}")],
        [InlineKeyboardButton("ماهانه 20 کلیک", callback_data=f"monthly20_{user_id}")],
    ])
    await message.reply(
        "**🦋 به بخش ارتقا پلن کاربران خوش آمدید.\n\n🚦پلن موردنظر برای کاربر را انتخاب کنید.👇**",
        quote=True,
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex('^daily5_(\d+)$'))
async def daily5(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=1)
    await db.set_user_plan(user_id, "daily_5", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : روزانه 5 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['daily_5']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن روزانه 5 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To daily_5. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^daily10_(\d+)$'))
async def daily10(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=1)
    await db.set_user_plan(user_id, "daily_10", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : روزانه 10 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['daily_10']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن روزانه 10 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To daily_10. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^daily20_(\d+)$'))
async def daily20(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=1)
    await db.set_user_plan(user_id, "daily_20", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : روزانه 20 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['daily_20']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن روزانه 20 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To daily_20. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^weekly5_(\d+)$'))
async def weekly5(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=7)
    await db.set_user_plan(user_id, "weekly_5", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : هفتگی 5 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['weekly_5']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن هفتگی 5 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To weekly_5. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^weekly10_(\d+)$'))
async def weekly10(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=7)
    await db.set_user_plan(user_id, "weekly_10", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : هفتگی 10 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['weekly_10']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن هفتگی 10 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To weekly_10. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^weekly15_(\d+)$'))
async def weekly15(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=7)
    await db.set_user_plan(user_id, "weekly_15", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : هفتگی 15 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['weekly_15']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن هفتگی 15 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To weekly_15. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^weekly20_(\d+)$'))
async def weekly20(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=7)
    await db.set_user_plan(user_id, "weekly_20", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : هفتگی 20 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['weekly_20']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن هفتگی 20 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To weekly_20. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^monthly5_(\d+)$'))
async def monthly5(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=30)
    await db.set_user_plan(user_id, "monthly_5", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : ماهانه 5 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['monthly_5']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن ماهانه 5 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To monthly_5. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^monthly10_(\d+)$'))
async def monthly10(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=30)
    await db.set_user_plan(user_id, "monthly_10", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : ماهانه 10 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['monthly_10']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن ماهانه 10 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To monthly_10. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^monthly15_(\d+)$'))
async def monthly15(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=30)
    await db.set_user_plan(user_id, "monthly_15", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : ماهانه 15 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['monthly_15']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن ماهانه 15 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To monthly_15. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^monthly20_(\d+)$'))
async def monthly20(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    expiry_date = datetime.date.today() + datetime.timedelta(days=30)
    await db.set_user_plan(user_id, "monthly_20", expiry_date.isoformat())
    await callback_query.message.edit(f"**✅ تغییر پلن کاربر {user_id} باموفقیت انجام شد.\n\n🔮 نوع پلن : ماهانه 20 کلیک\n📀 محدودیت روزانه این پلن: {DAILY_LINK_LIMITS['monthly_20']} کلیک**")
    try:
        await client.send_message(user_id, "**✅ حساب شما به پلن ماهانه 20 کلیک ارتقا پیدا کرد.\n⭕️ هم اکنون بررسی کنید 👈 /myplan **")
        await client.send_message(LOG_CHANNEL, f"⚡️ Plan Upgraded successfully 💥\n\nUser ID: `{user_id}` Upgraded To monthly_20. check their plan here /myplan")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_message(filters.private & PyroFilters.admin() & filters.command(["delete_premium"]))
@RateLimiter.hybrid_limiter(func_count=1)
async def delete_premium_handler(client: Client, message: Message):
    if len(message.command) != 2:
        await message.reply("⚠️ برای حذف پلن ویژه، آیدی عددی کاربر را بعد از دستور وارد کنید.\n\nمثال: `/delete_premium 123456789`", quote=True)
        return
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply("⚠️ آیدی کاربر باید یک عدد باشد.", quote=True)
        return

    await message.reply(
        f"آیا مطمئن هستید که می‌خواهید پلن ویژه کاربر با آیدی `{user_id}` را حذف کنید؟!",
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ بله", callback_data=f"delpremium_yes_{user_id}"),
                    InlineKeyboardButton("❌ خیر", callback_data=f"delpremium_no_{user_id}"),
                ]
            ]
        )
    )

@Client.on_callback_query(filters.regex('^delpremium_yes_(\d+)$'))
async def delete_premium_yes(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    await db.set_user_plan(user_id, "free", None)
    await callback_query.edit_message_text(f"✅ باموفقیت پلن کاربر با آیدی `{user_id}` به پلن رایگان بازگردانده شد.")
    try:
        await client.send_message(user_id, "⚠️ پلن ویژه شما منقضی شد و به پلن رایگان بازگشتید. برای اطلاع از وضعیت پلن خود از دستور `/myplan` استفاده کنید.")
        await client.send_message(LOG_CHANNEL, f"⚠️ Plan Removed successfully 🗑️\n\nUser ID: `{user_id}`'s premium plan has been removed.")
    except Exception as e:
        await callback_query.message.reply(f"⚠️ هنگام ارسال پیام به کاربر {user_id} خطایی رخ داد: {e}")

@Client.on_callback_query(filters.regex('^delpremium_no_(\d+)$'))
async def delete_premium_no(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.matches[0].group(1))
    await callback_query.edit_message_text(f"❌ عملیات حذف پلن ویژه برای کاربر با آیدی `{user_id}` لغو شد.")

HelpCmd.set_help(
    command="myplan",
    description="نمایش وضعیت پلن فعلی کاربر (تعداد کلیک/دانلود).",
    allow_global=True,
    allow_non_admin=True,
)

HelpCmd.set_help(
    command="addpremium",
    description="ارتقا پلن کاربر به سطوح روزانه/هفتگی/ماهانه.",
    allow_global=False,
    allow_non_admin=False,
)

HelpCmd.set_help(
    command="delete_premium",
    description="حذف پلن پریمیوم کاربر و بازگشت به رایگان.",
    allow_global=False,
    allow_non_admin=False,
)
