# bot/plugins/base/set.py file :
import logging
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

# Global ADMIN list synced with database
ADMIN = list(config.ROOT_ADMINS_ID)
DEFAULT_OWNERS = set(config.ROOT_ADMINS_ID)  # Capture initial owners at startup
logger.info(f"Initialized DEFAULT_OWNERS: {DEFAULT_OWNERS}")

# Store the message ID of the settings panel to update it
# {chat_id: message_id}
settings_panel_message_ids = {}
# Store user state for who is currently adding an admin
# {user_id: (prompt_message_id, original_admin_settings_message_id)}
user_awaiting_admin_input = {}

def get_admin_buttons():
    """Generate buttons for each admin ID and an add button."""
    buttons = [[InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin")]]
    for admin_id in ADMIN:
        buttons.append([InlineKeyboardButton(f"Admin ID: {admin_id}", callback_data=f"admin_{admin_id}")])
    return InlineKeyboardMarkup(buttons)

def get_delay_status_text():
    """Get current delay status text (placeholder, adapt to your delay var if exists)."""
    # Assuming a delay setting in options, e.g., FREE_DELAY_SECONDS
    delay = getattr(options.settings, 'FREE_DELAY_SECONDS', 0)  # Add to SettingsModel if needed
    return f"{delay} ثانیه" if delay > 0 else "غیرفعال"

@Client.on_message(
    filters.command("settings") & filters.private & PyroFilters.admin(),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def settings_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Log for debugging
    logger.info(f"Settings command called by user {user_id}")

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
    original_settings_message_id = query.message.id  # This is the main settings panel message

    # Check if the user is an admin
    if user_id not in ADMIN:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    admin_msg = await query.message.edit_text(
        "👑 **تنظیمات ادمین**\n\nلیست ادمین‌های فعلی:",
        reply_markup=get_admin_buttons()
    )
    settings_panel_message_ids[query.message.chat.id] = admin_msg.id  # Update to track admin settings panel
    await query.answer("تنظیمات ادمین باز شد.")

@Client.on_callback_query(filters.regex(r"^admin_(\d+)$"))
async def admin_id_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if user_id not in ADMIN:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if admin_id is a default owner
    if admin_id in DEFAULT_OWNERS:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    # Prevent removing the last admin
    if len(ADMIN) <= 1:
        await query.answer("⚠️ نمی‌توانید آخرین ادمین را حذف کنید!", show_alert=True)
        return

    # Prevent admin from removing themselves
    if user_id == admin_id:
        await query.answer("⚠️ شما نمی‌توانید خودتان را حذف کنید!", show_alert=True)
        return

    # Show confirmation message with Yes/Back buttons
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

    # Check if the user is an admin
    if user_id not in ADMIN:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if admin_id is a default owner
    if admin_id in DEFAULT_OWNERS:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    # Check if the admin_id is still in ADMIN
    if admin_id not in ADMIN:
        await query.answer("⚠️ این کاربر دیگر ادمین نیست!", show_alert=True)
        return

    # Remove admin from list and save to DB
    new_admins = list(ADMIN)
    new_admins.remove(admin_id)
    ADMIN[:] = new_admins  # Update global
    await database.db["BotSettings"].update_one(
        {"_id": "Admins"},
        {"$set": {"admins": ADMIN}},
        upsert=True
    )
    config.sync_admins(ADMIN)  # فیکس: sync با config برای فیلترها
    logger.info(f"Admin ID {admin_id} removed by user {user_id}. Updated ADMIN list: {ADMIN}")

    # Send notification to the removed admin
    try:
        await client.send_message(
            chat_id=admin_id,
            text="شما از ادمین بودن برکنار شدید ☺️🙏"
        )
        logger.info(f"Sent removal notification to user {admin_id}")
    except Exception as e:
        logger.error(f"Failed to send removal notification to user {admin_id}: {e}")

    # Update admin settings panel
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

    # Check if the user is an admin
    if user_id not in ADMIN:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Return to admin settings panel
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
    original_admin_settings_message_id = query.message.id  # This is the admin settings panel message

    # Check if the user is an admin
    if user_id not in ADMIN:
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if this user already has a prompt active to prevent multiple prompts
    if user_id in user_awaiting_admin_input:
        try:
            # Attempt to delete the old prompt if it exists
            old_prompt_id, _ = user_awaiting_admin_input[user_id]
            await client.delete_messages(query.message.chat.id, old_prompt_id)
        except Exception as e:
            logger.warning(f"Could not delete old admin prompt for {user_id}: {e}")

    prompt_msg = await query.message.reply_text(
        "لطفا ID عددی کاربر را برای افزودن به لیست ادمین‌ها ارسال کنید.",
        quote=True
    )
    user_awaiting_admin_input[user_id] = (prompt_msg.id, original_admin_settings_message_id)
    await query.answer("در انتظار دریافت ID ادمین جدید...")

@Client.on_message(
    filters.private & PyroFilters.admin() & filters.text & ~filters.command([]),
)
@RateLimiter.hybrid_limiter(func_count=1)
async def receive_input_value(client: Client, message: Message):
    user_id = message.from_user.id

    # Log for debugging
    logger.info(f"Input received from user {user_id}: {message.text}")

    # Handle admin ID input
    if user_id in user_awaiting_admin_input:
        prompt_message_id, admin_settings_message_id = user_awaiting_admin_input[user_id]

        # Check if the input is a valid number
        if not message.text.isdigit():
            await message.reply_text("⚠️ ورودی نامعتبر است. لطفا فقط ID عددی ارسال کنید.", quote=True)
            return

        new_admin_id = int(message.text)

        # Check if the ID is already in ADMIN
        if new_admin_id in ADMIN:
            await message.reply_text("⚠️ این ID قبلاً در لیست ادمین‌ها وجود دارد!", quote=True)
            return

        # Update ADMIN list and save to DB
        ADMIN.append(new_admin_id)
        await database.db["BotSettings"].update_one(
            {"_id": "Admins"},
            {"$set": {"admins": ADMIN}},
            upsert=True
        )
        config.sync_admins(ADMIN)  # فیکس: sync با config برای فیلترها
        logger.info(f"New admin ID {new_admin_id} added by admin {user_id}. Updated ADMIN list: {ADMIN}")

        # Send notification to the new admin
        try:
            await client.send_message(
                chat_id=new_admin_id,
                text="شما ادمین شدید 😍"
            )
            logger.info(f"Sent admin promotion notification to user {new_admin_id}")
        except Exception as e:
            logger.error(f"Failed to send admin promotion notification to user {new_admin_id}: {e}")

        # Delete prompt and input messages
        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_message_id, message.id])
        except Exception as e:
            logger.error(f"Error deleting prompt/input messages for admin setting: {e}")

        # Update admin settings panel
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

        # Clear user state
        del user_awaiting_admin_input[user_id]
        return

    # Handle other inputs (e.g., delay) if implemented
    # Placeholder for delay input - add FREE_DELAY_SECONDS to SettingsModel if needed
    # elif user_id in user_awaiting_delay_input:
    #     ... (similar logic)

HelpCmd.set_help(
    command="settings",
    description="دسترسی به پنل تنظیمات ربات برای مدیریت ادمین‌ها و سایر تنظیمات.",
    allow_global=False,
    allow_non_admin=False,
)
