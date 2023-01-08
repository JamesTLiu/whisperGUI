#!/usr/bin/env python3
# mypy: disable-error-code=union-attr

from __future__ import annotations

import base64
import inspect
import io
import multiprocessing
import platform
import random
import re
import signal
import sys
import threading
import time
import tkinter as tk
import traceback
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from itertools import islice, zip_longest
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as EventClass
from operator import itemgetter
from pathlib import Path
from pprint import pformat
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Type,
    TypeAlias,
    Union,
)

import PIL.Image
import PySimpleGUI as sg
import whisper
from codetiming import Timer, TimerError
from whisper.tokenizer import LANGUAGES as TO_LANGUAGE
from whisper.tokenizer import TO_LANGUAGE_CODE
from whisper.utils import write_srt, write_txt, write_vtt


if TYPE_CHECKING:
    from types import FrameType

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import (  # type: ignore
        Connection as PipeConnection,
    )

from utils import (
    CustomTimer,
    OutputRedirector,
    close_connections,
    get_traceback,
    popup_on_error,
)

from loguru import logger


class Transcriber:
    """A manager for transcription tasks."""

    def __init__(self) -> None:
        self.is_transcribing = False
        self._transcription_timer = CustomTimer()
        self.num_tasks = 0
        self.num_tasks_done = 0

        self.translate_to_english = False

        # Paths for the users selected audio video files to transcribe
        self.audio_video_file_paths: Tuple = tuple()

        # Thread that runs transcriptions as new processes
        self.transcribe_thread: Optional[threading.Thread] = None

        # Stop flag for the thread
        self.stop_transcriptions_flag = threading.Event()

    def _start_timer(self) -> None:
        """Start the timer for a new set of transcription tasks.

        Raises:
            TimerError: Timer is already running.
        """
        self._transcription_timer.start()

    def _stop_timer(self, log_time: bool = False) -> float:
        """Stop the timer for the current set of transcription tasks and
        optionally report the elapsed time.

        Args:
            log_time (bool, optional): If True, prints the elapsed time
                for the current set of transcription tasks. Defaults to
                False.

        Raises:
            TimerError: Timer is not running.

        Returns:
            float: The elapsed time in seconds for the current set of
                transcription tasks.
        """
        return self._transcription_timer.stop(log_time=log_time)

    def start(
        self,
        window: sg.Window,
        audio_video_file_paths: Iterable[str],
        output_dir_path: str,
        language: Optional[str],
        model: str,
        translate_to_english: bool,
        use_language_code: bool,
        initial_prompt: str,
    ) -> None:
        """Start transcribing the audio / video files.

        Args:
            audio_video_file_paths (Iterable[str]): File paths of the
                audio / video files selected by the user for
                transcription.
            window (sg.Window): The window the transcription thread will
                send events (including events with redirected stdout /
                stderr output) to.
            output_dir_path (str): The directory path where
                transcriptions will be written.
            language (Optional[str]): The language of the
                file(s) to transcribe. If None, it will be autodetected
                per file.
            model (str): The whisper model to use for
                transcription.
            translate_to_english (bool): If True, each transcription
                will be translated to English. Otherwise, no translation
                will occur.
            use_language_code (bool): If True, the detected language's
                language code will be used in the output file name if
                possible. Otherwise, the detected language's name will
                be used in the output file name if possible.
            initial_prompt (str): User provided text that guides the
                transcription to a certain dialect/language/style.
                Defaults to None.
        """
        self.audio_video_file_paths = tuple(audio_video_file_paths)
        self.num_tasks = len(self.audio_video_file_paths)

        # Start transcription in separate thread
        self.transcribe_thread = threading.Thread(
            target=transcribe_audio_video_files,
            kwargs={
                "window": window,
                "audio_video_file_paths": self.audio_video_file_paths,
                "output_dir_path": output_dir_path,
                "language": language,
                "model": model,
                "success_event": GenEvents.TRANSCRIBE_SUCCESS,
                "fail_event": GenEvents.TRANSCRIBE_ERROR,
                "progress_event": GenEvents.TRANSCRIBE_PROGRESS,
                "process_stopped_event": GenEvents.TRANSCRIBE_STOPPED,
                "print_event": GenEvents.PRINT_ME,
                "stop_flag": self.stop_transcriptions_flag,
                "translate_to_english": translate_to_english,
                "use_language_code": use_language_code,
                "initial_prompt": initial_prompt,
            },
            daemon=True,
        )

        with popup_on_error(TimerError):
            self._start_timer()

        self.transcribe_thread.start()
        self.is_transcribing = True

    def stop(self) -> None:
        """Signal the thread to stop transcribing. It may take some time
        for transcription to stop."""
        self.stop_transcriptions_flag.set()

    def done(self, success: bool) -> float:
        """Set the manager to wait for new tasks.

        Args:
            success (bool): If True, transcriptions succeeded.

        Raises:
            TimerError: Timer is not running.

        Returns:
            float: The elapsed time in seconds for the completed set of
                transcriptions.
        """
        self.is_transcribing = False
        self.num_tasks = 0
        self.num_tasks_done = 0
        self.transcribe_thread = None
        self.stop_transcriptions_flag.clear()

        elapsed_time = self._stop_timer(log_time=success)
        return elapsed_time

    def is_stopping(self) -> bool:
        """Return whether the transcriptions are in the process of
        stopping.

        Returns:
            bool: True if the transcriptions are in the process of
                stopping.
        """
        return self.stop_transcriptions_flag.is_set()

    @property
    def current_file(self) -> str:
        """The current file being transcribed."""
        current_file = "None"

        if self.num_tasks_done < self.num_tasks:
            current_file = self.audio_video_file_paths[self.num_tasks_done]

        # if self.num_tasks_done <= self.num_tasks:
        #     current_file = self.audio_video_file_paths[self.num_tasks_done]

        return current_file


