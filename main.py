#!/usr/bin/env python3
"""
A8.net成果データの取得・通知・保存を行うスクリプト。

環境変数（GitHub Secrets を想定）
- A8_LOGIN_EMAIL / A8_LOGIN_PASSWORD
- SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL
- SLACK_CHANNEL
- NOTION_API_TOKEN / NOTION_DATABASE_ID
- PROXY_URL (optional)
- A8_LOGIN_URL / A8_REPORT_URL (optional override)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import requests
from dateutil import parser as date_parser
from notion_client import Client as NotionClient
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.webhook import WebhookClient

LOGIN_URL_DEFAULT = "https://secure.a8.net/accounts/login/"
REPORT_URL_DEFAULT = "https://www.a8.net/a8v2/pcv2/support/download/report"


@dataclass
class Achievement:
    order_id: str
    program: str
    amount: float
    result_date: datetime
    status: str
    raw: Dict[str, str]


class SlackNotifier:
    def __init__(self, token: Optional[str], channel: Optional[str], webhook_url: Optional[str]) -> None:
        self.token = token
        self.channel = channel
        self.webhook_url = webhook_url
        self.client = WebClient(token=token) if token else None
        self.webhook_client = WebhookClient(webhook_url) if webhook_url else None

    def notify(self, achievements: Iterable[Achievement]) -> None:
        items = list(achievements)
        if not items:
            logging.info("Slack notification skipped: no new achievements")
            return

        lines = ["新しいA8成果を検出しました："]
        for a in items:
            lines.append(
                f"・{a.result_date.strftime('%Y-%m-%d %H:%M')}: {a.program} / {a.status} / {a.amount:,.0f}円 / ID={a.order_id}"
            )
        message = "\n".join(lines)

        if self.client and self.channel:
            try:
                self.client.chat_postMessage(channel=self.channel, text=message)
                logging.info("Slack (bot token) へ通知しました")
                return
            except SlackApiError as exc:
                logging.error("Slack API error via bot token: %s", exc)

        if self.webhook_client:
            try:
                resp = self.webhook_client.send(text=message)
                logging.info("Slack (webhook) へ通知しました: %s", resp.status_code)
            except Exception as exc:  # noqa: BLE001
                logging.error("Slack webhook error: %s", exc)
        else:
            logging.warning("Slack通知が無効です。SLACK_BOT_TOKEN もしくは SLACK_WEBHOOK_URL を設定してください。")


class NotionRepository:
    def __init__(self, api_token: str, database_id: str) -> None:
        self.client = NotionClient(auth=api_token)
        self.database_id = database_id

    def has_order(self, order_id: str) -> bool:
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={"property": "Order ID", "title": {"equals": order_id}},
            page_size=1,
        )
        exists = bool(response.get("results"))
        logging.debug("Notion check for order %s -> %s", order_id, exists)
        return exists

    def save(self, achievement: Achievement) -> None:
        self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Order ID": {"title": [{"text": {"content": achievement.order_id}}]},
                "Program": {"rich_text": [{"text": {"content": achievement.program or "-"}}]},
                "Amount": {"number": achievement.amount},
                "Result Date": {"date": {"start": achievement.result_date.isoformat()}},
                "Status": {"rich_text": [{"text": {"content": achievement.status}}]},
                "Raw": {"rich_text": [{"text": {"content": json.dumps(achievement.raw, ensure_ascii=False)}}]},
            },
        )
        logging.info("Notion へ成果(ID=%s)を保存しました", achievement.order_id)


def load_env() -> Dict[str, str]:
    required = [
        "A8_LOGIN_EMAIL",
        "A8_LOGIN_PASSWORD",
        "NOTION_API_TOKEN",
        "NOTION_DATABASE_ID",
    ]
    config = {key: os.getenv(key, "") for key in required}
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise RuntimeError(f"必須の環境変数が不足しています: {', '.join(missing)}")

    config.update(
        {
            "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
            "SLACK_CHANNEL": os.getenv("SLACK_CHANNEL", ""),
            "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL", ""),
            "PROXY_URL": os.getenv("PROXY_URL", ""),
            "A8_LOGIN_URL": os.getenv("A8_LOGIN_URL", LOGIN_URL_DEFAULT),
            "A8_REPORT_URL": os.getenv("A8_REPORT_URL", REPORT_URL_DEFAULT),
        }
    )
    return config


def build_session(proxy_url: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "a8-automation-bot/1.0"})
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
        logging.info("プロキシを使用します: %s", proxy_url)
    return session


def login_and_download_csv(session: requests.Session, login_url: str, report_url: str, email: str, password: str) -> bytes:
    logging.info("A8.net へログインします")
    login_payload = {"login": email, "password": password}
    resp = session.post(login_url, data=login_payload)
    resp.raise_for_status()

    logging.info("成果CSVをダウンロードします")
    csv_resp = session.get(report_url)
    csv_resp.raise_for_status()
    return csv_resp.content


def parse_csv(content: bytes) -> List[Dict[str, str]]:
    for encoding in ("cp932", "utf-8", "utf-8-sig"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "Failed to decode CSV")

    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, str]] = []
    for row in reader:
        normalized_row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
        rows.append(normalized_row)
    logging.info("CSV 行数: %d", len(rows))
    return rows


def pick_value(row: Dict[str, str], keys: List[str], default: str = "") -> str:
    for key in keys:
        if key in row and row[key]:
            return row[key]
    return default


def parse_amount(value: str) -> float:
    cleaned = value.replace(",", "").replace("円", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(value: str) -> datetime:
    try:
        return date_parser.parse(value)
    except (ValueError, TypeError):
        return datetime.now()


def normalize(row: Dict[str, str]) -> Achievement:
    order_id = pick_value(row, ["注文ID", "注文番号", "オーダーID", "成果ID", "order_id", "id"])
    if not order_id:
        order_id = f"auto-{abs(hash(json.dumps(row, ensure_ascii=False)))}"

    program = pick_value(row, ["プログラム名", "広告主", "program", "案件"], "(不明なプログラム)")
    amount_str = pick_value(row, ["成果報酬(税抜)", "成果報酬額", "成果報酬", "報酬", "金額", "amount"], "0")
    status = pick_value(row, ["状態", "ステータス", "status"], "不明")
    date_value = pick_value(row, ["成果発生日時", "発生日", "日時", "date", "created"], datetime.now().isoformat())

    return Achievement(
        order_id=order_id,
        program=program,
        amount=parse_amount(amount_str),
        result_date=parse_date(date_value),
        status=status,
        raw=row,
    )


def filter_new_achievements(rows: List[Dict[str, str]], notion_repo: NotionRepository) -> List[Achievement]:
    achievements: List[Achievement] = []
    for row in rows:
        achievement = normalize(row)
        if notion_repo.has_order(achievement.order_id):
            logging.debug("既存の成果をスキップ: %s", achievement.order_id)
            continue
        achievements.append(achievement)
    return achievements


def process() -> None:
    config = load_env()
    logging.info("環境変数を読み込みました")

    session = build_session(config.get("PROXY_URL", ""))
    csv_content = login_and_download_csv(
        session,
        login_url=config["A8_LOGIN_URL"],
        report_url=config["A8_REPORT_URL"],
        email=config["A8_LOGIN_EMAIL"],
        password=config["A8_LOGIN_PASSWORD"],
    )

    rows = parse_csv(csv_content)
    notion_repo = NotionRepository(config["NOTION_API_TOKEN"], config["NOTION_DATABASE_ID"])
    new_achievements = filter_new_achievements(rows, notion_repo)

    if not new_achievements:
        logging.info("新しい成果はありません")
        return

    notifier = SlackNotifier(
        token=config.get("SLACK_BOT_TOKEN"),
        channel=config.get("SLACK_CHANNEL"),
        webhook_url=config.get("SLACK_WEBHOOK_URL"),
    )
    notifier.notify(new_achievements)

    for achievement in new_achievements:
        notion_repo.save(achievement)

    logging.info("処理が完了しました。新規成果数: %d", len(new_achievements))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    try:
        process()
    except Exception as exc:  # noqa: BLE001
        logging.exception("処理中にエラーが発生しました: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
