from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.pipeline import run_pipeline  # noqa: E402


def main() -> None:
    run_pipeline(BASE_DIR)

    required_paths = [
        BASE_DIR / "data" / "leads.csv",
        BASE_DIR / "reports" / "decision.json",
        BASE_DIR / "reports" / "hypothesis.md",
        BASE_DIR / "docs" / "index.html",
        BASE_DIR / "reports" / "latest.md",
        BASE_DIR / "reports" / "latest.json",
    ]

    missing = [path for path in required_paths if not path.exists()]
    if missing:
        raise SystemExit(f"Missing outputs: {missing}")


if __name__ == "__main__":
    main()
