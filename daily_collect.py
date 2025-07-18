#!/usr/bin/env python3
"""Run one data collection suitable for cron or another scheduler."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_FILE = PROJECT_ROOT / "daily_collect.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
LOGGER = logging.getLogger("daily_collect")


def main() -> int:
    LOGGER.info("开始执行每日数据收集")
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "get_switch_data.py")],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        LOGGER.info(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            LOGGER.error(result.stderr.rstrip())
        LOGGER.error("数据收集失败，退出码：%s", result.returncode)
        return result.returncode
    LOGGER.info("每日数据收集完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
