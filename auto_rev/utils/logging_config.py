from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(level: int = logging.INFO, stream: Optional[object] = None) -> None:
    if logging.getLogger().handlers:
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        stream=stream or sys.stdout,
    )
