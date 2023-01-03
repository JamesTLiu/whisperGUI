#!/usr/bin/env python3
# mypy: disable-error-code=union-attr

from __future__ import annotations

import decimal
import multiprocessing
import platform
import signal
import sys
import threading
import time
import tkinter as tk
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as EventClass
from operator import itemgetter
from pathlib import Path
from types import EllipsisType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Type,
    TypeAlias,
    Union,
)

import PySimpleGUI as sg
import whisper
from codetiming import Timer, TimerError
from whisper.tokenizer import LANGUAGES as TO_LANGUAGE
from whisper.tokenizer import TO_LANGUAGE_CODE
from whisper.utils import write_srt, write_txt, write_vtt
from ext_PySimpleGUI import (
    FancyCheckbox,
    FancyToggle,
    Grid,
    ImageBase,
    InfoImage,
    ModalWindowManager,
    Multiline,
    Window,
    WindowTracker,
    popup,
    popup_scrolled,
    popup_tracked,
    save_checkbox_state,
    save_toggle_state,
    set_up_resize_event,
)

import set_env
from utils import (
    GetWidgetSizeError,
    OutputRedirector,
    _random_error_emoji,
    close_connections,
    convert_to_bytes,
    ensure_valid_layout,
    find_closest_element,
    get_element_size,
    get_event_widget,
    get_settings_file_path,
    function_details,
    get_traceback,
    get_widget_size,
    popup_on_error,
    resize_window_relative_to_screen,
    set_resizable_axis,
    set_window_to_autosize,
    str_to_file_paths,
    vertically_align_elements,
    widget_resized,
)

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import (  # type: ignore
        Connection as PipeConnection,
    )


if TYPE_CHECKING:
    from types import FrameType


def main():
    set_env.set_env_vars()
    start_GUI()


