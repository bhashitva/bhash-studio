"""Compiler-backed editor actions, with version checks before every source edit."""

from pathlib import Path
from urllib.parse import unquote, urlparse
import tkinter as tk
from tkinter import simpledialog, ttk
from queue import Empty

from .clipboard import ReadOnlyText
from .errors import StudioError


def offset_at(source, position):
    lines = source.splitlines(keepends=True)
    line, character = position["line"], position["character"]
    if line == len(lines) and character == 0:
        return len(source)
    if not 0 <= line < len(lines):
        raise StudioError("स्रोत स्थान बदल गया है।")
    text = lines[line].encode("utf-16-le")
    if character * 2 > len(text):
        raise StudioError("स्रोत स्थान बदल गया है।")
    return sum(map(len, lines[:line])) + len(text[:character * 2].decode("utf-16-le"))


def source_name(uri, source_root):
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise StudioError("यह स्थान परियोजना के बाहर है।")
    path = unquote(parsed.path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    try:
        return Path(path).resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError as error:
        raise StudioError("यह स्थान परियोजना के बाहर है।") from error


def edited_source(source, edits):
    spans = [(offset_at(source, edit["range"]["start"]), offset_at(source, edit["range"]["end"]),
              edit["newText"]) for edit in edits]
    previous = len(source) + 1
    for start, end, text in sorted(spans, reverse=True):
        if not 0 <= start <= end <= previous:
            raise StudioError("स्रोत के बदलाव आपस में टकराते हैं।")
        source = source[:start] + text + source[end:]
        previous = start
    return source


def choose(studio, title, rows, callback):
    window = tk.Toplevel(studio.root)
    window.title(title)
    window.transient(studio.root)
    window.geometry("800x420")
    listing = tk.Listbox(window, exportselection=False, font=("Nirmala UI", 12))
    scroll = ttk.Scrollbar(window, command=listing.yview)
    listing.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    listing.pack(fill="both", expand=True)
    for label, value in rows:
        listing.insert("end", label)

    def accept(*_):
        if listing.curselection():
            value = rows[listing.curselection()[0]][1]
            studio.guard(lambda: callback(value))
            window.destroy()
    ttk.Button(window, text="चुनें", command=accept).pack(pady=8)
    listing.bind("<Double-Button-1>", accept)
    listing.bind("<Return>", accept)
    window.bind("<Escape>", lambda _: window.destroy())
    if rows:
        listing.selection_set(0)


def language_action(studio, method):
    editor, filename, project = studio.editor, studio.active, studio.project
    if not project or not editor or not editor.source_mode:
        raise StudioError("पहले भाष स्रोत खोलें।")
    source = editor.get("1.0", "end-1c")
    caret = len(editor.get("1.0", "insert"))
    extra = {}
    if method == "rename":
        name = simpledialog.askstring("नाम बदलें", "नया नाम", parent=studio.root)
        if not name:
            return
        extra["newName"] = name
    if method == "references":
        extra["context"] = {"includeDeclaration": True}
    buffers = {name: studio.file_text(name) for name in studio.editors if name.endswith(".bhash")}
    tools = studio.tools
    if studio.compiler_override:
        from dataclasses import replace
        tools = replace(tools, compiler=studio.compiler_override)
    future = studio.signature_pool.submit(studio.language_server.request, tools, project,
                                          filename, buffers, caret, method, extra)

    def finish():
        if studio.closing:
            return
        if not future.done():
            studio.root.after(60, finish)
            return
        def display():
            result, source_root, versions = future.result()
            if studio.project is not project or not editor.winfo_exists():
                return

            def current():
                if studio.project is not project or studio.worker is not None:
                    raise StudioError("परियोजना का काम बदल गया है। आदेश फिर चलाएँ।")
                for name, (_, expected) in versions.items():
                    actual = studio.file_text(name) if name in studio.editors else project.read(name)
                    if actual != expected:
                        raise StudioError("स्रोत बदल गया है। आदेश फिर चलाएँ।")
                    if name in studio.editors and str(studio.editors[name].cget("state")) != "normal":
                        raise StudioError("स्रोत अभी केवल पढ़ने के लिए है।")

            def apply(workspace):
                current()
                changes = workspace.get("changes", {})
                for document in workspace.get("documentChanges", []):
                    if "textDocument" not in document:
                        raise StudioError("यह फ़ाइल कार्रवाई समर्थित नहीं है।")
                    uri = document["textDocument"]["uri"]
                    name = source_name(uri, source_root)
                    version = document["textDocument"].get("version")
                    if version is not None and versions[name][0] != version:
                        raise StudioError("स्रोत का संस्करण बदल गया है।")
                    changes[uri] = document["edits"]
                updates = {}
                for uri, edits in changes.items():
                    name = source_name(uri, source_root)
                    updates[name] = edited_source(versions[name][1], edits)
                # Validate every edit before modifying any buffer. Files remain undoable and unsaved.
                for name, text in updates.items():
                    studio.select_file(name)
                    studio.editor.insert_text("1.0", "end-1c", text)

            def navigate(location):
                current()
                name = source_name(location.get("uri", location.get("targetUri")), source_root)
                studio.select_file(name)
                where = location.get("range", location.get("targetSelectionRange"))["start"]
                offset = offset_at(versions[name][1], where)
                text = versions[name][1][:offset]
                index = f"1.0 +{studio.editor.tk.call('string', 'length', text)}c"
                studio.editor.mark_set("insert", index)
                studio.editor.see(index)
                studio.editor.focus_set()

            if method in {"definition", "references"}:
                locations = result if isinstance(result, list) else [result] if result else []
                choose(studio, "स्रोत स्थान", [(str(row.get("uri", row.get("targetUri"))), row)
                                              for row in locations], navigate)
            elif method == "rename":
                if result:
                    apply(result)
            elif method == "completion":
                entries = result.get("items", []) if isinstance(result, dict) else result or []
                def insert(item):
                    current()
                    if item.get("textEdit"):
                        edit = item["textEdit"]
                        apply({"changes": {(source_root / filename).as_uri(): [edit, *item.get("additionalTextEdits", [])]}})
                    else:
                        if studio.editor is not editor or len(editor.get("1.0", "insert")) != caret:
                            raise StudioError("कर्सर बदल गया है। आदेश फिर चलाएँ।")
                        editor.insert_template(item.get("insertText", item["label"]))
                choose(studio, "पूरा करें", [(row["label"] + " " + row.get("detail", ""), row) for row in entries], insert)
            elif method == "codeAction":
                actions = [row for row in result or [] if row.get("edit")]
                choose(studio, "सुझाए सुधार", [(row["title"], row["edit"]) for row in actions], apply)
            elif method == "hover":
                contents = (result or {}).get("contents", {})
                text = contents.get("value", "") if isinstance(contents, dict) else str(contents)
                window = tk.Toplevel(studio.root)
                window.title("प्रकार और विवरण")
                detail = ReadOnlyText(window, wrap="word", width=80, height=22, font=("Nirmala UI", 12))
                detail.pack(fill="both", expand=True)
                detail.set_text(text or "इस स्थान का विवरण उपलब्ध नहीं है।")
        try:
            studio.guard(display)
        except (Empty, KeyError, ValueError, RuntimeError) as error:
            studio.log("भाष सहायता पूरी नहीं हुई। स्रोत और कंपाइलर जाँचें। " + str(error))
    studio.root.after(60, finish)
