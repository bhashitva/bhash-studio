# Bhash Yantra architecture

Bhash Yantra is a general application development environment with an Android adapter first. The app developer authors Bhash and Hindi project files. The prototype implementation uses Python 3.11 and Tk so it runs without third-party Python dependencies. This bootstrap shell is a provisional implementation choice. Evaluate complex-script input, accessibility, large files and editor integration before committing to the production shell. The original roadmap proposed an Electron and Monaco evaluation.

## Boundaries

| Module | Responsibility |
| --- | --- |
| `config.py` | Parse and format the Hindi JSON dialect and validate project settings |
| `layout.py` | Validate XML and build the typed screen model |
| `project.py` | Unicode file persistence, stable application identity and conflict detection |
| `targets.py` | Validate a project snapshot and enumerate current and planned targets |
| `android.py` | Generate Kotlin/Compose and exports, then invoke the existing Bhash Android CLI |
| `app.py` | Hindi desktop UI, editor buffers, preview and background-job presentation |

The preview and generator consume the same typed screen model. The preview shows authored structure, labels and initial input values. The Android host captures the input value at the moment of the click and dispatches the text action through generated Kotlin/JNI bindings to a real Bhash function on its runtime worker. The lifecycle-bound Compose coroutine writes the returned text to the authored target. Each identified input and text result has independent `rememberSaveable` state. The legacy shared result is generated only for buttons that still use it.

The prototype bridge accepts handlers with one `पाठ` argument and a `पाठ` result. The full Bhash compiler checks source semantics during an Android build. The editor's check command validates configuration, layout and the handler signature shape. It does not implement a second Bhash compiler. Future type-aware editing should use the existing Bhash language server.

## Project and build ownership

The three authored project files remain the source of truth. Generation creates a fresh job directory beneath the configured build workspace. Each job contains the source snapshot, compiler SHA-256, input hashes, raw local tool log and generated Android project. A reference is stored in the project's `.studio` directory. The existing compiler starter pins and verifies its copied compiler JAR. Failed jobs remain available for diagnosis. Concurrent GUI jobs are blocked and a failed build never replaces an earlier build directory. The default workspace is in the OS temporary directory. Configure a persistent build root or copy artifacts to retain them across temporary-file cleanup.

On Windows the build workspace uses an ASCII path because Java launcher argument conversion and Android tools impose additional path constraints. A tiny source-mode Java launcher carries UTF-8 arguments in Base64 and forwards them to the real compiler. The compiler JAR and launcher are copied into the build workspace, so their Java argument paths are ASCII too. Authored project paths and filenames can contain Hindi. Filesystem calls use extended paths for long Windows names. Set `BHASH_STUDIO_BUILD_ROOT` to override the default cache path. Java 17 or 21 must include source-launch support. Explicit `JAVA_HOME` takes priority over PATH discovery.

Saving uses a temporary file followed by atomic replacement. Existing content hashes detect ordinary external edits before saving. This is optimistic conflict detection for a single editor process. A writer racing between comparison and replacement still requires a future file-locking protocol. Multi-file save can stop after some files are saved if a later file conflicts. Unsaved editor buffers remain available and the build is stopped.

The app launches only the explicitly configured Java/compiler with argument arrays and no command shell. The renderer treats labels as text. Generated Kotlin escapes quotes, backslashes, dollar interpolation and controls. Project symlinks to external source files and a redirected managed output directory are rejected. Project files and configured tools are trusted local developer inputs. Third-party project sandboxing is future work.

Known upstream constraints include the native Bhash runtime and JNI boundary, Android API 29 minimum, supported native ABIs and SDK/NDK versions. Generated Android files remain implementation details. Advanced users can inspect them for diagnostics, while the supported studio workflow edits the Hindi files.

## New targets

The target registry includes एंड्रॉयड, डेस्कटॉप and वेब. Only Android generation/build/run is implemented. Other targets produce an explicit Hindi message. Future adapters should accept the typed screen model and immutable source snapshot and return artifacts through the same job boundary. Platform capabilities, packaging and lifecycle policy belong to the adapter. Bhash's compiler backends remain in the existing `bhash` repository.

The studio currently applies the mobile handler contract to all project validation. Desktop and web need a capability model and their own validation before their adapters can become available. Avoid committing Android paths or Gradle state into the shared workspace model.

## Production gaps

The first prototype covers project creation, editing, validation, structural preview, export and debug build/run. Device and emulator management, automatic SDK setup, language-server completion, source debugging, interactive state previews, broader UI controls, resource catalogs, custom components, signed releases and installable desktop bundles remain on the roadmap. Test GUI input with Hindi-speaking developers before claiming the full Hindi-only end-to-end acceptance standard, especially for third-party setup and OS dialogs.
