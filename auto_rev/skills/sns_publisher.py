from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class XPostResult:
    id: str
    text: str


class XPublisher:
    def __init__(self, bearer_token: str) -> None:
        self.bearer_token = bearer_token
        self.api_url = "https://api.x.com/2/tweets"

    def post_text(self, text: str) -> Optional[XPostResult]:
        if not text:
            logger.info("No text provided for X post; skipping publish.")
            return None

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 401:
            logger.error("X API returned 401 Unauthorized. Check Bearer Token and tweet.write scope.")
        if resp.status_code >= 300:
            logger.error("X API error: status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()

        data = resp.json()
        try:
            tweet_data = data["data"]
            return XPostResult(id=str(tweet_data["id"]), text=str(tweet_data["text"]))
        except (KeyError, TypeError) as exc:
            logger.error("Unexpected X API response format: %s", data)
            raise RuntimeError("Failed to parse X API response") from exc
