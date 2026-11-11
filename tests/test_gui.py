import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bhash_studio.project import SOURCE, LAYOUT, Project


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_GUI_TESTS") == "1", "Enable GUI tests on a desktop session")
class DesktopTests(unittest.TestCase):
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
                app.select_file(LAYOUT)
                app.select_file(SOURCE)
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
