"""Exercise source-level Android debugging on a connected emulator."""

import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import unittest
import xml.etree.ElementTree as ET

from bhash_studio.android import Toolchain
from bhash_studio.android_debug import debug_android
from bhash_studio.debug import adapter_path
from bhash_studio.project import Project, SOURCE


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_ANDROID_DEBUG_TESTS") == "1", "Requires Android emulator and LLDB")
class AndroidDebugTests(unittest.TestCase):
    def test_button_breakpoint_and_local_value(self):
        tools = Toolchain.discover()
        adb = Path(tools.sdk) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        serial = os.environ.get("BHASH_STUDIO_DEVICE", "emulator-5554")
        events, commands = queue.Queue(), queue.Queue()
        cancel = threading.Event()

        def device(*args):
            return subprocess.check_output([str(adb), "-s", serial, *args], timeout=30).decode("utf-8")

        def wait_for(kind, timeout=300):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    event = events.get(timeout=max(.01, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if isinstance(event, Exception):
                    raise event
                if event.kind == kind:
                    return event.value
                if event.kind == "output":
                    print(event.value, end="", flush=True)
            self.fail(f"Debugger event not received: {kind}")

        with tempfile.TemporaryDirectory() as temp:
            project = Project.create(Path(temp) / "android-debug", "Debug")
            project.file(SOURCE).write_text('''फलन अभिवादन(नाम: पाठ) -> पाठ {
    मान संदेश: पाठ = "नमस्ते";
    लौटाओ संदेश + नाम;
}
''', encoding="utf-8")

            def start():
                try:
                    debug_android(tools, project, project.snapshot(), adapter_path(), serial, cancel,
                                  print, events.put, {SOURCE: [3]}, commands)
                except Exception as error:
                    events.put(error)

            worker = threading.Thread(target=start, daemon=True)
            worker.start()
            try:
                wait_for("running", 600)
                device("shell", "uiautomator", "dump", "/sdcard/yantra-debug-window.xml")
                xml = ET.fromstring(device("shell", "cat", "/sdcard/yantra-debug-window.xml"))
                button = next(node for node in xml.iter("node") if node.get("text") == "अभिवादन करें")
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", button.get("bounds")))
                device("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
                stop, reason, frames = wait_for("stopped", 30)
                self.assertEqual(reason, "breakpoint")
                frame = next(frame for frame in frames if frame.get("project_file") == SOURCE)
                self.assertEqual(frame["line"], 3)
                commands.put(("scopes", stop, (frame["id"],)))
                _, _, scopes, _ = wait_for("scopes", 30)
                local = next(scope for scope in scopes if scope.get("presentationHint") == "locals")
                commands.put(("variables", stop, ("local", local["variablesReference"])))
                _, _, _, values = wait_for("variables", 30)
                self.assertIn(("संदेश", '"नमस्ते"'), [(row["name"], row["value"]) for row in values])
                commands.put(("continue", stop, ()))
                wait_for("running", 30)
            finally:
                cancel.set()
                worker.join(timeout=60)
            self.assertFalse(worker.is_alive())
