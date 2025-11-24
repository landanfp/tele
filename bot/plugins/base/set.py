import logging
import time
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from bot.config import config
from bot.database import MongoDB
from bot.options import options
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

logger = logging.getLogger(__name__)
database = MongoDB()

# Capture initial owners at startup (only original admins from config/env)
DEFAULT_OWNERS = set(config.ROOT_ADMINS_ID)

# settings_panel_message_ids and user_awaiting_admin_input
settings_panel_message_ids = {}
user_awaiting_admin_input = {}

def get_admin_buttons():
    """Generate buttons for each admin ID and an add button."""
    buttons = [[InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin")]]
    for admin_id in config.ROOT_ADMINS_ID:
        buttons.append([InlineKeyboardButton(f"Admin ID: {admin_id}", callback_data=f"admin_{admin_id}")])
    return InlineKeyboardMarkup(buttons)

def get_delay_status_text():
    """Get current delay status text (placeholder, adapt to your delay var if exists)."""
    delay = getattr(options.settings, 'FREE_DELAY_SECONDS', 0)
    return f"{delay} ثانیه" if delay > 0 else "غیرفعال"

@Client.on_message(
    filters.command("settings") & filters.private & PyroFilters.admin(),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def settings_command(client: Client, message: Message):
    chat_id = message.chat.id

    logger.info(f"Settings command called by user {message.from_user.id}")

    status_text = get_delay_status_text()

    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"⏱️ تایم محدودیت رایگان: {status_text}", callback_data="set_free_delay")],
            [InlineKeyboardButton("👑 تنظیم ادمین", callback_data="admin_settings")],
            [InlineKeyboardButton("📢 مدیریت کانال‌ها", callback_data="channel_settings")]
        ]
    )

    settings_msg = await message.reply_text(
        "⚙️ **تنظیمات ربات**\n\nدر اینجا می‌توانید تنظیمات مربوط به کاربران رایگان، ادمین‌ها و کانال‌ها را مدیریت کنید:",
        reply_markup=buttons,
        quote=True
    )
    settings_panel_message_ids[chat_id] = settings_msg.id

@Client.on_callback_query(filters.regex("admin_settings"))
async def admin_settings_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_settings_message_id = query.message.id

    if user_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    admin_msg = await query.message.edit_text(
        "👑 **تنظیمات ادمین**\n\nلیست ادمین‌های فعلی:",
        reply_markup=get_admin_buttons()
    )
    settings_panel_message_ids[query.message.chat.id] = admin_msg.id
    await query.answer("تنظیمات ادمین باز شد.")

@Client.on_callback_query(filters.regex(r"^admin_(\d+)$"))
async def admin_id_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    if user_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    if admin_id in DEFAULT_OWNERS:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    if len(config.ROOT_ADMINS_ID) <= 1:
        await query.answer("⚠️ نمی‌توانید آخرین ادمین را حذف کنید!", show_alert=True)
        return

    if user_id == admin_id:
        await query.answer("⚠️ شما نمی‌توانید خودتان را حذف کنید!", show_alert=True)
        return

    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ بله", callback_data=f"remove_admin_{admin_id}")],
            [InlineKeyboardButton("↩️ برگشت", callback_data=f"cancel_remove_admin_{admin_id}")]
        ]
    )

    try:
        await query.message.edit_text(
            f"آیا موافق هستید ادمین `{admin_id}` از ادمینی برکنار شود؟",
            reply_markup=buttons
        )
        await query.answer()
    except Exception as e:
        logger.error(f"Error updating admin removal confirmation message: {e}")
        await query.message.reply_text("⚠️ خطایی در نمایش پیام تأیید رخ داد!", quote=True)

@Client.on_callback_query(filters.regex(r"^remove_admin_(\d+)$"))
async def remove_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    if user_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    if admin_id in DEFAULT_OWNERS:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    if admin_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ این کاربر دیگر ادمین نیست!", show_alert=True)
        return

    config.ROOT_ADMINS_ID.remove(admin_id)
    await database.db["BotSettings"].update_one(
        {"_id": "Admins"},
        {"$set": {"admins": list(config.ROOT_ADMINS_ID)}},
        upsert=True
    )
    logger.info(f"Admin ID {admin_id} removed by user {user_id}. Updated ROOT_ADMINS_ID: {config.ROOT_ADMINS_ID}")

    try:
        await client.send_message(
            chat_id=admin_id,
            text="شما از ادمین بودن برکنار شدید ☺️🙏"
        )
        logger.info(f"Sent removal notification to user {admin_id}")
    except Exception as e:
        logger.error(f"Failed to send removal notification to user {admin_id}: {e}")

    try:
        await query.message.edit_text(
            "👑 **تنظیمات ادمین**\n\nلیست ادمین‌های فعلی:",
            reply_markup=get_admin_buttons()
        )
        await query.message.reply_text(f"✅ باموفقیت کاربر `{admin_id}` از ادمینی برکنار شد.", quote=True)
        await query.answer()
    except Exception as e:
        logger.error(f"Error updating admin settings panel after removal: {e}")
        await query.message.reply_text("⚠️ خطایی در به‌روزرسانی پنل ادمین رخ داد، اما ادمین حذف شد!", quote=True)

