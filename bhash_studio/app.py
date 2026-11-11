"""Small, dependency-free desktop prototype. All developer-facing text is Hindi."""

import argparse
from dataclasses import replace
from pathlib import Path
import queue
from textwrap import fill
import threading
import tkinter as tk
from tkinter import ttk

from .android import AndroidTarget, Toolchain
from .bhash_syntax import COMMON_KEYWORDS, CONSTRUCTS
from .config import loads
from .editor import BhashEditor
from .errors import StudioError
from .path_picker import choose_path, jar_file, java_program
from .project import CONFIG, FILES, SOURCE, Project, digest
from .project_tree import ProjectTree
from .settings import load_settings, save_settings, settings_path
from .targets import validate_snapshot


APP_NAME = "भाष यंत्र"
HELP = '''भाष यंत्र में आपका स्वागत है

नई परियोजना के लिए ऐप का नाम और नए फ़ोल्डर का नाम लिखें। उसका मूल फ़ोल्डर चुनें। पहले से बनी परियोजना खोलने के लिए उसकी परियोजना.भाषविन्यास फ़ाइल चुनें।

परियोजना.भाषविन्यास में नाम, लक्ष्य और अनुमतियाँ हैं। सत्य, असत्य और रिक्त भाष के मूल मान हैं। ऐप की पहचान बनाए रखें, ताकि उसके अद्यतन उसी ऐप पर लगें।

पर्दा.भाषदृश्य में स्तंभ, पंक्ति, पाठ, प्रविष्टि और बटन लिखें। प्रविष्टि और परिणाम दिखाने वाले पाठ को अलग पहचान दें। बटन के इनपुटसे में प्रविष्टि की पहचान और परिणाममें में पाठ की पहचान लिखें। दबानेपर वाला फलन मुख्य.bhash में एक पाठ लेता है और एक पाठ लौटाता है।

सहेजें से खुली फ़ाइल सहेजें। फ़ाइल बदलने पर आपकी अधूरी लिखावट बनी रहती है। जाँचें और निर्माण के समय सभी फ़ाइलें सहेजी जाती हैं। बाहर बदली गई फ़ाइल मिलने पर अपनी लिखावट की प्रति बनाकर परियोजना फिर खोलें।

बाईं ओर परियोजना की फ़ाइलें दिखती हैं। फ़ोल्डर खोलें और पाठ फ़ाइल पर दो बार क्लिक करें। हर खुली फ़ाइल का अपना टैब है। फ़ाइल मेनू से चुना हुआ टैब बंद करें। भाष फ़ाइल में शब्द डालें और रचना डालें से लिखावट जोड़ें। भाष के आरक्षित शब्द बैंगनी रंग में दिखाई देते हैं। लिखते समय नीचे और ऊपर के तीर से सुझाव चुनें। टैब या एंटर से उसे डालें और एस्केप से सूची बंद करें।

पूर्वावलोकन केवल दृश्य की बनावट दिखाता है। बटन का भाष फलन उपकरण पर चलता है। पूरी भाष जाँच निर्माण के समय कंपाइलर करता है।

औज़ार में आधिकारिक भाष कंपाइलर 0.25.0 की जार फ़ाइल, जावा कार्यक्रम और एंड्रॉयड औज़ार फ़ोल्डर चुनें। एंड्रॉयड स्तर 36, निर्माण औज़ार 35.0.0 और मूल विकास औज़ार 28.2.13676358 स्थापित होने चाहिए।

एंड्रॉयड निर्यात से चुने हुए निर्माण फ़ोल्डर में पूरी परियोजना बनाएँ। विंडोज़ पर निर्माण फ़ोल्डर के मार्ग में अंग्रेज़ी अक्षर और अंक रखें। आपकी संपादित परियोजना हिंदी में रह सकती है। ऐप बनाएँ से परीक्षण पैकेज बनाएँ। उपकरण पर चलाएँ से पैकेज बनाकर चालू एमुलेटर या अधिकृत फ़ोन पर स्थापित करें। एक से अधिक उपकरण होने पर औज़ार में उपकरण की पहचान लिखें। डिफ़ॉल्ट निर्माण स्थान अस्थायी है। रखने योग्य पैकेज की स्थायी प्रति बनाएँ।

डेस्कटॉप और वेब लक्ष्य अगले चरण में आएँगे। उन्नत संपादन, चरणबद्ध दोष जाँच और हस्ताक्षरित प्रकाशन अगले चरण के काम हैं।
'''


