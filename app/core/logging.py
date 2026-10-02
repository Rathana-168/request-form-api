import logging

from app.core.config import get_settings

NOISY = ("httpx", "httpcore", "aiokafka", "asyncio")


def setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,                                    # replace any handlers set earlier
    )
    # your own code: DEBUG when developing
    logging.getLogger("app").setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # SQL: only when asked for, and only through our handler
    sql = logging.getLogger("sqlalchemy.engine")
    sql.setLevel(logging.INFO if settings.DB_ECHO else logging.WARNING)
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine"):
        logging.getLogger(name).handlers.clear()

    for name in NOISY:                                 # third-party chatter
        logging.getLogger(name).setLevel(logging.WARNING)
        

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
