"""Report formatters: turn a DiveReport into an output document.

A formatter is a class with a ``NAME`` and a ``format(report) -> str``
method — stateless, presentation only. Third-party formatters can register
under the ``diveplan.formatters`` entry-point group.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from diveplan.dive.dive_report import DiveReport

__all__ = ["BaseFormatter"]


class BaseFormatter(ABC):
    """Base class for all report formatters."""

    NAME: ClassVar[str]

    def __init__(self, **options: Any) -> None:
        """Formatters take keyword options only, defined per formatter.

        This permissive base signature is what lets registry-typed
        construction (``registry.formatter(name)(**options)``) type-check;
        options are still validated at runtime — here for formatters that
        define none, by the concrete ``__init__`` otherwise.
        """
        if options:
            raise TypeError(
                f"{type(self).__name__} accepts no options, got {sorted(options)}."
            )

    @abstractmethod
    def format(self, report: DiveReport) -> str:
        """Render the report as a string in this formatter's output format."""

    def write(self, report: DiveReport, path: str | Path) -> None:
        """Render the report and write it to `path` (UTF-8, LF endings)."""
        Path(path).write_text(self.format(report), encoding="utf-8", newline="\n")

    def print(self, report: DiveReport) -> None:
        """Render the report and print it to stdout.

        Formatters with terminal-aware rendering (rich) override this.
        """
        print(self.format(report))


from diveplan.dive.formatters.console import ConsoleFormatter  # noqa: E402
from diveplan.dive.formatters.json import JsonFormatter  # noqa: E402
from diveplan.dive.formatters.rich_console import RichConsoleFormatter  # noqa: E402
from diveplan.dive.formatters.runtime import RuntimeFormatter  # noqa: E402
from diveplan.dive.formatters.subsurface import SubsurfaceXmlFormatter  # noqa: E402

__all__ += [
    "ConsoleFormatter",
    "JsonFormatter",
    "RichConsoleFormatter",
    "RuntimeFormatter",
    "SubsurfaceXmlFormatter",
]
