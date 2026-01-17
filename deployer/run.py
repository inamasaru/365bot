from __future__ import annotations

from pathlib import Path


def run(base_dir: Path) -> Path:
    docs_dir = base_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    index_path = docs_dir / "index.html"
    if not index_path.exists():
        index_path.write_text("<html><body>Preparing...</body></html>", encoding="utf-8")
    return index_path
