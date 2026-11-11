import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bhash_studio.project import CONFIG, FILES, SOURCE, LAYOUT, LocalPath, Project


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_GUI_TESTS") == "1", "Enable GUI tests on a desktop session")
class DesktopTests(unittest.TestCase):
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
            tools = Toolchain("औज़ार/भाष.jar", "औज़ार/java", "औज़ार/एंड्रॉयड", "औज़ार/निर्माण")
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
                index = next(i for i in range(constructs.index("end") + 1)
                             if constructs.entrycget(i, "label") == "यदि")
                constructs.invoke(index)
                self.assertIn("    यदि (सत्य) {\n        \n    }", editor.get("1.0", "end-1c"))
                self.assertEqual(editor.get("insert linestart", "insert"), "        ")
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
