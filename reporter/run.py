from __future__ import annotations

import json
import os
from pathlib import Path

import requests


def _build_summary(base_dir: Path) -> dict:
    decision_path = base_dir / "reports" / "decision.json"
    hypothesis_path = base_dir / "reports" / "hypothesis.md"
    decision = {}
    if decision_path.exists():
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
    hypothesis = ""
    if hypothesis_path.exists():
        hypothesis = hypothesis_path.read_text(encoding="utf-8")

    return {
        "decision": decision,
        "hypothesis": hypothesis,
    }


def _send_to_notion(api_key: str, summary: dict) -> None:
    payload = {
        "parent": {"type": "page_id", "page_id": os.getenv("NOTION_PAGE_ID", "")},
        "properties": {
            "title": {
                "title": [
                    {
                        "text": {"content": "Daily AI Revenue Report"},
                    }
                ]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": json.dumps(summary, ensure_ascii=False)},
                        }
                    ]
                },
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=20)
    response.raise_for_status()


def run(base_dir: Path) -> tuple[Path, Path]:
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = _build_summary(base_dir)
    notion_key = os.getenv("NOTION_API_KEY")
    if notion_key:
        try:
            _send_to_notion(notion_key, summary)
        except requests.RequestException:
            pass

    md_path = reports_dir / "latest.md"
    json_path = reports_dir / "latest.json"

    md_body = "# Latest Report\n\n" + json.dumps(summary, ensure_ascii=False, indent=2)
    md_path.write_text(md_body, encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return md_path, json_path
