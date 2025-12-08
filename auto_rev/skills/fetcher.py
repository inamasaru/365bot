from __future__ import annotations

import datetime as dt
import decimal
import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

import requests

logger = logging.getLogger(__name__)


@dataclass
class SaleRecord:
    id: str
    occurred_at: dt.datetime  # tz-aware
    product_name: str
    amount: decimal.Decimal
    commission: decimal.Decimal
    raw: dict[str, Any] | None = None


class SalesSourceClient(Protocol):
    def fetch_sales(self, start: dt.datetime, end: dt.datetime) -> list[SaleRecord]:
        ...


class HttpJsonSalesSourceClient:
    """
    HTTP client for fetching sales from a JSON API.

    Expected response schema (JSON array of objects):
    [
        {
            "id": "unique-id",
            "occurred_at": "2024-01-01T12:34:56+09:00",  # ISO8601 string with timezone
            "product_name": "Product Name",
            "amount": 12345,      # number
            "commission": 6789    # number
        },
        ...
    ]
    """

    def __init__(self, base_url: str, api_key: str, timeout_sec: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    @classmethod
    def from_env(cls) -> "HttpJsonSalesSourceClient":
        base_url = os.getenv("AFFILIATE_API_BASE_URL")
        api_key = os.getenv("AFFILIATE_API_KEY")
        if not base_url or not api_key:
            raise RuntimeError("AFFILIATE_API_BASE_URL and AFFILIATE_API_KEY are required")
        return cls(base_url=base_url, api_key=api_key)

    def fetch_sales(self, start: dt.datetime, end: dt.datetime) -> list[SaleRecord]:
        params = {
            "from": start.isoformat(),
            "to": end.isoformat(),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        url = f"{self.base_url}/sales"
        logger.info("Fetching sales from %s to %s", params["from"], params["to"])
        response = requests.get(url, params=params, headers=headers, timeout=self.timeout_sec)
        if response.status_code != 200:
            logger.error("Failed to fetch sales: status=%s body=%s", response.status_code, response.text)
            response.raise_for_status()

        data = response.json()
        sales: list[SaleRecord] = []
        for item in data:
            occurred_at = dt.datetime.fromisoformat(item["occurred_at"])
            sales.append(
                SaleRecord(
                    id=str(item["id"]),
                    occurred_at=occurred_at,
                    product_name=str(item.get("product_name", "")),
                    amount=decimal.Decimal(str(item.get("amount", "0"))),
                    commission=decimal.Decimal(str(item.get("commission", "0"))),
                    raw=item,
                )
            )
        logger.info("Fetched %d sales", len(sales))
        return sales
