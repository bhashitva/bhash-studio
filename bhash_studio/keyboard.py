"""Preserve Devanagari input before older Windows Tk converts it to ANSI."""

from collections import deque
import sys
import tkinter as tk
from tkinter import ttk


def enable_hindi_input(window):
    if sys.platform != "win32":
        return

    import ctypes as c
    from ctypes import wintypes as w

    user = c.WinDLL("user32")
    controls = c.WinDLL("comctl32")
    result = c.c_ssize_t
    pointer = c.c_size_t
    procedure = c.WINFUNCTYPE(result, w.HWND, w.UINT, w.WPARAM, w.LPARAM, pointer, pointer)
    controls.SetWindowSubclass.argtypes = (w.HWND, procedure, pointer, pointer)
    controls.SetWindowSubclass.restype = w.BOOL
    controls.DefSubclassProc.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    controls.DefSubclassProc.restype = result
    controls.RemoveWindowSubclass.argtypes = (w.HWND, procedure, pointer)
    controls.RemoveWindowSubclass.restype = w.BOOL
    user.PeekMessageW.argtypes = (c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT)
    user.PeekMessageW.restype = w.BOOL
    pending_input = deque()

    def is_hindi(character):
        return 0x0900 <= character <= 0x097f or character in (0x200c, 0x200d)

    def insert(event):
        if not pending_input:
            return
        text = pending_input.popleft()
        widget = event.widget
        if not isinstance(widget, (tk.Text, ttk.Entry)) or widget.winfo_toplevel() is not window:
            return "break"
        if isinstance(widget, tk.Text):
            if widget.cget("state") == "disabled":
                return "break"
            if widget.tag_ranges("sel"):
                widget.delete("sel.first", "sel.last")
            widget.insert("insert", text)
            widget.see("insert")
        else:
            if widget.instate(("disabled", "readonly")):
                return "break"
            if widget.selection_present():
                widget.delete("sel.first", "sel.last")
            widget.insert("insert", text)
            widget.xview("insert")
        return "break"

    def deliver(hwnd, text):
        # Have Tk queue a key event to its logical focus. Calling a widget from
        # the native window procedure can re-enter Tcl during its message pump.
        # A key release leaves any other queued character messages alone.
        pending_input.append(text)
        return controls.DefSubclassProc(hwnd, 0x0101, 0x87, 0xc0000001)  # WM_KEYUP, VK_F24

    @procedure
    def window_proc(hwnd, message, key, flags, identifier, _data):
        if message in (0x0100, 0x0104):  # WM_KEYDOWN, WM_SYSKEYDOWN
            # The Windows message loop already called TranslateMessage. Read the
            # queued Unicode characters before older Tk reads them with GetMessageA.
            char_message = 0x0102 if message == 0x0100 else 0x0106
            pending = w.MSG()
            chars = []
            while (user.PeekMessageW(c.byref(pending), hwnd, char_message, char_message, 0)
                   and pending.message == char_message and is_hindi(pending.wParam)):
                user.PeekMessageW(c.byref(pending), hwnd, char_message, char_message, 1)
                chars.append(chr(pending.wParam))
            if chars:
                return deliver(hwnd, "".join(chars))
        elif message in (0x0102, 0x0109) and is_hindi(key):  # WM_CHAR, WM_UNICHAR
            return deliver(hwnd, chr(key))
        if message == 0x0082:  # WM_NCDESTROY
            controls.RemoveWindowSubclass(hwnd, window_proc, 1)
        return controls.DefSubclassProc(hwnd, message, key, flags)

    if controls.SetWindowSubclass(window.winfo_id(), window_proc, 1, 0):
        # Keep the callback alive until Windows finishes destroying the control.
        window._hindi_window_proc = window_proc
        window.bind("<KeyRelease-F24>", insert, add=True)
