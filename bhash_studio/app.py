"""Small, dependency-free desktop prototype. All developer-facing text is Hindi."""

import argparse
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk

from .android import AndroidTarget, Toolchain
from .config import loads
from .errors import StudioError
from .project import CONFIG, FILES, LAYOUT, SOURCE, Project, digest
from .targets import TARGETS, validate_snapshot


HELP = '''भाष विकासशाला में आपका स्वागत है

नई परियोजना के लिए ऐप का नाम और एक नए फ़ोल्डर का पूरा मार्ग लिखें। पहले से बनी परियोजना खोलने के लिए उसका फ़ोल्डर लिखें।

परियोजना.भाषविन्यास में नाम, लक्ष्य और अनुमतियाँ हैं। सत्य, असत्य और रिक्त भाष के मूल मान हैं। ऐप की पहचान बनाए रखें, ताकि उसके अद्यतन उसी ऐप पर लगें।

पर्दा.भाषदृश्य में स्तंभ, पंक्ति, पाठ और बटन लिखें। बटन का दबानेपर गुण मुख्य.bhash के फलन का नाम है। इस प्रारूप में बटन का फलन एक पाठ लेता है और एक पाठ लौटाता है। उसका उत्तर ऐप में नीचे दिखाई देता है।

सहेजें से खुली फ़ाइल सहेजें। फ़ाइल बदलने पर आपकी अधूरी लिखावट बनी रहती है। जाँचें और निर्माण के समय सभी फ़ाइलें सहेजी जाती हैं। बाहर बदली गई फ़ाइल मिलने पर अपनी लिखावट की प्रति बनाकर परियोजना फिर खोलें।

पूर्वावलोकन केवल दृश्य की बनावट दिखाता है। बटन का भाष फलन उपकरण पर चलता है। पूरी भाष जाँच निर्माण के समय कंपाइलर करता है।

औज़ार में आधिकारिक भाष कंपाइलर 0.25.0 की जार फ़ाइल, जावा कार्यक्रम और एंड्रॉयड औज़ार का मार्ग लिखें। एंड्रॉयड स्तर 36, निर्माण औज़ार 35.0.0 और मूल विकास औज़ार 28.2.13676358 स्थापित होने चाहिए।

एंड्रॉयड निर्यात से चुने हुए निर्माण फ़ोल्डर में पूरी परियोजना बनाएँ। विंडोज़ पर निर्माण फ़ोल्डर के मार्ग में अंग्रेज़ी अक्षर और अंक रखें। आपकी संपादित परियोजना हिंदी में रह सकती है। ऐप बनाएँ से परीक्षण पैकेज बनाएँ। उपकरण पर चलाएँ से पैकेज बनाकर चालू एमुलेटर या अधिकृत फ़ोन पर स्थापित करें। एक से अधिक उपकरण होने पर औज़ार में उपकरण की पहचान लिखें। डिफ़ॉल्ट निर्माण स्थान अस्थायी है। रखने योग्य पैकेज की स्थायी प्रति बनाएँ।

डेस्कटॉप और वेब लक्ष्य अगले चरण में आएँगे। उन्नत संपादन, चरणबद्ध दोष जाँच और हस्ताक्षरित प्रकाशन अगले चरण के काम हैं।
'''


class Form(tk.Toplevel):
    def __init__(self, parent, title, fields, action="स्वीकार करें"):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent)
        self.resizable(True, False)
        self.columnconfigure(1, weight=1)
        self.entries = {}
        for index, (key, label, value) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=12, pady=8, sticky="w")
            entry = ttk.Entry(self, width=65)
            entry.insert(0, value)
            entry.grid(row=index, column=1, padx=12, pady=8, sticky="ew")
            self.entries[key] = entry
        actions = ttk.Frame(self)
        actions.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ttk.Button(actions, text=action, command=self.accept).pack(side="left", padx=8)
        ttk.Button(actions, text="रद्द करें", command=self.destroy).pack(side="left", padx=8)
        self.bind("<Escape>", lambda _: self.destroy())
        self.grab_set()
        next(iter(self.entries.values())).focus_set()

    def accept(self):
        self.result = {key: entry.get().strip() for key, entry in self.entries.items()}
        self.destroy()


