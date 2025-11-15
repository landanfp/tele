# bot/utilities/pyrofilters/admin.py file :
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from bot.config import config


class AdminsFilter:
    """A filter to check if a user is an admin."""

    @classmethod
    def admin(cls) -> filters.Filter:
        """
        Creates a filter to check if a user is an admin.

        Returns:
            filters.Filter: A filter to check if a user is an admin.
        """

        async def func(flt: None, client: Client, message: Message) -> bool:  # noqa: ARG001
            """
            Checks if a user is an admin.

            Parameters:
                client (Client): The Pyrogram client.
                message (Message): The message to check.

            Returns:
                bool: True if the user is an admin, False otherwise.
            """
            user_id = message.from_user.id

            if user_id in config.ROOT_ADMINS_ID:
                return True
            
            # --- این بخش اصلاح شد تا دیگر پیام خطا ندهد ---
            return False 
            # --- پایان اصلاح ---


        return filters.create(func, "AdminFilter")
