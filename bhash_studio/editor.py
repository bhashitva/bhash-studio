"""Bhash source editing helpers for the studio's Tk text widget."""

from bisect import bisect_right
import re
import subprocess
import tkinter as tk

from .bhash_syntax import analyze, standard_library
from .errors import StudioError


class BhashEditor(tk.Text):
    def __init__(self, parent, syntax_check=None, compiler_path=None, **options):
        super().__init__(parent, exportselection=False, **options)
        self.source_mode = False
        self.pending = None
        self.suggest_after_edit = False
        self.completion = None
        self.syntax_check = syntax_check
        self.compiler_path = compiler_path
        self.syntax_status = tk.StringVar(self)
        self.syntax_timer = None
        self.syntax_future = None
        self.tag_configure("keyword", foreground="#663399")
        self.tag_configure("syntax_error", foreground="#a4252c", underline=True)
        self.tag_raise("sel")
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
        self.bind("<Destroy>", self.cancel_syntax, add=True)

    def open_buffer(self, text, source_mode):
        self.dismiss()
        self.source_mode = source_mode
        self.replace("1.0", "end-1c", text)
        self.mark_set("insert", "1.0")
        self.edit_reset()
        self.edit_modified(False)
        self.refresh()
        self.schedule_syntax()

    def edited(self, _event):
        if not self.edit_modified():
            return
        self.edit_modified(False)
        self.dismiss()
        if self.source_mode:
            self.schedule_syntax()
            self.cancel_refresh()
            self.suggest_after_edit = True
            self.pending = self.after(120, self.refresh_after_edit)

    def cancel_syntax(self, _event=None):
        if self.syntax_timer is not None:
            self.after_cancel(self.syntax_timer)
            self.syntax_timer = None
        if self.syntax_future is not None:
            self.syntax_future.cancel()
            self.syntax_future = None

    def schedule_syntax(self):
        self.cancel_syntax()
        self.tag_remove("syntax_error", "1.0", "end")
        self.syntax_status.set("")
        if self.source_mode and self.syntax_check is not None:
            self.syntax_timer = self.after(500, self.start_syntax)

    def start_syntax(self):
        self.syntax_timer = None
        self.syntax_future = self.syntax_check(self.get("1.0", "end-1c"))
        self.finish_syntax()

    def finish_syntax(self):
        self.syntax_timer = None
        if not self.syntax_future.done():
            self.syntax_timer = self.after(60, self.finish_syntax)
            return
        future, self.syntax_future = self.syntax_future, None
        try:
            diagnostics = future.result()
        except StudioError as error:
            self.syntax_status.set(str(error))
            return
        except (OSError, subprocess.TimeoutExpired):
            self.syntax_status.set("वाक्यविन्यास जाँच पूरी नहीं हुई। जावा और कंपाइलर की सेटिंग जाँचें।")
            return
        if not diagnostics:
            self.syntax_status.set("वाक्यविन्यास सही है।")
            return
        for line, column, _ in diagnostics:
            prefix = self.get(f"{line}.0", f"{line}.end")[:column - 1]
            start = f"{line}.{self.tk.call('string', 'length', prefix)}"
            if self.compare(start, ">=", "end-1c"):
                start = self.index("end-1c -1c")
            self.tag_add("syntax_error", start, f"{start} +1c")
        line, column, message = diagnostics[0]
        self.syntax_status.set(f"{len(diagnostics)} त्रुटि — पंक्ति {line}, स्थान {column} — {message}")

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
        if caret is not None and self.compiler_path is not None:
            ranges, completion = analyze(source, caret, *standard_library(self.compiler_path()))
        else:
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
            self.choices.configure(height=min(8, len(completion.options)))
            self.choices.yview_moveto(0)
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
        self.choices.see(next_index)
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
        self.schedule_syntax()
