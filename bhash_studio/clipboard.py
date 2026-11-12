"""Consistent clipboard commands for Yantra text widgets."""

import tkinter as tk
from tkinter import ttk


COMMANDS = (("Cut", "काटें", "x"), ("Copy", "प्रतिलिपि बनाएँ", "c"),
            ("Paste", "चिपकाएँ", "v"), ("SelectAll", "सब चुनें", "a"))


def clipboard_action(widget, action):
    if not isinstance(widget, (tk.Text, ttk.Entry)):
        return
    text = isinstance(widget, tk.Text)
    if action == "SelectAll":
        if text:
            widget.tag_add("sel", "1.0", "end-1c")
        else:
            widget.selection_range(0, "end")
        return
    editable = str(widget.cget("state")) == "normal"
    if not editable and action != "Copy":
        return
    if text:
        selection = widget.tag_ranges("sel")
    else:
        selection = ("sel.first", "sel.last") if widget.selection_present() else ()
    if action in {"Cut", "Copy"}:
        if not selection:
            return
        widget.clipboard_clear()
        value = widget.get(*selection) if text else widget.tk.call(
            "string", "range", widget.get(), widget.index("sel.first"), widget.index("sel.last") - 1,
        )
        widget.clipboard_append(value)
        if action == "Cut":
            widget.delete(*selection)
    elif action == "Paste":
        try:
            value = widget.clipboard_get()
        except tk.TclError:
            return
        if text:
            start, end = selection or ("insert", "insert")
            widget.edit_separator()
            widget.replace(start, end, value)
            widget.edit_separator()
            widget.see("insert")
        else:
            if selection:
                widget.delete(*selection)
            widget.insert("insert", value)


def enable_clipboard(widget):
    mac = widget.tk.call("tk", "windowingsystem") == "aqua"
    modifier, hint = ("Command", "⌘") if mac else ("Control", "Ctrl+")
    menu = tk.Menu(widget, tearoff=False)
    for action, label, key in COMMANDS:
        def run(_event=None, action=action):
            clipboard_action(widget, action)
            return "break"

        widget.bind(f"<{modifier}-{key}>", run)
        widget.bind(f"<<{action}>>", run)
        menu.add_command(label=label, accelerator=hint + key.upper(), command=run)

    def popup(event):
        widget.focus_set()
        editable = str(widget.cget("state")) == "normal"
        for index in (0, 2):
            menu.entryconfigure(index, state="normal" if editable else "disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    widget.bind("<Button-3>", popup)
    if mac:
        widget.bind("<Control-Button-1>", popup)


class ReadOnlyText(tk.Text):
    def __init__(self, parent, **options):
        super().__init__(parent, state="disabled", exportselection=False, **options)
        enable_clipboard(self)

    def set_text(self, value):
        if self.get("1.0", "end-1c") != value:
            self.configure(state="normal")
            self.replace("1.0", "end-1c", value)
            self.configure(state="disabled")
