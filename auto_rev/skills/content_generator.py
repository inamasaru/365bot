from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class GeneratedContent:
    x_post: str


class AffiliateContentGenerator:
    def __init__(self, api_key: str, model: str = "gpt-5.1-mini") -> None:
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def generate_x_post(
        self,
        product_name: str,
        description: Optional[str],
        affiliate_url: str,
        max_length: int = 130,
        tone: str = "ライトで砕けた日本語・タメ口",
    ) -> GeneratedContent:
        system_prompt = (
            "あなたは日本語のSNSマーケターです。X（旧Twitter）向けに短く魅力的な投稿文を作成します。"
            "誇大広告や虚偽の表現、医薬品的な断定表現は禁止です。"
        )
        user_prompt = (
            f"商品名: {product_name}\n"
            f"説明: {description or '情報なし'}\n"
            f"アフィリエイトURL: {affiliate_url}\n"
            f"トーン: {tone}\n"
            "ハッシュタグは最大2個まで。文字数はおおよそ"
            f"{max_length}文字以内。出力はポスト1件分のテキストのみ。"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 280,
        }

        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 300:
            logger.error("OpenAI API error: status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected OpenAI response format: %s", data)
            raise RuntimeError("Failed to parse OpenAI response") from exc

        if len(content) > 260:
            content = content[:259].rstrip() + "…"

        return GeneratedContent(x_post=content)
