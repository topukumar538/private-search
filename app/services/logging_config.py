import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Third-party loggers that would write request URLs, and therefore search
# queries, into our logs. Only their warnings and errors are kept.
QUIET_LOGGERS = ("httpx", "httpcore")


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)

    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)