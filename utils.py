#!/usr/bin/env python3
# mypy: disable-error-code=union-attr

from __future__ import annotations

import base64
import inspect
import io
import platform
import random
import re
import sys
import time
import tkinter as tk
import traceback
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from itertools import islice, zip_longest
from multiprocessing.connection import Connection
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
from codetiming import Timer, TimerError

from loggers import logger

if platform.system() == "Windows":
    from multiprocessing.connection import PipeConnection  # type: ignore
else:
    from multiprocessing.connection import (  # type: ignore
        Connection as PipeConnection,
    )


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


def get_event_widget(event: tk.Event) -> tk.Widget:
    """Return the event's widget.

    Args:
        event (tk.Event): An event.

    Raises:
        WidgetNotFoundError: Event's widget is None.

    Returns:
        tk.Widget: The event's widget.
    """
    widget = event.widget

    if widget is None:
        raise WidgetNotFoundError("Event's widget is None.")

    # It's a widget
    with suppress(AttributeError):
        widget.winfo_ismapped()
        return widget

    # Not a widget. A widget name was found instead.
    widget = widget_name_to_widget(widget)
    return widget


def widget_name_to_widget(widget_name: str) -> tk.Widget:
    """Return the widget in an active window based on a widget's Tcl
    name.

    Args:
        widget_name (str): The Tcl name of a widget.

    Raises:
        WidgetNotFoundError: Unable to lookup a widget based on the
            given widget name.

    Returns:
        tk.Widget: A widget.
    """
    for window in sg.Window._active_windows:
        with suppress(KeyError):
            widget = window.TKroot.nametowidget(widget_name)
            return widget
    raise WidgetNotFoundError(
        "Unable to lookup a widget based on the given widget name."
    )


