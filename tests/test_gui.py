import os
from pathlib import Path
import tempfile
import unittest

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
                app.buttons["save"].invoke()
                app.buttons["check"].invoke()
                root.update()
                self.assertIn("हिंदी टिप्पणी", Project.open(project.root).read(SOURCE))
                self.assertIn("जाँच सफल", app.output.get("1.0", "end"))
                self.assertEqual(len(app.preview.winfo_children()), 2)
            finally:
                root.destroy()
