# Yantra Windows installer preview

The Windows x64 ZIP is a per-user installer. Extract it, run `Install.cmd`,
then open **Bhash Yantra** from the Start menu. Setup validates Python/Tk,
JDK 21, and native debugger candidates before reusing them. It keeps
fallback tools under the installation directory and leaves the system PATH
alone. It supports the following options:

- `-SkipDebugTools` to skip downloading LLVM-MinGW.
- `-InstallAndroidPackages` to let Google's existing SDK Manager install
  missing SDK packages and prompt for licenses.
- `-InstallRoot <path>` and `-NoShortcut` for a staged or test installation.

Google's Android SDK is installed separately under Google's terms. Setup
detects `ANDROID_HOME`, `ANDROID_SDK_ROOT`, or the normal per-user SDK folder.
Clang and LLDB are fetched from LLVM-MinGW's publisher when a compatible
installation is missing. The developer tools themselves are optional for
editing and JVM web builds. See the archive README for third-party terms.

## Build the installer

From the repository root on Windows with Python 3.11+:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/fetch.ps1 -Directory installer-inputs
python packaging/windows/build.py installer-inputs dist/Bhash-Yantra-Windows-x64.zip
```

The builder verifies each pinned SHA-256 and puts the JDK's corresponding
source archive next to the binary. Release binaries are not checked into Git.
Linux/WSL and macOS can continue to use the Python installation from the main
README with system-provided Tk, Java, and platform-specific tools.
