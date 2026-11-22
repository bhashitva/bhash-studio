import os
from pathlib import Path
import tempfile
import unittest

from bhash_studio.android import Toolchain
from bhash_studio.compiler_options import profile, with_profile
from bhash_studio.language_actions import edited_source, offset_at
from bhash_studio.lookup import catalog, plain_template, search
from bhash_studio.project import Project
from bhash_studio.signature_help import LanguageServer


class LanguageFeaturesTests(unittest.TestCase):
    def test_shared_reference_inventory_and_bilingual_queries(self):
        words = [entry for entry in catalog()["language"] if entry["kind"] == "keywords"]
        constructs = [entry for entry in catalog()["language"] if entry["kind"] == "constructs"]
        self.assertEqual(len(words), 57)
        self.assertEqual(len(constructs), 25)
        for query in ("absolute", "निरपेक्ष", "MySQL", "SQL Server", "compression"):
            self.assertTrue(search(query), query)
        for query in ("class", "foreach", "मिलान", "विकल्पसमूह"):
            self.assertTrue(search(query, "language"), query)
        for entry in catalog()["library"]:
            text, spans = plain_template(entry["template"])
            self.assertNotIn("${", text)
            self.assertTrue(all(0 <= start <= end <= len(text) for start, end in spans))

    def test_utf16_edits_and_multiple_changes(self):
        source = '😀 नमस्ते\nमान नाम = १;\n'
        self.assertEqual(offset_at(source, {"line": 0, "character": 3}), 2)
        updated = edited_source(source, [{"range": {"start": {"line": 1, "character": 4},
                                                        "end": {"line": 1, "character": 7}}, "newText": "उत्तर"}])
        self.assertIn("मान उत्तर", updated)
        self.assertEqual(profile(with_profile("name=demo\nnullSafety=legacy\n", "strict")), "strict")

    @unittest.skipUnless(os.environ.get("BHASH_COMPILER_JAR"), "Needs compiler and JDK")
    def test_compiler_navigation_rename_and_semantic_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Project(Path(temp))
            source = 'फलन मुख्य() -> शून्य { मान संख्या: पूर्णांक = १; लिखो(संख्या); }'
            buffers = {"main.bhash": source}
            server = LanguageServer()
            try:
                tools = Toolchain.discover()
                caret = source.rindex("संख्या") + 1
                result, _, _ = server.request(tools, project, "main.bhash", buffers, caret, "definition")
                self.assertTrue(result)
                result, _, _ = server.request(tools, project, "main.bhash", buffers, caret, "rename", {"newName": "उत्तर"})
                self.assertTrue(result.get("documentChanges") or result.get("changes"))
                bad = 'फलन मुख्य() -> शून्य { मान संख्या: पूर्णांक = "पाठ"; }'
                self.assertTrue(server.diagnose(tools, project, "main.bhash", {"main.bhash": bad}))
                union = 'विकल्पसमूह उत्तर { ठीक(मूल्य: पूर्णांक); खाली(); } फलन मुख्य() -> शून्य { स्थिर उ = उत्तर.ठीक(१); स्थिर न = मिलान(उ) { विकल्प उत्तर.ठीक(_) => १ }; }'
                actions, _, _ = server.request(tools, project, "main.bhash", {"main.bhash": union}, union.index("मिलान"), "codeAction")
                self.assertTrue(any(action.get("edit") for action in actions), (actions, server.diagnostics))
            finally:
                server.close()

    @unittest.skipUnless(os.environ.get("BHASH_STUDIO_GUI_TESTS") == "1", "Needs desktop")
    def test_editor_shortcuts_reach_language_actions_without_mutating_source(self):
        import tkinter as tk
        from unittest.mock import patch
        from bhash_studio.app import Studio
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as temp:
                studio = Studio(root, Project.create(Path(temp) / "demo", "Demo"),
                                settings_file=Path(temp) / "settings.json")
                editor = studio.editor
                editor.focus_force()
                root.update()
                source = editor.get("1.0", "end-1c")
                with patch("bhash_studio.app.language_action") as action:
                    for sequence, method in (("<Control-k>", "hover"), ("<Control-Shift-space>", "completion")):
                        editor.event_generate(sequence)
                        root.update()
                        action.assert_called_with(studio, method)
                self.assertEqual(editor.get("1.0", "end-1c"), source)
        finally:
            root.destroy()

    @unittest.skipUnless(os.environ.get("BHASH_STUDIO_GUI_TESTS") == "1", "Needs desktop")
    def test_reference_insertion_selection_undo_and_stale_source(self):
        import tkinter as tk
        from types import SimpleNamespace
        from bhash_studio.editor import BhashEditor
        from bhash_studio.lookup import ReferenceWindow
        root = tk.Tk()
        try:
            editor = BhashEditor(root, undo=True)
            editor.pack()
            editor.open_buffer("    ", True)
            editor.mark_set("insert", "1.4")
            studio = SimpleNamespace(root=root, editor=editor)
            reference = ReferenceWindow(studio)
            reference.apply('लिखो(${मान});')
            self.assertEqual(editor.get("1.0", "end-1c"), "    लिखो(मान);")
            self.assertEqual(editor.get("sel.first", "sel.last"), "मान")
            editor.edit_undo()
            self.assertEqual(editor.get("1.0", "end-1c"), "    ")
            reference = ReferenceWindow(studio, "language")
            editor.insert("end-1c", "बदलाव")
            before = editor.get("1.0", "end-1c")
            reference.apply('लिखो(${मान});')
            self.assertEqual(editor.get("1.0", "end-1c"), before)
            self.assertIn("बदल", reference.status.get())
        finally:
            root.destroy()