class UpdateIdleTasksError(Exception):
    """An error occurred while updating tkinter idle tasks."""


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

    Raises:
        UpdateIdleTasksError: An error occurred while updating tkinter
            idle tasks.

    Returns:
        sg.Window: The window so that calls can be easily "chained".
    """
    if window.TKrootDestroyed:
        return window
    try:
        window.TKroot.update_idletasks()
    except Exception as e:
        raise UpdateIdleTasksError(
            "An error occurred while updating tkinter idle tasks."
        ) from e

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
    for element in elements:
        true_element_size_init_pad = get_element_true_size(
            element, init_pad=True
        )[0]
        original_pad = get_element_original_pad(element)
        elements_with_width_pad.append(
            (element, true_element_size_init_pad, original_pad)
        )

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


class WidgetNotFoundError(Exception):
    """The widget was not found for an element."""


def get_element_placement_info(element: sg.Element) -> Dict:
    """Return the placement information for an Element or tkinter widget
    as a dict.

    Args:
        target (Union[sg.Element, tk.Widget]): An Element or tkinter
            widget.

    Raises:
        WidgetNotFoundError: No widget was found for the element.

    Returns:
        Dict: The placement information.
    """
    widget = element.widget
    if widget is None:
        raise WidgetNotFoundError

    return get_widget_placement_info(widget)


class GetWidgetPlacementInfoError(Exception):
    """Error while getting the placement information of a widget."""


def get_widget_placement_info(widget: tk.Widget) -> Dict:
    """Return the placement information for an Element or tkinter widget
    as a dict.

    Args:
        target (Union[sg.Element, tk.Widget]): An Element or tkinter
            widget.

    Raises:
        GetWidgetPlacementInfoError: Error while getting the widget's
            placement information.

    Returns:
        Dict: The placement information of the widget.
    """
    try:
        placement_info = widget.info()
    except Exception as e:
        raise GetWidgetPlacementInfoError from e

    return placement_info  # type: ignore[return-value]


def get_element_pad(element: sg.Element) -> Pad:
    """Get the padding of the element/widget.

    Args:
        target (Union[sg.Element, tk.Widget]): The element/widget to get
            the padding for.

    Returns:
        Pad: The padding.
    """
    info = get_element_placement_info(element)

    padx = info["padx"]
    pady = info["pady"]

    return Pad(
        *process_pad_into_2_tuple(padx), *process_pad_into_2_tuple(pady)
    )


def get_element_original_pad(element: sg.Element) -> Pad:
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
    # It's a 2-tuple of numbers
    with suppress(TypeError):
        _, __ = pad
        _ + 1
        __ + 1
        return pad

    # It's a number
    try:
        pad + 1
        return pad, pad
    except TypeError as e:
        raise TypeError(
            "parameter must be a 2-tuple of numbers or a number"
        ) from e


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
    width, height = get_element_size(element)

    if init_pad:
        pad = get_element_original_pad(element)
    else:
        pad = get_element_pad(element)

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


def set_window_to_autosize(window: sg.Window) -> None:
    window.TKroot.geometry("")


def refresh_window_of_element(element: sg.Element) -> None:
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


class InvalidLayoutError(Exception):
    """An invalid layout was found."""


def ensure_valid_layout(layout: Sequence[Sequence[sg.Element]]) -> None:
    """Ensure that the layout is valid (an Iterable[Iterable[Element]]).

    Args:
        layout (Sequence[Sequence[sg.Element]]): The layout to check.

    Raises:
        InvalidLayoutError: 1. Layout is not an iterable.
                            2. Row is not an iterable.
                            3. An item in a row is not an Element.
                            4. Element in the layout is already in use.
    """
    try:
        iter(layout)
    except TypeError:
        raise InvalidLayoutError(
            "Error in layout",
            "Your layout is not an iterable (e.g. a list)",
            f"Instead of a list, the type found was {type(layout)}",
            "The offensive layout = ",
            layout,
        ) from None

    for row in layout:
        try:
            iter(row)
        except TypeError:
            raise InvalidLayoutError(
                "Error in layout",
                "Your row is not an iterable (e.g. a list)",
                f"Instead of an iterable, the type found was {type(layout)}",
                "The offensive row = ",
                row,
                "This item will be stripped from your layout",
            ) from None

        for element in row:
            try:
                element.ParentContainer
            except AttributeError:
                raise InvalidLayoutError(
                    "An item in a row is not an Element."
                ) from None

            if element.ParentContainer is not None:
                sg.warnings.warn(
                    (
                        "*** AN ELEMENT IN YOUR LAYOUT IS ALREADY IN USE! Once"
                        " placed in a layout, an element cannot be used in"
                        " another layout. ***"
                    ),
                    UserWarning,
                )
                raise InvalidLayoutError(
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
                ) from None


@dataclass(frozen=True)
class ElementWindow:
    """An element and it's window.

    Attributes:
        element (sg.Element): The element.
        window (sg.Window): The window that the element is in.
    """

    element: sg.Element
    window: sg.Window


def widget_to_element_with_window(
    widget: tk.Widget,
) -> Optional[ElementWindow]:
    """Return the element that matches a supplied tkinter widget and its
    window. If no matching element is found, then None is returned.

    Args:
        widget (tk.Widget): A tkinter widget.

    Returns:
        Optional[ElementWindow]: The element that matches a supplied
            tkinter
        widget and its window. Else, None.
    """

    for window in sg.Window._active_windows:
        element = window.widget_to_element(widget)
        if element:
            return ElementWindow(element, window)
    return None


def detect_all_widget_events(
    widget: tk.Widget, ignored_events: Iterable[str] = tuple()
):
    """Add event detail printing bindings to the widget for every
    possible tkinter event.

    Args:
        widget (tk.Widget): The widget to detect events for.
        ignored_events (Iterable[str], optional): An Iterable of names
            for ignored tkinter events. Event names can be accessed via
            tkinter.EventTypes.<type>.name. Defaults to tuple().
    """

    @function_details
    def event_handler(event: tk.Event):
        widget: tk.Widget = event.widget
        element_window = widget_to_element_with_window(widget)

        # Unable to get the element and window for the widget
        if not element_window:
            return

        element = element_window.element
        print(
            f"event_handler called for element with key: {element.key}",
            end="\n\n",
        )

    undocumented_events = (
        "Keymap",
        "GraphicsExpose",
        "NoExpose",
        "CirculateRequest",
        "SelectionClear",
        "SelectionRequest",
        "Selection",
        "ClientMessage",
        "Mapping",
        "VirtualEvent",
    )

    for event in tk.EventType:
        if (
            event.name not in undocumented_events
            and event.name not in ignored_events
        ):
            widget.bind(
                f"<{event.name}>",
                event_handler,
                add="+",
            )


def set_row_size_of_element(
    element: sg.Element,
    width: Optional[int] = None,
    height: Optional[int] = None,
):
    """Forcefully set the size of the row that the element is in. The
    row will no longer fit to its children.

    Args:
        element (sg.Element): The element whose row is to be resized.
        width (Optional[int], optional): New width of the row. Defaults
            to None.
        height (Optional[int], optional): New height of the row.
            Defaults to None.
    """
    row_frame: tk.Frame = element.ParentRowFrame

    try:
        current_width, current_height = get_widget_size(row_frame)
    except GetWidgetSizeError:
        current_width = current_height = 1

    new_width = width if width is not None else current_width
    new_height = height if height is not None else current_height

    row_frame.config(
        bg="skyblue3"
    )  # set a background color to see the row size
    row_frame.config(width=new_width, height=new_height)
    row_frame.pack_propagate(flag=False)


def change_row_autosizing(
    row: tk.Frame = None, element: sg.Element = None, auto_size: bool = False
) -> None:
    """Set whether the row or the row of an element fits its contents.
    If both are given, the row will be used.

    Args:
        row (tk.Frame): The tkinter Frame that represents the row.
            Defaults to None.
        element (sg.Element): The element whose row's setting is to be
            changed. Defaults to None.
        auto_size (bool): If True, the row will fit its contents.
            Defaults to False.
    """
    if row:
        row_frame = row
    elif element:
        row_frame = element.ParentRowFrame
    else:
        return

    row_frame.pack_propagate(flag=auto_size)


def find_closest_element(
    index: int,
    element_list: List[sg.Element],
    element_class: Type[sg.Element] = sg.Element,
) -> Optional[sg.Text]:
    """Find the closest element to a target element based on the target
    element's position in a list of elements.

    Args:
        index (int): The index in the list for the target element which
            the expanding search starts from.
        element_list (List[sg.Element]): A list of elements.
        element_class (Type[sg.Element]): The class requirement for the
            closest element. Defaults to sg.Element.

    Raises:
        IndexError: Invalid index for the given list.

    Returns:
        Optional[sg.Text]: The closest element if found. Else, None.
    """
    # Ensure a valid index by accessing it
    element_list[index]

    num_elements = len(element_list)

    get_pos_index(index, num_elements)

    # iterator for the elements before the target element
    prev_index = index - 1 if index > 0 else 0
    it_before = islice(
        reversed(element_list), num_elements - 1 - prev_index, None
    )

    # iterator for the elements after the target element
    next_index = index + 1 if index < num_elements - 1 else index
    it_after = islice(element_list, next_index, None)

    # Keep track of whether we're searching to the left and/or right of
    # the element
    search_expanding_left = True
    search_expanding_right = True

    while search_expanding_left or search_expanding_right:
        if search_expanding_left:
            try:
                text_element_before = is_next_element_of_class(
                    it=it_before, element_class=element_class
                )
            except StopIteration:
                search_expanding_left = False
            else:
                if text_element_before:
                    return text_element_before

        if search_expanding_right:
            try:
                text_element_after = is_next_element_of_class(
                    it=it_after, element_class=element_class
                )
            except StopIteration:
                search_expanding_right = False
            else:
                if text_element_after:
                    return text_element_after

    # No Text element found in window
    return None


def get_pos_index(index: int, length: int) -> int:
    """Return a positive index given an index.

    Args:
        index (int): An index.
        length (int): The length of the sequence the index is for.

    Returns:
        int: A positive index.
    """
    # Negative index
    if index < 0:
        index %= length
    return index


def is_next_element_of_class(
    it: Iterator[sg.Element], element_class: Type[sg.Element]
) -> Union[sg.Element, None]:
    """Test if the next element returned by the iterator is an
    instance of the specified class.

    Args:
        it (Iterator): The iterator for the elements to test.
        element_class (Type[sg.Element]): The class to test the next
            element returned by the iterator for. Defaults to
            sg.Element.

    Raises:
        StopIteration: Iterator exhausted.

    Returns:
        Union[sg.Element, None]: The element of the specified
            class or None.
    """
    next_element = next(it)
    return next_element if isinstance(next_element, element_class) else None


def convert_to_bytes(
    file_or_bytes: Union[str, bytes],
    width: Optional[int] = None,
    height: Optional[int] = None,
    fill: bool = False,
) -> bytes:
    """Will convert into bytes and optionally resize an image that is a
    file or a base64 bytes object. Turns into PNG format in the process
    so that it can be displayed by tkinter.
    :param file_or_bytes: Either a string filename or a bytes base64
        image object.
    :type file_or_bytes:  (Union[str, bytes])
    :param width:  Optional new width. The image's aspect ratio will be
        maintained while resizing. If width and height are both given,
        the image will be resized to meet the requested size as much as
        possible while maintaining the aspect ratio.
    :type width: (int or None)
    :param height:  Optional new height. The image's aspect ratio will
        be maintained while resizing. If width and height are both
        given, the image will be resized to meet the requested size as
        much as possible while maintaining the aspect ratio.
    :type height: (int or None)
    :param fill: If True, then the image is filled/padded into a square
        so that the image is not distorted.
    :type fill: (bool)
    :return: (bytes) A byte-string object.
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
        except Exception:
            dataBytesIO = io.BytesIO(file_or_bytes)
            img = PIL.Image.open(dataBytesIO)

    cur_width, cur_height = img.size

    if width is not None or height is not None:
        dimension_changes = ((width, cur_width), (height, cur_height))
        scale = min(
            new_length / cur_length
            for new_length, cur_length in dimension_changes
            if new_length is not None
        )

        img = img.resize(
            (int(cur_width * scale), int(cur_height * scale)),
            PIL.Image.Resampling.LANCZOS,
        )

        if fill:
            img = make_square(img, width)

    with io.BytesIO() as bio:
        img.save(bio, format="PNG")
        del img
        return bio.getvalue()


