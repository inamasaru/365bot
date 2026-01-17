from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from collector.run import run as collector_run  # noqa: E402
from kpi.run import run as kpi_run  # noqa: E402
from optimizer.run import run as optimizer_run  # noqa: E402
from generator.run import run as generator_run  # noqa: E402
from deployer.run import run as deployer_run  # noqa: E402
from reporter.run import run as reporter_run  # noqa: E402


def run_pipeline(base_dir: Path) -> None:
    collector_run(base_dir)
    kpi_run(base_dir)
    optimizer_run(base_dir)
    generator_run(base_dir)
    deployer_run(base_dir)
    reporter_run(base_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="run", choices=["run"])
    args = parser.parse_args()

    if args.mode == "run":
        run_pipeline(BASE_DIR)


if __name__ == "__main__":
    main()
