#!/usr/bin/env python3
"""
Main script for 365bot: lead management and KPI notification.
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# ログ設定
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# 環境変数読み込み
LINE_BOT_TOKEN = os.getenv("LINE_BOT_TOKEN")
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
NOTION_DB_ID   = os.getenv("NOTION_DB_ID")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
LINE_USER_ID   = os.getenv("LINE_USER_ID", "").strip()

# 必須環境変数チェック
required_env = {
    "LINE_BOT_TOKEN": LINE_BOT_TOKEN,
    "NOTION_TOKEN": NOTION_TOKEN,
    "NOTION_DB_ID": NOTION_DB_ID
}
for name, val in required_env.items():
    if not val:
        logging.error(f"Environment variable {name} is required but not set.")
        sys.exit(1)

# 定数
NOTION_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
LINE_PUSH_URL   = "https://api.line.me/v2/bot/message/push"
STRIPE_CHECKOUT_SESSION_URL = "https://api.stripe.com/v1/checkout/sessions"

def resolve_notify_user_ids(config: Dict[str, Any]) -> List[str]:
    """configの各genre.notify_user_idsと環境変数LINE_USER_IDから通知先IDリストを作成"""
    ids: List[str] = []
    for genre in config.get("genre", []):
        ids.extend(genre.get("notify_user_ids", []))
    if LINE_USER_ID:
        ids.append(LINE_USER_ID)
    # 重複を除去（順序保持）
    seen = set()
    result: List[str] = []
    for uid in ids:
        if uid and uid not in seen:
            seen.add(uid)
            result.append(uid)
    return result

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """YAML設定ファイルを読み込む"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logging.warning(f"Configuration file {config_path} not found. Using empty config.")
        return {}

