from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


class _EnvLoader:
    @staticmethod
    def require(name: str, default: Optional[str] = None) -> str:
        value = os.getenv(name, default)
        if value is None or value == "":
            raise RuntimeError(f"Environment variable {name} is required")
        return value


@dataclass
class Settings:
    affiliate_api_base_url: str
    affiliate_api_key: str
    notion_api_key: str
    notion_data_source_id: str
    line_channel_access_token: str
    line_to_user_id: str
    timezone: str = "Asia/Tokyo"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            affiliate_api_base_url=_EnvLoader.require("AFFILIATE_API_BASE_URL"),
            affiliate_api_key=_EnvLoader.require("AFFILIATE_API_KEY"),
            notion_api_key=_EnvLoader.require("NOTION_API_KEY"),
            notion_data_source_id=_EnvLoader.require("NOTION_DATA_SOURCE_ID"),
            line_channel_access_token=_EnvLoader.require("LINE_CHANNEL_ACCESS_TOKEN"),
            line_to_user_id=_EnvLoader.require("LINE_TO_USER_ID"),
            timezone=_EnvLoader.require("TIMEZONE", "Asia/Tokyo"),
        )
