# bot/plugins/base/start.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import config
from bot.database import MongoDB
from bot.options import options
from bot.utilities.helpers import DataEncoder, DataValidationError, PyroHelper, RateLimiter
from bot.utilities.pyrofilters import PyroFilters, SubscriptionMessage
from bot.utilities.pyrotools import FileResolverModel, HelpCmd, Pyrotools
from bot.utilities.schedule_manager import schedule_manager
# from bot.plugins.base.set import ADMIN  # فیکس: حذف import ADMIN برای جلوگیری از cyclic import

database = MongoDB()
# دیکشنری برای ذخیره آخرین زمان ارسال فایل برای کاربران
user_last_sent = {}


class FileSender:
    """Used to manage file sending functions between codexbotz and teleshare."""

    forward_limit_size = 100

    @staticmethod
    async def codexbotz(
        client: Client,
        codex_message_ids: list[int],
        chat_id: int,
        from_chat_id: int,
        protect_content: bool,  # noqa: FBT001
    ) -> list[Message]:
        all_sent_files = []

        if len(codex_message_ids) == 1:
            send_files = await client.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=codex_message_ids[0],
                protect_content=protect_content,
            )

            all_sent_files.append(send_files)

        else:
            codex_message_ids_chunk = [
                codex_message_ids[i : i + FileSender.forward_limit_size]
                for i in range(0, len(codex_message_ids), FileSender.forward_limit_size)
            ]

            for codex_files in codex_message_ids_chunk:
                send_files = await client.forward_messages(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_ids=codex_files,
                    hide_sender_name=True,
                    protect_content=protect_content,
                )
                all_sent_files.extend(send_files) if isinstance(send_files, list) else all_sent_files.append(send_files)

        return all_sent_files

    @staticmethod
    async def teleshare(
        client: Client,
        chat_id: int,
        file_data: list[FileResolverModel],
        file_origin: int,
        protect_content: bool,  # noqa: FBT001
    ) -> list[Message]:
        all_sent_files = []

        if len(file_data) == 1:
            send_files = await Pyrotools.send_media(
                client=client,
                chat_id=chat_id,
                file_data=file_data[0],
                file_origin=file_origin,
                protect_content=protect_content,
            )
            all_sent_files.append(send_files)
        else:
            file_data_chunk = [
                file_data[i : i + FileSender.forward_limit_size]
                for i in range(0, len(file_data), FileSender.forward_limit_size)
            ]

            for i_file_data in file_data_chunk:
                send_files = await Pyrotools.send_media_manager(
                    client=client,
                    chat_id=chat_id,
                    file_data=i_file_data,
                    file_origin=file_origin,
                    protect_content=protect_content,
                )
                all_sent_files.extend(send_files) if isinstance(send_files, list) else all_sent_files.append(send_files)
        return all_sent_files


@Client.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_callback(client: Client, callback: CallbackQuery):
    """
    هندلر بررسی عضویت برای دکمه شیشه‌ای (مخصوص استارت خالی).
    اگر کاربر عضو شده باشد، پیام قفل را حذف کرده و پیام استارت را می‌فرستد.
    """
    user_id = callback.from_user.id
    status = [
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    ]
    
    is_subscribed = True
    
    # بررسی ادمین نبودن (ادمین‌ها همیشه مجازند)
    if user_id not in config.ROOT_ADMINS_ID:  # فیکس: استفاده از config.ROOT_ADMINS_ID به جای ADMIN
        if await database.is_user_banned(user_id):
             await callback.answer("🚫 شما از استفاده از ربات محروم هستید.", show_alert=True)
             return

        if config.FORCE_SUB_CHANNELS:
            try:
                joined_request_channel = await database.user_requested_channels(user_id)

                for channel_info in config.channels_n_invite.values():
                    channel_is_private = channel_info["is_private"]
                    channel_id = channel_info["channel_id"]

                    if channel_is_private and channel_id not in joined_request_channel:
                        is_subscribed = False
                        break

                    if not channel_is_private:
                        try:
                            member = await client.get_chat_member(chat_id=channel_id, user_id=user_id)
                            if member.status not in status:
                                is_subscribed = False
                                break
                        except UserNotParticipant:
                            is_subscribed = False
                            break
            except Exception:
                 # در صورت بروز خطا فرض را بر عدم عضویت می‌گذاریم
                 is_subscribed = False

    if is_subscribed:
        # 1. حذف پیام جوین اجباری
        await callback.message.delete()
        
        # 2. ارسال پیام استارت (خوش‌آمدگویی)
        await PyroHelper.option_message(
            client=client,
            message=callback.message, # استفاده از کانتکست پیام قبلی
            option_key=options.settings.START_MESSAGE
        )
    else:
        await callback.answer("❌ هنوز در کانال‌های مورد نظر عضو نشده‌اید!", show_alert=True)


