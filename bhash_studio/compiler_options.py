"""Project language profile, retained when generating build projects."""

import re
from .errors import StudioError


def profile(manifest):
    values = re.findall(r"^\s*nullSafety\s*=\s*(\S+)\s*$", manifest, re.MULTILINE)
    if len(values) > 1 or values and values[0] not in {"legacy", "strict"}:
        raise StudioError("bhash.project में nullSafety केवल legacy या strict होना चाहिए।")
    return values[0] if values else "legacy"


def project_profile(project, overlays=None):
    if overlays and "bhash.project" in overlays:
        return profile(overlays["bhash.project"])
    file = project.file("bhash.project")
    return profile(project.read("bhash.project")) if file.is_file() else "legacy"


def with_profile(manifest, selected):
    line = "nullSafety=" + selected + "\n"
    if re.search(r"^\s*nullSafety\s*=", manifest, re.MULTILINE):
        return re.sub(r"^\s*nullSafety\s*=.*$", line.rstrip(), manifest, flags=re.MULTILINE)
    return manifest.rstrip() + "\n" + line
