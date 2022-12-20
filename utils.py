#!/usr/bin/env python3

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

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import (  # type: ignore
        Connection as PipeConnection,
    )


if TYPE_CHECKING:
    from types import FrameType


def get_settings_file_path() -> str:
    return str(sg.user_settings_object().full_filename)


def function_details(func: Callable) -> Callable:
    """Decorate a function to also prints the function and its arguments
    when it's called.

    Args:
        func (Callable): A function.

    Returns:
        Callable: The decorated function.
    """

    def inner_func(*args, **kwargs):
        func_args = inspect.signature(func).bind(*args, **kwargs).arguments
        func_args_str = ", ".join(
            map("{0[0]} = {0[1]!r}".format, func_args.items())
        )
        print(f"{func.__module__}.{func.__qualname__} ( {func_args_str} )")
        return func(*args, **kwargs)

    return inner_func


def get_event_widget(event: tk.Event) -> Optional[tk.Widget]:
    """Return the event's widget.

    Args:
        event (tk.Event): An event.

    Returns:
        Optional[tk.Widget]: The event's widget or None if it's not
            found.
    """
    # widget = event.widget
    widget = event.widget

    # Ensure a widget
    try:
        widget.winfo_ismapped()
    # A widget name was found
    except AttributeError:
        widget = widget_name_to_widget(widget)
    return widget


def widget_name_to_widget(widget_name: str) -> Optional[tk.Widget]:
    """Return the widget in an active window based on a widget's Tcl
    name.

    Args:
        widget_name (str): The Tcl name of a widget.

    Returns:
        Optional[tk.Widget]: A widget or None if it's not found.
    """
    for window in sg.Window._active_windows:
        with suppress(KeyError):
            widget = window.TKroot.nametowidget(widget_name)
            return widget
    return None


def refresh_idletasks(window: sg.Window) -> sg.Window:
    """Refreshes the window by calling tkroot.update_idletasks().
    Call this when you want all tkinter idle callbacks to be processed.
    This will update the display of windows before it next idles but not
    process events caused by the user.

    Some tasks in updating the display, such as resizing and redrawing
    widgets, are called idle tasks because they are usually deferred
    until the application has finished handling events and has gone back
    to the main loop to wait for new events.

    Args:
        window (sg.Window): The window to refresh and process idle tasks
            for.

    Returns:
        sg.Window: The window so that calls can be easily "chained".
    """
    if window.TKrootDestroyed:
        return window
    try:
        window.TKroot.update_idletasks()
    except Exception:
        pass
    return window


def resize_window_relative_to_screen(
    window: sg.Window,
    width_factor: Union[float, int],
    height_factor: Union[float, int],
) -> None:
    """Resize the window by specifying the width and height relative to
    the screen size.

    Args:
        window (sg.Window): The window to resize.
        width_factor (Union[float, int]): The proportion of the screen's
            width to make the window.
            E.g., 0.2 is 20% of the screen's width.
        height_factor (Union[float, int]): The proportion of the
            screen's height to make the window. E.g., 0.2 is 20% of the
            screen's height.
    """

    screen_width, screen_height = sg.Window.get_screen_size()

    window_width = int(screen_width * width_factor)
    window_height = int(screen_height * height_factor)

    window.size = (window_width, window_height)

    window.refresh()

    window.move_to_center()


def vertically_align_elements(window: sg.Window, keys: Iterable[str]) -> None:
    """Vertically align the elements.

    Args:
        window (sg.Window): The window the elements are in.
        keys (Iterable[str]): The keys for the elements to set to the
            same width.
    """
    elements: Iterator[sg.Element] = (window[key] for key in keys)

    elements_with_width_pad: List[Tuple[sg.Element, int, Pad]] = []

    # Get a list with each element paired with its width(including padx)
    # and pad
    try:
        for element in elements:
            true_element_size_init_pad = get_element_true_size(
                element, init_pad=True
            )[0]
            original_pad = get_original_pad(element)
            elements_with_width_pad.append(
                (element, true_element_size_init_pad, original_pad)
            )
    except GetWidgetSizeError:
        popup_get_size_error(
            "Error when vertically aligning elements", element=element
        )
        return

    longest_width_element_info = max(
        elements_with_width_pad, key=itemgetter(1)
    )
    longest_width = longest_width_element_info[1]

    # Vertically align using right padding
    for element, width, pad in elements_with_width_pad:
        # New right padding = original right padding + difference needed
        # for alignment
        extra_right_padding = longest_width - width
        right_padding = extra_right_padding + pad.right
        element.widget.pack_configure(padx=(pad.left, right_padding))