@Client.on_message(
    filters.command("start") & filters.private & PyroFilters.subscription(),
    group=0,
)
@RateLimiter.hybrid_limiter(func_count=1)
async def file_start(
    client: Client,
    message: Message,
) -> Message:
    """
    Handle start command, it returns files if a link is included otherwise sends the user a request.

    **Usage:**
        /start [optional file_link]
    """
    if not message.command[1:]:
        await PyroHelper.option_message(client=client, message=message, option_key=options.settings.START_MESSAGE)
        return message.stop_propagation()

    # shouldn't overwrite existing id it already exists
    await database.add_user(user_id=message.from_user.id)
    # --- بخش جدید: اعمال تاخیر برای کاربران رایگان ---
    plan = await database.get_user_plan(user_id)
    if plan == "free":
        last_sent = user_last_sent.get(user_id, 0)
        current_time = asyncio.get_event_loop().time()
        delay = config.FREE_USER_DELAY

        if delay > 0:
            # بررسی اختلاف زمانی
            if current_time - last_sent < delay:
                remaining_time = int(delay - (current_time - last_sent))
                await message.reply_text(
                    f"⏱️ **{remaining_time}** ثانیه دیگر می‌توانید فایل جدیدی دریافت کنید.",
                    quote=True
                )
                return message.stop_propagation()

        # اگر زمان سپری شده بود، تایمر را آپدیت می‌کنیم (قبل از پردازش سنگین)
        user_last_sent[user_id] = current_time
    # ----------------------------------------------------

    base64_file_link = message.text.split(maxsplit=1)[1]
    file_document = await database.get_link_document(base64_file_link=base64_file_link)

    user_id = message.from_user.id

    # چک محدودیت کلیک روزانه قبل از ارسال
    daily_clicks = await database.get_daily_clicks(user_id)
    daily_limit = await database.get_daily_limit(user_id)
    if daily_clicks >= daily_limit:
        await message.reply(
            f"⚠️ محدودیت روزانه شما ({daily_limit} کلیک) تمام شده. فردا دوباره امتحان کنید.\n\nوضعیت پلن: /myplan",
            quote=True
        )
        return message.stop_propagation()

    if not file_document:
        try:
            codex_message_ids = DataEncoder.codex_decode(
                base64_string=base64_file_link,
                backup_channel=config.BACKUP_CHANNEL,
            )
        except (DataValidationError, IndexError):
            await PyroHelper.option_message(
                client=client,
                message=message,
                option_key=options.settings.INVALID_LINK_MESSAGE,
            )
            return message.stop_propagation()

        send_files = await FileSender.codexbotz(
            client=client,
            codex_message_ids=codex_message_ids,
            chat_id=message.chat.id,
            from_chat_id=config.BACKUP_CHANNEL,
            protect_content=config.PROTECT_CONTENT,
        )
        if not send_files:
            await PyroHelper.option_message(
                client=client,
                message=message,
                option_key=options.settings.FILE_DOES_NOT_EXIST,
            )
            return message.stop_propagation()
    else:
        file_origin = file_document["file_origin"]
        file_data = [FileResolverModel(**file) for file in file_document["files"]]

        send_files = await FileSender.teleshare(
            client=client,
            chat_id=message.chat.id,
            file_data=file_data,
            file_origin=file_origin,
            protect_content=config.PROTECT_CONTENT,
        )

    # افزایش تعداد کلیک/دانلود فقط بعد از ارسال موفق
    await database.increase_daily_clicks(user_id)

    delete_n_seconds = options.settings.AUTO_DELETE_SECONDS

    additional_message = None
    if options.settings.ADDITIONAL_MESSAGE != 0:
        additional_message = await PyroHelper.option_message(
            client=client,
            message=message,
            option_key=options.settings.ADDITIONAL_MESSAGE,
        )

    if delete_n_seconds != 0:
        schedule_delete_message = [msg.id for msg in send_files]

        auto_delete_message = (
            options.settings.AUTO_DELETE_MESSAGE.format(int(delete_n_seconds / 60))
            if not isinstance(options.settings.AUTO_DELETE_MESSAGE, int)
            else options.settings.AUTO_DELETE_MESSAGE
        )
        auto_delete_message_reply = await PyroHelper.option_message(
            client=client,
            message=message,
            option_key=auto_delete_message,
        )
        schedule_delete_message.append(auto_delete_message_reply.id)

        if additional_message:
            schedule_delete_message.append(additional_message.id)

        await schedule_manager.schedule_delete(
            client=client,
            chat_id=message.chat.id,
            message_ids=schedule_delete_message,
            delete_n_seconds=delete_n_seconds,
        )

    return message.stop_propagation()


@Client.on_message(filters.command("start") & filters.private, group=69)
@RateLimiter.hybrid_limiter(func_count=1)
async def return_start(
    client: Client,
    message: SubscriptionMessage,
) -> Message | None:
    """
    Handle start command without files or not subscribed.
    """

    if hasattr(message, "user_is_banned") and message.user_is_banned:
        return await PyroHelper.option_message(
            client=client,
            message=message,
            option_key=options.settings.BANNED_USER_MESSAGE,
        )

    channels_n_invite = config.channels_n_invite
    buttons = []

    for channel, channel_info in channels_n_invite.items():
        buttons.append([InlineKeyboardButton(text=channel, url=channel_info["invite_link"])])

    # --- بخش اصلاح شده ---
    start_arg = message.command[1] if len(message.command) > 1 else ""
    
    if start_arg:
        # اگر لینک فایل باشد، دکمه باید لینک باشد تا کاربر فایل را بگیرد
        link = f"https://t.me/{client.me.username}?start={start_arg}"  # type: ignore[reportOptionalMemberAccess]
        buttons.append([InlineKeyboardButton(text="✅ عضو شدم - دریافت فایل", url=link)])
    else:
        # اگر استارت خالی باشد، دکمه Callback می‌سازیم تا پیام قبلی را حذف کند
        buttons.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_sub")])
    # ---------------------

    return await PyroHelper.option_message(
        client=client,
        message=message,
        option_key=options.settings.FORCE_SUB_MESSAGE,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


HelpCmd.set_help(
    command="start",
    description=file_start.__doc__,
    allow_global=True,
    allow_non_admin=True,
)
