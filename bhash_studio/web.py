"""Build and run Bhash web applications without Android tooling."""

import json
import os
from pathlib import Path
import re
import shutil
import uuid

from .android import run_tool
from .config import loads, validate_config
from .errors import StudioError
from .project import BUILD_DIRECTORY, CONFIG, SCRATCH_DIRECTORY, SOURCE, WEB_ASSETS, WEB_PAGE, WEB_PROFILES, atomic_write


DEFAULT_PROFILES = {
    "dev": {"port": 8080},
    "staging": {"port": 8081},
    "prod": {"port": 8080},
}
JAVA_ENCODING = ("-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8")


def validate_profiles(profiles):
    if not isinstance(profiles, dict) or not DEFAULT_PROFILES.keys() <= profiles.keys():
        raise StudioError("परिवेश में dev, staging और prod रखें।")
    for name, profile in profiles.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", name):
            raise StudioError(f"परिवेश का नाम अमान्य है — {name}")
        if (not isinstance(profile, dict) or profile.keys() != {"port"}
                or type(profile["port"]) is not int or not 1 <= profile["port"] <= 65535):
            raise StudioError(f"परिवेश ‘{name}’ में केवल port रखें, जिसका मान 1 से 65535 हो।")
    return profiles


def validate_web(snapshot):
    config = validate_config(loads(snapshot[CONFIG]))
    if config["लक्ष्य"] != "वेब":
        raise StudioError("वेब निर्माण के लिए वेब परियोजना खोलें।")
    if not snapshot[WEB_PAGE].strip() or not snapshot[SOURCE].strip():
        raise StudioError("वेब परियोजना के मुख्य भाष स्रोत और index.html में कोड लिखें।")
    return config, validate_profiles(loads(snapshot[WEB_PROFILES]))


def server_arguments(host, port, database):
    return [f"--host={host}", f"--port={port}", f"--db={database}", "--page=index.html"]


def copy_assets(source, destination):
    destination.mkdir()
    if not source.is_dir():
        return
    for path in source.iterdir():
        if path.name.startswith(".") or path.resolve() != path or path.is_symlink():
            continue
        target = destination / path.name
        if path.is_dir():
            copy_assets(path, target)
        elif path.is_file() and path.suffix != ".bhash":
            shutil.copyfile(path, target)


class WebTarget:
    def __init__(self, tools, runner=run_tool):
        self.tools = tools
        self.runner = runner

    def build(self, project, snapshot, profile, cancel, report, *, debug=False):
        _, profiles = validate_web(snapshot)
        if profile not in profiles:
            raise StudioError(f"परिवेश नहीं मिला — {profile}")
        self.tools.validate()
        job = project.file(Path(BUILD_DIRECTORY) / uuid.uuid4().hex[:16])
        job.mkdir(parents=True)
        log = job / "tool-output.log"
        log.touch()
        bundle = job / profile
        source_root = job / "src"
        bundle.mkdir()
        for filename, text in snapshot.items():
            if filename.endswith(".bhash"):
                path = source_root / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(path, text)
        atomic_write(job / "bhash.project", "name=yantra-web\nsources=src\n")
        shutil.copyfile(self.tools.compiler, job / "compiler.jar")
        report(f"वेब निर्माण — {profile}\nकंपाइलर लॉग — {log}")
        executable = ("server.exe" if os.name == "nt" else "server") if debug else "app.jar"
        target = ["--target", "native", "--debug"] if debug else ["--target", "jvm"]
        try:
            self.runner([self.tools.java, *JAVA_ENCODING, "-jar", "compiler.jar", "compile",
                         "bhash.project", *target, "-o", f"{profile}/{executable}"],
                        job, self.tools.environment(), log, cancel)
        except StudioError as error:
            if debug and not cancel.is_set():
                raise StudioError(f"मूल-मशीन डिबग निर्माण असफल हुआ। कंपाइलर लॉग — {log}") from error
            raise
        if not (bundle / executable).is_file():
            raise StudioError(f"कंपाइलर ने {executable} नहीं बनाया। लॉग देखें — {log}")
        atomic_write(bundle / WEB_PAGE, snapshot[WEB_PAGE])
        copy_assets(project.file(WEB_ASSETS), bundle / WEB_ASSETS)
        if debug:
            return bundle / executable
        port = profiles[profile]["port"]
        command = ["java", *JAVA_ENCODING, "-jar", "app.jar",
                   *server_arguments("0.0.0.0", port, "/data/tasks.db")]
        atomic_write(bundle / "Dockerfile",
                     "FROM eclipse-temurin:21-jre\nWORKDIR /app\n"
                     "RUN mkdir /data && chown 10001:10001 /data\n"
                     "COPY app.jar index.html ./\nCOPY assets/ assets/\nUSER 10001:10001\n"
                     f"ENV BHASH_ENV={profile}\nEXPOSE {port}\nVOLUME [\"/data\"]\n"
                     f"ENTRYPOINT {json.dumps(command)}\n")
        return bundle

    def serve(self, project, snapshot, cancel, report, ready):
        bundle = self.build(project, snapshot, "dev", cancel, report)
        _, profiles = validate_web(snapshot)
        port = profiles["dev"]["port"]
        arguments = self.local_arguments(project, port)
        log = bundle.parent / "server.log"
        report(f"स्थानीय वेब सर्वर शुरू हो रहा है। सर्वर लॉग — {log}")
        env = self.tools.environment()
        env["BHASH_ENV"] = "dev"
        announced = False

        def check_ready():
            nonlocal announced
            if not announced:
                with log.open("rb") as stream:
                    if f"READY {port}".encode() not in stream.read(65536).splitlines():
                        return
                announced = True
                ready(port)
                report(f"स्थानीय वेब सर्वर तैयार है — http://127.0.0.1:{port}/")

        self.runner([self.tools.java, *JAVA_ENCODING, "-jar", "app.jar",
                     *arguments],
                    bundle, env, log, cancel, timeout=float("inf"), on_wait=check_ready)

    @staticmethod
    def local_arguments(project, port, environment="dev"):
        data = Path(SCRATCH_DIRECTORY) / "web-data" / environment / "tasks.db"
        project.file(data).parent.mkdir(parents=True, exist_ok=True)
        database = Path("..", "..", "..") / data
        return server_arguments("127.0.0.1", port, database.as_posix())
