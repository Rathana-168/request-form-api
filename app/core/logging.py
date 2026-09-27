import logging

from app.core.config import get_settings


def setup_logging() -> None:
    level = logging.DEBUG if get_settings().DEBUG else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
