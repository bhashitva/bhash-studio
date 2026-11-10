# Prototype verification on November 10 2026

## Desktop and core checks

The Windows desktop suite ran 39 test methods with GUI checks enabled. Thirty-seven passed. The Android integration test was run separately and the local symlink test was skipped because the host disallows creating symlinks. The desktop widget test exercised buffer switching, Hindi editing, saving, validation and reopening. A visual review confirmed Hindi labels and the structural preview in the running desktop window.

GitHub Actions passed on Windows, Ubuntu and macOS. Windows also ran the real Tk widget workflow. The source and tests for the Android ABI and manifest fixes are in commit `9fb108b708ca3233aa4dca408d3bf65b692b999d`.

## Android build check

The generated greeting application compiled using the real Bhash 0.25.0 compiler, Java 21, Android platform 36, Build Tools 35.0.0 and NDK 28.2.13676358. Both `arm64-v8a` and `x86_64` Bhash native libraries and JNI bindings were generated. The generated Kotlin/Compose host compiled and a debug APK was packaged successfully.

The opt-in Android integration unittest also passed from a newly created Hindi-named project. It generated a fresh Android project and verified the real APK output. That test completed in approximately 158 seconds with the prepared local dependency cache and test-signing configuration.

The initial verified APK was 23,869,245 bytes and contained DEX bytecode plus both native ABIs. Its SHA-256 was `dfbd6f43b8ba91faa51a26be46050f28ad40eb30286db2feb46bc5d17c279d3f`. It is a local test artifact, with a generated application ID and a debug signing key.

The restricted verification session required a writable copy of the Gradle dependency cache, offline Gradle resolution and a workspace-local test keystore selected by a local Gradle init script. Those are validation environment settings. The normal studio build uses the existing Android toolchain's debug signing configuration. This check demonstrates a real generated app build, with those environment settings applied.

No emulator or phone was connected for installation and button-runtime validation. Device installation, lifecycle behavior on hardware, full IME composition, screen-reader access and the wider Hindi-only acceptance journey require further verification.
