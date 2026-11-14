# Android source debugging

Use the Bhash compiler 0.25.2 or later, JDK 17 or 21, the Android SDK with
Platform Tools and NDK, and a Python-enabled LLDB DAP adapter. Configure the
compiler JAR, Android SDK and LLDB path in **औज़ार → औज़ार सेटिंग…**.
The Windows v0.2.0 installer includes compiler 0.25.2. For a source installation, download the [compiler JAR](https://github.com/bhashitva/bhash/releases/tag/bhash-0.25.2).

1. Connect an authorized x86_64 or arm64-v8a device or start an emulator.
   Select its ADB serial in tool settings if several devices are ready.
2. Open an Android project and press **F9** on an executable line in a
   Bhash button handler.
3. Choose **एंड्रॉयड → उपकरण पर स्रोत डिबगिंग शुरू करें**. Yantra builds
   and installs a debuggable APK, opens the activity, and attaches LLDB.
4. Trigger the handler after the debugger reports it has attached. Use the
   call stack, stepping controls, and variable pane as with web debugging.
   The **मान बदलें…** button is available for supported writable scalars.
5. Choose **एंड्रॉयड → काम रोकें** to detach and remove the ADB forwarding.

The device must support Android's `run-as` for debuggable applications.
This workflow attaches after activity startup and covers Bhash native
code reached after attachment. Kotlin and Java use their own debugger.
