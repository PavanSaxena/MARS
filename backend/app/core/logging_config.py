import logging
import sys

def configure_logging() -> None:
    """
        Configures the logging settings for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )