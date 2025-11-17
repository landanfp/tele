# bot/plugins/base/set.py file :
import logging
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from bot.config import config
from bot.database import MongoDB
from bot.utilities.helpers import RateLimiter
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

logger = logging.getLogger(__name__)
database = MongoDB()
db = database

# Store the message ID of the settings panel to update it
# {chat_id: message_id}
settings_panel_message_ids = {}
# Store user state for who is currently adding an admin
# {user_id: (prompt_message_id, original_admin_settings_message_id)}
user_awaiting_admin_input = {}
# Store user state for who is currently adding a channel
# {user_id: (prompt_message_id, original_channel_settings_message_id)}
user_awaiting_channel_input = {}

def get_admin_buttons():
    """Generate buttons for each admin ID and an add button."""
    buttons = [[InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin")]]
    for admin_id in config.ROOT_ADMINS_ID:
        buttons.append([InlineKeyboardButton(f"Admin ID: {admin_id}", callback_data=f"admin_{admin_id}")])
    return InlineKeyboardMarkup(buttons)

def get_channel_buttons():
    """Generate buttons for each channel and an add button at the top."""
    channels = config.FORCE_SUB_CHANNELS
    buttons = [[InlineKeyboardButton("➕ افزودن کانال", callback_data="add_channel")]]
    for channel in channels:
        display_name = f"Channel ID: {channel}"
        buttons.append([InlineKeyboardButton(display_name, callback_data=f"channel_{channel}")])
    return InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("settings") & filters.private & PyroFilters.admin())
@RateLimiter.hybrid_limiter(func_count=1)
async def settings_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Log for debugging
    logger.info(f"Settings command called by user {user_id}")

    buttons = InlineKeyboardMarkup(
        [
            # [InlineKeyboardButton(f"⏱️ تایم محدودیت رایگان: {status_text}", callback_data="set_free_delay")],  # Commented out as per request
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

# @Client.on_callback_query(filters.regex("set_free_delay"))  # Commented out as per request
# async def set_free_delay_callback(client: Client, query: CallbackQuery):
#     ...  # Entire function commented out

@Client.on_callback_query(filters.regex("admin_settings"))
@RateLimiter.hybrid_limiter(func_count=1)
async def admin_settings_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_settings_message_id = query.message.id  # This is the main settings panel message

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    admin_msg = await query.message.edit_text(
        "👑 **تنظیمات ادمین**\n\nلیست ادمین‌های فعلی:",
        reply_markup=get_admin_buttons()
    )
    settings_panel_message_ids[query.message.chat.id] = admin_msg.id  # Update to track admin settings panel
    await query.answer("تنظیمات ادمین باز شد.")

@Client.on_callback_query(filters.regex(r"^admin_(\d+)$"))
@RateLimiter.hybrid_limiter(func_count=1)
async def admin_id_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if admin_id is a default owner (assuming first ID is owner)
    default_owners = [config.ROOT_ADMINS_ID[0]] if config.ROOT_ADMINS_ID else []
    if admin_id in default_owners:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    # Prevent removing the last admin
    if len(config.ROOT_ADMINS_ID) <= 1:
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
@RateLimiter.hybrid_limiter(func_count=1)
async def remove_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if admin_id is a default owner
    default_owners = [config.ROOT_ADMINS_ID[0]] if config.ROOT_ADMINS_ID else []
    if admin_id in default_owners:
        await query.answer("⚠️ نمی‌توانید مالک را حذف کنید!", show_alert=True)
        return

    # Check if the admin_id is still in ROOT_ADMINS_ID
    if admin_id not in config.ROOT_ADMINS_ID:
        await query.answer("⚠️ این کاربر دیگر ادمین نیست!", show_alert=True)
        return

    # Remove admin from ROOT_ADMINS_ID
    new_admin_ids = list(config.ROOT_ADMINS_ID)
    new_admin_ids.remove(admin_id)
    config.ROOT_ADMINS_ID = new_admin_ids  # Update config list
    logger.info(f"Admin ID {admin_id} removed by user {user_id}. Updated ROOT_ADMINS_ID: {config.ROOT_ADMINS_ID}")

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
@RateLimiter.hybrid_limiter(func_count=1)
async def cancel_remove_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    admin_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
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
@RateLimiter.hybrid_limiter(func_count=1)
async def add_admin_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_admin_settings_message_id = query.message.id  # This is the admin settings panel message

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
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

@Client.on_callback_query(filters.regex("channel_settings"))
@RateLimiter.hybrid_limiter(func_count=1)
async def channel_settings_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_settings_message_id = query.message.id  # This is the main settings panel message

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    channel_msg = await query.message.edit_text(
        "📢 **مدیریت کانال**\n\nلیست کانال‌های فعلی:",
        reply_markup=get_channel_buttons()
    )
    settings_panel_message_ids[query.message.chat.id] = channel_msg.id  # Update to track channel settings panel
    await query.answer("تنظیمات کانال باز شد.")

@Client.on_callback_query(filters.regex(r"^channel_(.+)$"))
@RateLimiter.hybrid_limiter(func_count=1)
async def channel_id_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    channel_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Show confirmation message with Yes/Back buttons
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ بله", callback_data=f"remove_channel_{channel_id}")],
            [InlineKeyboardButton("↩️ برگشت", callback_data=f"cancel_remove_channel_{channel_id}")]
        ]
    )

    try:
        await query.message.edit_text(
            f"آیا موافق هستید کانال `{channel_id}` از لیست حذف شود؟",
            reply_markup=buttons
        )
        await query.answer()
    except Exception as e:
        logger.error(f"Error updating channel removal confirmation message: {e}")
        await query.message.reply_text("⚠️ خطایی در نمایش پیام تأیید رخ داد!", quote=True)

@Client.on_callback_query(filters.regex(r"^remove_channel_(.+)$"))
@RateLimiter.hybrid_limiter(func_count=1)
async def remove_channel_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    channel_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Ensure FORCE_SUB_CHANNELS is a list
    channels = list(config.FORCE_SUB_CHANNELS)

    # Check if the channel_id is still in FORCE_SUB_CHANNELS
    if channel_id not in channels:
        await query.answer("⚠️ این کانال دیگر در لیست نیست!", show_alert=True)
        return

    # Prevent removing the last channel
    if len(channels) <= 1:
        await query.answer("⚠️ نمی‌توانید تنها کانال را حذف کنید!", show_alert=True)
        return

    # Remove channel from FORCE_SUB_CHANNELS
    channels.remove(channel_id)
    config.FORCE_SUB_CHANNELS = channels
    logger.info(f"Channel {channel_id} removed by user {user_id}. Updated FORCE_SUB_CHANNELS: {config.FORCE_SUB_CHANNELS}")

    # Update channel settings panel
    try:
        await query.message.edit_text(
            "📢 **مدیریت کانال**\n\nلیست کانال‌های فعلی:",
            reply_markup=get_channel_buttons()
        )
        await query.message.reply_text(f"✅ باموفقیت کانال `{channel_id}` حذف شد.", quote=True)
        await query.answer()
    except Exception as e:
        logger.error(f"Error updating channel settings panel after removal: {e}")
        await query.message.reply_text("⚠️ خطایی در به‌روزرسانی پنل کانال رخ داد، اما کانال حذف شد!", quote=True)

@Client.on_callback_query(filters.regex(r"^cancel_remove_channel_(.+)$"))
@RateLimiter.hybrid_limiter(func_count=1)
async def cancel_remove_channel_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    channel_id = int(query.matches[0].group(1))

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Return to channel settings panel
    try:
        await query.message.edit_text(
            "📢 **مدیریت کانال**\n\nلیست کانال‌های فعلی:",
            reply_markup=get_channel_buttons()
        )
        await query.answer("به منوی قبل برگشتید.", show_alert=True)
    except Exception as e:
        logger.error(f"Error returning to channel settings panel: {e}")
        await query.message.reply_text("⚠️ خطایی در بازگشت به پنل کانال رخ داد!", quote=True)

@Client.on_callback_query(filters.regex("add_channel"))
@RateLimiter.hybrid_limiter(func_count=1)
async def add_channel_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    original_channel_settings_message_id = query.message.id  # This is the channel settings panel message

    # Check if the user is an admin
    if not PyroFilters.admin().func(None, None, query):
        await query.answer("⚠️ شما ادمین نیستید!", show_alert=True)
        return

    # Check if this user already has a prompt active to prevent multiple prompts
    if user_id in user_awaiting_channel_input:
        try:
            # Attempt to delete the old prompt if it exists
            old_prompt_id, _ = user_awaiting_channel_input[user_id]
            await client.delete_messages(query.message.chat.id, old_prompt_id)
        except Exception as e:
            logger.warning(f"Could not delete old channel prompt for {user_id}: {e}")

    prompt_msg = await query.message.reply_text(
        "لطفا ID کانال (مثل -100123456789) را ارسال کنید.",
        quote=True
    )
    user_awaiting_channel_input[user_id] = (prompt_msg.id, original_channel_settings_message_id)
    await query.answer("در انتظار دریافت ID کانال جدید...")

@Client.on_message(filters.private & PyroFilters.admin() & filters.text & ~filters.command([]))
@RateLimiter.hybrid_limiter(func_count=1)
async def receive_input_value(client: Client, message: Message):
    user_id = message.from_user.id

    # Log for debugging
    logger.info(f"Input received from user {user_id}: {message.text}")

    # # Handle delay input  # Commented out as per request
    # if user_id in user_awaiting_delay_input:
    #     ...  # Entire block commented out

    # Handle admin ID input
    if user_id in user_awaiting_admin_input:
        prompt_message_id, admin_settings_message_id = user_awaiting_admin_input[user_id]

        # Check if the input is a valid number
        if not message.text.isdigit():
            await message.reply_text("⚠️ ورودی نامعتبر است. لطفا فقط ID عددی ارسال کنید.", quote=True)
            return

        new_admin_id = int(message.text)

        # Check if the ID is already in ROOT_ADMINS_ID
        if new_admin_id in config.ROOT_ADMINS_ID:
            await message.reply_text("⚠️ این ID قبلاً در لیست ادمین‌ها وجود دارد!", quote=True)
            return

        # Update ROOT_ADMINS_ID
        config.ROOT_ADMINS_ID = config.ROOT_ADMINS_ID + (new_admin_id,)
        logger.info(f"New admin ID {new_admin_id} added by owner {user_id}. Updated ROOT_ADMINS_ID: {config.ROOT_ADMINS_ID}")

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

    # Handle channel input
    elif user_id in user_awaiting_channel_input:
        prompt_message_id, channel_settings_message_id = user_awaiting_channel_input[user_id]

        new_channel = message.text.strip()

        # Validate channel input (numeric ID like -100123456789)
        if not new_channel.startswith('-') or not new_channel[1:].isdigit():
            await message.reply_text("⚠️ ورودی نامعتبر است. لطفا ID کانال (مثل -100123456789) را ارسال کنید.", quote=True)
            return

        new_channel_id = int(new_channel)

        # Ensure FORCE_SUB_CHANNELS is a list
        channels = list(config.FORCE_SUB_CHANNELS)

        # Check if the channel is already in FORCE_SUB_CHANNELS
        if new_channel_id in channels:
            await message.reply_text("⚠️ این کانال قبلاً در لیست وجود دارد!", quote=True)
            return

        # Update FORCE_SUB_CHANNELS
        channels.append(new_channel_id)
        config.FORCE_SUB_CHANNELS = channels
        logger.info(f"New channel {new_channel_id} added by owner {user_id}. Updated FORCE_SUB_CHANNELS: {config.FORCE_SUB_CHANNELS}")

        # Delete prompt and input messages
        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_message_id, message.id])
        except Exception as e:
            logger.error(f"Error deleting prompt/input messages for channel setting: {e}")

        # Update channel settings panel
        try:
            await client.edit_message_text(
                chat_id=message.chat.id,
                message_id=channel_settings_message_id,
                text="📢 **مدیریت کانال**\n\nلیست کانال‌های فعلی:",
                reply_markup=get_channel_buttons()
            )
            await client.send_message(message.chat.id, f"✅ کانال جدید `{new_channel_id}` اضافه شد.")
        except Exception as e:
            logger.error(f"Error updating channel settings panel: {e}")
            # Fallback: Send a new message with updated buttons
            new_channel_msg = await client.send_message(
                chat_id=message.chat.id,
                text="📢 **مدیریت کانال**\n\nلیست کانال‌های فعلی:",
                reply_markup=get_channel_buttons()
            )
            settings_panel_message_ids[message.chat.id] = new_channel_msg.id  # Update stored message ID
            await client.send_message(message.chat.id, f"✅ کانال جدید `{new_channel_id}` اضافه شد، اما پنل قبلی به‌روز نشد. پنل جدید نمایش داده شد.")

        # Clear user state
        del user_awaiting_channel_input[user_id]

    else:
        logger.debug(f"User {user_id} is not awaiting any input, passing message: {message.text}")
        await message.continue_propagation()


HelpCmd.set_help(
    command="settings",
    description="دسترسی به پنل تنظیمات ادمین و کانال‌ها.",
    allow_global=False,
    allow_non_admin=False,
)