def get_placement_info(target: Union[sg.Element, tk.Widget]) -> Dict[str, Any]:
    """Return the placement information for an Element or tkinter widget
    as a dict.

    Args:
        target (Union[sg.Element, tk.Widget]): An Element or tkinter
            widget.

    Raises:
        TypeError: target argument is not an Element or tkinter widget.

    Returns:
        Dict[str, Any]: The placement information.
    """
    if isinstance(target, sg.Element):
        widget = target.widget
    elif isinstance(target, tk.Widget):
        widget = target
    else:
        raise TypeError("target must be an Element or a tkinter widget")

    return widget.info()


def get_pad(target: Union[sg.Element, tk.Widget]) -> Pad:
    """Get the padding of the element/widget.

    Args:
        target (Union[sg.Element, tk.Widget]): The element/widget to get
            the padding for.

    Returns:
        Pad: The padding.
    """
    info = get_placement_info(target)
    padx = info["padx"]
    pady = info["pady"]
    return Pad(
        *process_pad_into_2_tuple(padx), *process_pad_into_2_tuple(pady)
    )


def get_original_pad(element: sg.Element) -> Pad:
    """Return the original padding for the Element that's set by
    PySimpleGUI.

    Args:
        element (sg.Element): The element.

    Returns:
        Pad: The original padding.
    """
    return process_pad(element.Pad)


