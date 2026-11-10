import os
from pathlib import Path
import tempfile
import threading
import unittest

from bhash_studio.android import AndroidTarget, Toolchain
from bhash_studio.project import Project


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_ANDROID_TESTS") == "1", "Enable with a real Bhash compiler and Android SDK")
class AndroidIntegrationTests(unittest.TestCase):
    def test_real_apk_build(self):
        # Keep artifacts when requested, so a failed Gradle build can be diagnosed.
        location = os.environ.get("BHASH_STUDIO_TEST_OUTPUT")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(location or temp)
            root.mkdir(parents=True, exist_ok=True)
            project = Project.create(root / "हिंदी-निर्माण", "भाष परीक्षण")
            output = AndroidTarget(Toolchain.discover()).execute(project, project.snapshot(), "build",
                       threading.Event(), lambda text: print(text, flush=True))
            apk = output / "app/build/outputs/apk/debug/app-debug.apk"
            self.assertTrue(apk.is_file())
            self.assertGreater(apk.stat().st_size, 100_000)