def disable_elements(gui_elements: Iterable[sg.Element]) -> None:
    """Disable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the
            elements to disable.
    """
    update_elements(gui_elements=gui_elements, disabled=True)


def enable_elements(gui_elements: Iterable[sg.Element]) -> None:
    """Enable the PySimpleGUI elements.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the
            elements to enable.
    """
    update_elements(gui_elements=gui_elements, disabled=False)


def update_elements(gui_elements: Iterable[sg.Element], **kwargs) -> None:
    """Update the PySimpleGUI elements using keyword arguments.

    Calls PySimpleGUI.update() with the keyword arguments provided.
    All elements must have the keyword arguments.

    Args:
        gui_elements (Iterable[sg.Element]): An Iterable with the
            elements to update.
    """
    for gui_element in gui_elements:
        gui_element.update(**kwargs)


class OutputRedirector(io.StringIO):
    """Redirector for stdout and/or stderr to a writeable Connection."""

    def __init__(
        self,
        write_conn: Union[Connection, PipeConnection],
        reroute_stdout: bool = True,
        reroute_stderr: bool = True,
    ) -> None:
        """
        Args:
            write_conn (Union[Connection, PipeConnection]): A writeable
                connection.
            reroute_stdout (bool, optional): If True, redirects stdout
                to the connection. Defaults to True.
            reroute_stderr (bool, optional): If True, redirects stderr
                to the connection. Defaults to True.
        """
        self._write_conn = write_conn
        self._previous_stdout: Optional[TextIO] = None
        self._previous_stderr: Optional[TextIO] = None

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
        """Restore a previously re-reouted stdout back to the original
        destination.
        """
        if self._previous_stdout:
            sys.stdout = self._previous_stdout
            self._previous_stdout = None  # indicate no longer routed here

    def restore_stderr(self) -> None:
        """Restore a previously re-reouted stderr back to the original
        destination.
        """
        if self._previous_stderr:
            sys.stderr = self._previous_stderr
            self._previous_stderr = None  # indicate no longer routed here

    def write(self, txt: str) -> int:
        """
        Called by Python when stdout or stderr wants to write.
        Send the text through the pipe's write connection.

        :param txt: text of output
        :type txt:  (str)
        """
        # Send text through the write connection and ignore OSError that
        # occurs if the process is killed.
        try:
            self._write_conn.send(txt)
        except OSError:
            return 0

        return len(txt)

    def flush(self) -> None:
        """Handle Flush parameter passed into a print statement.

        For now, flushing the previous stdout and stderr.
        """
        with suppress(AttributeError):
            self._previous_stdout.flush()

        with suppress(AttributeError):
            self._previous_stderr.flush()

    def __del__(self) -> None:
        """Restore the old stdout, stderr if this object is deleted"""
        self.restore_stdout()
        self.restore_stderr()


