from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from auto_rev.config.settings import Settings
from auto_rev.skills.fetcher import HttpJsonSalesSourceClient
from auto_rev.skills.line_notifier import LineNotifier
from auto_rev.skills.notion_logger import NotionLogger
from auto_rev.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


def _get_yesterday_range(tz: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(tz)
    yesterday = now.date() - dt.timedelta(days=1)
    start = dt.datetime.combine(yesterday, dt.time(0, 0, 0), tzinfo=tz)
    end = dt.datetime.combine(yesterday, dt.time(23, 59, 59), tzinfo=tz)
    return start, end


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    tz = ZoneInfo(settings.timezone)

    start, end = _get_yesterday_range(tz)
    logger.info("Processing sales from %s to %s", start, end)

    client = HttpJsonSalesSourceClient.from_env()
    sales = client.fetch_sales(start, end)

    logger.info("Fetched %d sales", len(sales))
    if not sales:
        logger.info("No sales found for yesterday. Exiting.")
        return

    notion = NotionLogger(settings.notion_api_key, settings.notion_database_id)
    notion.create_pages_for_sales(sales)

    notifier = LineNotifier(settings.line_channel_access_token, settings.line_to_user_id)
    notifier.send_summary(sales)


if __name__ == "__main__":
    main()
