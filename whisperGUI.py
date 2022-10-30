#!/usr/bin/env python3

import decimal
import multiprocessing
import os
import platform
import re
import shlex
import subprocess
import sys
import threading
import time
from contextlib import suppress
from decimal import Decimal
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as EventClass
from pathlib import Path
from signal import SIGTERM, signal
from tkinter import Button
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import Connection as PipeConnection  # type: ignore


import PySimpleGUI as sg
import whisper
from codetiming import Timer, TimerError
from whisper.tokenizer import TO_LANGUAGE_CODE, LANGUAGES as TO_LANGUAGES
from whisper.utils import write_srt, write_txt, write_vtt

import set_env


def main():
    set_env.set_env_vars()
    start_GUI()


def start_GUI():
    sg.theme("Dark Blue 3")

    # Keys for main tab
    multiline_key = "-CONSOLE-OUTPUT-"
    in_file_key = "-IN-FILE-"
    out_dir_key = "-OUT-FOLDER-"
    out_dir_field_key = "-OUT-FOLDER-FIELD-"
    language_key = "-LANGUAGE-"
    language_text_key = "-LANGUAGE-TEXT-"
    model_key = "-MODEL-"
    model_text_key = "-MODEL-TEXT-"
    translate_to_english_text_key = "-TRANSLATE-OPTION-TEXT-"
    translate_to_english_checkbox_key = "-CHECKBOX-TRANSLATE-"
    model_info_toggle_key = "-TOGGLE-MODEL-TABLE-"
    model_info_table_key = "-MODEL-TABLE-"
    start_key = "-START-"
    progress_key = "-PROGRESS-"

    # Keys for settings tab
    save_settings_key = "-SAVE-SETTINGS-"
    scaling_input_setting_key = "-GLOBAL-SCALING-"
    save_output_dir_text_key = "-SAVE-OUTPUT-DIR-OPTION-TEXT-"
    save_output_dir_checkbox_key = "-CHECKBOX-SAVE-OUTPUT-DIR-"
    language_code_text_setting_key = "-LANGUAGE-CODE-SPECIFIER-OPTION-TEXT-"
    language_code_checkbox_setting_key = "-CHECKBOX-LANGUAGE-CODE-SPECIFIER-OPTION-"

    # Keys for tabs
    main_tab_key = "-MAIN-TAB-"
    settings_tab_key = "-SETTINGS-TAB-"

    # Events for threads to report status
    TRANSCRIBE_SUCCESS = "-TRANSCRIBE-SUCCESS-"
    TRANSCRIBE_ERROR = "-TRANSCRIBE-ERROR-"
    TRANSCRIBE_PROGRESS = "-TRANSCRIBE-PROGRESS-"
    TRANSCRIBE_STOPPED = "-TRANSCRIBE-STOPPED-"

    # Event for threads to pass objects to print
    PRINT_ME = "-PRINT-ME-"

    # Events that indicate that transcription has ended
    TRANSCRIBE_DONE_EVENTS = (TRANSCRIBE_SUCCESS, TRANSCRIBE_ERROR, TRANSCRIBE_STOPPED)

    # scaling of the application's size
    DEFAULT_GLOBAL_SCALING = 1.5

    # Range of accepted scaling factor values from the user
    MIN_SCALING = 0.5
    MAX_SCALING = 3

    # Default global font for the GUI
    GUI_FONT = ("Arial", 20)

    # Config file
    config_file_path = sg.user_settings_filename(filename="whisperGUI.config")

    # Set global GUI options
    sg.set_options(
        scaling=sg.user_settings_get_entry(
            scaling_input_setting_key, DEFAULT_GLOBAL_SCALING
        ),
        font=GUI_FONT,
        tooltip_font=GUI_FONT,
    )

    # number of rows for the table
    num_table_rows = 5

    # height of the multiline element showing console output when the table is not shown
    multiline_height = 15

    # whether multiline element strips whitespaces from the end of the new text to append
    is_multiline_rstripping_on_update = False

    # Image data for toggle button
    toggle_btn_off = b"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"
    toggle_btn_on = b"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"

    # Image data for fancy checkbox
    checked_box_image = b"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"
    unchecked_box_image = b"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"

    # whether the table is shown
    is_table_shown = False

    # tracked windows
    tracked_windows: Set[sg.Window] = set()

    def fancy_checkbox(
        text: str,
        text_key: str,
        checkbox_key: str,
        checked: bool = False,
        checkbox_before_text: bool = False,
        text_tooltip: str = None,
    ) -> List[sg.Element]:
        """Return the PySimpleGUI elements for a fancy checkbox with text.

        Args:
            text (str): Text for the PySimpleGUI Text element that goes with the checkbox.
            text_key (str): The key to assign the PySimpleGUI Text element that goes with the checkbox
            checkbox_key (str): The key to assign the PySimpleGUI Image element which represents the checkbox.
            checked (bool, optional): If True, starts the checkbox checked. Defaults to False.
            checkbox_before_text (bool, optional): Put the checkbox before (to the left) of the text. Defaults to False.

        Returns:
            List[sg.Element]: A list with the PySimpleGUI elements that make up a fancy checkbox.
        """
        checkbox_elements = [
            sg.Text(
                text,
                key=text_key,
                tooltip=text_tooltip,
            ),
            sg.Image(
                checked_box_image if checked else unchecked_box_image,
                key=checkbox_key,
                metadata=checked,
                enable_events=True,
            ),
        ]

        # Flip the element order to put the checkbox before (to the left) of the text
        if checkbox_before_text:
            checkbox_elements.reverse()

        return checkbox_elements

    def make_main_window() -> sg.Window:
        # Supported language options for the model
        AUTODETECT_OPTION = "autodetect"
        LANGUAGES = (AUTODETECT_OPTION, *sorted(TO_LANGUAGE_CODE.keys()))

        # Information for the table comparing models
        model_data_table = [
            [
                "Size",
                "Parameters",
                "English-only",
                "Multilingual",
                "Needed VRAM",
                "Relative speed",
            ],
            ["tiny", "39 M", "tiny.en", "tiny", "~1 GB", "~32x"],
            ["base", "74 M", "base.en", "base", "~1 GB", "~16x"],
            ["small", "244 M", "small.en", "small", "~2 GB", "~6x"],
            ["medium", "769 M", "medium.en", "medium", "~5 GB", "~2x"],
            ["large", "1550 M", "N/A", "large", "~10 GB", "1x"],
        ]

        # list of available whisper models
        models = whisper.available_models()

        # default to base model
        DEFAULT_MODEL = models[3]

        # Append whitespace to each table header string to avoid cutoffs
        table_headings = [
            str(model_data_table[0][x]) + "  " for x in range(len(model_data_table[0]))
        ]

        # Load whether to translating to English or not from the settings file
        translate_to_english_last_choice = sg.user_settings_get_entry(
            translate_to_english_checkbox_key, False
        )

        # Load whether to save the output directory or not from the settings file
        save_output_dir = sg.user_settings_get_entry(
            save_output_dir_checkbox_key, False
        )

        # Load whether to use a language code as the specifier in the output filename or not from the settings file
        use_language_code = sg.user_settings_get_entry(
            language_code_checkbox_setting_key, False
        )

        # main tab
        tab1_layout = [
            [sg.Text("Select audio/video file(s)")],
            [sg.Input(disabled=True, expand_x=True), sg.FilesBrowse(key=in_file_key)],
            [sg.Text("Output folder:")],
            [
                sg.Input(
                    default_text=sg.user_settings_get_entry(out_dir_key, ""),
                    key=out_dir_field_key,
                    disabled=True,
                    expand_x=True,
                    enable_events=True,
                ),
                sg.FolderBrowse(
                    target=out_dir_field_key,
                    key=out_dir_key,
                    initial_folder=sg.user_settings_get_entry(out_dir_key),
                ),
            ],
            [
                sg.Text("Language:", key=language_text_key),
                sg.Combo(
                    values=LANGUAGES,
                    key=language_key,
                    default_value=sg.user_settings_get_entry(
                        language_key, AUTODETECT_OPTION
                    ),
                    auto_size_text=True,
                    readonly=True,
                    enable_events=True,
                ),
            ],
            [
                sg.Text("Transcription Model:", key=model_text_key),
                sg.Combo(
                    values=models,
                    key=model_key,
                    default_value=sg.user_settings_get_entry(model_key, DEFAULT_MODEL),
                    auto_size_text=True,
                    readonly=True,
                    enable_events=True,
                ),
            ],
            fancy_checkbox(
                text="Translate all results to English",
                text_key=translate_to_english_text_key,
                checkbox_key=translate_to_english_checkbox_key,
                checked=translate_to_english_last_choice,
            ),
            [
                sg.Text("Model Information"),
                sg.Button(
                    "",
                    image_data=toggle_btn_off,
                    key=model_info_toggle_key,
                    button_color=(
                        sg.theme_background_color(),
                        sg.theme_background_color(),
                    ),
                    border_width=0,
                ),
            ],
            [
                sg.pin(
                    sg.Table(
                        values=model_data_table[1:][:],
                        headings=table_headings,
                        max_col_width=25,
                        auto_size_columns=True,
                        justification="center",
                        num_rows=num_table_rows,
                        alternating_row_color="LightBlue3",
                        key=model_info_table_key,
                        selected_row_colors="black on white",
                        enable_events=True,
                        expand_x=True,
                        expand_y=True,
                        vertical_scroll_only=False,
                        hide_vertical_scroll=True,
                        visible=is_table_shown,
                    ),
                    expand_x=True,
                )
            ],
            [
                sg.Multiline(
                    key=multiline_key,
                    size=(70, multiline_height),
                    background_color="black",
                    text_color="white",
                    auto_refresh=True,
                    autoscroll=True,
                    reroute_stderr=True,
                    reroute_stdout=True,
                    reroute_cprint=True,
                    write_only=True,
                    echo_stdout_stderr=True,
                    # echo_stdout_stderr=False,
                    disabled=True,
                    rstrip=is_multiline_rstripping_on_update,
                    expand_x=True,
                    expand_y=True,
                )
            ],
        ]

        # settings tab
        tab2_layout = [
            [sg.Text("Program Settings", font=(GUI_FONT[0], 30))],
            [sg.HorizontalSeparator()],
            [
                sg.Text(
                    "Make the application larger or smaller.", font=(GUI_FONT[0], 22)
                )
            ],
            [
                sg.Text(f"Size multiplier ({MIN_SCALING} to {MAX_SCALING}):"),
                sg.Input(
                    sg.user_settings_get_entry(
                        scaling_input_setting_key, DEFAULT_GLOBAL_SCALING
                    ),
                    size=(5),
                    key=scaling_input_setting_key,
                ),
                # sg.Text("(2 is double size. 0.5 is half size)"),
            ],
            [sg.HorizontalSeparator()],
            [sg.Text(f"Settings file location:")],
            [sg.Text(f"{config_file_path}", relief=sg.RELIEF_SOLID)],
            [sg.HorizontalSeparator()],
            fancy_checkbox(
                text="Remember output directory",
                text_key=save_output_dir_text_key,
                checkbox_key=save_output_dir_checkbox_key,
                checked=save_output_dir,
            ),
            [sg.HorizontalSeparator()],
            fancy_checkbox(
                text="Use language code instead of language in output filenames",
                text_key=language_code_text_setting_key,
                checkbox_key=language_code_checkbox_setting_key,
                checked=use_language_code,
                text_tooltip="Ex. 'video.en.txt' instead of 'video.english.txt'",
            ),
            [sg.Button("Save settings", key=save_settings_key)],
        ]

        # Define the window's contents
        layout = [
            [
                sg.TabGroup(
                    [
                        [
                            sg.Tab(
                                "Main",
                                tab1_layout,
                                key=main_tab_key,
                            ),
                            sg.Tab(
                                "Settings",
                                tab2_layout,
                                key=settings_tab_key,
                            ),
                        ]
                    ],
                    tab_location="topright",
                    expand_x=True,
                    expand_y=True,
                )
            ],
            [
                sg.StatusBar(
                    "Powered by OpenAI Whisper Speech Recognition System",
                    auto_size_text=True,
                    justification="center",
                ),
                sg.Push(),
                sg.Button("Start", key=start_key, auto_size_button=True),
            ],
        ]

        # Create the window
        window = sg.Window(
            "whisperGUI - transcribe audio/video to text",
            layout,
            finalize=True,
            resizable=True,
            auto_size_buttons=True,
            auto_size_text=True,
        )

        # Load the FolderBrowse's selected folder from the settings file
        # (Needed until an arg for FolderBrowse adds this functionality)
        window[out_dir_key].TKStringVar.set(sg.user_settings_get_entry(out_dir_key, ""))

        # align language and model text by setting them to the same width
        set_same_width(
            window, (language_text_key, model_text_key, translate_to_english_text_key)
        )

        return window

    def make_main_window_tracked() -> sg.Window:
        window = make_main_window()
        tracked_windows.add(window)
        return window

    window = make_main_window_tracked()

    # timer for transcription task
    transcription_timer = CustomTimer()

    # tracks if transcription is in progress
    is_transcribing = False

    # holds paths for the users selected audio video files
    audio_video_file_paths = []

    # current transcription task being worked on
    num_tasks_done = None

    # total number of transcription tasks
    num_tasks = None

    # thread that runs transcriptions as processes
    transcribe_thread = None

    # stop flag for the thread
    stop_flag = threading.Event()

    while True:
        # Display and interact with the Window
        event, values = window.read(timeout=10)

        if event in (sg.WIN_CLOSED, "Exit"):
            # Tell the thread to end the ongoing transcription
            if transcribe_thread:
                print("Window closed but transcription is in progress.")
                stop_flag.set()
            break
        elif event == PRINT_ME:
            print(values[PRINT_ME], end="")
        elif event == out_dir_field_key:
            # Save the output directory when setting is on
            if sg.user_settings_get_entry(save_output_dir_checkbox_key):
                sg.user_settings_set_entry(out_dir_key, values[out_dir_key])
        # User selected a language
        elif event == language_key:
            # Save the choice to the config file
            sg.user_settings_set_entry(language_key, values[language_key])
        # User selected a model
        elif event == model_key:
            # Save the choice to the config file
            sg.user_settings_set_entry(model_key, values[model_key])
        # User clicked a checkbox
        elif "-CHECKBOX" in event:
            window[event].metadata = not window[event].metadata
            window[event].update(
                checked_box_image if window[event].metadata else unchecked_box_image
            )

            # Save the checkbox state to the config file
            save_checkbox_state(window, translate_to_english_checkbox_key)
        # User saved settings
        elif event == save_settings_key:

            def popup_tracked_scaling_invalid():
                popup_tracked(
                    f"Please enter a number for the scaling factor between {MIN_SCALING} and {MAX_SCALING}.",
                    popup_fn=popup,
                    tracked_windows=tracked_windows,
                    title="Invalid scaling factor",
                )

            # Ensure the scaling input is a decimal
            try:
                scaling_input = Decimal(values[scaling_input_setting_key])
            except decimal.InvalidOperation:
                popup_tracked_scaling_invalid()
            else:
                # Ensure scaling factor is within accepted range
                if Decimal(MIN_SCALING) <= scaling_input <= Decimal(MAX_SCALING):
                    # Save the settings to the config file
                    sg.user_settings_set_entry(
                        scaling_input_setting_key, values[scaling_input_setting_key]
                    )

                    # Use the new scaling globally
                    sg.set_options(
                        scaling=sg.user_settings_get_entry(
                            scaling_input_setting_key, DEFAULT_GLOBAL_SCALING
                        )
                    )
                # Scaling factor is out of accepted range
                else:
                    popup_tracked_scaling_invalid()

            # Update save output directory setting
            is_saving_output_directory = window[save_output_dir_checkbox_key].metadata
            save_checkbox_state(window, save_output_dir_checkbox_key)

            # Delete the saved output directory in the settings file if not saving output directory
            if not is_saving_output_directory:
                if sg.user_settings_get_entry(out_dir_key, None):
                    sg.user_settings_delete_entry(out_dir_key)

            # Update use language code as specifier setting
            save_checkbox_state(window, language_code_checkbox_setting_key)

            # Close all windows and remove them from tracking
            for win in tracked_windows:
                win.close()
            tracked_windows.clear()

            # Remake the window and go back to the settings tab
            window = make_main_window_tracked()
            window[settings_tab_key].select()
        # User pressed toggle button for the table
        elif event == model_info_toggle_key:
            is_table_shown = not is_table_shown

            # Update the toggle button's image
            if is_table_shown:
                toggle_image = toggle_btn_on
            else:
                toggle_image = toggle_btn_off

            window[model_info_toggle_key].update(image_data=toggle_image)

            # Show/hide the table
            window[model_info_table_key].update(visible=is_table_shown)

            # Update multine element's height based on whether the table is showing
            new_multiline_height = multiline_height

            if is_table_shown:
                new_multiline_height -= num_table_rows

            window[multiline_key].set_size((None, new_multiline_height))
        # User wants to start transcription
        elif event == start_key:
            # Get user provided paths for the video file and output directory
            audio_video_file_paths_str = str(values[in_file_key]).strip()
            output_dir_path = str(values[out_dir_key]).strip()

            # Require audio/video file(s) and output folder
            if not audio_video_file_paths_str or not output_dir_path:
                popup_tracked(
                    f"Please select audio/video file(s) and an output folder.",
                    popup_fn=popup,
                    tracked_windows=tracked_windows,
                    title="Missing selections",
                )
                continue

            # Disable buttons during transcription
            disable_elements(
                (
                    window[start_key],
                    window[save_settings_key],
                    window[out_dir_key],
                    window[in_file_key],
                )
            )

            # Get user selected language and model
            language_selected = values[language_key]
            if language_selected not in TO_LANGUAGE_CODE:
                language_selected = None

            model_selected = values[model_key]

            # Get the user's choice of whether to translate the results into english
            translate_to_english = window[translate_to_english_checkbox_key].metadata

            # Get the user's choice of whether to use a language code as the language specifier in output files
            language_code_as_specifier = sg.user_settings_get_entry(
                language_code_checkbox_setting_key, False
            )

            # Ensure timer is not running
            with suppress(TimerError):
                transcription_timer.stop()

            # Clear the console output element
            window[multiline_key].update("")
            window.refresh()

            # Convert string with file paths into a list
            audio_video_file_paths = list(str_to_file_paths(audio_video_file_paths_str))

            # Setup for task progress
            num_tasks_done = 0
            num_tasks = len(audio_video_file_paths)

            transcription_timer.start()

            # Start transcription
            transcribe_thread = threading.Thread(
                target=transcribe_audio_video_files,
                kwargs={
                    "window": window,
                    "audio_video_file_paths": audio_video_file_paths,
                    "output_dir_path": output_dir_path,
                    "language": language_selected,
                    "model": model_selected,
                    "success_event": TRANSCRIBE_SUCCESS,
                    "fail_event": TRANSCRIBE_ERROR,
                    "progress_event": TRANSCRIBE_PROGRESS,
                    "process_stopped_event": TRANSCRIBE_STOPPED,
                    "print_event": PRINT_ME,
                    "stop_flag": stop_flag,
                    "translate_to_english": translate_to_english,
                    "language_code_as_specifier": language_code_as_specifier,
                },
                daemon=True,
            )
            transcribe_thread.start()
            is_transcribing = True
        # 1 transcription completed
        elif event == TRANSCRIBE_PROGRESS:
            num_tasks_done += 1
        # All transcriptions completed
        elif event == TRANSCRIBE_SUCCESS:
            transcription_time = transcription_timer.stop()

            # Show output file paths in a popup
            output_paths = values[TRANSCRIBE_SUCCESS]
            output_paths_formatted = "\n".join(output_paths)
            popup_tracked(
                f"Status: COMPLETE\n\nTime taken: {transcription_time:.4f} secs\n\nOutput locations: \n\n{output_paths_formatted}",
                popup_fn=popup_scrolled,
                tracked_windows=tracked_windows,
                title="Complete",
                size=(40, 20),
                disabled=True,
            )
        # Error while transcribing
        elif event == TRANSCRIBE_ERROR:
            transcription_timer.stop(log_time=False)
            sg.one_line_progress_meter_cancel(key=progress_key)

            error_msg = values[TRANSCRIBE_ERROR]
            popup_tracked(
                f"Status: FAILED\n\n{error_msg}\n\nPlease see the console output for details.",
                popup_fn=popup,
                tracked_windows=tracked_windows,
                title="ERROR",
            )
        # User cancelled transcription
        elif event == TRANSCRIBE_STOPPED:
            transcription_timer.stop(log_time=False)
            stop_flag.clear()
            print("\nTranscription cancelled by user.")

        # Transcriptions complete. Enable the starting of the next task.
        if event in TRANSCRIBE_DONE_EVENTS:
            transcribe_thread = None
            enable_elements(
                (
                    window[start_key],
                    window[save_settings_key],
                    window[out_dir_key],
                    window[in_file_key],
                )
            )
            is_transcribing = False

        # Transcriptions in progress
        if is_transcribing:
            # Turn \r into \n in the multiline's text
            format_multiline_text(
                window[multiline_key], is_multiline_rstripping_on_update
            )

            # Update the progress meter unless the user has clicked the cancel button alraedy
            if not stop_flag.is_set():
                # Get the current file being worked on
                if num_tasks_done < num_tasks:
                    current_file = audio_video_file_paths[num_tasks_done]
                else:
                    current_file = "None"

                # Update the progress window
                meter_updated = sg.one_line_progress_meter(
                    "Progress",
                    num_tasks_done,
                    num_tasks,
                    f"Current file: \n{current_file}",
                    key=progress_key,
                    size=(30, 20),
                    orientation="h",
                )

            # User clicked the Cancel button
            if not meter_updated:
                # Close the progress window
                sg.one_line_progress_meter_cancel(key=progress_key)
                # Flag the thread to stop
                stop_flag.set()

    # Finish up by removing from the screen
    window.close()


