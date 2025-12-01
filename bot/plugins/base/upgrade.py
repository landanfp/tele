# bot/handlers/upgrade.py

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.private & filters.command(["upgrade"]))
async def upgrade_handler(client: Client, message):
    text = """**پلن رایگان**  
 ✓ نامحدود رایگان
 ✓ میزان استفاده روزانه : 2 لینک + 2 شانس
 ✓ فاصله زمانی بین فایل‌ها: 30 ثانیه
 قیمت : رایگان

**پلن‌های ۱ روزه**
۵ کلیک  → ۵,۰۰۰ تومان  
۱۰ کلیک → ۱۰,۰۰۰ تومان  
۲۰ کلیک → ۲۰,۰۰۰ تومان

**پلن‌های ۷ روزه**
۵ کلیک  → ۲۰,۰۰۰ تومان  
۱۰ کلیک → ۲۵,۰۰۰ تومان  
۱۵ کلیک → ۳۰,۰۰۰ تومان  
۲۰ کلیک → ۴۰,۰۰۰ تومان

**پلن‌های ۳۰ روزه**
۵ کلیک  → ۴۰,۰۰۰ تومان  
۱۰ کلیک → ۶۵,۰۰۰ تومان  
۱۵ کلیک → ۸۰,۰۰۰ تومان  
۲۰ کلیک → ۱۰۰,۰۰۰ تومان

در پلن‌های پولی محدودیت زمانی بین فایل‌ها وجود ندارد.

برای خرید و ارتقا پلن با پشتیبانی تماس بگیرید"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ارتقا پلن و خرید", url="https://t.me/dgg")]
    ])

    await message.reply(text, reply_markup=keyboard, disable_web_page_preview=True)
