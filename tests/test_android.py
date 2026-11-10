import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from bhash_studio.android import AndroidTarget, Toolchain, run_tool
from bhash_studio.config import dumps, loads
from bhash_studio.errors import StudioError
from bhash_studio.project import CONFIG, SOURCE, Project


class AndroidTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = Project.create(self.root / "ऐप", "हिंदी ऐप")
        self.jar = self.root / "compiler.jar"
        self.jar.write_bytes(b"test compiler fixture")
        self.tools = Toolchain(str(self.jar), sys.executable, "", str(self.root / "builds"))
        self.calls = []

    def fixture_runner(self, command, cwd, env, log, cancel):
        self.assertTrue(all(value.isascii() for value in command[5:]))
        arguments = [base64.urlsafe_b64decode(value).decode("utf-8") for value in command[5:]]
        self.calls.append(arguments)
        if "init" in arguments:
            destination = Path(arguments[2])
            (destination / "src").mkdir(parents=True)
            (destination / "src/greeting.bhash").write_text("old", encoding="utf-8")
            (destination / "gradle.properties").write_text("", encoding="utf-8")
            (destination / "app/src/main/java/org/bhashitva/androidstarter").mkdir(parents=True)
            manifest = destination / "app/src/main/AndroidManifest.xml"
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application/></manifest>', encoding="utf-8")
        elif arguments[1] in {"build", "run"}:
            apk = Path(arguments[2]) / "app/build/outputs/apk/debug/app-debug.apk"
            apk.parent.mkdir(parents=True)
            apk.write_bytes(b"APK fixture")
        return ""

    def execute(self, operation="export", snapshot=None):
        return AndroidTarget(self.tools, self.fixture_runner).execute(self.project, snapshot or self.project.snapshot(), operation,
                   threading.Event(), lambda _: None)

    def test_export_preserves_authored_source_and_records_inputs(self):
        original = self.project.snapshot()
        output = self.execute()
        self.assertEqual(self.project.snapshot(), original)
        self.assertEqual((output / "src" / SOURCE).read_text(encoding="utf-8"), original[SOURCE])
        self.assertFalse((output / "src/greeting.bhash").exists())
        self.assertIn("अभिवादन", (output / "bhash.exports").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((output.parent / "build-inputs.json").read_text())["schema"], 1)

    def test_repeated_export_has_isolated_output(self):
        self.assertNotEqual(self.execute(), self.execute())

    def test_network_permission_maps_to_manifest(self):
        snapshot = self.project.snapshot()
        config = loads(snapshot[CONFIG])
        config["संजाल_अनुमति"] = True
        snapshot[CONFIG] = dumps(config)
        output = self.execute(snapshot=snapshot)
        self.assertIn("android.permission.INTERNET", (output / "app/src/main/AndroidManifest.xml").read_text())

    def test_unimplemented_target_cannot_build(self):
        for target in ("वेब", "डेस्कटॉप"):
            snapshot = self.project.snapshot()
            config = loads(snapshot[CONFIG])
            config["लक्ष्य"] = target
            snapshot[CONFIG] = dumps(config)
            with self.assertRaises(StudioError):
                self.execute(snapshot=snapshot)
        self.assertEqual(self.calls, [])

    def test_missing_toolchain_has_hindi_error(self):
        with self.assertRaisesRegex(StudioError, "कंपाइलर"):
            Toolchain().validate()

    def test_java_home_has_priority_over_path(self):
        with patch.dict(os.environ, {"JAVA_HOME": str(self.root / "jdk")}), patch("shutil.which", return_value="other-java"):
            self.assertIn(str(self.root / "jdk"), Toolchain.discover().java)

    def test_build_calls_existing_cli_without_shell(self):
        output = self.execute("build")
        self.assertEqual(self.calls[-1][-3:], ["android", "build", str(output)])

    def test_subprocess_success(self):
        text = run_tool([sys.executable, "-c", "print('ok')"], self.root, os.environ.copy(), self.root / "log", threading.Event(), timeout=5)
        self.assertIn("ok", text)

    def test_subprocess_failure_hides_raw_english(self):
        with self.assertRaisesRegex(StudioError, "निर्माण असफल"):
            run_tool([sys.executable, "-c", "raise SystemExit(3)"], self.root, os.environ.copy(), self.root / "log", threading.Event(), timeout=5)

    def test_subprocess_timeout_and_cancel(self):
        event = threading.Event()
        event.set()
        with self.assertRaisesRegex(StudioError, "रोक"):
            run_tool([sys.executable, "-c", "pass"], self.root, os.environ.copy(), self.root / "log", event)
        with self.assertRaisesRegex(StudioError, "अधिक समय"):
            run_tool([sys.executable, "-c", "import time; time.sleep(30)"], self.root, os.environ.copy(), self.root / "log", threading.Event(), timeout=0.3)

    def test_active_process_can_be_cancelled(self):
        event = threading.Event()
        timer = threading.Timer(0.3, event.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaisesRegex(StudioError, "रोक"):
            run_tool([sys.executable, "-c", "import time; time.sleep(30)"], self.root, os.environ.copy(), self.root / "log", event, timeout=5)