def save_checkbox_state(window: sg.Window, checkbox_key: str):
    """Save the checkbox's checked state to the config file. The checkbox must
    be an Image element whose checked state is True or False and saved in the element's metadata.

    Args:
        window (sg.Window): The PySimpleGUI window with the checkbox as an Image element.
        checkbox_key (str): The key for the checkbox which is an Image element
            whose checked state is saved in its metadata.
    """
    sg.user_settings_set_entry(
        checkbox_key,
        window[checkbox_key].metadata,
    )


def popup_tracked(
    *args: Any,
    popup_fn: Callable,
    tracked_windows: Set[sg.Window],
    non_blocking: bool = True,
    **kwargs: Any,
):
    """Pop up a tracked window.

    Args:
        popup_fn (Callable): The function to call to create a popup.
        tracked_windows (Set[sg.Window]): Set containing all currently tracked windows which the created popup will be added to.
        non_blocking (bool, optional): If True, then will immediately return from the function without waiting for the user's input. Defaults to True.
    """
    popup_window, popup_button = popup_fn(*args, non_blocking=non_blocking, **kwargs)
    tracked_windows.add(popup_window)


def set_same_width(window: sg.Window, element_keys: Iterable[str]):
    """Resize the elements in the given window to the max text length among the elements.

    Args:
        window (sg.Window): The window containing the elements.
        element_keys (Iterable[str]): Iterable with the keys (str) of the elements to resize.
    """
    text_lengths = [len(window[key].get()) for key in element_keys]
    for key in element_keys:
        window[key].set_size((max(text_lengths), None))


