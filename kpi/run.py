from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _load_metrics(base_dir: Path) -> dict[str, Any]:
    metrics_path = base_dir / "reports" / "metrics.json"
    if metrics_path.exists():
        return json.loads(metrics_path.read_text(encoding="utf-8"))

    data_dir = base_dir / "data"
    data_files = sorted(data_dir.glob("*.json"))
    for data_file in data_files:
        try:
            content = json.loads(data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(content, dict) and "cpa" in content:
            return content

    price = int(os.getenv("PRICE_YEN", "1000000"))
    return {
        "cpa": int(price * 0.35),
        "price": price,
        "source": "default",
    }


def _decide(metrics: dict[str, Any]) -> dict[str, Any]:
    price = int(metrics.get("price") or os.getenv("PRICE_YEN", "1000000"))
    cpa = float(metrics.get("cpa", 0))

    if cpa <= price * 0.30:
        go = True
        reason = "CPAが目標レンジ内のためGO。"
    elif cpa >= price * 0.50:
        go = False
        reason = "CPAが高いためSTOP。"
    else:
        go = False
        reason = "CPAが保留レンジのため改善待ち。"

    return {
        "go": go,
        "reason": reason,
        "metrics": {
            "cpa": cpa,
            "price": price,
        },
    }


def run(base_dir: Path) -> Path:
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    metrics = _load_metrics(base_dir)
    decision = _decide(metrics)

    output_path = reports_dir / "decision.json"
    output_path.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
