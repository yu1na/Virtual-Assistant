import logging
from pathlib import Path
import uuid


def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def ensure_dir(path: Path | str) -> None:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)


def generate_uuid(prefix: str = "ins") -> str:
    return f"{prefix}_{uuid.uuid4()}"