class CustomTimer(Timer):
    """codetiming.Timer with a stop() that optionally prints the elapsed time."""

    def stop(self, log_time: bool = True) -> float:
        """Stop the timer, and optionally report the elapsed time."""
        if self._start_time is None:
            raise TimerError("Timer is not running. Use .start() to start it")

        # Calculate elapsed time
        self.last = time.perf_counter() - self._start_time
        self._start_time = None

        # Report elapsed time
        if self.logger and log_time:
            if callable(self.text):
                text = self.text(self.last)
            else:
                attributes = {
                    "name": self.name,
                    "milliseconds": self.last * 1000,
                    "seconds": self.last,
                    "minutes": self.last / 60,
                }
                text = self.text.format(self.last, **attributes)
            self.logger(text)
        if self.name:
            self.timers.add(self.name, self.last)

        return self.last


def disable_elements(gui_elements: Iterable[sg.Element]):
    """Disable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the PySimpleGUI elements to disable.
    """
    update_elements(gui_elements=gui_elements, disabled=True)


def enable_elements(gui_elements: Iterable[sg.Element]):
    """Enable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the PySimpleGUI elements to enable.
    """
    update_elements(gui_elements=gui_elements, disabled=False)


def update_elements(gui_elements: Iterable[sg.Element], **kwargs):
    """Update the PySimpleGUI elements using keyword arguments.

    Calls PySimpleGUI.update() with the keyword arguments provided.
    All elements must have the keyword arguments.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the PySimpleGUI elements to update.
    """
    for gui_element in gui_elements:
        gui_element.update(**kwargs)


