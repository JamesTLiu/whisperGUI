#!/usr/bin/env python3
# mypy: disable-error-code=union-attr

from __future__ import annotations

import base64
import decimal
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
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from itertools import islice, zip_longest
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

import PIL.Image
import PySimpleGUI as sg
import whisper
from codetiming import Timer, TimerError
from whisper.tokenizer import LANGUAGES as TO_LANGUAGE
from whisper.tokenizer import TO_LANGUAGE_CODE
from whisper.utils import write_srt, write_txt, write_vtt

import set_env
from utils import (
    GetWidgetSizeError,
    OutputRedirector,
    WidgetNotFoundError,
    _random_error_emoji,
    close_connections,
    convert_to_bytes,
    ensure_valid_layout,
    find_closest_element,
    get_element_size,
    get_event_widget,
    get_settings_file_path,
    function_details,
    get_widget_size,
    popup_on_error,
    resize_window_relative_to_screen,
    set_resizable_axis,
    set_window_to_autosize,
    setup_height_matched_images,
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


class PostInit:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._post_init()

    def _post_init(self):
        ...


class Multiline(sg.Multiline):
    """Multiline Element with extra capabilities - Display and/or read
    multiple lines of text. This is both an input and output element.
    """

    def write(self, txt: str) -> None:
        """Called by Python (not tkinter?) when stdout or stderr wants
        to write. The text is formatted before being written.

        :param txt: text of output
        :type txt:  (str)
        """
        formatted_txt = self._format_text(txt)
        super().write(formatted_txt)

    def _format_text(self, text: str) -> str:
        """Return formatted text meant for console output.

        Replaces \r with \n.
        Replaces progress characters between '|'s in progress bars with
        proper '█'s.

        Args:
            text (str): The text to format.
        """
        # remove the auto appended '\n' by every Multiline.get() call
        # when rstrip is False
        _text = text

        # Replace all \r with \n
        processed_text = re.sub(r"\r", "\n", _text)

        def replace_with_progress_bars(m: re.Match) -> str:
            # Replace all chars in the match with a █.
            return "█" * len(m.group())

        processed_text = re.sub(
            r"(?<=\|)\S+(?=\s*\|)", replace_with_progress_bars, processed_text
        )

        return processed_text


class Window(PostInit, sg.Window):
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
    ) -> None:
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
            right_click_menu_background_color=right_click_menu_background_color,  # noqa: E501
            right_click_menu_text_color=right_click_menu_text_color,
            right_click_menu_disabled_text_color=right_click_menu_disabled_text_color,  # noqa: E501
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

    def _post_init(self):
        self._setup()

    def _setup(self) -> None:
        # Make sure the window and its contents are drawn.
        self.refresh()

        # Run the setup for each element if it exists
        for element in self.element_list():
            with suppress(AttributeError):
                element._setup()

        # Make the changes appear
        self.refresh()


class SuperElement(PostInit, sg.Element):
    """The base class for all Elements but with extra capabilities."""

    def __init__(
        self,
        type=sg.ELEM_TYPE_BLANK,
        size=(None, None),
        auto_size_text=None,
        font=None,
        background_color=None,
        text_color=None,
        key=None,
        pad=None,
        tooltip=None,
        visible=True,
        metadata=None,
        sbar_trough_color=None,
        sbar_background_color=None,
        sbar_arrow_color=None,
        sbar_width=None,
        sbar_arrow_width=None,
        sbar_frame_color=None,
        sbar_relief=None,
        *args,
        **kwargs,
    ):
        super().__init__(
            type=type,
            size=size,
            auto_size_text=auto_size_text,
            font=font,
            background_color=background_color,
            text_color=text_color,
            key=key,
            pad=pad,
            tooltip=tooltip,
            visible=visible,
            metadata=metadata,
            sbar_trough_color=sbar_trough_color,
            sbar_background_color=sbar_background_color,
            sbar_arrow_color=sbar_arrow_color,
            sbar_width=sbar_width,
            sbar_arrow_width=sbar_arrow_width,
            sbar_frame_color=sbar_frame_color,
            sbar_relief=sbar_relief,
        )

    def _setup(self) -> None:
        """Set up internal tkinter event binds and update internal
        components. Only call this after the widget is created via
        calling window.refresh() or window.read() on the window with
        this element.
        """

        # Update internal components now that a widget exists
        if self._widget_was_created():
            self._setup_binds()
            self._update_internals()
        else:
            sg.PopupError(
                "Error during element setup.",
                "The widget for this element does not exist.",
                (
                    "You MUST only call this method after the widget is"
                    " created via calling window.refresh() or window.read()"
                ),
                "The offensive Element = ",
                self,
                "and has a key = ",
                self.Key,
                "The setup for this element will be aborted.",
                keep_on_top=True,
                image=_random_error_emoji(),
            )

    def _setup_binds(self) -> None:
        """Set up tkinter bind events. Automatically called when
        self._setup() is called.
        """
        ...

    def _update_internals(self) -> None:
        """Update internal components. Automatically called when
        self._setup() is called.
        """
        ...

    def _unbind_all(self) -> None:
        """Remove all event bindings for this element's widget."""
        for event in self.widget.bind():
            self.unbind(event)


