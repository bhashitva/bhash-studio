"""Browse the filesystem of the open project."""

from tkinter import ttk


class ProjectTree(ttk.Frame):
    def __init__(self, parent, open_file, guard):
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
        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", lambda _event: guard(lambda: self.expand(self.tree.focus())))
        self.tree.bind("<Double-Button-1>", self.activate)
        self.tree.bind("<Return>", self.activate)
        self.set_project(None)

    def set_project(self, project):
        self.project = project
        self.refresh_button.configure(state="normal" if project else "disabled")
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        if self.project:
            item = self.tree.insert("", "end", text=self.project.root.name, open=True)
            self.populate(item, self.project.root)

    def populate(self, item, folder):
        children = [(path, path.is_dir() and not path.is_symlink()) for path in folder.iterdir()]
        self.tree.delete(*self.tree.get_children(item))
        for path, directory in sorted(children, key=lambda entry: (not entry[1], entry[0].name.casefold())):
            child = self.tree.insert(item, "end", text=path.name)
            relative = path.relative_to(self.project.root).as_posix()
            self.entries[child] = (relative, directory)
            if directory:
                self.tree.insert(child, "end")

    def expand(self, item):
        entry = self.entries.get(item)
        if entry and entry[1]:
            children = self.tree.get_children(item)
            if children and children[0] not in self.entries:
                self.populate(item, self.project.file(entry[0]))

    def activate(self, event):
        item = self.tree.identify_row(event.y) if event.num == 1 else self.tree.focus()
        entry = self.entries.get(item)
        if entry:
            if entry[1]:
                self.guard(lambda: self.expand(item))
                self.tree.item(item, open=not self.tree.item(item, "open"))
            else:
                self.guard(lambda: self.open_file(entry[0]))
            return "break"
