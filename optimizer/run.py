from __future__ import annotations

import os
from pathlib import Path

import requests


def _template_hypothesis() -> str:
    return """# 仮説メモ

- リードの絞り込み条件を業界別に整理し、反応率の高いセグメントから優先的にアプローチする。
- LPのCTA文言を簡潔にし、問い合わせまでのステップ数を減らす。
- 直近の成功事例を1件追加し、信頼性を補強する。
"""


def _llm_hypothesis(api_key: str) -> str:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a B2B growth strategist. Provide 3 concise hypotheses in Japanese.",
            },
            {
                "role": "user",
                "content": "成果報酬型AI集客/営業エンジンの改善仮説を3点提案してください。",
            },
        ],
        "temperature": 0.4,
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    message = data["choices"][0]["message"]["content"].strip()
    return f"# 仮説メモ\n\n{message}\n"


def run(base_dir: Path) -> Path:
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY")
    hypothesis = _template_hypothesis()
    if api_key:
        try:
            hypothesis = _llm_hypothesis(api_key)
        except (requests.RequestException, KeyError, IndexError, ValueError):
            hypothesis = _template_hypothesis()

    output_path = reports_dir / "hypothesis.md"
    output_path.write_text(hypothesis, encoding="utf-8")
    return output_path