class Grid(sg.Column, SuperElement):
    """Grid element - a container element that is used to create a
    horizontally and vertically aligned layout within your window's
    layout.

    Note: The Elements in each row of the passed in layout will be
    wrapped non-recursively in a Column which acts as a block in the
    grid.
    """

    def __init__(
        self,
        layout,
        background_color=None,
        size=(None, None),
        s=(None, None),
        size_subsample_width=1,
        size_subsample_height=2,
        pad=None,
        p=None,
        scrollable=False,
        vertical_scroll_only=False,
        right_click_menu=None,
        key=None,
        k=None,
        visible=True,
        justification=None,
        element_justification=None,
        vertical_alignment=None,
        grab=None,
        expand_x=None,
        expand_y=None,
        metadata=None,
        sbar_trough_color=None,
        sbar_background_color=None,
        sbar_arrow_color=None,
        sbar_width=None,
        sbar_arrow_width=None,
        sbar_frame_color=None,
        sbar_relief=None,
        uniform_block_sizes=False,
    ):
        self.uniform_block_sizes = uniform_block_sizes

        # processed_layout = self._process_layout(layout=layout)

        # Lookup the block that a widget is in
        self._widget_to_block: Dict[tk.Widget, Block] = {}

        # Lookup a block column by number. Block columns are numbered
        # left to right starting from 0.
        self.block_col_num_to_block_col: Dict[int, BlockColumn] = {}

        self.uniform_block_width = self.uniform_block_height = 1

        super().__init__(
            layout=layout,
            background_color=background_color,
            size=size,
            s=s,
            size_subsample_width=size_subsample_width,
            size_subsample_height=size_subsample_height,
            pad=pad,
            p=p,
            scrollable=scrollable,
            vertical_scroll_only=vertical_scroll_only,
            right_click_menu=right_click_menu,
            key=key,
            k=k,
            visible=visible,
            justification=justification,
            element_justification=element_justification,
            vertical_alignment=vertical_alignment,
            grab=grab,
            expand_x=expand_x,
            expand_y=expand_y,
            metadata=metadata,
            sbar_trough_color=sbar_trough_color,
            sbar_background_color=sbar_background_color,
            sbar_arrow_color=sbar_arrow_color,
            sbar_width=sbar_width,
            sbar_arrow_width=sbar_arrow_width,
            sbar_frame_color=sbar_frame_color,
            sbar_relief=sbar_relief,
        )

    def _setup_binds(self) -> None:
        # Update the layout when the widget is made visible. Needed for
        # widgets that are not visible on window creation.
        self._bind_layout_element_resize_to_layout_update()

    def _bind_layout_element_resize_to_layout_update(self) -> None:
        # Bind the elements in the layout to update the layout on resize
        for row in self.Rows:
            self._bind_elements_resize_to_layout_update(row)

    def _bind_elements_resize_to_layout_update(
        self, blocks: Iterable[Block]
    ) -> None:
        # Bind the elements to update the layout on resize
        # @function_details
        def update_grid_on_element_resize(event: tk.Event) -> None:
            """Update the Grid's layout when the element of a block
            resizes. Use as an event handler function for a tkinter
            widget binding.

            Args:
                event (tk.Event): The event that triggered this event
                    handler function.
            """
            # widget: tk.Widget = event.widget
            # lookup = widget_to_element_with_window(widget)
            # if not lookup or not lookup.element or not lookup.window:
            #     print("\twidget is not tracked by an active window")
            #     return
            # wrapper_element = lookup.element
            # print(
            #     "\tupdate_grid_on_element_resize called for element "
            #     f"with key: {wrapper_element.key}"
            # )

            try:
                with popup_on_error(Exception):
                    # Only update the Grid if it's visible and has a
                    # layout
                    if not self._is_visible_with_layout():
                        return

                    # widget: tk.Widget = event.widget
                    # lookup = widget_to_element_with_window(widget)
                    # if not lookup or not lookup.element:
                    #     print(
                    #         "\tresized event widget is not tracked by "
                    #         "an active window"
                    #     )
                    # else:
                    #     wrapper_element = lookup.element
                    #     print(
                    #         "\tresized event element key: "
                    #         f"{wrapper_element.key}."
                    #     )

                    if self.uniform_block_sizes and self.ParentForm.Resizable:
                        self._set_nonresizable_autosize_window()

                    self._update_layout()
            # Abort updating the grid on error
            except Exception:
                return

        for block in blocks:
            try:
                inner_element = block.inner_element
            except AttributeError:
                sg.PopupError(
                    (
                        "Error in layout. The wrapper element does not have an"
                        " inner element."
                    ),
                    (
                        "The processed layout should contain rows whose"
                        " original elements are wrapped in Block elements."
                    ),
                    "The offensive element = ",
                    f"{block}",
                    "The offensive layout = ",
                    self.Rows,
                    keep_on_top=True,
                    image=_random_error_emoji(),
                )
                continue

            try:
                inner_element.widget.bind(
                    "<<Resize>>",
                    update_grid_on_element_resize,
                    add="+",
                )
            except AttributeError:
                sg.PopupError(
                    (
                        "Error in layout. Failed to bind to an inner element's"
                        " widget"
                    ),
                    "The offensive inner element = ",
                    f"{inner_element}",
                    keep_on_top=True,
                    image=_random_error_emoji(),
                )
                continue

    def remove_all_block_paddings(self):
        for block in self.blocks:
            block_widget: tk.Widget = block.widget
            block_widget.pack_configure(padx=0, pady=0)

    def _update_internals(self, **kwargs) -> None:
        if self.uniform_block_sizes:
            self._set_nonresizable_autosize_window()

        self._update_layout(**kwargs)

    def _set_nonresizable_autosize_window(self):
        set_resizable_axis(window=self.ParentForm, x_axis=False, y_axis=False)
        set_window_to_autosize(self.ParentForm)

    def _popup_get_size_error(self, element: sg.Element):
        sg.PopupError(
            "Error when updating the Grid layout",
            "Unable to get the size of an element",
            "The offensive element = ",
            element,
            keep_on_top=True,
            image=_random_error_emoji(),
        )

    # @function_details
    def _update_layout(self, **kwargs) -> None:
        # Update the layout and vertically align the rows.

        self.ParentForm.refresh()

        # Only update the Grid if it's visible and has a layout
        if not self._is_visible_with_layout():
            return

        self._update_alignment_uniform_size_info()

        self._update_all_block_sizes()

    def _update_alignment_uniform_size_info(self) -> None:
        # Update the block column widths and the uniform block size

        # The height to set all blocks to when uniform block sizes are
        # used
        self.uniform_block_height = 1

        for block_col in self.block_columns:
            block_col.width = 1
            for block in block_col.blocks:
                try:
                    (
                        inner_element_width,
                        inner_element_height,
                    ) = get_element_size(block.inner_element)
                except GetWidgetSizeError:
                    self._popup_get_size_error(block.inner_element)
                    continue

                if inner_element_width > block_col.width:
                    block_col.width = inner_element_width
                if inner_element_height > self.uniform_block_height:
                    self.uniform_block_height = inner_element_height
                self._widget_to_block[block.inner_element.widget] = block

        # Get the width needed for uniform blocks
        self.uniform_block_width = max(
            {block_col.width for block_col in self.block_columns}
        )

        # print(
        #     "updated uniform size:"
        #     f" {self.uniform_block_width, self.uniform_block_height}"
        # )

        ...

    @property
    def block_columns(self) -> Tuple[BlockColumn, ...]:
        """Return the block columns for the Grid's layout.

        Returns:
            Tuple[BlockColumn, ...]: The block columns.
        """
        return tuple(self.block_col_num_to_block_col.values())

    @property
    def blocks(self) -> Iterator[Block]:
        """The blocks in the Grid's layout.

        Yields:
            Block: The next block in the Grid's layout.
        """
        for block_col in self.block_columns:
            for block in block_col.blocks:
                yield block

    def _update_all_block_sizes(self) -> None:
        self._update_block_sizes(self.blocks)

    def _update_block_sizes(self, blocks: Iterable[Block]) -> None:
        # Update the given block's sizes based on the current Grid
        # state. Only call this method after alignment info exists.

        # The alignment info for block columns doesn't exist
        if not self.block_col_num_to_block_col:
            sg.PopupError(
                "Error when updating the Grid's block sizes",
                "The alignment info for block columns doesn't exist",
                keep_on_top=True,
                image=_random_error_emoji(),
            )
            return

        for block in blocks:
            try:
                inner_element_width, inner_element_height = get_element_size(
                    block.inner_element
                )
            except GetWidgetSizeError:
                self._popup_get_size_error(block.inner_element)
                continue

            spacing_element = block.spacing_element

            try:
                spacing_widget_width, spacing_widget_height = get_element_size(
                    spacing_element
                )
            except GetWidgetSizeError:
                self._popup_get_size_error(spacing_element)
                continue

            spacing_widget: tk.Widget = spacing_element.widget

            # Set all blocks to the same size using padding
            if self.uniform_block_sizes:
                # Set the block's height to the uniform block height by
                # making the spacing widget's
                # height + padding = uniform_block_height
                height_padding = (
                    self.uniform_block_height - spacing_widget_height
                )

                # Error: the spacing widget is taller than the uniform
                # block height
                if height_padding < 0:
                    self._popup_alignment_error(block)
                    height_padding = 0

                # Use horizontal padding to expand the block's width to
                # the uniform block width
                right_padding = self.uniform_block_width - inner_element_width

                spacing_widget.pack_configure(
                    padx=(0, right_padding),
                    pady=(0, height_padding),
                )
            else:
                block_col = block.block_col

                try:
                    block_col_width = block_col.width
                except AttributeError:
                    sg.PopupError(
                        "Error when updating the Grid layout's block sizes",
                        "Unable to get the Block's block column width",
                        "The offensive block = ",
                        Block,
                        keep_on_top=True,
                        image=_random_error_emoji(),
                    )
                    continue

                # Use horizontal padding to expand the block's width to
                # the uniform block width
                right_padding = block_col_width - inner_element_width

                spacing_widget.pack_configure(padx=(0, right_padding))

    def _popup_alignment_error(self, block: Block) -> None:
        sg.PopupError(
            "Error when updating the Grid layout",
            "The spacing element is larger than the needed alignment padding",
            "The offensive block = ",
            block,
            keep_on_top=True,
            image=_random_error_emoji(),
        )

    def _is_visible_with_layout(self) -> bool:
        # Return True if the Grid is visible and has a layout.
        return True if self._is_visible() and self._layout_exists() else False

    def _layout_exists(self) -> bool:
        # Return True if the Grid has a layout.
        return True if self.Rows else False

    def _is_visible(self) -> bool:
        # Return True if the Grid is visible.
        return True if self.widget.winfo_ismapped() else False

    def add_row(self, *args: sg.Element) -> None:
        # Wrap the elements in Block elements along with an element for
        # spacing.
        block_wrapped_elements = tuple(
            Block(layout=[[element, sg.Image("", pad=0, size=(1, 1))]], pad=0)
            for element in args
        )

        super().add_row(*block_wrapped_elements)

        # Set the block column for each block
        for block_col_num, block in enumerate(block_wrapped_elements):
            # Get the block column for this block col number or create
            # it if it doesn't exist
            block_col = self.block_col_num_to_block_col.setdefault(
                block_col_num,
                BlockColumn(blocks=[], width=0, number=block_col_num),
            )

            # Add this block to the block column
            block_col.blocks.append(block)

            # Set the block's block column
            block.block_col = block_col

        # Refresh the window after adding the elements
        try:
            self.ParentForm.refresh()
        # No window and therefore no Grid widget yet
        except AttributeError:
            return

        # Update the layout and bind the resizing of the elements to
        # update the layout.
        if self._is_visible_with_layout():
            self._update_internals()
            self._bind_elements_resize_to_layout_update(block_wrapped_elements)

    AddRow = add_row


