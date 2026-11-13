"""Debugger controls, call stack, and variable inspector."""

import tkinter as tk
from tkinter import ttk

from .debug import scalar_value
from .clipboard import ReadOnlyText


class DebugView(ttk.Frame):
    def __init__(self, parent, navigate, send, edit):
        super().__init__(parent)
        self.navigate = navigate
        self.send = send
        self.edit = edit
        self.stop_id = None
        self.frame = None
        self.frames = {}
        self.nodes = {}
        self.can_edit = False
        self.status = tk.StringVar(self)
        ttk.Label(self, textvariable=self.status).pack(anchor="w")
        controls = ttk.Frame(self)
        controls.pack(fill="x")
        self.buttons = {}
        for index, (command, label) in enumerate((
            ("continue", "जारी रखें"), ("next", "अगली पंक्ति"),
            ("stepIn", "अंदर जाएँ"), ("stepOut", "बाहर आएँ"),
        )):
            button = ttk.Button(controls, text=label, command=lambda cmd=command: self.resume(cmd))
            button.grid(row=index // 2, column=index % 2, sticky="ew")
            self.buttons[command] = button
        ttk.Label(self, text="कॉल स्टैक").pack(anchor="w", pady=(8, 0))
        self.stack = self.make_tree(height=5)
        self.stack.bind("<<TreeviewSelect>>", self.select_frame)
        ttk.Label(self, text="चर और मान").pack(anchor="w", pady=(8, 0))
        self.variables = self.make_tree(height=8, columns=("value",), expand=True)
        self.variables.column("#0", width=120, stretch=True)
        self.variables.column("value", width=130, stretch=True)
        self.variables.bind("<<TreeviewOpen>>", self.expand)
        self.variables.bind("<<TreeviewSelect>>", self.show_selected_value)
        self.variables.bind("<Double-1>", self.double_click)
        self.value_preview = ReadOnlyText(self, height=4, width=1, wrap="word")
        self.value_preview.pack(fill="x", pady=(4, 0))
        self.edit_button = ttk.Button(self, text="मान बदलें…", command=self.edit_selected)
        self.edit_button.pack(anchor="w")
        self.reset("डिबग सर्वर बन रहा है…")

    def make_tree(self, height, columns=(), expand=False):
        container = ttk.Frame(self)
        container.pack(fill="both" if expand else "x", expand=expand)
        tree = ttk.Treeview(container, height=height, columns=columns, show="tree", selectmode="browse")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        if columns:
            horizontal = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=horizontal.set)
            horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    def clear_variables(self):
        self.variables.delete(*self.variables.get_children())
        self.nodes.clear()
        self.can_edit = False
        self.value_preview.set_text("")

    def show_selected_value(self, _event=None):
        selection = self.variables.selection()
        _, variable = self.nodes.get(selection[0], (0, {})) if selection else (0, {})
        self.value_preview.set_text(variable.get("value", ""))
        self.update_buttons()

    def reset(self, label):
        self.status.set(label)
        self.stop_id = None
        self.frame = None
        self.frames.clear()
        self.stack.delete(*self.stack.get_children())
        self.clear_variables()
        self.update_buttons()

    def selected_variable(self):
        selected = self.variables.selection()
        if not self.can_edit or not selected or selected[0] not in self.nodes:
            return None
        node = selected[0]
        reference, variable = self.nodes[node]
        if not variable or not reference:
            return None
        parent = self.variables.parent(node)
        scope = self.nodes.get(parent, (0, {}))[1]
        if scope.get("presentationHint") not in {"locals", "arguments"}:
            return None
        if not scalar_value(variable, "0") and not scalar_value(variable, "false"):
            return None
        siblings = [self.nodes[item][1] for item in self.variables.get_children(parent)
                    if item in self.nodes]
        if sum(bool(item and item.get("name") == variable.get("name")) for item in siblings) != 1:
            return None
        return node, reference, variable

    def update_buttons(self):
        for button in self.buttons.values():
            button.configure(state="normal" if self.stop_id is not None else "disabled")
        self.edit_button.configure(state="normal" if self.selected_variable() else "disabled")

    def resume(self, command):
        if self.stop_id is not None:
            self.send(command, self.stop_id)
            for button in self.buttons.values():
                button.configure(state="disabled")
            self.edit_button.configure(state="disabled")

    def stopped(self, stop_id, reason, frames):
        self.reset("विराम बिंदु पर रुका" if reason == "breakpoint" else "डिबग सर्वर रुका")
        self.stop_id = stop_id
        initial = None
        for frame in frames:
            file = frame.get("project_file")
            label = f"{frame['name']}  {file}:{frame['line']}" if file else frame["name"]
            item = self.stack.insert("", "end", text=label)
            self.frames[item] = frame
            if initial is None and file:
                initial = item
        initial = initial or next(iter(self.frames), None)
        if initial:
            self.stack.selection_set(initial)
            self.stack.see(initial)
        self.update_buttons()

    def select_frame(self, _event):
        selection = self.stack.selection()
        if not selection or self.stop_id is None:
            return
        frame = self.frames[selection[0]]
        if self.frame == frame["id"]:
            return
        self.frame = frame["id"]
        self.clear_variables()
        self.update_buttons()
        if frame.get("project_file") and frame["line"] > 0:
            self.navigate(frame["project_file"], frame["line"])
        self.send("scopes", self.stop_id, self.frame)

    def show_scopes(self, stop_id, frame, scopes, can_edit):
        if (stop_id, frame) != (self.stop_id, self.frame):
            return
        selection = self.stack.selection()
        self.can_edit = bool(can_edit and selection and self.frames[selection[0]].get("project_file"))
        for scope in scopes:
            hint = scope.get("presentationHint")
            if hint in {"registers", "globals"}:
                continue
            reference = scope["variablesReference"]
            label = {"locals": "स्थानीय चर", "arguments": "मापदंड"}.get(hint, scope["name"])
            node = self.variables.insert("", "end", text=label)
            self.nodes[node] = (0, scope)
            if reference:
                if scope.get("expensive"):
                    self.variables.insert(node, "end", text="…")
                else:
                    self.variables.item(node, open=True)
                    self.send("variables", stop_id, node, reference)

    def expand(self, _event):
        node = self.variables.focus()
        if node in self.nodes and self.stop_id is not None:
            _, variable = self.nodes[node]
            children = self.variables.get_children(node)
            if len(children) == 1 and children[0] not in self.nodes:
                self.send("variables", self.stop_id, node, variable.get("bhashChildren") or variable["variablesReference"])

    def show_variables(self, stop_id, node, reference, variables):
        if stop_id != self.stop_id or node not in self.nodes:
            return
        self.variables.delete(*self.variables.get_children(node))
        for variable in variables:
            child = self.variables.insert(node, "end", text=variable["name"],
                                          values=(variable.get("value", ""),))
            self.nodes[child] = (reference, variable)
            if variable.get("variablesReference") or variable.get("bhashChildren"):
                self.variables.insert(child, "end", text="…")

    def double_click(self, event):
        if self.variables.identify_column(event.x) == "#1":
            self.edit_selected()

    def edit_selected(self):
        selected = self.selected_variable()
        if selected and self.stop_id is not None:
            self.edit(self.stop_id, *selected)

    def edited(self, stop_id, node, value):
        if stop_id == self.stop_id and node in self.nodes:
            _, variable = self.nodes[node]
            variable["value"] = value
            self.variables.item(node, values=(value,))
            self.show_selected_value()
