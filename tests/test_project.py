from pathlib import Path
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from bhash_studio.config import dumps, loads
from bhash_studio.errors import StudioError
from bhash_studio.project import BUILD_DIRECTORY, CONFIG, SOURCE, FILES, Project, LocalPath, digest


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "मेरी परियोजना"
        self.project = Project.create(self.directory, "हिंदी ऐप")

    def test_create_open_and_unicode_round_trip(self):
        reopened = Project.open(self.directory)
        self.assertEqual(set(reopened.snapshot()), set(FILES))
        config = loads(reopened.read(CONFIG))
        self.assertEqual(config["नाम"], "हिंदी ऐप")
        self.assertIs(config["संजाल_अनुमति"], False)
        self.assertIsNone(config["प्रारंभिक_मान"])

    def test_existing_directory_is_preserved(self):
        before = self.project.snapshot()
        with self.assertRaises(StudioError):
            Project.create(self.directory, "दूसरा नाम")
        self.assertEqual(self.project.snapshot(), before)

    def test_external_edits_are_preserved(self):
        old = self.project.read(SOURCE)
        file = self.directory / SOURCE
        file.write_text("बाहरी लिखावट", encoding="utf-8")
        with self.assertRaises(StudioError):
            self.project.save(SOURCE, "अपनी लिखावट", digest(old))
        self.assertEqual(file.read_text(encoding="utf-8"), "बाहरी लिखावट")

    def test_atomic_save_and_reopen(self):
        old = self.project.read(SOURCE)
        changed = old + "\n// टिप्पणी\n"
        self.project.save(SOURCE, changed, digest(old))
        self.assertEqual(Project.open(self.directory).read(SOURCE), changed)

    def test_application_id_cannot_accidentally_change(self):
        old = self.project.read(CONFIG)
        config = loads(old)
        config["ऐप_पहचान"] = "org.other.app"
        with self.assertRaises(StudioError):
            self.project.save(CONFIG, dumps(config), digest(old))
        self.assertEqual(self.project.read(CONFIG), old)

    def test_save_failure_retains_original(self):
        old = self.project.read(SOURCE)
        with patch("bhash_studio.project.os.replace", side_effect=OSError("disk")), self.assertRaises(OSError):
            self.project.save(SOURCE, "बदला हुआ", digest(old))
        self.assertEqual(self.project.read(SOURCE), old)
        self.assertEqual({f.name for f in self.directory.iterdir()}, set(FILES))

    def test_creation_failure_never_publishes_partial_project(self):
        destination = Path(self.temp.name) / "अधूरी"
        with patch("bhash_studio.project.atomic_write", side_effect=OSError("disk")), self.assertRaises(OSError):
            Project.create(destination, "ऐप")
        self.assertFalse(destination.exists())

    def test_paths_outside_project_are_rejected(self):
        with self.assertRaises(StudioError):
            self.project.read("../secret")

    def test_add_file_creates_or_copies_without_overwriting(self):
        filename = "नया.भाषदृश्य"
        self.project.add_file(filename)
        self.assertEqual(self.project.read(filename), "")
        original = Path(self.temp.name) / "चित्र.bin"
        data = b"\x00\xff"
        original.write_bytes(data)
        self.project.add_file(original.name, original)
        self.assertEqual((self.project.root / original.name).read_bytes(), data)
        self.assertEqual(original.read_bytes(), data)
        with self.assertRaises(StudioError):
            self.project.add_file(original.name)
        with self.assertRaises(StudioError):
            self.project.add_file("../बाहर")
        self.assertEqual((self.project.root / original.name).read_bytes(), data)

    def test_long_hindi_project_paths(self):
        parent = LocalPath(self.temp.name) / ("a" * 80) / ("b" * 80)
        parent.mkdir(parents=True)
        if os.name == "nt":
            # Keep recursive cleanup in extended-path form even when its root is short.
            parent.relative_to(Path(self.temp.name))
            self.addCleanup(shutil.rmtree, "\\\\?\\" + str(parent.parent))
        project = Project.create(parent / "हिंदी", "हिंदी ऐप")
        old = project.read(SOURCE)
        project.save(SOURCE, old + "\n", digest(old))
        self.assertEqual(Project.open(project.root).read(SOURCE), old + "\n")

    def test_build_cleanup_removes_long_children_under_a_short_root(self):
        name = "0123456789abcdef"
        output = self.project.root / BUILD_DIRECTORY
        job = output / name
        if os.name == "nt":
            self.addCleanup(shutil.rmtree, output.extended_path())
        nested = job / "android" / "app" / "build" / ("intermediate_" * 10) / ("bucket_" * 15)
        nested.mkdir(parents=True)
        (nested / "result.dex").write_bytes(b"test")
        self.assertLess(len(str(job)), 248)
        self.assertGreater(len(str(nested)), 260)
        self.assertEqual(self.project.previous_builds(), [name])
        self.assertTrue(self.project.remove_build(name))
        self.assertFalse(job.exists())
        self.assertTrue(output.is_dir())

    def test_symlink_files_are_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.write_text("private", encoding="utf-8")
        file = self.directory / SOURCE
        file.unlink()
        try:
            file.symlink_to(outside)
        except OSError:
            self.skipTest("Host does not permit symlinks")
        with self.assertRaises(StudioError):
            self.project.read(SOURCE)