# Taken from Pysimplegui.popup() and modified
def popup(
    *args: Any,
    title=None,
    button_color=None,
    background_color=None,
    text_color=None,
    button_type=sg.POPUP_BUTTONS_OK,
    auto_close=False,
    auto_close_duration=None,
    custom_text=(None, None),
    non_blocking=False,
    icon=None,
    line_width=None,
    font=None,
    no_titlebar=False,
    grab_anywhere=False,
    keep_on_top=None,
    location=(None, None),
    relative_location=(None, None),
    any_key_closes=False,
    image=None,
    modal=True,
) -> Tuple[sg.Window, Optional[str]]:
    """
    Popup - Display a popup Window with as many parms as you wish to include.  This is the GUI equivalent of the
    "print" statement.  It's also great for "pausing" your program's flow until the user can read some error messages.

    If this popup doesn't have the features you want, then you can easily make your own. Popups can be accomplished in 1 line of code:
    choice, _ = sg.Window('Continue?', [[sg.T('Do you want to continue?')], [sg.Yes(s=10), sg.No(s=10)]], disable_close=True).read(close=True)


    :param *args:               Variable number of your arguments.  Load up the call with stuff to see!
    :type *args:                (Any)
    :param title:               Optional title for the window. If none provided, the first arg will be used instead.
    :type title:                (str)
    :param button_color:        Color of the buttons shown (text color, button color)
    :type button_color:         (str, str) | None
    :param background_color:    Window's background color
    :type background_color:     (str)
    :param text_color:          text color
    :type text_color:           (str)
    :param button_type:         NOT USER SET!  Determines which pre-defined buttons will be shown (Default value = POPUP_BUTTONS_OK). There are many Popup functions and they call Popup, changing this parameter to get the desired effect.
    :type button_type:          (int)
    :param auto_close:          If True the window will automatically close
    :type auto_close:           (bool)
    :param auto_close_duration: time in seconds to keep window open before closing it automatically
    :type auto_close_duration:  (int)
    :param custom_text:         A string or pair of strings that contain the text to display on the buttons
    :type custom_text:          (str, str) | str
    :param non_blocking:        If True then will immediately return from the function without waiting for the user's input.
    :type non_blocking:         (bool)
    :param icon:                icon to display on the window. Same format as a Window call
    :type icon:                 str | bytes
    :param line_width:          Width of lines in characters.  Defaults to MESSAGE_BOX_LINE_WIDTH
    :type line_width:           (int)
    :param font:                specifies the  font family, size, etc. Tuple or Single string format 'name size styles'. Styles: italic * roman bold normal underline overstrike
    :type font:                 str | Tuple[font_name, size, modifiers]
    :param no_titlebar:         If True will not show the frame around the window and the titlebar across the top
    :type no_titlebar:          (bool)
    :param grab_anywhere:       If True can grab anywhere to move the window. If no_titlebar is True, grab_anywhere should likely be enabled too
    :type grab_anywhere:        (bool)
    :param location:            Location on screen to display the top left corner of window. Defaults to window centered on screen
    :type location:             (int, int)
    :param relative_location:   (x,y) location relative to the default location of the window, in pixels. Normally the window centers.  This location is relative to the location the window would be created. Note they can be negative.
    :type relative_location:    (int, int)
    :param keep_on_top:         If True the window will remain above all current windows
    :type keep_on_top:          (bool)
    :param any_key_closes:      If True then will turn on return_keyboard_events for the window which will cause window to close as soon as any key is pressed.  Normally the return key only will close the window.  Default is false.
    :type any_key_closes:       (bool)
    :param image:               Image to include at the top of the popup window
    :type image:                (str) or (bytes)
    :param modal:               If True then makes the popup will behave like a Modal window... all other windows are non-operational until this one is closed. Default = True
    :type modal:                bool
    :return:                    Returns the window for the popup and text of the button that was pressed.  None will be returned in place of the button text if user closed window with X
    :rtype:                     (sg.Window, str | None)
    """

    if not args:
        args_to_print: Sequence[Any] = [""]
    else:
        args_to_print = args
    if line_width != None:
        local_line_width = line_width
    else:
        local_line_width = sg.MESSAGE_BOX_LINE_WIDTH
    _title = title if title is not None else args_to_print[0]

    layout: List[List] = [[]]
    max_line_total, total_lines = 0, 0
    if image is not None:
        if isinstance(image, str):
            layout += [[sg.Image(filename=image)]]
        else:
            layout += [[sg.Image(data=image)]]

    for message in args_to_print:
        # fancy code to check if string and convert if not is not need. Just always convert to string :-)
        # if not isinstance(message, str): message = str(message)
        message = str(message)
        if message.count(
            "\n"
        ):  # if there are line breaks, then wrap each segment separately
            # message_wrapped = message         # used to just do this, but now breaking into smaller pieces
            message_wrapped = ""
            msg_list = message.split(
                "\n"
            )  # break into segments that will each be wrapped
            message_wrapped = "\n".join(
                [sg.textwrap.fill(msg, local_line_width) for msg in msg_list]
            )
        else:
            message_wrapped = sg.textwrap.fill(message, local_line_width)
        message_wrapped_lines = message_wrapped.count("\n") + 1
        longest_line_len = max([len(l) for l in message.split("\n")])
        width_used = min(longest_line_len, local_line_width)
        max_line_total = max(max_line_total, width_used)
        # height = _GetNumLinesNeeded(message, width_used)
        height = message_wrapped_lines
        layout += [
            [
                sg.Text(
                    message_wrapped,
                    auto_size_text=True,
                    text_color=text_color,
                    background_color=background_color,
                )
            ]
        ]
        total_lines += height

    if non_blocking:
        PopupButton = (
            sg.DummyButton
        )  # important to use or else button will close other windows too!
    else:
        PopupButton = sg.Button
    # show either an OK or Yes/No depending on paramater
    if custom_text != (None, None):
        if type(custom_text) is not tuple:
            layout += [
                [
                    PopupButton(
                        custom_text,
                        size=(len(custom_text), 1),
                        button_color=button_color,
                        focus=True,
                        bind_return_key=True,
                    )
                ]
            ]
        elif custom_text[1] is None:
            layout += [
                [
                    PopupButton(
                        custom_text[0],
                        size=(len(custom_text[0]), 1),
                        button_color=button_color,
                        focus=True,
                        bind_return_key=True,
                    )
                ]
            ]
        else:
            layout += [
                [
                    PopupButton(
                        custom_text[0],
                        button_color=button_color,
                        focus=True,
                        bind_return_key=True,
                        size=(len(custom_text[0]), 1),
                    ),
                    PopupButton(
                        custom_text[1],
                        button_color=button_color,
                        size=(len(custom_text[1]), 1),
                    ),
                ]
            ]
    elif button_type is sg.POPUP_BUTTONS_YES_NO:
        layout += [
            [
                PopupButton(
                    "Yes",
                    button_color=button_color,
                    focus=True,
                    bind_return_key=True,
                    pad=((20, 5), 3),
                    size=(5, 1),
                ),
                PopupButton("No", button_color=button_color, size=(5, 1)),
            ]
        ]
    elif button_type is sg.POPUP_BUTTONS_CANCELLED:
        layout += [
            [
                PopupButton(
                    "Cancelled",
                    button_color=button_color,
                    focus=True,
                    bind_return_key=True,
                    pad=((20, 0), 3),
                )
            ]
        ]
    elif button_type is sg.POPUP_BUTTONS_ERROR:
        layout += [
            [
                PopupButton(
                    "Error",
                    size=(6, 1),
                    button_color=button_color,
                    focus=True,
                    bind_return_key=True,
                    pad=((20, 0), 3),
                )
            ]
        ]
    elif button_type is sg.POPUP_BUTTONS_OK_CANCEL:
        layout += [
            [
                PopupButton(
                    "OK",
                    size=(6, 1),
                    button_color=button_color,
                    focus=True,
                    bind_return_key=True,
                ),
                PopupButton("Cancel", size=(6, 1), button_color=button_color),
            ]
        ]
    elif button_type is sg.POPUP_BUTTONS_NO_BUTTONS:
        pass
    else:
        layout += [
            [
                PopupButton(
                    "OK",
                    size=(5, 1),
                    button_color=button_color,
                    focus=True,
                    bind_return_key=True,
                    pad=((20, 0), 3),
                )
            ]
        ]

    window = sg.Window(
        _title,
        layout,
        auto_size_text=True,
        background_color=background_color,
        button_color=button_color,
        auto_close=auto_close,
        auto_close_duration=auto_close_duration,
        icon=icon,
        font=font,
        no_titlebar=no_titlebar,
        grab_anywhere=grab_anywhere,
        keep_on_top=keep_on_top,
        location=location,
        relative_location=relative_location,
        return_keyboard_events=any_key_closes,
        modal=modal,
    )

    if non_blocking:
        button, values = window.read(timeout=0)
    else:
        button, values = window.read()
        window.close()

    return window, button