@dataclass
class BlockColumn:
    blocks: Blocks
    width: int
    number: int


class Block(sg.Column):
    """A block used in a Grid's layout."""

    def __init__(
        self,
        layout,
        background_color=None,
        size=(None, None),
        s=(None, None),
        size_subsample_width=1,
        size_subsample_height=2,
        pad=None,
        p=None,
        scrollable=False,
        vertical_scroll_only=False,
        right_click_menu=None,
        key=None,
        k=None,
        visible=True,
        justification=None,
        element_justification=None,
        vertical_alignment=None,
        grab=None,
        expand_x=None,
        expand_y=None,
        metadata=None,
        sbar_trough_color=None,
        sbar_background_color=None,
        sbar_arrow_color=None,
        sbar_width=None,
        sbar_arrow_width=None,
        sbar_frame_color=None,
        sbar_relief=None,
    ):
        self.block_col: Optional[BlockColumn] = None

        super().__init__(
            layout=layout,
            background_color=background_color,
            size=size,
            s=s,
            size_subsample_width=size_subsample_width,
            size_subsample_height=size_subsample_height,
            pad=pad,
            p=p,
            scrollable=scrollable,
            vertical_scroll_only=vertical_scroll_only,
            right_click_menu=right_click_menu,
            key=key,
            k=k,
            visible=visible,
            justification=justification,
            element_justification=element_justification,
            vertical_alignment=vertical_alignment,
            grab=grab,
            expand_x=expand_x,
            expand_y=expand_y,
            metadata=metadata,
            sbar_trough_color=sbar_trough_color,
            sbar_background_color=sbar_background_color,
            sbar_arrow_color=sbar_arrow_color,
            sbar_width=sbar_width,
            sbar_arrow_width=sbar_arrow_width,
            sbar_frame_color=sbar_frame_color,
            sbar_relief=sbar_relief,
        )

    @property
    def inner_element(self) -> sg.Element:
        return self.Rows[0][0]

    @property
    def spacing_element(self) -> sg.Element:
        return self.Rows[0][1]