@Client.on_callback_query(filters.regex(r"^cancel_remove_admin_(\d+)$"))
async def cancel_remove_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    if user_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    try:
        await query.message.edit_text(
            "👑 **تنظیمات ادمین**\n\nلیست ادمین‌های فعلی:",
            reply_markup=get_admin_buttons()
        )
        await query.answer("به منوی قبل برگشتید.", show_alert=True)
    except Exception as e:
        logger.error(f"Error returning to admin settings panel: {e}")
        await query.message.reply_text("⚠️ خطایی در بازگشت به پنل ادمین رخ داد!", quote=True)

@Client.on_callback_query(filters.regex("add_admin"))
async def add_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_admin_settings_message_id = query.message.id

    if user_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    if user_id in user_awaiting_admin_input:
        try:
            old_prompt_id, _ = user_awaiting_admin_input[user_id]
            await client.delete_messages(query.message.chat.id, old_prompt_id)
        except Exception as e:
            logger.warning(f"Could not delete old admin prompt for {user_id}: {e}")

    prompt_msg = await query.message.reply_text(
        "لطفا ID عددی کاربر را برای افزودن به لیست ادمین‌ها ارسال کنید.",
        quote=True
    )
    user_awaiting_admin_input[user_id] = (prompt_msg.id, original_admin_settings_message_id, time.time())  # Add timestamp
    await query.answer("در انتظار دریافت ID ادمین جدید...")

@Client.on_message(
    filters.private & PyroFilters.admin() & filters.text,
)
@RateLimiter.hybrid_limiter(func_count=1)
async def receive_input_value(client: Client, message: Message):
    user_id = message.from_user.id

    logger.info(f"Input received from user {user_id}: {message.text}")

    if user_id in user_awaiting_admin_input:
        # Timeout: 5 minutes (300 seconds)
        if time.time() - user_awaiting_admin_input[user_id][2] > 300:
            del user_awaiting_admin_input[user_id]
            logger.info(f"Admin input state timed out for user {user_id}")
            return message.continue_propagation()

        # If it's a command (starts with /), skip and propagate
        if message.text.startswith('/'):
            logger.info(f"Skipping command '{message.text}' during admin input state for user {user_id}")
            return message.continue_propagation()

        prompt_message_id, admin_settings_message_id, _ = user_awaiting_admin_input[user_id]

        if not message.text.isdigit():
            await message.reply_text("⚠️ ورودی نامعتبر است. لطفا فقط ID عددی ارسال کنید.", quote=True)
            return message.continue_propagation()

        new_admin_id = int(message.text)

        if new_admin_id in config.ROOT_ADMINS_ID:
            await message.reply_text("⚠️ این ID قبلاً در لیست ادمین‌ها وجود دارد!", quote=True)
            return message.continue_propagation()

        config.ROOT_ADMINS_ID.append(new_admin_id)
        await database.db["BotSettings"].update_one(
            {"_id": "Admins"},
            {"$set": {"admins": list(config.ROOT_ADMINS_ID)}},
            upsert=True
        )
        logger.info(f"New admin ID {new_admin_id} added by admin {user_id}. Updated ROOT_ADMINS_ID: {config.ROOT_ADMINS_ID}")

        try:
            await client.send_message(
                chat_id=new_admin_id,
                text="شما ادمین شدید 😍"
            )
            logger.info(f"Sent admin promotion notification to user {new_admin_id}")
        except Exception as e:
            logger.error(f"Failed to send admin promotion notification to user {new_admin_id}: {e}")

        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_message_id, message.id])
        except Exception as e:
            logger.error(f"Error deleting prompt/input messages for admin setting: {e}")

        try:
            await client.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=admin_settings_message_id,
                reply_markup=get_admin_buttons()
            )
            await client.send_message(message.chat.id, f"✅ ادمین جدید با ID {new_admin_id} اضافه شد.")
        except Exception as e:
            logger.error(f"Error updating admin settings panel markup: {e}")
            await client.send_message(message.chat.id, f"✅ ادمین جدید با ID {new_admin_id} اضافه شد، اما نمایش پنل ادمین به‌روز نشد.")

        del user_awaiting_admin_input[user_id]
        return message.continue_propagation()

    return message.continue_propagation()

HelpCmd.set_help(
    command="settings",
    description="دسترسی به پنل تنظیمات ربات برای مدیریت ادمین‌ها و سایر تنظیمات.",
    allow_global=False,
    allow_non_admin=False,
)
