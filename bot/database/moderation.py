# bot/database/moderation.py file :
from async_lru import alru_cache
from motor.motor_asyncio import AsyncIOMotorDatabase


class Moderation:
    db: AsyncIOMotorDatabase

    async def ban_user(self, user_id: int) -> bool:
        """
        Bans a user in the database.
        If user does not exist, creates and bans them.

        Parameters:
            user_id (int): The ID of the user to ban.

        Returns:
            bool: Whether the operation was successful.
        """
        collection = self.db["Users"]
        result = await collection.update_one(
            filter={"_id": user_id},
            update={"$set": {"_id": user_id, "banned": True}},
            upsert=True,  # <-- **تغییر اصلی**
        )

        return result.acknowledged  # <-- **تغییر برای گزارش صحیح**

    async def unban_user(self, user_id: int) -> bool:
        """
        Unbans a user in the database.

        Parameters:
            user_id (int): The ID of the user to unban.

        Returns:
            bool: Whether the user was successfully unbanned.
        """
        collection = self.db["Users"]
        result = await collection.update_one(
            filter={"_id": user_id},
            update={"$set": {"_id": user_id, "banned": False}},
            upsert=False,  # <-- این باید False بماند، چون کاربری که وجود ندارد را نباید آنبن کنیم
        )
        return bool(result.matched_count)

    @alru_cache(maxsize=69, ttl=15)
    async def is_user_banned(self, user_id: int) -> bool:
        """
        Checks if a user is banned in the database.

        Parameters:
            user_id (int): The ID of the user to check.

        Returns:
            bool: True if the user is banned, False otherwise.
        """
        collection = self.db["Users"]
        user = await collection.find_one({"_id": user_id}, {"_id": 0, "banned": 1})

        return user.get("banned", False) if user else False

async def get_banned_users(self) -> list[dict]:
        """
        Retrieves all banned users from the database.

        Returns:
            list[dict]: List of banned user documents with 'id' key.
        """
        collection = self.db["Users"]
        try:
            cursor = collection.find({"banned": True}, {"_id": 1})
            docs = await cursor.to_list(length=None)
            # Map _id to id برای سازگاری با handler
            result = [{"id": doc["_id"]} for doc in docs]
            logger.info(f"Queried {len(result)} banned users from DB")
            return result
        except Exception as e:
            logger.error(f"DB query error in get_banned_users: {e}")
            return []
