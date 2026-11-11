"""Browse the filesystem of the open project."""

import tkinter as tk
from tkinter import ttk

from .project import SCRATCH_DIRECTORY


class ProjectTree(ttk.Frame):
    def __init__(self, parent, open_file, guard, new_file, new_folder, import_file, trash_files):
        super().__init__(parent)
        self.project = None
        self.entries = {}
        self.open_file = open_file
        self.guard = guard
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="परियोजना की फ़ाइलें").pack(side="left")
        self.refresh_button = ttk.Button(header, text="फिर देखें", command=lambda: guard(self.refresh))
        self.refresh_button.pack(side="right")
        self.tree = ttk.Treeview(self, show="tree", selectmode="extended")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", lambda _event: guard(lambda: self.expand(self.tree.focus())))
        self.tree.bind("<ButtonPress-1>", self.click_indicator)
        self.tree.bind("<Double-Button-1>", self.activate)
        self.tree.bind("<Return>", self.activate)
        self.menu = tk.Menu(self, tearoff=False)
        self.target = ""
        for label, action in (("नई फ़ाइल…", new_file), ("नया फ़ोल्डर…", new_folder),
                              ("फ़ाइल आयात करें…", import_file)):
            self.menu.add_command(label=label, command=lambda action=action: guard(lambda: action(self.target)))
        self.menu.add_separator()
        self.menu.add_command(label="चुनी हुई फ़ाइलें कूड़ेदान में भेजें…",
                              command=lambda: guard(lambda: trash_files(self.selected_files())))
        self.tree.bind("<Button-3>", self.popup)
        self.tree.bind("<Shift-F10>", self.popup)
        if self.tk.call("tk", "windowingsystem") == "aqua":
            self.tree.bind("<Control-Button-1>", self.popup)
        self.set_project(None)

    def selected_files(self):
        return [self.entries[item][0] for item in self.tree.selection()
                if item in self.entries and not self.entries[item][1]]

    def click_indicator(self, event):
        item = self.tree.identify_row(event.y)
        if item in self.entries and self.tree.identify_element(event.x, event.y).endswith(
                ("indicator", "disclosure")) and self.tree.get_children(item):
            self.tree.focus_set()
            self.tree.focus(item)
            self.toggle(item)
            return "break"

    def toggle(self, item):
        def change():
            opening = not self.tree.item(item, "open")
            if opening:
                self.expand(item)
            self.tree.item(item, open=opening)
        self.guard(change)

    def set_project(self, project):
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        self.project = project
        self.refresh_button.configure(state="normal" if project else "disabled")
        self.refresh()

    def refresh(self, folder=""):
        opened = {name for item, (name, directory) in self.entries.items()
                  if directory and self.tree.item(item, "open")}
        parts = folder.split("/") if folder else []
        opened.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        if self.project:
            item = self.tree.insert("", "end", text=self.project.root.name, open=True)
            self.populate(item, self.project.root, opened)

    def populate(self, item, folder, opened=()):
        children = [(path, path.is_dir() and not path.is_symlink()) for path in folder.iterdir()
                    if folder != self.project.root or path.name != SCRATCH_DIRECTORY]
        self.tree.delete(*self.tree.get_children(item))
        for path, directory in sorted(children, key=lambda entry: (not entry[1], entry[0].name.casefold())):
            child = self.tree.insert(item, "end", text=path.name)
            relative = path.relative_to(self.project.root).as_posix()
            self.entries[child] = (relative, directory)
            if directory and relative in opened:
                self.tree.item(child, open=True)
                self.populate(child, path, opened)
            elif directory:
                self.tree.insert(child, "end")

    def popup(self, event):
        if not self.project:
            return
        if event.num in (1, 3):
            item = self.tree.identify_row(event.y)
            x, y = event.x_root, event.y_root
        else:
            item = self.tree.focus()
            x, y = self.tree.winfo_rootx(), self.tree.winfo_rooty()
        if item:
            self.tree.focus(item)
            if item not in self.tree.selection() and event.num in (1, 3):
                self.tree.selection_set(item)
        elif event.num in (1, 3):
            self.tree.selection_remove(self.tree.selection())
        name, directory = self.entries.get(item, ("", True))
        self.target = name if directory else name.rpartition("/")[0]
        self.menu.entryconfigure("end", state="normal" if self.selected_files() else "disabled")
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()
        return "break"

    def expand(self, item):
        entry = self.entries.get(item)
        if entry and entry[1]:
            children = self.tree.get_children(item)
            if children and children[0] not in self.entries:
                self.populate(item, self.project.file(entry[0]))

    def activate(self, event):
        if event.num == 1 and self.tree.identify_element(event.x, event.y).endswith(
                ("indicator", "disclosure")):
            return "break"
        item = self.tree.identify_row(event.y) if event.num == 1 else self.tree.focus()
        entry = self.entries.get(item)
        if entry:
            if entry[1]:
                self.toggle(item)
            else:
                self.guard(lambda: self.open_file(entry[0]))
            return "break"
