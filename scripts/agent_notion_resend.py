#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
365bot agent-notion-resend
Notion データベースからページ一覧を取得し、Resend API でメール送信する
"""

import os
import sys
import datetime as dt
from typing import List, Dict, Any

try:
    from notion_client import Client
    import requests
except ImportError as e:
    print(f"[ERROR] Missing required package: {e}")
    print("[INFO] Please install: pip install notion-client requests")
    sys.exit(1)


def fetch_notion_items(notion: Client, database_id: str, limit: int = 50):
    print("[INFO] Fetching pages from Notion database...")

    try:
        results = notion.databases.query(
            database_id=database_id,
            page_size=limit
        )
    except Exception as e:
        print(f"Error: Failed to fetch Notion pages: {e}")
        return []

    pages = results.get("results", [])
    items = []

    for page in pages:
        props = page.get("properties", {})
        title_prop = props.get("Name")
        title = "(無題)"

        if title_prop and isinstance(title_prop.get("title"), list):
            texts = [t.get("plain_text", "") for t in title_prop["title"]]
            joined_title = "".join(texts).strip()
            if joined_title:
                title = joined_title

        url = page.get("url", "")
        items.append({"title": title, "url": url})

    return items


def send_email_via_resend(
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    html_content: str
) -> bool:
    """
    Resend API を使ってメールを送信
    
    Args:
        api_key: Resend API キー
        from_email: 送信元メールアドレス
        to_email: 送信先メールアドレス
        subject: メール件名
        html_content: メール本文（HTML）
        
    Returns:
        送信成功の場合 True、失敗の場合 False
    """
    print("[INFO] Sending email via Resend API...")
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            email_id = result.get("id", "unknown")
            print(f"[INFO] Email sent successfully! ID: {email_id}")
            return True
        else:
            print(f"[ERROR] Failed to send email: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception while sending email: {e}")
        return False


def generate_email_html(items: List[Dict[str, Any]]) -> str:
    """
    Notion ページ一覧から HTML メールを生成
    
    Args:
        items: Notion ページ情報のリスト
        
    Returns:
        HTML メール本文
    """
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .page-list {{
            list-style: none;
            padding: 0;
        }}
        .page-item {{
            background: #f8f9fa;
            margin: 10px 0;
            padding: 15px;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }}
        .page-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .page-title a {{
            color: #2c3e50;
            text-decoration: none;
        }}
        .page-title a:hover {{
            color: #3498db;
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            font-size: 14px;
            color: #7f8c8d;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>📋 Notion Database Digest</h1>
    <p>Generated at: {now}</p>
    <p>Total pages: {len(items)}</p>
    
    <ul class="page-list">
"""
    
    if not items:
        html += """
        <li class="page-item">
            <div class="page-title">No pages found</div>
        </li>
"""
    else:
        for item in items:
            title = item.get("title", "(無題)")
            url = item.get("url", "#")
            
            html += f"""
        <li class="page-item">
            <div class="page-title">
                <a href="{url}" target="_blank">{title}</a>
            </div>
        </li>
"""
    
    html += """
    </ul>
    
    <div class="footer">
        <p>This email was automatically generated by 365bot agent-notion-resend</p>
    </div>
</body>
</html>
"""
    
    return html


def main():
    """メイン処理"""
    print("=== 365bot agent-notion-resend START ===")
    now = dt.datetime.now().isoformat()
    print(f"[INFO] Now: {now}")
    
    # 環境変数の確認
    required_envs = [
        "NOTION_TOKEN",
        "NOTION_DB_ID",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "RESEND_TO_EMAIL",
    ]
    
    missing = [name for name in required_envs if not os.getenv(name)]
    if missing:
        print(f"[WARN] Missing envs: {', '.join(missing)}")
        print("[INFO] 環境変数が欠けているためメール送信をスキップします")
        print("=== 365bot agent-notion-resend END (SKIPPED) ===")
        return
    
    # 環境変数を取得
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DB_ID")
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL")
    to_email = os.getenv("RESEND_TO_EMAIL")
    
    try:
        # Notion クライアントを初期化
        notion = Client(auth=notion_token)
        
        # Notion からページ一覧を取得
        items = fetch_notion_items(notion, database_id)
        
        if not items:
            print("[WARN] No items found in Notion database")
            print("=== 365bot agent-notion-resend END (NO ITEMS) ===")
            return
        
        print(f"[INFO] Found {len(items)} items in Notion database")
        
        # HTML メールを生成
        html_content = generate_email_html(items)
        
        # メールを送信
        subject = f"📋 Notion Database Digest - {dt.datetime.now().strftime('%Y-%m-%d')}"
        success = send_email_via_resend(
            api_key=resend_api_key,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )
        
        if success:
            print("=== 365bot agent-notion-resend END (SUCCESS) ===")
        else:
            print("=== 365bot agent-notion-resend END (EMAIL FAILED) ===")
            
    except Exception as e:
        print(f"Error: [ERROR] Unexpected error: {e}")
        print("=== 365bot agent-notion-resend END (ERROR BUT NOT FAILED) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        print("=== 365bot agent-notion-resend END (FATAL ERROR) ===")
        # GitHub Actions では失敗扱いにしない（exit code 0）
        sys.exit(0)
