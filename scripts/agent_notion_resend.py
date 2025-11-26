#!/usr/bin/env python3
"""
Notion → Resend メール送信エージェント
Lead_DB_New3 の全レコードを取得し、タイトルとページURLの一覧をメールで送る。

環境変数:
  NOTION_TOKEN       : Notion API インテグレーショントークン
  NOTION_DB_ID       : 取得対象の Notion データベース ID
  RESEND_API_KEY     : Resend API キー
  RESEND_FROM_EMAIL  : 送信元メールアドレス（Resendに登録済のもの）
  RESEND_TO_EMAIL    : 送信先メールアドレス
"""

import os
import requests
from typing import List, Dict

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"
RESEND_ENDPOINT = "https://api.resend.com/emails"


def get_leads() -> List[Dict[str, str]]:
    """Notion データベースから全ページを取得し、タイトルとURLを返す。"""
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_DB_ID")
    if not token or not db_id:
        print("WARNING: NOTION_TOKEN または NOTION_DB_ID が設定されていません。")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"{NOTION_API_BASE}/databases/{db_id}/query"
    payload = {}
    results: List[Dict[str, str]] = []

    while True:
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
        except Exception as e:
            print(f"ERROR: Notion API へのリクエストに失敗しました: {e}")
            break

        if resp.status_code != 200:
            print(f"ERROR: Notion API から {resp.status_code} エラーが返されました: {resp.text}")
            break

        data = resp.json()
        for page in data.get("results", []):
            properties = page.get("properties", {})
            # Name プロパティのタイトルを抽出
            title_prop = properties.get("Name", {})
            title_text = ""
            if title_prop.get("type") == "title":
                for t in title_prop.get("title", []):
                    title_text += t.get("plain_text", "")
            page_url = page.get("url", "")
            results.append({"name": title_text or "(no title)", "url": page_url})

        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break

    return results


def send_email(leads: List[Dict[str, str]]) -> None:
    """Resend API を使ってダイジェストメールを送信する。"""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL")
    to_email = os.environ.get("RESEND_TO_EMAIL")
    if not api_key or not from_email or not to_email:
        print("WARNING: RESEND_API_KEY / RESEND_FROM_EMAIL / RESEND_TO_EMAIL が設定されていません。")
        return

    # メール本文の作成
    body_lines = [f"- {item['name']}: {item['url']}" for item in leads]
    body_text = "Lead_DB_New3 のダイジェスト\n" + ("\n".join(body_lines) if body_lines else "レコードがありません。")

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": "Lead_DB_New3 Daily Digest",
        "text": body_text,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(RESEND_ENDPOINT, json=payload, headers=headers, timeout=30)
        if 200 <= resp.status_code < 300:
            print("INFO: メール送信に成功しました。")
        else:
            print(f"ERROR: メール送信に失敗しました。status={resp.status_code} body={resp.text}")
    except Exception as e:
        print(f"ERROR: Resend API への接続に失敗しました: {e}")


def main() -> None:
    leads = get_leads()
    send_email(leads)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 想定外の例外は握りつぶしてログに出す
        print(f"ERROR: スクリプト実行時に例外が発生しました: {e}")
