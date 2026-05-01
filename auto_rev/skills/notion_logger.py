from __future__ import annotations

import datetime as dt
import logging
import requests

from auto_rev.skills.fetcher import SaleRecord

logger = logging.getLogger(__name__)


class NotionLogger:
    def __init__(self, api_key: str, database_id: str, api_base: str = "https://api.notion.com/v1"):
        self.api_key = api_key
        self.database_id = database_id
        self.api_base = api_base.rstrip("/")

    def _build_page_payload(self, sale: SaleRecord) -> dict:
        occurred_date = sale.occurred_at.date().isoformat()
        return {
            "parent": {
                "type": "database_id",
                "database_id": self.database_id,
            },
            "properties": {
                "Name": {
                    "title": [
                        {"text": {"content": sale.product_name or sale.id}}
                    ]
                },
                "Amount": {"number": float(sale.amount)},
                "Commission": {"number": float(sale.commission)},
                "Occurred": {"date": {"start": occurred_date}},
            },
        }

    def create_page_for_sale(self, sale: SaleRecord) -> str:
        payload = self._build_page_payload(sale)
        url = f"{self.api_base}/pages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        logger.info("Creating Notion page for sale %s", sale.id)
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(
                "Failed to create Notion page: status=%s body=%s", response.status_code, response.text
            )
            response.raise_for_status()
        page_id = response.json().get("id", "")
        logger.info("Created Notion page %s for sale %s", page_id, sale.id)
        return page_id

    def create_pages_for_sales(self, sales: list[SaleRecord]) -> list[str]:
        page_ids: list[str] = []
        for sale in sales:
            page_ids.append(self.create_page_for_sale(sale))
        return page_ids
