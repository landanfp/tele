# bot/main.py file :
# bot/main.py file :
# farshidband
import asyncio
import logging
import sys
import threading

from pyrogram.client import Client
from pyrogram.errors import ChannelInvalid, ChatAdminRequired
from pyrogram.sync import idle
from rich.logging import RichHandler
from rich.traceback import install

from bot.config import config
from bot.options import options
from bot.database import MongoDB  # فیکس: import مستقیم database برای لود admins
from bot.utilities.helpers import NoInviteLinkError, PyroHelper, RateLimiter
from bot.utilities.http_server import HTTPServer
from bot.utilities.schedule_manager import schedule_manager

install(show_locals=True)

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)

try:
    import uvloop  # type: ignore[reportMissingImports]

    uvloop.install()
    logging.info("Using UVLoop for enhanced performance")
except ImportError:
    logging.warning("UVLoop not installed. Falling back to asyncio")

background_tasks = set()

# فیکس: تعریف ADMIN global در main (برای جلوگیری از cyclic import)
ADMIN = list(config.ROOT_ADMINS_ID)  # اولیه از config

async def load_admins_from_db():  # فیکس: تابع محلی async برای لود admins
    """Load admins from DB and update global ADMIN."""
    global ADMIN
    database = MongoDB()
    admins_doc = await database.db["BotSettings"].find_one({"_id": "Admins"}, {"admins": 1})
    if admins_doc and "admins" in admins_doc:
        ADMIN = list(admins_doc["admins"])
    else:
        ADMIN = list(config.ROOT_ADMINS_ID)  # fallback به config
    logging.info(f"Loaded ADMIN list from DB: {ADMIN}")
    config.sync_admins(ADMIN)  # sync با config

async def load_channels_from_db():  # جدید: تابع محلی async برای لود channels
    """Load channels from DB and update config.FORCE_SUB_CHANNELS."""
    database = MongoDB()
    
    # Save original env value before loading from DB
    env_channels = config.FORCE_SUB_CHANNELS.copy()
    
    channels_doc = await database.db["BotSettings"].find_one({"_id": "Channels"}, {"channels": 1})
    if channels_doc and "channels" in channels_doc:
        config.FORCE_SUB_CHANNELS = list(channels_doc["channels"])
    else:
        # fallback به config (که از env می‌آد)
        pass
    
    # If env was empty but DB had values, sync DB to empty (clear DB)
    if len(env_channels) == 0 and len(config.FORCE_SUB_CHANNELS) > 0:
        config.FORCE_SUB_CHANNELS = []
        await database.db["BotSettings"].update_one(
            {"_id": "Channels"},
            {"$set": {"channels": []}},
            upsert=True
        )
        logging.info("Synced empty env to DB: Cleared FORCE_SUB_CHANNELS in DB")
    
    logging.info(f"Loaded FORCE_SUB_CHANNELS from DB: {config.FORCE_SUB_CHANNELS}")

async def main() -> None:
    bot_client = Client(
        name=config.BOT_SESSION,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workers=config.BOT_WORKER,
        plugins={"root": f"{__package__}/plugins" if __package__ else "plugins"},
        max_message_cache_size=config.BOT_MAX_MESSAGE_CACHE_SIZE,
    )

    # Load database settings
    await options.load_settings()
    await load_admins_from_db()  # فیکس: لود admins محلی بدون import از set
    await load_channels_from_db()  # جدید: لود channels

    await bot_client.start()
    # Bot setup

    try:
        channels_n_invite = await PyroHelper.get_channel_invites(
            client=bot_client,
            channels=config.FORCE_SUB_CHANNELS,
        )
        config.channels_n_invite = channels_n_invite
    except (ChannelInvalid, ChatAdminRequired, NoInviteLinkError) as e:
        sys.exit(f"Please add and give me permission in FORCE_SUB_CHANNELS and BACKUP_CHANNEL:\n{e}")

    await schedule_manager.start()

    task = None
    if config.HTTP_SERVER:
        http_server = HTTPServer(host=config.HOSTNAME, port=config.PORT)
        task = asyncio.create_task(http_server.run_server())
        background_tasks.add(task)
    if config.RATE_LIMITER:
        thread = threading.Thread(target=RateLimiter.cooldown_limiter)
        thread.daemon = True
        thread.start()

    await idle()

    if task:
        task.add_done_callback(background_tasks.discard)

    await bot_client.stop()


asyncio.run(main())
