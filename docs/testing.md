# Testing Bhash Yantra

Run the core suite from the repository root. It uses the Python standard library and requires no package install.

```sh
python -m unittest discover -s tests -v
```

On a desktop session, enable the real Tk widget tests. They open Help from the menu, browse to a Hindi project's configuration file, check toolchain file filters, switch files, and save and check the project. They also verify keyword coloring outside strings, live completion and keyboard acceptance, indented construct insertion, and Android job cancellation.

```powershell
$env:BHASH_STUDIO_GUI_TESTS = '1'
python -m unittest discover -s tests -p test_gui.py -v
```

For a real Android build, install Java 17 or 21, the official Bhash 0.25.0 compiler, Android Platform 36, Build Tools 35.0.0 and NDK 28.2.13676358. Accept applicable SDK licenses yourself. The existing Bhash starter may need network access for Gradle and Maven dependencies.

```powershell
$env:BHASH_COMPILER_JAR = 'C:\tools\bhash-compiler-0.25.0.jar'
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:BHASH_STUDIO_ANDROID_TESTS = '1'
python -m unittest discover -s tests -p test_integration.py -v
```

`BHASH_STUDIO_TEST_OUTPUT` optionally names an existing writable output parent where the integration test keeps its source and build logs. Give each run a fresh parent. Core tests use fixtures to verify process argument boundaries and generation. They do not claim Android execution. The optional integration test invokes the real compiler and checks a real APK. An authorized emulator or phone is needed separately for install and button behavior.

## Emulator instrumentation

Every new Android export includes `StudioScreenTest` for its authored title and first button. It replaces the upstream starter's greeting tests, which reference a different Bhash export. Action tests require fixture expectations supplied as Base64 UTF-8 instrumentation arguments. Without those expectations the action-specific tests are skipped, while the title test still runs. The native runtime uses forced GC in the test runner.

For the unchanged greeting fixture, start an Android API 29 or later emulator and point the opt-in Python wrapper at a studio-generated Android output directory. The wrapper refreshes the generated device tests, builds the app and instrumentation APKs, and installs them through ADB. It runs the three tests with Android's `am instrument` command, rejects skipped or incomplete cases, writes a JUnit-compatible result, and verifies a cold launch through the same Bhash Android CLI used by the studio. This execution path does not require Gradle's additional Unified Test Platform host plugins.

```powershell
$env:BHASH_STUDIO_DEVICE_TESTS = '1'
$env:BHASH_STUDIO_DEVICE = 'emulator-5554'
$env:BHASH_STUDIO_ANDROID_OUTPUT = 'C:\builds\JOB\android'
python -m unittest discover -s tests -p test_device.py -v
```

Use the Java and Android environment configuration above. `ANDROID_SERIAL` is set for this test subprocess only. This wrapper is restricted to emulator serials and expects the default `अभिवादन` fixture, including `नमस्ते, दुनिया!`. It checks screen text, tapping the Bhash handler, landscape and portrait transitions, activity recreation, repeated actions, and 40 native calls with nukta, conjuncts and emoji. For other applications, supply expectations appropriate to their handlers through Gradle instrumentation arguments.

## Manual acceptance

1. Launch the app and create a project using a Hindi display name and a path containing spaces and Hindi characters.
2. Change the label in पर्दा.भाषदृश्य and the greeting returned by मुख्य.bhash. Check, save and reopen.
3. Confirm सत्य and असत्य remain booleans and रिक्त remains null. Introduce a malformed value and confirm a Hindi message with source position.
4. Build an APK, run it on an API 29 or later emulator and tap the generated button. Verify the result came from the Bhash function. Rotate and check result text restoration.
5. Change the source after one build and build again. Confirm isolated output and preserved app identity.
6. Trigger an external file edit, missing tool, failed build and cancellation. Confirm recoverable state and Hindi action messages.
7. Test InScript and phonetic IME composition, conjunct caret movement, selection, copy/paste, undo and screen-reader access. Record host, Tk and OS versions. This prototype has yet to establish the production acceptance standard for these areas.

## GitHub CI

The CI workflow runs on pushes, pull requests and manual dispatches. It covers Python 3.11 and 3.12 on Windows, Ubuntu and macOS. Windows runs the real Tk desktop workflow, and Ubuntu runs it under a virtual display. A separate job builds the Python wheel and verifies the console entry point and bundled Java launcher.

Android jobs download Bhash 0.25.0 and verify its fixed SHA-256 before execution. Java 21, Android platform 36, Build Tools 35.0.0 and NDK 28.2.13676358 build the real application for ARM64 and x86-64. Hardware-accelerated x86-64 emulators on API 29 and API 36 run the instrumentation and cold-launch wrapper. Android checks run automatically in GitHub and remain opt-in when running tests locally.

Actions are pinned to commit SHAs. Workflow credentials have read-only repository access and checkout does not persist them. Gradle caching is disabled because Android projects are generated during the job. APKs, test results, logs and the Python wheel are retained as downloadable workflow artifacts for 14 days. The stable `CI checks` job succeeds only when every core, package and Android matrix job succeeds, making it suitable as the required branch check.

See [the prototype verification record](verification.md) for completed checks and their limits. Restricted build accounts may need writable Gradle and Android user directories and a workspace-local debug signing configuration. Keep any generated debug key out of Git. An existing full Android installation normally supplies its own debug signing setup.
