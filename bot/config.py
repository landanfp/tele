# bot/config.py file : 
# © @FarshidBand 
"""General configuration.

Config: Bot Config
"""

# ruff: noqa: ARG003
import logging
import sys
import os
from pathlib import Path
from typing import Annotated

from pydantic import ValidationError, field_validator
from pydantic.networks import UrlConstraints
from pydantic_core import MultiHostUrl
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources import SettingsError
from typing_extensions import TypedDict

MongoSRVDsn = Annotated[MultiHostUrl, UrlConstraints(allowed_schemes=["mongodb+srv"])]
BASE_PATH = Path(__file__).parent.parent

DAILY_LINK_LIMITS = {
    "free": 2,  # 2 clicks per day, no expiry
    "daily_5": 5,  # 5 clicks per day, 1 day expiry
    "daily_10": 10,
    "daily_20": 20,
    "weekly_5": 5,  # 5 clicks per day, 7 days expiry
    "weekly_10": 10,
    "weekly_15": 15,
    "weekly_20": 20,
    "monthly_5": 5,  # 5 clicks per day, 30 days expiry
    "monthly_10": 10,
    "monthly_15": 15,
    "monthly_20": 20,
    "vip_15days": 10,  # 10 clicks per day, 15 days expiry (VIP special)
    "gift_7days": 5,  # 5 clicks per day, 7 days expiry (Gift plan)
}

class ChannelInfo(TypedDict):
    is_private: bool
    invite_link: str
    channel_id: int


class Config(BaseSettings):
    """A general configuration setup to read either .env or environment keys."""

    # Bot deploy config
    PORT: int = 8080
    HOSTNAME: str = "0.0.0.0"  # noqa: S104
    HTTP_SERVER: bool = True

    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    BOT_WORKER: int = 8
    BOT_SESSION: str = "Zaws-File-Share"
    BOT_MAX_MESSAGE_CACHE_SIZE: int = 100

    MONGO_DB_URL: MongoSRVDsn
    MONGO_DB_NAME: str = "Zaws-File-Share"

    # Bot main config
    RATE_LIMITER: bool = True
    BACKUP_CHANNEL: int
    BACKUP_CHANNEL2: int  # اضافه کردن کانال دوم برای فایل‌های پرمیوم
    ROOT_ADMINS_ID: list[int] = list(int(x) for x in os.environ.get("ROOT_ADMINS_ID", "763990585 705518424").split())  # فیکس: type annotation اضافه شد
    FORCE_SUB_CHANNELS: list[int] = list(int(x) for x in os.environ.get("FORCE_SUB_CHANNELS", "").split()) #-1001208480573

    PRIVATE_REQUEST: bool = False
    PROTECT_CONTENT: bool = True 
    AUTO_GENERATE_LINK: bool = True

    # --- NEW CONFIG ---
    FREE_USER_DELAY: int = 30  # Delay in seconds for free users
# ------------------

    # Injected Config
    channels_n_invite: dict[str, ChannelInfo] = {}

    model_config = SettingsConfigDict(
        env_file=f"{BASE_PATH}/.env",
    )

    # فیکس: متد sync admins
    def sync_admins(self, new_admins: list[int]) -> None:
        """Sync ROOT_ADMINS_ID with updated admins."""
        self.ROOT_ADMINS_ID = new_admins

    @field_validator("ROOT_ADMINS_ID", "FORCE_SUB_CHANNELS", mode="before")
    @classmethod
    def convert_int_to_list(cls, value: int | list[int]) -> list[int]:
        if isinstance(value, int):
            return [value]
        return value

    @field_validator("channels_n_invite", mode="before")
    @classmethod
    def ignore_keys(cls, value: dict[str, ChannelInfo]) -> dict[str, ChannelInfo]:
        return {}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            DotEnvSettingsSource(settings_cls),
            EnvSettingsSource(settings_cls),
        )


try:
    config = Config()  # type: ignore[reportCallIssue]
except (ValidationError, SettingsError):
    logging.exception("Configuration Error")
    sys.exit(1)
