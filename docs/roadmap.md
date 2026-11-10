# Roadmap for Bhash Studio

Bhash Studio starts with Android applications and will expand to desktop and web applications. Shared project models and target adapters keep platform-specific build and packaging work outside the common editor and schema. The Android phases below form the initial delivery track. Desktop and web need separate capability, lifecycle, preview, packaging and acceptance milestones before being enabled.

**Proposed product name** भाष विकासशाला  
**Planning date** November 10, 2026

Build a standalone desktop environment in which a Hindi-speaking developer can start with a blank project, write application logic and screens in Bhash, configure Android capabilities, test on a phone, fix failures, and ship a signed Android app. Familiarity with Latin letters and digits is sufficient for any machine identifiers the developer encounters. Every instruction, decision, and recovery step in the supported workflow is explained in Hindi.

## 1. Build on the Android implementation already in Bhash

| Area | Existing foundation observed in the workspace | Work for the studio |
| --- | --- | --- |
| Android runtime | Bhash compiles to an Android native library. The task-list starter uses Bhash for rules and SQLite and calls it from a Kotlin/Compose host through generated Kotlin/JNI bindings. | Generate the host and bindings from Bhash-owned screens and typed events. Extend the Android runtime where the app model requires it. |
| Build and release | The starter and CLI cover project creation, environment checks, build and run. Release tooling covers signed APK and AAB output. The 0.25.0 compiler snapshot contains the Android starter and release material. | Expose the same capabilities through a Hindi project and build service, with structured errors and a signing wizard. |
| Editor and device tooling | The existing language server provides a reuse point. The VS Code 0.24.1 release material describes a new-project wizard, device selection, install/run, and app-scoped logs. | Put these capabilities behind a standalone Hindi desktop shell. Add Android source debugging and a preview that shares the same screen model as the app. |
| Docs and examples | Hindi learning materials, Android tutorials and an offline task-list example are available. | Rewrite the developer journey around the studio and Hindi project files. Extend the same terminology to contextual help, test output and recovery. |