@dataclass
class Pad:
    """The padding of an element."""

    left: int
    right: int
    top: int
    bottom: int

    def as_tuple(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Return the pad as a tuple ((left, right), (top, bottom)).

        Returns:
            Tuple[Tuple[int, int], Tuple[int, int]]: The pad.
        """
        return (self.left, self.right), (self.top, self.bottom)


def process_pad_into_2_tuple(pad) -> Tuple:
    """Return the padding (x or y) as a tuple.

    Args:
        pad (Union[int, Tuple[int, int]]): Padx as an int or (int, int).

    Raises:
        TypeError: Pad parameter must be a 2-tuple or a number

    Returns:
        Tuple: The padding.
    """
    # It's a 2-tuple
    with suppress(TypeError):
        _, __ = pad
        _ + 1
        __ + 1
        return pad

    # It's a number
    try:
        pad + 1
        return pad, pad
    except TypeError:
        raise TypeError(
            "parameter must be a 2-tuple of numbers or a number"
        ) from None


def process_pad(pad) -> Pad:
    """Return the padding as a tuple ((left, right), (top, bottom)). If
    no padding exists, the default Element padding will be returned.

    Args:
        pad (Union[None, int, Tuple[int, int], Tuple[Tuple[int, int],
            Tuple[int, int]]]): The pad.

    Returns:
        Pad: The processed pad.
    """
    # No padding set when creating the Element. Use the default element
    # padding.
    if pad is None:
        pad = sg.DEFAULT_ELEMENT_PADDING

    # Turn pad into a 2-tuple
    pad = process_pad_into_2_tuple(pad)

    # Turn padx and pady each into a 2-tuple and make a Pad out of them
    return Pad(
        *process_pad_into_2_tuple(pad[0]), *process_pad_into_2_tuple(pad[1])
    )


def get_element_true_size(
    element: sg.Element, init_pad=False
) -> Tuple[int, int]:
    """Return the true element's size which includes the external
    padding.

    Args:
        element (sg.Element): The element.
        init_pad (bool, optional): If True, the size will be calculated
            using the initial padding for the element instead of the
            current padding. Defaults to False.

    Returns:
        Tuple[int, int]: The element's true size.
    """
    try:
        width, height = get_element_size(element)
    except GetWidgetSizeError:
        popup_get_size_error(element=element)
        raise

    pad = get_original_pad(element) if init_pad else get_pad(element)

    return (width + pad.left + pad.right, height + pad.top + pad.bottom)


def get_element_size(element: sg.Element) -> Tuple[int, int]:
    """Return the size of an Element's widget in Pixels.  Care must be
    taken as some elements use characters to specify their size but will
    return pixels when calling this method.

    Args:
        element (sg.Element): An Element.

    Raises:
        GetWidgetSizeError: Error while getting the size of the widget
            for this element.

    Returns:
        Tuple[int, int]: Width and height of the element's widget as
            reported by the tkinter windows manager.
    """
    widget = element.widget
    return get_widget_size(widget)


class GetWidgetSizeError(Exception):
    """Error while getting the size of the widget."""


@dataclass
class WidgetSize:
    width: int
    height: int


def widget_resized(widget: tk.Widget) -> bool:
    """Return whether the widget has resized by comparing the last size
    and the current size returned by the tkinter windows manager.

    Args:
        widget (tk.Widget): The widget to check for resizing.

    Raises:
        GetWidgetSizeError: Error while getting the size of the widget.

    Returns:
        bool: True if widget has resized.
    """
    # lookup = widget_to_element_with_window(widget)
    # if not lookup or not lookup.element or not lookup.window:
    #     print(
    #         "\tchecking if widget resized. widget is not tracked by "
    #         "an active window"
    #     )
    # else:
    #     wrapper_element = lookup.element
    #     print(
    #         "\tchecking if widget resized for element w/ key:"
    #         f" {wrapper_element.key}"
    #     )

    last_size = get_widget_last_size(widget)

    widget_width, widget_height = get_widget_size(widget)

    # No last size for widget
    if last_size is None:
        return True
    # Widget resized. Update the last size.
    elif widget_width != last_size.width or widget_height != last_size.height:
        last_size.width = widget_width
        last_size.height = widget_height
        return True
    # Widget has not resized
    else:
        return False


def get_widget_last_size(widget: tk.Widget) -> Optional[WidgetSize]:
    """Return the last size of the widget.

    If there's no last size for the widget, one will be created using
    the current size for future calls and None will be returned.

    Args:
        widget (tk.Widget): The widget.

    Raises:
        GetWidgetSizeError: Error while getting the size of the widget.

    Returns:
        Optional[WidgetSize]: The last size of the widget.
    """
    last_size_attr = "_last_size"
    last_size: Optional[WidgetSize] = getattr(widget, last_size_attr, None)

    # No last size attribute yet. Add the last size attribute to the
    # widget with the current size.
    if last_size is None:
        widget_width, widget_height = get_widget_size(widget)

        last_size = WidgetSize(width=widget_width, height=widget_height)
        setattr(
            widget,
            last_size_attr,
            last_size,
        )

    return last_size


def get_widget_size(widget: tk.Widget) -> Tuple[int, int]:
    """Return the size of a widget in Pixels.

    Args:
        widget (tk.Widget): A widget.

    Raises:
        GetWidgetSizeError: Error while getting the size of the widget.

    Returns:
        Tuple[int, int]: Width and height of the widget as reported by
            the tkinter windows manager.
    """
    try:
        w = widget.winfo_width()
        h = widget.winfo_height()
    except Exception as e:
        raise GetWidgetSizeError(
            f"Error getting size of widget: {widget}"
        ) from e
    return w, h


def popup_get_size_error(*lines: str, element: sg.Element = None) -> None:
    """Pop up an error window due to failure when getting the size of an
    element.

    Args:
        *lines (str): Variable length list of strings to print first.
        element (sg.Element, optional): An Element. Defaults to None.
    """
    if element is not None:
        offending_element_text = f"The offensive Element = \n{element}"
    else:
        offending_element_text = ""

    sg.PopupError(
        *lines,
        "Unable to get the size of an element",
        offending_element_text,
        keep_on_top=True,
        image=_random_error_emoji(),
    )


def _random_error_emoji():
    c = random.choice(sg.EMOJI_BASE64_SAD_LIST)
    return c


def set_resizable_axis(window: sg.Window, x_axis: bool, y_axis: bool) -> None:
    window.Resizable = True if x_axis or y_axis else False
    window.TKroot.resizable(x_axis, y_axis)


def set_window_autosize(window: sg.Window) -> None:
    window.TKroot.geometry("")


def refresh_window(element: sg.Element) -> None:
    """Refresh the window of the given Element.

    Args:
        element (sg.Element): An element.
    """
    element.ParentForm.refresh()


def convert_rows_to_columns_for_elements(
    rows: Sequence[Sequence[sg.Element]], fill_element_type: Type[sg.Element]
) -> List[List[sg.Column]]:
    """Convert a series of rows into a list of columns.

    Args:
        rows (Sequence[Sequence[sg.Element]]): Rows with elements.
        fill_element_type (Type[sg.Element]): The type of element that's
            used to filling in column rows when the given rows are of
            unequal length.

    Returns:
        List[sg.Column]: A list of PySimpleGUI columns.
    """
    # Group the elements into columns
    column_grouped_elements_list = zip_longest(*rows, fillvalue=None)

    # Make a list of PySimpleGUI Column elements from the column grouped
    # elements
    columns = []
    for column_elements in column_grouped_elements_list:
        # Replace None values with elements of the specified type
        column_layout = [
            [element if element is not None else fill_element_type()]
            for element in column_elements
        ]
        column = sg.Column(column_layout, pad=(0, 0))
        columns.append(column)

    return [columns]


def ensure_valid_layout(layout: Sequence[Sequence[sg.Element]]) -> None:
    """Ensure that the layout is valid (an Iterable[Iterable[Element]]).

    Args:
        layout (Sequence[Sequence[sg.Element]]): The layout to check.
    """
    try:
        iter(layout)
    except TypeError:
        sg.PopupError(
            "Error in layout",
            "Your layout is not an iterable (e.g. a list)",
            "Instead of a list, the type found was {}".format(type(layout)),
            "The offensive layout = ",
            layout,
            keep_on_top=True,
            image=_random_error_emoji(),
        )
        return

    for row in layout:
        try:
            iter(row)
        except TypeError:
            sg.PopupError(
                "Error in layout",
                "Your row is not an iterable (e.g. a list)",
                "Instead of a list, the type found was {}".format(type(row)),
                "The offensive row = ",
                row,
                "This item will be stripped from your layout",
                keep_on_top=True,
                image=_random_error_emoji(),
            )
            continue
        for element in row:
            if type(element) == list:
                sg.PopupError(
                    "Error in layout",
                    "Layout has a LIST instead of an ELEMENT",
                    "This means you have a badly placed ]",
                    "The offensive list is:",
                    element,
                    "This list will be stripped from your layout",
                    keep_on_top=True,
                    image=_random_error_emoji(),
                )
                continue
            elif callable(element) and not isinstance(element, sg.Element):
                sg.PopupError(
                    "Error in layout",
                    "Layout has a FUNCTION instead of an ELEMENT",
                    "This likely means you are missing () from your layout",
                    "The offensive list is:",
                    element,
                    "This item will be stripped from your layout",
                    keep_on_top=True,
                    image=_random_error_emoji(),
                )
                continue
            if element.ParentContainer is not None:
                sg.warnings.warn(
                    (
                        "*** AN ELEMENT IN YOUR LAYOUT IS ALREADY IN USE! Once"
                        " placed in a layout, an element cannot be used in"
                        " another layout. ***"
                    ),
                    UserWarning,
                )
                sg.PopupError(
                    "Error in layout",
                    "The layout specified has already been used",
                    (
                        'You MUST start with a "clean", unused layout every'
                        " time you create a window"
                    ),
                    "The offensive Element = ",
                    element,
                    "and has a key = ",
                    element.Key,
                    "This item will be stripped from your layout",
                    (
                        "Hint - try printing your layout and matching the IDs"
                        ' "print(layout)"'
                    ),
                    keep_on_top=True,
                    image=_random_error_emoji(),
                )
                continue
