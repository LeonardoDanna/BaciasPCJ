from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


def setup_logging(output_dir: Path) -> tuple[logging.Logger, Path]:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"monitor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger("pcj_monitor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)
    return logger, log_path