# Taken from Pysimplegui.popup_scrolled() and modified
# ========================  Scrolled Text Box   =====#
# ===================================================#
def popup_scrolled(
    *args,
    title=None,
    button_color=None,
    background_color=None,
    text_color=None,
    yes_no=False,
    auto_close=False,
    auto_close_duration=None,
    size=(None, None),
    location=(None, None),
    relative_location=(None, None),
    non_blocking=False,
    no_titlebar=False,
    grab_anywhere=False,
    keep_on_top=None,
    font=None,
    image=None,
    icon=None,
    modal=True,
    no_sizegrip=False,
    disabled=False,
) -> Optional[Tuple[sg.Window, Optional[str]]]:
    """
    Show a scrolled Popup window containing the user's text that was supplied.  Use with as many items to print as you
    want, just like a print statement.

    :param *args:               Variable number of items to display
    :type *args:                (Any)
    :param title:               Title to display in the window.
    :type title:                (str)
    :param button_color:        button color (foreground, background)
    :type button_color:         (str, str) or str
    :param yes_no:              If True, displays Yes and No buttons instead of Ok
    :type yes_no:               (bool)
    :param auto_close:          if True window will close itself
    :type auto_close:           (bool)
    :param auto_close_duration: Older versions only accept int. Time in seconds until window will close
    :type auto_close_duration:  int | float
    :param size:                (w,h) w=characters-wide, h=rows-high
    :type size:                 (int, int)
    :param location:            Location on the screen to place the upper left corner of the window
    :type location:             (int, int)
    :param relative_location:   (x,y) location relative to the default location of the window, in pixels. Normally the window centers.  This location is relative to the location the window would be created. Note they can be negative.
    :type relative_location:    (int, int)
    :param non_blocking:        if True the call will immediately return rather than waiting on user input
    :type non_blocking:         (bool)
    :param background_color:    color of background
    :type background_color:     (str)
    :param text_color:          color of the text
    :type text_color:           (str)
    :param no_titlebar:         If True no titlebar will be shown
    :type no_titlebar:          (bool)
    :param grab_anywhere:       If True, than can grab anywhere to move the window (Default = False)
    :type grab_anywhere:        (bool)
    :param keep_on_top:         If True the window will remain above all current windows
    :type keep_on_top:          (bool)
    :param font:                specifies the  font family, size, etc. Tuple or Single string format 'name size styles'. Styles: italic * roman bold normal underline overstrike
    :type font:                 (str or (str, int[, str]) or None)
    :param image:               Image to include at the top of the popup window
    :type image:                (str) or (bytes)
    :param icon:                filename or base64 string to be used for the window's icon
    :type icon:                 bytes | str
    :param modal:               If True then makes the popup will behave like a Modal window... all other windows are non-operational until this one is closed. Default = True
    :type modal:                bool
    :param no_sizegrip:         If True no Sizegrip will be shown when there is no titlebar. It's only shown if there is no titlebar
    :type no_sizegrip:          (bool)
    :return:                    Returns the window for the popup and text of the button that was pressed.  None will be returned in place of the button text if user closed window with X
    :rtype:                     (sg.Window, str | None | TIMEOUT_KEY) | None
    """
    if not args:
        return None
    width, height = size
    width = width if width else sg.MESSAGE_BOX_LINE_WIDTH

    layout: List[List] = [[]]

    if image is not None:
        if isinstance(image, str):
            layout += [[sg.Image(filename=image)]]
        else:
            layout += [[sg.Image(data=image)]]
    max_line_total, max_line_width, total_lines, height_computed = 0, 0, 0, 0
    complete_output = ""
    for message in args:
        # fancy code to check if string and convert if not is not need. Just always convert to string :-)
        # if not isinstance(message, str): message = str(message)
        message = str(message)
        longest_line_len = max([len(l) for l in message.split("\n")])
        width_used = min(longest_line_len, width)
        max_line_total = max(max_line_total, width_used)
        max_line_width = width
        lines_needed = _GetNumLinesNeeded(message, width_used)
        height_computed += lines_needed + 1
        complete_output += message + "\n"
        total_lines += lines_needed
    height_computed = (
        sg.MAX_SCROLLED_TEXT_BOX_HEIGHT
        if height_computed > sg.MAX_SCROLLED_TEXT_BOX_HEIGHT
        else height_computed
    )
    if height:
        height_computed = height
    layout += [
        [
            sg.Multiline(
                complete_output,
                size=(max_line_width, height_computed),
                background_color=background_color,
                text_color=text_color,
                expand_x=True,
                expand_y=True,
                k="-MLINE-",
                disabled=disabled,
            )
        ]
    ]
    pad = max_line_total - 15 if max_line_total > 15 else 1
    # show either an OK or Yes/No depending on paramater
    button = sg.DummyButton if non_blocking else Button
    if yes_no:
        layout += [
            [
                sg.Text(
                    "",
                    size=(pad, 1),
                    auto_size_text=False,
                    background_color=background_color,
                ),
                button("Yes"),
                button("No"),
            ]
        ]
    else:
        layout += [
            [
                sg.Text(
                    "",
                    size=(pad, 1),
                    auto_size_text=False,
                    background_color=background_color,
                ),
                button("OK", size=(5, 1), button_color=button_color),
            ]
        ]
    if no_titlebar and no_sizegrip is not True:
        layout += [[sg.Sizegrip()]]

    window = sg.Window(
        title or args[0],
        layout,
        auto_size_text=True,
        button_color=button_color,
        auto_close=auto_close,
        auto_close_duration=auto_close_duration,
        location=location,
        relative_location=relative_location,
        resizable=True,
        font=font,
        background_color=background_color,
        no_titlebar=no_titlebar,
        grab_anywhere=grab_anywhere,
        keep_on_top=keep_on_top,
        modal=modal,
        icon=icon,
    )
    if non_blocking:
        button, values = window.read(timeout=0)
    else:
        button, values = window.read()
        window.close()
    return window, button


