Bhash Yantra Windows x64 installer preview

Extract the entire ZIP to a local folder. Run Install.cmd from that folder.
Setup installs per-user and adds Bhash Yantra to the Start menu.

Setup reuses Python 3.11 through 3.14 with Tk and a full JDK 21 when found.
Compatible Windows trash dependencies are reused, or installed privately.
The pinned Bhash compiler is included. The installer can download the
checksum-pinned LLVM-MinGW toolchain from its publisher for native debugging
if compatible tools are missing. For an offline core install, run
Install.cmd -SkipDebugTools. Existing Android SDKs are detected. Install
missing SDK packages through Android Studio or Google's sdkmanager.
If Google's command-line tools are already in that SDK, run
Install.cmd -InstallAndroidPackages to request only missing packages from
Google. sdkmanager prompts for any required license acceptance.

Third-party software

CPython 3.13.12 Windows x64 installer (PSF and bundled third-party licenses)
https://www.python.org/downloads/release/python-31312/
License and third-party notices are included in its distribution. The
installed Python distribution includes LICENSE.txt. Tcl/Tk is included.

Eclipse Temurin OpenJDK 21.0.10+7 (GPL-2.0 with Classpath Exception and
component-specific terms). The unmodified upstream binary ZIP includes its
legal directory. The corresponding upstream source archive is alongside it
as payload/java-source.tar.gz.
https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.10%2B7

Bhash compiler 0.25.0 (Apache-2.0 and component-specific terms).
See META-INF/bhash and third-party notices in payload/compiler.jar.
https://github.com/bhashitva/bhash/releases/tag/bhash-0.25.0

Send2Trash 2.1.0 and pywin32 312 are unmodified upstream wheels.
Their license files are inside the wheels and are preserved on extraction.
https://pypi.org/project/Send2Trash/2.1.0/
https://pypi.org/project/pywin32/312/

LLVM-MinGW 20240619 is obtained directly from its publisher.
https://github.com/mstorsjo/llvm-mingw/releases/tag/20240619
Android SDK packages are supplied separately by Google.
https://developer.android.com/studio/terms