Blocks: TypeAlias = List[Block]


class ImageBase(sg.Image, SuperElement):
    """ImageBase Element - Image Element with extra capabilities. Show
    an image in the window. Should be a GIF or a PNG only.
    """

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
        size_match_element_key=None,
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
        :type background_color:         (str)
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
        :param size_match_element_key:  The key of the element to size match the image to.
        :type size_match_element_key:   (str)
        :param size_match_element_type: The type of the closest Element to size match will be this type.
        :type size_match_element_type:  (Type[sg.Element])
        """  # noqa: E501

        self.size_match = size_match

        self._size_match_element_key = size_match_element_key

        self.size_match_element = size_match_element

        self.size_match_element_type = size_match_element_type

        # Track if auto size matching a target element is set up
        self._auto_size_matching = False

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

    def _update_internals(self) -> None:
        self._update_image()

    # @function_details
    def _update_image(
        self, source: Union[str, bytes, None, EllipsisType] = ...
    ) -> None:
        """Update the image with the given source. If size matching is
        on, a size-matched version of the source will be used.

        Args:
            source (Union[str, bytes, None], optional): A filename or a
            base64 bytes. Defaults to ... .
        """
        window = self.ParentForm

        new_source = self._determine_new_source(source)

        if window and self.size_match:
            # Look up the element with the given key for the size match
            # target
            if (
                self.size_match_element is None
                and self._size_match_element_key
            ):
                if self._size_match_element_key in window.key_dict:
                    self.size_match_element = window[
                        self._size_match_element_key
                    ]
                else:
                    sg.PopupError(
                        "Invalid key for size match element of this Image.",
                        (
                            "The window with this Image does not contain an"
                            " element with the key"
                            f" {self._size_match_element_key}."
                        ),
                        "The closest element will be used instead.",
                        keep_on_top=True,
                        image=_random_error_emoji(),
                    )

            size_matched_pairs = setup_height_matched_images(
                image_file_or_bytes=new_source,
                window=window,
                image_element=self,
                size_match_element=self.size_match_element,
                closest_element_type=self.size_match_element_type,
            )

            # Save the size match element as the closest element
            if self.size_match_element is None:
                self.size_match_element = size_matched_pairs.get(self, None)

            # Set up auto size matching to the size match element
            if (
                not self._auto_size_matching
                and self.size_match_element is not None
            ):
                self._set_up_auto_size_match_element(self.size_match_element)
                self._auto_size_matching = True
        else:
            self.update(source=new_source)

    def _set_up_auto_size_match_element(self, element: sg.Element) -> None:
        """Set up a binding so that this element updates when the size
        match element resizes.

        Args:
            element (sg.Element): The element to size match.
        """

        # @function_details
        def update_image_on_element_resize(event: tk.Event) -> None:
            # Only handle resizes if the Image's widget is mapped
            if self.widget.winfo_ismapped():
                self._update_internals()

        # Make the Image update size matching whenever its element to
        # size match resizes
        element.widget.bind(
            "<<Resize>>", update_image_on_element_resize, add="+"
        )

    def _determine_new_source(
        self, source: Union[str, bytes, None, EllipsisType]
    ) -> Union[str, bytes, None]:
        """Return the new source based on the argument and any
        default(s).

        Args:
            source (Union[str, bytes, None, EllipsisType]): A filename,
                a base64 bytes, None, or ... (no given source).

        Returns:
            Union[str, bytes, None]:  The new source.
        """
        return source if source is not ... else self.Source


class Image(ImageBase):
    """Image Element with size-matching functionality - show an image in
    the window. Should be a GIF or a PNG only.
    """

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
        size_match_element_key=None,
        size_match_element_type=sg.Element,
    ) -> None:
        """
        :param source:                  A filename or a base64 bytes. Will automatically detect the type and fill in filename or data for you.
        :type source:                   str | bytes | EllipsisType | None
        :param filename:                image filename if there is a button image. GIFs and PNGs only.
        :type filename:                 str | EllipsisType | None
        :param data:                    Raw or Base64 representation of the image to put on button. Choose either filename or data
        :type data:                     bytes | str | EllipsisType | None
        :param background_color:        color of background
        :type background_color:         (str)
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
        :param size_match_element_key:  The key of the element to size match the image to.
        :type size_match_element_key:   (str)
        :param size_match_element_type: The type of the closest Element to size match will be this type.
        :type size_match_element_type:  (Type[sg.Element])
        """  # noqa: E501
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
            size_match_element_key=size_match_element_key,
            size_match_element_type=size_match_element_type,
        )

    def _post_init(self):
        self._original_source = self.Source

    def _setup_binds(self) -> None:
        # Update the image when the widget is made visible. Needed for
        # widgets that are not visible on window creation.
        self.widget.bind("<Map>", lambda e: self._update_image(), add="+")

    update_image = ImageBase._update_image

    def _determine_new_source(
        self, source: Union[str, bytes, None, EllipsisType]
    ) -> Union[str, bytes, None]:
        return source if source is not ... else self._original_source


class InfoImage(Image):
    """InfoImage Element with size-matching functionality. Displays an
    image with an info icon as the default image. Image should be a GIF
    or a PNG only.
    """

    _source_default: Union[
        str, bytes, None
    ] = b"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"  # noqa: E501


class EmptyImage(Image):
    """EmptyImage Element with size-matching functionality. Displays an
    transparent image as the default image. Image should be a GIF or a
    PNG only.
    """

    _source_default: Union[
        str, bytes, None
    ] = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAANSURBVBhXY2BgYGAAAAAFAAGKM+MAAAAAAElFTkSuQmCC"  # noqa: E501


class ToggleImage(ImageBase):
    """ToggleImage Element with size-matching functionality - show an
    image that can be toggled in the window. Toggle On and Off images
    should be a GIF or a PNG only.
    """

    _toggle_on_source_default: Union[str, bytes, None] = None
    _toggle_off_source_default: Union[str, bytes, None] = None

    def __init__(
        self,
        start_toggled_on: bool,
        toggle_on_source: Union[str, bytes, None, EllipsisType] = ...,
        toggle_off_source: Union[str, bytes, None, EllipsisType] = ...,
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
        size_match_element_key=None,
        size_match_element_type: Type[sg.Element] = sg.Element,
    ):
        """
        :param start_toggled_on:        Set to True if you want this element to start toggled on.
        :type start_toggled_on:         bool
        :param toggle_on_source:        A filename or a base64 bytes for the toggle on image. Will automatically detect and handle the type.
        :type toggle_on_source:         str | bytes | None
        :param toggle_off_source:       A filename or a base64 bytes for the toggle off image. Will automatically detect and handle the type.
        :type toggle_off_source:        str | bytes | None
        :param source:                  A filename or a base64 bytes. Will automatically detect the type and fill in filename or data for you.
        :type source:                   str | bytes | None
        :param background_color:        color of background
        :type background_color:         (str)
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
        :param size_match_element_key:  The key of the element to size match the image to.
        :type size_match_element_key:   (str)
        :param size_match_element_type: The type of the closest Element to size match will be this type.
        :type size_match_element_type:  (Type[sg.Element])
        """  # noqa: E501

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
            self.toggle_on_source
            if self.is_toggled_on
            else self.toggle_off_source
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
            size_match_element_key=size_match_element_key,
            size_match_element_type=size_match_element_type,
        )

    def _setup_binds(self) -> None:
        # Remove existing event bindings
        self._unbind_all()

        # Set up PySimpleGUI events on left click release if they're
        # enabled for this element
        if self.EnableEvents:
            self.bind("<ButtonRelease-1>", "")

        # Toggle the element on left click release
        self.widget.bind("<ButtonRelease-1>", lambda e: self.toggle(), add="+")

        # Update the image when the widget is made visible. Needed for
        # widgets that are not visible on window creation.
        self.widget.bind("<Map>", lambda e: self.update_toggle_images())

    def toggle(self) -> None:
        """Toggle the image."""
        self.is_toggled_on ^= True
        self.update_toggle_images()

    def set_toggle(self, state: bool) -> None:
        """Set the toggle state of the element.

        Args:
            state (bool): If True, the element will be toggled on. Else,
                it will be toggled off.
        """
        self.is_toggled_on = state
        self.update_toggle_images()

    def update_toggle_images(
        self,
        toggle_on_source: Union[str, bytes, None, EllipsisType] = ...,
        toggle_off_source: Union[str, bytes, None, EllipsisType] = ...,
    ) -> None:
        """Update the sources for the toggle images and update the image
        with a new source based on the current toggle state. If size
        matching is on, a size-matched version of the new source will
        be used.

        Args:
            toggle_on_source (Union[str, bytes, None], optional): A
                filename or a base64 bytes for the toggle on image. Will
                automatically detect and handle the type. Defaults to
                ... .
            toggle_off_source (Union[str, bytes, None], optional): A
                filename or a base64 bytes for the toggle off image.
                Will automatically detect and handle the type. Defaults
                to ... .
        """

        if toggle_on_source is not ...:
            self.toggle_on_source = toggle_on_source

        if toggle_off_source is not ...:
            self.toggle_off_source = toggle_off_source

        self._update_image()

    def _determine_new_source(
        self, source: Union[str, bytes, None, EllipsisType]
    ) -> Union[str, bytes, None]:
        if source is not ...:
            return source
        else:
            # Return the source for the current toggle state
            return (
                self.toggle_on_source
                if self.is_toggled_on
                else self.toggle_off_source
            )


class FancyCheckbox(ToggleImage):
    """FancyCheckbox Element with size-matching functionality. Displays
    a checkbox with fancy checked/unchecked default images. Checked and
    unchecked images should be a GIF or a PNG only.
    """

    _toggle_on_source_default = b"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"  # noqa: E501
    _toggle_off_source_default = b"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"  # noqa: E501

    @property
    def checked(self) -> bool:
        """The toggle state of the checkbox. True if the checkbox is
        checked."""
        return self.is_toggled_on

    @checked.setter
    def checked(self, is_checked: bool) -> None:
        self.set_toggle(is_checked)


class FancyToggle(ToggleImage):
    """FancyToggle Element with size-matching functionality. Displays a
    toggle button with fancy on/off default images. Toggle On and Off
    images should be a GIF or a PNG only.
    """

    _toggle_off_source_default = b"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"  # noqa: E501
    _toggle_on_source_default = b"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"  # noqa: E501


def save_toggle_state(toggle_element: ToggleImage) -> None:
    """Save the toggle element's toggle state to the config file.

    Args:
        toggle_element (ToggleImage): The toggle element whose toggle
            state is to be saved.
    """
    _save_binary_state(
        element=toggle_element, state=toggle_element.is_toggled_on
    )


def save_checkbox_state(checkbox_element: FancyCheckbox) -> None:
    """Save the checkbox's checked state to the config file.

    Args:
        checkbox_element (FancyCheckbox): The checkbox element whose
            checked state is to be saved.
    """
    _save_binary_state(
        element=checkbox_element, state=checkbox_element.checked
    )


def _save_binary_state(element: sg.Element, state: bool) -> None:
    """Save an element's binary state to the config file.

    Args:
        element (sg.Element): An element with a binary state.
        state (bool): The state of the element.
    """
    sg.user_settings_set_entry(
        element.key,
        state,
    )


def popup_tracked(
    *args: Any,
    popup_fn: Callable[..., Tuple[sg.Window, Optional[str]]],
    window_tracker: WindowTracker,
    **kwargs: Any,
) -> sg.Window:
    """Pop up a tracked window.

    Args:
        popup_fn (Popup_Callable): The function to call to create a
            popup.
        window_tracker (WindowTracker): Tracker for possibly active
            windows which the created popup will be added to.
    """
    popup_window, _ = popup_fn(*args, **kwargs)

    window_tracker.track_window(popup_window)

    return popup_window


# Taken from Pysimplegui.popup() and modified
def popup(  # noqa: C901
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
    """  # noqa: E501

    if not args:
        args_to_print: Sequence[Any] = [""]
    else:
        args_to_print = args
    if line_width is not None:
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
        # always convert message to string
        message = str(message)
        if message.count("\n"):
            # if there are line breaks, wrap each segment separately
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
        longest_line_len = max([len(line) for line in message.split("\n")])
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
    """  # noqa: E501
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
        # Always convert message to string
        message = str(message)
        longest_line_len = max([len(line) for line in message.split("\n")])
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


# Taken from Pysimplegui._GetNumLinesNeeded().
# Needed by popup_scrolled().
# ========================= GetNumLinesNeeded =========================#
# Helper function for determining how to wrap text                     #
# =====================================================================#
def GetNumLinesNeeded(text: str, max_line_width: int) -> int:
    """Get the number of lines needed to wrap the text.

    Args:
        text (str): The text that needs the number of lines to use when
            wrapping.
        max_line_width (int): The max width of each line that will be
            used during text wrapping.

    Returns:
        int: The number of lines needed to wrap the text.
    """
    if max_line_width == 0:
        return 1
    lines = text.split("\n")
    # num_lines = len(lines)  # number of original lines of text
    # max_line_len = max([len(line) for line in lines])  # longest line
    lines_used = []
    for line in lines:
        # fancy math to round up
        lines_used.append(
            len(line) // max_line_width + (len(line) % max_line_width > 0)
        )
    total_lines_needed = sum(lines_used)
    return total_lines_needed


# Taken from Pysimplegui.DummyButton() and modified.
# ---------------  Dummy BUTTON Element lazy function  --------------- #
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
    """  # noqa: E501
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


