import os
import requests
from datetime import datetime, timezone, timedelta

# 認証情報と API バージョン
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ.get("DATABASE_ID")
NOTION_VERSION = "2025-09-03"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

def get_database_id_by_name(name: str) -> str | None:
    """
    Notion にあるデータベース名から ID を検索して返します。
    """
    url = "https://api.notion.com/v1/search"
    payload = {
        "query": name,
        "filter": {"value": "database", "property": "object"},
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    for result in res.json().get("results", []):
        if result.get("object") != "database":
            continue
        title_parts = result.get("title", [])
        title = "".join(part.get("plain_text", "") for part in title_parts)
        if title == name:
            return result["id"]
    return None

def ensure_database_id() -> str:
    """
    DATABASE_ID が設定されていない場合、データベース名から検索して設定します。
    """
    global DATABASE_ID
    if DATABASE_ID:
        return DATABASE_ID
    db_id = get_database_id_by_name("GPT長期記憶")
    if db_id is None:
        raise RuntimeError("DATABASE_ID が設定されておらず、データベース名からも見つかりません。")
    DATABASE_ID = db_id
    return DATABASE_ID

def add_memory(user: str, memory_text: str, date: datetime | None = None) -> dict:
    """
    新しい記憶をデータベースに追加します。
    """
    db_id = ensure_database_id()
    if date is None:
        # JST タイムゾーンの日付を設定（時刻部分は不要）
        date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    iso_date = date.date().isoformat()

    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "User": {
                "title": [{"text": {"content": user}}],
            },
            "Memory": {
                "rich_text": [{"text": {"content": memory_text}}],
            },
            "Date": {"date": {"start": iso_date}},
        },
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    return res.json()

def read_memories(limit: int = 10, sort_by_date_desc: bool = True) -> list[dict]:
    """
    データベースから記憶を取得します。
    """
    db_id = ensure_database_id()
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    sorts = []
    if sort_by_date_desc:
        sorts.append({"property": "Date", "direction": "descending"})
    payload: dict = {"sorts": sorts}
    if limit:
        payload["page_size"] = limit
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()

    memory_entries: list[dict] = []
    for page in res.json().get("results", []):
        props = page.get("properties", {})
        user = ""
        if props.get("User", {}).get("title"):
            user = props["User"]["title"][0]["plain_text"]
        memory_text = "".join(rt["plain_text"] for rt in props.get("Memory", {}).get("rich_text", []))
        date_str = None
        if props.get("Date", {}).get("date"):
            date_str = props["Date"]["date"]["start"]
        memory_entries.append({"user": user, "memory": memory_text, "date": date_str})
    return memory_entries

if __name__ == "__main__":
    # MEMO: MEMORY_TEXT を設定すると記憶を追加、設定しない場合は既存の記憶を出力します。
    user_name = os.environ.get("MEMORY_USER", "稲村優")
    memory_text = os.environ.get("MEMORY_TEXT")
    if memory_text:
        add_memory(user_name, memory_text)
    else:
        print(read_memories())