def transcribe_audio_video_files(
    window: sg.Window,
    audio_video_file_paths: Iterable[str],
    output_dir_path: str,
    language: Optional[str],
    model: str,
    success_event: str,
    fail_event: str,
    progress_event: str,
    process_stopped_event: str,
    print_event: str,
    stop_flag: threading.Event,
    translate_to_english: bool = False,
    use_language_code: bool = False,
    initial_prompt: str = None,
) -> None:
    """Transcribe a list of audio/video files.

    Results are written to files with the same name but with .txt, .vtt,
    and .srt extensions.

    Args:
        window (sg.Window): The window to send events (including events
            with redirected stdout / stderr output) to.
        audio_video_file_paths (Iterable[str]): File paths of the
            audio / video files selected by the user for
            transcription.
        output_dir_path (str): The directory path where transcriptions
            will be written.
        language (Optional[str]): The language of the file(s) to
            transcribe. If None, it will be autodetected per file.
        model (str): The whisper model to use for transcription.
        success_event (str): The event to send to the window when all
            transcriptions are successful.
        fail_event (str): The event to send to the window on
            transcription failure.
        progress_event (str): The event to send to the window on a
            transcription success.
        process_stopped_event (str): The event to send to the window
            after stopping the process because the stop flag is set.
        print_event (str): The event to send to the window to print a
            string.
        stop_flag (threading.Event): The flag that causes transcription
            to abort when it's set.
        translate_to_english (bool): If True, each transcription will be
            translated to English. Otherwise, no translation will occur.
        use_language_code (bool): If True, the detected language's
            language code will be used in the output file name if
            possible. Otherwise, the detected language's name will be
            used in the output file name if possible.
        initial_prompt (str, optional): User provided text that guides
            the transcription to a certain dialect/language/style.
            Defaults to None.
    """

    # logger = process_safe_logging.get_logger()
    # logger.info("in transcribe_audio_video_files()")
    # Paths for the transcription result files
    all_output_paths: List[str] = []

    # pipe for stdout and stderr output in a child process
    read_connection, write_connection = multiprocessing.Pipe()

    for audio_video_path in audio_video_file_paths:
        # pass results from the child process through here
        mp_queue: multiprocessing.Queue = multiprocessing.Queue()

        # Process will set this flag when it's done
        process_done_flag = multiprocessing.Event()

        # Start transcription of the file in a process
        process = multiprocessing.Process(
            target=transcribe_audio_video,
            kwargs={
                "language": language,
                "model": model,
                "audio_video_path": audio_video_path,
                "queue": mp_queue,
                "write_connection": write_connection,
                "process_done_flag": process_done_flag,
                "translate_to_english": translate_to_english,
                "initial_prompt": initial_prompt,
            },
            daemon=True,
        )
        process.start()

        def send_piped_output_to_window(
            win: sg.Window, conn: Union[Connection, PipeConnection]
        ) -> None:
            """Send the contents in a connection to a window as a print
            event.

            Args:
                win (sg.Window): The window to write the print event to.
                conn (Union[Connection, PipeConnection]): The connection
                    to read from.
            """
            win.write_event_value(print_event, str(conn.recv()))

        # Transcribing
        while not process_done_flag.is_set():
            # Main thread has set the stop flag. Stop the process, wait
            # for it to join, and return.
            if stop_flag.is_set():
                process.terminate()
                close_connections((read_connection, write_connection))
                process.join()
                window.write_event_value(
                    process_stopped_event,
                    "Transcription stopped due to stop flag.",
                )
                return

            # Print the stdout stderr output piped from the process
            while read_connection.poll():
                send_piped_output_to_window(window, read_connection)

        # Finish sending piped output from the process to the window
        while read_connection.poll():
            send_piped_output_to_window(window, read_connection)

        # Get the result from transcribing the file
        result = mp_queue.get()

        # Handle a possible Exception in the process
        if isinstance(result, Exception):
            window.write_event_value(
                fail_event,
                "\n".join(
                    (
                        "An error occurred while transcribing the file.",
                        get_traceback(result),
                    )
                ),
            )
            close_connections((read_connection, write_connection))
            return

        # Write transcription results to files
        output_paths = write_transcript_to_files(
            transcribe_result=result,
            audio_path=audio_video_path,
            output_dir_path=output_dir_path,
            language_code_as_specifier=use_language_code,
            is_translated_to_english=translate_to_english,
        )

        # Track the paths for the transcription result files
        all_output_paths.extend(output_paths)

        # Tell the GUI that 1 transcription is completed
        window.write_event_value(progress_event, "")

    # close connections for the pipe
    close_connections((read_connection, write_connection))

    # Tell the GUI that all transcriptions are completed
    window.write_event_value(success_event, all_output_paths)


