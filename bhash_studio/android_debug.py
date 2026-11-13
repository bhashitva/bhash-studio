"""Attach LLDB to the debuggable Android APK built by Yantra."""

import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from .android import AndroidTarget
from .debug import WebDebugger
from .errors import StudioError
from .targets import validate_snapshot


def debug_android(tools, project, snapshot, adapter, device, cancel, report, emit, breakpoints, commands):
    target = AndroidTarget(tools)
    env = tools.environment()
    sdk = env.get("ANDROID_HOME") or env.get("ANDROID_SDK_ROOT")
    adb = Path(sdk or "") / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    if not sdk or not adb.is_file():
        raise StudioError("औज़ार सेटिंग में एंड्रॉयड SDK और Platform Tools चुनें।")
    output = target.execute(project, snapshot, "debug", cancel, report)
    log = output.parent / "android-debug.log"

    def run(args, cleanup=False):
        if cancel.is_set() and not cleanup:
            raise StudioError("एंड्रॉयड डिबगिंग रोक दी गई।")
        try:
            result = subprocess.run([str(adb), *args], cwd=output, env=env, capture_output=True,
                                    encoding="utf-8", errors="replace", timeout=45 if not cleanup else 5,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as error:
            raise StudioError(f"ADB से समय पर उत्तर नहीं मिला — {args[0]}") from error
        with log.open("a", encoding="utf-8") as stream:
            stream.write(result.stdout + result.stderr)
        if result.returncode and not cleanup:
            raise StudioError(f"ADB आदेश असफल — {result.stderr.strip() or result.stdout.strip()}\n{log}")
        return result.stdout.strip()

    ready = [fields[0] for line in run(["devices"]).splitlines()
             if len(fields := line.split()) >= 2 and fields[1] == "device"]
    if not device and len(ready) == 1:
        device = ready[0]
    if device not in ready:
        raise StudioError("एक तैयार एंड्रॉयड उपकरण जोड़ें या औज़ार सेटिंग में उसकी पहचान चुनें।")
    serial = ["-s", device]
    abis = run([*serial, "shell", "getprop", "ro.product.cpu.abilist"]).split(",")
    abi = next((value for value in abis if value in {"x86_64", "arm64-v8a"}), None)
    if not abi:
        raise StudioError("डिबगिंग के लिए x86_64 या arm64-v8a उपकरण चाहिए।")
    symbols = next((path for path in output.rglob("libbhash_app.so")
                    if path.parent.name == abi and path.parent.parent.name == "libraries"), None)
    if symbols is None:
        raise StudioError("ऐप की मूल-मशीन डिबग जानकारी नहीं मिली।")
    architecture = "aarch64" if abi == "arm64-v8a" else abi
    studio = Path(os.environ.get("ProgramFiles", "/opt")) / "Android/Android Studio"
    bundled_server = studio / "plugins/android-ndk/resources/lldb/android" / abi / "lldb-server"
    gradle = (output / "app/build.gradle.kts").read_text(encoding="utf-8")
    ndk = re.search(r'ndkVersion\s*=\s*"([0-9.]+)"', gradle)
    server = next(iter(Path(sdk).glob(
        f"ndk/{ndk[1] if ndk else '*'}/toolchains/llvm/prebuilt/*/lib/clang/*/lib/linux/{architecture}/lldb-server"
    )), bundled_server)
    if not server.is_file():
        raise StudioError("एंड्रॉयड NDK में उपकरण के लिए lldb-server नहीं मिला।")
    config, _ = validate_snapshot(snapshot)
    package = config["ऐप_पहचान"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise StudioError("एंड्रॉयड ऐप की पहचान अमान्य है।")
    token = uuid.uuid4().hex[:12]
    temporary = f"/data/local/tmp/bhash-{token}"
    run([*serial, "install", "-r", "app/build/outputs/apk/debug/app-debug.apk"])
    home = run([*serial, "shell", "run-as", package, "pwd"])
    if not re.fullmatch(r"/data/(?:data|user/[0-9]+)/[A-Za-z0-9_.]+", home):
        raise StudioError("ऐप का डिबग फ़ोल्डर नहीं मिला।")
    local = f"{home}/bhash-{token}"
    socket = f"{home}/bhash-{token}.sock"
    app = [*serial, "shell", "run-as", package]
    forward = None
    bridge = None
    try:
        run([*serial, "shell", "am", "force-stop", package])
        run([*serial, "shell", "am", "start", "-W", "-n",
             f"{package}/org.bhashitva.androidstarter.MainActivity"])
        pid = run([*serial, "shell", "pidof", package])
        if not pid.isdecimal():
            raise StudioError("एंड्रॉयड ऐप की प्रक्रिया नहीं मिली।")
        run([*serial, "push", str(server), temporary])
        run([*app, "cp", temporary, local])
        run([*app, "chmod", "700", local])
        allocated = run([*serial, "forward", "tcp:0", f"localfilesystem:{socket}"])
        if not re.fullmatch(r"[0-9]{1,5}", allocated) or not 0 < int(allocated) <= 65535:
            raise StudioError("ADB ने डिबग पोर्ट नहीं दिया।")
        forward = allocated
        with log.open("ab") as stream:
            bridge = subprocess.Popen([str(adb), *app, local, "gdbserver", "--attach", pid,
                                       f"unix-accept://{socket}"], cwd=output, env=env,
                                      stdout=stream, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            deadline = time.monotonic() + 12
            while not cancel.is_set() and bridge.poll() is None and time.monotonic() < deadline:
                result = subprocess.run([str(adb), *app, "ls", "-ld", socket], cwd=output, env=env,
                                        capture_output=True, timeout=4,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode == 0 and result.stdout.startswith(b"s"):
                    break
                cancel.wait(.15)
            else:
                with log.open("rb") as diagnostic:
                    diagnostic.seek(max(0, log.stat().st_size - 2048))
                    detail = diagnostic.read().decode("utf-8", errors="replace").strip()
                raise StudioError(f"एंड्रॉयड डिबग सर्वर शुरू नहीं हुआ — {log}\n{detail}")
            debugger = WebDebugger(symbols, output / "src", adapter, [], None, breakpoints,
                                   cancel, emit, android_port=int(forward))
            debugger.commands = commands
            report("एंड्रॉयड डिबगर जुड़ रहा है। डिबग सत्र चलने पर ऐप में अपना कार्य चलाएँ।")
            try:
                debugger.run()
            except StudioError as error:
                with log.open("rb") as diagnostic:
                    diagnostic.seek(max(0, log.stat().st_size - 2048))
                    detail = diagnostic.read().decode("utf-8", errors="replace").strip()
                raise StudioError(f"{error}\n{detail}") from error
    finally:
        if bridge is not None and bridge.poll() is None:
            bridge.terminate()
            bridge.wait(timeout=5)
        cleanup = [[*app, "rm", "-f", local, socket], [*serial, "shell", "rm", "-f", temporary]]
        if forward and forward.isdecimal():
            cleanup.insert(0, [*serial, "forward", "--remove", f"tcp:{forward}"])
        for args in cleanup:
            try:
                run(args, cleanup=True)
            except (OSError, StudioError):
                pass
