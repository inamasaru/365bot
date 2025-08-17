#!/usr/bin/env python3
"""
main.py

This script implements the core functionality for the 365億Bot automation.
It handles interactions with LINE Messaging API, Notion API for lead
management, optional Stripe integration for payment links, KPI calculation,
and daily notifications. The script is designed to run on GitHub Actions
via cron and can also be invoked manually. Configuration for different
business genres is loaded from `config.yaml`.

Usage:
    python main.py  # Execute scheduled tasks and KPI notifications

Environment variables (expected to be set via GitHub Secrets or .env):
    LINE_BOT_TOKEN     - Required. Access token for LINE Messaging API (ntn_ or secret_ prefix).
    NOTION_TOKEN       - Required. Notion internal integration token (ntn_ prefix).
    NOTION_DB_ID       - Required. ID of the Notion database for lead management.
    STRIPE_SECRET_KEY  - Optional. Secret key for Stripe API (sk_live_ or sk_test_ prefix).

The script uses tenacity for exponential backoff when calling external APIs
and logs key events. Errors are communicated via LINE to ensure prompt
awareness without exposing sensitive information.
"""

import os
import sys
import json
import yaml
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Configure logging to STDOUT
logging.basicConfig(stream=sys.stdout,
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

LINE_BOT_TOKEN = os.getenv("LINE_BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
LINE_USER_ID = os.getenv("LINE_USER_ID", "").strip()

def resolve_notify_user_ids(config: dict) -> list:
    """Return list of LINE user IDs to notify, using config genre list and fallback to LINE_USER_ID."""
    ids = []
    for genre in config.get('genre', []):
        ids += genre.get('notify_user_ids', [])
    if LINE_USER_ID:
        ids.append(LINE_USER_ID)
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for uid in ids:
        if uid and uid not in seen:
            seen.add(uid)
            result.append(uid)
    return result

  

#Validate required environment variables
fr var_name, var_value in {

     


    "LINE_BOT_TOKEN": LINE_BOT_TOKEN,
    "NOTION_TOKEN": NOTION_TOKEN,
    "NOTION_DB_ID": NOTION_DB_ID,
}.items():
  if not var_value:
        logging.error(f"Environment variable {var_name} is required but not set.")
        sys.exit(1)

# Constants for API endpoints
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
STRIPE_CHECKOUT_SESSION_URL = "https://api.stripe.com/v1/checkout/sessions"


def load_config(config_path: str = "config.yaml") -> Dict[str, any]:
    """Load YAML configuration for business genres.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed configuration as a dictionary.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config or {}
    except FileNotFoundError:
        logging.warning(f"Configuration file {config_path} not found. Using empty config.")
        return {}


@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def send_line_message(user_id: str, text: str) -> None:
    """Send a push message to a LINE user.

    Args:
        user_id: LINE user ID to send the message to.
        text: Message content.
    """
    headers = {
        "Authorization": f"Bearer {LINE_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
    if response.status_code != 200:
        logging.error(f"LINE push failed: {response.status_code} {response.text}")
        response.raise_for_status()
    logging.info("Sent LINE message successfully.")


@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def query_notion_leads() -> List[Dict[str, any]]:
    """Retrieve all leads from the Notion database.

    Returns:
        List of page objects representing leads.
    """
    url = f"{NOTION_BASE_URL}/databases/{NOTION_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    leads = []
    payload = {}
    while True:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            logging.error(f"Failed to query Notion: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        data = resp.json()
        leads.extend(data.get("results", []))
        next_cursor = data.get("next_cursor")
        has_more = data.get("has_more", False)
        if not has_more or not next_cursor:
            break
        payload["start_cursor"] = next_cursor
    logging.info(f"Fetched {len(leads)} leads from Notion.")
    return leads


@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def create_notion_lead(lead_props: Dict[str, any]) -> str:
    """Create a new lead in the Notion database.

    Args:
        lead_props: Dictionary of properties conforming to Notion API.

    Returns:
        The created page ID.
    """
    url = f"{NOTION_BASE_URL}/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": lead_props
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    if resp.status_code != 200:
        logging.error(f"Failed to create lead: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    page_id = resp.json().get("id")
    logging.info(f"Created new lead with page ID {page_id}")
    return page_id


def extract_lead_metrics(leads: List[Dict[str, any]]) -> Dict[str, any]:
    """Extract KPI metrics from a list of lead pages.

    Args:
        leads: List of Notion page objects.

    Returns:
        Dictionary containing total leads, conversions, revenue, CVR and other metrics.
    """
    total_leads = len(leads)
    conversions = 0
    revenue = 0
    for page in leads:
        props = page.get("properties", {})
        payment_status = props.get("Payment_Status", {}).get("select", {}).get("name")
        price_val = props.get("Price", {}).get("number", 0)
        if payment_status == "Completed":
            conversions += 1
            revenue += price_val
    cvr = (conversions / total_leads) if total_leads > 0 else 0
    metrics = {
        "total_leads": total_leads,
        "conversions": conversions,
        "revenue": revenue,
        "cvr": cvr
    }
    return metrics


@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def create_stripe_checkout_link(product_name: str, price: int) -> Optional[str]:
    """Create a Stripe Checkout Session for a single-item purchase.

    Args:
        product_name: Name of the product.
        price: Price in JPY.

    Returns:
        Checkout session URL or None if Stripe is not configured.
    """
    if not STRIPE_SECRET_KEY:
        logging.info("Stripe secret key not provided. Skipping checkout link generation.")
        return None
    # Convert JPY to smallest currency unit (yen) * 100 for Stripe (i.e., to yen subunits)
    unit_amount = price * 100
    data = {
        'payment_method_types[]': 'card',
        'mode': 'payment',
        'line_items[0][price_data][currency]': 'jpy',
        'line_items[0][price_data][unit_amount]': unit_amount,
        'line_items[0][price_data][product_data][name]': product_name,
        'line_items[0][quantity]': 1,
        'success_url': 'https://example.com/success',
        'cancel_url': 'https://example.com/cancel'
    }
    auth = (STRIPE_SECRET_KEY, '')
    resp = requests.post(STRIPE_CHECKOUT_SESSION_URL, data=data, auth=auth, timeout=10)
    if resp.status_code != 200:
        logging.error(f"Stripe checkout session creation failed: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    url = resp.json().get("url")
    logging.info(f"Created Stripe checkout session: {url}")
    return url


def send_daily_kpi_notification(config: Dict[str, any]) -> None:
    """Compute metrics and send a daily KPI summary via LINE.

    Args:
        config: Loaded configuration dictionary.
    """
    leads = query_notion_leads()
    metrics = extract_lead_metrics(leads)
    # Build KPI message
    message_lines = [
        "【日次KPI報告】",
        f"リード数: {metrics['total_leads']}",
        f"成約数: {metrics['conversions']}",
        f"CVR: {metrics['cvr']:.2%}",
        f"売上: ¥{int(metrics['revenue'])}"
    ]
    # Estimate days remaining for 1st month target
    month_target = 1_000_000  # 1,000万円
    if metrics['revenue'] > 0:
        days_elapsed = (datetime.now() - datetime(datetime.now().year, datetime.now().month, 1)).days + 1
        avg_per_day = metrics['revenue'] / days_elapsed
        remaining = month_target - metrics['revenue']
        days_left = remaining / avg_per_day if avg_per_day > 0 else float('inf')
        if days_left < 0:
            days_left_msg = "目標達成済み"
        else:
            days_left_msg = f"あと{int(days_left)}日"
    else:
        days_left_msg = "データ不足"
    message_lines.append(f"達成予測残日数: {days_left_msg}")
    # Send message to all configured recipients per genre
  for uid in resolve_notify_user_ids(config):
        
            try:
                send_line_message(uid, "\n".join(message_lines))
            except Exception as e:
                logging.error(f"Failed to send KPI notification to {uid}: {e}")


def process_lead_registration(form_data: Dict[str, str], config: Dict[str, any]) -> None:
    """Process incoming lead data from a pseudo form submission.

    This function simulates receiving lead data from a web form and writes it
    into Notion. It deduplicates using the External_ID property. After
    registering, it generates a Stripe checkout link (if possible) and sends
    notification via LINE.

    Args:
        form_data: Dictionary with keys 'external_id', 'email', 'phone', 'product'.
        config: Loaded configuration dictionary.
    """
    leads = query_notion_leads()
    # Check for duplicates
    for page in leads:
        props = page.get("properties", {})
        ext_id = props.get("External_ID", {}).get("rich_text", [])
        if ext_id and ext_id[0]["text"]["content"] == form_data['external_id']:
            logging.info(f"Lead with External_ID {form_data['external_id']} already exists; skipping creation.")
            return
    # Determine product configuration
    selected_genre = None
    for genre in config.get('genre', []):
        if genre.get('product_name') == form_data['product']:
            selected_genre = genre
            break
    if not selected_genre:
        logging.warning(f"Product {form_data['product']} not found in config; using first genre as default.")
        selected_genre = config.get('genre', [{}])[0]
    price = selected_genre.get('price', 0)
    # C        for uid in resolve_notify_user_ids(config):
    properties = {
        "Name": {"title": [{"text": {"content": form_data.get('name', form_data['external_id'])}}]},
        "External_ID": {"rich_text": [{"text": {"content": form_data['external_id']}}]},
        "Email": {"email": form_data.get('email')},
        "Phone": {"phone_number": form_data.get('phone')},
        "Product": {"rich_text": [{"text": {"content": form_data['product']}}]},
        "Price": {"number": price},
        "CVR": {"number": selected_genre.get('expected_cvr')},
        "Status": {"select": {"name": "New"}},
        "Payment_Status": {"select": {"name": "Pending"}},
        "Notes": {"rich_text": []}
    }
    try:
        page_id = create_notion_lead(properties)
    except Exception as e:
        # Notify error via LINE
        #for genre in config.get('genre', []):
            #for uid in genre.get('notify_user_ids', []):
                #
                for uid in resolve_notify_user_ids(config):
                                send_line_message(uid, f"リード登録失敗: {str(e)}")
                    send_line_message(uid, f"リード登録に失敗しました: {e}")
        return
    # Generate Stripe checkout link if possible
    checkout_url = create_stripe_checkout_link(selected_genre['product_name'], price)
    # Notify sales rep via LINE
    if checkout_url:
        msg = f"新規リード登録: {form_data['external_id']}. 決済URL: {checkout_url}"
    else:
        msg = f"新規リード登録: {form_data['external_id']}"
   for uid in resolve_notify_user_ids(config):
        send_line_message(uid, msg)


def main():
    """Main entry point for scheduled and manual runs."""
    config = load_config()
    # In this simple example, always compute and send daily KPI on each run
    try:
        send_daily_kpi_notification(config)
    except Exception as e:
        logging.error(f"Daily KPI notification failed: {e}")
    # Example: handle pseudo form data if provided via environment
    if os.getenv('FORM_EXTERNAL_ID'):
        form_data = {
            'external_id': os.getenv('FORM_EXTERNAL_ID'),
            'email': os.getenv('FORM_EMAIL', ''),
            'phone': os.getenv('FORM_PHONE', ''),
            'product': os.getenv('FORM_PRODUCT', ''),
            'name': os.getenv('FORM_NAME', '')
        }
        process_lead_registration(form_data, config)


if __name__ == '__main__':
    main()