Baseline evidence comes from the workspace copies of the [Bhash compiler 0.25.0 snapshot](https://github.com/bhashitva/bhash/tree/00966e8d286590906d2b7560d167cff58ef5f3fd), [Android starter PR](https://github.com/bhashitva/bhash/pull/99), and [VS Code 0.24.1 release](https://github.com/bhashitva/bhash/releases/tag/vscode-0.24.1). Verify current upstream and reproduce builds in Phase 0.

## 2. Set the product boundary

- **Hindi everywhere the developer makes a decision.** Translate installer and update screens, menus, settings, command search, keyboard shortcut descriptions, accessibility labels, project templates, diagnostics, logs, tests, signing, support and troubleshooting. Use plain Hindi and familiar Hindi-script technical terms. Run the studio in Hindi even when the desktop OS uses another language.
- **Bhash owns the editable project.** Author app logic, state, events, reusable UI components and tests in Bhash. Use the versioned Hindi schema for declarative screens, navigation, configuration, permissions, resources, dependencies and release settings. A visual editor writes the same declarative screen model. The app developer sees one authoritative version of each screen.
- **Machine identifiers are opaque data.** Generate a stable Android application ID from a unique seed or accept a valid existing one. Display a Hindi explanation wherever an ID, URL, version number, device serial or checksum is needed. Preserve application IDs across updates and project renames. The user can use digits 0–9 and paste identifiers. Android defines the format of the application ID and uses it to identify updates. [Android app module configuration](https://developer.android.com/build/configure-app-module)
- **Validate external handoffs separately.** Google supports Hindi in Play Console. Use its Hindi interface with a tested walkthrough for account setup, identity verification, policy forms and first submission. Check actual SDK license screens, OS prompts, USB authorization and store rejections in the pilot. Provide Hindi guidance and a Hindi explanation of applicable license terms alongside the authoritative text where allowed. Keep the developer's informed assent. Treat any mandatory step that still requires understanding English as an open release blocker for that workflow. [Play Console languages](https://support.google.com/googleplay/android-developer/table/4419860?hl=hi) · [Android SDK terms](https://developer.android.com/studio/terms)

## 3. Architecture and Hindi schema

**Desktop shell.** Start with Windows 11 x64 and a standalone Electron shell with a locally bundled Monaco editor, subject to a two-week Hindi input and accessibility test. Test InScript and phonetic input, conjuncts, nukta, grapheme-aware caret and deletion, undo, search, long Hindi labels, keyboard navigation and screen readers. Reuse the Bhash language server for semantic editing. Keep build, device, emulator and debug execution in isolated local services behind a small typed interface. Evaluate Linux next and macOS after its installer and toolchain matrix pass.

**Android application pipeline.** Parse and validate Hindi source and project files into a shared, typed application model. Use it to generate Kotlin/Compose screens and platform glue, Gradle configuration, Android manifests and resources, and JNI exports under a managed build directory. Compile Bhash logic with the existing Android native target. Reuse Android tools for packaging, device control and signing. Maintain source maps from generated code to Bhash or markup and a build-ID index for native symbols. Keep compatibility with the current starter through an explicit migration path. [Command-line Android builds](https://developer.android.com/build/building-cmdline) · [Android signing](https://developer.android.com/studio/publish/app-signing)

**Bhash mobile framework.** Provide Hindi APIs for state, validation, navigation, collections, persistence, HTTP, files, permissions and device capabilities. Start with typed action and state snapshots over the existing JNI bridge and prove that the bridge supports lifecycle transitions, error propagation, cancellation and list rendering without blocking the Android UI. Keep long-running work off the UI thread and avoid a native round trip for each rendered item. Use Hindi API docs and runnable examples. For advanced capabilities, provide a curated package catalog with Hindi docs and a maintainer-facing adapter SDK. Let catalog coverage define the supported surface and grow it as integrations pass tests.

**One schema with two encodings.** Define a versioned semantic schema with Hindi field names, component names, enums, validation messages, source locations and stable identifiers. Use XML for screens and JSON for settings by default. Support both encodings through the same typed model and version rules. Allow only one authored representation of each resource in a project. Validate unknown keys, references, types and duplicate normalized names. Generate Android-safe IDs with collision checks and preserve existing mappings. Apply Unicode normalization to identifiers and schema keys under a documented policy while preserving display strings and user data. Retain comments and user formatting when practical in visual edits. Test parse–edit–save round trips and schema migrations.

XML allows Devanagari element and attribute names. Reuse Bhash's existing literals throughout source, UI expressions and configuration. `सत्य` means true, `असत्य` means false, and `रिक्त` means null. The Hindi JSON dialect accepts these as unquoted typed literals, using a dedicated parser that shares Bhash's literal definitions. Its validator, formatter, completion and migration tools must preserve those types. Standard JSON fixes its corresponding literal tokens as `true`, `false` and `null`, so the Hindi dialect needs a syntax extension as well as a schema. Translate the typed values to standard JSON only at integration boundaries that require it. Distinguish an omitted field from an explicit `रिक्त` value when the schema gives them different meanings. [XML 1.0](https://www.w3.org/TR/xml/) · [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html)

**Illustrative schema sketches**  
Names and syntax below are proposals. The event references a typed Bhash handler.

```xml
<पर्दा पहचान="मुख्य" शीर्षक="कार्यसूची">
  <स्तंभ>
    <पाठ>आज के काम</पाठ>
    <बटन दबानेपर="कार्य_जोड़ो">जोड़ें</बटन>
  </स्तंभ>
</पर्दा>
```

```text
{
  "योजना_संस्करण": 1,
  "नाम": "मेरी कार्यसूची",
  "न्यूनतम_एंड्रॉयड_स्तर": 29,
  "संजाल_अनुमति": असत्य
}
```

## 4. Delivery phases and gates

Time windows are elapsed from kickoff. They are planning ranges for a core team of roughly five full-time contributors across compiler/runtime, Android/toolchain, desktop/editor, and Hindi product quality, with design and community-pilot support. Phase 0 should refine them based on bridge and debugger results. Phases can overlap after the shared model and service boundaries are in place.

| Phase | Target window | Deliverable | Exit gate |
| --- | --- | --- | --- |
| 0. Baseline and risk tests | Weeks 1–4 | Reproduce current starter, debug and signed builds. Test desktop IME and accessibility, native Android source debugging and Hindi SDK/Play handoffs. Draft terminology and schema. | On a clean Windows machine, build and run the existing task list on an emulator and ARM64 phone. Record a debugger attach and source breakpoint or document the gap and its technical plan. |
| 1. Install and run alpha | Months 2–3 | Hindi installer, SDK setup and recovery, project wizard, editor, language server, device selection, emulator start, one-click build/install/run and filtered diagnostics. | A Hindi-speaking tester installs, creates a project, corrects an injected source error and runs it on emulator and phone from the desktop UI. |
| 2. Author screens and configuration | Months 3–5 | Hindi XML and JSON, typed state and events, Compose generator, navigation, resource and permission editors, visual preview and basic layout editing. | Rebuild the task list from a blank project using editable Hindi files only. Add and edit tasks, filter, retain data across restart and rotation, and check TalkBack. |
| 3. Debug and test on devices | Months 5–7 | Bhash source breakpoints, stepping, variables, call stacks and crash mapping. Add unit and device tests, failure explanations, Hindi logs, test templates and CI runner. | Diagnose a Bhash error, a malformed layout and a native crash from original source. Run Bhash tests and a device test suite in the IDE and CI. Verify Android lifecycle and state restoration. |
| 4. Release workflow beta | Months 7–10 | Hindi signing, secure key creation/import and backup, versioning, APK/AAB export, manifest and permission review, device checks, and Hindi Play submission guidance. | A pilot team signs and installs a release APK, submits an AAB to Play internal testing and ships a same-ID update that preserves data. Validate applicable target API, ABI and 16 KB native packaging requirements. |
| 5. Production v1 | Months 10–12 | Curated Android APIs and packages, project migration and recovery, stable update channel, Hindi reference and tutorials, and a supported Windows/device matrix. | Independent Hindi-speaking pilot teams complete the acceptance journey for multiple app types. Zero release-blocking English dependencies or unresolved critical workflow failures. |
| 6. Broader IDE capability | Months 12–24 | Profiling, device and layout inspection, advanced refactoring, build variants and multi-module apps, wider Android APIs, richer version control and CI, and additional desktop hosts. | Publish a capability matrix and demonstrate each newly supported workflow end to end in Hindi before marking it supported. |

Release engineering should continuously test current Play target API requirements and native-library alignment for release builds. Preserve signing-key separation, use protected OS credential storage, and include a Hindi key backup and restore drill. [Target API requirements](https://developer.android.com/google/play/requirements/target-sdk) · [16 KB page-size support](https://developer.android.com/guide/practices/page-sizes)

## 5. What production v1 must support

1. **Build three realistic reference apps.** Use an offline task list with local storage and process-death recovery, an inventory app with forms and a camera or photo-picker flow, and a catalog app with HTTP, loading/error states, offline caching and retry. At least one app ships a signed update and preserves user data.
2. **Cover the whole developer journey.** Install → create → author screens and logic → configure capabilities → preview → run on emulator and phone → debug → test → sign → distribute → update. Complete every supported step with Hindi documentation and the visible controls provided. Include an offline build after prerequisites are cached.
3. **Test failure paths.** Inject missing SDK components, a device that has yet to authorize USB debugging, a disconnected network, a malformed layout, permission denial, a native crash, a wrong signing key and a rejected upload. A failure is acceptable only when the studio explains what happened and what the developer can do next in Hindi. Preserve stable diagnostic codes and capture raw tool detail in an opt-in maintainer bundle with secrets redacted.
4. **Enforce localization in builds and pilot tests.** Fail CI on missing Hindi strings or English fallback for first-party messages. Run screenshot and accessibility-tree checks and maintain a small allowlist for opaque IDs, version numbers and URLs. Have Hindi-dominant developers complete the journey without English documentation or interpreter help. A visible action, blocker, or recovery step that requires English comprehension fails the gate.
5. **Verify support and recovery.** Check install/update rollback, migration from an earlier schema, reproducible build inputs, signing backup restore, source-to-crash mapping and project export. Cover a low-spec Windows laptop, an emulator, an older supported ARM64 phone and a current ARM64 phone.

## 6. First 30 days

| Week | Work | Reviewable result |
| --- | --- | --- |
| 1 | Inventory the Android compiler, starter and extension workflows. Build on a clean Windows machine, on the emulator and on an ARM64 phone. Walk a Hindi user through the existing setup. | Baseline report with commands, tested versions and a list of English-dependent steps. |
| 2 | Prototype the standalone Hindi editor and background build service. Run input, shaping, accessibility and native debugger spikes in parallel. | Desktop prototype, debugger findings, and a shell decision based on observed behavior. |
| 3 | Write the draft schema and event contract. Generate a screen, manifest and safe identifiers. Bind a Hindi button to Bhash logic and map an injected error back to its source. | A minimal project whose entire editable surface is Hindi. |
| 4 | Move the prototype from installation through signed export. Run two pilot walkthroughs, log failures and prioritize fixes. | Recorded demonstration, schema and build contracts, and an ordered backlog for alpha. |

Start with the offline task list. By the end of Phase 2, a developer should be able to recreate it from a blank project, including the UI, state, validation and configuration, without opening the generated Android host.
