"""Bhash Yantra's Hindi-first desktop interface."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import queue
import sys
from textwrap import fill
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from .android import AndroidTarget, Toolchain
from .bhash_syntax import CONSTRUCTS, KEYWORDS, check_syntax
from .clipboard import COMMANDS, ReadOnlyText, clipboard_action, enable_clipboard
from .config import loads
from .editor import BhashEditor
from .errors import StudioError
from .keyboard import enable_hindi_input
from .path_picker import choose_path, jar_file, java_program
from .project import BUILD_DIRECTORY, CONFIG, FILES, SOURCE, LocalPath, Project, digest
from .project_tree import ProjectTree
from .settings import (load_project_session, load_session, load_settings,
                       save_project_session, save_session, save_settings, settings_path)
from .targets import validate_snapshot
from .signature_help import LanguageServer


APP_NAME = "भाष यंत्र"


def move_to_trash(path):
    try:
        if sys.platform == "win32":
            from send2trash.win.modern import send2trash
        else:
            from send2trash import send2trash
    except ImportError as error:
        raise StudioError("कूड़ेदान के लिए भाष यंत्र की निर्भरताएँ स्थापित करें — python -m pip install .") from error
    send2trash(str(path))
    if path.exists():
        raise OSError("फ़ाइल अपने मूल स्थान पर है।")


HELP = '''भाष यंत्र में आपका स्वागत है

नई परियोजना के लिए ऐप का नाम और नए फ़ोल्डर का नाम लिखें। उसका मूल फ़ोल्डर चुनें। पहले से बनी परियोजना खोलने के लिए उसकी परियोजना.भाषविन्यास फ़ाइल चुनें।

परियोजना.भाषविन्यास में नाम, लक्ष्य और अनुमतियाँ हैं। सत्य, असत्य और रिक्त भाष के मूल मान हैं। ऐप की पहचान बनाए रखें, ताकि उसके अद्यतन उसी ऐप पर लगें।

पर्दा.भाषदृश्य में स्तंभ, पंक्ति, पाठ, प्रविष्टि और बटन लिखें। प्रविष्टि और परिणाम दिखाने वाले पाठ को अलग पहचान दें। बटन के इनपुटसे में प्रविष्टि की पहचान और परिणाममें में पाठ की पहचान लिखें। दबानेपर वाला फलन मुख्य.bhash में एक पाठ लेता है और एक पाठ लौटाता है।

सहेजें से खुली फ़ाइल सहेजें। टैब या भाष यंत्र बंद करने पर अधूरी लिखावट परियोजना के .studio फ़ोल्डर में रखी जाती है। अगली बार परियोजना खोलने पर खुले टैब और उनकी लिखावट लौट आती है। बंद किए गए टैब की लिखावट पाने के लिए फ़ाइल फिर खोलें। जाँच और निर्माण से पहले खुली फ़ाइलें सहेजी जाती हैं।

बाईं ओर परियोजना की फ़ाइलें दिखती हैं। फ़ोल्डर खोलें और पाठ फ़ाइल पर दो बार क्लिक करें। किसी फ़ोल्डर पर दायाँ क्लिक करके उसमें फ़ाइल या फ़ोल्डर बनाएँ या फ़ाइल आयात करें। हर टैब पर उसे बंद करने का चिह्न है। भाष फ़ाइल में शब्द डालें और रचना डालें से लिखावट जोड़ें। भाष के आरक्षित शब्द बैंगनी रंग में दिखाई देते हैं। लिखते समय नीचे और ऊपर के तीर से सुझाव चुनें। टैब या एंटर से उसे डालें और एस्केप से सूची बंद करें।

पूर्वावलोकन केवल दृश्य की बनावट दिखाता है। बटन का भाष फलन उपकरण पर चलता है। पूरी भाष जाँच निर्माण के समय कंपाइलर करता है।

संपादन मेनू या दाएँ क्लिक से पाठ की प्रतिलिपि बनाएँ और संपादन योग्य स्थान पर चिपकाएँ। त्रुटि, फलन सहायता और कार्य विवरण से भी पाठ चुनकर प्रतिलिपि बना सकते हैं। पुराने पैकेज और निर्माण विवरण हटाने के लिए bhash-studio-builds पर दायाँ क्लिक करके पूर्व निर्माण हटाओ चुनें।

औज़ार में आधिकारिक भाष कंपाइलर 0.25.0 की जार फ़ाइल, जावा कार्यक्रम और एंड्रॉयड औज़ार फ़ोल्डर चुनें। एंड्रॉयड स्तर 36, निर्माण औज़ार 35.0.0 और मूल विकास औज़ार 28.2.13676358 स्थापित होने चाहिए।

फ़ाइल मेनू से नई फ़ाइल बनाएँ या बाहर की फ़ाइल की प्रति परियोजना में आयात करें। एंड्रॉयड निर्यात से उत्पन्न परियोजना बनाएँ। ऐप बनाएँ से परीक्षण पैकेज बनाएँ। उपकरण पर चलाएँ से पैकेज बनाकर चालू एमुलेटर या अधिकृत फ़ोन पर स्थापित करें। एक से अधिक उपकरण होने पर औज़ार में उपकरण की पहचान लिखें। निर्माण के परिणाम परियोजना के bhash-studio-builds फ़ोल्डर में मिलेंगे।

डेस्कटॉप और वेब लक्ष्य अगले चरण में आएँगे। उन्नत संपादन, चरणबद्ध दोष जाँच और हस्ताक्षरित प्रकाशन अगले चरण के काम हैं।
'''


class Form(tk.Toplevel):
    def __init__(self, parent, title, fields, action="स्वीकार करें", paths=None):
        super().__init__(parent)
        enable_hindi_input(self)
        self.title(title)
        self.result = None
        self.transient(parent)
        self.resizable(True, False)
        self.columnconfigure(1, weight=1)
        self.entries = {}
        self.paths = paths or {}
        for index, (key, label, value) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=12, pady=8, sticky="w")
            entry = ttk.Entry(self, width=65)
            enable_clipboard(entry)
            entry.insert(0, value)
            entry.grid(row=index, column=1, padx=12, pady=8, sticky="ew")
            self.entries[key] = entry
            if key in self.paths:
                entry.configure(state="readonly")
                ttk.Button(self, text="चुनें…", command=lambda key=key, label=label: self.browse(key, label)).grid(
                    row=index, column=2, padx=(0, 12), pady=8,
                )
        actions = ttk.Frame(self)
        actions.grid(row=len(fields), column=0, columnspan=3, pady=12)
        ttk.Button(actions, text=action, command=self.accept).pack(side="left", padx=8)
        ttk.Button(actions, text="रद्द करें", command=self.destroy).pack(side="left", padx=8)
        self.bind("<Escape>", lambda _: self.destroy())
        self.grab_set()
        next(iter(self.entries.values())).focus_set()

    def accept(self):
        self.result = {key: entry.get() if key in self.paths else entry.get().strip()
                       for key, entry in self.entries.items()}
        self.destroy()

    def browse(self, key, title):
        path = choose_path(self, title, self.paths[key])
        if path is not None:
            entry = self.entries[key]
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.configure(state="readonly")


class Studio:
    def __init__(self, root, project=None, tools=None, settings_file=None, compiler_override=None):
        self.root = root
        self.syntax_pool = ThreadPoolExecutor(max_workers=1)
        self.signature_pool = ThreadPoolExecutor(max_workers=1)
        self.language_server = LanguageServer()
        enable_hindi_input(root)
        self.project = None
        self.buffers = {}
        self.hashes = {}
        self.active = None
        self.editors = {}
        self.file_states = {}
        self.pressed_close = None
        self.tools = tools or Toolchain.discover()
        self.device = ""
        self.settings_file = settings_file if settings_file is not None else settings_path()
        self.session_file = self.settings_file.with_name("session.json")
        settings_error = None
        try:
            self.tools, self.device = load_settings(self.settings_file, self.tools)
        except StudioError as error:
            settings_error = str(error)
        self.compiler_override = compiler_override
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        root.title(APP_NAME)
        root.geometry("1280x820")
        root.minsize(920, 620)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TLabel", font=("Nirmala UI", 11))
        style.configure("TButton", font=("Nirmala UI", 11), padding=6)
        self.create_menu_bar()
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=14)
        self.explorer = ProjectTree(panes, self.select_file, self.guard,
                                    self.new_file, self.new_folder, self.import_file, self.trash_files,
                                    self.cleanup_builds)
        self.explorer.configure(width=240)
        panes.add(self.explorer, weight=0)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        helpers = ttk.Frame(left)
        helpers.pack(fill="x", pady=(6, 0))
        self.configure_tab_style(style)
        self.notebook = ttk.Notebook(left, style="Yantra.TNotebook")
        self.notebook.pack(fill="both", expand=True, pady=6)
        self.notebook.enable_traversal()
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)
        self.notebook.bind("<ButtonPress-1>", self.press_tab_close)
        self.notebook.bind("<ButtonRelease-1>", self.release_tab_close)
        self.helpers = [
            self.insertion_menu(helpers, "शब्द डालें", ((word, (word, "")) for word in KEYWORDS)),
            self.insertion_menu(helpers, "रचना डालें", CONSTRUCTS.items()),
        ]
        self.preview = tk.Frame(right, background="#ffffff", padx=20, pady=20)
        self.preview.pack(fill="both", expand=True, padx=(12, 0), pady=6)
        ttk.Label(root, text="कार्य विवरण").pack(anchor="w", padx=18)
        self.output = ReadOnlyText(root, height=5, wrap="word", font=("Nirmala UI", 11), padx=10)
        self.output.pack(fill="x", padx=14, pady=(4, 10))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.log("नई परियोजना बनाएँ या पहले से बनी परियोजना खोलें।")
        if settings_error:
            self.log(settings_error)
        if project:
            self.load(project)
        self.poll_timer = root.after(100, self.poll)
        root.bind("<Destroy>", self.stop_polling)

    @property
    def editor(self):
        return self.editors.get(self.active)

    def configure_tab_style(self, style):
        icon = self.tab_close_image = tk.PhotoImage(master=self.root, width=14, height=14)
        for offset in range(4, 10):
            icon.put("#334155", (offset, offset))
            icon.put("#334155", (13 - offset, offset))
        if "Yantra.close" not in style.element_names():
            style.element_create("Yantra.close", "image", icon, sticky="")
        style.layout("Yantra.TNotebook.Tab", [
            ("Notebook.tab", {"sticky": "nswe", "children": [
                ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                    ("Notebook.label", {"side": "left", "sticky": ""}),
                    ("Yantra.close", {"side": "left", "sticky": ""}),
                ]}),
            ]}),
        ])

    def close_at(self, event):
        if self.notebook.identify(event.x, event.y) == "Yantra.close":
            index = self.notebook.index(f"@{event.x},{event.y}")
            return list(self.editors)[index]
        return None

    def press_tab_close(self, event):
        self.pressed_close = self.close_at(event)
        if self.pressed_close is not None:
            return "break"

    def release_tab_close(self, event):
        filename, self.pressed_close = self.pressed_close, None
        if filename is not None:
            if filename == self.close_at(event):
                self.guard(lambda: self.close_tab(filename))
            return "break"

    def open_tab(self, filename):
        frame = ttk.Frame(self.notebook)
        source_mode = Path(filename).suffix == ".bhash"
        editor = BhashEditor(frame, syntax_check=self.submit_syntax,
                             compiler_path=lambda: self.compiler_override or self.tools.compiler,
                             signature_check=lambda caret, site: self.submit_signature(filename, caret, site),
                             undo=True, wrap="none", font=("Nirmala UI", 13),
                             padx=12, pady=12, background="#f7f9fc", foreground="#182d43", insertwidth=2)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=editor.xview)
        editor.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        editor.grid(row=0, column=0, sticky="nsew")
        enable_clipboard(editor)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        if source_mode:
            status = ReadOnlyText(frame, height=3, width=1, wrap="word", relief="flat",
                                  background=ttk.Style(frame).lookup("TFrame", "background"),
                                  font=("Nirmala UI", 11))
            status.grid(row=2, column=0, sticky="ew")
            status.grid_remove()

            def update_status(*_):
                value = editor.syntax_status.get()
                status.set_text(value)
                if value:
                    status.configure(height=3 if len(value) > 120 else 1)
                    status.grid()
                else:
                    status.grid_remove()

            trace = editor.syntax_status.trace_add("write", update_status)
            status.bind("<Destroy>", lambda _: editor.syntax_status.trace_remove("write", trace))
            self.add_signature_panel(frame, editor)
        state = self.file_states.get(filename, {})
        editor.open_buffer(state.get("text", self.buffers[filename]), source_mode)
        cursor = state.get("cursor")
        if isinstance(cursor, str):
            editor.mark_set("insert", cursor)
        if "x" in state or "y" in state:
            editor.bind("<Map>", lambda _event: self.restore_view(editor, state))
        self.editors[filename] = editor
        self.notebook.add(frame, text=filename)
        return editor

    def submit_syntax(self, source):
        tools = replace(self.tools, compiler=self.compiler_override) if self.compiler_override else self.tools
        return self.syntax_pool.submit(check_syntax, tools, source)

    def submit_signature(self, filename, caret, site):
        tools = replace(self.tools, compiler=self.compiler_override) if self.compiler_override else self.tools
        buffers = {name: self.file_text(name) for name in self.editors if name.endswith(".bhash")}
        return self.signature_pool.submit(self.language_server.help, tools, self.project, filename, buffers, caret, site)

    def add_signature_panel(self, frame, editor):
        panel = ttk.Frame(frame, padding=(6, 4))
        panel.grid(row=3, column=0, sticky="ew")
        panel.columnconfigure(0, weight=1)
        text = ReadOnlyText(panel, width=1, height=3, wrap="word", relief="flat",
                            background=ttk.Style(frame).lookup("TFrame", "background"),
                            font=("Nirmala UI", 11))
        text.grid(row=0, column=0, sticky="ew")
        link = ttk.Button(panel, text="GitHub संदर्भ")
        link.grid(row=1, column=0, sticky="w")
        panel.grid_remove()

        def display(help):
            if not help:
                panel.grid_remove()
                return
            lines = list(help.signatures[:4])
            if len(help.signatures) > 4:
                lines.append(f"और {len(help.signatures) - 4} रूप")
            if help.parameter:
                lines.append(f"वर्तमान मापदंड — {help.parameter}")
            if help.description:
                lines.append(help.description)
            text.set_text("\n".join(lines))
            text.configure(height=min(8, len(lines) + bool(help.description)))
            if help.url:
                link.configure(command=lambda: webbrowser.open(help.url))
                link.grid()
            else:
                link.grid_remove()
            panel.grid()

        editor.signature_display = display

    def restore_view(self, editor, state):
        editor.unbind("<Map>")
        for axis, move in (("x", editor.xview_moveto), ("y", editor.yview_moveto)):
            position = state.get(axis)
            if isinstance(position, (int, float)) and 0 <= position <= 1:
                move(position)

    def insertion_menu(self, parent, label, entries):
        button = ttk.Menubutton(parent, text=label, state="disabled")
        menu = tk.Menu(button, tearoff=False)
        for index, (name, parts) in enumerate(entries):
            menu.add_command(label=name, columnbreak=index > 0 and index % 18 == 0,
                             command=lambda parts=parts: self.editor.insert_helper(*parts))
        button.configure(menu=menu)
        button.pack(side="left", padx=(0, 6))
        return button

    def create_menu_bar(self):
        self.menu_bar = tk.Menu(self.root, tearoff=False)
        self.menu_items = {}
        self.root.configure(menu=self.menu_bar)
        mac = self.root.tk.call("tk", "windowingsystem") == "aqua"
        modifier = "Command" if mac else "Control"
        accelerator = "⌘" if mac else "Ctrl+"

        def dropdown(label):
            menu = tk.Menu(self.menu_bar, tearoff=False)
            self.menu_bar.add_cascade(label=label, menu=menu)
            return menu

        def add(menu, key, label, command, shortcut=None, hint=""):
            menu.add_command(label=label, command=lambda: self.guard(command), accelerator=hint)
            index = menu.index("end")
            self.menu_items[key] = (menu, index)
            if shortcut:
                def invoke(_event):
                    menu.invoke(index)
                    return "break"
                self.root.bind(shortcut, invoke)

        file_menu = dropdown("फ़ाइल")
        add(file_menu, "new", "नई परियोजना…", self.new_project, f"<{modifier}-n>", accelerator + "N")
        add(file_menu, "open", "परियोजना खोलें…", self.open_project, f"<{modifier}-o>", accelerator + "O")
        file_menu.add_separator()
        add(file_menu, "new_file", "नई फ़ाइल…", self.new_file)
        add(file_menu, "import_file", "फ़ाइल आयात करें…", self.import_file)
        file_menu.add_separator()
        add(file_menu, "save", "वर्तमान फ़ाइल सहेजें", self.save_current, f"<{modifier}-s>", accelerator + "S")
        add(file_menu, "close_tab", "वर्तमान फ़ाइल बंद करें", self.close_tab, f"<{modifier}-w>", accelerator + "W")
        self.selected_file = tk.StringVar(self.root)
        file_picker = tk.Menu(file_menu, tearoff=False)
        for filename in FILES:
            file_picker.add_radiobutton(
                label=filename, value=filename, variable=self.selected_file,
                command=lambda name=filename: self.guard(lambda: self.select_file(name)),
            )
        file_menu.add_cascade(label="फ़ाइल बदलें", menu=file_picker)
        self.menu_items["files"] = (file_menu, file_menu.index("end"))
        file_menu.add_separator()
        add(file_menu, "exit", "बंद करें", self.close)

        edit_menu = dropdown("संपादन")
        for action, label, key in COMMANDS:
            edit_menu.add_command(label=label, accelerator=accelerator + key.upper(),
                                  command=lambda action=action: clipboard_action(self.root.focus_get(), action))

        project_menu = dropdown("परियोजना")
        add(project_menu, "check", "परियोजना जाँचें", self.validate)

        android_menu = dropdown("एंड्रॉयड")
        add(android_menu, "export", "एंड्रॉयड निर्यात", lambda: self.start_job("export"))
        add(android_menu, "build", "ऐप बनाएँ", lambda: self.start_job("build"))
        add(android_menu, "run", "उपकरण पर चलाएँ", lambda: self.start_job("run"))
        android_menu.add_separator()
        add(android_menu, "stop", "काम रोकें", self.cancel.set)

        add(dropdown("औज़ार"), "tools", "औज़ार सेटिंग…", self.settings)
        add(dropdown("सहायता"), "help", "भाष यंत्र सहायता", self.help, "<F1>", "F1")
        self.update_menu_state()

    def update_menu_state(self):
        busy = self.worker is not None
        for key, (menu, index) in self.menu_items.items():
            if key == "stop":
                enabled = busy
            elif key in {"files", "new_file", "import_file"}:
                enabled = self.project is not None
            elif key == "close_tab":
                enabled = self.active is not None
            elif key == "save":
                enabled = self.active is not None and not busy
            elif key in {"check", "export", "build", "run"}:
                enabled = all(name in self.buffers for name in FILES) and not busy
            else:
                enabled = not busy or key == "exit"
            menu.entryconfigure(index, state="normal" if enabled else "disabled")

    def guard(self, action):
        try:
            return action()
        except StudioError as error:
            self.log(str(error))
        except (OSError, UnicodeError):
            self.log("फ़ाइल नहीं पढ़ी या सहेजी जा सकी। उसका मार्ग, खाली स्थान और अनुमति जाँचें।")

    def log(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def file_text(self, filename):
        editor = self.editors.get(filename)
        return editor.get("1.0", "end-1c") if editor is not None else self.buffers[filename]

    def select_file(self, filename):
        if not self.project:
            return
        editor = self.editors.get(filename)
        if editor is None:
            if filename not in self.buffers:
                self.project.file(filename)
                try:
                    text = self.project.read(filename)
                except (StudioError, OSError):
                    if "text" not in self.file_states.get(filename, {}):
                        raise
                    text = None
                    self.log(f"मूल फ़ाइल नहीं मिली या पढ़ी नहीं जा सकी। अस्थायी लिखावट खोली गई — {filename}")
                self.buffers[filename] = text
                if text is not None:
                    self.hashes[filename] = digest(text)
            state = self.file_states.get(filename, {})
            if "text" in state and state["text"] != self.buffers[filename]:
                if filename in self.hashes and self.hashes[filename] != state["hash"]:
                    self.log(f"फ़ाइल बाहर से बदली गई है। अस्थायी लिखावट अलग रखी गई — {filename}")
                self.hashes[filename] = state["hash"]
            editor = self.open_tab(filename)
        self.notebook.select(editor.master)
        self.tab_changed()
        editor.focus_set()

    def tab_changed(self, _event=None):
        page = self.notebook.select()
        self.active = next((name for name, editor in self.editors.items() if str(editor.master) == page), None)
        self.selected_file.set(self.active or "")
        for helper in self.helpers:
            helper.configure(state="normal" if self.editor and self.editor.source_mode else "disabled")
        self.update_menu_state()

    def close_tab(self, filename=None):
        filename = self.active if filename is None else filename
        if filename not in self.editors or self.closing:
            return
        tabs = list(self.editors)
        index = tabs.index(filename)
        tabs.remove(filename)
        active = self.active
        if active == filename:
            active = tabs[min(index, len(tabs) - 1)] if tabs else None
        self.persist_project(tabs, active)
        self.forget_tab(filename, active)

    def forget_tab(self, filename, active=None):
        page = self.editors.pop(filename).master
        self.notebook.forget(page)
        page.destroy()
        if filename not in FILES:
            self.buffers.pop(filename)
            self.hashes.pop(filename)
        if active is not None:
            self.notebook.select(self.editors[active].master)
        self.tab_changed()

    def persist_project(self, tabs, active):
        states = self.file_states.copy()
        for name, editor in self.editors.items():
            state = {"cursor": editor.index("insert"), "x": editor.xview()[0], "y": editor.yview()[0]}
            text = self.file_text(name)
            if text != self.buffers[name]:
                state.update(text=text, hash=self.hashes[name])
            if name in tabs or "text" in state:
                states[name] = state
            else:
                states.pop(name, None)
        save_project_session(self.project, tabs, active, states)
        self.file_states = states

    def load(self, project):
        if self.project is not None:
            if self.project.root == project.root:
                return
            self.persist_project(list(self.editors), self.active)
        self.open_workspace(project, [SOURCE], SOURCE)

    def show_project(self, project, snapshot):
        for editor in self.editors.values():
            editor.master.destroy()
        self.editors.clear()
        self.file_states = {}
        self.project = project
        self.buffers = snapshot
        self.hashes = {name: digest(text) for name, text in snapshot.items()}
        self.update_project_title()
        self.guard(lambda: self.explorer.set_project(project))
        self.tab_changed()

    def restore_session(self):
        try:
            session = load_session(self.session_file)
            if session is None:
                return
            path, tabs, active = session
            folder = LocalPath(path).resolve()
            if not folder.is_dir():
                self.log(f"पिछली परियोजना का फ़ोल्डर नहीं मिला — {path}")
                return
        except (StudioError, OSError, ValueError, RuntimeError) as error:
            message = str(error) if isinstance(error, StudioError) else "पिछली परियोजना का फ़ोल्डर नहीं खोला जा सका।"
            self.log(message)
            return

        self.open_workspace(Project(folder), tabs, active)
        self.log("पिछली परियोजना फिर खोल दी गई।")

    def open_workspace(self, project, tabs, active):
        snapshot = {}
        missing = set()
        for filename in FILES:
            try:
                snapshot[filename] = project.read(filename)
            except (StudioError, OSError):
                missing.add(filename)
                self.log(f"पिछली परियोजना की आवश्यक फ़ाइल नहीं खुली — {filename}")
        self.show_project(project, snapshot)
        try:
            saved = load_project_session(project)
            if saved is not None:
                tabs, active, self.file_states = saved
        except (StudioError, OSError, ValueError, RuntimeError) as error:
            self.log(str(error))
        for filename in tabs:
            if filename in missing and "text" not in self.file_states.get(filename, {}):
                continue
            try:
                self.select_file(filename)
            except (StudioError, OSError, ValueError, RuntimeError):
                self.log(f"पहले खुली फ़ाइल अब नहीं खोली जा सकी — {filename}")
        selected = active if active in self.editors else next(iter(self.editors), None)
        if selected is not None:
            self.select_file(selected)
        if not missing:
            self.guard(self.refresh_preview)

    def update_project_title(self):
        name = self.project.root.name
        try:
            config = loads(self.buffers.get(CONFIG, ""))
            if isinstance(config, dict) and isinstance(config.get("नाम"), str):
                name = config["नाम"].strip() or name
        except StudioError:
            pass
        self.root.title(f"{APP_NAME} — {name}")

    def new_project(self):
        dialog = Form(self.root, "नई परियोजना", [("name", "ऐप का नाम", "मेरा पहला ऐप"),
                      ("folder", "नए फ़ोल्डर का नाम", "मेरा-ऐप"),
                      ("directory", "मूल फ़ोल्डर", str(Path.cwd()))],
                      "परियोजना बनाएँ", paths={"directory": None})
        self.root.wait_window(dialog)
        if dialog.result:
            folder = dialog.result["folder"]
            if not folder or folder in {".", ".."} or Path(folder).name != folder or any(c in folder for c in "/\\"):
                raise StudioError("नए फ़ोल्डर के लिए केवल उसका नाम लिखें। मूल फ़ोल्डर अलग से चुनें।")
            self.load(Project.create(Path(dialog.result["directory"]) / folder, dialog.result["name"]))

    def open_project(self):
        path = choose_path(self.root, f"‘{CONFIG}’ फ़ाइल चुनें", lambda path: path.name == CONFIG)
        if path is not None:
            self.load(Project.open(path))

    def new_file(self, folder=""):
        dialog = Form(self.root, "नई फ़ाइल", [("name", "फ़ाइल का नाम", "")], "बनाएँ")
        self.root.wait_window(dialog)
        if dialog.result:
            filename = dialog.result["name"]
            self.project.add_file(filename, folder=folder)
            self.explorer.refresh(folder)
            self.select_file((Path(folder) / filename).as_posix())

    def new_folder(self, folder=""):
        dialog = Form(self.root, "नया फ़ोल्डर", [("name", "फ़ोल्डर का नाम", "")], "बनाएँ")
        self.root.wait_window(dialog)
        if dialog.result:
            self.project.add_folder(dialog.result["name"], folder)
            self.explorer.refresh(folder)

    def import_file(self, folder=""):
        path = choose_path(self.root, "आयात करने वाली फ़ाइल चुनें", lambda _path: True)
        if path is not None:
            source = LocalPath(path)
            self.project.add_file(source.name, source, folder)
            self.explorer.refresh(folder)
            self.log(f"परियोजना में फ़ाइल की प्रति रखी गई — {source.name}")

    def trash_files(self, names):
        if not self.project or not names or self.closing:
            return
        paths = [(name, self.project.file(name)) for name in names]
        for name, path in paths:
            if not path.is_file():
                raise StudioError(f"फ़ाइल नहीं मिली — {name}")
        if not messagebox.askokcancel(
            "फ़ाइलें कूड़ेदान में भेजें",
            f"{len(paths)} चुनी हुई फ़ाइलें कूड़ेदान में भेजें?",
            parent=self.root, default=messagebox.CANCEL,
        ):
            return
        self.persist_project(list(self.editors), self.active)
        count = 0
        for name, path in paths:
            try:
                move_to_trash(path)
            except OSError as error:
                self.log(f"फ़ाइल कूड़ेदान में नहीं भेजी जा सकी — {name}\n{error}")
                continue
            count += 1
            if name in self.editors:
                self.forget_tab(name)
            self.buffers.pop(name, None)
            self.hashes.pop(name, None)
            if "text" not in self.file_states.get(name, {}):
                self.file_states.pop(name, None)
            if name in FILES:
                for widget in self.preview.winfo_children():
                    widget.destroy()
        self.explorer.refresh()
        self.update_menu_state()
        if count:
            self.persist_project(list(self.editors), self.active)
            self.log(f"{count} फ़ाइलें कूड़ेदान में भेज दी गईं।")

    def cleanup_builds(self):
        if not self.project or self.closing:
            return
        if self.worker is not None:
            raise StudioError("निर्माण हटाने से पहले चल रहा काम पूरा होने दें या उसे रोकें।")
        project = self.project
        names = project.previous_builds()
        if not names:
            self.log("हटाने के लिए कोई पूर्व निर्माण नहीं मिला।")
            return
        if not messagebox.askokcancel(
            "पूर्व निर्माण हटाओ",
            f"{len(names)} पूर्व निर्माण स्थायी रूप से हटाएँ? उनके पैकेज और कार्य विवरण भी हटेंगे।",
            parent=self.root, default=messagebox.CANCEL, icon=messagebox.WARNING,
        ):
            return
        prefixes = tuple(f"{BUILD_DIRECTORY}/{name}/" for name in names)
        for filename in list(self.editors):
            if filename.startswith(prefixes):
                self.close_tab(filename)

        def cleanup():
            removed = 0
            for name in names:
                if self.cancel.is_set():
                    break
                try:
                    if project.remove_build(name):
                        removed += 1
                except (OSError, StudioError) as error:
                    self.messages.put(f"निर्माण नहीं हट सका — {name}\n{error}")
            self.messages.put(f"{removed} पूर्व निर्माण हटाए गए।")

        self.start_worker(cleanup)

    def save_current(self):
        if self.active is None:
            raise StudioError("पहले परियोजना की कोई फ़ाइल खोलें।")
        self.save_file(self.active)
        self.log("फ़ाइल सहेज दी गई।")

    def save_file(self, filename):
        text = self.file_text(filename)
        self.hashes[filename] = self.project.save(filename, text, self.hashes[filename])
        self.buffers[filename] = text
        self.file_states.pop(filename, None)
        if filename == CONFIG:
            self.update_project_title()

    def save_all(self):
        if not self.project:
            raise StudioError("पहले एक परियोजना खोलें।")
        for name in FILES:
            self.save_file(name)
        for name in self.editors:
            if name not in FILES and self.file_text(name) != self.buffers[name]:
                self.save_file(name)

    def refresh_preview(self, snapshot=None):
        if snapshot is None:
            snapshot = self.project.snapshot()
            snapshot.update((name, self.file_text(name)) for name in self.editors if name in snapshot)
        _, screen = validate_snapshot(snapshot)
        for widget in self.preview.winfo_children():
            widget.destroy()
        tk.Label(self.preview, text=screen.title, font=("Nirmala UI", 18, "bold"), bg="white", wraplength=350).pack(anchor="w", pady=(0, 18))

        def render(node, parent, side="top"):
            if node.children or node.kind in {"स्तंभ", "पंक्ति"}:
                frame = tk.Frame(parent, bg="white")
                frame.pack(side=side, anchor="nw", padx=4, pady=4)
                for child in node.children:
                    render(child, frame, "left" if node.kind == "पंक्ति" else "top")
            elif node.kind == "पाठ":
                tk.Label(parent, text=node.text, font=("Nirmala UI", 13), bg="white", wraplength=330).pack(side=side, anchor="w", pady=8)
            elif node.kind == "प्रविष्टि":
                field = tk.Frame(parent, bg="white")
                field.pack(side=side, anchor="w", pady=8)
                ttk.Label(field, text=node.text).pack(anchor="w")
                entry = ttk.Entry(field, font=("Nirmala UI", 13))
                enable_clipboard(entry)
                entry.insert(0, node.initial)
                entry.configure(state="readonly")
                entry.pack(anchor="w")
            else:
                ttk.Button(parent, text=node.text, state="disabled").pack(side=side, anchor="w", padx=4, pady=8)

        render(screen.content, self.preview)

    def validate(self):
        self.save_all()
        snapshot = self.project.snapshot()
        self.refresh_preview(snapshot)
        self.log("विन्यास, दृश्य और बटन के फलन रूप की जाँच सफल। पूरी भाष जाँच निर्माण में होगी।")
        return snapshot

    def settings(self):
        dialog = Form(self.root, "औज़ार सेटिंग", [("compiler", "आधिकारिक भाष कंपाइलर की जार फ़ाइल", self.tools.compiler),
                      ("java", "जावा कार्यक्रम", self.tools.java),
                      ("sdk", "एंड्रॉयड औज़ार फ़ोल्डर", self.tools.sdk),
                      ("device", "उपकरण की पहचान — वैकल्पिक", self.device)],
                      paths={"compiler": jar_file, "java": java_program, "sdk": None})
        self.root.wait_window(dialog)
        if dialog.result:
            values = dialog.result
            tools = Toolchain(values["compiler"], values["java"], values["sdk"])
            save_settings(self.settings_file, tools, values["device"])
            self.tools = tools
            self.device = values["device"]
            for editor in self.editors.values():
                editor.schedule_syntax()
            self.log("औज़ार सेटिंग सहेज दी गई। अगली बार भी यही सेटिंग उपयोग में आएगी।")

    def help(self):
        window = tk.Toplevel(self.root)
        window.title(f"{APP_NAME} सहायता")
        window.transient(self.root)
        window.bind("<Escape>", lambda _event: window.destroy())
        # Use explicit line breaks instead of Tk's native wrapped layout for long Hindi paragraphs.
        text = ReadOnlyText(window, wrap="none", width=80, height=30, font=("Nirmala UI", 12), padx=16, pady=16)
        vertical = ttk.Scrollbar(window, orient="vertical", command=text.yview)
        horizontal = ttk.Scrollbar(window, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        text.pack(fill="both", expand=True)
        text.set_text("\n\n".join(fill(paragraph, width=76, break_long_words=False, break_on_hyphens=False)
                                  for paragraph in HELP.strip().split("\n\n")))
        text.focus_set()

    def start_job(self, operation):
        if self.worker is not None:
            raise StudioError("पहला कार्य पूरा होने दें या उसे रोकें।")
        snapshot = self.validate()
        project = self.project
        tools = replace(self.tools, compiler=self.compiler_override) if self.compiler_override else self.tools
        device = self.device
        def work():
            try:
                result = AndroidTarget(tools).execute(project, snapshot, operation, self.cancel, self.messages.put, device)
                self.messages.put("कार्य पूरा हुआ। निर्माण फ़ोल्डर — " + str(result))
            except StudioError as error:
                self.messages.put(str(error))
            except Exception:
                self.messages.put("कार्य पूरा नहीं हो सका। फ़ाइल मार्ग और औज़ार सेटिंग जाँचें।")
        self.start_worker(work)

    def start_worker(self, action):
        self.cancel.clear()

        def work():
            try:
                action()
            finally:
                self.messages.put(None)

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.update_menu_state()

    def poll(self):
        self.root.after_cancel(self.poll_timer)
        try:
            while True:
                message = self.messages.get_nowait()
                if message is None:
                    self.worker = None
                    self.update_menu_state()
                    self.guard(self.explorer.refresh)
                else:
                    self.log(message)
        except queue.Empty:
            pass
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.poll_timer = self.root.after(100, self.poll)

    def stop_polling(self, event):
        if event.widget is self.root:
            self.root.after_cancel(self.poll_timer)
            self.syntax_pool.shutdown(wait=False, cancel_futures=True)
            self.signature_pool.submit(self.language_server.close)
            self.signature_pool.shutdown(wait=False)

    def close(self):
        if self.closing:
            return
        if self.project is not None:
            try:
                self.persist_project(list(self.editors), self.active)
                save_session(self.session_file, self.project.root, self.editors, self.active)
            except (StudioError, OSError, ValueError, RuntimeError) as error:
                self.log(str(error))
                return
        self.closing = True
        for editor in self.editors.values():
            editor.configure(state="disabled")
        self.cancel.set()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--project", help="परियोजना फ़ोल्डर")
    parser.add_argument("--compiler", help="भाष कंपाइलर की जार फ़ाइल")
    options = parser.parse_args()
    root = tk.Tk()
    studio = Studio(root, compiler_override=options.compiler)
    if options.project:
        studio.guard(lambda: studio.load(Project.open(options.project)))
    else:
        studio.restore_session()
    root.mainloop()