def transcribe_audio_video(
    language: Optional[str],
    model: str,
    audio_video_path: str,
    queue: multiprocessing.Queue,
    write_connection: Union[Connection, PipeConnection],
    process_done_flag: EventClass,
    translate_to_english: bool = False,
    initial_prompt: str = None,
) -> None:
    """Transcribe an audio/video file.

    Args:
        language (Optional[str]): The language of the file(s) to
            transcribe. If None, it will be autodetected per file.
        model (str): The whisper model to use for transcription.
        audio_video_path (str): An audio/video file path.
        queue (multiprocessing.Queue): The queue that the results of the
            transcription will be put in.
        write_connection (Union[Connection, PipeConnection]): A
            writeable Connection to redirect prints into.
        process_done_flag (EventClass): The flag that signals process
            completion to the parent thread.
        translate_to_english (bool): True if the user has chosen to
            translate the transcription to English, False otherwise.
        initial_prompt (str, optional): User provided text that guides
            the transcription to a certain dialect/language/style.
            Defaults to None.
    """
    redirector = OutputRedirector(write_connection)

    # Clean up when this process is told to terminate
    def handler(sig: int, frame: Optional[FrameType] = None) -> None:
        queue.close()
        nonlocal redirector
        del redirector
        write_connection.close()
        # end the process
        sys.exit(0)

    # handle sigterm
    signal.signal(signal.SIGTERM, handler)

    whisper_model = whisper.load_model(model)

    print(f"\nTranscribing file: {audio_video_path}", end="\n\n")

    if translate_to_english:
        task = "translate"
    else:
        task = "transcribe"

    try:
        raise Exception(f"{__file__}")
    except Exception as e:
        logger.exception(e)

    test()

    # Transcribe the file
    try:
        result = whisper_model.transcribe(
            audio=audio_video_path,
            verbose=False,
            language=language,
            beam_size=5,
            best_of=5,
            task=task,
            initial_prompt=initial_prompt,
        )
    except Exception as e:
        # logger.exception(e)
        queue.put(e)
        raise

    # Pass the result out
    queue.put(result)

    # Clean up
    write_connection.close()
    del redirector
    queue.close()

    # Signal process completion to the parent thread
    process_done_flag.set()