class Form(tk.Toplevel):
    def __init__(self, parent, title, fields, action="स्वीकार करें", paths=None):
        super().__init__(parent)
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
        self.project = None
        self.buffers = {}
        self.hashes = {}
        self.active = None
        self.editors = {}
        self.tools = tools or Toolchain.discover()
        self.device = ""
        self.settings_file = settings_file if settings_file is not None else settings_path()
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
        self.explorer = ProjectTree(panes, self.select_file, self.guard)
        self.explorer.configure(width=240)
        panes.add(self.explorer, weight=0)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        helpers = ttk.Frame(left)
        helpers.pack(fill="x", pady=(6, 0))
        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill="both", expand=True, pady=6)
        self.notebook.enable_traversal()
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)
        self.helpers = [
            self.insertion_menu(helpers, "शब्द डालें", ((word, (word, "")) for word in COMMON_KEYWORDS)),
            self.insertion_menu(helpers, "रचना डालें", CONSTRUCTS.items()),
        ]
        self.preview = tk.Frame(right, background="#ffffff", padx=20, pady=20)
        self.preview.pack(fill="both", expand=True, padx=(12, 0), pady=6)
        ttk.Label(root, text="कार्य विवरण").pack(anchor="w", padx=18)
        self.output = tk.Text(root, height=5, state="disabled", wrap="word", font=("Nirmala UI", 11), padx=10)
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

    def open_tab(self, filename):
        frame = ttk.Frame(self.notebook)
        editor = BhashEditor(frame, undo=True, wrap="none", font=("Nirmala UI", 13),
                             padx=12, pady=12, background="#f7f9fc", foreground="#182d43", insertwidth=2)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=editor.xview)
        editor.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        editor.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        editor.bind("<Control-a>", self.select_all)
        editor.open_buffer(self.buffers[filename], Path(filename).suffix == ".bhash")
        self.editors[filename] = editor
        self.notebook.add(frame, text=filename)
        return editor

    def insertion_menu(self, parent, label, entries):
        button = ttk.Menubutton(parent, text=label, state="disabled")
        menu = tk.Menu(button, tearoff=False)
        for name, parts in entries:
            menu.add_command(label=name, command=lambda parts=parts: self.editor.insert_helper(*parts))
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
        add(file_menu, "save", "वर्तमान फ़ाइल सहेजें", self.save_current, f"<{modifier}-s>", accelerator + "S")
        add(file_menu, "close_tab", "वर्तमान फ़ाइल बंद करें", self.close_tab, f"<{modifier}-w>", accelerator + "W")
        self.selected_file = tk.StringVar(self.root)
        file_picker = tk.Menu(file_menu, tearoff=False)
        for filename in FILES:
            file_picker.add_radiobutton(
                label=filename, value=filename, variable=self.selected_file,
                command=lambda name=filename: self.select_file(name),
            )
        file_menu.add_cascade(label="फ़ाइल बदलें", menu=file_picker)
        self.menu_items["files"] = (file_menu, file_menu.index("end"))
        file_menu.add_separator()
        add(file_menu, "exit", "बंद करें", self.close)

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
            elif key == "files":
                enabled = self.project is not None
            elif key in {"save", "close_tab"}:
                enabled = self.active is not None and not busy
            elif key in {"check", "export", "build", "run"}:
                enabled = self.project is not None and not busy
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

    def select_all(self, _):
        self.editor.tag_add("sel", "1.0", "end-1c")
        return "break"

    def file_text(self, filename):
        editor = self.editors.get(filename)
        return editor.get("1.0", "end-1c") if editor is not None else self.buffers[filename]

    def select_file(self, filename):
        if not self.project:
            return
        editor = self.editors.get(filename)
        if editor is None:
            if filename not in self.buffers:
                text = self.project.read(filename)
                self.buffers[filename] = text
                self.hashes[filename] = digest(text)
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

    def close_tab(self):
        filename = self.active
        if filename is None or (self.file_text(filename) != self.buffers[filename] and not self.confirm_discard()):
            return
        page = self.editors.pop(filename).master
        self.notebook.forget(page)
        page.destroy()
        if filename not in FILES:
            self.buffers.pop(filename)
            self.hashes.pop(filename)
        self.tab_changed()

    def confirm_leave(self):
        if all(self.file_text(name) == self.buffers[name] for name in self.editors):
            return True
        return self.confirm_discard()

    def confirm_discard(self):
        dialog = Form(self.root, "अधूरी लिखावट", [("answer", "लिखावट छोड़ने के लिए ‘छोड़ें’ लिखें", "")], "आगे बढ़ें")
        self.root.wait_window(dialog)
        return dialog.result is not None and dialog.result["answer"] == "छोड़ें"

    def load(self, project):
        snapshot = project.snapshot()
        for editor in self.editors.values():
            editor.master.destroy()
        self.editors.clear()
        self.project = project
        self.buffers = snapshot
        self.hashes = {name: digest(text) for name, text in snapshot.items()}
        self.update_project_title()
        self.guard(lambda: self.explorer.set_project(project))
        self.select_file(SOURCE)
        self.log("परियोजना खोल दी गई।")
        self.guard(self.refresh_preview)

    def update_project_title(self):
        name = self.project.root.name
        try:
            config = loads(self.buffers[CONFIG])
            if isinstance(config, dict) and isinstance(config.get("नाम"), str):
                name = config["नाम"].strip() or name
        except StudioError:
            pass
        self.root.title(f"{APP_NAME} — {name}")

    def new_project(self):
        if not self.confirm_leave():
            return
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
        if not self.confirm_leave():
            return
        path = choose_path(self.root, f"‘{CONFIG}’ फ़ाइल चुनें", lambda path: path.name == CONFIG)
        if path is not None:
            self.load(Project.open(path))

    def save_current(self):
        if self.active is None:
            raise StudioError("पहले परियोजना की कोई फ़ाइल खोलें।")
        self.save_file(self.active)
        self.log("फ़ाइल सहेज दी गई।")

    def save_file(self, filename):
        text = self.file_text(filename)
        self.hashes[filename] = self.project.save(filename, text, self.hashes[filename])
        self.buffers[filename] = text
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

    def refresh_preview(self):
        _, screen = validate_snapshot({name: self.file_text(name) for name in FILES})
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
                entry.insert(0, node.initial)
                entry.configure(state="readonly")
                entry.pack(anchor="w")
            else:
                ttk.Button(parent, text=node.text, state="disabled").pack(side=side, anchor="w", padx=4, pady=8)

        render(screen.content, self.preview)

    def validate(self):
        self.save_all()
        self.refresh_preview()
        self.log("विन्यास, दृश्य और बटन के फलन रूप की जाँच सफल। पूरी भाष जाँच निर्माण में होगी।")

    def settings(self):
        dialog = Form(self.root, "औज़ार सेटिंग", [("compiler", "आधिकारिक भाष कंपाइलर की जार फ़ाइल", self.tools.compiler),
                      ("java", "जावा कार्यक्रम", self.tools.java),
                      ("sdk", "एंड्रॉयड औज़ार फ़ोल्डर", self.tools.sdk),
                      ("workspace", "निर्माण फ़ोल्डर — अक्षर और अंकों वाला मार्ग", self.tools.workspace),
                      ("device", "उपकरण की पहचान — वैकल्पिक", self.device)],
                      paths={"compiler": jar_file, "java": java_program, "sdk": None, "workspace": None})
        self.root.wait_window(dialog)
        if dialog.result:
            values = dialog.result
            tools = Toolchain(values["compiler"], values["java"], values["sdk"], values["workspace"])
            save_settings(self.settings_file, tools, values["device"])
            self.tools = tools
            self.device = values["device"]
            self.log("औज़ार सेटिंग सहेज दी गई। अगली बार भी यही सेटिंग उपयोग में आएगी।")

    def help(self):
        window = tk.Toplevel(self.root)
        window.title(f"{APP_NAME} सहायता")
        window.transient(self.root)
        window.bind("<Escape>", lambda _event: window.destroy())
        # Use explicit line breaks instead of Tk's native wrapped layout for long Hindi paragraphs.
        text = tk.Text(window, wrap="none", width=80, height=30, font=("Nirmala UI", 12), padx=16, pady=16)
        vertical = ttk.Scrollbar(window, orient="vertical", command=text.yview)
        horizontal = ttk.Scrollbar(window, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        text.pack(fill="both", expand=True)
        text.insert("1.0", "\n\n".join(fill(paragraph, width=76, break_long_words=False, break_on_hyphens=False)
                                       for paragraph in HELP.strip().split("\n\n")))
        text.configure(state="disabled")
        text.focus_set()

    def start_job(self, operation):
        if self.worker is not None:
            raise StudioError("पहला कार्य पूरा होने दें या उसे रोकें।")
        self.validate()
        snapshot = {name: self.buffers[name] for name in FILES}
        project = self.project
        tools = replace(self.tools, compiler=self.compiler_override) if self.compiler_override else self.tools
        device = self.device
        self.cancel.clear()

        def work():
            try:
                result = AndroidTarget(tools).execute(project, snapshot, operation, self.cancel, self.messages.put, device)
                self.messages.put("कार्य पूरा हुआ। निर्माण फ़ोल्डर — " + str(result))
            except StudioError as error:
                self.messages.put(str(error))
            except Exception:
                self.messages.put("कार्य पूरा नहीं हो सका। फ़ाइल मार्ग और औज़ार सेटिंग जाँचें।")
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

    def close(self):
        if not self.confirm_leave():
            return
        self.closing = True
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
    root.mainloop()