def start_GUI() -> None:
    """Start the GUI.

    Raises:
        NonExistentPromptProfileName: A non-existent prompt profile name
            was used.
    """
    set_global_GUI_settings()

    prompt_manager = PromptManager(Keys.SAVED_PROMPTS_SETTINGS)

    modal_window_manager = ModalWindowManager()

    transcriber = Transcriber()

    window_tracker = WindowTracker()

    prompt_manager_window = None

    add_new_prompt_window = None

    main_window = make_tracked_main_window_with_synced_profiles(
        window_tracker=window_tracker,
        prompt_manager=prompt_manager,
        prompt_profile_dropdown_key=Keys.PROMPT_PROFILE_DROPDOWN,
    )

    while True:
        # Display and interact with the Window
        window, event, values = sg.read_all_windows(timeout=1)

        if event in (sg.WIN_CLOSED, "Exit", "Close", "Cancel", "OK"):
            if window is main_window:
                # Tell the thread to end the ongoing transcription
                if transcriber.transcribe_thread:
                    print("Window closed but transcription is in progress.")
                    transcriber.stop_transcribing()
                break
            elif window is add_new_prompt_window:
                add_new_prompt_window = None
            elif window is prompt_manager_window:
                prompt_manager_window = None

            window.close()
        elif event == GenEvents.PRINT_ME:
            print(values[GenEvents.PRINT_ME], end="")
        # User selected an output directory
        elif event == Keys.OUTPUT_DIR_FIELD:
            # Save the output directory to the settings file when the
            # corresponding option is on
            if sg.user_settings_get_entry(Keys.SAVE_OUTPUT_DIR_CHECKBOX):
                sg.user_settings_set_entry(Keys.OUT_DIR, values[Keys.OUT_DIR])
        # User selected a language
        elif event == Keys.LANGUAGE:
            # Save the choice to the config file
            sg.user_settings_set_entry(Keys.LANGUAGE, values[Keys.LANGUAGE])
        # User selected a model
        elif event == Keys.MODEL:
            # Save the choice to the config file
            sg.user_settings_set_entry(Keys.MODEL, values[Keys.MODEL])
        # User clicked a checkbox
        elif is_custom_checkbox_event(window=window, event=event):
            # Save the checkbox state to the config file for
            # save-on-click checkboxes
            save_on_click_checkboxes = (
                Keys.TRANSLATE_TO_ENGLISH_CHECKBOX,
                Keys.SAVE_OUTPUT_DIR_CHECKBOX,
            )

            if event in save_on_click_checkboxes:
                save_checkbox_state(window[event])

            # Delete the saved output directory from the settings file
            # when the option is off
            if (
                event == Keys.SAVE_OUTPUT_DIR_CHECKBOX
                and not window[event].checked
            ):
                if sg.user_settings_get_entry(Keys.OUT_DIR):
                    sg.user_settings_delete_entry(Keys.OUT_DIR)
        # Popup prompt manager window
        elif event == Keys.START_PROMPT_MANAGER:
            prompt_manager_window = window_tracker.track_window(
                popup_prompt_manager(prompt_manager=prompt_manager)
            )
            modal_window_manager.track_modal_window(prompt_manager_window)
        # Popup add new prompt profile window
        elif event == Keys.OPEN_ADD_PROMPT_WINDOW:
            # Pop up a window to get a prompt name and prompt
            add_new_prompt_window = popup_add_prompt_profile(
                title="Add new prompt profile",
                submit_event=Keys.ADD_PROMPT_PROFILE,
            )
            modal_window_manager.track_modal_window(add_new_prompt_window)
        # User wants to edit a saved prompt profile
        elif event == Keys.OPEN_EDIT_PROMPT_WINDOW:
            selected_table_row_indices = values[Keys.SAVED_PROMPTS_TABLE]

            # Ensure user has selected a row in the prompt profile table
            if selected_table_row_indices:
                # Look up the profile using the index of the first
                # selected table row
                selected_profile = prompt_manager.saved_prompt_profiles_list[
                    selected_table_row_indices[0]
                ]
                (
                    selected_profile_name,
                    selected_profile_prompt,
                ) = selected_profile

                # Pop up a window to edit the prompt name and prompt
                edit_prompt_window = popup_edit_prompt_profile(
                    title="Edit prompt profile",
                    submit_event=Keys.EDIT_PROMPT_PROFILE,
                    profile_name=selected_profile_name,
                    profile_prompt=selected_profile_prompt,
                )
                modal_window_manager.track_modal_window(edit_prompt_window)
            # User has not selected a row in the prompt profile table
            else:
                popup_window = popup_tracked(
                    "Please select a profile in the table.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid selection",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # Handle adding or editing of a prompt profile
        elif event in (Keys.ADD_PROMPT_PROFILE, Keys.EDIT_PROMPT_PROFILE):
            # Get the name and prompt to be saved
            new_profile_name = values[Keys.NEW_PROFILE_NAME]
            new_profile_prompt = values[Keys.NEW_PROFILE_PROMPT]

            # Get the original profile name of the add/edit profile
            # window before user changes.
            original_profile_name = window[Keys.NEW_PROFILE_NAME].metadata

            if event == Keys.ADD_PROMPT_PROFILE:
                (
                    add_edit_success,
                    error_msg,
                ) = prompt_manager.add_prompt_profile(
                    profile_name=new_profile_name,
                    profile_prompt=new_profile_prompt,
                )
            elif event == Keys.EDIT_PROMPT_PROFILE:
                (
                    add_edit_success,
                    error_msg,
                ) = prompt_manager.edit_prompt_profile(
                    profile_name=new_profile_name,
                    profile_prompt=new_profile_prompt,
                    original_profile_name=original_profile_name,
                )

            # Successfully added / edited a saved prompt profile
            if add_edit_success:
                # Close the add new prompt window
                window.close()
                add_new_prompt_window = None

                prompt_manager_window = reload_prompt_manager_window(
                    prompt_manager=prompt_manager,
                    prompt_manager_window=prompt_manager_window,
                    modal_window_manager=modal_window_manager,
                    window_tracker=window_tracker,
                )
            # Failed to add new prompt
            else:
                popup_window = popup_tracked(
                    error_msg,
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid prompt name",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # User wants to delete a saved prompt profile
        elif event == Keys.DELETE_PROMPT:
            # Delete the saved prompt profile
            selected_table_row_indices = values[Keys.SAVED_PROMPTS_TABLE]

            # Ensure user has selected a row in the prompt profile table
            if selected_table_row_indices:
                prompt_profile_names = (
                    prompt_manager.saved_prompt_profile_names
                )
                prompt_profile_name_to_delete = prompt_profile_names[
                    selected_table_row_indices[0]
                ]
                prompt_manager.delete_prompt_profile(
                    prompt_profile_name_to_delete
                )

                prompt_manager_window = reload_prompt_manager_window(
                    prompt_manager=prompt_manager,
                    prompt_manager_window=prompt_manager_window,
                    modal_window_manager=modal_window_manager,
                    window_tracker=window_tracker,
                )
            # User has not selected a row in the prompt profile table
            else:
                popup_window = popup_tracked(
                    "Please select a profile in the table.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid selection",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # User modified the initial prompt.
        elif event == Keys.INITIAL_PROMPT_INPUT:
            # Select the unsaved prompt profile
            window[Keys.PROMPT_PROFILE_DROPDOWN].update(
                value=prompt_manager.unsaved_prompt_profile_name
            )
        # User has chosen a prompt profile
        elif event == Keys.PROMPT_PROFILE_DROPDOWN:
            # Update the initial prompt input with the prompt profile's
            # prompt
            chosen_prompt_profile = values[Keys.PROMPT_PROFILE_DROPDOWN]

            if (
                chosen_prompt_profile
                in prompt_manager.saved_prompt_profile_names
            ):
                new_initial_prompt_input = (
                    prompt_manager.saved_prompt_profiles[chosen_prompt_profile]
                )
            elif (
                chosen_prompt_profile
                == prompt_manager.unsaved_prompt_profile_name
            ):
                new_initial_prompt_input = ""
            else:
                raise NonExistentPromptProfileName(
                    f"{chosen_prompt_profile} is not a saved prompt profile"
                    " name or the unsaved prompt profile"
                )

            window[Keys.INITIAL_PROMPT_INPUT].update(
                value=new_initial_prompt_input
            )

            # Save the user's selected prompt profile to the settings
            # file
            sg.user_settings_set_entry(
                Keys.PROMPT_PROFILE_DROPDOWN, chosen_prompt_profile
            )
        # User selected a language specifier for the result files
        elif event == Keys.LANGUAGE_SPECIFIER_SETTING:
            # Update the language specifier option setting
            sg.user_settings_set_entry(event, values[event])
            current_language_specifier = values[event]
            example_text = LanguageSpecifier.TO_EXAMPLE_TEXT[
                current_language_specifier
            ]
            window[Keys.LANGUAGE_SPECIFIER_EXAMPLE_TEXT].update(
                value=example_text
            )
        # User saved settings
        elif event == Keys.APPLY_GLOBAL_SCALING:
            # Ensure the scaling input is a decimal
            try:
                scaling_input = Decimal(values[Keys.SCALING_INPUT_SETTING])
            except decimal.InvalidOperation:
                popup_tracked_scaling_invalid(
                    window_tracker=window_tracker,
                    modal_window_manager=modal_window_manager,
                )
                continue

            # Ensure scaling factor is within accepted range
            if (
                Decimal(GUI_Settings.MIN_SCALING)
                <= scaling_input
                <= Decimal(GUI_Settings.MAX_SCALING)
            ):
                # Save the settings to the config file
                sg.user_settings_set_entry(
                    Keys.SCALING_INPUT_SETTING,
                    values[Keys.SCALING_INPUT_SETTING],
                )

                # Use the new scaling globally
                sg.set_options(
                    scaling=sg.user_settings_get_entry(
                        Keys.SCALING_INPUT_SETTING,
                        GUI_Settings.DEFAULT_GLOBAL_SCALING,
                    )
                )
            # Scaling factor is out of accepted range
            else:
                popup_tracked_scaling_invalid(
                    window_tracker=window_tracker,
                    modal_window_manager=modal_window_manager,
                )
                continue

            # Close all windows and remove them from tracking
            for win in window_tracker.windows:
                win.close()
            del window_tracker.windows

            # Remake the main window and go back to the settings tab
            window = (
                main_window
            ) = make_tracked_main_window_with_synced_profiles(
                window_tracker=window_tracker,
                prompt_manager=prompt_manager,
                prompt_profile_dropdown_key=Keys.PROMPT_PROFILE_DROPDOWN,
            )
            window[Keys.SETTINGS_TAB].select()
        # User pressed toggle button for the table
        elif event == Keys.MODEL_INFO_TOGGLE:
            # window[model_info_toggle_key].update(image_data=toggle_image)
            model_info_toggled_on = window[
                Keys.MODEL_INFO_TOGGLE
            ].is_toggled_on

            # Show/hide the table
            window[Keys.MODEL_INFO_TABLE].update(visible=model_info_toggled_on)
        # User wants to start transcription
        elif event == Keys.START:
            # Get user provided paths for the video file and output
            # directory
            audio_video_file_paths_str = str(values[Keys.IN_FILE]).strip()
            output_dir_path = str(values[Keys.OUT_DIR]).strip()

            # Require audio/video file(s) and output folder
            if audio_video_file_paths_str and output_dir_path:
                # Get user selected language and model
                language_selected = values[Keys.LANGUAGE]
                if language_selected not in TO_LANGUAGE_CODE:
                    language_selected = None

                model_selected = values[Keys.MODEL]

                # Get the user's choice of whether to translate the
                # results into english
                translate_to_english = window[
                    Keys.TRANSLATE_TO_ENGLISH_CHECKBOX
                ].checked

                # Get the user's choice of whether to use a language
                # code as the language specifier in output files
                language_specifier_selection = values[
                    Keys.LANGUAGE_SPECIFIER_SETTING
                ]
                use_language_code = (
                    True
                    if language_specifier_selection
                    == LanguageSpecifier.Options.CODE
                    else False
                )

                #  Get the user's initial prompt for all transcriptions
                # in this task
                initial_prompt = values[Keys.INITIAL_PROMPT_INPUT]

                # Clear the console output element
                window[Keys.MULTILINE].update("")
                window.refresh()

                # Convert string with file paths into a list
                transcriber.audio_video_file_paths = str_to_file_paths(
                    audio_video_file_paths_str
                )

                # Setup for task progress
                transcriber.num_tasks = len(
                    transcriber.audio_video_file_paths
                )

                with popup_on_error(TimerError):
                    transcriber.start_timer()

                # Start transcription
                transcriber.transcribe_thread = threading.Thread(
                    target=transcribe_audio_video_files,
                    kwargs={
                        "window": window,
                        "audio_video_file_paths": transcriber.audio_video_file_paths,
                        "output_dir_path": output_dir_path,
                        "language": language_selected,
                        "model": model_selected,
                        "success_event": GenEvents.TRANSCRIBE_SUCCESS,
                        "fail_event": GenEvents.TRANSCRIBE_ERROR,
                        "progress_event": GenEvents.TRANSCRIBE_PROGRESS,
                        "process_stopped_event": GenEvents.TRANSCRIBE_STOPPED,
                        "print_event": GenEvents.PRINT_ME,
                        "stop_flag": transcriber.stop_transcriptions_flag,
                        "translate_to_english": translate_to_english,
                        "use_language_code": use_language_code,
                        "initial_prompt": initial_prompt,
                    },
                    daemon=True,
                )
                transcriber.transcribe_thread.start()
                transcriber.is_transcribing = True
            else:
                popup_window = popup_tracked(
                    "Please select audio/video file(s) and an output folder.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Missing selections",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # 1 transcription completed
        elif event == GenEvents.TRANSCRIBE_PROGRESS:
            transcriber.num_tasks_done += 1
        # All transcriptions completed
        elif event == GenEvents.TRANSCRIBE_SUCCESS:
            transcription_time = "TIMER_ERROR"

            with popup_on_error(TimerError):
                transcription_time_float = transcriber.stop_timer(
                    log_time=True
                )
                transcription_time = f"{transcription_time_float:.4f}"

            # Show output file paths in a popup
            output_paths = values[GenEvents.TRANSCRIBE_SUCCESS]
            output_paths_formatted = "\n".join(output_paths)
            popup_window = popup_tracked(
                (
                    "Status: COMPLETE\n\nTime taken:"
                    f" {transcription_time} secs\n\nOutput locations:"
                    f" \n\n{output_paths_formatted}"
                ),
                popup_fn=popup_scrolled,
                window_tracker=window_tracker,
                title="Complete",
                size=(40, 20),
                disabled=True,
                non_blocking=True,
            )
            modal_window_manager.track_modal_window(popup_window)
        # Error while transcribing
        elif event == GenEvents.TRANSCRIBE_ERROR:
            sg.one_line_progress_meter_cancel(key=Keys.PROGRESS)

            error_msg = values[GenEvents.TRANSCRIBE_ERROR]
            popup_window = popup_tracked(
                (
                    f"Status: FAILED\n\n{error_msg}\n\nPlease see the console"
                    " output for details."
                ),
                popup_fn=popup,
                window_tracker=window_tracker,
                title="ERROR",
                non_blocking=True,
            )
            modal_window_manager.track_modal_window(popup_window)
        # User cancelled transcription
        elif event == GenEvents.TRANSCRIBE_STOPPED:
            print("\nTranscription cancelled by user.")

        # Clear selection highlighting if a dropdown option was selected
        if (
            window
            and event in window.key_dict
            and isinstance(window[event], sg.Combo)
        ):
            window[event].widget.selection_clear()

        # Transcriptions complete. Enable the main window for the user.
        if event in GenEvents.TRANSCRIBE_DONE_EVENTS:
            transcriber.clear()

        # Transcriptions in progress
        if transcriber.is_transcribing:
            # Update the progress meter unless the user has clicked the
            # cancel button already
            if not transcriber.is_waiting_for_tasks_stop():
                # Get the current file being worked on
                if transcriber.num_tasks_done < transcriber.num_tasks:
                    current_file = transcriber.audio_video_file_paths[
                        transcriber.num_tasks_done
                    ]
                else:
                    current_file = "None"

                # Update the progress window
                meter_updated = sg.one_line_progress_meter(
                    "Progress",
                    transcriber.num_tasks_done,
                    transcriber.num_tasks,
                    f"Current file: \n{current_file}",
                    key=Keys.PROGRESS,
                    size=(30, 20),
                    orientation="h",
                )

                # Track the meter window in case it was remade to ensure
                # it's modal
                if meter_updated:
                    # Track the meter window as a modal window if it's
                    # still active
                    if Keys.PROGRESS in sg.QuickMeter.active_meters:
                        meter_window = sg.QuickMeter.active_meters[
                            Keys.PROGRESS
                        ].window
                        modal_window_manager.track_modal_window(meter_window)
                # User clicked the Cancel button
                else:
                    # Close the progress window
                    sg.one_line_progress_meter_cancel(key=Keys.PROGRESS)
                    transcriber.stop_transcribing()

        # Set as modal the most recent non-closed tracked modal window
        modal_window_manager.update()

    # Finish up by removing from the screen
    main_window.close()


def set_global_GUI_settings():
    """Set global PySimpleGUI settings."""
    sg.theme(GUI_Settings.THEME)

    # Set the settings file's name
    sg.user_settings_filename(filename=GUI_Settings.SETTINGS_FILE_NAME)

    # Set global GUI options
    sg.set_options(
        scaling=sg.user_settings_get_entry(
            Keys.SCALING_INPUT_SETTING, GUI_Settings.DEFAULT_GLOBAL_SCALING
        ),
        font=GUI_Settings.DEFAULT_FONT,
        tooltip_font=GUI_Settings.DEFAULT_FONT,
        force_modal_windows=True,
    )

    # App icon
    icon_data = b"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"  # noqa: E501
    sg.set_global_icon(icon_data)

    set_up_global_bindings()


class GUI_Settings:
    """Settings used in the GUI."""

    # scaling of the application's size
    DEFAULT_GLOBAL_SCALING = 1.5

    # Range of accepted scaling factor values from the user
    MIN_SCALING = 0.5
    MAX_SCALING = 3

    # Default global font for the GUI
    DEFAULT_FONT = ("Arial", 20)

    SETTINGS_FILE_NAME = "whisperGUI.config"

    THEME = "Dark Blue 3"


def set_up_global_bindings() -> None:
    """Set up global tk bindings."""
    set_up_resize_event()


def make_tracked_main_window_with_synced_profiles(
    window_tracker: WindowTracker,
    prompt_manager: PromptManager,
    prompt_profile_dropdown_key: str,
) -> sg.Window:
    """Create a tracked main window whose prompt profile dropdown is
    updated by the prompt manager when needed.

    Args:
        window_tracker (WindowTracker): The window tracker to add
            the created window to.
        prompt_manager (PromptManager): The prompt manager for the
            application.
        prompt_profile_dropdown_key (str): The key of the prompt
            profile dropdown that's updated by the prompt manager
            when needed.

    Returns:
        sg.Window: The created main window.
    """

    window = window_tracker.track_window(
        make_main_window(prompt_manager=prompt_manager)
    )

    # give the prompt manager the prompt profile dropdown so that
    # it's updated on profile changes
    prompt_manager.set_prompt_profile_dropdown(
        window, prompt_profile_dropdown_key
    )
    return window


def make_main_window(prompt_manager: PromptManager) -> sg.Window:
    """Create the main window for the GUI.

    Returns:
        sg.Window: The created main window.
    """
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
        str(model_data_table[0][x]) + "  "
        for x in range(len(model_data_table[0]))
    ]

    # Load whether to translating to English or not from the
    # settings file
    translate_to_english_last_choice = sg.user_settings_get_entry(
        Keys.TRANSLATE_TO_ENGLISH_CHECKBOX, False
    )

    # Load whether to save the output directory or not from the
    # settings file
    save_output_dir = sg.user_settings_get_entry(
        Keys.SAVE_OUTPUT_DIR_CHECKBOX, False
    )

    # Startup prompt profile
    startup_prompt_profile = sg.user_settings_get_entry(
        Keys.PROMPT_PROFILE_DROPDOWN,
        prompt_manager.unsaved_prompt_profile_name,
    )

    show_model_info_at_start = False

    info_image_tooltip = "\n".join(
        [
            (
                "Use this when a dialect/style of a language or"
                " punctuation is desired."
            ),
            "Does NOT guarantee the result will follow the initial prompt.",
            "Initial prompt will NOT be included in the result.",
            (
                "Try a larger model if the result does not follow the"
                " initial prompt."
            ),
            "\nEx. Chinese (simplified) with punctuation: 以下是普通话的句子。",
        ]
    )

    tab1_options_layout = [
        [
            sg.Text("Language:", key=Keys.LANGUAGE_TEXT),
            sg.Combo(
                values=LANGUAGES,
                key=Keys.LANGUAGE,
                default_value=sg.user_settings_get_entry(
                    Keys.LANGUAGE, AUTODETECT_OPTION
                ),
                auto_size_text=True,
                readonly=True,
                enable_events=True,
            ),
        ],
        [
            sg.Text("Transcription Model:", key=Keys.MODEL_TEXT),
            sg.Combo(
                values=models,
                key=Keys.MODEL,
                default_value=sg.user_settings_get_entry(
                    Keys.MODEL, DEFAULT_MODEL
                ),
                auto_size_text=True,
                readonly=True,
                enable_events=True,
            ),
        ],
        [
            sg.Text(
                text="Translate to English",
                key=Keys.TRANSLATE_TO_ENGLISH_TEXT,
            ),
            FancyCheckbox(
                start_toggled_on=translate_to_english_last_choice,
                key=Keys.TRANSLATE_TO_ENGLISH_CHECKBOX,
                enable_events=True,
                size_match=True,
                size_match_element_key=Keys.TRANSLATE_TO_ENGLISH_TEXT,
            ),
        ],
        [
            sg.Text("Prompt Profile"),
            sg.Column(
                layout=[
                    [
                        sg.Text(
                            "Initial Prompt",
                            key=Keys.INITIAL_PROMPT_TEXT,
                        ),
                        InfoImage(
                            tooltip=info_image_tooltip,
                            key=Keys.INITIAL_PROMPT_INFO,
                            size_match=True,
                            size_match_element_key=Keys.INITIAL_PROMPT_TEXT,
                        ),
                    ]
                ],
                pad=0,
            ),
        ],
        [
            sg.Combo(
                values=prompt_manager.prompt_profile_names,
                key=Keys.PROMPT_PROFILE_DROPDOWN,
                default_value=startup_prompt_profile,
                readonly=True,
                enable_events=True,
            ),
            sg.Input(
                default_text=prompt_manager.saved_prompt_profiles.get(
                    startup_prompt_profile, ""
                ),
                key=Keys.INITIAL_PROMPT_INPUT,
                expand_x=True,
                enable_events=True,
            ),
        ],
        [
            sg.Button(
                "Prompt Manager",
                key=Keys.START_PROMPT_MANAGER,
            ),
        ],
        [
            sg.Text("Model Information", key=Keys.MODEL_INFO_TEXT),
            FancyToggle(
                start_toggled_on=show_model_info_at_start,
                key=Keys.MODEL_INFO_TOGGLE,
                enable_events=True,
                size_match=True,
                size_match_element_key=Keys.MODEL_INFO_TEXT,
            ),
        ],
    ]

    # number of rows for the table
    num_table_rows = 5

    # whether multiline element strips whitespaces from the end of the
    # new text to append
    is_multiline_rstripping_on_update = False

    # main tab
    tab1_layout = [
        [sg.Text("Select Audio/Video File(s)")],
        [
            sg.Input(disabled=True, expand_x=True),
            sg.FilesBrowse(key=Keys.IN_FILE),
        ],
        [sg.Text("Output Folder:")],
        [
            sg.Input(
                default_text=sg.user_settings_get_entry(Keys.OUT_DIR, ""),
                key=Keys.OUTPUT_DIR_FIELD,
                disabled=True,
                expand_x=True,
                enable_events=True,
            ),
            sg.FolderBrowse(
                target=Keys.OUTPUT_DIR_FIELD,
                key=Keys.OUT_DIR,
                initial_folder=sg.user_settings_get_entry(Keys.OUT_DIR),
            ),
        ],
        [Grid(layout=tab1_options_layout, uniform_block_sizes=False)],
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
                    key=Keys.MODEL_INFO_TABLE,
                    selected_row_colors="black on white",
                    enable_events=True,
                    expand_x=True,
                    expand_y=True,
                    vertical_scroll_only=False,
                    hide_vertical_scroll=True,
                    visible=show_model_info_at_start,
                ),
                expand_x=True,
            )
        ],
        [
            Multiline(
                key=Keys.MULTILINE,
                background_color="black",
                text_color="white",
                auto_refresh=True,
                autoscroll=True,
                reroute_stderr=True,
                reroute_stdout=True,
                reroute_cprint=True,
                write_only=True,
                echo_stdout_stderr=True,
                disabled=True,
                rstrip=is_multiline_rstripping_on_update,
                expand_x=True,
                expand_y=True,
            )
        ],
    ]

    language_specifier = sg.user_settings_get_entry(
        Keys.LANGUAGE_SPECIFIER_SETTING,
        LanguageSpecifier.Options.LANG,
    )

    app_size_frame_layout = [
        [
            sg.Text(
                (
                    f"Size Multiplier ({GUI_Settings.MIN_SCALING} to"
                    f" {GUI_Settings.MAX_SCALING}):"
                ),
                key=Keys.SCALING_TEXT_SETTING,
            ),
            sg.Column(
                layout=[
                    [
                        sg.Input(
                            sg.user_settings_get_entry(
                                Keys.SCALING_INPUT_SETTING,
                                GUI_Settings.DEFAULT_GLOBAL_SCALING,
                            ),
                            size=(5),
                            key=Keys.SCALING_INPUT_SETTING,
                        ),
                        sg.Button(
                            "Apply",
                            key=Keys.APPLY_GLOBAL_SCALING,
                        ),
                    ]
                ],
                pad=0,
            ),
        ]
    ]

    output_folder_frame_layout = [
        [
            sg.Text(
                text="Remember Output Folder",
                key=Keys.SAVE_OUTPUT_DIR_TEXT,
            ),
            FancyCheckbox(
                start_toggled_on=save_output_dir,
                key=Keys.SAVE_OUTPUT_DIR_CHECKBOX,
                enable_events=True,
                size_match=True,
                size_match_element_key=Keys.SAVE_OUTPUT_DIR_TEXT,
            ),
        ]
    ]

    language_specifier_frame_layout = [
        [
            sg.Column(
                layout=[
                    [sg.Text("Specifier")],
                    [
                        sg.Text(
                            "Output File Name Format:",
                            key=Keys.LANGUAGE_SPECIFIER_OUTPUT_FORMAT_TEXT,
                        )
                    ],
                ],
                pad=0,
            ),
            sg.Column(
                layout=[
                    [
                        sg.Combo(
                            values=LanguageSpecifier.Options.get_all_options(),
                            key=Keys.LANGUAGE_SPECIFIER_SETTING,
                            default_value=language_specifier,
                            auto_size_text=True,
                            readonly=True,
                            enable_events=True,
                        ),
                    ],
                    [
                        sg.Text(
                            LanguageSpecifier.TO_EXAMPLE_TEXT[
                                language_specifier
                            ],
                            text_color="black",
                            key=Keys.LANGUAGE_SPECIFIER_EXAMPLE_TEXT,
                        )
                    ],
                ],
                pad=0,
            ),
        ]
    ]

    settings_file_path = get_settings_file_path()

    file_path_frame_layout = [
        [
            sg.Input(
                f"{settings_file_path}",
                size=len(settings_file_path) - 6,
                disabled=True,
            )
        ]
    ]

    tab2_settings_layout = [
        [
            sg.Frame(
                title="Resize the Application",
                layout=app_size_frame_layout,
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                title="Output Folder",
                layout=output_folder_frame_layout,
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                title="Language Specifier",
                layout=language_specifier_frame_layout,
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                title="Settings File Path",
                layout=file_path_frame_layout,
                expand_x=True,
            )
        ],
    ]

    # settings tab
    tab2_layout = [
        [sg.Text("Program Settings", font=(GUI_Settings.DEFAULT_FONT[0], 30))],
        [sg.Column(layout=tab2_settings_layout, pad=0)],
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
                            key=Keys.MAIN_TAB,
                        ),
                        sg.Tab(
                            "Settings",
                            tab2_layout,
                            key=Keys.SETTINGS_TAB,
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
            sg.Button("Start", key=Keys.START, auto_size_button=True),
        ],
    ]

    # Create the window
    window = Window(
        "WhisperGUI - Convert Audio/Video Files to Text",
        layout,
        finalize=True,
        resizable=True,
        auto_size_buttons=True,
        auto_size_text=True,
        alpha_channel=0,
    )

    # Set the window size relative to the screen
    resize_window_relative_to_screen(
        window=window, width_factor=0.9, height_factor=0.85
    )

    # Load the FolderBrowse's selected folder from the settings file
    # (Needed until an arg for FolderBrowse adds this functionality)
    window[Keys.OUT_DIR].TKStringVar.set(
        sg.user_settings_get_entry(Keys.OUT_DIR, "")
    )

    # Switch to the settings tab to load it and then switch back to
    # the main tab
    window[Keys.SETTINGS_TAB].select()
    window.refresh()

    vertically_align_elements(
        window=window,
        keys=(
            Keys.SCALING_TEXT_SETTING,
            Keys.SAVE_OUTPUT_DIR_TEXT,
            Keys.LANGUAGE_SPECIFIER_OUTPUT_FORMAT_TEXT,
        ),
    )
    window[Keys.MAIN_TAB].select()

    # Show the window
    window.reappear()

    return window


