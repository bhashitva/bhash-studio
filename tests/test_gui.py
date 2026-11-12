import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from bhash_studio.project import CONFIG, FILES, SOURCE, LAYOUT, LocalPath, Project


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_GUI_TESTS") == "1", "Enable GUI tests on a desktop session")
class DesktopTests(unittest.TestCase):
    def test_build_folder_context_menu_confirms_and_removes_previous_builds(self):
        import tkinter as tk
        from bhash_studio.app import Studio
        from bhash_studio.project import BUILD_DIRECTORY, Project

        with tempfile.TemporaryDirectory() as temp:
            root = tk.Tk()
            try:
                project = Project.create(Path(temp) / "demo", "परीक्षा")
                output = project.root / BUILD_DIRECTORY
                old = output / "0123456789abcdef"
                old.mkdir(parents=True)
                (old / "app.apk").write_bytes(b"test")
                (old / "tool-output.log").write_text("build", encoding="utf-8")
                (output / "abcdef0123456789").mkdir()
                keep = output / "notes.txt"
                keep.write_text("keep", encoding="utf-8")
                studio = Studio(root, project, settings_file=Path(temp) / "settings.json")
                root.update()
                tree = studio.explorer
                folder = next(item for item, entry in tree.entries.items() if entry == (BUILD_DIRECTORY, True))
                _, y, _, height = tree.tree.bbox(folder)
                with patch.object(tree.build_menu, "tk_popup") as popup:
                    tree.tree.event_generate("<Button-3>", x=40, y=y + height // 2)
                    popup.assert_called_once()
                with patch("bhash_studio.app.messagebox.askokcancel", return_value=False):
                    tree.build_menu.invoke(0)
                self.assertTrue(old.is_dir())
                with patch("bhash_studio.app.messagebox.askokcancel", return_value=True):
                    tree.build_menu.invoke(0)
                studio.worker.join(timeout=5)
                studio.poll()
                self.assertFalse(old.exists())
                self.assertTrue(keep.exists())
                self.assertTrue((output / "abcdef0123456789").is_dir())
                self.assertTrue(output.is_dir())
                self.assertIn("1 पूर्व निर्माण हटाए गए", studio.output.get("1.0", "end"))
            finally:
                root.destroy()

    def test_clipboard_copies_diagnostics_and_pastes_into_editor_and_form(self):
        import tkinter as tk
        from bhash_studio.app import Form, Studio
        from bhash_studio.clipboard import ReadOnlyText
        from bhash_studio.project import Project

        with tempfile.TemporaryDirectory() as temp:
            root = tk.Tk()
            try:
                project = Project.create(Path(temp) / "demo", "परीक्षा")
                studio = Studio(root, project, settings_file=Path(temp) / "settings.json")
                editor = studio.editor
                message = "पंक्ति २ — फलन चाहिए"
                editor.syntax_status.set(message)
                status = next(child for child in editor.master.winfo_children() if isinstance(child, ReadOnlyText))
                root.update()
                status.event_generate("<<SelectAll>>")
                status.event_generate("<<Copy>>")
                self.assertEqual(root.clipboard_get(), message)
                editor.event_generate("<<SelectAll>>")
                editor.event_generate("<<Paste>>")
                self.assertEqual(editor.get("1.0", "end-1c"), message)
                studio.log(message)
                studio.output.tag_add("sel", "end-2l", "end-1l -1c")
                studio.output.event_generate("<<Copy>>")
                self.assertEqual(root.clipboard_get(), message)
                form = Form(root, "नाम", [("name", "नाम", "पुराना")])
                entry = form.entries["name"]
                entry.event_generate("<<SelectAll>>")
                entry.event_generate("<<Paste>>")
                self.assertEqual(entry.get(), message)
                entry.configure(state="readonly")
                entry.event_generate("<<SelectAll>>")
                entry.event_generate("<<Cut>>")
                self.assertEqual(entry.get(), message)
            finally:
                root.destroy()

    def test_editor_inserts_a_standard_library_import(self):
        import tkinter as tk
        from bhash_studio.editor import BhashEditor

        root = tk.Tk()
        try:
            editor = BhashEditor(root)
            editor.pack()
            editor.open_buffer("आयात मानक.पा", source_mode=True)
            editor.mark_set("insert", "end-1c")
            root.update()
            editor.refresh(show=True)
            self.assertEqual(editor.choices.get(0), "पाठ्य")
            editor.apply_choice(0)
            self.assertEqual(editor.get("1.0", "end-1c"), "आयात मानक.पाठ्य")
        finally:
            root.destroy()

    def test_editor_marks_syntax_errors_and_clears_them_after_correction(self):
        from concurrent.futures import Future
        import tkinter as tk
        from bhash_studio.editor import BhashEditor

        def check(source):
            future = Future()
            future.set_result(((1, 6, "नाम चाहिए"),) if "?" in source else ())
            return future

        root = tk.Tk()
        try:
            editor = BhashEditor(root, syntax_check=check)
            editor.open_buffer("फलन  ?", source_mode=True)
            editor.cancel_syntax()
            editor.start_syntax()
            self.assertTrue(editor.tag_ranges("keyword"))
            self.assertEqual(tuple(map(str, editor.tag_ranges("syntax_error"))), ("1.5", "1.6"))
            self.assertIn("नाम चाहिए", editor.syntax_status.get())
            editor.open_buffer("फलन नाम() {}", source_mode=True)
            editor.cancel_syntax()
            editor.start_syntax()
            self.assertFalse(editor.tag_ranges("syntax_error"))
            self.assertEqual(editor.syntax_status.get(), "वाक्यविन्यास सही है।")
        finally:
            root.destroy()

    def test_explorer_indicator_and_multi_file_trash(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = Project.create(base / "मेरा-ऐप", "परीक्षा")
            project.add_folder("फ़ोल्डर")
            for name in ("पहली.txt", "दूसरी.txt", "तीसरी.txt"):
                project.add_file(name, folder="फ़ोल्डर")
            trash = base / "trash"
            trash.mkdir()
            root = tk.Tk()
            try:
                studio = Studio(root, project, settings_file=base / "settings.json")
                explorer = studio.explorer
                tree = explorer.tree
                root.update()
                folder = next(item for item, entry in explorer.entries.items() if entry == ("फ़ोल्डर", True))
                _, y, width, height = tree.bbox(folder)
                y += height // 2
                x = next(x for x in range(width)
                         if tree.identify_element(x, y).endswith(("indicator", "disclosure")))
                tree.event_generate("<ButtonPress-1>", x=x, y=y)
                tree.event_generate("<ButtonRelease-1>", x=x, y=y)
                root.update()
                self.assertTrue(tree.item(folder, "open"))
                files = {explorer.entries[item][0]: item for item in tree.get_children(folder)}
                self.assertEqual(len(files), 3)

                first, second = "फ़ोल्डर/पहली.txt", "फ़ोल्डर/दूसरी.txt"
                studio.select_file(first)
                studio.editor.insert("1.0", "अधूरा")
                tree.selection_set(files[first], files[second])
                _, y, _, height = tree.bbox(files[first])
                with patch.object(explorer.menu, "tk_popup"):
                    tree.event_generate("<Button-3>", x=40, y=y + height // 2)
                self.assertEqual(set(explorer.selected_files()), {first, second})
                with patch("bhash_studio.app.messagebox.askokcancel", return_value=False), \
                        patch("bhash_studio.app.move_to_trash") as move:
                    explorer.menu.invoke("end")
                    move.assert_not_called()
                with patch("bhash_studio.app.messagebox.askokcancel", return_value=True), \
                        patch("bhash_studio.app.move_to_trash", side_effect=lambda path: path.rename(trash / path.name)):
                    explorer.menu.invoke("end")
                self.assertEqual({path.name for path in trash.iterdir()}, {"पहली.txt", "दूसरी.txt"})
                self.assertTrue(project.file("फ़ोल्डर/तीसरी.txt").is_file())
                self.assertNotIn(first, studio.editors)
                self.assertEqual(studio.file_states[first]["text"], "अधूरा")
            finally:
                root.destroy()

    @unittest.skipUnless(sys.platform == "win32", "Windows keyboard messages")
    def test_windows_hindi_keyboard_in_editor_and_form(self):
        import ctypes as c
        from ctypes import wintypes as w
        import tkinter as tk
        from bhash_studio.app import Form, Studio

        user = c.WinDLL("user32")
        user.SendMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        user.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        user.GetFocus.restype = w.HWND
        user.GetKeyboardLayout.argtypes = (w.DWORD,)
        user.GetKeyboardLayout.restype = w.HKL
        user.LoadKeyboardLayoutW.argtypes = (w.LPCWSTR, w.UINT)
        user.LoadKeyboardLayoutW.restype = w.HKL
        user.ActivateKeyboardLayout.argtypes = (w.HKL, w.UINT)
        user.ActivateKeyboardLayout.restype = w.HKL
        root = tk.Tk()
        original_layout = user.GetKeyboardLayout(0)
        hindi_layout = user.LoadKeyboardLayoutW("00010439", 0)
        if hindi_layout:
            user.ActivateKeyboardLayout(hindi_layout, 0)

        def type_hindi(window, widget):
            root.update()
            widget.focus_force()
            root.update()
            # Windows focuses the toplevel; Tk's logical focus is the text widget.
            hwnd = user.GetFocus()
            self.assertEqual(hwnd, window.winfo_id())
            self.assertIs(window.focus_get(), widget)
            for char in "हिंदी":
                user.SendMessageW(hwnd, 0x0102, ord(char), 0)
            if hindi_layout and user.GetKeyboardLayout(0) == hindi_layout:
                # Let the Windows message loop translate a Hindi Traditional key.
                self.assertTrue(user.PostMessageW(hwnd, 0x0100, ord("K"), 1 | (0x25 << 16)))
                self.assertTrue(user.PostMessageW(hwnd, 0x0101, ord("K"), 0xc0250001))
                self.assertTrue(user.PostMessageW(hwnd, 0x0100, 0x20, 1 | (0x39 << 16)))
                self.assertTrue(user.PostMessageW(hwnd, 0x0101, 0x20, 0xc0390001))
            else:
                self.assertTrue(user.PostMessageW(hwnd, 0x0102, ord("क"), 1))
                user.SendMessageW(hwnd, 0x0100, ord("K"), 1 | (0x25 << 16))
                self.assertTrue(user.PostMessageW(hwnd, 0x0102, ord(" "), 1))
            root.update()

        with tempfile.TemporaryDirectory() as temp:
            try:
                base = Path(temp)
                project = Project.create(base / "मेरा-ऐप", "परीक्षा")
                studio = Studio(root, project, settings_file=base / "settings.json")
                editor = studio.editor
                editor.delete("1.0", "end")
                type_hindi(root, editor)
                self.assertEqual(editor.get("1.0", "end-1c"), "हिंदीक ")
                dialog = Form(root, "फ़ाइल", [("name", "नाम", "")])
                entry = dialog.entries["name"]
                type_hindi(dialog, entry)
                self.assertEqual(entry.get(), "हिंदीक ")
            finally:
                user.ActivateKeyboardLayout(original_layout, 0)
                root.destroy()

    def test_dirty_tabs_recover_without_writing_project_files(self):
        import tkinter as tk
        from bhash_studio.app import Studio
        from bhash_studio.errors import StudioError

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = Project.create(base / "मेरा-ऐप", "परीक्षा")
            settings = base / "settings.json"
            original = project.read(SOURCE)
            project.add_file("टिप्पणी.txt")
            root = tk.Tk()
            try:
                studio = Studio(root, project, settings_file=settings)
                studio.editor.insert("end", "# अधूरा\n")
                studio.editor.mark_set("insert", "2.3")
                studio.select_file("टिप्पणी.txt")
                studio.editor.insert("end", "अधूरी टिप्पणी")
                root.update()
                for x in range(studio.notebook.winfo_width()):
                    y = next((row for row in range(30)
                              if studio.notebook.identify(x, row) == "Yantra.close"), None)
                    if y is not None and studio.notebook.index(f"@{x},{y}") == 1:
                        break
                else:
                    self.fail("The second tab has no close button")
                studio.notebook.event_generate("<ButtonPress-1>", x=x, y=y)
                studio.notebook.event_generate("<ButtonRelease-1>", x=x, y=y)
                self.assertEqual(list(studio.editors), [SOURCE])
                studio.close()
                self.assertTrue(studio.closing)
                self.assertTrue((project.root / ".studio" / "session.json").is_file())
                self.assertEqual(project.read(SOURCE), original)
                self.assertEqual(project.read("टिप्पणी.txt"), "")
            finally:
                root.destroy()

            project.file(SOURCE).write_text(original + "# external\n", encoding="utf-8")
            root = tk.Tk()
            try:
                studio = Studio(root, settings_file=settings)
                studio.restore_session()
                root.update_idletasks()
                self.assertEqual(list(studio.editors), [SOURCE])
                self.assertEqual(studio.editor.get("1.0", "end-1c"), original + "# अधूरा\n")
                self.assertEqual(studio.editor.index("insert"), "2.3")
                with self.assertRaises(StudioError):
                    studio.save_current()
                studio.select_file("टिप्पणी.txt")
                self.assertEqual(studio.editor.get("1.0", "end-1c"), "अधूरी टिप्पणी")
                studio.save_current()
                self.assertEqual(project.read("टिप्पणी.txt"), "अधूरी टिप्पणी")
            finally:
                root.destroy()

    def test_explorer_context_menu_creates_and_imports_in_selected_folder(self):
        import tkinter as tk
        from bhash_studio.app import Form, Studio

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = Project.create(base / "मेरा-ऐप", "परीक्षा")
            original = base / "चित्र.bin"
            original.write_bytes(b"\xff\0")
            root = tk.Tk()
            try:
                studio = Studio(root, project, settings_file=base / "settings.json")
                explorer = studio.explorer

                def accept_name(name):
                    dialog = next(widget for widget in root.winfo_children() if isinstance(widget, Form))
                    dialog.entries["name"].insert(0, name)
                    dialog.accept()

                root.after_idle(accept_name, "संसाधन")
                explorer.menu.invoke(1)
                root.update()
                folder = next(item for item, entry in explorer.entries.items() if entry == ("संसाधन", True))
                _, y, _, height = explorer.tree.bbox(folder)
                with patch.object(explorer.menu, "tk_popup"):
                    explorer.tree.event_generate("<Button-3>", x=20, y=y + height // 2)
                self.assertEqual(explorer.target, "संसाधन")
                root.after_idle(accept_name, "दृश्य.भाषदृश्य")
                explorer.menu.invoke(0)
                self.assertEqual(studio.active, "संसाधन/दृश्य.भाषदृश्य")
                with patch("bhash_studio.app.choose_path", return_value=str(original)):
                    explorer.menu.invoke(2)
                self.assertEqual((project.root / "संसाधन" / original.name).read_bytes(), b"\xff\0")
            finally:
                root.destroy()

    def test_new_and_import_file_menus_update_the_project_tree(self):
        import tkinter as tk
        from bhash_studio.app import Form, Studio

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = Project.create(base / "मेरा-ऐप", "परीक्षण ऐप")
            original = base / "चित्र.bin"
            original.write_bytes(b"\xff\0")
            root = tk.Tk()
            try:
                studio = Studio(root, project, settings_file=base / "settings.json")

                def name_file():
                    dialog = next(widget for widget in root.winfo_children() if isinstance(widget, Form))
                    dialog.entries["name"].insert(0, "सहायक.bhash")
                    dialog.accept()

                root.after_idle(name_file)
                menu, index = studio.menu_items["new_file"]
                menu.invoke(index)
                self.assertEqual(studio.active, "सहायक.bhash")
                with patch("bhash_studio.app.choose_path", return_value=str(original)):
                    menu, index = studio.menu_items["import_file"]
                    menu.invoke(index)
                names = {name for name, _ in studio.explorer.entries.values()}
                self.assertTrue({"सहायक.bhash", original.name} <= names)
                self.assertEqual((project.root / original.name).read_bytes(), b"\xff\0")
            finally:
                root.destroy()

    def test_last_project_restores_tabs_and_skips_missing_paths(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            prefs = base / "settings.json"
            project = Project.create(base / "मेरा-ऐप", "परीक्षण ऐप")
            notes = project.root / "टिप्पणी.txt"
            notes.write_text("नमस्ते", encoding="utf-8")
            root = tk.Tk()
            try:
                studio = Studio(root, project, settings_file=prefs)
                studio.select_file(notes.name)
                studio.select_file(LAYOUT)
                studio.select_file(notes.name)
                root.update_idletasks()
                studio.close()
            finally:
                root.destroy()

            for expected, active, warnings in (
                ([SOURCE, notes.name, LAYOUT], notes.name, []),
                ([LAYOUT], LAYOUT, [notes.name, SOURCE]),
                ([], None, ["पिछली परियोजना का फ़ोल्डर नहीं मिला"]),
            ):
                root = tk.Tk()
                try:
                    studio = Studio(root, settings_file=prefs)
                    studio.restore_session()
                    root.update_idletasks()
                    self.assertEqual(list(studio.editors), expected)
                    self.assertEqual(studio.active, active)
                    for warning in warnings:
                        self.assertIn(warning, studio.output.get("1.0", "end"))
                    self.assertEqual(studio.project is not None, bool(expected))
                finally:
                    root.destroy()
                if not warnings:
                    notes.unlink()
                    (project.root / SOURCE).unlink()
                elif expected:
                    project.root.rename(base / "स्थानांतरित")

    def test_tool_settings_are_restored_on_next_launch(self):
        import tkinter as tk
        from bhash_studio.android import Toolchain
        from bhash_studio.app import Form, Studio

        with tempfile.TemporaryDirectory() as temp:
            settings_file = Path(temp) / "settings.json"
            tools = Toolchain("औज़ार/भाष.jar", "औज़ार/java", "औज़ार/एंड्रॉयड")
            root = tk.Tk()
            try:
                first = Studio(root, tools=tools, settings_file=settings_file, compiler_override="launch.jar")

                def apply_settings():
                    dialog = next(widget for widget in root.winfo_children() if isinstance(widget, Form))
                    dialog.entries["device"].insert(0, "emulator-5554")
                    dialog.accept()

                root.after_idle(apply_settings)
                menu, index = first.menu_items["tools"]
                menu.invoke(index)
                self.assertTrue(settings_file.is_file())
            finally:
                root.destroy()

            root = tk.Tk()
            try:
                second = Studio(root, tools=Toolchain(), settings_file=settings_file)
                root.update_idletasks()
                self.assertEqual(second.tools, tools)
                self.assertEqual(second.device, "emulator-5554")
            finally:
                root.destroy()

    def test_help_menu_opens_and_closes_read_only_help(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        root = tk.Tk()
        try:
            app = Studio(root)
            menu, index = app.menu_items["help"]
            menu.invoke(index)
            root.update()
            window = next(widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel))
            text = next(widget for widget in window.winfo_children() if isinstance(widget, tk.Text))
            self.assertEqual(text.cget("state"), "disabled")
            self.assertIn("भाष यंत्र", text.get("1.0", "2.0"))
            window.destroy()
            self.assertTrue(root.winfo_exists())
        finally:
            root.destroy()

    def test_project_open_menu_chooses_the_real_config_path(self):
        import tkinter as tk
        from bhash_studio.app import Studio
        from bhash_studio.path_picker import PathPicker

        with tempfile.TemporaryDirectory() as temp:
            folder = LocalPath(temp)
            project = Project.create(folder / "मेरा-ऐप", "अभिवादन")
            (project.root / (CONFIG + ".txt")).write_text("test", encoding="utf-8")
            root = tk.Tk()
            try:
                app = Studio(root)
                observed = []

                def pick():
                    picker = next(widget for widget in root.winfo_children() if isinstance(widget, PathPicker))
                    try:
                        observed.append(picker.directory)
                        picker.files.selection_set(picker.files.get_children()[0])
                        picker.select()
                        rows = picker.files.get_children()
                        observed.append([picker.files.item(row, "text") for row in rows])
                        picker.files.selection_set(rows[0])
                        picker.select()
                    finally:
                        if picker.winfo_exists():
                            picker.destroy()

                with patch("bhash_studio.path_picker.LocalPath.cwd", return_value=folder):
                    root.after_idle(pick)
                    menu, index = app.menu_items["open"]
                    menu.invoke(index)
                self.assertEqual(observed, [folder, [CONFIG]])
                self.assertEqual(app.project.root, project.root)
                self.assertIn("अभिवादन", app.editor.get("1.0", "end"))
            finally:
                root.destroy()

    def test_explorer_opens_nested_files_in_independent_tabs(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        with tempfile.TemporaryDirectory() as temp:
            project = Project.create(Path(temp) / "मेरा-ऐप", "परीक्षण ऐप")
            folder = project.root / "सामग्री"
            folder.mkdir()
            extra = folder / "टिप्पणी.txt"
            extra.write_text("पहली लिखावट", encoding="utf-8")
            root = tk.Tk()
            try:
                app = Studio(root, project)
                root.update()
                source_editor = app.editor
                source_editor.insert("end", "\n// अधूरी लिखावट")
                explorer = app.explorer
                directory = next(i for i, value in explorer.entries.items() if value == ("सामग्री", True))
                explorer.tree.focus(directory)
                explorer.tree.event_generate("<<TreeviewOpen>>")
                item = explorer.tree.get_children(directory)[0]
                explorer.tree.focus(item)
                explorer.tree.focus_force()
                root.update()
                explorer.tree.event_generate("<Return>")
                self.assertEqual(app.active, "सामग्री/टिप्पणी.txt")
                self.assertEqual(app.editor.get("1.0", "end-1c"), "पहली लिखावट")
                self.assertEqual(len(app.notebook.tabs()), 2)
                self.assertIn("परीक्षण ऐप", root.title())
                app.editor.insert("end", " नई")
                app.notebook.select(source_editor.master)
                root.update()
                self.assertIs(app.editor, source_editor)
                self.assertIn("अधूरी लिखावट", app.editor.get("1.0", "end"))
                app.select_file("सामग्री/टिप्पणी.txt")
                self.assertEqual(len(app.notebook.tabs()), 2)
                app.save_current()
                app.close_tab()
                self.assertEqual(extra.read_text(encoding="utf-8"), "पहली लिखावट नई")
                self.assertIs(app.editor, source_editor)
            finally:
                root.destroy()

    def test_toolchain_picker_filters_files_by_field(self):
        import tkinter as tk
        from bhash_studio.path_picker import PathPicker, jar_file, java_program

        java = "java.exe" if os.name == "nt" else "java"
        with tempfile.TemporaryDirectory() as temp:
            folder = LocalPath(temp)
            (folder / "औज़ार").mkdir()
            for filename in ("भाष.jar", java, "जानकारी.txt"):
                (folder / filename).touch()
            root = tk.Tk()
            try:
                for predicate, expected in ((jar_file, ["औज़ार", "भाष.jar"]),
                                            (java_program, ["औज़ार", java]),
                                            (None, ["औज़ार"])):
                    with self.subTest(expected=expected), patch(
                        "bhash_studio.path_picker.LocalPath.cwd", return_value=folder,
                    ):
                        picker = PathPicker(root, "चुनें", predicate)
                        self.assertEqual([picker.files.item(row, "text") for row in picker.files.get_children()],
                                         expected)
                        picker.destroy()
                root.update_idletasks()
            finally:
                root.destroy()

    def test_edit_save_switch_validate_and_reopen(self):
        import tkinter as tk
        from bhash_studio.app import Studio
        with tempfile.TemporaryDirectory() as temp:
            project = Project.create(Path(temp) / "हिंदी ऐप", "परीक्षण")
            root = tk.Tk()
            try:
                app = Studio(root, project)
                root.update()
                app.editor.insert("end", "\n// हिंदी टिप्पणी\n")
                file_menu, index = app.menu_items["files"]
                picker = root.nametowidget(file_menu.entrycget(index, "menu"))
                picker.invoke(FILES.index(LAYOUT))
                self.assertEqual(app.active, LAYOUT)
                self.assertTrue(app.helpers[0].instate(["disabled"]))
                picker.invoke(FILES.index(SOURCE))
                self.assertIn("हिंदी टिप्पणी", app.editor.get("1.0", "end"))
                for key in ("save", "check"):
                    menu, index = app.menu_items[key]
                    menu.invoke(index)
                root.update()
                self.assertIn("हिंदी टिप्पणी", Project.open(project.root).read(SOURCE))
                self.assertIn("जाँच सफल", app.output.get("1.0", "end"))
                self.assertEqual(len(app.preview.winfo_children()), 2)
            finally:
                root.destroy()

    def test_bhash_editor_highlights_and_completes_from_the_active_buffer(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        with tempfile.TemporaryDirectory() as temp:
            root = tk.Tk()
            try:
                app = Studio(root, Project.create(Path(temp) / "परियोजना", "अभिवादन"))
                editor = app.editor
                editor.open_buffer('लिखो("🙂 यदि"); मान परिणाम: पाठ = "";\n', True)
                editor.focus_force()
                root.update()
                editor.mark_set("insert", "end-1c")
                editor.insert("insert", "परि")
                done = tk.BooleanVar(root)
                root.after(240, lambda: done.set(True))
                root.wait_variable(done)
                ranges = editor.tag_ranges("keyword")
                self.assertEqual([editor.get(a, b) for a, b in zip(ranges[::2], ranges[1::2])],
                                 ["लिखो", "मान", "पाठ"])
                self.assertIn("परिणाम", editor.choices.get(0, "end"))
                self.assertTrue(editor.choices.winfo_ismapped())
                choice = editor.choices.get(0, "end").index("परिणाम")
                editor.choices.selection_clear(0, "end")
                editor.choices.selection_set(choice)
                editor.event_generate("<Tab>")
                self.assertEqual(editor.get("insert linestart", "insert"), "परिणाम")
                self.assertFalse(editor.choices.winfo_ismapped())

                editor.insert("insert", "\n    ")
                constructs = root.nametowidget(app.helpers[1].cget("menu"))
                from bhash_studio.bhash_syntax import KEYWORDS
                keywords = root.nametowidget(app.helpers[0].cget("menu"))
                self.assertEqual(
                    {keywords.entrycget(i, "label") for i in range(keywords.index("end") + 1)},
                    set(KEYWORDS),
                )
                switch = next(i for i in range(constructs.index("end") + 1)
                              if constructs.entrycget(i, "label") == "चयन")
                index = next(i for i in range(constructs.index("end") + 1)
                             if constructs.entrycget(i, "label") == "यदि")
                constructs.invoke(index)
                self.assertIn("    यदि (सत्य) {\n        \n    }", editor.get("1.0", "end-1c"))
                self.assertEqual(editor.get("insert linestart", "insert"), "        ")
                constructs.invoke(switch)
                self.assertIn("चयन (मूल्य)", editor.get("1.0", "end-1c"))
                self.assertIn("विकल्प १:", editor.get("1.0", "end-1c"))
                self.assertIn("शेष:", editor.get("1.0", "end-1c"))
            finally:
                root.destroy()

    def test_android_menu_cancels_running_job(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        def wait_for_cancel(_target, project, snapshot, operation, cancel, emit, device):
            self.assertTrue(cancel.wait(timeout=5))
            return project.root

        with tempfile.TemporaryDirectory() as temp:
            root = tk.Tk()
            try:
                app = Studio(root)
                root.update_idletasks()
                build, build_index = app.menu_items["build"]
                stop, stop_index = app.menu_items["stop"]
                self.assertEqual(str(root.cget("menu")), str(app.menu_bar))
                self.assertEqual(build.entrycget(build_index, "state"), "disabled")
                app.load(Project.create(Path(temp) / "परियोजना", "अभिवादन"))
                self.assertEqual(build.entrycget(build_index, "state"), "normal")
                self.assertEqual(stop.entrycget(stop_index, "state"), "disabled")
                with patch("bhash_studio.app.AndroidTarget.execute", autospec=True, side_effect=wait_for_cancel) as execute:
                    build.invoke(build_index)
                    self.assertEqual(build.entrycget(build_index, "state"), "disabled")
                    self.assertEqual(stop.entrycget(stop_index, "state"), "normal")
                    stop.invoke(stop_index)
                    self.assertTrue(app.cancel.is_set())
                    app.worker.join(timeout=5)
                    self.assertFalse(app.worker.is_alive())
                    execute.assert_called_once()
                    self.assertEqual(execute.call_args.args[3], "build")
                app.poll()
                self.assertEqual(build.entrycget(build_index, "state"), "normal")
                self.assertEqual(stop.entrycget(stop_index, "state"), "disabled")
            finally:
                root.destroy()
