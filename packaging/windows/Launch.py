"""Start Yantra using the paths selected by Windows setup."""

import json
import os
from pathlib import Path
import site
import sys


def main():
    directory = Path(__file__).resolve().parent
    site.addsitedir(str(directory))
    config = json.loads((directory / "installed-tools.json").read_text(encoding="utf-8"))
    if config["clangBin"]:
        os.environ["PATH"] = config["clangBin"] + os.pathsep + os.environ.get("PATH", "")

    from bhash_studio.android import Toolchain
    from bhash_studio.app import Studio
    from bhash_studio.errors import StudioError
    from bhash_studio.project import Project
    from bhash_studio.settings import load_settings, save_settings, settings_path
    import tkinter as tk

    defaults = Toolchain(**{key: config[key] for key in ("compiler", "java", "sdk", "debugger")})
    path = settings_path()
    checking = sys.argv[1:] == ["--check"]
    if path.is_file() and not checking:
        # Keep working user overrides and fill paths that were never configured.
        try:
            saved, device = load_settings(path, defaults)
            tools = Toolchain(**{
                name: value if value and Path(value).exists() else getattr(defaults, name)
                for name, value in vars(saved).items()
            })
            if tools != saved:
                save_settings(path, tools, device)
        except (OSError, ValueError, StudioError):
            pass
    if checking:
        defaults.validate()
        from send2trash.win.modern import send2trash
        assert callable(send2trash)
        root = tk.Tk()
        try:
            studio = Studio(root, tools=defaults)
            root.update_idletasks()
            assert studio.root is root
        finally:
            root.destroy()
        print("Yantra, Tk, Bhash compiler, Java and Windows trash imports are ready.")
        return
    root = tk.Tk()
    studio = Studio(root, tools=defaults)
    if len(sys.argv) == 3 and sys.argv[1] == "--project":
        studio.guard(lambda: studio.load(Project.open(sys.argv[2])))
    else:
        studio.restore_session()
    root.mainloop()


if __name__ == "__main__":
    main()
