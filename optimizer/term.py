"""Tiny ANSI console. Color only when it makes sense; plain text otherwise.

    console = Console()                  # color if stdout is a TTY and NO_COLOR is unset
    console = Console(color=False)       # --no-color
    console = Console(stream=sys.stderr) # --json keeps stdout for the JSON payload

The verifier's report module renders plain text; this is the only layer that
decorates it.
"""

from __future__ import annotations

import os
import sys
from typing import IO

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"


class Console:
    def __init__(self, stream: IO[str] | None = None, color: bool | None = None):
        self.stream = stream if stream is not None else sys.stdout
        self.color = self._resolve(self.stream, color)

    @staticmethod
    def _resolve(stream: IO[str], color: bool | None) -> bool:
        if color is not None:
            return color
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        isatty = getattr(stream, "isatty", None)
        return bool(isatty and isatty())

    def paint(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return "".join(codes) + text + RESET

    def print(self, text: str = "", *codes: str) -> None:
        self.stream.write(self.paint(text, *codes) + "\n")
        self.stream.flush()

    def heading(self, text: str) -> None:
        self.print(text, BOLD)

    def ok(self, text: str) -> None:
        self.print(text, GREEN)

    def warn(self, text: str) -> None:
        self.print(text, YELLOW)

    def error(self, text: str) -> None:
        self.print(text, RED)

    def diff(self, text: str) -> None:
        """Unified diff with the conventional +/-/@@ coloring."""
        for line in text.rstrip("\n").split("\n"):
            if line.startswith(("+++", "---")):
                self.print(line, BOLD)
            elif line.startswith("+"):
                self.print(line, GREEN)
            elif line.startswith("-"):
                self.print(line, RED)
            elif line.startswith("@@"):
                self.print(line, CYAN)
            else:
                self.print(line)

    def candidate(self, block: str) -> None:
        """format_candidate() output with VALID green and REJECTED red."""
        for line in block.split("\n"):
            if line.startswith("Result: VALID"):
                self.print(line, GREEN)
            elif line.startswith("Result: REJECTED"):
                self.print(line, RED)
            else:
                self.print(line)
