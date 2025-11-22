# bot/plugins/base/add_change.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.database import MongoDB
from bot.utilities.pyrofilters import PyroFilters
from bot.utilities.pyrotools import HelpCmd

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
    else:
        await message.reply("❌ خطا در اضافه کردن کد. دوباره امتحان کنید.")

@Client.on_message(filters.private & PyroFilters.admin() & filters.command("change_list"))
async def change_list_handler(client: Client, message: Message):
    collection = database.db["VIPCodes"]
    codes = await collection.find({}).to_list(length=None)

    if not codes:
        await message.reply("📝 لیست کدهای VIP خالی است.")
        return

    # فرمت جدول Markdown
    table = "| کد VIP | وضعیت | استفاده‌شده توسط | تاریخ استفاده |\n|--------|--------|-------------------|---------------|\n"
    for code_doc in codes:
        code = code_doc.get("code", "N/A")
        used = "✅ استفاده شده" if code_doc.get("used", False) else "❌ موجود"
        used_by = str(code_doc.get("used_by", "هیچکس")) if code_doc.get("used", False) else "-"
        used_at = code_doc.get("used_at", "-")
        table += f"| `{code}` | {used} | {used_by} | {used_at} |\n"

    await message.reply(f"📋 **لیست کدهای VIP:**\n\n{table}", parse_mode="Markdown")

HelpCmd.set_help(
    command="add_change",
    description="اضافه کردن کد VIP جدید به لیست: /add_change {code}",
    allow_global=False,
    allow_non_admin=False,
)

HelpCmd.set_help(
    command="change_list",
    description="نمایش لیست کدهای VIP (وضعیت استفاده)",
    allow_global=False,
    allow_non_admin=False,
)
