#!/usr/bin/env python3
# mypy: disable-error-code=union-attr
from pathlib import Path
from random import random
from time import sleep
from multiprocessing import current_process
from multiprocessing import Process
from multiprocessing import Queue
from logging.handlers import QueueHandler
import logging
from typing import Union


class ProcessSafeLogging:
    """Process safe logging to a file."""

    PROCESS_SAFE_LOGGER_NAME = "app"

    def __init__(self, file: Union[str, Path] = "log.txt") -> None:
        """Process safe logging to a file.

        Args:
            file (Union[str, Path]): The path of the file that all
                logged messages are written to.
        """
        self._shared_queue = self._start_logger_process()
        self._file = Path(file)

    def _logger_process(self) -> None:
        """Process log messages in the queue. This function should be
        executed in its own process.

        Args:
            queue (Queue): The shared queue where multiple processes log
                to.
        """
        # create a logger
        logger = logging.getLogger(self.PROCESS_SAFE_LOGGER_NAME)

        # configure a formatter
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        f_format = logging.Formatter(log_format)

        # configure a file handler
        f_handler = logging.FileHandler(self._file, mode="a")
        f_handler.setFormatter(f_format)
        f_handler.setLevel(logging.WARNING)

        # add the file handler to the logger
        logger.addHandler(f_handler)

        # log all messages, debug and up
        logger.setLevel(logging.DEBUG)

        # run forever
        while True:
            # consume a log message, block until one arrives
            message = self._shared_queue.get()

            # check for shutdown
            if message is None:
                break

            # log the message
            logger.handle(message)

    def get_logger(
        self, logging_level: Union[int, str] = logging.DEBUG
    ) -> logging.Logger:
        """Return a process safe logger. All process safe loggers'
        messages are written to a single file.

        Args:
            logging_level (Union[int, str], optional): _description_.
                Defaults to logging.DEBUG.

        Returns:
            logging.Logger: A process safe logger.
        """
        # create a logger
        logger = logging.getLogger(self.PROCESS_SAFE_LOGGER_NAME)

        # add a handler that uses the shared queue
        logger.addHandler(QueueHandler(self._shared_queue))

        # log all messages, debug and up
        logger.setLevel(logging_level)

        return logger

    def _start_logger_process(self) -> Queue:
        """Start the process that consumes log messages in the shared
        queue.

        Returns:
            Queue: The shared queue.
        """
        # create the shared queue
        queue: Queue = Queue()

        # start the logger process
        logger_p = Process(target=self._logger_process, args=(queue,))
        logger_p.start()

        return queue

    @property
    def file(self) -> Path:
        """The path of the file that all logged messages are written
        to.
        """
        return self._file


process_safe_logging = ProcessSafeLogging()
