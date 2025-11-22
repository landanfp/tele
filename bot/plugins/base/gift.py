# bot/plugins/base/gift.py file :
import asyncio
import datetime
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery  # اضافه: InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

# ... (بقیه importها و متغیرها مثل قبل: config, MongoDB, etc.)

# ... (functions: is_gift_plan_used, get_user_state, etc. مثل قبل)

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
        if current_plan != 'free':
            await message.reply_text("⚠️ شما به دلیل داشتن پلن ویژه قادر به دریافت این هدیه نیستید.")
            return

    if await is_gift_plan_used(user_id):
        await message.reply_text("⚠️ شما قبلاً از این هدیه استفاده کرده‌اید.")
        return

    # تنظیم state اولیه
    set_user_state(user_id, {'step': 'waiting_phone'})
    
    # اضافه: Inline Keyboard برای شروع
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 اشتراک‌گذاری شماره تلفن", callback_data="gift_share_contact")]
    ])
    
    await message.reply_text(
        "🎁 برای فعال‌سازی پلن هدیه، ابتدا اطلاعات خود را تأیید کنید.\n\n"
        "👆 روی دکمه زیر کلیک کنید تا شماره تلفن واقعی‌تون رو به اشتراک بذارید.",
        reply_markup=markup
    )
    print(f"DEBUG: Waiting for phone from user {user_id}")

@Client.on_callback_query(filters.regex(r"^gift_share_contact$") & filters.private)
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_share_contact_callback(client: Client, callback: CallbackQuery) -> None:
    """Callback برای دکمه Inline Share Contact – نمایش ReplyKeyboard."""
    user_id = callback.from_user.id
    state = get_user_state(user_id)
    
    if state.get('step') != 'waiting_phone':
        await callback.answer("❌ این مرحله منقضی شده. دوباره /gift بزنید.", show_alert=True)
        return
    
    # نمایش ReplyKeyboard با Share Contact
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.edit_text(
        "📱 لطفاً دکمه Share Contact رو بزنید و شماره تلفن واقعی‌تون رو به اشتراک بذارید.",
        reply_markup=markup
    )
    await callback.answer("دکمه Share Contact ظاهر شد!")  # تأیید بدون alert
    print(f"DEBUG: ReplyKeyboard shown for user {user_id}")

# handler برای contact (مثل قبل، اما بدون تغییر عمده)
@Client.on_message(filters.contact & filters.private & PyroFilters.subscription())
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_phone_share(client: Client, message: Message) -> None:
    """دریافت شماره تلفن از contact share."""
    print(f"DEBUG: Contact message received from user {message.from_user.id}")
    user_id = message.from_user.id
    state = get_user_state(user_id)

    if state.get('step') != 'waiting_phone':
        print(f"DEBUG: Ignoring contact - wrong state: {state.get('step')}")
        return

    if not hasattr(message, 'contact') or not message.contact:
        print("DEBUG: No contact in message!")
        return

    phone_number = message.contact.phone_number
    print(f"DEBUG: Phone received: {phone_number}")
    set_user_state(user_id, {'step': 'waiting_name', 'phone': phone_number})
    
    # پاک کردن کیبورد Reply
    remove_markup = ReplyKeyboardMarkup([], resize_keyboard=True)
    
    await message.reply_text(
        "✅ شماره تلفن دریافت شد.\n\n👤 حالا نام کامل خود را ارسال کنید.",
        reply_markup=remove_markup
    )
    print(f"DEBUG: Waiting for name from user {user_id}")

# handler برای text (مثل قبل)
@Client.on_message(filters.text & filters.private & PyroFilters.subscription())
@RateLimiter.hybrid_limiter(func_count=1)
async def handle_name_input(client: Client, message: Message) -> None:
    """دریافت نام و فعال‌سازی پلن."""
    print(f"DEBUG: Text message received from user {message.from_user.id}: {message.text}")
    user_id = message.from_user.id
    state = get_user_state(user_id)

    if state.get('step') != 'waiting_name':
        print(f"DEBUG: Ignoring text - wrong state: {state.get('step')}")
        return

    full_name = message.text.strip()
    phone_number = state.get('phone', 'نامشخص')
    print(f"DEBUG: Name received: {full_name}, Phone: {phone_number}")

    if not full_name:
        await message.reply_text("❌ نام نمی‌تواند خالی باشد. لطفاً نام کامل خود را ارسال کنید.")
        return

    # فعال‌سازی پلن
    expiry_date = datetime.date.today() + datetime.timedelta(days=GIFT_PLAN_DURATION)
    try:
        await db.set_user_plan(user_id, GIFT_PLAN_NAME, expiry_date.isoformat())
        print(f"DEBUG: Plan set for user {user_id}")
    except Exception as e:
        print(f"DEBUG: Error setting plan: {e}")
        await message.reply_text(f"❌ خطا در فعال‌سازی پلن: {e}")
        clear_user_state(user_id)
        return

    try:
        daily_limit = DAILY_LINK_LIMITS.get(GIFT_PLAN_NAME, 5)
        # اضافه: Inline Keyboard برای موفقیت (با لینک به /myplan)
        success_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 بررسی پلن من", callback_data="gift_check_plan")]
        ])
        
        await message.reply_text(
            f"🎁 پلن هدیه 7 روزه با موفقیت برای شما فعال شد!\n\n"
            f"👤 نام: {full_name}\n"
            f"📱 شماره: {phone_number}\n"
            f"⏳ این پلن تا تاریخ {expiry_date.strftime('%Y/%m/%d')} معتبر است.\n"
            f"💾 محدودیت کلیک روزانه این پلن: {daily_limit} کلیک\n\n"
            f"روی دکمه زیر کلیک کنید تا وضعیت پلن‌تون رو ببینید.",
            reply_markup=success_markup
        )

        user_mention = f"[{message.from_user.first_name}](tg://user?id={user_id})"
        await client.send_message(
            LOG_CHANNEL,
            f"🎉 پلن هدیه فعال شد!\n\n"
            f"👤 کاربر: {user_mention}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"👤 نام کامل: {full_name}\n"
            f"📱 شماره تلفن: `{phone_number}`\n"
            f"نوع پلن: {GIFT_PLAN_NAME}\n"
            f"🗓️ تاریخ انقضا: {expiry_date.strftime('%Y/%m/%d')}"
        )
        print(f"DEBUG: Success message and log sent for user {user_id}")

        clear_user_state(user_id)

    except FloodWait as e:
        print(f"Sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        await message.reply_text("⚠️ به دلیل شلوغی سرور، فعال سازی با تاخیر انجام شد. لطفاً مجدداً بررسی کنید.")
        clear_user_state(user_id)
    except Exception as e:
        print(f"DEBUG: Error in final steps: {e}")
        await message.reply_text(f"❌ خطایی در فعال سازی پلن هدیه رخ داد: {e}")
        clear_user_state(user_id)

# اضافه: Callback برای دکمه بررسی پلن (اختیاری – می‌تونه /myplan رو trigger کنه)
@Client.on_callback_query(filters.regex(r"^gift_check_plan$") & filters.private)
async def check_plan_callback(client: Client, callback: CallbackQuery) -> None:
    """Callback برای بررسی پلن بعد از موفقیت."""
    user_id = callback.from_user.id
    await callback.message.reply_text("📋 برای بررسی وضعیت پلن، دستور /myplan رو بزنید.")
    await callback.answer("بررسی پلن باز شد!")  # بدون alert

# ... (HelpCmd مثل قبل)
