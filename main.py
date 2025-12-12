#!/usr/bin/env python3
"""
Keepa API を利用した完全自動の利益検知 Bot。
Render の Cron Job/Worker でそのまま動くように設計している。

機能概要:
- 指定 ASIN の現在価格を Keepa API から取得
- 仕入れ原価・手数料を考慮して利益/利益率を計算
- 条件を満たす商品を Slack Webhook へ通知（他 Webhook も差し替え容易）
- HTTP エラー時は自動リトライ＆レートリミット付き
- ログは stdout へ出力（Render ダッシュボードで確認可能）
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ローカル実行時は .env を読み込む（Render では不要だが安全）
load_dotenv()


@dataclass
class ProductConfig:
    asin: str
    cost_price: float
    min_profit: float
    min_margin: float
    min_sale_price: Optional[float]
    title: Optional[str]


@dataclass
class ProfitResult:
    asin: str
    current_price: float
    profit: float
    margin: float
    config: ProductConfig
    product_title: str


class KeepaClient:
    """薄い Keepa API クライアント。requests + Retry で安定動作させる。"""

    def __init__(
        self,
        api_key: str,
        domain: int,
        timeout: float,
        retries: int,
        backoff_seconds: float,
        rate_limit_interval: float,
    ) -> None:
        self.api_key = api_key
        self.domain = domain
        self.timeout = timeout
        self.rate_limit_interval = rate_limit_interval

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_seconds,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_product(self, asin: str) -> Dict[str, Any]:
        url = "https://api.keepa.com/product"
        params = {
            "key": self.api_key,
            "domain": self.domain,
            "asin": asin,
            "buybox": 1,
            "stats": 1,
        }
        logging.info("Keepa から商品情報を取得: ASIN=%s", asin)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if payload.get("error"):
            raise RuntimeError(f"Keepa API error: {payload['error']}")

        products = payload.get("products") or []
        if not products:
            raise RuntimeError(f"Keepa API returned no product for ASIN {asin}")

        time.sleep(self.rate_limit_interval)  # 無料プラン配慮のレートリミット
        return products[0]


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_product_catalog(raw: str) -> List[ProductConfig]:
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("PRODUCT_CATALOG は JSON 配列で指定してください") from exc

    if not isinstance(entries, list) or not entries:
        raise ValueError("PRODUCT_CATALOG は1件以上の JSON オブジェクトを含む配列で指定してください")

    configs: List[ProductConfig] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("PRODUCT_CATALOG の各要素はオブジェクトにしてください")
        try:
            asin = str(entry["asin"]).strip()
            cost_price = float(entry["cost_price"])
        except KeyError as exc:
            raise ValueError("asin と cost_price は必須です") from exc

        configs.append(
            ProductConfig(
                asin=asin,
                cost_price=cost_price,
                min_profit=float(entry.get("min_profit", 0.0)),
                min_margin=float(entry.get("min_margin", 0.0)),
                min_sale_price=float(entry["min_sale_price"]) if "min_sale_price" in entry else None,
                title=entry.get("title"),
            )
        )
    return configs


def pick_latest_price(raw_history: Optional[List[int]]) -> Optional[int]:
    if not raw_history:
        return None
    for value in reversed(raw_history):
        if isinstance(value, int) and value > 0:
            return value
    return None


def extract_current_price(product: Dict[str, Any]) -> Optional[float]:
    stats = product.get("stats", {}) or {}
    current = stats.get("current", {}) or {}
    raw_price: Optional[int] = None

    for key in ("buyBox", "new", "used"):
        candidate = current.get(key)
        if isinstance(candidate, int) and candidate > 0:
            raw_price = candidate
            break

    if raw_price is None:
        raw_price = pick_latest_price(product.get("buyBoxPriceHistory"))

    if raw_price is None or raw_price <= 0:
        return None
    return raw_price / 100


def calculate_profit(current_price: float, cost_price: float, fee_rate: float, fba_fee: float) -> tuple[float, float]:
    revenue_after_fee = current_price * (1 - fee_rate) - fba_fee
    profit = revenue_after_fee - cost_price
    margin = profit / current_price if current_price > 0 else 0.0
    return profit, margin


def evaluate_product(
    product: Dict[str, Any],
    config: ProductConfig,
    fee_rate: float,
    fba_fee: float,
) -> Optional[ProfitResult]:
    price = extract_current_price(product)
    if price is None:
        logging.warning("現在価格を取得できませんでした: ASIN=%s", config.asin)
        return None

    profit, margin = calculate_profit(price, config.cost_price, fee_rate, fba_fee)

    if config.min_sale_price is not None and price < config.min_sale_price:
        logging.info("希望売価に未達: ASIN=%s price=%.2f", config.asin, price)
        return None
    if profit < config.min_profit or margin < config.min_margin:
        logging.info(
            "利益条件未達: ASIN=%s profit=%.2f margin=%.2f",
            config.asin,
            profit,
            margin,
        )
        return None

    title = config.title or product.get("title") or "(title not provided)"
    return ProfitResult(
        asin=config.asin,
        current_price=price,
        profit=profit,
        margin=margin,
        config=config,
        product_title=title,
    )


def build_webhook_payload(results: List[ProfitResult]) -> Dict[str, Any]:
    lines = ["Keepa 利益検知結果"]
    for item in results:
        lines.append(
            "\n".join(
                [
                    f"ASIN: {item.asin} ({item.product_title})",
                    f"現行価格: ¥{item.current_price:,.0f}",
                    f"想定利益: ¥{item.profit:,.0f}",
                    f"利益率: {item.margin*100:.1f}%",
                    f"原価: ¥{item.config.cost_price:,.0f}",
                ]
            )
        )
    return {"text": "\n\n".join(lines)}


def send_notification(webhook_url: str, payload: Dict[str, Any], timeout: float, retries: int) -> None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            logging.info("Webhook 通知に成功しました (attempt %d)", attempt)
            return
        except Exception as exc:  # noqa: BLE001
            logging.error("Webhook 通知に失敗しました (attempt %d/%d): %s", attempt, retries, exc)
            if attempt == retries:
                raise
            time.sleep(2**attempt)


def load_settings() -> Dict[str, Any]:
    required = ["KEEPA_API_KEY", "PRODUCT_CATALOG", "NOTIFY_WEBHOOK_URL"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise EnvironmentError(f"必須の環境変数が未設定です: {', '.join(missing)}")

    return {
        "keepa_api_key": os.environ["KEEPA_API_KEY"],
        "keepa_domain": int(os.getenv("KEEPA_DOMAIN", "5")),
        "product_catalog": parse_product_catalog(os.environ["PRODUCT_CATALOG"]),
        "fee_rate": float(os.getenv("PROFIT_FEE_RATE", "0.15")),
        "fba_fee": float(os.getenv("PROFIT_FBA_FEE", "440")),
        "request_timeout": float(os.getenv("REQUEST_TIMEOUT", "15")),
        "http_retries": int(os.getenv("RETRY_COUNT", "3")),
        "retry_backoff_seconds": float(os.getenv("RETRY_BACKOFF_SECONDS", "1")),
        "rate_limit_interval": float(os.getenv("RATE_LIMIT_INTERVAL", "1.0")),
        "webhook_url": os.environ["NOTIFY_WEBHOOK_URL"],
        "webhook_retries": int(os.getenv("WEBHOOK_RETRIES", "3")),
        "dry_run": parse_bool(os.getenv("DRY_RUN", "false")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings["log_level"].upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s: %(message)s",
    )

    client = KeepaClient(
        api_key=settings["keepa_api_key"],
        domain=settings["keepa_domain"],
        timeout=settings["request_timeout"],
        retries=settings["http_retries"],
        backoff_seconds=settings["retry_backoff_seconds"],
        rate_limit_interval=settings["rate_limit_interval"],
    )

    profitable: List[ProfitResult] = []
    for config in settings["product_catalog"]:
        try:
            product = client.fetch_product(config.asin)
            result = evaluate_product(
                product=product,
                config=config,
                fee_rate=settings["fee_rate"],
                fba_fee=settings["fba_fee"],
            )
            if result:
                profitable.append(result)
        except Exception as exc:  # noqa: BLE001
            logging.exception("商品処理中にエラーが発生しました: ASIN=%s error=%s", config.asin, exc)

    if not profitable:
        logging.info("通知対象の商品はありませんでした")
        return

    payload = build_webhook_payload(profitable)
    if settings["dry_run"]:
        logging.info("DRY_RUN 有効のため通知をスキップします: %s", payload)
        return

    send_notification(
        webhook_url=settings["webhook_url"],
        payload=payload,
        timeout=settings["request_timeout"],
        retries=settings["webhook_retries"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        logging.exception("致命的なエラー: %s", exc)
        sys.exit(1)