def close_connections(
    connections: Iterable[Union[Connection, PipeConnection]]
) -> None:
    """Close all given connections.

    Args:
        connections (Iterable[Union[Connection, PipeConnection]]):
            Iterable with all of the connections to close.
    """
    for conn in connections:
        conn.close()


def str_to_file_paths(
    file_paths_string: str, delimiter: str = r";"
) -> Tuple[str, ...]:
    """Split a string with file paths based on a delimiter.

    Args:
        file_paths_string (str): The string with file paths.
        delimiter (str, optional): The delimiter that separates file
            paths in the string. Defaults to r";".

    Returns:
        Tuple[str, ...]: A tuple of file paths (str).
    """
    audio_video_paths_list = re.split(delimiter, file_paths_string)
    return tuple(
        str(Path(file_path).resolve()) for file_path in audio_video_paths_list
    )


def setup_height_matched_images(
    image_file_or_bytes: Union[str, bytes, None],
    window: sg.Window,
    image_subkey: str = "",
    image_element: sg.Image = None,
    size_match_element: sg.Element = None,
    closest_element_type: Type[sg.Element] = sg.Element,
) -> Dict[sg.Image, sg.Element]:
    """Assign the same image to all Image elements in the window with a
    height that matches the target element if given or the closest
    element of the specified type.

    Usage:
        Put an Image element next to a Text element in a layout.
        (Optional) Assign a key that contains a unique string to the
        Image (Ex. key='-CHECKBOX-10' where image_subkey='-CHECKBOX-'
        will be passed to this f(x) when you intend to only update
        Image's whose key contains '-CHECKBOX-'). Call this f(x).

    Args:
        image_file_or_bytes (Union[str, bytes]): Either a string
            filename for an image file or a bytes base64 image object.
        window (sg.Window): The window to update images in.
        image_subkey (str, optional): Only update Image elements whose
            key contains this string. Defaults to "".
        image_element (sg.Image, optional): The Image element to update.
            image_subkey parameter will be ignored if this parameter is
            given. Defaults to None.
        size_match_element (sg.Element, optional): The element to size
            match. If not given, the closest element will be used.
            Defaults to None.
        closest_element_type (Type[sg.Element]): The type of the closest
            Element to size match. Defaults to sg.Element.

    Raises:
        ClosestElementOfSpecifiedTypeNotFoundInWindow: Unable to find
            closest element of the specified type in the window.

    Returns:
        Dict[sg.Image, sg.Element]: A dict with each handled Image whose
            value is its size matched element.
    """
    element_list = window.element_list()

    size_matched_pairs = {}

    for index, element in enumerate(element_list):
        # Image element given and found in list.
        given_image_found = image_element and image_element is element

        # Image element not given. Image element found with a key that
        # contains the required subkey.
        valid_image_key = (
            image_element is None
            and is_image_element(element)
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

            # Update the Image element with an image whose size matches
            # the closest element of the specified type.
            if element_to_size_match:
                update_size_matched_image(
                    image_file_or_bytes=image_file_or_bytes,
                    image_element=element,
                    element_to_size_match=element_to_size_match,
                    size_match_mode=SizeMatchMode.HEIGHT,
                )
                size_matched_pairs[element] = element_to_size_match
            else:
                raise ClosestElementOfSpecifiedTypeNotFoundInWindow(
                    f"Unable to find closest {closest_element_type} element to"
                    f" the Image element with the key={element.key} in the"
                    " main window."
                )

            # Stop after updating only the specified Image
            if image_element:
                return size_matched_pairs

    return size_matched_pairs


SizeMatchMode = Enum("SizeMatchMode", "BOTH WIDTH HEIGHT")


def update_size_matched_image(
    image_file_or_bytes: Union[str, bytes, None],
    image_element: sg.Image,
    element_to_size_match: sg.Element,
    size_match_mode: SizeMatchMode = SizeMatchMode.BOTH,
) -> None:
    """Update the Image element with an image that size matches a target
    element as much as possible while maintaining the image's aspect
    ratio.

    Args:
        image_file_or_bytes (Union[str, bytes, None]): Either a string
            filename for an image file or a bytes base64 image object.
        image_element (sg.Image): The Image element whose image is to be
            updated.
        element_to_size_match (sg.Element): The element that the image
            needs to size match.
        size_match_mode (SizeMatchMode, optional): Size match the width,
            height, or both width and height of the target element. If
            both width and height are to be size matched, the image will
            be resized as much as possible while maintaining the image's
            aspect ratio. Defaults to SizeMatchMode.BOTH.

    Raises:
        InvalidElementSize: The width and/or height of the element to
            size match is None or not greater than 0.
    """
    if image_file_or_bytes is None:
        image_element.update(source=None)
        return

    width, height = element_to_size_match.get_size()
    if width is not None and height is not None and width > 0 and height > 0:
        if size_match_mode == SizeMatchMode.BOTH:
            ...
        elif size_match_mode == SizeMatchMode.WIDTH:
            height = None
        elif size_match_mode == SizeMatchMode.HEIGHT:
            width = None
        else:
            raise ValueError(
                f"Invalid size_match_mode value of {size_match_mode}."
                f"Valid values: {list(SizeMatchMode)}"
            )

        image_element.update(
            source=convert_to_bytes(
                file_or_bytes=image_file_or_bytes,
                width=width,
                height=height,
            )
        )
    else:
        raise InvalidElementSize(
            "Unusable size for closest element"
            f" (key={element_to_size_match.key}). width={width},"
            f" height={height}."
        )


class InvalidElementSize(Exception):
    """The width and/or height of the element is not greater than 0."""


class ClosestElementOfSpecifiedTypeNotFoundInWindow(Warning):
    """Unable to find closest element of the specified type in the
    window.
    """


@contextmanager
def popup_on_error(
    *exceptions: Type[Exception], suppress_error: bool = False
) -> Generator[None, None, None]:
    """Return a context manager that creates an error popup if any of
    the given exceptions occur.

    Args:
        suppress_error (bool, optional): If True, the given exceptions
            will be suppressed if they occur. Defaults to False.

    Yields:
        Generator[None, None, None]: _description_
    """
    try:
        yield
    except exceptions as e:
        sg.PopupError(
            get_traceback(e),
            keep_on_top=True,
            image=_random_error_emoji(),
        )
        if not suppress_error:
            raise


def get_traceback(ex: Exception) -> str:
    """Return a formatted exception string.

    Args:
        ex (Exception): An exception.

    Returns:
        str: Formatted stack trace and exception information.
    """
    tb_lines = traceback.format_exception(ex.__class__, ex, ex.__traceback__)

    if len(ex.args) > 1:
        tb_lines[-1] = tb_lines[-1].split(maxsplit=1)[0]
        for arg in ex.args:
            tb_lines.append("\n\t" + pformat(arg))

    tb_text = "".join(tb_lines)
    return tb_text


def is_image_element(element: sg.Element) -> bool:
    """Test if an element is an Image element.

    Args:
        element (sg.Element): The element to test.

    Returns:
        bool: True if element is an Image element.
    """
    try:
        element.key
        element.update(source=element.Source)
    except (AttributeError, TypeError):
        return False
    return True


def function_details_legacy(func: Callable) -> Callable:
    # Issue: It uses up iterators when printing function details.

    # Getting the argument names of the called function
    argnames = func.__code__.co_varnames[: func.__code__.co_argcount]

    # Getting the Function name of the called function
    fname = func.__name__

    def inner_func(*args, **kwargs):
        print(fname, "(", end="")

        # printing the function arguments
        print(
            ", ".join(
                "% s = % r" % entry
                for entry in zip(argnames, args[: len(argnames)])
            ),
            end=", ",
        )

        # Printing the variable length Arguments
        print("args =", list(args[len(argnames) :]), end=", ")

        # Printing the variable length keyword arguments
        print("kwargs =", kwargs, end="")
        print(")")

        return func(*args, **kwargs)

    return inner_func


def get_abs_resource_path(relative_path: str) -> str:
    """Get the absolute path to the resource.

    Works when used in a frozen application for Windows made using a
    tool like Pyinstaller.

    Args:
        relative_path (str): Relative file path for the resource.

    Returns:
        str: Absolute file path for the resource.
    """
    import os

    base_path = getattr(
        sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(base_path, relative_path)


def convert_audio_video_to_audio(
    audio_video_file_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    shell_output_window: Optional[sg.Window] = None,
) -> Tuple[int, str, str]:
    """Convert an audio/video file into an audio file using ffmpeg.

    Args:
        audio_video_file_path (Union[str, Path]): The file path for
            the audio/video file.
        output_dir_path (Union[str, Path]): The output directory path.
        shell_output_window (Optional[sg.Window], optional): The
            window that the shell command writes console output should
            to. Defaults to None.

    Returns:
        Tuple[int, str, str]: A Tuple with the return value from
            executing a subprocess, a copy of the console output by
            the shell command, and the absolute file path for the
            converted audio file.
    """
    video_path = Path(audio_video_file_path)

    output_directory_path = Path(output_dir_path)

    audio_file_name = f"{video_path.stem}.mp3"

    audio_output_path = output_directory_path / audio_file_name

    cmd = (
        f'ffmpeg -i "{video_path.resolve()}" -y -q:a 0 -map a'
        f' "{audio_output_path}"'
    )

    retval, shell_output = run_shell_cmd(
        cmd=cmd,
        window=shell_output_window,
    )
    return retval, shell_output, str(audio_output_path.resolve())


def run_shell_cmd(
    cmd: str,
    timeout: Optional[float] = None,
    window: Optional[sg.Window] = None,
) -> Tuple[int, str]:
    """Run shell command.
    @param cmd: command to execute.
    @param timeout: timeout for command execution.
    @param window: the PySimpleGUI window that the output is going to
        (needed to do refresh on).
    @return: (return code from command, command output).
    """
    import shlex
    import subprocess

    p = subprocess.Popen(
        shlex.split(cmd),
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
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
        file_path (Union[str, Path]): The file path for the file to
            delete.

    Raises:
        NotAFileError: The path does not lead to a file.
    """
    p = Path(file_path)
    if p.exists():
        if not p.is_file():
            raise NotAFileError
        p.unlink()


def combo_configure(event: tk.Event) -> None:
    """Set the width of the dropdown list to fit all options.

    Does not change the entry box width.

    Usage:
        window[combo_key].widget.bind(
            "<ButtonPress>", combo_configure
        )
    """
    import tkinter.font as tkfont
    import tkinter.ttk as ttk

    combo = event.widget
    style = ttk.Style()

    long = max(combo.cget("values"), key=len)

    # font = tkfont.nametofont(str(combo.cget('font')))
    font = tkfont.Font(font=combo.cget("font"))
    width = max(
        0,
        font.measure(long.strip() + "0") - combo.winfo_width(),
    )

    style_name = "TCombobox"

    style.configure(style_name, postoffset=(0, 0, width, 0))
    combo.configure(style=style_name)


def get_combo_values(combo: sg.Combo) -> Tuple:
    """Get the values for the Combo element.

    Args:
        combo (sg.Combo): The Combo element.

    Returns:
        Tuple: A Tuple with the values for the Combo element.
    """
    return combo.widget.cget("values")


def set_combo_input_justify(combo: sg.Combo, justify: str) -> None:
    """Align the text in the combo input field.

    Args:
        combo (sg.Combo): The Combo element to update.
        justify (str): Specifies how the text is aligned within the
            Combo's input field. One of "left", "center", or "right".

    Raises:
        ValueError: justify parameter must be 'left', 'center', or
            'right'
    """
    if justify not in ("left", "center", "right"):
        raise ValueError(
            f"Invalid justify parameter value: {justify}. "
            "justify parameter must be 'left', 'center', or 'right'"
        )

    combo.widget.configure(justify=justify)


def format_multiline_text(
    element: sg.Multiline, is_multiline_rstripping_on_update: bool
) -> None:
    """Update the text in a multiline element.

    Replaces \r with \n. Replaces progress characters between |s in
    progress bars with proper █s.

    Args:
        element (sg.ErrorElement): A Multiline element.
        is_multiline_rstripping_on_update (bool): If True, the
            Multiline is stripping whitespace from the end of each
            string that is appended to its text.
    """
    # Get the text in the Multiline element
    text = element.get()

    # remove the auto appended '\n' by every Multiline.get() call when
    # rstrip=False option is set for Multiline
    if not is_multiline_rstripping_on_update:
        text = text[:-1]

    # Replace all \r with \n
    processed_text = re.sub(r"\r", "\n", text)

    def repl_progress_bars(m: re.Match):
        return "█" * len(m.group())

    processed_text = re.sub(
        r"(?<=\|)\S+(?=\s*\|)", repl_progress_bars, processed_text
    )

    element.update(processed_text)


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


@dataclass
class Font:
    family: str
    size: int
    style: str = "normal"

    def as_tuple(self):
        return (self.family, self.size, self.style)
