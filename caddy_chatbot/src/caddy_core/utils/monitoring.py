import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()


debug_enabled = os.environ.get("DEBUG", False)
logger_level = logging.INFO

if debug_enabled:
    logger_level = logging.DEBUG


class Colours:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class ColourFormatter(logging.Formatter):
    COLOURS = {
        "DEBUG": Colours.BLUE,
        "INFO": Colours.MAGENTA,
        "WARNING": Colours.YELLOW,
        "ERROR": Colours.RED,
        "CRITICAL": Colours.BOLD + Colours.RED,
    }

    def format(self, record):
        log_message = super().format(record)
        return f"{self.COLOURS.get(record.levelname, '')}{log_message}{Colours.RESET}"


def setup_logger(name, level=logger_level):
    """
    Function to setup a colour-coded logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = ColourFormatter("%(name)s | %(asctime)s | %(levelname)s | %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logger("CADDY")
