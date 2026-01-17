from __future__ import annotations

import os
import re
from pathlib import Path

import requests

BANNED_WORDS = ["必ず", "絶対", "100%", "確実", "永久", "絶対に"]


def _template_copy() -> dict[str, str]:
    return {
        "headline": "成果報酬型で始めるB2B向けAI集客/営業エンジン",
        "subheadline": "公開情報を活用し、意思決定に必要なリードを着実に創出します。",
        "cta": "相談する",
    }


def _llm_copy(api_key: str) -> dict[str, str]:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You create concise Japanese landing page copy without exaggeration.",
            },
            {
                "role": "user",
                "content": "成果報酬型AI集客/営業エンジンのLPコピーを3行で作成してください。",
            },
        ],
        "temperature": 0.5,
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()
    lines = [line.strip("- ") for line in content.splitlines() if line.strip()]
    headline = lines[0] if len(lines) > 0 else "成果報酬型B2B AI集客"
    subheadline = lines[1] if len(lines) > 1 else "公開情報を活用し、安定した商談創出を支援。"
    cta = lines[2] if len(lines) > 2 else "相談する"
    return {"headline": headline, "subheadline": subheadline, "cta": cta}


def _sanitize(text: str) -> str:
    sanitized = text
    for word in BANNED_WORDS:
        sanitized = re.sub(re.escape(word), "", sanitized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", sanitized).strip()


def _render_html(copy: dict[str, str]) -> str:
    headline = _sanitize(copy["headline"])
    subheadline = _sanitize(copy["subheadline"])
    cta = _sanitize(copy["cta"])

    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>成果報酬型AI集客/営業エンジン</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #1a1a1a; }}
    .hero {{ max-width: 720px; margin: 0 auto; }}
    .cta {{ display: inline-block; margin-top: 20px; padding: 12px 24px; background: #1f6feb; color: #fff; text-decoration: none; border-radius: 6px; }}
    .note {{ margin-top: 24px; font-size: 0.9rem; color: #4a4a4a; }}
  </style>
</head>
<body>
  <section class=\"hero\">
    <h1>{headline}</h1>
    <p>{subheadline}</p>
    <a class=\"cta\" href=\"mailto:contact@example.com\">{cta}</a>
    <p class=\"note\">公開情報のみを活用し、個人情報は取り扱いません。</p>
  </section>
</body>
</html>"""


def run(base_dir: Path) -> Path:
    docs_dir = base_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY")
    copy = _template_copy()
    if api_key:
        try:
            copy = _llm_copy(api_key)
        except (requests.RequestException, KeyError, IndexError, ValueError):
            copy = _template_copy()

    html = _render_html(copy)
    output_path = docs_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path
