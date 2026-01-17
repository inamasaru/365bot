from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def _seed_leads() -> Iterable[dict[str, str]]:
    return [
        {
            "company": "サンプル電子株式会社",
            "url": "https://example.com",
            "industry": "製造業",
            "location": "東京都",
            "source_url": "https://example.com/companies",
        },
        {
            "company": "ブルースカイ物流",
            "url": "https://example.org",
            "industry": "物流",
            "location": "大阪府",
            "source_url": "https://example.org/list",
        },
        {
            "company": "グリーンエナジー合同会社",
            "url": "https://example.net",
            "industry": "エネルギー",
            "location": "福岡県",
            "source_url": "https://example.net/catalog",
        },
    ]


def run(base_dir: Path) -> Path:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "leads.csv"

    fieldnames = ["company", "url", "industry", "location", "source_url"]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in _seed_leads():
            writer.writerow(row)

    return output_path
