from __future__ import annotations

from dataclasses import dataclass
import os


__all__ = ["Settings"]


def _require_env(name: str, default: str | None = None) -> str:
    """Fetch a required environment variable.

    Empty strings are treated as missing. If ``default`` is provided, it is
    returned when the variable is not set.
    """

    value = os.getenv(name)
    if value is None or value.strip() == "":
        if default is not None:
            return default
        raise RuntimeError(f"Environment variable {name} is required and must be non-empty.")
    return value


@dataclass
class Settings:
    affiliate_api_base_url: str
    affiliate_api_key: str
    notion_api_key: str
    notion_data_source_id: str
    line_channel_access_token: str
    line_to_user_id: str
    timezone: str
    openai_api_key: str
    openai_model: str
    notion_campaign_data_source_id: str
    x_bearer_token: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            affiliate_api_base_url=_require_env("AFFILIATE_API_BASE_URL"),
            affiliate_api_key=_require_env("AFFILIATE_API_KEY"),
            notion_api_key=_require_env("NOTION_API_KEY"),
            notion_data_source_id=_require_env("NOTION_DATA_SOURCE_ID"),
            line_channel_access_token=_require_env("LINE_CHANNEL_ACCESS_TOKEN"),
            line_to_user_id=_require_env("LINE_TO_USER_ID"),
            timezone=_require_env("TIMEZONE"),
            openai_api_key=_require_env("OPENAI_API_KEY"),
            openai_model=_require_env("OPENAI_MODEL", default="gpt-5.1-mini"),
            notion_campaign_data_source_id=_require_env("NOTION_CAMPAIGN_DATA_SOURCE_ID"),
            x_bearer_token=_require_env("X_BEARER_TOKEN"),
        )