def is_custom_checkbox_event(
    window: Optional[sg.Window], event: Optional[str]
) -> bool:
    """Return whether the event is for a custom checkbox.

    Args:
        window (Optional[sg.Window]): The window of the event.
        event (Optional[str]): The event.

    Returns:
        bool: True if the event is for a custom checkbox.
    """
    # No window or event
    if window is None or event is None:
        return False

    # Element lookup
    if event in window.key_dict:
        element = window[event]
    # Event is not for an element in the window
    else:
        return False

    # Check if the element is a custom checkbox
    try:
        element.checked
    except AttributeError:
        return False

    return True


def popup_prompt_manager(
    prompt_manager: PromptManager,
    location: Tuple[Optional[int], Optional[int]] = (None, None),
    alpha_channel: float = None,
) -> Window:
    """Pop up the prompt manager window.

    Args:
        location (Tuple[Optional[int], Optional[int]], optional):
            The location for the prompt manager window. Defaults to
            (None, None).
        alpha_channel (float, optional): The alpha channel to set
            for the prompt manager window. Defaults to None.

    Returns:
        sg.Window: The prompt manager window.
    """
    layout = [
        [
            sg.Table(
                prompt_manager.saved_prompt_profiles_list,
                headings=[" Profile ", " Prompt   "],
                key=Keys.SAVED_PROMPTS_TABLE,
                expand_x=True,
                expand_y=True,
                justification="center",
                auto_size_columns=True,
                max_col_width=100,
                alternating_row_color="LightBlue3",
                selected_row_colors="black on white",
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                enable_events=True,
            ),
            sg.Column(
                [
                    [
                        sg.Button(
                            "Add Profile",
                            key=Keys.OPEN_ADD_PROMPT_WINDOW,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Button(
                            "Edit Profile",
                            key=Keys.OPEN_EDIT_PROMPT_WINDOW,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Button(
                            "Delete Profile",
                            key=Keys.DELETE_PROMPT,
                            expand_x=True,
                        )
                    ],
                    [sg.Text("")],
                    [sg.Text("")],
                    [sg.Text("")],
                    [sg.Text("")],
                    [
                        sg.Button(
                            "Close",
                            focus=True,
                            bind_return_key=True,
                            expand_x=True,
                        )
                    ],
                ],
                vertical_alignment="top",
                expand_x=False,
                pad=(0, 0),
            ),
        ]
    ]

    # Create the window
    win = Window(
        "Prompt Manager",
        layout,
        finalize=True,
        resizable=True,
        auto_size_buttons=True,
        auto_size_text=True,
        location=location,
        alpha_channel=alpha_channel,
    )

    return win


def reload_prompt_manager_window(
    prompt_manager: PromptManager,
    prompt_manager_window: sg.Window,
    modal_window_manager: ModalWindowManager = None,
    window_tracker: WindowTracker = None,
) -> Optional[sg.Window]:
    """Reload the prompt manager window and track the new window.

    Args:
        prompt_manager_window (sg.Window): The prompt manager window
            to reload.
        modal_window_manager (ModalWindowManager, optional): The new
            prompt manager window
            will be tracked and made modal by a modal window manager
            if given. Defaults to None.
        window_tracker (WindowTracker, optional): The new prompt
            manager window will be tracked by a window tracker if
            given. Defaults to None.

    Returns:
        Optional[sg.Window]: The new prompt manager window or None.
    """

    if prompt_manager_window:
        # prompt_manager_window.close()
        # new_prompt_manager_window = popup_prompt_manager()
        x_pos, y_pos = prompt_manager_window.current_location(
            more_accurate=True
        )

        if x_pos is None or y_pos is None:
            sg.PopupError(
                "Error reloading the prompt manager window",
                (
                    "Unable to get the current location of the current"
                    " prompt manager window."
                ),
                "The offensive prompt manager window = ",
                prompt_manager_window,
                keep_on_top=True,
                image=_random_error_emoji(),
            )
            return None

        new_prompt_manager_window = popup_prompt_manager(
            prompt_manager=prompt_manager,
            location=(x_pos, y_pos),
            alpha_channel=0,
        )
        new_prompt_manager_window.reappear()
        prompt_manager_window.close()

        if window_tracker:
            window_tracker.track_window(new_prompt_manager_window)
        if modal_window_manager:
            modal_window_manager.update()
            modal_window_manager.track_modal_window(prompt_manager_window)

        return new_prompt_manager_window
    else:
        return None


def popup_add_edit_prompt_profile(
    title: str,
    submit_event: str,
    profile_name: str = "",
    profile_prompt: str = "",
) -> sg.Window:
    """Pop up either the add or edit prompt profile window.

    Args:
        title (str): The title for the popup window.
        submit_event (str): The event that occurs when new profile
            values are submitted.
        profile_name (str, optional): The editted profile's name
            which prefills the profile name field in the window.
            ONLY FOR PROFILE EDITS. Defaults to "".
        prompt (str, optional): The editted profile's prompt which
            prefills the profile prompt field in the window. ONLY
            FOR PROFILE EDITS. Defaults to "".

    Returns:
        sg.Window: The add/edit prompt profile window.
    """
    layout = [
        [
            [sg.Text("Profile Name")],
            [
                sg.Input(
                    profile_name,
                    key=Keys.NEW_PROFILE_NAME,
                    expand_x=True,
                    metadata=profile_name,
                )
            ],
            [sg.Text("Prompt")],
            [
                sg.Input(
                    profile_prompt,
                    key=Keys.NEW_PROFILE_PROMPT,
                    expand_x=True,
                    metadata=profile_prompt,
                )
            ],
            [
                sg.Button(
                    "Save",
                    key=submit_event,
                    focus=True,
                    bind_return_key=True,
                    expand_x=True,
                ),
                sg.Button(
                    "Cancel",
                    expand_x=True,
                ),
            ],
        ],
    ]

    # Create the window
    win = Window(
        title=title,
        layout=layout,
        finalize=True,
        resizable=True,
        auto_size_buttons=True,
        auto_size_text=True,
    )

    return win


def popup_add_prompt_profile(
    title: str,
    submit_event: str,
) -> sg.Window:
    """Pop up the add prompt profile window.

    Args:
        title (str): The title for the popup window.
        submit_event (str): The event that occurs when new profile
            values are submitted.

    Returns:
        sg.Window: The add prompt profile window.
    """
    return popup_add_edit_prompt_profile(
        title=title, submit_event=submit_event
    )


def popup_edit_prompt_profile(
    title: str,
    submit_event: str,
    profile_name: str = "",
    profile_prompt: str = "",
) -> sg.Window:
    """Pop up either the edit prompt profile window.

    Args:
        title (str): The title for the popup window.
        submit_event (str): The event that occurs when new profile
            values are submitted.
        profile_name (str, optional): The editted profile's name
            which prefills the profile name field in the window.
            ONLY FOR PROFILE EDITS. Defaults to "".
        prompt (str, optional): The editted profile's prompt which
            prefills the profile prompt field in the window. ONLY
            FOR PROFILE EDITS. Defaults to "".

    Returns:
        sg.Window: The edit prompt profile window.
    """
    return popup_add_edit_prompt_profile(
        title=title,
        submit_event=submit_event,
        profile_name=profile_name,
        profile_prompt=profile_prompt,
    )


class LanguageSpecifier:
    """Language specifier related info."""

    class Options:
        # Options used in the language specifier setting
        LANG = "Language"
        CODE = "Language Code"

        @classmethod
        def get_all_options(cls) -> Tuple[str, ...]:
            """Return all language specifier options.

            Returns:
                Tuple[str, ...]: All language specifier options.
            """
            return (cls.LANG, cls.CODE)

    EXAMPLE_TEXTS = ("video.english.txt", "video.en.txt")
    TO_EXAMPLE_TEXT = dict(zip(Options.get_all_options(), EXAMPLE_TEXTS))


class Keys:
    """Keys for elements and/or settings."""

    # Shared prefixes for keys
    CHECKBOX_KEY_PREFIX = "-CHECKBOX-"
    INFO_IMAGE_KEY_PREFIX = "-INFO-"

    # Keys for main tab
    MULTILINE = "-CONSOLE-OUTPUT-"
    IN_FILE = "-IN-FILE-"
    OUT_DIR = "-OUT-FOLDER-"
    OUTPUT_DIR_FIELD = "-OUT-FOLDER-FIELD-"
    LANGUAGE = "-LANGUAGE-"
    LANGUAGE_TEXT = "-LANGUAGE-TEXT-"
    MODEL = "-MODEL-"
    MODEL_TEXT = "-MODEL-TEXT-"
    TRANSLATE_TO_ENGLISH_TEXT = "-TRANSLATE-OPTION-TEXT-"
    TRANSLATE_TO_ENGLISH_CHECKBOX = CHECKBOX_KEY_PREFIX + "TRANSLATE-"
    MODEL_INFO_TEXT = "-MODEL-TABLE-TEXT-"
    MODEL_INFO_TOGGLE = "-TOGGLE-MODEL-TABLE-"
    MODEL_INFO_TABLE = "-MODEL-TABLE-"
    INITIAL_PROMPT_TEXT = "-INITIAL-PROMPT-TEXT-"
    INITIAL_PROMPT_INPUT = "-INITIAL-PROMPT-"
    INITIAL_PROMPT_INFO = INFO_IMAGE_KEY_PREFIX + "INITIAL-PROMPT-"
    PROMPT_PROFILE_DROPDOWN = "-PROMPT-PROFILE-"
    START_PROMPT_MANAGER = "-START-PROMPT-MANAGER-"
    START = "-START-TRANSCRIPTIONS-"
    PROGRESS = "-PROGRESS-"

    # Keys for prompt manager window
    SAVED_PROMPTS_TABLE = "-SAVED-PROMPTS-TABLE-"
    OPEN_ADD_PROMPT_WINDOW = "-OPEN-ADD-PROMPT-WINDOW-"
    OPEN_EDIT_PROMPT_WINDOW = "-OPEN-EDIT-PROMPT-WINDOW-"
    DELETE_PROMPT = "-DELETE-PROMPT-"

    # Keys for add/edit prompt window
    NEW_PROFILE_NAME = "-NEW-PROMPT-NAME-"
    NEW_PROFILE_PROMPT = "-NEW-PROMPT-"

    ADD_PROMPT_PROFILE = "-ADD-PROMPT-"
    EDIT_PROMPT_PROFILE = "-EDIT-PROMPT-"

    # Keys for settings tab
    APPLY_GLOBAL_SCALING = "-SAVE-SCALING-"
    SCALING_TEXT_SETTING = "-GLOBAL-SCALING-TEXT-"
    SCALING_INPUT_SETTING = "-GLOBAL-SCALING-"
    SAVE_OUTPUT_DIR_TEXT = "-SAVE-OUTPUT-DIR-TEXT-"
    SAVE_OUTPUT_DIR_CHECKBOX = CHECKBOX_KEY_PREFIX + "SAVE-OUTPUT-DIR-"
    LANGUAGE_SPECIFIER_SETTING = "-LANGUAGE-SPECIFIER-"
    LANGUAGE_SPECIFIER_EXAMPLE_TEXT = "-LANGUAGE-SPECIFIER-EXAMPLE-TEXT-"
    LANGUAGE_SPECIFIER_OUTPUT_FORMAT_TEXT = (
        "-LANGUAGE-SPECIFIER-OUTPUT-FORMAT-TEXT-"
    )

    # Keys for tabs
    MAIN_TAB = "-MAIN-TAB-"
    SETTINGS_TAB = "-SETTINGS-TAB-"

    # Key for saved prompts in the settings file
    SAVED_PROMPTS_SETTINGS = "SAVED PROMPTS"


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
    TRANSCRIBE_DONE_EVENTS = (
        TRANSCRIBE_SUCCESS,
        TRANSCRIBE_ERROR,
        TRANSCRIBE_STOPPED,
    )


def popup_tracked_scaling_invalid(
    window_tracker: WindowTracker, modal_window_manager: ModalWindowManager
) -> None:
    """Pop up a tracked modal message window indicating an
    invalid scaling input.
    """
    popup_window = popup_tracked(
        (
            "Please enter a number for the scaling factor between"
            f" {GUI_Settings.MIN_SCALING} and"
            f" {GUI_Settings.MAX_SCALING}."
        ),
        popup_fn=popup,
        window_tracker=window_tracker,
        title="Invalid scaling factor",
        non_blocking=True,
    )
    modal_window_manager.track_modal_window(popup_window)


class NonExistentPromptProfileName(Exception):
    """A non-existent prompt profile name was used."""


class PromptManager:
    """A manager for prompt profiles."""

    _unsaved_prompt_profile_name = "(None)"

    def __init__(self, saved_prompts_settings_key: str) -> None:
        """
        Args:
            saved_prompts_settings_key (str): Key for the saved prompts
                in the settings file.
        """
        self._saved_prompts_settings_key = saved_prompts_settings_key
        self.saved_prompt_profiles = sg.user_settings_get_entry(
            self._saved_prompts_settings_key, {}
        )
        self._dropdown_window = None
        self._dropdown_key: Optional[str] = None

    @property
    def unsaved_prompt_profile_name(self) -> str:
        """Name of the Prompt profile for when the user is not using a
        saved prompt profile.
        """
        return self._unsaved_prompt_profile_name

    @property
    def saved_prompt_profiles(self) -> Dict[str, str]:
        """A dict with the saved prompt profiles names and their prompt
        values.
        """
        self._saved_prompt_profiles: Dict[
            str, str
        ] = sg.user_settings_get_entry(
            self._saved_prompts_settings_key, self._saved_prompt_profiles
        )
        return self._saved_prompt_profiles

    @saved_prompt_profiles.setter
    def saved_prompt_profiles(self, new_prompt_dict: Dict[str, str]) -> None:
        self._saved_prompt_profiles = new_prompt_dict

    @saved_prompt_profiles.deleter
    def saved_prompt_profiles(self) -> None:
        self._saved_prompt_profiles.clear()

    @property
    def prompt_profile_names(self) -> List[str]:
        """The unsaved prompt profile name and the sorted ascending
        names of the saved prompt profiles.
        """
        return [
            self.unsaved_prompt_profile_name,
            *sorted(self.saved_prompt_profiles.keys()),
        ]

    @property
    def saved_prompt_profiles_list(self) -> List[Tuple[str, str]]:
        """The saved prompt profiles as a list of tuples sorted
        ascending.
        """
        return sorted(self.saved_prompt_profiles.items(), key=itemgetter(0))

    @property
    def saved_prompt_profile_names(self) -> List[str]:
        """The names of the saved prompt profiles sorted ascending."""
        return sorted(self.saved_prompt_profiles.keys())

    def add_prompt_profile(
        self, profile_name: str, profile_prompt: str
    ) -> Tuple[bool, str]:
        """Add a new prompt profile.

        Args:
            profile_name (str): The name for the new prompt profile.
            profile_prompt (str): The prompt for the new prompt profile.

        Returns:
            Tuple[bool, str]: Tuple with the success state and an error
                message. The success state will be True if the prompt
                profile was successfully added. False, otherwise. The
                error message will be an empty string if no error
                occurred.
        """
        error_msg = ""

        # Invalid prompt name. Prompt name is empty or only has
        # whitespaces.
        if not profile_name.strip():
            error_msg = (
                "Invalid prompt name: name can't be empty or whitespace only."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        # Invalid prompt name. Prompt name already in use.
        if profile_name in self.prompt_profile_names:
            error_msg = (
                "Invalid prompt name: name already in use."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        self._save_profile(
            profile_name=profile_name, profile_prompt=profile_prompt
        )

        return True, error_msg

    def edit_prompt_profile(
        self,
        profile_name: str,
        profile_prompt: str,
        original_profile_name: str,
    ) -> Tuple[bool, str]:
        """Edit a prompt profile.

        Args:
            profile_name (str): The new name for the prompt profile.
            profile_prompt (str): The new prompt for the prompt profile.
            original_profile_name (str): The original name of the prompt
                profile being edited.

        Returns:
            Tuple[bool, str]: Tuple with the success state and an error
                message. The success state will be True if the prompt
                profile was successfully editted. False, otherwise. The
                error message will be an empty string if no error
                occurred.
        """
        is_successful = False

        profile_name_changed = profile_name != original_profile_name

        # Invalid prompt name. Prompt name is empty or only has
        # whitespaces.
        if not profile_name.strip():
            error_msg = (
                "Invalid prompt name: name can't be empty or whitespace only."
                "\n\nPlease enter a new prompt name."
            )
            return is_successful, error_msg
        # Invalid prompt name. Profile name is already in use and user
        # isn't editing the selected profile's prompt.
        elif (
            profile_name in self.prompt_profile_names and profile_name_changed
        ):
            error_msg = (
                "Invalid prompt name: name already in use."
                "\n\nPlease enter a new prompt name."
            )
            return is_successful, error_msg
        else:
            is_successful = True

        self._save_profile(
            profile_name=profile_name,
            profile_prompt=profile_prompt,
            original_profile_name=original_profile_name,
        )

        error_msg = ""
        return is_successful, error_msg

    def _save_profile(
        self,
        profile_name: str,
        profile_prompt: str,
        original_profile_name: str = None,
    ) -> None:
        """Save the prompt profile while overwriting the original
        profile if it is given.

        Overwrites an existing prompt profile if it already exists.

        Args:
            prompt_name (str): The name for the prompt profile.
            prompt (str): The prompt for the prompt profile.
            original_profile_name (str, None): The original name of the
                prompt profile being edited if applicable. Defaults to
                None.
        """
        # Editing a profile. Delete the old prompt profile.
        if original_profile_name is not None:
            with suppress(KeyError):
                del self.saved_prompt_profiles[original_profile_name]

        # Save the new profile
        self.saved_prompt_profiles[profile_name] = profile_prompt

        self._save_profiles_to_settings()

        if self._dropdown:
            selected_dropdown_profile_name = self._dropdown.get()

            # Edited the currently selected profile in the dropdown.
            # Select the new profile.
            if (
                original_profile_name is not None
                and original_profile_name == selected_dropdown_profile_name
            ):
                self._update_prompt_profile_dropdown(
                    new_selected_profile=profile_name
                )
            # Added a profile or did not edit the currently selected
            # profile in the dropdown
            else:
                self._update_prompt_profile_dropdown()

    def delete_prompt_profile(self, profile_name: str) -> None:
        """Delete a prompt profile by name.

        Args:
            prompt_name (str): The name of the prompt profile to be
                deleted.
        """
        del self.saved_prompt_profiles[profile_name]

        self._save_profiles_to_settings()

        # Get the currently selected profile in the dropdown
        if self._dropdown:
            selected_prompt_profile_name = self._dropdown.get()

            # Update the profile dropdown and select the unsaved prompt
            # profile in the dropdown since the current profile
            # selection was deleted
            if profile_name == selected_prompt_profile_name:
                self._update_prompt_profile_dropdown(
                    new_selected_profile=self.unsaved_prompt_profile_name
                )
            # Update the profile dropdown and keep the current profile
            # selection
            else:
                self._update_prompt_profile_dropdown()

    def _save_profiles_to_settings(self) -> None:
        """Update the settings file with the current prompt profiles."""
        sg.user_settings_set_entry(
            self._saved_prompts_settings_key, self.saved_prompt_profiles
        )

    @property
    def _dropdown(self) -> Optional[sg.Combo]:
        """The prompt profile dropdown element that will be updated
        when the prompt profiles change.

        Returns:
            Optional[sg.Combo]: Returns the dropdown element if known.
                Else, returns None.
        """
        if self._dropdown_window and self._dropdown_key is not None:
            return self._dropdown_window[self._dropdown_key]
        else:
            return None

    def set_prompt_profile_dropdown(self, window: sg.Window, key: str) -> None:
        """Set the prompt profile dropdown element that will be updated
        when the prompt profiles change.

        Args:
            window (sg.Window): The window containing the dropdown
                element.
            key (str): The key for the dropdown element.
        """
        self._dropdown_window = window
        self._dropdown_key = key

    def _update_prompt_profile_dropdown(
        self, new_selected_profile: Union[str, EllipsisType] = ...
    ) -> None:
        """Update the tracked prompt profile dropdown element if it
        exists.

        Args:
            new_selected_profile (str, EllipsisType): The dropdown
                selection will be changed to this profile if given.
                Defaults to ... .
        """
        if self._dropdown:
            selected_profile = new_selected_profile

            # Keep the old selection for the dropdown if a new selection
            #  is not given
            if selected_profile is ...:
                selected_profile = self._dropdown.get()

            # The width of the dropbox that fits all options
            new_dropdown_width = len(max(self.prompt_profile_names, key=len))

            # Update the prompt profile list and the selected profile
            # for the dropdown
            self._dropdown.update(
                value=selected_profile,
                values=self.prompt_profile_names,
                size=(new_dropdown_width, None),
            )

            # Send an event changing the dropdown selection if a new
            # selected profile is given.
            if (
                self._dropdown_window
                and self._dropdown_key is not None
                and new_selected_profile is not ...
            ):
                self._dropdown_window.write_event_value(
                    self._dropdown_key, new_selected_profile
                )


class Transcriber:
    """A manager for transcription tasks."""

    def __init__(self) -> None:
        self.is_transcribing = False
        self._transcription_timer = CustomTimer()
        self.num_tasks = 0
        self.num_tasks_done = 0

        # Paths for the users selected audio video files to transcribe
        self.audio_video_file_paths: Tuple = tuple()

        # Thread that runs transcriptions as new processes
        self.transcribe_thread: Optional[threading.Thread] = None

        # Stop flag for the thread
        self.stop_transcriptions_flag = threading.Event()

    def start_timer(self) -> None:
        """Start the timer for a new set of transcription tasks.

        Raises:
            TimerError: Timer is already running.
        """
        self._transcription_timer.start()

    def stop_timer(self, log_time: bool = False) -> float:
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

    def stop_transcribing(self) -> None:
        """Signal the thread to stop transcribing."""
        self.stop_transcriptions_flag.set()

    def clear(self) -> None:
        """Set the manager to wait for new tasks."""
        with suppress(TimerError):
            self.stop_timer(log_time=False)

        self.is_transcribing = False
        self.num_tasks = 0
        self.num_tasks_done = 0
        self.transcribe_thread = None
        self.stop_transcriptions_flag.clear()

    def is_waiting_for_tasks_stop(self) -> bool:
        return self.stop_transcriptions_flag.is_set()


class CustomTimer(Timer):
    """codetiming.Timer with a stop() that optionally prints the elapsed
    time.
    """

    def stop(self, log_time: bool = False) -> float:
        """Stop the timer, and optionally report the elapsed time.

        Args:
            log_time (bool, optional): If True, prints the elapsed time.
                Defaults to False.

        Raises:
            TimerError: Timer is not running.

        Returns:
            float: The elapsed time in seconds.
        """
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
    use_language_code: bool = False,
    initial_prompt: str = None,
) -> None:
    """Transcribe a list of audio/video files.

    Results are written to files with the same name but with .txt, .vtt,
    and .srt extensions.

    Args:
        window (sg.Window): The window to send events to.
        audio_video_file_paths (Iterable[str]): An Iterable with the
            audio/vidoe file paths.
        output_dir_path (str): The output directory path.
        language (str): The language of the file(s) to transcribe.
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
    language: str,
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
        language (str): The language of the file to transcribe.
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


def cycle_gui_through_themes() -> None:
    """Cycles through the GUI with every built-in theme. Close the
    current GUI for the GUI with the next theme to pop up.
    """
    themes = [
        "Black",
        "BlueMono",
        "BluePurple",
        "BrightColors",
        "BrownBlue",
        "Dark",
        "Dark2",
        "DarkAmber",
        "DarkBlack",
        "DarkBlack1",
        "DarkBlue",
        "DarkBlue1",
        "DarkBlue10",
        "DarkBlue11",
        "DarkBlue12",
        "DarkBlue13",
        "DarkBlue14",
        "DarkBlue15",
        "DarkBlue16",
        "DarkBlue17",
        "DarkBlue2",
        "DarkBlue3",
        "DarkBlue4",
        "DarkBlue5",
        "DarkBlue6",
        "DarkBlue7",
        "DarkBlue8",
        "DarkBlue9",
        "DarkBrown",
        "DarkBrown1",
        "DarkBrown2",
        "DarkBrown3",
        "DarkBrown4",
        "DarkBrown5",
        "DarkBrown6",
        "DarkBrown7",
        "DarkGreen",
        "DarkGreen1",
        "DarkGreen2",
        "DarkGreen3",
        "DarkGreen4",
        "DarkGreen5",
        "DarkGreen6",
        "DarkGreen7",
        "DarkGrey",
        "DarkGrey1",
        "DarkGrey10",
        "DarkGrey11",
        "DarkGrey12",
        "DarkGrey13",
        "DarkGrey14",
        "DarkGrey15",
        "DarkGrey2",
        "DarkGrey3",
        "DarkGrey4",
        "DarkGrey5",
        "DarkGrey6",
        "DarkGrey7",
        "DarkGrey8",
        "DarkGrey9",
        "DarkPurple",
        "DarkPurple1",
        "DarkPurple2",
        "DarkPurple3",
        "DarkPurple4",
        "DarkPurple5",
        "DarkPurple6",
        "DarkPurple7",
        "DarkRed",
        "DarkRed1",
        "DarkRed2",
        "DarkTanBlue",
        "DarkTeal",
        "DarkTeal1",
        "DarkTeal10",
        "DarkTeal11",
        "DarkTeal12",
        "DarkTeal2",
        "DarkTeal3",
        "DarkTeal4",
        "DarkTeal5",
        "DarkTeal6",
        "DarkTeal7",
        "DarkTeal8",
        "DarkTeal9",
        "Default",
        "Default1",
        "DefaultNoMoreNagging",
        "GrayGrayGray",
        "Green",
        "GreenMono",
        "GreenTan",
        "HotDogStand",
        "Kayak",
        "LightBlue",
        "LightBlue1",
        "LightBlue2",
        "LightBlue3",
        "LightBlue4",
        "LightBlue5",
        "LightBlue6",
        "LightBlue7",
        "LightBrown",
        "LightBrown1",
        "LightBrown10",
        "LightBrown11",
        "LightBrown12",
        "LightBrown13",
        "LightBrown2",
        "LightBrown3",
        "LightBrown4",
        "LightBrown5",
        "LightBrown6",
        "LightBrown7",
        "LightBrown8",
        "LightBrown9",
        "LightGray1",
        "LightGreen",
        "LightGreen1",
        "LightGreen10",
        "LightGreen2",
        "LightGreen3",
        "LightGreen4",
        "LightGreen5",
        "LightGreen6",
        "LightGreen7",
        "LightGreen8",
        "LightGreen9",
        "LightGrey",
        "LightGrey1",
        "LightGrey2",
        "LightGrey3",
        "LightGrey4",
        "LightGrey5",
        "LightGrey6",
        "LightPurple",
        "LightTeal",
        "LightYellow",
        "Material1",
        "Material2",
        "NeutralBlue",
        "Purple",
        "Python",
        "PythonPlus",
        "Reddit",
        "Reds",
        "SandyBeach",
        "SystemDefault",
        "SystemDefault1",
        "SystemDefaultForReal",
        "Tan",
        "TanBlue",
        "TealMono",
        "Topanga",
    ]

    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    s_handler = logging.StreamHandler()
    logger.addHandler(s_handler)

    for theme in themes:
        logger.info(f"theme={theme}")
        GUI_Settings.THEME = theme
        start_GUI()


if __name__ == "__main__":
    # Required for when a program which uses multiprocessing has been
    # frozen to produce a Windows executable. (Has been tested with
    # py2exe, PyInstaller and cx_Freeze.) has no effect when invoked on
    # any operating system other than Windows
    multiprocessing.freeze_support()

    # The only method that works on both Windows and Linux is "spawn"
    multiprocessing.set_start_method("spawn")
    main()
