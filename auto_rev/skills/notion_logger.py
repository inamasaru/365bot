from __future__ import annotations

import logging
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"


class NotionLogger:
    def __init__(self, api_key: str, data_source_id: str) -> None:
        self.api_key = api_key
        self.data_source_id = data_source_id

    def log_sales(self, sales_payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://api.notion.com/v1/data_sources/{self.data_source_id}/ingest"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=sales_payload, timeout=30)
        if response.status_code >= 300:
            logger.error("Failed to log sales to Notion: status=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
        return response.json()