class ModalWindowManager:
    """A manager for tracking modal windows in order to remodal a
    previous window when a more recent one is closed.
    """

    def __init__(self) -> None:
        self._modal_window_stack: List[sg.Window] = []

    def track_modal_window(self, window: sg.Window) -> Tuple[sg.Window, bool]:
        """Add a modal window as the most recent tracked modal window.

        The given window will be ignored if it's a closed window.

        Args:
            window (sg.Window): A modal window. If a non-modal window is
                added, it will be changed into a modal window.

        Returns:
            Tuple[sg.Window, bool]: A tuple with the window and True if
                tracking succeeded, False otherwise.
        """

        # Ignore the window if it's already the most recent tracked
        # modal window
        if self._modal_window_stack and window is self._modal_window_stack[-1]:
            return (window, True)

        if not window.is_closed():
            window.make_modal()

        # Add the window as the most recent tracked modal window.
        self._modal_window_stack.append(window)
        return (window, True)

    def update(self) -> None:
        """Set as modal the most recent non-closed tracked modal
        window.
        """

        stack_changed = False

        # Clear closed modal windows from the top of the modal window
        # tracking stack
        while (
            self._modal_window_stack
            and self._modal_window_stack[-1].was_closed()
        ):
            self._modal_window_stack.pop()
            stack_changed = True

        # Restore as modal the most recent non-closed tracked modal
        # window
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


