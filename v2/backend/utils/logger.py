# -- Structured logging setup. --
import logging
import sys
from pathlib import Path

LOG_FILE = Path("../logs/leadharvest.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def setup_logging(level: int = logging.INFO):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)
    # Quiet noisy libs
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
