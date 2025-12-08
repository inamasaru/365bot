from __future__ import annotations

import logging
from typing import Any

from auto_rev.config.settings import Settings
from auto_rev.skills.fetcher import AffiliateFetcher
from auto_rev.skills.line_notifier import LineNotifier
from auto_rev.skills.notion_logger import NotionLogger
from auto_rev.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    configure_logging()
    settings = Settings.from_env()

    fetcher = AffiliateFetcher(settings.affiliate_api_base_url, settings.affiliate_api_key)
    notion = NotionLogger(settings.notion_api_key, settings.notion_data_source_id)
    notifier = LineNotifier(settings.line_channel_access_token, settings.line_to_user_id)

    logger.info("Fetching daily affiliate sales data...")
    sales_data: Any = fetcher.fetch_daily_sales()

    logger.info("Sending sales data to Notion...")
    notion_response = notion.log_sales(sales_data if isinstance(sales_data, dict) else {"data": sales_data})

    notifier.notify(["日次アフィリエイト売上をNotionに送信しました。", f"レスポンス: {notion_response}"])


def main() -> None:
    try:
        run()
    except Exception:
        logger.exception("Daily affiliate report failed")
        raise


if __name__ == "__main__":
    main()
