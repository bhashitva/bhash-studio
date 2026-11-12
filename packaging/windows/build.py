"""Build the Windows x64 setup ZIP from checksum-pinned upstream payloads."""

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HASHES = {
    "python.exe": "96159fcb523ae404b707186a75b4104ee23851e476a5e838e14584cf1e03f981",
    "java.zip": "08cae782814f027f8b159d6b68823f0f87422eb475c1a0ea1abc7a4357aaf11f",
    "java-source.tar.gz": "a286b69953cdb56ab2dc74287e6ebaca8fad7d397a4b5f975b73d23eedeec252",
    "compiler.jar": "9e353b85365c50367ec008486d8ef83eeeb550a1dd9dbcc9d889f79dab904162",
    "send2trash-2.1.0-py3-none-any.whl": "0da2f112e6d6bb22de6aa6daa7e144831a4febf2a87261451c4ad849fe9a873c",
    "pywin32-312-cp311-cp311-win_amd64.whl": "d11417d84412f859b722fad0841b3614459ed0047f7542d8362e77884f6b6e8a",
    "pywin32-312-cp312-cp312-win_amd64.whl": "b457f6d628a47e8a7346ce22acb7e1a46a4a78b52e1d17e1af56871bd19a93bc",
    "pywin32-312-cp313-cp313-win_amd64.whl": "c53e878d15a1c44788082bfe712a905433473aa38f86375b7cf8b45e3acbaaf9",
    "pywin32-312-cp314-cp314-win_amd64.whl": "a4dd3a848290ef724347b19f301045831d8e802fa4464f491b98b1e0a081432e",
}
LLVM_SHA256 = "810703594a7e3eea03385b5329c7ea3bd65f5e496b44cf1b68c17ff436d265e7"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for name, expected in HASHES.items():
        with (args.inputs / name).open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            parser.error(f"Checksum mismatch: {name}")
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for source in sorted((REPO / "bhash_studio").glob("*")):
            if source.is_file():
                archive.write(source, f"bhash_studio/{source.name}")
        archive.write(REPO / "LICENSE", "LICENSE-Yantra.txt")
        archive.write(HERE / "Launch.py", "Launch.py")
    application = buffer.getvalue()
    app_hash = hashlib.sha256(application).hexdigest()
    manifest = {**HASHES, "llvm": LLVM_SHA256, "app.zip": app_hash, "app": app_hash[:16]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w", ZIP_STORED) as archive:
        for name in ("Install.cmd", "Install.ps1", "README.txt"):
            archive.write(HERE / name, name)
        for name in HASHES:
            archive.write(args.inputs / name, f"payload/{name}")
        archive.writestr("payload/app.zip", application)
        archive.writestr("payload.json", json.dumps(manifest, indent=2))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
