from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import requests

from auto_rev.config.settings import Settings
from auto_rev.skills.content_generator import AffiliateContentGenerator
from auto_rev.skills.sns_publisher import XPublisher
from auto_rev.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)

NOTION_VERSION = "2025-09-03"


def _extract_rich_text_text(prop: Optional[Dict[str, Any]]) -> str:
    if not prop or "rich_text" not in prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("rich_text", []))


def pick_next_campaign(settings: Settings) -> Optional[Dict[str, Any]]:
    url = f"https://api.notion.com/v1/data_sources/{settings.notion_campaign_data_source_id}/query"
    headers = {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "filter": {
            "and": [
                {"property": "Enabled", "checkbox": {"equals": True}},
                {"property": "Platform", "select": {"equals": "X"}},
            ]
        },
        "sorts": [
            {"property": "LastPostedAt", "direction": "ascending"},
            {"timestamp": "created_time", "direction": "ascending"},
        ],
        "page_size": 1,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 300:
        logger.error("Failed to query Notion campaigns: status=%s body=%s", resp.status_code, resp.text)
        resp.raise_for_status()

    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        logger.info("No eligible campaigns found for X posting.")
        return None
    return results[0]


def update_campaign_posted(settings: Settings, page_id: str, posted_at: dt.datetime) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "properties": {
            "LastPostedAt": {
                "date": {
                    "start": posted_at.astimezone(dt.timezone.utc).isoformat()
                }
            }
        }
    }

    resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 300:
        logger.error("Failed to update campaign posted time: status=%s body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
    else:
        logger.info("Updated LastPostedAt for page %s", page_id)


def run() -> None:
    configure_logging()
    settings = Settings.from_env()

    tz = ZoneInfo(settings.timezone)
    now_local = dt.datetime.now(tz)

    campaign = pick_next_campaign(settings)
    if not campaign:
        return

    properties = campaign.get("properties", {}) if isinstance(campaign, dict) else {}

    title_prop = properties.get("Name", {})
    description_prop = properties.get("Description", {})
    url_prop = properties.get("AffiliateUrl", {})

    try:
        title_text = "".join(part.get("plain_text", "") for part in title_prop.get("title", []))
    except AttributeError:
        title_text = ""
    description_text = _extract_rich_text_text(description_prop)
    affiliate_url = url_prop.get("url") if isinstance(url_prop, dict) else None

    if not title_text or not affiliate_url:
        logger.warning("Campaign is missing required Name or AffiliateUrl; skipping. id=%s", campaign.get("id"))
        return

    content_generator = AffiliateContentGenerator(settings.openai_api_key, settings.openai_model)
    generated = content_generator.generate_x_post(
        product_name=title_text,
        description=description_text,
        affiliate_url=affiliate_url,
    )

    publisher = XPublisher(settings.x_bearer_token)
    result = publisher.post_text(generated.x_post)
    if result:
        logger.info("Posted to X with id=%s", result.id)
        update_campaign_posted(settings, campaign.get("id", ""), now_local)


def main() -> None:
    try:
        run()
    except Exception:
        logger.exception("daily_sns_affiliate_post failed")
        raise


if __name__ == "__main__":
    main()
