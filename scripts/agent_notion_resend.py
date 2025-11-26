import os
import datetime as dt
from typing import List
import requests


NOTION_API_VERSION = "2022-06-28"


def _get_env(name: str, missing: List[str]) -> str:
    value = os.getenv(name)
    if not value:
        missing.append(name)
    return value or ""


def fetch_notion_items(token: str, database_id: str, limit: int = 50):
    """
    Notion REST API を直接叩いてデータベースからページ一覧を取得する。
    """
    print("[INFO] Fetching pages from Notion database...")

    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    payload = {"page_size": limit}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Error: Failed to fetch Notion pages: {e}")
        return []

    pages = data.get("results", [])
    items = []

    for page in pages:
        props = page.get("properties", {})
        title_prop = props.get("Name", {})
        title = "(無題)"

        # タイトル抽出
        if isinstance(title_prop, dict) and isinstance(title_prop.get("title"), list):
            texts = [t.get("plain_text", "") for t in title_prop["title"]]
            joined = "".join(texts).strip()
            if joined:
                title = joined

        url = page.get("url") or ""
        items.append({"title": title, "url": url})

    return items


def build_email_body(items):
    if not items:
        return "対象のNotionデータベースにレコードがありませんでした。"

    lines = []
    for i, item in enumerate(items, start=1):
        title = item.get("title", "(無題)")
        url = item.get("url") or ""
        if url:
            lines.append(f"{i}. {title}\n   {url}")
        else:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)


def send_email(api_key: str, from_email: str, to_email: str, subject: str, body: str):
    """
    Resend の REST API を使ってメール送信
    """
    print("[INFO] Sending email via Resend...")
    res = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
        },
        timeout=30,
    )
    res.raise_for_status()
    print(f"[INFO] Resend response: {res.status_code} {res.text}")


def main():
    print("=== 365bot agent-notion-resend START ===")
    now = dt.datetime.now()
    print(f"[INFO] Now: {now.isoformat()}")

    missing: List[str] = []
    notion_token = _get_env("NOTION_TOKEN", missing)
    notion_db_id = _get_env("NOTION_DB_ID", missing)
    resend_api_key = _get_env("RESEND_API_KEY", missing)
    from_email = _get_env("RESEND_FROM_EMAIL", missing)
    to_email = _get_env("RESEND_TO_EMAIL", missing)

    if missing:
        print(f"[WARN] Missing envs: {', '.join(missing)}")
        print("[INFO] 環境変数が揃えばメール送信ロジックを実行します。")
        print("=== 365bot agent-notion-resend END (SKIPPED) ===")
        return

    try:
        items = fetch_notion_items(notion_token, notion_db_id, limit=50)

        if not items:
            print("[WARN] No items found in Notion database")
            print("=== 365bot agent-notion-resend END (NO ITEMS) ===")
            return

        body = build_email_body(items)
        subject = f"365bot Notionダイジェスト {now.strftime('%Y-%m-%d')}"

        send_email(resend_api_key, from_email, to_email, subject, body)
        print("[INFO] メール送信が完了しました。")
        print("=== 365bot agent-notion-resend END (SUCCESS) ===")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        print("=== 365bot agent-notion-resend END (ERROR BUT NOT FAILED) ===")


if __name__ == "__main__":
    main()
