class StudioError(Exception):
    """An actionable Hindi message safe to display to the developer."""


class FormatError(StudioError):
    def __init__(self, message, source, offset):
        self.line = source.count("\n", 0, offset) + 1
        self.column = offset - source.rfind("\n", 0, offset)
        super().__init__(f"पंक्ति {self.line}, स्थान {self.column} — {message}")