@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def send_line_message(user_id: str, text: str) -> None:
    """LINEプッシュ通知"""
    headers = {"Authorization": f"Bearer {LINE_BOT_TOKEN}",
               "Content-Type": "application/json"}
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }
    resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
    if resp.status_code != 200:
        logging.error(f"LINE push failed: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    logging.info(f"Sent LINE message to {user_id}")

@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def query_notion_leads() -> List[Dict[str, Any]]:
    """Notionデータベースからリード一覧取得（ページネーション対応）"""
    url = f"{NOTION_BASE_URL}/databases/{NOTION_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    payload: Dict[str, Any] = {}
    results: List[Dict[str, Any]] = []
    while True:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            logging.error(f"Failed to query Notion: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        next_cursor = data.get("next_cursor")
        if not data.get("has_more", False) or not next_cursor:
            break
        payload["start_cursor"] = next_cursor
    logging.info(f"Fetched {len(results)} leads from Notion")
    return results

@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def create_notion_lead(properties: Dict[str, Any]) -> str:
    """Notionに新規リードを登録"""
    url = f"{NOTION_BASE_URL}/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    if resp.status_code != 200:
        logging.error(f"Failed to create Notion lead: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    page_id = resp.json().get("id")
    logging.info(f"Created Notion lead with page ID {page_id}")
    return page_id

def extract_lead_metrics(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """KPI計算（総リード数・成約数・売上・CVR）"""
    total_leads = len(leads)
    conversions = 0
    revenue = 0
    for page in leads:
        props = page.get("properties", {})
        payment_status = props.get("Payment_Status", {}).get("select", {}).get("name")
        price = props.get("Price", {}).get("number", 0) or 0
        if payment_status == "Completed":
            conversions += 1
            revenue += price
    cvr = (conversions / total_leads) if total_leads > 0 else 0
    return {
        "total_leads": total_leads,
        "conversions": conversions,
        "revenue": revenue,
        "cvr": cvr
    }

@retry(wait=wait_exponential(multiplier=1, min=1, max=8),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.RequestException,)))
def create_stripe_checkout_link(product_name: str, price: int) -> Optional[str]:
    """Stripe決済リンクを生成（定期購読）"""
    if not STRIPE_SECRET_KEY:
        logging.info("STRIPE_SECRET_KEY not set; skipping checkout link creation.")
        return None
    unit_amount = price * 100  # 円→最小単位
    data = {
        "payment_method_types[]": "card",
        "mode": "subscription",
        "line_items[0][price_data][currency]": "jpy",
        "line_items[0][price_data][unit_amount]": unit_amount,
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": product_name,
        "line_items[0][quantity]": 1,
        "success_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel"
    }
    resp = requests.post(
        STRIPE_CHECKOUT_SESSION_URL,
        data=data,
        auth=(STRIPE_SECRET_KEY, ''),
        timeout=10
    )
    if resp.status_code != 200:
        logging.error(f"Stripe checkout session failed: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    url = resp.json().get("url")
    logging.info(f"Created Stripe checkout session: {url}")
    return url

def send_daily_kpi_notification(config: Dict[str, Any]) -> None:
    """日次KPIを計算してLINE通知"""
    leads = query_notion_leads()
    metrics = extract_lead_metrics(leads)
    message_lines = [
        "【日次KPI報告】",
        f"リード数: {metrics['total_leads']}",
        f"成約数: {metrics['conversions']}",
        f"CVR: {metrics['cvr']:.2%}",
        f"売上: ¥{int(metrics['revenue'])}"
    ]
    # 月間目標1,000万円に対する残日数推定
    month_target = 1_000_000
    if metrics["revenue"] > 0:
        today = datetime.now()
        days_elapsed = (today - datetime(today.year, today.month, 1)).days + 1
        avg_per_day = metrics["revenue"] / days_elapsed if days_elapsed > 0 else 0
        remaining = month_target - metrics["revenue"]
        days_left = remaining / avg_per_day if avg_per_day > 0 else float("inf")
        days_left_msg = "目標達成済み" if days_left < 0 else f"あと{int(days_left)}日"
    else:
        days_left_msg = "データ不足"
    message_lines.append(f"達成予測残日数: {days_left_msg}")
    message_text = "\n".join(message_lines)
    for uid in resolve_notify_user_ids(config):
        try:
            send_line_message(uid, message_text)
        except Exception as e:
            logging.error(f"Failed to send KPI notification to {uid}: {e}")

def process_lead_registration(form_data: Dict[str, str], config: Dict[str, Any]) -> None:
    """フォームデータをNotionへ登録し、Stripeリンク作成・通知"""
    leads = query_notion_leads()
    # 重複チェック
    for page in leads:
        ext_info = page.get("properties", {}).get("External_ID", {}).get("rich_text", [])
        if ext_info and ext_info[0]["text"]["content"] == form_data["external_id"]:
            logging.info(f"Lead with External_ID {form_data['external_id']} already exists; skipping.")
            return
    # 商品設定を取得
    genre = None
    for g in config.get("genre", []):
        if g.get("product_name") == form_data["product"]:
            genre = g
            break
    if not genre:
        logging.warning(f"Product {form_data['product']} not found in config; using default genre.")
        genre = config.get("genre", [{}])[0] if config.get("genre") else {}
    price = genre.get("price", 0) or 0
    expected_cvr = genre.get("expected_cvr")
    # Notion登録用プロパティ
    properties: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": form_data.get("name", form_data['external_id'])}}]},
        "External_ID": {"rich_text": [{"text": {"content": form_data['external_id']}}]},
        "Email": {"email": form_data.get("email")},
        "Phone": {"phone_number": form_data.get("phone")},
        "Product": {"rich_text": [{"text": {"content": form_data['product']}}]},
        "Price": {"number": price},
        "CVR": {"number": expected_cvr},
        "Status": {"select": {"name": "New"}},
        "Payment_Status": {"select": {"name": "Pending"}},
        "Notes": {"rich_text": []}
    }
    # Notionへ登録
    try:
        page_id = create_notion_lead(properties)
    except Exception as e:
        error_msg = f"リード登録に失敗しました: {e}"
        for uid in resolve_notify_user_ids(config):
            try:
                send_line_message(uid, error_msg)
            except Exception as e2:
                logging.error(f"Failed to send error notification to {uid}: {e2}")
        return
    # Stripeリンク生成
    checkout_url = create_stripe_checkout_link(genre.get("product_name", form_data["product"]), price)
    msg = f"新規リード登録: {form_data['external_id']}"
    if checkout_url:
        msg += f" 決済URL: {checkout_url}"
    # 通知送信
    for uid in resolve_notify_user_ids(config):
        try:
            send_line_message(uid, msg)
        except Exception as e2:
            logging.error(f"Failed to send lead notification to {uid}: {e2}")

def main():
    """GitHub Actionsから呼び出されるメイン処理"""
    config = load_config()
    # KPI通知
    try:
        send_daily_kpi_notification(config)
    except Exception as e:
        logging.error(f"Daily KPI notification failed: {e}")
    # フォーム環境変数があればリード登録
    if os.getenv("FORM_EXTERNAL_ID"):
        form_data = {
            "external_id": os.getenv("FORM_EXTERNAL_ID"),
            "email": os.getenv("FORM_EMAIL", ""),
            "phone": os.getenv("FORM_PHONE", ""),
            "product": os.getenv("FORM_PRODUCT", ""),
            "name": os.getenv("FORM_NAME", "")
        }
        process_lead_registration(form_data, config)

if __name__ == "__main__":
    main()
