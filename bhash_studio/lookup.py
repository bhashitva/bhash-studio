"""Offline reference shared with the Bhash VS Code and notebook tools."""

from functools import lru_cache
from importlib.resources import files
import json
import re
from unicodedata import normalize
from urllib.parse import quote
import webbrowser
import tkinter as tk
from tkinter import ttk

from .clipboard import ReadOnlyText


def search_key(value):
    return normalize("NFC", value).casefold()


@lru_cache(maxsize=1)
def catalog():
    return json.loads(files("bhash_studio").joinpath("lookup_catalog.json").read_text(encoding="utf-8"))


def search(query="", mode="library", group="", kind=""):
    terms = search_key(query).split()
    return [entry for entry in catalog()[mode]
            if (not group or entry["group"] == group)
            and (not kind or entry["kind"] == kind)
            and all(term in search_key(entry["search"]) for term in terms)]


def plain_template(template):
    """Return editable text and placeholder spans without executing the source."""
    output, spans, cursor = [], [], 0
    for match in re.finditer(r"\$\{([^}]*)\}", template):
        output.append(template[cursor:match.start()])
        start = sum(map(len, output))
        output.append(match[1])
        spans.append((start, start + len(match[1])))
        cursor = match.end()
    output.append(template[cursor:])
    return "".join(output), spans


class ReferenceWindow:
    def __init__(self, studio, mode="library"):
        self.studio = studio
        self.editor = studio.editor
        self.source = self.editor.get("1.0", "end-1c") if self.editor else None
        self.selection = tuple(map(str, self.editor.tag_ranges("sel"))) if self.editor else ()
        self.caret = self.editor.index("insert") if self.editor else None
        self.window = tk.Toplevel(studio.root)
        self.window.title("भाष संदर्भ · Bhash reference")
        self.window.geometry("1000x650")
        self.window.transient(studio.root)
        self.window.bind("<Escape>", lambda _: self.window.destroy())
        controls = ttk.Frame(self.window, padding=8)
        controls.pack(fill="x")
        self.mode = tk.StringVar(value=mode)
        for value, title in (("library", "पुस्तकालय"), ("language", "शब्द और ढाँचे")):
            ttk.Radiobutton(controls, text=title, variable=self.mode, value=value,
                            command=self.switch_mode).pack(side="left", padx=4)
        self.query = tk.StringVar()
        ttk.Label(controls, text="खोजें · Search").pack(side="left", padx=8)
        entry = ttk.Entry(controls, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True)
        self.group = tk.StringVar()
        self.groups = ttk.Combobox(controls, textvariable=self.group, state="readonly", width=22)
        self.groups.pack(side="left", padx=6)
        self.groups.bind("<<ComboboxSelected>>", self.refresh)
        self.kind = tk.StringVar()
        self.kinds = ttk.Combobox(controls, textvariable=self.kind, state="readonly", width=14)
        self.kinds.pack(side="left", padx=4)
        self.kinds.bind("<<ComboboxSelected>>", self.refresh)
        self.query.trace_add("write", self.refresh)
        panes = ttk.Panedwindow(self.window, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)
        left = ttk.Frame(panes)
        self.results = tk.Listbox(left, exportselection=False, font=("Nirmala UI", 11))
        scroll = ttk.Scrollbar(left, command=self.results.yview)
        self.results.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.results.pack(fill="both", expand=True)
        self.results.bind("<<ListboxSelect>>", self.show)
        self.detail = ReadOnlyText(panes, wrap="word", font=("Nirmala UI", 12), padx=12, pady=12)
        panes.add(left, weight=1)
        panes.add(self.detail, weight=2)
        actions = ttk.Frame(self.window, padding=8)
        actions.pack(fill="x")
        for title, command in (("कोड डालें", self.insert), ("उदाहरण डालें", self.insert_example),
                               ("कॉपी करें", self.copy), ("पूरा प्रलेखन", self.documentation)):
            ttk.Button(actions, text=title, command=command).pack(side="left", padx=4)
        self.status = tk.StringVar()
        ttk.Label(self.window, textvariable=self.status, padding=8).pack(fill="x")
        self.switch_mode()
        entry.focus_set()

    def switch_mode(self):
        self.groups.configure(values=["", *sorted({row["group"] for row in catalog()[self.mode.get()]})])
        self.group.set("")
        kinds = ("types", "members") if self.mode.get() == "library" else ("keywords", "constructs")
        self.kinds.configure(values=["", *kinds])
        self.kind.set("")
        self.refresh()

    def refresh(self, *_):
        self.rows = search(self.query.get(), self.mode.get(), self.group.get(), self.kind.get())
        self.results.delete(0, "end")
        for row in self.rows:
            self.results.insert("end", row["label"])
        self.status.set(f"{len(self.rows)} नतीजे · सूची इंटरनेट के बिना उपलब्ध है")
        self.detail.set_text("")
        if self.rows:
            self.results.selection_set(0)
            self.show()

    def selected(self):
        choice = self.results.curselection()
        return self.rows[choice[0]] if choice else None

    def show(self, *_):
        row = self.selected()
        self.detail.set_text(row["detail"] if row else "")

    def insert(self):
        row = self.selected()
        if row:
            self.apply(row["template"], row.get("kind") == "keywords")

    def insert_example(self):
        row = self.selected()
        if row and row.get("example"):
            self.apply(row["example"])
        else:
            self.status.set("इस प्रविष्टि का उदाहरण उपलब्ध नहीं है।")

    def apply(self, template, keyword=False):
        editor = self.editor
        if (not editor or not editor.winfo_exists() or self.studio.editor is not editor
                or not editor.source_mode or str(editor.cget("state")) == "disabled"
                or editor.get("1.0", "end-1c") != self.source
                or editor.index("insert") != self.caret
                or tuple(map(str, editor.tag_ranges("sel"))) != self.selection):
            self.status.set("चुना स्रोत बदल गया है। स्रोत में कर्सर रखें और संदर्भ फिर खोलें।")
            return
        editor.insert_template(template, keyword=keyword)
        self.window.destroy()

    def copy(self):
        row = self.selected()
        if row:
            self.window.clipboard_clear()
            self.window.clipboard_append(plain_template(row["template"])[0])

    def documentation(self):
        row = self.selected()
        if row and row.get("path", "").startswith(("tutorial/", "docs/")):
            webbrowser.open("https://github.com/bhashitva/bhash/blob/" + catalog()["revision"] + "/"
                            + quote(row["path"], safe="/"))
