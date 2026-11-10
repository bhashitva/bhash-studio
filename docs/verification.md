# Prototype verification on November 10 2026

## Desktop and core checks

The Windows desktop suite ran 39 test methods with GUI checks enabled. Thirty-seven passed. The Android integration test was run separately and the local symlink test was skipped because the host disallows creating symlinks. The desktop widget test exercised buffer switching, Hindi editing, saving, validation and reopening. A visual review confirmed Hindi labels and the structural preview in the running desktop window.

After adding emulator coverage, the local desktop and core suite ran 45 test methods. Forty-two passed and three environment-dependent cases were skipped in that invocation. The emulator wrapper was run separately and passed, including its three result-parser regression tests.

GitHub Actions passed on Windows, Ubuntu and macOS. Windows also ran the real Tk widget workflow. The source and tests for the Android ABI and manifest fixes are in commit `9fb108b708ca3233aa4dca408d3bf65b692b999d`.

## Android build check

The generated greeting application compiled using the real Bhash 0.25.0 compiler, Java 21, Android platform 36, Build Tools 35.0.0 and NDK 28.2.13676358. Both `arm64-v8a` and `x86_64` Bhash native libraries and JNI bindings were generated. The generated Kotlin/Compose host compiled and a debug APK was packaged successfully.

The opt-in Android integration unittest also passed from a newly created Hindi-named project. It generated a fresh Android project and verified the real APK output. That test completed in approximately 158 seconds with the prepared local dependency cache and test-signing configuration.

The initial verified APK was 23,869,245 bytes and contained DEX bytecode plus both native ABIs. Its SHA-256 was `dfbd6f43b8ba91faa51a26be46050f28ad40eb30286db2feb46bc5d17c279d3f`. It is a local test artifact, with a generated application ID and a debug signing key.

The restricted verification session required a writable copy of the Gradle dependency cache, offline Gradle resolution and a workspace-local test keystore selected by a local Gradle init script. Those are validation environment settings. The normal studio build uses the existing Android toolchain's debug signing configuration. This check demonstrates a real generated app build, with those environment settings applied.

## Android emulator runtime checks

The locally running Pixel emulator used Android 10 API 29 and the x86-64 ABI. Its system locale was en-US. The studio-generated app installed successfully and displayed its Hindi title and labels. A manual tap of अभिवादन करें in Android Studio's emulator view displayed नमस्ते, दुनिया!, exercising the normal Bhash runtime startup path.

All three generated Android instrumentation tests passed in approximately 30 seconds, with zero failures or skipped cases.

| Test | Verified behavior |
| --- | --- |
| authoredTitleIsDisplayed | The Hindi title from the authored layout is visible |
| actionSurvivesRotationAndRecreation | The Bhash handler result survives landscape and portrait transitions and explicit activity recreation, with repeated button actions |
| unicodeArgumentsSurviveRepeatedNativeCalls | Forty native calls preserve nukta, conjuncts and emoji with forced garbage collection enabled |

The generator now replaces the upstream starter's original greeting tests with tests for the studio-authored screen and Bhash export. The emulator wrapper builds instrumentation APKs and uses Android's on-device runner directly. The verification environment's offline cache lacked a Gradle Unified Test Platform host plugin, so the direct runner avoided that additional host dependency. A shorter local Gradle cache path also avoided Windows filesystem path checks during test packaging.

After instrumentation, the wrapper force-stopped the test application and used the studio's existing Bhash Android run command to rebuild as needed, install and launch it on emulator-5554. The cold-launch workflow passed and the application process remained running. The complete emulator wrapper and parser checks passed in approximately 197 seconds.

Physical ARM64 device execution, full keyboard IME composition, screen-reader access and the wider Hindi-only acceptance journey require further verification.
