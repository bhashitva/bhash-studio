# Testing Bhash Studio

Run the core suite from the repository root. It uses the Python standard library and requires no package install.

```sh
python -m unittest discover -s tests -v
```

On a desktop session, enable the real Tk widget test. It edits, switches buffers, saves, invokes the check button and reopens the project through normal application methods.

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

## Manual acceptance

1. Launch the app and create a project using a Hindi display name and a path containing spaces and Hindi characters.
2. Change the label in पर्दा.भाषदृश्य and the greeting returned by मुख्य.bhash. Check, save and reopen.
3. Confirm सत्य and असत्य remain booleans and रिक्त remains null. Introduce a malformed value and confirm a Hindi message with source position.
4. Build an APK, run it on an API 29 or later emulator and tap the generated button. Verify the result came from the Bhash function. Rotate and check result text restoration.
5. Change the source after one build and build again. Confirm isolated output and preserved app identity.
6. Trigger an external file edit, missing tool, failed build and cancellation. Confirm recoverable state and Hindi action messages.
7. Test InScript and phonetic IME composition, conjunct caret movement, selection, copy/paste, undo and screen-reader access. Record host, Tk and OS versions. This prototype has yet to establish the production acceptance standard for these areas.

CI runs core tests on Windows, Ubuntu and macOS, plus the Tk workflow on Windows. Android SDK builds are opt-in local integration checks in this first release.

See [the prototype verification record](verification.md) for completed checks and their limits. Restricted build accounts may need writable Gradle and Android user directories and a workspace-local debug signing configuration. Keep any generated debug key out of Git. An existing full Android installation normally supplies its own debug signing setup.
