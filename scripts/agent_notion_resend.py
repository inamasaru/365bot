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
    from notion_client import Client as NotionClient
    import requests
except ImportError as e:
    print(f"[ERROR] Missing required package: {e}")
    print("[INFO] Please install: pip install notion-client requests")
    sys.exit(1)


def fetch_notion_pages(notion_token: str, database_id: str) -> List[Dict[str, Any]]:
    """
    Notion データベースからページ一覧を取得
    
    Args:
        notion_token: Notion API トークン
        database_id: Notion データベース ID
        
    Returns:
        ページ情報のリスト（タイトル、URL、作成日時など）
    """
    print("[INFO] Fetching pages from Notion database...")
    
    notion = NotionClient(auth=notion_token)
    
    try:
        # データベースからページを取得（最大100件）
        response = notion.databases.query(
            database_id=database_id,
            page_size=100
        )
        
        pages = []
        for page in response.get("results", []):
            page_id = page.get("id", "")
            page_url = page.get("url", "")
            
            # タイトルを取得（プロパティ名は "Name" または "title" を想定）
            title = "Untitled"
            properties = page.get("properties", {})
            
            # タイトルプロパティを探す
            for prop_name, prop_value in properties.items():
                if prop_value.get("type") == "title":
                    title_array = prop_value.get("title", [])
                    if title_array:
                        title = title_array[0].get("plain_text", "Untitled")
                    break
            
            # 作成日時を取得
            created_time = page.get("created_time", "")
            
            pages.append({
                "id": page_id,
                "title": title,
                "url": page_url,
                "created_time": created_time
            })
        
        print(f"[INFO] Found {len(pages)} pages in Notion database")
        return pages
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch Notion pages: {e}")
        raise


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


def generate_email_html(pages: List[Dict[str, Any]]) -> str:
    """
    Notion ページ一覧から HTML メールを生成
    
    Args:
        pages: Notion ページ情報のリスト
        
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
        .page-meta {{
            font-size: 14px;
            color: #7f8c8d;
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
    <p>Total pages: {len(pages)}</p>
    
    <ul class="page-list">
"""
    
    if not pages:
        html += """
        <li class="page-item">
            <div class="page-title">No pages found</div>
        </li>
"""
    else:
        for page in pages:
            title = page.get("title", "Untitled")
            url = page.get("url", "#")
            created_time = page.get("created_time", "")
            
            html += f"""
        <li class="page-item">
            <div class="page-title">
                <a href="{url}" target="_blank">{title}</a>
            </div>
            <div class="page-meta">Created: {created_time}</div>
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
        "NOTION_DATABASE_ID",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "RESEND_TO_EMAIL",
    ]
    
    missing = [name for name in required_envs if not os.getenv(name)]
    if missing:
        print(f"[WARN] Missing envs: {', '.join(missing)}")
        print("[INFO] 環境変数が揃えばメール送信ロジックを実行します")
        print("=== 365bot agent-notion-resend END (SKIPPED) ===")
        return
    
    # 環境変数を取得
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL")
    to_email = os.getenv("RESEND_TO_EMAIL")
    
    try:
        # Notion からページ一覧を取得
        pages = fetch_notion_pages(notion_token, database_id)
        
        # HTML メールを生成
        html_content = generate_email_html(pages)
        
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
        print(f"[ERROR] Unexpected error: {e}")
        print("=== 365bot agent-notion-resend END (ERROR BUT NOT FAILED) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        print("=== 365bot agent-notion-resend END (FATAL ERROR) ===")
        # GitHub Actions では失敗扱いにしない（exit code 0）
        sys.exit(0)
