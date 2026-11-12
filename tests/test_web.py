import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from threading import Event
import time
import unittest
from urllib.request import Request, urlopen

from bhash_studio.android import Toolchain
from bhash_studio.errors import StudioError
from bhash_studio.project import LAYOUT, WEB_FILES, Project
from bhash_studio.web import JAVA_ENCODING, WebTarget, server_arguments, validate_web


class WebProjectTests(unittest.TestCase):
    def test_web_project_opens_and_includes_nested_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Project.create(Path(temporary) / "वेब-परीक्षण", "कार्य", "वेब")
            reopened = Project.open(project.root)
            project.add_folder("सेवा")
            project.add_file("नियम.bhash", folder="सेवा")
            snapshot = reopened.snapshot()
            self.assertEqual(set(snapshot), {*WEB_FILES, "सेवा/नियम.bhash"})
            self.assertTrue(project.file("assets/app.js").is_file())
            self.assertNotIn(LAYOUT, snapshot)
            self.assertEqual(validate_web(snapshot)[1]["dev"]["port"], 8080)

    def test_web_profile_rejects_invalid_port_before_creating_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "web"
            profiles = {"dev": {"port": True}, "staging": {"port": 8081}, "prod": {"port": 8080}}
            with self.assertRaises(StudioError):
                Project.create(root, "Web", "वेब", profiles)
            self.assertFalse(root.exists())


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_WEB_TESTS") == "1", "Enable with Bhash and Java")
class WebIntegrationTests(unittest.TestCase):
    def test_generated_bundle_serves_html_and_persists_hindi_crud(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Project.create(Path(temporary) / "वेब-परीक्षण", "कार्य", "वेब")
            tools = Toolchain.discover()
            bundle = WebTarget(tools).build(project, project.snapshot(), "staging", Event(), print)
            self.assertIn("ENV BHASH_ENV=staging", (bundle / "Dockerfile").read_text())
            command = [tools.java, *JAVA_ENCODING, "-jar", "app.jar",
                       *server_arguments("127.0.0.1", 0, "test.db")]
            log = bundle.parent / "server.log"
            with log.open("wb") as output, subprocess.Popen(
                command, cwd=bundle, env={**tools.environment(), "BHASH_ENV": "staging"},
                stdout=output, stderr=subprocess.STDOUT,
            ) as server:
                try:
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline and server.poll() is None:
                        match = re.search(r"READY ([0-9]+)", log.read_text(encoding="utf-8"))
                        if match:
                            break
                        time.sleep(0.1)
                    else:
                        self.fail(log.read_text(encoding="utf-8"))
                    url = f"http://127.0.0.1:{match[1]}"

                    def request(path, method="GET", payload=None):
                        headers = {"Content-Type": "application/json"} if payload is not None else {}
                        body = json.dumps(payload, ensure_ascii=False).encode() if headers else None
                        with urlopen(Request(url + path, body, headers, method=method), timeout=5) as response:
                            return response.read()

                    self.assertIn("मेरे कार्य", request("/").decode())
                    self.assertIn("fetch(", request("/assets/app.js").decode())
                    self.assertIn("font:", request("/assets/app.css").decode())
                    self.assertIn("ठीक", request("/health").decode())
                    request("/api/tasks", "POST", {"id": "yantra", "title": "परीक्षण"})
                    request("/api/tasks/yantra", "PUT", {"title": "परीक्षण", "done": True})
                    self.assertEqual(json.loads(request("/api/tasks")),
                                     [{"id": "yantra", "title": "परीक्षण", "done": True}])
                    request("/api/tasks/yantra", "DELETE")
                    self.assertEqual(json.loads(request("/api/tasks")), [])
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        server.kill()
            self.assertTrue((bundle / "test.db").is_file())
            self.assertIn("server_started", log.read_text(encoding="utf-8"))
