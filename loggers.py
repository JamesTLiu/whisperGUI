#!/usr/bin/env python3
# mypy: disable-error-code=union-attr
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

f_handler = logging.FileHandler("log.txt", mode="a")
f_handler.setLevel(logging.WARNING)

log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

f_format = logging.Formatter(log_format)

f_handler.setFormatter(f_format)

logger.addHandler(f_handler)