# Taken from Pysimplegui._GetNumLinesNeeded(). Needed by popup_scrolled().
# ==============================_GetNumLinesNeeded ==#
# Helper function for determining how to wrap text   #
# ===================================================#
def _GetNumLinesNeeded(text: str, max_line_width: int) -> int:
    """Get the number of lines needed to wrap the text.

    Args:
        text (str): The text that needs the number of lines to use when wrapping.
        max_line_width (int): The max width of each line that will be used during text wrapping.

    Returns:
        int: The number of lines needed to wrap the text.
    """
    if max_line_width == 0:
        return 1
    lines = text.split("\n")
    num_lines = len(lines)  # number of original lines of text
    max_line_len = max([len(l) for l in lines])  # longest line
    lines_used = []
    for L in lines:
        # fancy math to round up
        lines_used.append(len(L) // max_line_width + (len(L) % max_line_width > 0))
    total_lines_needed = sum(lines_used)
    return total_lines_needed


def str_to_file_paths(file_paths_string: str, delimiter: str = r";") -> Tuple[str, ...]:
    """Split a string with file paths based on a delimiter.

    Args:
        file_paths_string (str): The string with file paths.
        delimiter (str, optional): The delimiter that separates file paths in the string. Defaults to r";".

    Returns:
        Tuple[str, ...]: A tuple of file paths (str).
    """
    audio_video_paths_list = re.split(delimiter, file_paths_string)
    return tuple(str(Path(file_path).resolve()) for file_path in audio_video_paths_list)


def format_multiline_text(
    element: sg.ErrorElement, is_multiline_rstripping_on_update: bool
):
    """Update the text in a multiline element.

    Replaces \r with \n.
    Replaces progress characters between |s in progress bars with proper █s.

    Args:
        element (sg.ErrorElement): A Multiline element.
        is_multiline_rstripping_on_update (bool): If True, the Multiline is stripping whitespace
            from the end of each string that is appended to its text.
    """
    # Get the text in the Multiline element
    text = element.get()

    # remove the auto appended '\n' by every Multiline.get() call when rstrip=False option is set for Multiline
    if not is_multiline_rstripping_on_update:
        text = text[:-1]

    # Replace all \r with \n
    processed_text = re.sub(r"\r", "\n", text)

    def repl_progress_bars(m: re.Match):
        return "█" * len(m.group())

    processed_text = re.sub(r"(?<=\|)\S+(?=\s*\|)", repl_progress_bars, processed_text)

    element.update(processed_text)


def transcribe_audio_video_files(
    window: sg.Window,
    audio_video_file_paths: Iterable[str],
    output_dir_path: str,
    language: str,
    model: str,
    success_event: str,
    fail_event: str,
    progress_event: str,
    process_stopped_event: str,
    print_event: str,
    stop_flag: threading.Event,
    translate_to_english: bool = False,
    language_code_as_specifier: bool = False,
):
    """Transcribe a list of audio/video files.

    Results are written to files with the same name but with .txt, .vtt, .srt extensions.

    Args:
        window (sg.Window): The window to send events to.
        audio_video_file_paths (Iterable[str]): An Iterable with the audio/vidoe file paths.
        output_dir_path (str): The output directory path.
        language (str): The language of the file(s) to transcribe.
        model (str): The whisper model to use for transcription.
        success_event (str): The event to send to the window when all transcriptions are successful.
        fail_event (str): The event to send to the window on transcription failure.
        progress_event (str): The event to send to the window on a transcription success.
        process_stopped_event (str): The event to send to the window after stopping the process because the stop flag is set.
        print_event (str): The event to send to the window to print a string.
        stop_flag (threading.Event): The flag that causes transcription to abort when it's set.
        translate_to_english (bool): If True, each transcription will be translated to English. Otherwise, no translation will
            occur.
        language_code_as_specifier (bool): If True, the detected language's language code will be used in the
            output file name if possible. Otherwise, the detected language's name will be used in the output
            file name if possible.
    """

    # Paths for the transcription result files
    all_output_paths: List[str] = []

    # pipe for stdout and stderr output in a child process
    read_connection, write_connection = multiprocessing.Pipe()

    # window.write_event_value(print_event, "In thread...\n")

    # with os.fdopen(read_connection.fileno(), 'r') as reader:
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
            },
            daemon=True,
        )
        process.start()

        def send_to_print_from_connection(conn: Union[Connection, PipeConnection]):
            window.write_event_value(print_event, str(conn.recv()))

        # Transcribing
        while not process_done_flag.is_set():
            # Main thread has set the stop flag. Stop the process, wait for it to join, and return
            if stop_flag.is_set():
                process.terminate()
                close_connections((read_connection, write_connection))
                process.join()
                window.write_event_value(
                    process_stopped_event, "Transcription stopped due to stop flag."
                )
                return

            # Print the stdout stderr output piped from the process
            while read_connection.poll():
                send_to_print_from_connection(read_connection)

            # print('process alive')

        while read_connection.poll():
            send_to_print_from_connection(read_connection)

        # Get the result from transcribing the file
        result = mp_queue.get()

        # Handle a possible Exception in the process
        if isinstance(result, Exception):
            window.write_event_value(
                fail_event, "An error occurred while transcribing the file."
            )
            close_connections((read_connection, write_connection))
            return

        # Write transcription results to files
        output_paths = write_transcript_to_files(
            transcribe_result=result,
            audio_path=audio_video_path,
            output_dir_path=output_dir_path,
            language_code_as_specifier=language_code_as_specifier,
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
    language: str,
    model: str,
    audio_video_path: str,
    queue: multiprocessing.Queue,
    write_connection: Union[Connection, PipeConnection],
    process_done_flag: EventClass,
    translate_to_english: bool = False,
):
    """Transcribe an audio/video file.

    Args:
        language (str): The language of the file to transcribe.
        model (str): The whisper model to use for transcription.
        audio_video_path (str): An audio/video file path.
        queue (multiprocessing.Queue): The queue that the results of the transcription will be put in.
        write_connection (Union[Connection, PipeConnection]): A writeable Connection to redirect prints into.
        process_done_flag (EventClass): The flag that signals process completion to the parent thread.
        translate_to_english (bool): True if the user has chosen to translate the transcription to English, False otherwise.
    """
    redirector = OutputRedirector(write_connection)

    # print("In process...")

    # Clean up when this process is told to terminate
    def handler(sig, frame):
        queue.close()
        redirector.close()
        write_connection.close()
        # end the process
        sys.exit(0)

    # handle sigterm
    signal(SIGTERM, handler)

    whisper_model = whisper.load_model(model)

    print(f"\nTranscribing file: {audio_video_path}", end="\n\n")

    # task = "transcribe"
    if translate_to_english:
        task = "translate"
    else:
        task = "transcribe"

    # Transcribe the file
    try:
        result = whisper_model.transcribe(
            audio=audio_video_path,
            verbose=False,
            language=language,
            beam_size=5,
            best_of=5,
            task=task,
        )
    except Exception as e:
        queue.put(e)
        raise

    # Pass the result out
    queue.put(result)

    # Clean up
    write_connection.close()
    redirector.close()
    queue.close()

    # Signal process completion to the parent thread
    process_done_flag.set()


