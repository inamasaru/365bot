from __future__ import annotations

import logging
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


class AffiliateFetcher:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def fetch_daily_sales(self) -> Dict[str, Any]:
        url = f"{self.base_url}/sales/daily"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code >= 300:
            logger.error("Failed to fetch daily sales: status=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
        return response.json()