class Studio:
    def __init__(self, root, project=None, tools=None):
        self.root = root
        self.project = None
        self.buffers = {}
        self.hashes = {}
        self.active = SOURCE
        self.tools = tools or Toolchain.discover()
        self.device = ""
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        root.title("भाष विकासशाला")
        root.geometry("1280x820")
        root.minsize(920, 620)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TLabel", font=("Nirmala UI", 11))
        style.configure("TButton", font=("Nirmala UI", 11), padding=6)
        style.configure("Header.TLabel", font=("Nirmala UI", 21, "bold"), foreground="#193a59")
        self.title = ttk.Label(root, text="भाष विकासशाला", style="Header.TLabel")
        self.title.pack(anchor="w", padx=16, pady=(10, 0))
        self.subtitle = ttk.Label(root, text="अपने विचार से अपना ऐप बनाएँ")
        self.subtitle.pack(anchor="w", padx=18, pady=(0, 8))
        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", padx=12)
        self.buttons = {}
        actions = [("new", "नई परियोजना", self.new_project), ("open", "खोलें", self.open_project),
                   ("save", "सहेजें", self.save_current), ("check", "जाँचें", self.validate),
                   ("export", "एंड्रॉयड निर्यात", lambda: self.start_job("export")),
                   ("build", "ऐप बनाएँ", lambda: self.start_job("build")),
                   ("run", "उपकरण पर चलाएँ", lambda: self.start_job("run")),
                   ("tools", "औज़ार", self.settings), ("help", "सहायता", self.help)]
        for key, label, command in actions:
            button = ttk.Button(toolbar, text=label, command=lambda fn=command: self.guard(fn))
            button.pack(side="left", padx=2)
            self.buttons[key] = button
        self.stop = ttk.Button(toolbar, text="रोकें", command=self.cancel.set, state="disabled")
        self.stop.pack(side="left", padx=2)
        target_frame = ttk.Frame(root)
        target_frame.pack(fill="x", padx=18, pady=8)
        ttk.Label(target_frame, text="लक्ष्य").pack(side="left")
        self.target_labels = []
        for target in TARGETS:
            text = target.name + (" — उपलब्ध" if target.implemented else " — आगामी")
            label = ttk.Label(target_frame, text=text)
            label.pack(side="left", padx=18)
            self.target_labels.append(label)
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=14)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        tabs = ttk.Frame(left)
        tabs.pack(fill="x")
        self.tabs = {}
        for filename in FILES:
            button = ttk.Button(tabs, text=filename, command=lambda name=filename: self.select_file(name))
            button.pack(side="left", padx=2)
            self.tabs[filename] = button
        editor_frame = ttk.Frame(left)
        editor_frame.pack(fill="both", expand=True, pady=6)
        self.editor = tk.Text(editor_frame, undo=True, wrap="none", font=("Nirmala UI", 13),
                              padx=12, pady=12, background="#f7f9fc", foreground="#182d43", insertwidth=2)
        scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview)
        horizontal = ttk.Scrollbar(editor_frame, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        self.editor.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        ttk.Label(right, text="दृश्य पूर्वावलोकन — केवल बनावट").pack(anchor="w", pady=7)
        self.preview = tk.Frame(right, background="#ffffff", padx=20, pady=20)
        self.preview.pack(fill="both", expand=True, padx=(12, 0), pady=6)
        ttk.Label(root, text="कार्य विवरण").pack(anchor="w", padx=18)
        self.output = tk.Text(root, height=5, state="disabled", wrap="word", font=("Nirmala UI", 11), padx=10)
        self.output.pack(fill="x", padx=14, pady=(4, 10))
        self.editor.bind("<Control-s>", lambda _: self.guard(self.save_current))
        self.editor.bind("<Control-a>", self.select_all)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.log("नई परियोजना बनाएँ या पहले से बनी परियोजना खोलें।")
        if project:
            self.load(project)
        root.after(100, self.poll)

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

    def remember(self):
        if self.project:
            self.buffers[self.active] = self.editor.get("1.0", "end-1c")

    def select_file(self, filename):
        if not self.project:
            return
        self.remember()
        self.active = filename
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.buffers[filename])
        self.editor.edit_reset()
        self.subtitle.configure(text=f"{self.project.root} — {filename}")

    def confirm_leave(self):
        self.remember()
        if not self.project or all(digest(text) == self.hashes[name] for name, text in self.buffers.items()):
            return True
        dialog = Form(self.root, "अधूरी लिखावट", [("answer", "लिखावट छोड़ने के लिए ‘छोड़ें’ लिखें", "")], "आगे बढ़ें")
        self.root.wait_window(dialog)
        return dialog.result is not None and dialog.result["answer"] == "छोड़ें"

    def load(self, project):
        snapshot = project.snapshot()
        self.project = project
        self.buffers = snapshot
        self.hashes = {name: digest(text) for name, text in snapshot.items()}
        self.active = SOURCE
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", snapshot[SOURCE])
        self.editor.edit_reset()
        self.subtitle.configure(text=str(project.root))
        self.log("परियोजना खोल दी गई।")
        self.guard(self.refresh_preview)

    def new_project(self):
        if not self.confirm_leave():
            return
        dialog = Form(self.root, "नई परियोजना", [("name", "ऐप का नाम", "मेरा पहला ऐप"),
                      ("directory", "नए फ़ोल्डर का पूरा मार्ग", str(Path.cwd() / "मेरा-ऐप"))], "परियोजना बनाएँ")
        self.root.wait_window(dialog)
        if dialog.result:
            self.load(Project.create(dialog.result["directory"], dialog.result["name"]))

    def open_project(self):
        if not self.confirm_leave():
            return
        dialog = Form(self.root, "परियोजना खोलें", [("directory", "परियोजना फ़ोल्डर का पूरा मार्ग", "")], "खोलें")
        self.root.wait_window(dialog)
        if dialog.result:
            self.load(Project.open(dialog.result["directory"]))

    def save_current(self):
        if not self.project:
            raise StudioError("पहले एक परियोजना खोलें।")
        self.remember()
        self.hashes[self.active] = self.project.save(self.active, self.buffers[self.active], self.hashes[self.active])
        self.log("फ़ाइल सहेज दी गई।")

    def save_all(self):
        if not self.project:
            raise StudioError("पहले एक परियोजना खोलें।")
        self.remember()
        for name, text in self.buffers.items():
            self.hashes[name] = self.project.save(name, text, self.hashes[name])

    def refresh_preview(self):
        self.remember()
        _, screen = validate_snapshot(self.buffers)
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
            else:
                ttk.Button(parent, text=node.text, state="disabled").pack(side=side, anchor="w", padx=4, pady=8)

        render(screen.content, self.preview)

    def validate(self):
        self.save_all()
        self.refresh_preview()
        self.log("विन्यास, दृश्य और बटन के फलन रूप की जाँच सफल। पूरी भाष जाँच निर्माण में होगी।")

    def settings(self):
        dialog = Form(self.root, "औज़ार सेटिंग", [("compiler", "आधिकारिक भाष कंपाइलर की जार फ़ाइल", self.tools.compiler),
                      ("java", "जावा कार्यक्रम का पूरा मार्ग", self.tools.java),
                      ("sdk", "एंड्रॉयड औज़ार फ़ोल्डर", self.tools.sdk),
                      ("workspace", "निर्माण फ़ोल्डर — अक्षर और अंकों वाला मार्ग", self.tools.workspace),
                      ("device", "उपकरण की पहचान — वैकल्पिक", self.device)])
        self.root.wait_window(dialog)
        if dialog.result:
            values = dialog.result
            self.tools = Toolchain(values["compiler"], values["java"], values["sdk"], values["workspace"])
            self.device = values["device"]
            self.log("इस सत्र के औज़ार सेट कर दिए गए।")

    def help(self):
        window = tk.Toplevel(self.root)
        window.title("भाष विकासशाला सहायता")
        text = tk.Text(window, wrap="word", width=80, height=30, font=("Nirmala UI", 12), padx=16, pady=16)
        text.pack(fill="both", expand=True)
        text.insert("1.0", HELP)
        text.configure(state="disabled")

    def start_job(self, operation):
        if self.worker and self.worker.is_alive():
            raise StudioError("पहला कार्य पूरा होने दें या उसे रोकें।")
        self.validate()
        snapshot = self.buffers.copy()
        project = self.project
        tools = self.tools
        device = self.device
        self.cancel.clear()
        for button in self.buttons.values():
            button.configure(state="disabled")
        self.stop.configure(state="normal")

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

    def poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                if message is None:
                    for button in self.buttons.values():
                        button.configure(state="normal")
                    self.stop.configure(state="disabled")
                else:
                    self.log(message)
        except queue.Empty:
            pass
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self.poll)

    def close(self):
        if not self.confirm_leave():
            return
        self.closing = True
        self.cancel.set()


def main():
    parser = argparse.ArgumentParser(description="भाष विकासशाला")
    parser.add_argument("--project", help="परियोजना फ़ोल्डर")
    parser.add_argument("--compiler", help="भाष कंपाइलर की जार फ़ाइल")
    options = parser.parse_args()
    tools = Toolchain.discover()
    if options.compiler:
        tools = Toolchain(options.compiler, tools.java, tools.sdk, tools.workspace)
    root = tk.Tk()
    studio = Studio(root, tools=tools)
    if options.project:
        studio.guard(lambda: studio.load(Project.open(options.project)))
    root.mainloop()
