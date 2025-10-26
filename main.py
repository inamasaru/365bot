#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime


def load_config() -> dict:
    """Load configuration from environment variables."""
    return {
        "LINE_USER_IDS": os.getenv("LINE_USER_ID", ""),
    }


def send_line_message(user_id: str, message: str) -> None:
    """Placeholder for sending a message via the LINE API."""
    # In production, integrate with the LINE Messaging API here.
    logging.info(f"Sending message to {user_id}: {message}")


def compute_kpi() -> str:
    """Compute a simple KPI message with a timestamp."""
    now = datetime.now()
    return f"[{now.strftime('%Y-%m-%d %H:%M')}] KPI report generated."


def main() -> None:
    """Main entry point for scheduled tasks."""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    config = load_config()
    kpi_message = compute_kpi()
    user_ids = [uid.strip() for uid in config.get("LINE_USER_IDS", "").split(",") if uid.strip()]
    for uid in user_ids:
        try:
            send_line_message(uid, kpi_message)
        except Exception as e:
            logging.error(f"Failed to send KPI notification to {uid}: {e}")


if __name__ == "__main__":
    main()
