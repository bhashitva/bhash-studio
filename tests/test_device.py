"""Opt-in emulator checks against an existing studio-generated Android project."""

import base64
import json
import os
import re
import subprocess
import threading
import unittest
import xml.etree.ElementTree as ET

from bhash_studio.android import AndroidTarget, Toolchain, generate_device_tests, run_tool
from bhash_studio.layout import parse_layout
from bhash_studio.project import LAYOUT, LocalPath as Path, atomic_write


EXPECTED_TESTS = {"authoredTitleIsDisplayed", "actionSurvivesRotationAndRecreation", "unicodeArgumentsSurviveRepeatedNativeCalls"}


def instrumentation_cases(output):
    """Reject incomplete runs, failures and skipped cases even when adb exits zero."""
    fields = {}
    passed = []
    for line in output.splitlines():
        if line.startswith("INSTRUMENTATION_STATUS: "):
            key, _, value = line[len("INSTRUMENTATION_STATUS: "):].partition("=")
            fields[key] = value
        elif line.startswith("INSTRUMENTATION_STATUS_CODE:"):
            code = int(line.partition(":")[2])
            if code <= 0 and "test" in fields:
                if code != 0:
                    raise AssertionError("Instrumentation case failed or skipped: " + fields["test"])
                passed.append(fields["test"])
            fields = {}
    if not re.search(r"(?m)^INSTRUMENTATION_CODE:\s*-1\s*$", output):
        raise AssertionError("Instrumentation did not finish successfully")
    if len(passed) != 3 or set(passed) != EXPECTED_TESTS:
        raise AssertionError("All three expected instrumentation cases must pass")
    return passed


class InstrumentationResultTests(unittest.TestCase):
    def report(self, code=0, complete=True):
        text = "".join(f"INSTRUMENTATION_STATUS: test={name}\nINSTRUMENTATION_STATUS_CODE: {code}\n" for name in sorted(EXPECTED_TESTS))
        return text + ("INSTRUMENTATION_CODE: -1\n" if complete else "")

    def test_complete_success_is_recognized(self):
        self.assertEqual(set(instrumentation_cases(self.report())), EXPECTED_TESTS)

    def test_failure_and_assumption_skip_are_rejected(self):
        for code in (-2, -3):
            with self.subTest(code=code), self.assertRaises(AssertionError):
                instrumentation_cases(self.report(code))

    def test_incomplete_run_is_rejected(self):
        with self.assertRaises(AssertionError):
            instrumentation_cases(self.report(complete=False))


@unittest.skipUnless(os.environ.get("BHASH_STUDIO_DEVICE_TESTS") == "1", "Enable emulator instrumentation explicitly")
class EmulatorTests(unittest.TestCase):
    def test_hindi_handler_rotation_recreation_unicode_and_cold_launch(self):
        output = Path(os.environ["BHASH_STUDIO_ANDROID_OUTPUT"]).resolve()
        job = output.parent
        serial = os.environ.get("BHASH_STUDIO_DEVICE", "emulator-5554")
        self.assertTrue(serial.startswith("emulator-"), "Use an emulator for this fixture")
        tools = Toolchain.discover()
        env = tools.environment()
        env["ANDROID_SERIAL"] = serial
        adb = Path(tools.sdk) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        def device(*arguments, timeout=60):
            result = subprocess.run([str(adb), "-s", serial, *arguments], capture_output=True,
                                    timeout=timeout, env=env, creationflags=flags)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
            return result.stdout.decode("utf-8", errors="replace").strip()

        self.assertEqual(device("get-state"), "device")
        self.assertEqual(device("shell", "getprop", "sys.boot_completed"), "1")
        screen = parse_layout((job / LAYOUT).read_text(encoding="utf-8"))
        test = output / "app/src/androidTest/java/org/bhashitva/androidstarter/StarterTest.kt"
        atomic_write(test, generate_device_tests(screen))
        expected = {
            "expectedResultBase64": "नमस्ते, दुनिया!",
            "inputBase64": "दुनिया",
            "unicodeArgumentBase64": "क़ क्ष ज्ञ 😀",
            "unicodeResultBase64": "नमस्ते, क़ क्ष ज्ञ 😀!",
        }
        command = [tools.java, "-Dfile.encoding=UTF-8", "-cp", str(output / "gradle/wrapper/gradle-wrapper.jar"),
                   "org.gradle.wrapper.GradleWrapperMain", ":app:assembleDebug", ":app:assembleDebugAndroidTest", "--no-daemon", "--console=plain"]
        run_tool(command, output, env, job / "device-test.log", threading.Event())
        device("install", "-r", str(output / "app/build/outputs/apk/debug/app-debug.apk"))
        device("install", "-r", "-t", str(output / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"))
        metadata = json.loads((output / "app/build/outputs/apk/androidTest/debug/output-metadata.json").read_text())
        arguments = ["shell", "am", "instrument", "-w", "-r", "-e", "class", "org.bhashitva.androidstarter.StudioScreenTest"]
        for key, value in expected.items():
            arguments += ["-e", key, base64.b64encode(value.encode("utf-8")).decode("ascii")]
        arguments.append(metadata["applicationId"] + "/org.bhashitva.androidstarter.StarterTestRunner")
        result = device(*arguments, timeout=300)
        atomic_write(job / "instrumentation-output.txt", result)
        passed = instrumentation_cases(result)
        suite = ET.Element("testsuite", tests="3", failures="0", errors="0", skipped="0")
        for name in passed:
            ET.SubElement(suite, "testcase", classname="org.bhashitva.androidstarter.StudioScreenTest", name=name)
        atomic_write(job / "device-results.xml", ET.tostring(suite, encoding="unicode"))
        properties = dict(line.split("=", 1) for line in (output / "gradle.properties").read_text().splitlines() if "=" in line)
        app_id = properties["bhashApplicationId"]
        device("shell", "am", "force-stop", app_id)
        target = AndroidTarget(tools)
        run_tool(target.command(["android", "run", str(output), "--device", serial]),
                 job, env, job / "device-test.log", threading.Event())
        self.assertTrue(device("shell", "pidof", app_id), "The cold-launched app must remain running")
        print("Three emulator instrumentation tests and cold-launch CLI workflow passed", flush=True)