class OutputRedirector:
    """Redirector for stdout and/or stderr to a writeable Connection."""

    def __init__(
        self,
        write_conn: Union[Connection, PipeConnection],
        reroute_stdout=True,
        reroute_stderr=True,
    ):
        """__init__

        Args:
            write_conn (Union[Connection, PipeConnection]): A writeable connection.
            reroute_stdout (bool, optional): If True, redirects stdout to the connection. Defaults to True.
            reroute_stderr (bool, optional): If True, redirects stderr to the connection. Defaults to True.
        """
        self.write_conn = write_conn
        if reroute_stdout:
            self.reroute_stdout_to_here()
        if reroute_stderr:
            self.reroute_stderr_to_here()

    def reroute_stdout_to_here(self):
        """Send stdout (prints) to this element."""
        self.previous_stdout = sys.stdout
        sys.stdout = self

    def reroute_stderr_to_here(self):
        """Send stderr to this element."""
        self.previous_stderr = sys.stderr
        sys.stderr = self

    def restore_stdout(self):
        """Restore a previously re-reouted stdout back to the original destination."""
        if self.previous_stdout:
            sys.stdout = self.previous_stdout
            self.previous_stdout = None  # indicate no longer routed here

    def restore_stderr(self):
        """Restore a previously re-reouted stderr back to the original destination."""
        if self.previous_stderr:
            sys.stderr = self.previous_stderr
            self.previous_stderr = None  # indicate no longer routed here

    def write(self, txt: str):
        """
        Called by Python when stdout or stderr wants to write.
        Send the text through the pipe's write connection.

        :param txt: text of output
        :type txt:  (str)
        """
        # Send text through the write connection and ignore OSError that occurs when the process is killed.
        with suppress(OSError):
            self.write_conn.send(str(txt))

    def flush(self):
        """Handle Flush parameter passed into a print statement.

        For now doing nothing.  Not sure what action should be taken to ensure a flush happens regardless.
        """
        try:
            self.previous_stdout.flush()
        except:
            pass

    def __del__(self):
        """Restore the old stdout, stderr if this object is deleted"""
        # These trys are here because found that if the init fails, then
        # the variables holding the old stdout won't exist and will get an error
        try:
            self.restore_stdout()
        except Exception as e:
            pass
        try:
            self.restore_stderr()
        except:
            pass

    def close(self):
        self.__del__()