def test():
    try:
        raise Exception(f"{__file__}")
    except Exception as e:
        logger.exception(e)

    logger.debug("TEST DEBUG")
    logger.info("TEST INFO")
    logger.warning("TEST WARNING")
    logger.error("TEST ERROR")
    logger.critical("TEST CRITICAL")


def write_transcript_to_files(
    transcribe_result: Dict[str, Union[dict, Any, str]],
    audio_path: str,
    output_dir_path: str,
    language_code_as_specifier: bool,
    is_translated_to_english: bool,
) -> Tuple[str, str, str]:
    """Write the results of a whisper transcription to .txt, .vtt, and
    .srt files with the same name as the source file and a language
    specifier.

    Output file format: [filename].[language specifier].[txt/vtt/srt]

    Example output files for my_video.mp4:
        my_video.[language specifier].txt
        my_video.[language specifier].vtt
        my_video.[language specifier].srt

    Args:
        transcribe_result (Dict[str, Union[dict, Any]]): The results of
            a whisper transcription.
        audio_path (str): The file path of the source audio/video file.
        output_dir_path (str): The directory to write the transcription
            result files to.
        language_code_as_specifier (bool): If True, the detected
            language's language code will be used in the output file
            name if possible. Otherwise, the detected language's name
            will be used in the output file name if possible.
        is_translated_to_english (bool): If True, the result was
            translated into English.

    Returns:
        Tuple[str, str, str]: A Tuple with the file paths for the
            transcription result files.
    """
    output_dir = Path(output_dir_path)
    audio_basename = Path(audio_path).stem

    language_specifier = str(transcribe_result["language"]).strip()

    # A translated result will be in English even though the detected
    # language may be different
    if is_translated_to_english:
        language_specifier = "english"

    # Try to convert language specifier to the selected type
    to_language_specifier_type = (
        TO_LANGUAGE_CODE if language_code_as_specifier else TO_LANGUAGE
    )

    language_specifier = to_language_specifier_type.get(
        language_specifier, language_specifier
    )

    def write_transcript(
        write_fn: Callable[[Iterator[dict], TextIO], None],
        transcript: Iterator[dict],
        language_specifier: str,
        file_suffix: str,
    ) -> str:
        """Write a transcript to a file.

        Args:
            write_fn (Callable[[Iterator[dict], TextIO], None]): A
                Callable that writes a transcript to a file.
            transcript (Iterator[dict]): The segment-level details from
                a transcription result.
            language_specifier (str): The language specifier to put in
                the file's name.
            file_suffix (str): The extension for the file.

        Returns:
            str: Name of the resulting file.
        """
        with open(
            output_dir
            / "".join((audio_basename, ".", language_specifier, file_suffix)),
            "w",
            encoding="utf-8",
        ) as file:
            write_fn(transcript, file)
            return file.name

    transcript: Iterator[dict] = transcribe_result["segments"]  # type: ignore
    srt_path = write_transcript(
        write_srt, transcript, language_specifier, ".srt"
    )
    txt_path = write_transcript(
        write_txt, transcript, language_specifier, ".txt"
    )
    vtt_path = write_transcript(
        write_vtt, transcript, language_specifier, ".vtt"
    )
    return (srt_path, txt_path, vtt_path)


class GenEvents:
    """Manually generated events."""

    # Events for threads to report status
    TRANSCRIBE_SUCCESS = "-TRANSCRIBE-SUCCESS-"
    TRANSCRIBE_ERROR = "-TRANSCRIBE-ERROR-"
    TRANSCRIBE_PROGRESS = "-TRANSCRIBE-PROGRESS-"
    TRANSCRIBE_STOPPED = "-TRANSCRIBE-STOPPED-"

    # Event for threads to pass objects to print
    PRINT_ME = "-PRINT-ME-"

    # Events that indicate that transcription has ended
    TRANSCRIBE_DONE_NO_SUCCESS_EVENTS = (
        TRANSCRIBE_ERROR,
        TRANSCRIBE_STOPPED,
    )
