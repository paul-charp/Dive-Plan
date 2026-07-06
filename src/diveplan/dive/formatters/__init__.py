"""Report formatters: turn a DiveReport into an output document.

A formatter is a class with a ``NAME`` and a ``format(report) -> str``
method — stateless, presentation only. Third-party formatters can register
under the ``diveplan.formatters`` entry-point group.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from diveplan.dive.dive_report import DiveReport

__all__ = ["BaseFormatter"]


class BaseFormatter(ABC):
    """Base class for all report formatters."""

    NAME: ClassVar[str]

    @abstractmethod
    def format(self, report: DiveReport) -> str:
        """Render the report as a string in this formatter's output format."""


from diveplan.dive.formatters.console import ConsoleFormatter  # noqa: E402
from diveplan.dive.formatters.json import JsonFormatter  # noqa: E402
from diveplan.dive.formatters.subsurface import SubsurfaceXmlFormatter  # noqa: E402

__all__ += ["ConsoleFormatter", "JsonFormatter", "SubsurfaceXmlFormatter"]