def close_connections(connections: Iterable[Union[Connection, PipeConnection]]):
    """Close all given connections.

    Args:
        connections (Iterable[Union[Connection, PipeConnection]]): Iterable with all of the connections to close.
    """
    for conn in connections:
        conn.close()


def write_transcript_to_files(
    transcribe_result: Dict[str, Union[dict, Any]],
    audio_path: str,
    output_dir_path: str,
    language_code_as_specifier: bool,
) -> Tuple[str, str, str]:
    """Write the results of a whisper transcription to .txt, .vtt, and .srt files with the
    same name as the source file and a language specifier.

    Output file format: [filename].[language specifier].[txt/vtt/srt]

    Example output files for my_video.mp4:
        my_video.[language specifier].txt
        my_video.[language specifier].vtt
        my_video.[language specifier].srt

    Args:
        transcribe_result (Dict[str, Union[dict, Any]]): The results of a whisper transcription.
        audio_path (str): The file path of the source audio/video file.
        output_dir_path (str): The directory to write the transcription result files to.
        language_code_as_specifier (bool): If True, the detected language's language code will be used in the
            output file name if possible. Otherwise, the detected language's name will be used in the output
            file name if possible.

    Returns:
        Tuple[str, str, str]: A Tuple with the file paths for the transcription result files.
    """
    output_dir = Path(output_dir_path)
    audio_basename = Path(audio_path).stem

    language_specifier = str(transcribe_result["language"]).strip()

    # Try to convert language specifier to the selected type
    to_lang_specifier_type = (
        TO_LANGUAGE_CODE if language_code_as_specifier else TO_LANGUAGES
    )
    language_specifier = to_lang_specifier_type.get(
        language_specifier, language_specifier
    )

    def write_file(write_fn: Callable, language_code: str, file_suffix: str):
        with open(
            output_dir / "".join((audio_basename, ".", language_code, file_suffix)),
            "w",
            encoding="utf-8",
        ) as file:
            write_fn(transcribe_result["segments"], file=file)
            return file.name

    srt_path = write_file(write_srt, language_specifier, ".srt")
    txt_path = write_file(write_txt, language_specifier, ".txt")
    vtt_path = write_file(write_vtt, language_specifier, ".vtt")
    return (srt_path, txt_path, vtt_path)


# ===================================================#
# =============== Unused f(x)s below ================#
# ===================================================#


def get_abs_resource_path(relative_path: str) -> str:
    """Get the absolute path to the resource.

    Works when used in a frozen application for Windows made using a tool like Pyinstaller.

    Args:
        relative_path (str): Relative file path for the resource.

    Returns:
        str: Absolute file path for the resource.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def convert_audio_video_to_audio(
    audio_video_file_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    shell_output_window: Optional[sg.Window] = None,
) -> Tuple[int, str, str]:
    """Convert an audio/video file into an audio file using ffmpeg.

    Args:
        audio_video_file_path (Union[str, Path]): The file path for the audio/video file.
        output_dir_path (Union[str, Path]): The output directory path.
        shell_output_window (Optional[sg.Window], optional): The window that the shell command writes console output should to.
            Defaults to None.

    Returns:
        Tuple[int, str, str]: A Tuple with the return value from executing a subprocess, a copy of the console output by the shell command,
            and the absolute file path for the converted audio file.
    """
    video_path = Path(audio_video_file_path)

    output_directory_path = Path(output_dir_path)

    audio_file_name = f"{video_path.stem}.mp3"

    audio_output_path = output_directory_path / audio_file_name

    cmd = f'ffmpeg -i "{video_path.resolve()}" -y -q:a 0 -map a "{audio_output_path}"'

    retval, shell_output = run_shell_cmd(cmd=cmd, window=shell_output_window)
    return retval, shell_output, str(audio_output_path.resolve())


def run_shell_cmd(
    cmd: str, timeout: Optional[float] = None, window: Optional[sg.Window] = None
) -> Tuple[int, str]:
    """Run shell command.
    @param cmd: command to execute.
    @param timeout: timeout for command execution.
    @param window: the PySimpleGUI window that the output is going to (needed to do refresh on).
    @return: (return code from command, command output).
    """
    p = subprocess.Popen(
        shlex.split(cmd), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    shell_output = ""
    if p.stdout:
        for line in p.stdout:
            print(f"sys.version_info= {sys.version_info}")
            if sys.version_info < (3, 5):
                errors = "replace"
            else:
                errors = "backslashreplace"
            decoded_line = line.decode(errors=errors).rstrip()
            shell_output += decoded_line
            print(decoded_line)
            if window:
                window.refresh()
    retval = p.wait(timeout)
    return (retval, shell_output)


class NotAFileError(Exception):
    """Operation only works on files."""


def del_existing_file(file_path: Union[str, Path]):
    """Delete an existing file.

    Args:
        file_path (Union[str, Path]): The file path for the file to delete.

    Raises:
        NotAFileError: The path does not lead to a file.
    """
    p = Path(file_path)
    if p.exists():
        if not p.is_file():
            raise NotAFileError
        p.unlink()


if __name__ == "__main__":
    # required for when a program which uses multiprocessing has been frozen to produce a Windows executable.
    # (Has been tested with py2exe, PyInstaller and cx_Freeze.) has no effect when invoked on any operating system other than Windows
    multiprocessing.freeze_support()
    # The only method that works on both Windows and Linux is "spawn"
    multiprocessing.set_start_method("spawn")
    main()
