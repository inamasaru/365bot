from __future__ import annotations

import decimal
import logging
from collections import Counter
from typing import List

import requests

from auto_rev.skills.fetcher import SaleRecord

logger = logging.getLogger(__name__)


class LineNotifier:
    def __init__(self, channel_access_token: str, to: str):
        self.channel_access_token = channel_access_token
        self.to = to

    def _build_summary_text(self, sales: List[SaleRecord]) -> str:
        total_amount = sum((sale.amount for sale in sales), decimal.Decimal("0"))
        total_commission = sum((sale.commission for sale in sales), decimal.Decimal("0"))
        product_counts = Counter(sale.product_name for sale in sales if sale.product_name)
        top_products = ", ".join(name for name, _ in product_counts.most_common(3))
        occurred_dates = sorted({sale.occurred_at.date() for sale in sales})
        date_range = (
            occurred_dates[0].isoformat()
            if len(occurred_dates) == 1
            else f"{occurred_dates[0].isoformat()}〜{occurred_dates[-1].isoformat()}"
        )
        message = (
            f"売上サマリ ({date_range})\n"
            f"件数: {len(sales)}件\n"
            f"売上合計: {total_amount}円\n"
            f"報酬合計: {total_commission}円"
        )
        if top_products:
            message += f"\n主な商品: {top_products}"
        # Example body structure for LINE push message:
        # {
        #   "to": "LINE_TO_USER_ID",
        #   "messages": [
        #       {"type": "text", "text": message}
        #   ]
        # }
        return message

    def send_summary(self, sales: list[SaleRecord]) -> None:
        if not sales:
            logger.info("No sales to notify. Skipping LINE notification.")
            return

        message = self._build_summary_text(sales)
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": self.to,
            "messages": [{"type": "text", "text": message}],
        }
        logger.info("Sending LINE notification to %s", self.to)
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(
                "Failed to send LINE notification: status=%s body=%s", response.status_code, response.text
            )
            response.raise_for_status()
        logger.info("LINE notification sent successfully")
