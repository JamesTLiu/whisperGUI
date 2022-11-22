#!/usr/bin/env python3

from __future__ import annotations
from dataclasses import dataclass

import decimal
from functools import partial, partialmethod
import io
import multiprocessing
import operator
import platform
import re
import signal
import sys
import threading
import time
from contextlib import suppress
from decimal import Decimal
from itertools import islice, zip_longest
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as EventClass
from operator import itemgetter
from pathlib import Path
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
    Union,
)

from multipledispatch import dispatch

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import Connection as PipeConnection  # type: ignore

if TYPE_CHECKING:
    from types import FrameType

import tkinter as tk
from collections import namedtuple

import PySimpleGUI as sg
import whisper
from codetiming import Timer, TimerError
from whisper.tokenizer import LANGUAGES as TO_LANGUAGE
from whisper.tokenizer import TO_LANGUAGE_CODE
from whisper.utils import write_srt, write_txt, write_vtt

import set_env


def main():
    set_env.set_env_vars()
    start_GUI()


def start_GUI() -> None:
    """Start the GUI.

    Raises:
        NonExistentPromptProfileName: A non-existent prompt profile name was used.
    """

    sg.theme("Dark Blue 3")

    # Config file
    config_file_path = sg.user_settings_filename(filename="whisperGUI.config")

    checkbox_key_prefix = "-CHECKBOX-"

    info_image_key_prefix = "-INFO-"

    # Keys for main tab
    multiline_key = "-CONSOLE-OUTPUT-"
    in_file_key = "-IN-FILE-"
    out_dir_key = "-OUT-FOLDER-"
    output_dir_field_key = "-OUT-FOLDER-FIELD-"
    language_key = "-LANGUAGE-"
    language_text_key = "-LANGUAGE-TEXT-"
    model_key = "-MODEL-"
    model_text_key = "-MODEL-TEXT-"
    translate_to_english_text_key = "-TRANSLATE-OPTION-TEXT-"
    translate_to_english_checkbox_key = checkbox_key_prefix + "TRANSLATE-"
    model_info_toggle_key = "-TOGGLE-MODEL-TABLE-"
    model_info_table_key = "-MODEL-TABLE-"
    initial_prompt_text_key = "-INITIAL-PROMPT-TEXT-"
    initial_prompt_input_key = "-INITIAL-PROMPT-"
    initial_prompt_info_key = info_image_key_prefix + "INITIAL-PROMPT-"
    prompt_profile_dropdown_key = "-PROMPT-PROFILE-"
    start_prompt_manager_key = "-START-PROMPT-MANAGER-"
    start_key = "-START-TRANSCRIPTIONS-"
    progress_key = "-PROGRESS-"

    # Keys for prompt manager window
    saved_prompts_table_key = "-SAVED-PROMPTS-TABLE-"
    open_add_prompt_window_key = "-OPEN-ADD-PROMPT-WINDOW-"
    open_edit_prompt_window_key = "-OPEN-EDIT-PROMPT-WINDOW-"
    delete_prompt_key = "-DELETE-PROMPT-"

    # Keys for add/edit prompt window
    new_profile_name_key = "-NEW-PROMPT-NAME-"
    new_profile_prompt_key = "-NEW-PROMPT-"

    add_prompt_profile_key = "-ADD-PROMPT-"
    edit_prompt_profile_key = "-EDIT-PROMPT-"

    # Keys for settings tab
    apply_global_scaling_key = "-SAVE-SCALING-"
    scaling_text_setting_key = "-GLOBAL-SCALING-TEXT-"
    scaling_input_setting_key = "-GLOBAL-SCALING-"
    save_output_dir_text_key = "-SAVE-OUTPUT-DIR-TEXT-"
    save_output_dir_checkbox_key = checkbox_key_prefix + "SAVE-OUTPUT-DIR-"
    language_specifier_text_setting_key = "-LANGUAGE-SPECIFIER-TEXT-"
    language_specifier_setting_key = "-LANGUAGE-SPECIFIER-"

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

    # Key for saved prompts in the settings file
    SAVED_PROMPTS_SETTINGS_KEY = "SAVED PROMPTS"

    prompt_manager = PromptManager(SAVED_PROMPTS_SETTINGS_KEY)

    # scaling of the application's size
    DEFAULT_GLOBAL_SCALING = 1.5

    # Range of accepted scaling factor values from the user
    MIN_SCALING = 0.5
    MAX_SCALING = 3

    # Default global font for the GUI
    GUI_FONT = ("Arial", 20)

    # Set global GUI options
    sg.set_options(
        scaling=sg.user_settings_get_entry(
            scaling_input_setting_key, DEFAULT_GLOBAL_SCALING
        ),
        font=GUI_FONT,
        tooltip_font=GUI_FONT,
        force_modal_windows=True,
    )

    icon_data = b"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"
    sg.set_global_icon(icon_data)

    # number of rows for the table
    num_table_rows = 5

    # whether multiline element strips whitespaces from the end of the new text to append
    is_multiline_rstripping_on_update = False

    # Options used in the language specifier setting
    LANGUAGE_SPECIFIER_AS_LANG = "Language"
    LANGUAGE_SPECIFIER_AS_CODE = "Language Code"

    # tracker for possibly active windows
    window_tracker = WindowTracker()

    def make_main_window() -> sg.Window:
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

        # Startup prompt profile
        startup_prompt_profile = sg.user_settings_get_entry(
            prompt_profile_dropdown_key, prompt_manager.unsaved_prompt_profile_name
        )

        show_model_info_at_start = False

        # The tab1 option elements as rows
        tab1_options_rows = [
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
            size_matched_image_element(
                size_match_element=sg.Text(
                    text="Translate to English",
                    key=translate_to_english_text_key,
                ),
                image_element=FancyCheckbox(
                    start_toggled_on=translate_to_english_last_choice,
                    key=translate_to_english_checkbox_key,
                    enable_events=True,
                    size_match=True,
                ),
            ),
            [
                sg.Text("Prompt Profile"),
                sg.Column(
                    [
                        [
                            sg.Text(
                                "Initial Prompt",
                                tooltip=(
                                    "Use this when a dialect/style of a language or punctuation is desired.\n"
                                    "Does NOT guarantee the result will follow the initial prompt.\n"
                                    "Initial prompt will NOT be included in the result.\n"
                                    "Try a larger model if the result does not follow the initial prompt.\n\n"
                                    "Ex. Chinese (simplified) with punctuation: 以下是普通话的句子。"
                                ),
                                key=initial_prompt_text_key,
                            ),
                            InfoImage(
                                tooltip=(
                                    "Use this when a dialect/style of a language or punctuation is desired.\n"
                                    "Does NOT guarantee the result will follow the initial prompt.\n"
                                    "Initial prompt will NOT be included in the result.\n"
                                    "Try a larger model if the result does not follow the initial prompt.\n\n"
                                    "Ex. Chinese (simplified) with punctuation: 以下是普通话的句子。"
                                ),
                                key=initial_prompt_info_key,
                                size_match=True,
                                size_match_element_type=sg.Text,
                            ),
                        ]
                    ],
                    pad=0,
                ),
            ],
            [
                sg.Combo(
                    values=prompt_manager.prompt_profile_names,
                    key=prompt_profile_dropdown_key,
                    default_value=startup_prompt_profile,
                    readonly=True,
                    enable_events=True,
                ),
                sg.Input(
                    default_text=prompt_manager.saved_prompt_profiles.get(
                        startup_prompt_profile, ""
                    ),
                    key=initial_prompt_input_key,
                    expand_x=True,
                    enable_events=True,
                ),
            ],
            size_matched_image_element(
                size_match_element=sg.Button(
                    "Prompt Manager",
                    key=start_prompt_manager_key,
                ),
                image_element=EmptyImage(
                    size_match=True,
                ),
            ),
            [
                sg.Text("Model Information"),
                FancyToggle(
                    start_toggled_on=show_model_info_at_start,
                    key=model_info_toggle_key,
                    size_match=True,
                    size_match_element_type=sg.Text,
                    enable_events=True,
                ),
            ],
        ]

        class SizeMatchingEmptyImage(EmptyImage):
            __init__ = partialmethod(EmptyImage.__init__, size_match=True)  # type: ignore

        # Put the options in columns to align their components
        tab1_options_layout = convert_rows_to_columns_for_elements(
            rows=tab1_options_rows,
            fill_element_type=SizeMatchingEmptyImage,
        )

        # main tab
        tab1_layout = [
            [sg.Text("Select Audio/Video File(s)")],
            [sg.Input(disabled=True, expand_x=True), sg.FilesBrowse(key=in_file_key)],
            [sg.Text("Output Folder:")],
            [
                sg.Input(
                    default_text=sg.user_settings_get_entry(out_dir_key, ""),
                    key=output_dir_field_key,
                    disabled=True,
                    expand_x=True,
                    enable_events=True,
                ),
                sg.FolderBrowse(
                    target=output_dir_field_key,
                    key=out_dir_key,
                    initial_folder=sg.user_settings_get_entry(out_dir_key),
                ),
            ],
            tab1_options_layout,
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
                        visible=show_model_info_at_start,
                    ),
                    expand_x=True,
                )
            ],
            [
                Multiline(
                    key=multiline_key,
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

        language_specifier_options = (
            LANGUAGE_SPECIFIER_AS_LANG,
            LANGUAGE_SPECIFIER_AS_CODE,
        )

        # settings tab
        # tab2_layout = [
        #     [sg.Text("Program Settings", font=(GUI_FONT[0], 30))],
        #     [sg.HorizontalSeparator()],
        #     [sg.Text("Resize the Application", font=(GUI_FONT[0], 22))],
        #     [
        #         sg.Text(
        #             f"Size Multiplier ({MIN_SCALING} to {MAX_SCALING}):",
        #             key=scaling_text_setting_key,
        #         ),
        #         sg.Input(
        #             sg.user_settings_get_entry(
        #                 scaling_input_setting_key, DEFAULT_GLOBAL_SCALING
        #             ),
        #             size=(5),
        #             key=scaling_input_setting_key,
        #         ),
        #         sg.Button("Apply", key=apply_global_scaling_key),
        #     ],
        #     [sg.HorizontalSeparator()],
        #     size_matched_image_element(
        #         size_match_element=sg.Text(
        #             text="Remember Output Folder",
        #             key=save_output_dir_text_key,
        #         ),
        #         image_element=FancyCheckbox(
        #             start_toggled_on=save_output_dir,
        #             key=save_output_dir_checkbox_key,
        #             enable_events=True,
        #             size_match=True,
        #         ),
        #     ),
        #     [sg.HorizontalSeparator()],
        #     [
        #         sg.Text(
        #             "Language Specifier in Output File Names",
        #             key=language_specifier_text_setting_key,
        #         ),
        #         sg.Combo(
        #             values=language_specifier_options,
        #             key=language_specifier_setting_key,
        #             default_value=sg.user_settings_get_entry(
        #                 language_specifier_setting_key, language_specifier_options[0]
        #             ),
        #             auto_size_text=True,
        #             readonly=True,
        #             enable_events=True,
        #         ),
        #     ],
        #     [
        #         sg.Column(
        #             [[sg.Text("      Language:")], [sg.Text("      Language Code:")]],
        #             pad=0,
        #         ),
        #         sg.Column(
        #             [[sg.Text("video.english.txt")], [sg.Text("video.en.txt")]], pad=0
        #         ),
        #     ],
        #     [sg.HorizontalSeparator()],
        #     [sg.Text(f"Location of the Settings File:")],
        #     [
        #         sg.Input(
        #             f"{config_file_path}", size=len(config_file_path) - 6, disabled=True
        #         )
        #     ],
        # ]

        tab2_layout = [
            [
                sg.Text(
                    f"Size Multiplier ({MIN_SCALING} to {MAX_SCALING}):",
                    key=scaling_text_setting_key,
                ),
                sg.Button("Apply", key=apply_global_scaling_key),
            ],
            [sg.Text("foo"), sg.Text("bar")],
            [
                sg.Text(
                    "Language Specifier in Output File Names",
                    key=language_specifier_text_setting_key,
                ),
                sg.Combo(
                    values=language_specifier_options,
                    key=language_specifier_setting_key,
                    default_value=sg.user_settings_get_entry(
                        language_specifier_setting_key, language_specifier_options[0]
                    ),
                    auto_size_text=True,
                    readonly=True,
                    enable_events=True,
                ),
            ],
        ]

        tab2_columns = convert_rows_to_columns_for_elements(tab2_layout, sg.Button)

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
                                # tab2_layout,
                                [tab2_columns],
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
            window=window, width_factor=0.6, height_factor=0.85
        )

        # Load the FolderBrowse's selected folder from the settings file
        # (Needed until an arg for FolderBrowse adds this functionality)
        window[out_dir_key].TKStringVar.set(sg.user_settings_get_entry(out_dir_key, ""))

        # set_same_width(
        #     [
        #         window[scaling_text_setting_key],
        #         window[save_output_dir_text_key],
        #         window[language_specifier_text_setting_key],
        #     ]
        # )

        window.reappear()

        # ----------------- Test -------------------#
        window[settings_tab_key].select()

        window.refresh()

        set_row_size_of_element(window[apply_global_scaling_key], 100)
        # ----------------- EndTest ----------------#

        return window

    def set_row_size_of_element(
        element: sg.Element, width: Optional[int] = None, height: Optional[int] = None
    ):
        """Forcefully set the size of the row that the element is in. The row will no longer
        fit to its children.

        Args:
            element (sg.Element): The element whose row is to be resized.
            width (Optional[int], optional): New width of the row. Defaults to None.
            height (Optional[int], optional): New height of the row. Defaults to None.
        """
        current_width, current_height = element.get_size()

        row_frame: tk.Frame = element.ParentRowFrame

        new_width = width if width is not None else current_width
        new_height = height if height is not None else current_height

        row_frame.config(bg="skyblue3", height=new_width, width=new_height)
        row_frame.pack_propagate(flag=False)

    def make_tracked_main_window_with_synced_profiles(
        window_tracker: WindowTracker,
        prompt_manager: PromptManager,
        prompt_profile_dropdown_key: str,
    ) -> sg.Window:
        """Create a tracked main window whose prompt profile dropdown is updated by the
        prompt manager when needed.

        Args:
            window_tracker (WindowTracker): The window tracker to add the created window to.
            prompt_manager (PromptManager): The prompt manager for the application.
            prompt_profile_dropdown_key (str): The key of the prompt profile dropdown that's updated by the
                prompt manager when needed.

        Returns:
            sg.Window: The created main window.
        """

        window = window_tracker.track_window(make_main_window())

        # give the prompt manager the prompt profile dropdown so that it's updated on profile changes
        prompt_manager.set_prompt_profile_dropdown(window, prompt_profile_dropdown_key)
        return window

    main_window = make_tracked_main_window_with_synced_profiles(
        window_tracker=window_tracker,
        prompt_manager=prompt_manager,
        prompt_profile_dropdown_key=prompt_profile_dropdown_key,
    )

    def popup_prompt_manager() -> sg.Window:
        """Pop up the prompt manager window.

        Returns:
            sg.Window: The prompt manager window.
        """
        layout = [
            [
                sg.Table(
                    prompt_manager.saved_prompt_profiles_list,
                    headings=[" Profile ", " Prompt   "],
                    key=saved_prompts_table_key,
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
                                key=open_add_prompt_window_key,
                                expand_x=True,
                            )
                        ],
                        [
                            sg.Button(
                                "Edit Profile",
                                key=open_edit_prompt_window_key,
                                expand_x=True,
                            )
                        ],
                        [
                            sg.Button(
                                "Delete Profile", key=delete_prompt_key, expand_x=True
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
        )

        return win

    def reload_prompt_manager_window(
        prompt_manager_window: sg.Window,
        modal_window_manager: ModalWindowManager = None,
        window_tracker: WindowTracker = None,
    ) -> Optional[sg.Window]:
        """Reload the prompt manager window and track the new window.

        Args:
            prompt_manager_window (sg.Window): The prompt manager window to reload.
            modal_window_manager (ModalWindowManager, optional): The new prompt manager window
                will be tracked and made modal by a modal window manager if given. Defaults to None.
            window_tracker (WindowTracker, optional): The new prompt manager window
                will be tracked by a window tracker if given. Defaults to None.

        Returns:
            Optional[sg.Window]: The new prompt manager window or None.
        """

        if prompt_manager_window:
            prompt_manager_window.close()
            new_prompt_manager_window = popup_prompt_manager()
            if window_tracker:
                window_tracker.track_window(new_prompt_manager_window)
            if modal_window_manager:
                modal_window_manager.update()
                modal_window_manager.track_modal_window(prompt_manager_window)

            return new_prompt_manager_window
        else:
            return None

    # keep track of the prompt manager window
    prompt_manager_window = None

    def popup_add_edit_prompt_profile(
        title: str, submit_event: str, profile_name: str = "", profile_prompt: str = ""
    ) -> sg.Window:
        """Pop up either the add or edit prompt profile window.

        Args:
            title (str): The title for the popup window.
            submit_event (str): The event that occurs when new profile values are submitted.
            profile_name (str, optional): The editted profile's name which prefills the profile name field in the window.
                ONLY FOR PROFILE EDITS. Defaults to "".
            prompt (str, optional): The editted profile's prompt which prefills the profile prompt field in the window.
                ONLY FOR PROFILE EDITS. Defaults to "".

        Returns:
            sg.Window: The add/edit prompt profile window.
        """
        layout = [
            [
                [sg.Text("Profile Name")],
                [
                    sg.Input(
                        profile_name,
                        key=new_profile_name_key,
                        expand_x=True,
                        metadata=profile_name,
                    )
                ],
                [sg.Text("Prompt")],
                [
                    sg.Input(
                        profile_prompt,
                        key=new_profile_prompt_key,
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
            submit_event (str): The event that occurs when new profile values are submitted.

        Returns:
            sg.Window: The add prompt profile window.
        """
        return popup_add_edit_prompt_profile(title=title, submit_event=submit_event)

    def popup_edit_prompt_profile(
        title: str, submit_event: str, profile_name: str = "", profile_prompt: str = ""
    ) -> sg.Window:
        """Pop up either the edit prompt profile window.

        Args:
            title (str): The title for the popup window.
            submit_event (str): The event that occurs when new profile values are submitted.
            profile_name (str, optional): The editted profile's name which prefills the profile name field in the window.
                ONLY FOR PROFILE EDITS. Defaults to "".
            prompt (str, optional): The editted profile's prompt which prefills the profile prompt field in the window.
                ONLY FOR PROFILE EDITS. Defaults to "".

        Returns:
            sg.Window: The edit prompt profile window.
        """
        return popup_add_edit_prompt_profile(
            title=title,
            submit_event=submit_event,
            profile_name=profile_name,
            profile_prompt=profile_prompt,
        )

    # keep track of the add new prompt window
    add_new_prompt_window = None

    # timer for transcription task
    transcription_timer = CustomTimer()

    # tracks if transcription is in progress
    is_transcribing = False

    # holds paths for the users selected audio video files
    audio_video_file_paths = []

    # current transcription task being worked on
    num_tasks_done = 0

    # total number of transcription tasks
    num_tasks = 0

    # thread that runs transcriptions as processes
    transcribe_thread = None

    # stop flag for the thread
    stop_flag = threading.Event()

    modal_window_manager = ModalWindowManager()

    while True:
        # Display and interact with the Window
        window, event, values = sg.read_all_windows(timeout=1)

        if event in (sg.WIN_CLOSED, "Exit", "Close", "Cancel", "OK"):
            if window is main_window:
                # Tell the thread to end the ongoing transcription
                if transcribe_thread:
                    print("Window closed but transcription is in progress.")
                    stop_flag.set()
                break
            elif window is add_new_prompt_window:
                add_new_prompt_window = None
            elif window is prompt_manager_window:
                prompt_manager_window = None

            window.close()
        elif event == PRINT_ME:
            print(values[PRINT_ME], end="")
        # User selected an output directory
        elif event == output_dir_field_key:
            # Save the output directory to the settings file when the corresponding option is on
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
        elif (
            window
            and event in window.key_dict
            and isinstance(window[event], FancyCheckbox)
        ):
            # Save the checkbox state to the config file for save-on-click checkboxes
            save_on_click_checkboxes = (
                translate_to_english_checkbox_key,
                save_output_dir_checkbox_key,
            )

            if event in save_on_click_checkboxes:
                save_toggle_state(window[event])

            # Delete the saved output directory from the settings file when the option is off
            if event == save_output_dir_checkbox_key and not window[event].checked:
                if sg.user_settings_get_entry(out_dir_key):
                    sg.user_settings_delete_entry(out_dir_key)
        # Popup prompt manager window
        elif event == start_prompt_manager_key:
            prompt_manager_window = window_tracker.track_window(popup_prompt_manager())
            modal_window_manager.track_modal_window(prompt_manager_window)
        # Popup add new prompt profile window
        elif event == open_add_prompt_window_key:
            # Pop up a window to get a prompt name and prompt
            add_new_prompt_window = popup_add_prompt_profile(
                title="Add new prompt profile", submit_event=add_prompt_profile_key
            )
            modal_window_manager.track_modal_window(add_new_prompt_window)
        # User wants to edit a saved prompt profile
        elif event == open_edit_prompt_window_key:
            selected_table_row_indices = values[saved_prompts_table_key]

            # Ensure user has selected a row in the prompt profile table
            if selected_table_row_indices:
                # Look up the profile using the index of the first selected table row
                selected_profile = prompt_manager.saved_prompt_profiles_list[
                    selected_table_row_indices[0]
                ]
                selected_profile_name, selected_profile_prompt = selected_profile

                # Pop up a window to edit the prompt name and prompt
                edit_prompt_window = popup_edit_prompt_profile(
                    title="Edit prompt profile",
                    submit_event=edit_prompt_profile_key,
                    profile_name=selected_profile_name,
                    profile_prompt=selected_profile_prompt,
                )
                modal_window_manager.track_modal_window(edit_prompt_window)
            # User has not selected a row in the prompt profile table
            else:
                popup_window = popup_tracked(
                    f"Please select a profile in the table.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid selection",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # Handle adding or editing of a prompt profile
        elif event in (add_prompt_profile_key, edit_prompt_profile_key):
            # Get the name and prompt to be saved
            new_profile_name = values[new_profile_name_key]
            new_profile_prompt = values[new_profile_prompt_key]

            # Get the original profile name of the add/edit profile window before user changes.
            original_profile_name = window[new_profile_name_key].metadata

            if event == add_prompt_profile_key:
                (add_edit_success, error_msg,) = prompt_manager.add_prompt_profile(
                    profile_name=new_profile_name,
                    profile_prompt=new_profile_prompt,
                )
            elif event == edit_prompt_profile_key:
                (add_edit_success, error_msg,) = prompt_manager.edit_prompt_profile(
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
        elif event == delete_prompt_key:
            # Delete the saved prompt profile
            selected_table_row_indices = values[saved_prompts_table_key]

            # Ensure user has selected a row in the prompt profile table
            if selected_table_row_indices:
                prompt_profile_names = prompt_manager.saved_prompt_profile_names
                prompt_profile_name_to_delete = prompt_profile_names[
                    selected_table_row_indices[0]
                ]
                prompt_manager.delete_prompt_profile(prompt_profile_name_to_delete)

                prompt_manager_window = reload_prompt_manager_window(
                    prompt_manager_window=prompt_manager_window,
                    modal_window_manager=modal_window_manager,
                    window_tracker=window_tracker,
                )
            # User has not selected a row in the prompt profile table
            else:
                popup_window = popup_tracked(
                    f"Please select a profile in the table.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid selection",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # User modified the initial prompt.
        elif event == initial_prompt_input_key:
            # Select the unsaved prompt profile
            window[prompt_profile_dropdown_key].update(
                value=prompt_manager.unsaved_prompt_profile_name
            )
        # User has chosen a prompt profile
        elif event == prompt_profile_dropdown_key:
            # Update the initial prompt input with the prompt profile's prompt
            chosen_prompt_profile = values[prompt_profile_dropdown_key]

            if chosen_prompt_profile in prompt_manager.saved_prompt_profile_names:
                new_initial_prompt_input = prompt_manager.saved_prompt_profiles[
                    chosen_prompt_profile
                ]
            elif chosen_prompt_profile == prompt_manager.unsaved_prompt_profile_name:
                new_initial_prompt_input = ""
            else:
                raise NonExistentPromptProfileName(
                    f"{chosen_prompt_profile} is not a saved prompt profile name or the unsaved prompt profile"
                )

            window[initial_prompt_input_key].update(value=new_initial_prompt_input)

            # Save the user's selected prompt profile to the settings file
            sg.user_settings_set_entry(
                prompt_profile_dropdown_key, chosen_prompt_profile
            )
        # User selected a language specifier for the result files
        elif event == language_specifier_setting_key:
            # Update the language specifier option setting
            sg.user_settings_set_entry(
                language_specifier_setting_key, values[language_specifier_setting_key]
            )
        # User saved settings
        elif event == apply_global_scaling_key:

            def popup_tracked_scaling_invalid() -> None:
                """Pop up a tracked modal message window indicating an invalid scaling input."""
                popup_window = popup_tracked(
                    f"Please enter a number for the scaling factor between {MIN_SCALING} and {MAX_SCALING}.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Invalid scaling factor",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)

            # Ensure the scaling input is a decimal
            try:
                scaling_input = Decimal(values[scaling_input_setting_key])
            except decimal.InvalidOperation:
                popup_tracked_scaling_invalid()
                continue

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
                continue

            # Close all windows and remove them from tracking
            for win in window_tracker.windows:
                win.close()
            del window_tracker.windows

            # Remake the main window and go back to the settings tab
            window = main_window = make_tracked_main_window_with_synced_profiles(
                window_tracker=window_tracker,
                prompt_manager=prompt_manager,
                prompt_profile_dropdown_key=prompt_profile_dropdown_key,
            )
            window[settings_tab_key].select()
        # User pressed toggle button for the table
        elif event == model_info_toggle_key:
            # window[model_info_toggle_key].update(image_data=toggle_image)
            model_info_toggled_on = window[model_info_toggle_key].is_toggled_on

            # Show/hide the table
            window[model_info_table_key].update(visible=model_info_toggled_on)
        # User wants to start transcription
        elif event == start_key:
            # Get user provided paths for the video file and output directory
            audio_video_file_paths_str = str(values[in_file_key]).strip()
            output_dir_path = str(values[out_dir_key]).strip()

            # Require audio/video file(s) and output folder
            if audio_video_file_paths_str and output_dir_path:
                # Get user selected language and model
                language_selected = values[language_key]
                if language_selected not in TO_LANGUAGE_CODE:
                    language_selected = None

                model_selected = values[model_key]

                # Get the user's choice of whether to translate the results into english
                translate_to_english = window[translate_to_english_checkbox_key].checked

                # Get the user's choice of whether to use a language code as the language specifier in output files
                language_specifier_selection = values[language_specifier_setting_key]
                use_language_code = (
                    True
                    if language_specifier_selection == LANGUAGE_SPECIFIER_AS_CODE
                    else False
                )

                #  Get the user's initial prompt for all transcriptions in this task
                initial_prompt = values[initial_prompt_input_key]

                # Ensure timer is not running
                with suppress(TimerError):
                    transcription_timer.stop()

                # Clear the console output element
                window[multiline_key].update("")
                window.refresh()

                # Convert string with file paths into a list
                audio_video_file_paths = list(
                    str_to_file_paths(audio_video_file_paths_str)
                )

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
                        "use_language_code": use_language_code,
                        "initial_prompt": initial_prompt,
                    },
                    daemon=True,
                )
                transcribe_thread.start()
                is_transcribing = True
            else:
                popup_window = popup_tracked(
                    f"Please select audio/video file(s) and an output folder.",
                    popup_fn=popup,
                    window_tracker=window_tracker,
                    title="Missing selections",
                    non_blocking=True,
                )
                modal_window_manager.track_modal_window(popup_window)
        # 1 transcription completed
        elif event == TRANSCRIBE_PROGRESS:
            num_tasks_done += 1
        # All transcriptions completed
        elif event == TRANSCRIBE_SUCCESS:
            transcription_time = transcription_timer.stop()

            # Show output file paths in a popup
            output_paths = values[TRANSCRIBE_SUCCESS]
            output_paths_formatted = "\n".join(output_paths)
            popup_window = popup_tracked(
                f"Status: COMPLETE\n\nTime taken: {transcription_time:.4f} secs\n\nOutput locations: \n\n{output_paths_formatted}",
                popup_fn=popup_scrolled,
                window_tracker=window_tracker,
                title="Complete",
                size=(40, 20),
                disabled=True,
                non_blocking=True,
            )
            modal_window_manager.track_modal_window(popup_window)
        # Error while transcribing
        elif event == TRANSCRIBE_ERROR:
            transcription_timer.stop(log_time=False)
            sg.one_line_progress_meter_cancel(key=progress_key)

            error_msg = values[TRANSCRIBE_ERROR]
            popup_window = popup_tracked(
                f"Status: FAILED\n\n{error_msg}\n\nPlease see the console output for details.",
                popup_fn=popup,
                window_tracker=window_tracker,
                title="ERROR",
                non_blocking=True,
            )
            modal_window_manager.track_modal_window(popup_window)
        # User cancelled transcription
        elif event == TRANSCRIBE_STOPPED:
            transcription_timer.stop(log_time=False)
            stop_flag.clear()
            print("\nTranscription cancelled by user.")

        # Clear selection highlighting if a dropdown option was selected
        if window and event in window.key_dict and isinstance(window[event], sg.Combo):
            window[event].widget.selection_clear()

        # Transcriptions complete. Enable the main window for the user.
        if event in TRANSCRIBE_DONE_EVENTS:
            transcribe_thread = None
            is_transcribing = False

        # Transcriptions in progress
        if is_transcribing:
            # Update the progress meter unless the user has clicked the cancel button already
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

                # Track the meter window in case it was remade to ensure it's modal
                if meter_updated:
                    # Track the meter window as a modal window if it's still active
                    if progress_key in sg.QuickMeter.active_meters:
                        meter_window = sg.QuickMeter.active_meters[progress_key].window
                        modal_window_manager.track_modal_window(meter_window)
                # User clicked the Cancel button
                else:
                    # Close the progress window
                    sg.one_line_progress_meter_cancel(key=progress_key)
                    # Flag the thread to stop
                    stop_flag.set()

        # Set as modal the most recent non-closed tracked modal window
        modal_window_manager.update()

    # Finish up by removing from the screen
    main_window.close()


class Window(sg.Window):
    """Represents a single Window."""

    def __init__(
        self,
        title,
        layout=None,
        default_element_size=None,
        default_button_element_size=(None, None),
        auto_size_text=None,
        auto_size_buttons=None,
        location=(None, None),
        relative_location=(None, None),
        size=(None, None),
        element_padding=None,
        margins=(None, None),
        button_color=None,
        font=None,
        progress_bar_color=(None, None),
        background_color=None,
        border_depth=None,
        auto_close=False,
        auto_close_duration=sg.DEFAULT_AUTOCLOSE_TIME,
        icon=None,
        force_toplevel=False,
        alpha_channel=None,
        return_keyboard_events=False,
        use_default_focus=True,
        text_justification=None,
        no_titlebar=False,
        grab_anywhere=False,
        grab_anywhere_using_control=True,
        keep_on_top=None,
        resizable=False,
        disable_close=False,
        disable_minimize=False,
        right_click_menu=None,
        transparent_color=None,
        debugger_enabled=True,
        right_click_menu_background_color=None,
        right_click_menu_text_color=None,
        right_click_menu_disabled_text_color=None,
        right_click_menu_selected_colors=(None, None),
        right_click_menu_font=None,
        right_click_menu_tearoff=False,
        finalize=False,
        element_justification="left",
        ttk_theme=None,
        use_ttk_buttons=None,
        modal=False,
        enable_close_attempted_event=False,
        titlebar_background_color=None,
        titlebar_text_color=None,
        titlebar_font=None,
        titlebar_icon=None,
        use_custom_titlebar=None,
        scaling=None,
        sbar_trough_color=None,
        sbar_background_color=None,
        sbar_arrow_color=None,
        sbar_width=None,
        sbar_arrow_width=None,
        sbar_frame_color=None,
        sbar_relief=None,
        metadata=None,
    ):
        super().__init__(
            title=title,
            layout=layout,
            default_element_size=default_element_size,
            default_button_element_size=default_button_element_size,
            auto_size_text=auto_size_text,
            auto_size_buttons=auto_size_buttons,
            location=location,
            relative_location=relative_location,
            size=size,
            element_padding=element_padding,
            margins=margins,
            button_color=button_color,
            font=font,
            progress_bar_color=progress_bar_color,
            background_color=background_color,
            border_depth=border_depth,
            auto_close=auto_close,
            auto_close_duration=auto_close_duration,
            icon=icon,
            force_toplevel=force_toplevel,
            alpha_channel=alpha_channel,
            return_keyboard_events=return_keyboard_events,
            use_default_focus=use_default_focus,
            text_justification=text_justification,
            no_titlebar=no_titlebar,
            grab_anywhere=grab_anywhere,
            grab_anywhere_using_control=grab_anywhere_using_control,
            keep_on_top=keep_on_top,
            resizable=resizable,
            disable_close=disable_close,
            disable_minimize=disable_minimize,
            right_click_menu=right_click_menu,
            transparent_color=transparent_color,
            debugger_enabled=debugger_enabled,
            right_click_menu_background_color=right_click_menu_background_color,
            right_click_menu_text_color=right_click_menu_text_color,
            right_click_menu_disabled_text_color=right_click_menu_disabled_text_color,
            right_click_menu_selected_colors=right_click_menu_selected_colors,
            right_click_menu_font=right_click_menu_font,
            right_click_menu_tearoff=right_click_menu_tearoff,
            finalize=finalize,
            element_justification=element_justification,
            ttk_theme=ttk_theme,
            use_ttk_buttons=use_ttk_buttons,
            modal=modal,
            enable_close_attempted_event=enable_close_attempted_event,
            titlebar_background_color=titlebar_background_color,
            titlebar_text_color=titlebar_text_color,
            titlebar_font=titlebar_font,
            titlebar_icon=titlebar_icon,
            use_custom_titlebar=use_custom_titlebar,
            scaling=scaling,
            sbar_trough_color=sbar_trough_color,
            sbar_background_color=sbar_background_color,
            sbar_arrow_color=sbar_arrow_color,
            sbar_width=sbar_width,
            sbar_arrow_width=sbar_arrow_width,
            sbar_frame_color=sbar_frame_color,
            sbar_relief=sbar_relief,
            metadata=metadata,
        )

        self._setup()

    def _setup(self):
        self.refresh()

        # Run the setup for each element if it exists
        for element in self.element_list():
            with suppress(AttributeError):
                element._setup()

        self.refresh()


def resize_window_relative_to_screen(
    window: sg.Window,
    width_factor: Union[float, int],
    height_factor: Union[float, int],
) -> None:
    """Resize the window by specifying the width and height relative to the screen size.

    Args:
        window (sg.Window): The window to resize.
        width_factor (Union[float, int]): The proportion of the screen's width to make the window.
            E.g., 0.2 is 20% of the screen's width.
        height_factor (Union[float, int]): The proportion of the screen's height to make the window.
            E.g., 0.2 is 20% of the screen's height.
    """

    screen_width, screen_height = sg.Window.get_screen_size()

    window_width = int(screen_width * width_factor)
    window_height = int(screen_height * height_factor)

    window.size = (window_width, window_height)

    window.refresh()

    window.move_to_center()


def set_same_width(text_elements: Sequence[sg.Text]) -> None:
    """Set the width of the text elements to the longest text value among the elements.

    Only works properly with monospaced fonts. Non-monospaced fonts cause the textbox to not
    properly fit the text.

    Args:
        text_elements (Sequence[sg.Text]): A Sequence with the text elements to set to the same width.
    """
    longest_width = max([len(element.get()) for element in text_elements])

    for element in text_elements:
        element.set_size((longest_width, None))


def find_closest_element(
    index: int,
    element_list: List[sg.Element],
    element_class: Type[sg.Element] = sg.Element,
) -> Optional[sg.Text]:
    """Find the closest element to a target element based on the target element's position in a list of elements.

    Args:
        index (int): The index in the list for the target element which the expanding search starts from.
        element_list (List[sg.Element]): A list of elements.
        element_class (Type[sg.Element]): The class requirement for the closest element. Defaults to sg.Element.

    Raises:
        IndexError: Invalid index for the given list.

    Returns:
        Optional[sg.Text]: The closest element if found. Else, None.
    """

    # Ensure a valid index by accessing it
    element_list[index]

    num_elements = len(element_list)

    # Convert a negative index to a positive index
    if index < 0:
        index %= num_elements

    # iterator for the elements before the target element
    prev_index = index - 1 if index > 0 else 0
    it_before = islice(reversed(element_list), num_elements - 1 - prev_index, None)

    # iterator for the elements after the target element
    next_index = index + 1 if index < num_elements - 1 else index
    it_after = islice(element_list, next_index, None)

    @dataclass(frozen=True)
    class TestResult:
        """The result from testing an element in a list.

        Attributes:
            element (Optional[sg.Element]): The element if it passes the test. Else, None.
            more_values_to_test (bool): True if there are more values to test in the list.
        """

        element: Optional[sg.Element]
        more_values_to_test: bool

        def __iter__(self):
            return iter((self.element, self.more_values_to_test))

    def is_next_element_of_class(
        it: Iterator[sg.Element], element_class: Type[sg.Element]
    ) -> TestResult:
        """Test if the next element returned by the iterator is of the specified class.

        Args:
            it (Iterator): The iterator for the elements to test.
            element_class (Type[sg.Element]): The class to test the next element returned by
                the iterator for. Defaults to sg.Element.

        Returns:
            TestResult: Contains the element if it's of the specified class or None, and a
                bool that's True if the iterator can keep iterating.
        """

        try:
            next_element = next(it)
        except StopIteration:
            return TestResult(element=None, more_values_to_test=False)
        else:
            if isinstance(next_element, element_class):
                return TestResult(element=next_element, more_values_to_test=True)
            return TestResult(element=None, more_values_to_test=True)

    search_expanding_left = True
    search_expanding_right = True

    while search_expanding_left or search_expanding_right:
        if search_expanding_left:
            text_element_before, search_expanding_left = is_next_element_of_class(
                it=it_before, element_class=element_class
            )
            if text_element_before:
                return text_element_before

        if search_expanding_right:
            text_element_after, search_expanding_right = is_next_element_of_class(
                it=it_after, element_class=element_class
            )
            if text_element_after:
                return text_element_after

    # No Text element found in window
    return None


class InvalidElementSize(Exception):
    """The width and/or height of the element is not greater than 0."""


class ClosestTextElementInWindowNotFound(Warning):
    """Unable to find closest Text element in the window."""


def setup_line_height_images(
    image_file_or_bytes: Union[str, bytes, None],
    window: sg.Window,
    image_subkey: str = "",
    image_element: sg.Image = None,
    size_match_element: sg.Element = None,
    closest_element_type: Type[sg.Element] = sg.Element,
) -> None:
    """Assign the same image to all Image elements in the window with a height that matches
    the target element if given or the closest Text element.

    Usage:
        Put an Image element next to a Text element in a layout. (Optionally) Assign a key that
        contains a unique string to the Image (Ex. key='-CHECKBOX-10' where '-CHECKBOX-' will be
        passed to this f(x) when you intend to only update Image's whose key contains '-CHECKBOX-').
        Call this f(x).

    Args:
        image_file_or_bytes (Union[str, bytes]): Either a string filename for an image file or a bytes
            base64 image object.
        window (sg.Window): The window to update images in.
        image_subkey (str, optional): Only update Image elements whose key contains this string.
            Defaults to "".
        image_element (sg.Image, optional): The Image element to update. image_subkey parameter will be ignored
            if this parameter is given. Defaults to None.
        size_match_element (sg.Element, optional): The element to size match. If not given, the closest element will be used.
            Defaults to None.
        closest_element_type (Type[sg.Element]): The type of the closest Element to size match. Defaults to sg.Element.

    Raises:
        InvalidElementSize: The width and/or height of a closest Text element is not greater than 0.
        ClosestTextElementInWindowNotFound: Unable to find closest Text element for an Image element in this window.
    """

    element_list = window.element_list()

    for index, element in enumerate(element_list):
        # Image element given and found in list.
        given_image_found = image_element and image_element is element

        # Image element not given. Image element found with a key that contains the required subkey.
        valid_image_key = (
            image_element is None
            and isinstance(element, sg.Image)
            and image_subkey in str(element.key)
        )

        if given_image_found or valid_image_key:
            # Size match with the given element
            if size_match_element:
                element_to_size_match = size_match_element
            # Size match with the closest element
            else:
                element_to_size_match = find_closest_element(
                    index=index,
                    element_list=element_list,
                    element_class=closest_element_type,
                )

            # Update the Image element with an image whose size matches the closest Text element.
            if element_to_size_match:
                update_size_matched_image(
                    image_file_or_bytes=image_file_or_bytes,
                    image_element=element,
                    element_to_size_match=element_to_size_match,
                )
            else:
                raise ClosestTextElementInWindowNotFound(
                    f"Unable to find closest Text element to Image element with key={element.key} in the  main window."
                )

            # Stop after updating only the Image with the given key
            if image_element:
                return


def update_size_matched_image(
    image_file_or_bytes: Union[str, bytes, None],
    image_element: sg.Image,
    element_to_size_match: sg.Element,
) -> None:
    """Update the Image element with an image that size matches a target element.

    Args:
        image_file_or_bytes (Union[str, bytes, None]): Either a string filename for an image file or a bytes
            base64 image object.
        image_element (sg.Image): The Image element whose image is to be updated.
        element_to_size_match (sg.Element): The element that the image needs to size match.

    Raises:
        InvalidElementSize: The closest element has an unusable size.
    """
    if image_file_or_bytes is None:
        image_element.update(source=None)
        return

    width, height = element_to_size_match.get_size()
    if width > 0 and height > 0:
        image_element.update(
            source=convert_to_bytes(
                file_or_bytes=image_file_or_bytes,
                resize=(width, height),
                fill=False,
            )
        )
    else:
        raise InvalidElementSize(
            f"Unusable size for closest element (key={element_to_size_match.key}). width={width}, height={height}."
        )


import base64
import io

import PIL.Image


def convert_to_bytes(file_or_bytes, resize=None, fill=False):
    """
    Will convert into bytes and optionally resize an image that is a file or a base64 bytes object.
    Turns into  PNG format in the process so that can be displayed by tkinter
    :param file_or_bytes: either a string filename or a bytes base64 image object
    :type file_or_bytes:  (Union[str, bytes])
    :param resize:  optional new size
    :type resize: (Tuple[int, int] or None)
    :param fill: If True then the image is filled/padded so that the image is not distorted
    :type fill: (bool)
    :return: (bytes) a byte-string object
    :rtype: (bytes)
    """

    def make_square(im, min_size=256, fill_color=(0, 0, 0, 0)):
        x, y = im.size
        size = max(min_size, x, y)
        new_im = PIL.Image.new("RGBA", (size, size), fill_color)
        new_im.paste(im, (int((size - x) / 2), int((size - y) / 2)))
        return new_im

    if isinstance(file_or_bytes, str):
        img = PIL.Image.open(file_or_bytes)
    else:
        try:
            img = PIL.Image.open(io.BytesIO(base64.b64decode(file_or_bytes)))
        except Exception as e:
            dataBytesIO = io.BytesIO(file_or_bytes)
            img = PIL.Image.open(dataBytesIO)

    cur_width, cur_height = img.size
    if resize:
        new_width, new_height = resize
        scale = min(new_height / cur_height, new_width / cur_width)
        img = img.resize(
            (int(cur_width * scale), int(cur_height * scale)),
            PIL.Image.Resampling.LANCZOS,
        )
    if fill:
        if resize is not None:
            img = make_square(img, resize[0])
    with io.BytesIO() as bio:
        img.save(bio, format="PNG")
        del img
        return bio.getvalue()


class NonExistentPromptProfileName(Exception):
    """A non-existent prompt profile name was used."""


class ModalWindowManager:
    """A manager for tracking modal windows in order to remodal a previous window
    when a more recent one is closed.
    """

    def __init__(self) -> None:
        self._modal_window_stack: List[sg.Window] = []

    def track_modal_window(self, window: sg.Window) -> Tuple[sg.Window, bool]:
        """Add a modal window as the most recent tracked modal window.

        The given window will be ignored if it's a closed window.

        Args:
            window (sg.Window): A modal window. If a non-modal window is added,
                it will be changed into a modal window.

        Returns:
            Tuple[sg.Window, bool]: A tuple with the window and True if
                tracking succeeded, False otherwise.
        """

        # Ignore the window if it's already the most recent tracked modal window
        if self._modal_window_stack and window is self._modal_window_stack[-1]:
            return (window, True)

        if not window.is_closed():
            window.make_modal()

        # Add the window as the most recent tracked modal window.
        self._modal_window_stack.append(window)
        return (window, True)

    def update(self) -> None:
        """Set as modal the most recent non-closed tracked modal window."""

        stack_changed = False

        # Clear closed modal windows from the top of the modal window tracking stack
        while self._modal_window_stack and self._modal_window_stack[-1].was_closed():
            self._modal_window_stack.pop()
            stack_changed = True

        # Restore as modal the most recent non-closed tracked modal window
        if stack_changed and self._modal_window_stack:
            self._modal_window_stack[-1].make_modal()


class WindowTracker:
    """A tracker for possibly open windows."""

    def __init__(self) -> None:
        self._tracked_windows: Set[sg.Window] = set()

    def track_window(self, window: sg.Window) -> sg.Window:
        """Track the window.

        Args:
            win (sg.Window): The window to be tracked.

        Returns:
            sg.Window: The tracked window.
        """
        self._tracked_windows.add(window)
        return window

    @property
    def windows(self) -> Set[sg.Window]:
        """The currently tracked windows."""
        return self._tracked_windows

    @windows.deleter
    def windows(self) -> None:
        """Stop tracking the currently tracked windows."""
        self._tracked_windows.clear()


class PromptManager:
    """A manager for prompt profiles."""

    _unsaved_prompt_profile_name = "(None)"

    def __init__(self, saved_prompts_settings_key: str) -> None:
        """
        Args:
            saved_prompts_settings_key (str): Key for the saved prompts in the settings file.
        """
        self._saved_prompts_settings_key = saved_prompts_settings_key
        self.saved_prompt_profiles = sg.user_settings_get_entry(
            self._saved_prompts_settings_key, {}
        )
        self._dropdown_window = None
        self._dropdown_key: Optional[str] = None

    @property
    def unsaved_prompt_profile_name(self) -> str:
        """Name of the Prompt profile for when the user is not using a saved prompt profile."""
        return self._unsaved_prompt_profile_name

    @property
    def saved_prompt_profiles(self) -> Dict[str, str]:
        """A dict with the saved prompt profiles names and their prompt values."""
        self._saved_prompt_profiles: Dict[str, str] = sg.user_settings_get_entry(
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
        """The unsaved prompt profile name and the sorted ascending names of the saved prompt profiles."""
        return [
            self.unsaved_prompt_profile_name,
            *sorted(self.saved_prompt_profiles.keys()),
        ]

    @property
    def saved_prompt_profiles_list(self) -> List[Tuple[str, str]]:
        """The saved prompt profiles as a list of tuples sorted ascending."""
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
            Tuple[bool, str]: Tuple with the success state and an error message.
                The success state will be True if the prompt profile was successfully added.
                False, otherwise. The error message will be an empty string if no error occurred.
        """
        error_msg = ""

        # Invalid prompt name. Prompt name is empty or only has whitespaces.
        if not profile_name.strip():
            error_msg = (
                f"Invalid prompt name: name can't be empty or whitespace only."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        # Invalid prompt name. Prompt name already in use.
        if profile_name in self.prompt_profile_names:
            error_msg = (
                f"Invalid prompt name: name already in use."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        self._save_profile(profile_name=profile_name, profile_prompt=profile_prompt)

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
            original_profile_name (str): The original name of the prompt profile being edited.

        Returns:
            Tuple[bool, str]: Tuple with the success state and an error message.
                The success state will be True if the prompt profile was successfully editted.
                False, otherwise. The error message will be an empty string if no error occurred.
        """
        error_msg = ""

        # Invalid prompt name. Prompt name is empty or only has whitespaces.
        if not profile_name.strip():
            error_msg = (
                f"Invalid prompt name: name can't be empty or whitespace only."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        profile_name_changed = profile_name != original_profile_name

        # Invalid prompt name. Profile name is already in use and user isn't editing the selected profile's prompt.
        if profile_name in self.prompt_profile_names and profile_name_changed:
            error_msg = (
                f"Invalid prompt name: name already in use."
                "\n\nPlease enter a new prompt name."
            )
            return False, error_msg

        self._save_profile(
            profile_name=profile_name,
            profile_prompt=profile_prompt,
            original_profile_name=original_profile_name,
        )

        return True, error_msg

    def _save_profile(
        self, profile_name: str, profile_prompt: str, original_profile_name: str = None
    ) -> None:
        """Save the prompt profile while overwriting the original profile if it is given.

        Overwrites an existing prompt profile if it already exists.

        Args:
            prompt_name (str): The name for the prompt profile.
            prompt (str): The prompt for the prompt profile.
            original_profile_name (str, None): The original name of the prompt profile being edited
                if applicable. Defaults to None.
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

            # Edited the currently selected profile in the dropdown. Select the new profile.
            if (
                original_profile_name is not None
                and original_profile_name == selected_dropdown_profile_name
            ):
                self._update_prompt_profile_dropdown(new_selected_profile=profile_name)
            # Added a profile or did not edit the currently selected profile in the dropdown
            else:
                self._update_prompt_profile_dropdown()

    def delete_prompt_profile(self, profile_name: str) -> None:
        """Delete a prompt profile by name.

        Args:
            prompt_name (str): The name of the prompt profile to be deleted.
        """
        del self.saved_prompt_profiles[profile_name]

        self._save_profiles_to_settings()

        # Get the currently selected profile in the dropdown
        if self._dropdown:
            selected_prompt_profile_name = self._dropdown.get()

            # Update the profile dropdown and select the unsaved prompt profile in the
            # dropdown since the current profile selection was deleted
            if profile_name == selected_prompt_profile_name:
                self._update_prompt_profile_dropdown(
                    new_selected_profile=self.unsaved_prompt_profile_name
                )
            # Update the profile dropdown and keep the current profile selection
            else:
                self._update_prompt_profile_dropdown()

    def _save_profiles_to_settings(self) -> None:
        """Update the settings file with the current prompt profiles."""
        sg.user_settings_set_entry(
            self._saved_prompts_settings_key, self.saved_prompt_profiles
        )

    @property
    def _dropdown(self) -> Optional[sg.Combo]:
        """The prompt profile dropdown element that will be updated when the prompt
        profiles change.

        Returns:
            Optional[sg.Combo]: Returns the dropdown element if known. Else, returns None.
        """
        if self._dropdown_window and self._dropdown_key is not None:
            return self._dropdown_window[self._dropdown_key]
        else:
            return None

    def set_prompt_profile_dropdown(self, window: sg.Window, key: str) -> None:
        """Set the prompt profile dropdown element that will be updated when the prompt
        profiles change.

        Args:
            window (sg.Window): The window containing the dropdown element.
            key (str): The key for the dropdown element.
        """
        self._dropdown_window = window
        self._dropdown_key = key

    def _update_prompt_profile_dropdown(
        self, new_selected_profile: Union[str, ellipsis] = ...
    ) -> None:
        """Update the tracked prompt profile dropdown element if it exists.

        Args:
            new_selected_profile (str, ellipsis): The dropdown selection will be changed
                to this profile if given. Defaults to ellipsis.
        """
        if self._dropdown:
            selected_profile = new_selected_profile

            # Keep the old selection for the dropdown if a new selection is not given
            if selected_profile is ...:
                selected_profile = self._dropdown.get()

            # The width of the dropbox that fits all options
            new_dropdown_width = len(max(self.prompt_profile_names, key=len))

            # Update the prompt profile list and the selected profile for the dropdown
            self._dropdown.update(
                value=selected_profile,
                values=self.prompt_profile_names,
                size=(new_dropdown_width, None),
            )

            # Send an event changing the dropdown selection if a new selected profile is given.
            if (
                self._dropdown_window
                and self._dropdown_key is not None
                and new_selected_profile is not ...
            ):
                self._dropdown_window.write_event_value(
                    self._dropdown_key, new_selected_profile
                )


@dataclass(frozen=True)
class ElementWindow:
    """An element and it's window.

    Attributes:
        element (Optional[sg.Element]): The element.
        window (Optional[sg.Window]): The window that the element is in.
    """

    element: Optional[sg.Element] = None
    window: Optional[sg.Window] = None

    def __bool__(self) -> bool:
        if self.element and self.window:
            return True
        return False


def widget_to_element_with_window(widget: tk.Widget) -> Optional[ElementWindow]:
    """Return the element that matches a supplied tkinter widget and its window.
    If no matching element is found, then None is returned.

    Args:
        widget (tk.Widget): A tkinter widget.

    Returns:
        Optional[ElementWindow]: The element that matches a supplied tkinter
        widget and its window. Else, None.
    """

    for window in sg.Window._active_windows:
        element = window.widget_to_element(widget)
        if element:
            return ElementWindow(element, window)
    return None


def size_matched_image_element(
    size_match_element: sg.Element, image_element: ImageBase
) -> List[sg.Element]:
    """Return the element and the image element that's set to size match it.

    Args:
        size_match_element (sg.Element): The element that the image element will size match.
        image_element (ImageBase): The image element that will be set to size match the given element.

    Returns:
        List[sg.Element]: A list with the element and the image element set to size match it.
    """
    image_element.size_match = True
    image_element.size_match_element = size_match_element
    return [size_match_element, image_element]


class Multiline(sg.Multiline):
    """Multiline Element with extra capabilities - Display and/or read multiple lines of text.
    This is both an input and output element.
    """

    def write(self, txt: str) -> None:
        """
        Called by Python (not tkinter?) when stdout or stderr wants to write

        :param txt: text of output
        :type txt:  (str)
        """
        _txt = self._format_text(txt)
        try:
            self.update(_txt, append=True)
            if self.echo_stdout_stderr:
                self.previous_stdout.write(_txt)
        except:
            pass

    def _format_text(self, text: str) -> str:
        """Return formatted text meant for console output.

        Replaces \r with \n.
        Replaces progress characters between '|'s in progress bars with proper '█'s.

        Args:
            text (str): The text to format.
        """
        # remove the auto appended '\n' by every Multiline.get() call when rstrip is False
        _text = text if self.rstrip else text[:-1]

        # Replace all \r with \n
        processed_text = re.sub(r"\r", "\n", _text)

        def replace_with_progress_bars(m: re.Match) -> str:
            # Replace all characters in the match with a block character.
            return "█" * len(m.group())

        processed_text = re.sub(
            r"(?<=\|)\S+(?=\s*\|)", replace_with_progress_bars, processed_text
        )

        return processed_text


class ImageBase(sg.Image):
    """Image element with extra capabilities - show an image in the window. Should be a GIF or a PNG only."""

    def __init__(
        self,
        source=None,
        filename=None,
        data=None,
        background_color=None,
        size=(None, None),
        s=(None, None),
        pad=None,
        p=None,
        key=None,
        k=None,
        tooltip=None,
        subsample=None,
        right_click_menu=None,
        expand_x=False,
        expand_y=False,
        visible=True,
        enable_events=False,
        metadata=None,
        size_match=False,
        size_match_element=None,
        size_match_element_type=sg.Element,
    ) -> None:
        """
        :param source:                  A filename or a base64 bytes. Will automatically detect the type and fill in filename or data for you.
        :type source:                   str | bytes | None
        :param filename:                image filename if there is a button image. GIFs and PNGs only.
        :type filename:                 str | None
        :param data:                    Raw or Base64 representation of the image to put on button. Choose either filename or data
        :type data:                     bytes | str | None
        :param background_color:        color of background
        :type background_color:
        :param size:                    (width, height) size of image in pixels
        :type size:                     (int, int)
        :param s:                       Same as size parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, size will be used
        :type s:                        (int, int)  | (None, None) | int
        :param pad:                     Amount of padding to put around element in pixels (left/right, top/bottom) or ((left, right), (top, bottom)) or an int. If an int, then it's converted into a tuple (int, int)
        :type pad:                      (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param p:                       Same as pad parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, pad will be used
        :type p:                        (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param key:                     Used with window.find_element and with return values to uniquely identify this element to uniquely identify this element
        :type key:                      str | int | tuple | object
        :param k:                       Same as the Key. You can use either k or key. Which ever is set will be used.
        :type k:                        str | int | tuple | object
        :param tooltip:                 text, that will appear when mouse hovers over the element
        :type tooltip:                  (str)
        :param subsample:               amount to reduce the size of the image. Divides the size by this number. 2=1/2, 3=1/3, 4=1/4, etc
        :type subsample:                (int)
        :param right_click_menu:        A list of lists of Menu items to show when this element is right clicked. See user docs for exact format.
        :type right_click_menu:         List[List[ List[str] | str ]]
        :param expand_x:                If True the element will automatically expand in the X direction to fill available space
        :type expand_x:                 (bool)
        :param expand_y:                If True the element will automatically expand in the Y direction to fill available space
        :type expand_y:                 (bool)
        :param visible:                 set visibility state of the element
        :type visible:                  (bool)
        :param enable_events:           Turns on the element specific events. For an Image element, the event is "image clicked"
        :type enable_events:            (bool)
        :param metadata:                User metadata that can be set to ANYTHING
        :type metadata:                 (Any)
        :param size_match:              If True, the image will be sized matched to the size_match_element if given or the closest Element with the size_match_element_type.
        :type size_match:               (bool)
        :param size_match_element:      The element to size match the image to.
        :type size_match_element:       (sg.Element)
        :param size_match_element_type: The type of the closest Element to size match will be this type.
        :type size_match_element_type:  (Type[sg.Element])
        """

        self.size_match = size_match
        self.size_match_element = size_match_element
        self.size_match_element_type = size_match_element_type

        super().__init__(
            source=source,
            filename=filename,
            data=data,
            background_color=background_color,
            size=size,
            s=s,
            pad=pad,
            p=p,
            key=key,
            k=k,
            tooltip=tooltip,
            subsample=subsample,
            right_click_menu=right_click_menu,
            expand_x=expand_x,
            expand_y=expand_y,
            visible=visible,
            enable_events=enable_events,
            metadata=metadata,
        )

        self._post_init()

    def _post_init(self):
        ...

    def _setup(self) -> None:
        """Set up internal tkinter event binds and update the image. Only call this after the
        widget is created via calling window.refresh() or window.read() on the window with
        this element.
        """

        self._setup_binds()

        # Update the image so it's size matched after initial creation
        self._update_image()

    def _setup_binds(self) -> None:
        # Set up tkinter bind events
        ...

    def _unbind_all(self) -> None:
        # Remove all event bindings for this element's widget
        for event in self.widget.bind():
            self.unbind(event)

    def _update_image(self, source: Union[str, bytes, None, ellipsis] = ...) -> None:
        """Update the image with the given source. If size matching is on, a size-matched version of
        the source will be used.

        Args:
            source (Union[str, bytes, None], optional): A filename or a base64 bytes. Defaults to ....
        """

        window = self.ParentForm

        new_source = self._determine_new_source(source)

        if window and self.size_match:
            setup_line_height_images(
                image_file_or_bytes=new_source,
                window=window,
                image_element=self,
                size_match_element=self.size_match_element,
                closest_element_type=self.size_match_element_type,
            )
        else:
            self.update(source=new_source)

    def _determine_new_source(
        self, source: Union[str, bytes, None, ellipsis]
    ) -> Union[str, bytes, None]:
        return source if source is not ... else self.Source


class Image(ImageBase):
    """Image element with size-matching functionality - show an image in the window. Should be a GIF or a PNG only."""

    _source_default: Union[str, bytes, None] = None

    def __init__(
        self,
        source=...,
        filename=...,
        data=...,
        background_color=None,
        size=(None, None),
        s=(None, None),
        pad=None,
        p=None,
        key=None,
        k=None,
        tooltip=None,
        subsample=None,
        right_click_menu=None,
        expand_x=False,
        expand_y=False,
        visible=True,
        enable_events=False,
        metadata=None,
        size_match=False,
        size_match_element=None,
        size_match_element_type=sg.Element,
    ) -> None:
        """
        :param source:                  A filename or a base64 bytes. Will automatically detect the type and fill in filename or data for you.
        :type source:                   str | bytes | None
        :param filename:                image filename if there is a button image. GIFs and PNGs only.
        :type filename:                 str | None
        :param data:                    Raw or Base64 representation of the image to put on button. Choose either filename or data
        :type data:                     bytes | str | None
        :param background_color:        color of background
        :type background_color:
        :param size:                    (width, height) size of image in pixels
        :type size:                     (int, int)
        :param s:                       Same as size parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, size will be used
        :type s:                        (int, int)  | (None, None) | int
        :param pad:                     Amount of padding to put around element in pixels (left/right, top/bottom) or ((left, right), (top, bottom)) or an int. If an int, then it's converted into a tuple (int, int)
        :type pad:                      (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param p:                       Same as pad parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, pad will be used
        :type p:                        (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param key:                     Used with window.find_element and with return values to uniquely identify this element to uniquely identify this element
        :type key:                      str | int | tuple | object
        :param k:                       Same as the Key. You can use either k or key. Which ever is set will be used.
        :type k:                        str | int | tuple | object
        :param tooltip:                 text, that will appear when mouse hovers over the element
        :type tooltip:                  (str)
        :param subsample:               amount to reduce the size of the image. Divides the size by this number. 2=1/2, 3=1/3, 4=1/4, etc
        :type subsample:                (int)
        :param right_click_menu:        A list of lists of Menu items to show when this element is right clicked. See user docs for exact format.
        :type right_click_menu:         List[List[ List[str] | str ]]
        :param expand_x:                If True the element will automatically expand in the X direction to fill available space
        :type expand_x:                 (bool)
        :param expand_y:                If True the element will automatically expand in the Y direction to fill available space
        :type expand_y:                 (bool)
        :param visible:                 set visibility state of the element
        :type visible:                  (bool)
        :param enable_events:           Turns on the element specific events. For an Image element, the event is "image clicked"
        :type enable_events:            (bool)
        :param metadata:                User metadata that can be set to ANYTHING
        :type metadata:                 (Any)
        :param size_match:              If True, the image will be sized matched to the size_match_element if given or the closest Element with the size_match_element_type.
        :type size_match:               (bool)
        :param size_match_element:      The element to size match the image to.
        :type size_match_element:       (sg.Element)
        :param size_match_element_type: The type of the closest Element to size match will be this type.
        :type size_match_element_type:  (Type[sg.Element])
        """
        no_source_given = all(arg is ... for arg in (source, filename, data))

        if no_source_given:
            _source = self._source_default
            _filename = _data = None
        else:
            _source = source if source is not ... else None
            _filename = filename if filename is not ... else None
            _data = data if data is not ... else None

        super().__init__(
            source=_source,
            filename=_filename,
            data=_data,
            background_color=background_color,
            size=size,
            s=s,
            pad=pad,
            p=p,
            key=key,
            k=k,
            tooltip=tooltip,
            subsample=subsample,
            right_click_menu=right_click_menu,
            expand_x=expand_x,
            expand_y=expand_y,
            visible=visible,
            enable_events=enable_events,
            metadata=metadata,
            size_match=size_match,
            size_match_element=size_match_element,
            size_match_element_type=size_match_element_type,
        )

    def _post_init(self):
        self._original_source = self.Source

    def _setup_binds(self) -> None:
        # Set up tkinter bind events

        # Update the image when the widget is made visible. Needed for widgets that are not visible on window creation.
        self.widget.bind("<Map>", lambda e: self._update_image(), add="+")

    update_image = ImageBase._update_image

    def _determine_new_source(
        self, source: Union[str, bytes, None, ellipsis]
    ) -> Union[str, bytes, None]:
        # Return the given source if not None or else the current source.
        return source if source is not ... else self._original_source


class InfoImage(Image):
    """InfoImage element with size-matching functionality. Displays an image with
    an info icon as the default image. Image should be a GIF or a PNG only.
    """

    _source_default: Union[
        str, bytes, None
    ] = b"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"


class EmptyImage(Image):
    """EmptyImage element with size-matching functionality. Displays an empty (transparent)
    image as the default image. An empty image can be used to horizontally align rows in
    multiple columns that don't have the same number of rows. Image should be a GIF or a PNG only.
    """

    _source_default: Union[
        str, bytes, None
    ] = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAANSURBVBhXY2BgYGAAAAAFAAGKM+MAAAAAAElFTkSuQmCC"


class ToggleImage(ImageBase):
    """Toggleable Image element with size-matching functionality - show an image that can be toggled in the window.
    Toggle On and Off images should be a GIF or a PNG only.
    """

    _toggle_on_source_default: Union[str, bytes, None] = None
    _toggle_off_source_default: Union[str, bytes, None] = None

    def __init__(
        self,
        start_toggled_on: bool,
        toggle_on_source: Union[str, bytes, None, ellipsis] = ...,
        toggle_off_source: Union[str, bytes, None, ellipsis] = ...,
        background_color=None,
        size=(None, None),
        s=(None, None),
        pad=None,
        p=None,
        key=None,
        k=None,
        tooltip=None,
        subsample=None,
        right_click_menu=None,
        expand_x=False,
        expand_y=False,
        visible=True,
        enable_events=False,
        metadata=None,
        size_match=False,
        size_match_element: sg.Element = None,
        size_match_element_type: Type[sg.Element] = sg.Element,
    ):
        """
        :param start_toggled_on:               Set to True if you want this element to start toggled on.
        :type start_toggled_on:                bool
        :param toggle_on_source:               A filename or a base64 bytes for the toggle on image. Will automatically detect and handle the type.
        :type toggle_on_source:                str | bytes | None
        :param toggle_off_source:              A filename or a base64 bytes for the toggle off image. Will automatically detect and handle the type.
        :type toggle_off_source:               str | bytes | None
        :param source:                         A filename or a base64 bytes. Will automatically detect the type and fill in filename or data for you.
        :type source:                          str | bytes | None
        :param background_color:               color of background
        :type background_color:
        :param size:                           (width, height) size of image in pixels
        :type size:                            (int, int)
        :param s:                              Same as size parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, size will be used
        :type s:                               (int, int)  | (None, None) | int
        :param pad:                            Amount of padding to put around element in pixels (left/right, top/bottom) or ((left, right), (top, bottom)) or an int. If an int, then it's converted into a tuple (int, int)
        :type pad:                             (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param p:                              Same as pad parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, pad will be used
        :type p:                               (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
        :param key:                            Used with window.find_element and with return values to uniquely identify this element to uniquely identify this element
        :type key:                             str | int | tuple | object
        :param k:                              Same as the Key. You can use either k or key. Which ever is set will be used.
        :type k:                               str | int | tuple | object
        :param tooltip:                        text, that will appear when mouse hovers over the element
        :type tooltip:                         (str)
        :param subsample:                      amount to reduce the size of the image. Divides the size by this number. 2=1/2, 3=1/3, 4=1/4, etc
        :type subsample:                       (int)
        :param right_click_menu:               A list of lists of Menu items to show when this element is right clicked. See user docs for exact format.
        :type right_click_menu:                List[List[ List[str] | str ]]
        :param expand_x:                       If True the element will automatically expand in the X direction to fill available space
        :type expand_x:                        (bool)
        :param expand_y:                       If True the element will automatically expand in the Y direction to fill available space
        :type expand_y:                        (bool)
        :param visible:                        set visibility state of the element
        :type visible:                         (bool)
        :param enable_events:                  Turns on the element specific events. For an Image element, the event is "image clicked"
        :type enable_events:                   (bool)
        :param metadata:                       User metadata that can be set to ANYTHING
        :type metadata:                        (Any)
        :param size_match:                     If True, the image will be sized matched to the size_match_element if given or the closest Element with the size_match_element_type.
        :type size_match:                      (bool)
        :param size_match_element:             The element to size match the image to.
        :type size_match_element:              (sg.Element)
        :param size_match_element_type:        The type of the closest Element to size match will be this type.
        :type size_match_element_type:         (Type[sg.Element])
        """

        self.is_toggled_on = start_toggled_on
        self.toggle_on_source = (
            toggle_on_source
            if toggle_on_source is not ...
            else self._toggle_on_source_default
        )
        self.toggle_off_source = (
            toggle_off_source
            if toggle_off_source is not ...
            else self._toggle_off_source_default
        )

        current_source = (
            self.toggle_on_source if self.is_toggled_on else self.toggle_off_source
        )

        super().__init__(
            source=current_source,
            background_color=background_color,
            size=size,
            s=s,
            pad=pad,
            p=p,
            key=key,
            k=k,
            tooltip=tooltip,
            subsample=subsample,
            right_click_menu=right_click_menu,
            expand_x=expand_x,
            expand_y=expand_y,
            visible=visible,
            enable_events=enable_events,
            metadata=metadata,
            size_match=size_match,
            size_match_element=size_match_element,
            size_match_element_type=size_match_element_type,
        )

    def _setup_binds(self) -> None:
        # Set up tkinter bind events

        # Remove existing event bindings
        self._unbind_all()

        # Set up PySimpleGUI events on left click release if they're enabled for this element
        if self.EnableEvents:
            self.bind("<ButtonRelease-1>", "")

        # Toggle the element on left click release
        self.widget.bind("<ButtonRelease-1>", lambda e: self.toggle(), add="+")

        # Update the image when the widget is made visible. Needed for widgets that are not visible on window creation.
        self.widget.bind("<Map>", lambda e: self.update_toggle_images())

    def toggle(self) -> None:
        """Toggle the image."""
        self.is_toggled_on ^= True
        self.update_toggle_images()

    def set_toggle(self, state: bool) -> None:
        """Set the toggle state of the element.

        Args:
            state (bool): If True, the element will be toggled on. Else, it will be toggled off.
        """
        self.is_toggled_on = state
        self.update_toggle_images()

    def update_toggle_images(
        self,
        toggle_on_source: Union[str, bytes, None, ellipsis] = ...,
        toggle_off_source: Union[str, bytes, None, ellipsis] = ...,
    ) -> None:
        """Update the sources for the toggle images and update the image with a new source based on the
        current toggle state. If size matching is on, a size-matched version of the new source will
        be used.

        Args:
            toggle_on_source (Union[str, bytes, None], optional): A filename or a base64 bytes for the toggle on image. Will automatically detect and handle the type. Defaults to ... .
            toggle_off_source (Union[str, bytes, None], optional): A filename or a base64 bytes for the toggle off image. Will automatically detect and handle the type. Defaults to ... .
        """

        if toggle_on_source is not ...:
            self.toggle_on_source = toggle_on_source

        if toggle_off_source is not ...:
            self.toggle_off_source = toggle_off_source

        self._update_image()

    def _determine_new_source(
        self, source: Union[str, bytes, None, ellipsis]
    ) -> Union[str, bytes, None]:
        if source is not ...:
            return source
        else:
            # Return the appropriate source for the current toggle state.
            return (
                self.toggle_on_source if self.is_toggled_on else self.toggle_off_source
            )


class FancyCheckbox(ToggleImage):
    """FancyCheckbox Element with size-matching functionality. Displays a checkbox
    with fancy checked/unchecked default images. Checked and unchecked images should
    be a GIF or a PNG only.
    """

    _toggle_on_source_default = b"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"
    _toggle_off_source_default = b"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"

    @property
    def checked(self) -> bool:
        """Toggle state of the checkbox. True if the checkbox is checked."""
        return self.is_toggled_on

    @checked.setter
    def checked(self, is_checked: bool) -> None:
        self.set_toggle(is_checked)


class FancyToggle(ToggleImage):
    """FancyToggle Element with size-matching functionality. Displays a toggle button
    with fancy on/off default images. Toggle On and Off images should be a GIF or a
    PNG only.
    """

    _toggle_off_source_default = b"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"
    _toggle_on_source_default = b"iVBORw0KGgoAAAANSUhEUgAAAGQAAAAoCAYAAAAIeF9DAAARfUlEQVRoge1bCZRVxZn+qure+/q91zuNNNKAtKC0LYhs3R1iZHSI64iQObNkMjJk1KiJyXjc0cQzZkRwGTPOmaAmxlGcmUQnbjEGUVGC2tggGDZFBTEN3ey9vvXeWzXnr7u893oBkjOBKKlDcW9X1a137//Vv9ZfbNmyZTjSwhiDEAKGYVSYpnmOZVkzTdM8zTTNU4UQxYyxMhpzHJYupVSvUmqr67pbbNteadv2a7Ztd2SzWTiOA9d1oZQ6LGWOCJAACMuyzisqKroqGo1eYFlWxDRN3c4512OCejwWInZQpZQEQMa27WXZbHZJKpVank6nFYFzOGAOCwgR2zTNplgs9m/FxcXTioqKEABxvBL/SAsRngCwbXtNOp3+zpSLJzf3ffS5Jc8X/G0cam7DMIqKioruLy4uvjoej7NIJBICcbDnIN78cBXW71qH7d3bsTvZjoRMwpE2wIirjg0RjlbRi1wBBjcR5zFUx4ajtrQWZ46YjC+Mm4Gq0ipNJ8MwiGbTTNN8a+PyTUsSicT1jXMa0oO95oAc4k80MhqNvlBWVjYpHo9rrqD2dZ+sw9I1j6Nl/2qoGCCiDMzgYBYD49BghGh8XlEJRA5d6Z8EVFZBORJuSgEJhYahTfj7afMweczkvMcUcct7iUTikvr6+ta+0xIWAwJimmZdLBZ7uby8fGQsFtMo7zq4C/e+cg9aupphlBngcQ5OIFAVXvXA6DPZ5wkUIr4rAenfEyDBvfTulaMgHQWVVHC6HTSUN+GGP78JNUNqvCmUIiXfmkwmz6urq3s/f/oBARFC1MTj8eaKigq6ajCW/eZXuKd5EbKlGRjlBngRAzO5xxG8z0v7AAyKw2cNH180wQEmV07B2dUzcWbVFIwqHY2ySJnu68p04dOuHVi/Zx3eaF2BtXvXQkFCOYDb48LqieDGxptxwaQLw2kdx9mZSCSa6urqdgZt/QDhnBfFYjECY1JxcbEWU4+8/jAe+/DHME8wYZSIkCMKgOgLwueFKRTAJMPsmjm4YvxVGFUyyvs2LbF8iRCIL7+dLjs6d+DhdUvw7LZnoBiJMQnnoIP5p1yOK//sG+H0JL56e3ub6uvrtU4hLEKlTvrBNM37iouLJwWc8ejKH+Oxjx+FVW1BlAgtosDzCJ4PxEAgfJa5RAEnWiNw39QHcPqQCfqltdXkSCSSCWTSaUgyYcn4IZegqAiaboJjVNloLDxnMf667qu47pVvY5e7E2aVicc+ehScMVw+80r9E4ZhEK3vA/At+BiEHGIYRmNJScnblZWVjPTGyxuW4Z9Xf0+DYZQKMLM/GP2AGOy+X+cfdyElPbVsKu6f/gNURCr0uyaTSXR2duqrOsTXEO3Ky8v1lQZ1JA/i2hevwbsH10K5gL3fxh1Nd+L8My7wcFdKJZPJGePGjWt+9dVXPcHDGGOWZT1YXFysTdu2g21Y3Hy3FlPEGQVgMNYfDNa35hpyDiM+E5Wo3VTRhIdm/AjlVrn2I3bv3o329nakUin9LZyR/mQFzjCtfMY50qkU2ne362dcx0V5tAI/mfMEmqq+qEkiKgwsfvtu7DqwCwHtI5HIA3RvWZYHiBDiy0VFRdrpIz/jnlcWwy7Nap1RIKYCwvJBwAhByBG/P1h/xBXA6Oho3DvtARgQsG0HbW3tSCZT4AQAzweDhyBQG3iwSD2Akqkk2tva4WQdGNzAgxf9O0Zbo8EFQzaWweLli0KuEkI0bNu2bRbRn/viisIhWom/t2N9aNqyPjpjUK5AHhfwvHb+2QKEKYbvT1iIGI/BcST27dsL13U8MBgPweB5HOFd6W+h+7kPEFXHdbBn7x44rouoGcXds+4FyzDwIo6Wjmas274u4BKi/TWEAeecVViWdWEkYsEwBJauecLzM6LeD/VV4H3VwoT4GVgw7nZsvPgDr17k1VtOuh315gQoV/lWCXDr2O9i44Uf6HrL6Nshs7k+Kj9r+LnuWzFzFWRKes8eraKAi4ddgtPK66GURGdXpw8GL6gBR/S9Emhhf95VShddHR06vjVh+ARcMma29llEXODJtY+HksQwBGFQwTkX51qWZZmmhY7eTryzvxk8xrWfEZq2g+iM2SfMxf+c8xS+Ov5r/aj2d/Vfw09nPY1LSudoR8nXYGH/nHFzUS8nQNoyN2fQTcrvgANlq6PHIS4wr3a+Jlw6nUY2kwFjwhNPeaAInzOED4B3ZXmgsQI9Q5yTzmaQTmf03P/YcCVUGtp1WL2nGQd7OnwJwwmDc7kQ4ktBsPDNraugogCPHMKCYjnOuKvh7sMu34VnL0K9mgDpFOCBmBXD9WfeCJlU2qop4EByetN57X/oCoZJpZNRUzQSUklPeXMGoQEQ+toXGOYT3yO8yOMUkQcU1zpDcKHnpLlHVYzE5KopmkukCaza+uvwswkLAuR00u4EyLq2dV5symT9uaMAGIYrx14VNm1u3YQrHr8ctYtH4eT7R+PKn16Bzbs2hf3fGH81ZMItEE9UGsY0YHblXMBWA0ZcjlalldJU+QVNMOlKuFLqlU2rmAt/pecTXARXGuMBE4BGY3QANtyW8MAjn4XmllLhi6PO0iEWbgJrW9eGlhphwTnnY4P9jO0d27yQiBjEys5rbhjeqK879u3AxUsvxBvdr8EabsIaYWEVW4mvvHYpNrdv1mOaxjRB9voxIL88t/ZZfXP9jBvg9rr6BY9ZkcDpJRM0sRzb8QnsrWweXj1OITA05wTcQhwkhC/GvH4CQfgACh8w4iLbsbXYmnjiRB1WodXwScf2vEXITua0yxdsMu1Ot4MZrD8gff6cEJ+ImBnT98RyIs5hVAkYFYY2CMiRNCoNvHdgvR4Ti8QwMXpGASBL1z+BfT37MLRkKG4bf4dW4seqkCitiY7UxCIuITHFfTACEcR9YueLKw2CyOkW4hjBcyB4QOXaaH7y9kdVjgZ8g6U92Z7zZTgvJ0BKg4akm/ydHeruTDd4lOtKYAY6hpsMWxKbw3G1JWMLAGECeHrTU/p+7sSvoJ5P7CfSjlqRCnEjpsGAvykXiqVAmefpDtGnzauij0Um+t0TaQiUkkiJJxGUQoponuOQUp7vbarfgyKlRaXa9xho97C+4vTwftuBjwq1Omd48KMHsK93n+ag6yffqEMLx6SQESHJiJDeShV9iRuII5EHggg5RlejcHzQJ/KAIVGmuZA4Rfr7KAqFHr9SqjvYC46J2BGt0o29G5C0PWTPn3CBP3nhg/RDM6pn6PtkJon1nev7+TLEUQ+sv1/fk4IfUznmGCHihdClv2C0qBKFYGjlzVjhqmf9uSGnW3JmsAZSeFYSgd6Z6PJ+VAExEQ3fgbDgfsaEbhgeG6FZqZ9DNgBIq3d628NDS4fi2Yt/gdkVcz02lApfKpuJn037X4wuPUmP2di60RNnffZOiLNe6HwOm/d6oo1M4WNSGNCa+K1nBSnlE1uEK531UeqBWat1hfBM2wAAFoq6PCNAr36hudBVEjv2f+J9pVSojg7PTw7p5FLKj4NMiNqyWij7EB5y0MyARz58KGyuP7EeC2cuwqa/2Ko97f9oWoLThtSH/YtXLNKbWgX6KdhGEMB/fbT02AARFM6wqWOj9tBdx4Eg38E3ebnvhwiWrz9EKNY8P0XkiTkRWmnM7w84xXFtSFdhQ+t7Hi2kwpiK2vA1lFLbSGRtIkBIrk0bNU3vCWsPWYajCkS/R0iFjakNWLDilsN+681P3YgNqfUQxQIQhX3eljTDCx3PoaX1nf59R6lSWX2wWfsfru8vhA5eYLaKfEXPwvAJ83WDNnEDMISvX4QIn9W6Qy98ibe2v6mlA+WDTB05NeQQKeVm4pBfU74QPXDWqWeBpQCZUWFWRSEQuS1NmvC5jmfxV8/8JZ58p/8KX7rqCcx9ZA5+3vY0jAqh9+ALOSRHbZrrX7fQPs0xQoQpbOrdgJ09rZoOyXRa6wvB8j10plc744Gz6HEN90MnIvTchecMEucwFoou7alLhU/3/xbv7f6N53DbDGefdnb4yVLKlez111+vKCkp2V1VVWXRtu21//1NtDirYZ5ggFs8t6oHimfBQ1mlXLgJ6QUEHS/+pL3cGIco5uAxoc1g6nO6XDhdju43hxge5zAvOYD2n50OFzIrdTv1kzn9By86VCMxK/ZlXFd/k/60srIyUDg897GqMN4WEkLljcj/P9eazqTR1ekp8oW//Be8tONFzTXTKxvx0PyHPQtXqWxvb281iSxKd3wpk8lodp3f+HVNMEmiS+ZFYwfJtiP3nxPxqgxY1SYiNRYiIyzttZtDDW/r1/T0Byl2USpgDaM+s4DYBBCNNYeZ+nkCQ4f/j0bx3+2VjuXYevB9zSVdXV36Gsas8i0nFlhcOasrNy4/5sW8uTq9ubbs2oKXPvylTpuSWRfzm+aH7oLruoRBh6aIbdsPEUvZto3JtVPQVDlDp7BQrlGQ5hJi0kd0wVfMRDweF7rS6qbwMnGYDuHniTwCh/pELC9Eo/JA0Vwl9J6BflbhqFT9LiZwz/t3I5FN6D2MvXv3Qfoh+HxdEYixcKcw3BPxrClPZHGd00tz0DWZSeDOl+4AIl4q0PQTGjH91Aafrjpf64eEAfdl1/JMJkPpjhrJW8+/DVZXBE6P6+1ZBKD4Cl7JAYBRuT9C8SyPDjH/XyotCJOhTe3CXevvhO1k4Dg2drfv0fvoHkegQKfkgocMHPkhFYZUKqm3cWmOrGvju8/fhtZUq168RXYRFlx0e5gFKqVsqampeYWkFPcRUplM5ju9vb10RU1VDRacdTvsvbYX+LMLQQktr4FACcaE4AT16Orp36eS+YsIx7r0u7ij5XtIZpOwaddvzx60tbUhlUoXcgXru63LtPJub2vTz5AKIKd4wTM3oWVPi97WIF1188xbcVL1SQF3UBL2dXRPtBfz5s0LOnYqpYYahjGd9kfqauqgeoCWT1v0ytHZibxvdiILdV2/GNihPP6jpBp+5xJs5XKgLdWGVTtWYnxxHYZEh2ix09Pdg67uLmRtG45taxFPFiqB0NXdjb1796K7u0uPpbK1/QPc9PwN+KDrfe2HkfX69UlX4LKZ8zR30EKl7PgRI0Y8TOMvu+yyXF6W33ljT0/PDMoXIna8etY1Or71oy0PDZwo5yt6FQDTxwIbFJRjGGk/XNGvbnBQFIkSyP9pzbdwbsUs/E3d32J46QhIx0F3VxfCXCDi/mBF6sWp0Na1E0+2PImXt70MFkHIGQTGtRd8W4MBL3uR8nxvCF6JMGArVqwoeEXDMMJUUjKDKWHuxXd/gbtWfR92Wdbbbz8OUkmVn6erUtIz6RMSddHTMH1YI+qH1uPE0hEoiRRrEHqyPWjrbMPm3ZvQ/Onb2LhvE5ihNI3IUo3YEdwycwFmN1yaD8ZOylqsra0NU0kJi36AwE+2jsfjOtk6yGJs3d+KRS8vRPOBt3LJ1hGWE2efx2RrnVztRS5kxvOzdE1LL9ud+tzCkJK3SJneoyfTtnFYE26+cAHGVI/RRkCQbJ1IJM6rra0tSLYeFJDgOEIsFguPI9A2L7Wv+XgN/vOdn6B591tAnB0fxxECYBy/ZqUHhJsLo8Pf3yBHGRmgYUQT/qFxPhrHN2ogkFMLJKYuHTt27Kd9f4awGPDAjm8XE4pNUsr7HccJD+xMPXkqpo2dhgM9B7Dy/TfwbutabOvchvYD7eh1e+HS3uTn+cCO9I+vSe+ew0CxiKM6Xo3ailpMrpmiwyHDKqpDp88/SUXW1JLe3t7rx48fP/iBnYE4JL8QupZl0ZG2H8Tj8emUs/qnI21HVvKOtLUkk8nrxo0b9/ahHhyUQ/ILOYqZTKbZcZyGTCYzK5lMfjMajZ4fiUT0oU8vIir+dOgz79CnHz3P2rb9q0wm88NTTjll+ZHOc1gOKRjsn8Y1TZOORVOC3dmWZdUbhqGPRXPOS49TQHqUUj1SSjoWvdlxnJXZbPa1bDbbQb4K1SM6Fg3g/wC58vyvEBd3YwAAAABJRU5ErkJggg=="


def save_toggle_state(toggle_element: ToggleImage) -> None:
    """Save the toggle element's toggle state to the config file.

    Args:
        toggle_element (ToggleImage): The toggle element whose toggle state is to be saved.
    """
    sg.user_settings_set_entry(
        toggle_element.key,
        toggle_element.is_toggled_on,
    )


def convert_rows_to_columns_for_elements(
    rows: Sequence[Sequence[sg.Element]], fill_element_type: Type[sg.Element]
) -> List[sg.Column]:
    """Convert a series of rows with PySimpleGUI elements into a list of PySimpleGUI columns.

    Args:
        rows (Sequence[Sequence[sg.Element]]): A Sequence of rows (Sequence) with PySimpleGUI elements.
        fill_element_type (Type[sg.Element]): The type of element that's used to filling in column rows
            when the given rows are of unequal length.

    Returns:
        List[sg.Column]: A list of PySimpleGUI columns.
    """
    # Group the elements into columns
    column_grouped_elements_list = zip_longest(*rows, fillvalue=None)

    # Make a list of PySimpleGUI Column elements from the column grouped elements
    columns = []
    for column_elements in column_grouped_elements_list:
        # Replace None values with elements of the specified type
        column_layout = [
            [element if element is not None else fill_element_type()]
            for element in column_elements
        ]
        column = sg.Column(column_layout, pad=(0, 0))
        columns.append(column)

    return columns


def popup_tracked(
    *args: Any,
    popup_fn: Callable[..., Tuple[sg.Window, Optional[str]]],
    window_tracker: WindowTracker,
    **kwargs: Any,
) -> sg.Window:
    """Pop up a tracked window.

    Args:
        popup_fn (Popup_Callable): The function to call to create a popup.
        window_tracker (WindowTracker): Tracker for possibly active windows which the created popup will be added to.
    """
    popup_window, _ = popup_fn(*args, **kwargs)

    window_tracker.track_window(popup_window)

    return popup_window


class CustomTimer(Timer):
    """codetiming.Timer with a stop() that optionally prints the elapsed time."""

    def stop(self, log_time: bool = True) -> float:
        """Stop the timer, and optionally report the elapsed time.

        Args:
            log_time (bool, optional): If True, prints the elapsed time. Defaults to True.

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


def disable_elements(gui_elements: Iterable[sg.Element]) -> None:
    """Disable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the PySimpleGUI elements to disable.
    """
    update_elements(gui_elements=gui_elements, disabled=True)


def enable_elements(gui_elements: Iterable[sg.Element]) -> None:
    """Enable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the PySimpleGUI elements to enable.
    """
    update_elements(gui_elements=gui_elements, disabled=False)


def update_elements(gui_elements: Iterable[sg.Element], **kwargs) -> None:
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
    choice, _ = Window('Continue?', [[sg.T('Do you want to continue?')], [sg.Yes(s=10), sg.No(s=10)]], disable_close=True).read(close=True)


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

    window = Window(
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
        finalize=True,
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
) -> Tuple[Optional[sg.Window], Optional[str]]:
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
    :return:                    Returns the window for the popup and text of the button that was pressed.  None will be returned in place of the button text if user closed window with X.
                                (None, None) will be returned if no positional arguments are given.
    :rtype:                     (sg.Window | None, str | None | TIMEOUT_KEY)
    """
    if not args:
        return (None, None)
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
        lines_needed = GetNumLinesNeeded(message, width_used)
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
            Multiline(
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
    button = sg.DummyButton if non_blocking else sg.Button
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

    window = Window(
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
# ============================== GetNumLinesNeeded ==#
# Helper function for determining how to wrap text   #
# ===================================================#
def GetNumLinesNeeded(text: str, max_line_width: int) -> int:
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


# Taken from Pysimplegui.DummyButton() and modified.
# -------------------------  Dummy BUTTON Element lazy function  ------------------------- #
def DummyButton(
    button_text,
    image_filename=None,
    image_data=None,
    image_size=(None, None),
    image_subsample=None,
    border_width=None,
    tooltip=None,
    size=(None, None),
    s=(None, None),
    auto_size_button=None,
    button_color=None,
    font=None,
    disabled=False,
    bind_return_key=False,
    focus=False,
    pad=None,
    p=None,
    key=None,
    k=None,
    visible=True,
    metadata=None,
    expand_x=False,
    expand_y=False,
):
    """
    This is a special type of Button.

    It will close the window but NOT send an event that the window has been closed.

    It's used in conjunction with non-blocking windows to silently close them.  They are used to
    implement the non-blocking popup windows. They're also found in some Demo Programs, so look there for proper use.

    :param button_text:      text in the button
    :type button_text:       (str)
    :param image_filename:   image filename if there is a button image
    :type image_filename:    image filename if there is a button image
    :param image_data:       in-RAM image to be displayed on button
    :type image_data:        in-RAM image to be displayed on button
    :param image_size:       image size (O.K.)
    :type image_size:        (Default = (None))
    :param image_subsample:  amount to reduce the size of the image
    :type image_subsample:   amount to reduce the size of the image
    :param border_width:     width of border around element
    :type border_width:      (int)
    :param tooltip:          text, that will appear when mouse hovers over the element
    :type tooltip:           (str)
    :param size:             (w,h) w=characters-wide, h=rows-high
    :type size:              (int, int)
    :param s:                Same as size parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, size will be used
    :type s:                 (int, int)  | (None, None) | int
    :param auto_size_button: True if button size is determined by button text
    :type auto_size_button:  (bool)
    :param button_color:     button color (foreground, background)
    :type button_color:      (str, str) or str
    :param font:             specifies the  font family, size, etc. Tuple or Single string format 'name size styles'. Styles: italic * roman bold normal underline overstrike
    :type font:              (str or (str, int[, str]) or None)
    :param disabled:         set disable state for element (Default = False)
    :type disabled:          (bool)
    :param bind_return_key:  (Default = False) If True, then the return key will cause a the Listbox to generate an event
    :type bind_return_key:   (bool)
    :param focus:            if focus should be set to this
    :type focus:             (bool)
    :param pad:              Amount of padding to put around element in pixels (left/right, top/bottom) or ((left, right), (top, bottom)) or an int. If an int, then it's converted into a tuple (int, int)
    :type pad:               (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
    :param p:                Same as pad parameter.  It's an alias. If EITHER of them are set, then the one that's set will be used. If BOTH are set, pad will be used
    :type p:                 (int, int) or ((int, int),(int,int)) or (int,(int,int)) or  ((int, int),int) | int
    :param key:              key for uniquely identify this element (for window.find_element)
    :type key:               str | int | tuple | object
    :param k:                Same as the Key. You can use either k or key. Which ever is set will be used.
    :type k:                 str | int | tuple | object
    :param visible:          set initial visibility state of the Button
    :type visible:           (bool)
    :param metadata:         Anything you want to store along with this button
    :type metadata:          (Any)
    :param expand_x:         If True the element will automatically expand in the X direction to fill available space
    :type expand_x:          (bool)
    :param expand_y:         If True the element will automatically expand in the Y direction to fill available space
    :type expand_y:          (bool)
    :return:                 returns a button
    :rtype:                  (Button)
    """
    return sg.Button(
        button_text=button_text,
        button_type=sg.BUTTON_TYPE_CLOSES_WIN_ONLY,
        image_filename=image_filename,
        image_data=image_data,
        image_size=image_size,
        image_subsample=image_subsample,
        border_width=border_width,
        tooltip=tooltip,
        size=size,
        s=s,
        auto_size_button=auto_size_button,
        button_color=button_color,
        font=font,
        disabled=disabled,
        bind_return_key=bind_return_key,
        focus=focus,
        pad=pad,
        p=p,
        key=key,
        k=k,
        visible=visible,
        metadata=metadata,
        expand_x=expand_x,
        expand_y=expand_y,
    )


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
        use_language_code (bool): If True, the detected language's language code will be used in the
            output file name if possible. Otherwise, the detected language's name will be used in the output
            file name if possible.
        initial_prompt (str, optional): User provided text that guides the transcription to a certain dialect/language/style. Defaults to None.
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
            """Send the contents in a connection to a window as a print event.

            Args:
                win (sg.Window): The window to write the print event to.
                conn (Union[Connection, PipeConnection]): The connection to read from.
            """
            win.write_event_value(print_event, str(conn.recv()))

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
                send_piped_output_to_window(window, read_connection)

        while read_connection.poll():
            send_piped_output_to_window(window, read_connection)

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
        queue (multiprocessing.Queue): The queue that the results of the transcription will be put in.
        write_connection (Union[Connection, PipeConnection]): A writeable Connection to redirect prints into.
        process_done_flag (EventClass): The flag that signals process completion to the parent thread.
        translate_to_english (bool): True if the user has chosen to translate the transcription to English, False otherwise.
        initial_prompt (str, optional): User provided text that guides the transcription to a certain dialect/language/style. Defaults to None.
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


class OutputRedirector(io.StringIO):
    """Redirector for stdout and/or stderr to a writeable Connection."""

    def __init__(
        self,
        write_conn: Union[Connection, PipeConnection],
        reroute_stdout=True,
        reroute_stderr=True,
    ) -> None:
        """
        Args:
            write_conn (Union[Connection, PipeConnection]): A writeable connection.
            reroute_stdout (bool, optional): If True, redirects stdout to the connection. Defaults to True.
            reroute_stderr (bool, optional): If True, redirects stderr to the connection. Defaults to True.
        """
        self._write_conn = write_conn
        if reroute_stdout:
            self.reroute_stdout_to_here()
        if reroute_stderr:
            self.reroute_stderr_to_here()

    def reroute_stdout_to_here(self) -> None:
        """Send stdout (prints) to this element."""
        self._previous_stdout = sys.stdout
        sys.stdout = self

    def reroute_stderr_to_here(self) -> None:
        """Send stderr to this element."""
        self._previous_stderr = sys.stderr
        sys.stderr = self

    def restore_stdout(self) -> None:
        """Restore a previously re-reouted stdout back to the original destination."""
        if self._previous_stdout:
            sys.stdout = self._previous_stdout
            self.previous_stdout = None  # indicate no longer routed here

    def restore_stderr(self) -> None:
        """Restore a previously re-reouted stderr back to the original destination."""
        if self._previous_stderr:
            sys.stderr = self._previous_stderr
            self.previous_stderr = None  # indicate no longer routed here

    def write(self, txt: str) -> int:
        """
        Called by Python when stdout or stderr wants to write.
        Send the text through the pipe's write connection.

        :param txt: text of output
        :type txt:  (str)
        """
        # Send text through the write connection and ignore OSError that occurs when the process is killed.
        with suppress(OSError):
            self._write_conn.send(txt)

        return len(txt)

    def flush(self) -> None:
        """Handle Flush parameter passed into a print statement.

        For now doing nothing.  Not sure what action should be taken to ensure a flush happens regardless.
        """
        try:
            self._previous_stdout.flush()
        except:
            pass

    def __del__(self) -> None:
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


def close_connections(connections: Iterable[Union[Connection, PipeConnection]]) -> None:
    """Close all given connections.

    Args:
        connections (Iterable[Union[Connection, PipeConnection]]): Iterable with all of the connections to close.
    """
    for conn in connections:
        conn.close()


def write_transcript_to_files(
    transcribe_result: Dict[str, Union[dict, Any, str]],
    audio_path: str,
    output_dir_path: str,
    language_code_as_specifier: bool,
    is_translated_to_english: bool,
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
        is_translated_to_english (bool): If True, the result was translated into English.

    Returns:
        Tuple[str, str, str]: A Tuple with the file paths for the transcription result files.
    """
    output_dir = Path(output_dir_path)
    audio_basename = Path(audio_path).stem

    language_specifier = str(transcribe_result["language"]).strip()

    # A translated result will be in English even though the detected language may be different
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
            write_fn (Callable[[Iterator[dict], TextIO], None]): A Callable that writes a transcript to a file.
            transcript (Iterator[dict]): The segment-level details from a transcription result.
            language_specifier (str): The language specifier to put in the file's name.
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
    srt_path = write_transcript(write_srt, transcript, language_specifier, ".srt")
    txt_path = write_transcript(write_txt, transcript, language_specifier, ".txt")
    vtt_path = write_transcript(write_vtt, transcript, language_specifier, ".vtt")
    return (srt_path, txt_path, vtt_path)


# ===================================================#
# =============== Unused f(x)s below ================#
# ===================================================#

# import os

# def get_abs_resource_path(relative_path: str) -> str:
#     """Get the absolute path to the resource.

#     Works when used in a frozen application for Windows made using a tool like Pyinstaller.

#     Args:
#         relative_path (str): Relative file path for the resource.

#     Returns:
#         str: Absolute file path for the resource.
#     """
#     base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
#     return os.path.join(base_path, relative_path)


# def convert_audio_video_to_audio(
#     audio_video_file_path: Union[str, Path],
#     output_dir_path: Union[str, Path],
#     shell_output_window: Optional[sg.Window] = None,
# ) -> Tuple[int, str, str]:
#     """Convert an audio/video file into an audio file using ffmpeg.

#     Args:
#         audio_video_file_path (Union[str, Path]): The file path for the audio/video file.
#         output_dir_path (Union[str, Path]): The output directory path.
#         shell_output_window (Optional[sg.Window], optional): The window that the shell command writes console output should to.
#             Defaults to None.

#     Returns:
#         Tuple[int, str, str]: A Tuple with the return value from executing a subprocess, a copy of the console output by the shell command,
#             and the absolute file path for the converted audio file.
#     """
#     video_path = Path(audio_video_file_path)

#     output_directory_path = Path(output_dir_path)

#     audio_file_name = f"{video_path.stem}.mp3"

#     audio_output_path = output_directory_path / audio_file_name

#     cmd = f'ffmpeg -i "{video_path.resolve()}" -y -q:a 0 -map a "{audio_output_path}"'

#     retval, shell_output = run_shell_cmd(cmd=cmd, window=shell_output_window)
#     return retval, shell_output, str(audio_output_path.resolve())

# import subprocess
# import shlex

# def run_shell_cmd(
#     cmd: str, timeout: Optional[float] = None, window: Optional[sg.Window] = None
# ) -> Tuple[int, str]:
#     """Run shell command.
#     @param cmd: command to execute.
#     @param timeout: timeout for command execution.
#     @param window: the PySimpleGUI window that the output is going to (needed to do refresh on).
#     @return: (return code from command, command output).
#     """
#     p = subprocess.Popen(
#         shlex.split(cmd), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
#     )
#     shell_output = ""
#     if p.stdout:
#         for line in p.stdout:
#             print(f"sys.version_info= {sys.version_info}")
#             if sys.version_info < (3, 5):
#                 errors = "replace"
#             else:
#                 errors = "backslashreplace"
#             decoded_line = line.decode(errors=errors).rstrip()
#             shell_output += decoded_line
#             print(decoded_line)
#             if window:
#                 window.refresh()
#     retval = p.wait(timeout)
#     return (retval, shell_output)


# class NotAFileError(Exception):
#     """Operation only works on files."""


# def del_existing_file(file_path: Union[str, Path]):
#     """Delete an existing file.

#     Args:
#         file_path (Union[str, Path]): The file path for the file to delete.

#     Raises:
#         NotAFileError: The path does not lead to a file.
#     """
#     p = Path(file_path)
#     if p.exists():
#         if not p.is_file():
#             raise NotAFileError
#         p.unlink()

# import tkinter as tk
# import tkinter.font as tkfont
# import tkinter.ttk as ttk

# def combo_configure(event: tk.Event) -> None:
#     """Set the width of the dropdown list to fit all options.

#     Does not change the entry box width.

#     Usage:
#         window[combo_key].widget.bind(
#             "<ButtonPress>", combo_configure
#         )
#     """


#     combo = event.widget
#     style = ttk.Style()

#     long = max(combo.cget("values"), key=len)

#     # font = tkfont.nametofont(str(combo.cget('font')))
#     font = tkfont.Font(font=combo.cget("font"))
#     width = max(0, font.measure(long.strip() + "0") - combo.winfo_width())

#     style_name = "TCombobox"

#     style.configure(style_name, postoffset=(0, 0, width, 0))
#     combo.configure(style=style_name)


# def get_combo_values(combo: sg.Combo) -> Tuple:
#     """Get the values for the Combo element.

#     Args:
#         combo (sg.Combo): The Combo element.

#     Returns:
#         Tuple: A Tuple with the values for the Combo element.
#     """
#     return combo.widget.cget("values")


# def set_combo_input_justify(combo: sg.Combo, justify: str) -> None:
#     """Align the text in the combo input field.

#     Args:
#         combo (sg.Combo): The Combo element to update.
#         justify (str): Specifies how the text is aligned within the Combo's input field.
#             One of "left", "center", or "right".

#     Raises:
#         ValueError: justify parameter must be 'left', 'center', or 'right'
#     """
#     if justify not in ("left", "center", "right"):
#         raise ValueError(
#             f"Invalid justify parameter value: {justify}. "
#             f"justify parameter must be 'left', 'center', or 'right'"
#         )

#     combo.widget.configure(justify=justify)


# def format_multiline_text(
#     element: sg.Multiline, is_multiline_rstripping_on_update: bool
# ) -> None:
#     """Update the text in a multiline element.

#     Replaces \r with \n.
#     Replaces progress characters between |s in progress bars with proper █s.

#     Args:
#         element (sg.ErrorElement): A Multiline element.
#         is_multiline_rstripping_on_update (bool): If True, the Multiline is stripping whitespace
#             from the end of each string that is appended to its text.
#     """
#     # Get the text in the Multiline element
#     text = element.get()

#     # remove the auto appended '\n' by every Multiline.get() call when rstrip=False option is set for Multiline
#     if not is_multiline_rstripping_on_update:
#         text = text[:-1]

#     # Replace all \r with \n
#     processed_text = re.sub(r"\r", "\n", text)

#     def repl_progress_bars(m: re.Match):
#         return "█" * len(m.group())

#     processed_text = re.sub(r"(?<=\|)\S+(?=\s*\|)", repl_progress_bars, processed_text)

#     element.update(processed_text)


if __name__ == "__main__":
    # Required for when a program which uses multiprocessing has been frozen to produce a Windows executable.
    # (Has been tested with py2exe, PyInstaller and cx_Freeze.) has no effect when invoked on any operating system other than Windows
    multiprocessing.freeze_support()

    # The only method that works on both Windows and Linux is "spawn"
    multiprocessing.set_start_method("spawn")
    main()
