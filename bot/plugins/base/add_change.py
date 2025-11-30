# bot/plugins/base/add_change.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.database import MongoDB
from bot.utilities.pyrofilters import PyroFilters
import logging

logger = logging.getLogger(__name__)
database = MongoDB()

# لیست اولیه کدهای VIP (فقط یکبار اجرا کن یا دستی insert کن)
INITIAL_VIP_CODES = ["ckfhyjj", "jgfjjj", "gjgjkk"]

async def init_vip_codes():
    """ابتدا لیست اولیه رو به DB اضافه کن (فقط یکبار)."""
    collection = database.db["VIPCodes"]
    for code in INITIAL_VIP_CODES:
        await collection.update_one(
            {"code": code},
            {"$set": {"code": code, "used": False, "created_at": "2025-11-22"}},
            upsert=True
        )

@Client.on_message(filters.private & PyroFilters.admin() & filters.command("add_change"))
async def add_change_handler(client: Client, message: Message):
    if len(message.command) != 2:
        await message.reply("⚠️ استفاده: /add_change {code}\nمثال: /add_change mynewcode")
        return

    new_code = message.command[1].strip().upper()
    if len(new_code) < 6:  # حداقل طول کد
        await message.reply("❌ کد باید حداقل 6 کاراکتر باشد.")
        return

    collection = database.db["VIPCodes"]
    result = await collection.update_one(
        {"code": new_code},
        {"$set": {"code": new_code, "used": False, "created_at": "2025-11-22"}},
        upsert=True
    )

    if result.acknowledged:
        await message.reply(f"✅ کد VIP `{new_code}` با موفقیت به لیست اضافه شد.")
        logger.info(f"Added VIP code: {new_code} by admin {message.from_user.id}")
    else:
        await message.reply("❌ خطا در اضافه کردن کد. دوباره امتحان کنید.")
        logger.error(f"Failed to add VIP code: {new_code}")

@Client.on_message(filters.private & PyroFilters.admin() & filters.command("change_list"))
async def change_list_handler(client: Client, message: Message):
    logger.info(f"change_list called by user {message.from_user.id}")
    try:
        collection = database.db["VIPCodes"]
        codes = await collection.find({}).sort("code").to_list(length=None)  # مرتب بر اساس کد

        # فرمت جدید: {code} - ❌ یا {code} - ✅ > {user_id}
        text = "📋 **لیست کدهای VIP:**\n\n"
        if not codes:
            text += "کدی وجود ندارد."
        else:
            for code_doc in codes:
                code = code_doc.get("code", "N/A")
                used = code_doc.get("used", False)
                if used:
                    used_by = str(code_doc.get("used_by", "نامشخص"))
                    text += f"{code} - ✅ > {used_by}\n"
                else:
                    text += f"{code} - ❌\n"

        # دکمه حذف
        keyboard = [[InlineKeyboardButton("🗑️ حذف کدهای استفاده شده", callback_data="delete_used_codes")]]

        await message.reply(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"change_list sent to {message.from_user.id}, {len(codes)} codes found")
    except Exception as e:
        await message.reply("❌ خطا در نمایش لیست. لاگ‌ها را چک کنید.")
        logger.error(f"Error in change_list: {e}")

@Client.on_callback_query(filters.regex(r"delete_used_codes"))
async def delete_used_codes_handler(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger.info(f"delete_used_codes called by user {user_id}")
    try:
        collection = database.db["VIPCodes"]
        # حذف کده‌های used=True
        result = await collection.delete_many({"used": True})
        deleted_count = result.deleted_count

        # بروزرسانی لیست
        codes = await collection.find({}).sort("code").to_list(length=None)

        text = "📋 **لیست کدهای VIP:**\n\n"
        if not codes:
            text += "کدی وجود ندارد."
        else:
            for code_doc in codes:
                code = code_doc.get("code", "N/A")
                used = code_doc.get("used", False)
                if used:
                    used_by = str(code_doc.get("used_by", "نامشخص"))
                    text += f"{code} - ✅ > {used_by}\n"
                else:
                    text += f"{code} - ❌\n"

        # دکمه حذف رو نگه دار (برای بروزرسانی‌های بعدی)
        keyboard = [[InlineKeyboardButton("🗑️ حذف کدهای استفاده شده", callback_data="delete_used_codes")]]

        await callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Deleted {deleted_count} used codes for user {user_id}")
    except Exception as e:
        await callback_query.answer("❌ خطا در حذف. لاگ‌ها را چک کنید.", show_alert=True)
        logger.error(f"Error in delete_used_codes: {e}")

