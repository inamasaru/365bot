from __future__ import annotations

import logging
from typing import Iterable

import requests

logger = logging.getLogger(__name__)


class LineNotifier:
    def __init__(self, channel_access_token: str, to_user_id: str) -> None:
        self.channel_access_token = channel_access_token
        self.to_user_id = to_user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def notify(self, messages: Iterable[str]) -> None:
        messages_list = [m for m in messages if m]
        if not messages_list:
            logger.info("No LINE messages to send; skipping notification.")
            return

        payload = {
            "to": self.to_user_id,
            "messages": [{"type": "text", "text": msg} for msg in messages_list],
        }
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 300:
            logger.error("Failed to send LINE notification: status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
