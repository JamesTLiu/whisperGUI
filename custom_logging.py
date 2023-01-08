#!/usr/bin/env python3
# mypy: disable-error-code=union-attr
from pathlib import Path
from random import random
import sys
from time import sleep
from multiprocessing import current_process, Process, Queue, Manager
from logging.handlers import QueueHandler
import logging
from typing import Iterable, Union

from logging_utils import get_console_logger


class ProcessSafeLoggingError(Exception):
    """An error occurred during process safe logging."""


class QueueHandlingProcessLoggerHasHandlers(ProcessSafeLoggingError):
    """The logger for handling the shared queue already has handlers but
    should not. Check if an existing logger was accidentally retrieved.
    """


class ProcessSafeLogging:
    """Process safe logging to a file."""

    LOGGER_NAME = "app"

    _queue_process_id = 1

    def __init__(self, handlers: Iterable[logging.Handler] = ()) -> None:
        """Process safe logging to a file.

        Args:
            handlers (Iterable[logging.Handler], optional): Handlers to
                add to the queue processing logger. If no handlers are
                given, a default filehandler will be used. Defaults to
                ().
        """
        self._handlers = tuple(handlers)
        # self._manager = Manager()
        # self._manager.Queue()
        # self._manager.start()

        self._shared_queue: Queue = Queue()

    def _logger_process(
        self, queue: Queue, handlers: Iterable[logging.Handler]
    ) -> None:
        """Process log messages in the queue. This function should be
        executed in its own process.

        Args:
            queue (Queue): The shared queue where multiple processes log
                to.
            handlers (Iterable[logging.Handler]): Handlers to add to the
                queue processing logger.
        """
        # temp_logger = get_console_logger()
        # temp_logger.info(
        #     f"inside of queue handling process:\n{self._shared_queue}"
        # )

        # create a logger
        logger = logging.getLogger(f"queue_processor{self._queue_process_id}")

        # a logger with handlers was returned
        if logger.hasHandlers():
            raise QueueHandlingProcessLoggerHasHandlers

        # add the handlers to the logger
        for handler in handlers:
            logger.addHandler(handler)

        # No handlers were given. Add the default handler.
        if not logger.hasHandlers():
            logger.addHandler(self._get_default_handler())

        # log all messages, debug and up
        logger.setLevel(logging.DEBUG)

        # run forever
        while True:
            # consume a log message, block until one arrives
            message = queue.get()

            # check for shutdown
            if message is None:
                break

            # log the message
            logger.handle(message)
            # print(f"_logger_process got msg:\n{message}")

    def _get_default_handler(self) -> logging.FileHandler:
        # configure a formatter
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        f_format = logging.Formatter(log_format)

        # Get the default log file number
        log_num = self._queue_process_id if self._queue_process_id > 1 else ""

        # configure a file handler
        f_handler = logging.FileHandler(f"log{log_num}.txt", mode="a")
        f_handler.setFormatter(f_format)
        f_handler.setLevel(logging.DEBUG)
        return f_handler

    def get_logger(
        self, logging_level: Union[int, str, None] = None
    ) -> logging.Logger:
        """Return a process safe logger. All process safe loggers'
        messages are put in a queue for processing.

        Note: Multiple calls in the same process will return the same
        logger and set the logging level each call.

        Args:
            logging_level (Union[int, str, None], optional): The logging
                level of the returned logger. If None, the logging level
                will not be changed. If None and the logger is created,
                the logging level of logging.DEBUG will be used.
                Defaults to None.

        Returns:
            logging.Logger: A process safe logger.
        """
        # create a logger
        logger = logging.getLogger(self.LOGGER_NAME)

        # new logger
        if not logger.handlers:
            # add a handler that uses the shared queue
            logger.addHandler(QueueHandler(self._shared_queue))

            # use the debug logging level if no logging level is given
            if logging_level is None:
                logging_level = logging.DEBUG

        # set a new logging level
        if logging_level is not None:
            logger.setLevel(logging_level)

        return logger

    def start_queue_handling_logger_process(self) -> None:
        """Start the process that consumes log messages in the shared
        queue.
        """
        # temp_logger = get_console_logger()
        # temp_logger.info(
        #     f"outside of queue handling process:\n{self._shared_queue}"
        # )

        # start the logger process
        logger_p = Process(
            target=self._logger_process,
            args=(self._shared_queue, self._handlers),
            daemon=True,
        )
        logger_p.start()
        self._queue_process_id += 1

    def __del__(self) -> None:
        """Shut down the queue handling process."""
        logger = get_console_logger()
        logger.info("ProcessSafeSharedLogging instance deleted.")
        print("blah", file=sys.__stderr__, flush=True)
        self._shared_queue.put(None)

    close = __del__


def get_logger_for_queue(
    queue: Queue, logging_level: Union[int, str, None] = None
) -> logging.Logger:
    """Return a process safe logger. All process safe loggers'
    messages are put in a queue for processing.

    Note: Multiple calls in the same process will return the same
    logger and set the logging level each call.

    Args:
        logging_level (Union[int, str, None], optional): The logging
            level of the returned logger. If None, the logging level
            will not be changed. If None and the logger is created,
            the logging level of logging.DEBUG will be used.
            Defaults to None.

    Returns:
        logging.Logger: A process safe logger.
    """
    # create a logger
    logger = logging.getLogger(f"logger_{queue}")

    # new logger
    if not logger.handlers:
        # add a handler that uses a shared queue
        logger.addHandler(QueueHandler(queue))

        # use the debug logging level if no logging level is given
        if logging_level is None:
            logging_level = logging.DEBUG

    # set a new logging level
    if logging_level is not None:
        logger.setLevel(logging_level)

    return logger


process_safe_logging = ProcessSafeLogging()
