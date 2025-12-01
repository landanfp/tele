# bot/handlers/upgrade.py

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.private & filters.command("upgrade"))
async def upgrade_handler(client: Client, message):
    text = """**⭕️ پلن رایگان 🎁 | مشخصات پلن رایگان 🎉
 ✓ نامحدود رایگان
 ✓ میزان استفاده روزانه : 2 لینک + 2شانس
 ✓ فاصله زمانی بین فایل ها 30ثانیه میباشد.
 💰قیمت : 0 / رایگان 

🟢 پلن های 1روزه :
🔖 5 تا کلیک برای دریافت-فایل ‌== 5,000 ت
🔖 10 تا کلیک برای  دریافت-فایل  == 10,000ت
🔖 15 تا کلیک برای دریافت-فایل == 15,000
✓ فاصله زمانی بین فایل ها ندارد.

🟢 پلن های 7روزه :
🔖 5 تا کلیک برای دریافت-فایل == 20,000ت
🔖 10 تا کلیک برای دریافت-فایل == 25,000ت
🔖 15 تا کلیک برای دریافت-فایل == 30,000ت
🔖 20 تا کلیک برای دریافت-فایل == 40,000ت
✓ فاصله زمانی بین فایل ها ندارد.

🟢 پلن های 30روزه :
🔖 5 تا کلیک برای دریافت-فایل == 40,000ت
🔖 10 تا کلیک برای دریافت-فایل == 65,000ت
🔖 15 تا کلیک برای دریافت-فایل == 80,000ت
🔖 20 تا کلیک برای دریافت-فایل == 100,000ت
✓ فاصله زمانی بین فایل ها ندارد.**"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ارتقا پلن و خرید", url="https://t.me/dgg")]
    ])

    await message.reply(text, reply_markup=keyboard, disable_web_page_preview=True)
