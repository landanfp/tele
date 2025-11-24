# bot/utilities/pyrofilters/admins.py file :
# ruff: noqa: ARG001

from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config
from bot.plugins.base.set import ADMIN  # تغییر: import ADMIN global
from bot.options import options


class AdminsFilter:
    @staticmethod
    def admin(
        allow_global: bool = False,  # noqa: FBT001, FBT002
    ) -> filters.Filter:
        async def func(flt: None, client: Client, message: Message) -> bool:
            user_id = message.from_user.id
            global_mode = options.settings.GLOBAL_MODE
            return user_id in ADMIN or (global_mode and allow_global)  # تغییر: ADMIN به جای config.ROOT_ADMINS_ID

        return filters.create(func, "AdminFilter")
