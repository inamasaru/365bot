from __future__ import annotations

import json
from pathlib import Path

VARIATIONS = [
    ("相談する", "資料請求をする"),
    ("相談する", "デモ依頼をする"),
    ("相談する", "概要を受け取る"),
]


def _load_decision(base_dir: Path) -> dict:
    decision_path = base_dir / "reports" / "decision.json"
    if decision_path.exists():
        return json.loads(decision_path.read_text(encoding="utf-8"))
    return {}


def run(base_dir: Path) -> Path:
    decision = _load_decision(base_dir)
    docs_path = base_dir / "docs" / "index.html"
    if not docs_path.exists():
        return docs_path

    content = docs_path.read_text(encoding="utf-8")
    variation_index = 0
    metrics = decision.get("metrics", {}) if isinstance(decision, dict) else {}
    cpa = metrics.get("cpa") or 0
    if cpa:
        variation_index = int(float(cpa)) % len(VARIATIONS)

    before, after = VARIATIONS[variation_index]
    if before in content:
        content = content.replace(before, after, 1)
    docs_path.write_text(content, encoding="utf-8")
    return docs_path


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    run(base)