def set_up_resize_event() -> None:
    """Set up the <<Resize>> virtual event for all widgets."""
    # Make a temporary window to ensure that tkroot exists
    _ = Window("", layout=[[sg.Text()]], finalize=True, alpha_channel=0)

    _.TKroot.event_add("<<Resize>>", "None")
    _.TKroot.bind_all("<Configure>", forward_resize_event, add="+")

    # Read the window once before closing it to avoid the bug where
    # closing the 1st finalized window without reading it causes future
    # windows to not use the global icon in the taskbar.
    _.read(0)
    _.close()


# @function_details
def forward_resize_event(event: tk.Event) -> None:
    """Generates a <<Resize>> virtual event if the passed <Configure>
    event indicates a widget resize.

    Args:
        event (tk.Event): A tkinter <Configure> event.
    """
    valid_event_type = tk.EventType.Configure

    if event.type != valid_event_type:
        sg.PopupError(
            (
                "Warning: forward_resize_event() was passed an event of the"
                " wrong type."
            ),
            f"The event's type must be <{valid_event_type.name}>.",
            "The offensive event = ",
            event,
            keep_on_top=True,
            image=_random_error_emoji(),
        )
        return

    # The widget for the event cannot be retrieved. Ignore this event.
    try:
        widget = get_event_widget(event)
    except WidgetNotFoundError:
        return

    try:
        has_widget_resized = widget_resized(widget)
    except GetWidgetSizeError:
        sg.PopupError(
            "Warning: Error while determining if the event's widget resized.",
            "The offensive widget = ",
            widget,
            keep_on_top=True,
            image=_random_error_emoji(),
        )
        return

    if has_widget_resized:
        # print(f"forwarding resize event.")
        # lookup = widget_to_element_with_window(widget)
        # if not lookup or not lookup.element or not lookup.window:
        #     print("\tevent widget is not tracked by an active window")
        #     ...
        # else:
        #     wrapper_element = lookup.element
        #     print(
        #         f"\tevent element key: {wrapper_element.key}. size:"
        #         f" {event.width, event.height}."
        #     )

        widget.event_generate(
            "<<Resize>>",
        )
