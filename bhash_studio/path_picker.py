"""Hindi file and folder selection for project and toolchain paths."""

import os
from pathlib import Path
import string
import tkinter as tk
from tkinter import ttk

from .project import LocalPath


def choose_path(parent, title, matches=None):
    previous_grab = parent.grab_current()
    picker = PathPicker(parent, title, matches)
    try:
        parent.wait_window(picker)
        return picker.result
    finally:
        if previous_grab is not None and previous_grab.winfo_exists():
            previous_grab.grab_set()


class PathPicker(tk.Toplevel):
    def __init__(self, parent, title, matches=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.geometry("740x470")
        self.minsize(500, 310)
        self.result = None
        self.matches = matches
        self.directory = LocalPath.cwd()
        self.paths = {}

        navigation = ttk.Frame(self, padding=8)
        navigation.pack(fill="x")
        ttk.Button(navigation, text="ऊपर जाएँ", command=self.up).pack(side="left")
        ttk.Button(navigation, text="वर्तमान स्थान", command=lambda: self.show(LocalPath.cwd())).pack(side="left", padx=6)
        if os.name == "nt":
            self.add_drives(navigation)
        self.location = tk.StringVar(self)
        ttk.Entry(self, state="readonly", textvariable=self.location).pack(fill="x", padx=8)

        contents = ttk.Frame(self, padding=8)
        contents.pack(fill="both", expand=True)
        self.files = ttk.Treeview(contents, columns=("kind",), show="tree headings", selectmode="browse")
        self.files.heading("#0", text="नाम")
        self.files.heading("kind", text="प्रकार")
        self.files.column("kind", width=100, stretch=False)
        scroll = ttk.Scrollbar(contents, orient="vertical", command=self.files.yview)
        self.files.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.files.pack(fill="both", expand=True)
        self.files.bind("<Double-Button-1>", self.enter)
        self.files.bind("<Return>", self.enter)
        self.files.bind("<BackSpace>", self.up)
        self.files.bind("<<TreeviewSelect>>", self.update_choice)

        actions = ttk.Frame(self, padding=(8, 0, 8, 8))
        actions.pack(fill="x")
        self.status = ttk.Label(actions)
        self.status.pack(side="left")
        ttk.Button(actions, text="रद्द करें", command=self.destroy).pack(side="right")
        self.select_button = ttk.Button(actions, text="चुनें", command=self.select)
        self.select_button.pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.show(self.directory)
        self.files.focus_set()
        self.grab_set()

    def add_drives(self, parent):
        # Python 3.11 predates os.listdrives().
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = ttk.Menubutton(parent, text="ड्राइव")
        menu = tk.Menu(drives, tearoff=False)
        for index, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << index):
                path = LocalPath(letter + ":\\")
                menu.add_command(label=str(path), command=lambda path=path: self.show(path))
        drives.configure(menu=menu)
        drives.pack(side="left")

    def show(self, directory):
        try:
            entries = []
            for path in directory.iterdir():
                if path.is_dir():
                    entries.append((path, True))
                elif self.matches is not None and self.matches(path) and path.is_file():
                    entries.append((path, False))
        except OSError:
            self.status.configure(text="फ़ोल्डर नहीं पढ़ा जा सका।")
            return

        self.directory = directory
        self.location.set(str(directory))
        self.files.delete(*self.files.get_children())
        self.paths.clear()
        for path, is_folder in sorted(entries, key=lambda item: (not item[1], item[0].name.casefold())):
            item = self.files.insert("", "end", text=path.name, values=("फ़ोल्डर" if is_folder else "फ़ाइल",))
            self.paths[item] = (path, is_folder)
        self.status.configure(text="")
        self.update_choice()

    def selected(self):
        items = self.files.selection()
        return self.paths.get(items[0]) if items else None

    def update_choice(self, _event=None):
        entry = self.selected()
        if self.matches is None:
            label = "चुना फ़ोल्डर लें" if entry else "यह फ़ोल्डर लें"
            self.select_button.configure(text=label, state="normal")
        else:
            label = "फ़ोल्डर खोलें" if entry and entry[1] else "फ़ाइल चुनें"
            self.select_button.configure(text=label, state="normal" if entry else "disabled")

    def up(self, _event=None):
        self.show(self.directory.parent)
        return "break"

    def enter(self, event):
        if event.type == tk.EventType.ButtonPress:
            row = self.files.identify_row(event.y)
            if not row:
                return "break"
            self.files.selection_set(row)
        entry = self.selected()
        if entry and entry[1]:
            self.show(entry[0])
        elif entry:
            self.select()
        return "break"

    def select(self):
        entry = self.selected()
        if self.matches is None:
            self.result = str(entry[0] if entry else self.directory)
        elif entry and entry[1]:
            self.show(entry[0])
            return
        elif entry:
            self.result = str(entry[0])
        if self.result is not None:
            self.destroy()


def jar_file(path: Path):
    return path.suffix.lower() == ".jar"


def java_program(path: Path):
    return path.name.lower() == ("java.exe" if os.name == "nt" else "java")
