import io
import json
import os
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from bhash_studio.android import Toolchain
from bhash_studio.debug import DebugEvent, WebDebugger, read_message, scalar_value
from bhash_studio.project import SOURCE, Project


class DebugProtocolTests(unittest.TestCase):
    def test_framing_preserves_devanagari(self):
        message = {"name": "संख्या", "value": "१२"}
        payload = json.dumps(message, ensure_ascii=False).encode()
        stream = io.BytesIO(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
        self.assertEqual(read_message(stream), message)
        self.assertIsNone(read_message(stream))

    def test_only_typed_scalar_literals_can_be_written(self):
        self.assertEqual(scalar_value({"type": "long long"}, "-१२"), "-12")
        self.assertEqual(scalar_value({"type": "double"}, "१.२५"), "1.25")
        self.assertEqual(scalar_value({"type": "bool"}, "सत्य"), "true")
        self.assertIsNone(scalar_value({"type": "long long"}, "f()"))
        self.assertIsNone(scalar_value({"type": "double"}, "1e999"))
        self.assertIsNone(scalar_value({"type": "unsigned char"}, "256"))
        self.assertIsNone(scalar_value({"type": "long long", "variablesReference": 4}, "42"))
        self.assertIsNone(scalar_value({"type": "पाठ"}, "42"))

    def test_lldb_18_reports_edited_value_as_result(self):
        events = []
        debugger = WebDebugger(None, None, None, [], 0, {}, threading.Event(), events.append)
        debugger.thread = 1
        with patch.object(debugger, "_call", return_value={"result": "41"}) as call:
            debugger._command("setVariable", 0, ("node", 1, {"name": "संख्या"}, "41"))
        call.assert_called_once_with("setVariable", variablesReference=1, name="संख्या", value="41")
        self.assertEqual(events, [DebugEvent("edited", (0, "node", "41"))])


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_DEBUG_TESTS") == "1", "Enable with native Bhash, LLDB, and Tk")
class WebDebuggerIntegrationTests(unittest.TestCase):
    def test_break_step_edit_and_resume_http_request(self):
        import tkinter as tk
        from bhash_studio.app import Studio

        with tempfile.TemporaryDirectory() as temporary, socket.socket() as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
            port_probe.close()
            root = Path(temporary)
            project = Project.create(root / "वेब", "कार्य", "वेब", {
                "dev": {"port": port}, "staging": {"port": 8081}, "prod": {"port": 8080},
            })
            source = project.read(SOURCE)
            original = 'सार्वजनिक फलन संभालो(अनुरोध: वेबअनुरोध) -> वेबउत्तर { लौटाओ वेब.पाठउत्तर(२००,"ठीक\\n"); }'
            self.assertIn(original, source)
            source = source.replace(original, """सार्वजनिक फलन संभालो(अनुरोध: वेबअनुरोध) -> वेबउत्तर {
        मान संख्या: पूर्णांक = २०;
        संख्या = उत्तरसंख्या(संख्या);
        लौटाओ वेब.पाठउत्तर(२००, वेब.अंक(संख्या));
    }""") + """
फलन उत्तरसंख्या(इनपुट: पूर्णांक) -> पूर्णांक {
    लौटाओ इनपुट + १;
}
"""
            project.file(SOURCE).write_text(source, encoding="utf-8")
            line = next(n for n, text in enumerate(source.splitlines(), 1) if "संख्या = उत्तरसंख्या" in text)
            window = tk.Tk()
            app = Studio(window, project=project, tools=Toolchain.discover(),
                         settings_file=root / "settings.json")
            output = queue.Queue()

            def request():
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=45) as response:
                        output.put(response.read())
                except OSError as error:
                    output.put(error)

            def until(predicate, timeout=15):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    window.update()
                    if predicate():
                        return
                    if app.worker is None:
                        break
                    time.sleep(.025)
                self.fail(app.output.get("1.0", "end"))

            try:
                app.editors[SOURCE].mark_set("insert", f"{line}.0")
                app.toggle_breakpoint()
                app.start_debug()
                until(lambda: app.web_port == port, timeout=150)
                requester = threading.Thread(target=request, daemon=True)
                requester.start()
                view = app.debug_view
                until(lambda: app.debug_location == (SOURCE, line))
                self.assertTrue(output.empty())

                def find_scalar():
                    return next(((node, reference, variable) for node, (reference, variable) in view.nodes.items()
                                 if variable.get("name") == "संख्या"), None)

                until(find_scalar)
                node, reference, variable = find_scalar()
                self.assertEqual(variable["value"], "20")
                view.variables.selection_set(node)
                window.update()
                self.assertEqual(str(view.edit_button.cget("state")), "normal")
                app.send_debug("setVariable", view.stop_id, node, reference, variable, "41")
                until(lambda: tuple(map(str, view.variables.item(node, "values"))) == ("41",))
                first_stop = view.stop_id
                view.resume("stepIn")
                until(lambda: view.stop_id is not None and view.stop_id != first_stop
                      and any("उत्तरसंख्या" in frame["name"] for frame in view.frames.values()))
                inner_stop = view.stop_id
                view.resume("stepOut")
                until(lambda: view.stop_id is not None and view.stop_id != inner_stop)
                view.resume("continue")
                until(lambda: not output.empty())
                self.assertEqual(output.get_nowait(), b"42")
                requester.join(timeout=5)
                app.cancel.set()
                until(lambda: app.worker is None)
                self.assertEqual(app.editors[SOURCE].cget("state"), "normal")
            finally:
                app.cancel.set()
                if app.worker:
                    app.worker.join(timeout=15)
                window.destroy()
