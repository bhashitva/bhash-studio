"""Bhash source editing helpers for the studio's Tk text widget."""

from bisect import bisect_right
import re
import tkinter as tk

from .bhash_syntax import analyze


class BhashEditor(tk.Text):
    def __init__(self, parent, **options):
        super().__init__(parent, exportselection=False, **options)
        self.source_mode = False
        self.pending = None
        self.suggest_after_edit = False
        self.completion = None
        self.tag_configure("keyword", foreground="#663399")
        self.choices = tk.Listbox(
            self, font=self.cget("font"), width=25, takefocus=False,
            exportselection=False, background="#ffffff", foreground="#182d43",
            selectbackground="#193a59", selectforeground="#ffffff",
        )
        self.choices.bind("<Button-1>", self.choose)
        self.bind("<<Modified>>", self.edited)
        self.bind("<Control-space>", self.complete_now)
        self.bind("<Up>", lambda event: self.move_choice(-1))
        self.bind("<Down>", lambda event: self.move_choice(1))
        self.bind("<Return>", self.accept)
        self.bind("<Tab>", self.accept)
        for sequence in ("<Escape>", "<FocusOut>", "<ButtonPress-1>", "<Left>", "<Right>",
                         "<Home>", "<End>", "<Prior>", "<Next>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.dismiss)
        self.bind("<Destroy>", self.cancel_refresh)

    def open_buffer(self, text, source_mode):
        self.dismiss()
        self.source_mode = source_mode
        self.replace("1.0", "end-1c", text)
        self.mark_set("insert", "1.0")
        self.edit_reset()
        self.edit_modified(False)
        self.refresh()

    def edited(self, _event):
        if not self.edit_modified():
            return
        self.edit_modified(False)
        self.dismiss()
        if self.source_mode:
            self.cancel_refresh()
            self.suggest_after_edit = True
            self.pending = self.after(120, self.refresh_after_edit)

    def cancel_refresh(self, _event=None):
        if self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None

    def refresh_after_edit(self):
        self.pending = None
        self.refresh(show=self.suggest_after_edit and self.focus_get() == self)

    def refresh(self, show=False):
        self.cancel_refresh()
        self.dismiss()
        self.tag_remove("keyword", "1.0", "end")
        if not self.source_mode:
            return
        source = self.get("1.0", "end-1c")
        caret = len(self.get("1.0", "insert")) if show and not self.tag_ranges("sel") else None
        ranges, completion = analyze(source, caret)
        line_starts = [0, *(match.end() for match in re.finditer("\n", source))]

        def index_at(offset):
            row = bisect_right(line_starts, offset)
            # Tk 8.6 counts supplementary characters differently from Python.
            col = self.tk.call("string", "length", source[line_starts[row - 1]:offset])
            return f"{row}.{col}"

        if ranges:
            self.tag_add("keyword", *(index_at(offset) for pair in ranges for offset in pair))
        if completion and (cursor := self.bbox("insert")):
            self.completion = (index_at(completion.start), index_at(completion.end), completion.options)
            self.choices.delete(0, "end")
            self.choices.insert("end", *completion.options)
            self.choices.configure(height=len(completion.options))
            x, y, _, line_height = cursor
            width = self.choices.winfo_reqwidth()
            height = self.choices.winfo_reqheight()
            y = y + line_height if y + line_height + height <= self.winfo_height() else y - height
            self.choices.place(x=max(0, min(x, self.winfo_width() - width)), y=max(0, y))
            self.choices.selection_set(0)
            self.choices.lift()

    def complete_now(self, _event):
        self.refresh(show=True)
        return "break"

    def dismiss(self, _event=None):
        self.suggest_after_edit = False
        self.completion = None
        self.choices.place_forget()

    def move_choice(self, step):
        if self.completion is None:
            return None
        selected = self.choices.curselection()[0]
        next_index = (selected + step) % self.choices.size()
        self.choices.selection_clear(0, "end")
        self.choices.selection_set(next_index)
        self.choices.activate(next_index)
        return "break"

    def choose(self, event):
        if self.completion is not None:
            self.apply_choice(self.choices.nearest(event.y))
        return "break"

    def accept(self, _event):
        if self.completion is not None:
            self.apply_choice(self.choices.curselection()[0])
            return "break"
        return None

    def apply_choice(self, choice):
        start, end, options = self.completion
        self.insert_text(start, end, options[choice])

    def insert_helper(self, before, after=""):
        if not self.source_mode:
            return
        selection = self.tag_ranges("sel")
        start, end = selection if selection else ("insert", "insert")
        line = self.get(f"{start} linestart", start)
        indent = re.match(r"[ \t]*", line).group()
        before = before.replace("\n", "\n" + indent)
        after = after.replace("\n", "\n" + indent)
        self.insert_text(start, end, before, after)
        self.focus_set()

    def insert_text(self, start, end, before, after=""):
        start = self.index(start)
        self.edit_separator()
        self.replace(start, end, before + after)
        self.edit_separator()
        self.mark_set("insert", f"{start} + {len(before)} chars")
        self.tag_remove("sel", "1.0", "end")
        self.see("insert")
        self.edit_modified(False)
        self.refresh()
