#!/usr/bin/env python3
# mypy: disable-error-code=union-attr

import logging
import sys


def get_console_logger() -> logging.Logger:
    """Return a logger for the actual sys.stderr. Works even if
    sys.stderr was redirected.

    Returns:
        logging.Logger: A logger for the original sys.stderr.
    """
    logger = logging.getLogger("ConsoleLogging")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.__stderr__))
    return logger
