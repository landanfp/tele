# ruff: noqa: ARG001

from async_lru import alru_cache
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
import logging
from bot.config import DAILY_LINK_LIMITS

logger = logging.getLogger(__name__)

class Moderation:
    db: AsyncIOMotorDatabase

    async def ban_user(self, user_id: int) -> bool:
        """
        Bans a user in the database.

        Parameters:
            user_id (int): The ID of the user to ban.

        Returns:
            bool: Whether the user was successfully banned.
        """
        collection = self.db["Users"]
        result = await collection.update_one(
            filter={"_id": user_id},
            update={"$set": {"_id": user_id, "banned": True}},
            upsert=False,
        )

        return bool(result.matched_count)

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
            upsert=False,
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

    async def get_user_plan(self, user_id: int):
        """دریافت نام پلن فعلی کاربر."""
        user = await self.db["Users"].find_one({'_id': user_id})
        return user.get("plan", "free") if user else "free"

    async def set_user_plan(self, user_id: int, plan: str, expiry_date: str = None):
        """تنظیم پلن کاربر و محدودیت روزانه."""
        if not await self.is_user_exist(user_id):
            await self.add_user(user_id)
        update_data = {
            'plan': plan,
            'plan_expiry': expiry_date,
            'daily_limit': DAILY_LINK_LIMITS.get(plan, DAILY_LINK_LIMITS.get("free"))
        }
        await self.db["Users"].update_one({'_id': user_id}, {'$set': update_data})

    async def increase_daily_clicks(self, user_id: int):
        """افزایش تعداد کلیک/دانلود روزانه کاربر."""
        await self.check_and_reset_daily_usage(user_id)
        await self.db["Users"].update_one(
            {'_id': user_id},
            {'$inc': {'daily_clicks': 1}}
        )

    async def get_daily_clicks(self, user_id: int):
        """دریافت تعداد کلیک/دانلود روزانه کاربر."""
        await self.check_and_reset_daily_usage(user_id)
        user = await self.db["Users"].find_one({'_id': user_id})
        return user.get("daily_clicks", 0) if user else 0

    async def get_plan_expiry(self, user_id: int):
        """دریافت تاریخ انقضای پلن کاربر."""
        user = await self.db["Users"].find_one({'_id': user_id})
        if user and user.get("plan") != "free":
            return user.get("plan_expiry")
        return None

    async def get_daily_limit(self, user_id: int):
        """دریافت محدودیت کلیک روزانه کاربر."""
        await self.check_and_reset_daily_usage(user_id)
        user = await self.db["Users"].find_one({'_id': user_id})
        if user:
            plan = user.get('plan', 'free')
            return DAILY_LINK_LIMITS.get(plan, DAILY_LINK_LIMITS.get("free", 2))
        return DAILY_LINK_LIMITS.get("free", 2)

    async def update_user_plan2(self, user_id: int, plan: str = "free", daily_limit: int = -1, days: int = 0):
        """به‌روزرسانی پلن کاربر با جزئیات بیشتر."""
        if not await self.is_user_exist(user_id):
            await self.add_user(user_id)
        limit_to_set = daily_limit if daily_limit != -1 else DAILY_LINK_LIMITS.get(plan, DAILY_LINK_LIMITS.get("free"))
        expiry_date_iso = None
        if days > 0:
            expiry_date_iso = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
        update_fields = {
            "plan": plan,
            "daily_limit": limit_to_set,
            "plan_expiry": expiry_date_iso
        }
        result = await self.db["Users"].update_one({"_id": user_id}, {"$set": update_fields})
        return "success" if result.modified_count > 0 else "failed"

    async def update_one(self, user_id: int, update_dict: dict):
        """به‌روزرسانی یک یا چند فیلد خاص برای کاربر."""
        if not await self.is_user_exist(user_id):
            pass
        await self.db["Users"].update_one({"_id": user_id}, {"$set": update_dict})

    async def check_and_reset_daily_usage(self, user_id: int):
        """بررسی و ریست کردن آمار روزانه کاربر."""
        user = await self.db["Users"].find_one({'_id': user_id})
        today_str = str(datetime.date.today())
        await self.check_and_update_expired_plan(user_id)
        if not user:
            await self.add_user(user_id)
            return
        last_reset = user.get('last_reset_date')
        if last_reset != today_str:
            await self.db["Users"].update_one(
                {'_id': user_id},
                {'$set': {
                    'daily_clicks': 0,
                    'last_reset_date': today_str
                }}
            )
            logger.info(f"Daily clicks reset for user {user_id} on {today_str}")

    async def check_and_update_expired_plan(self, user_id: int, client=None):
        """بررسی تاریخ انقضای پلن و تغییر به رایگان در صورت منقضی شدن."""
        user = await self.db["Users"].find_one({'_id': user_id})
        if not user or user.get('plan', 'free') == 'free':
            return False
        expiry_date = user.get('plan_expiry')
        if expiry_date:
            today = datetime.date.today()
            expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
            if today > expiry:
                await self.db["Users"].update_one(
                    {'_id': user_id},
                    {'$set': {
                        'plan': 'free',
                        'plan_expiry': None,
                        'daily_limit': DAILY_LINK_LIMITS.get('free', 2)
                    }}
                )
                logger.info(f"Plan for user {user_id} expired. Changed to free plan.")
                if client:
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text="⚠️ اعتبار پلن شما پایان یافت و پلن رایگان جایگزین آن شد."
                        )
                        logger.info(f"Expiration message sent to user {user_id}")
                    except Exception as e:
                        logger.warning(f"Failed to send expiration message to user {user_id}: {e}")
                return True
        return False

    async def reset_daily_usage(self):
        """ریست آمار روزانه همه کاربران."""
        today_str = str(datetime.date.today())
        result = await self.db["Users"].update_many(
            {},
            {'$set': {
                'daily_clicks': 0,
                'last_reset_date': today_str
            }}
        )
        logger.info(f"[{datetime.datetime.now()}] Global daily clicks reset executed for date: {today_str}. Users modified: {result.modified_count}")

    async def check_all_expired_plans(self, client=None):
        """بررسی و به‌روزرسانی پلن‌های منقضی‌شده همه کاربران."""
        today_str = str(datetime.date.today())
        async for user in self.db["Users"].find({'plan': {'$ne': 'free'}, 'plan_expiry': {'$ne': None}}):
            user_id = user['_id']
            expiry_date = user.get('plan_expiry')
            if expiry_date:
                expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
                if datetime.date.today() > expiry:
                    await self.db["Users"].update_one(
                        {'_id': user_id},
                        {'$set': {
                            'plan': 'free',
                            'plan_expiry': None,
                            'daily_limit': DAILY_LINK_LIMITS.get('free', 2)
                        }}
                    )
                    logger.info(f"Plan for user {user_id} expired. Changed to free plan.")
                    if client:
                        try:
                            await client.send_message(
                                chat_id=user_id,
                                text="⚠️ اعتبار پلن شما پایان یافت و پلن رایگان جایگزین آن شد."
                            )
                            logger.info(f"Expiration message sent to user {user_id}")
                        except Exception as e:
                            logger.warning(f"Failed to send expiration message to user {user_id}: {e}")
        logger.info(f"[{datetime.datetime.now()}] Checked all users for expired plans on {today_str}")

    async def is_user_exist(self, user_id: int) -> bool:
        user = await self.db["Users"].find_one({'_id': user_id})
        return bool(user)

    async def add_user(self, user_id: int) -> bool:
        collection = self.db["Users"]
        result = await collection.update_one(
            filter={"_id": user_id},
            update={"$set": {"_id": user_id}},
            upsert=True,
        )
        return result.acknowledged
