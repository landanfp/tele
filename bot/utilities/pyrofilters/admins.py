# bot/utilities/pyrofilters/admins.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config


class AdminsFilter:
    """A filter to check if a user is an admin."""

    @classmethod
    def admin(cls, **kwargs) -> filters.Filter: # <-- تغییر مهم: اضافه شدن **kwargs
        """
        Creates a filter to check if a user is an admin.

        Returns:
            filters.Filter: A filter to check if a user is an admin.
        """

        async def func(flt: None, client: Client, message: Message) -> bool:  # noqa: ARG001
            """
            Checks if a user is an admin.
            """
            user_id = message.from_user.id

            if user_id in config.ROOT_ADMINS_ID:
                return True
            
            # در اینجا False برگردانده می‌شود تا اجرای دستور متوقف شود
            return False 

        return filters.create(func, "AdminFilter")
