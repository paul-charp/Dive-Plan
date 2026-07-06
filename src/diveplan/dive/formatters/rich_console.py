"""Rich terminal formatter: the report as styled tables.

Same content as :class:`~diveplan.dive.formatters.console.ConsoleFormatter`,
rendered with `rich <https://rich.readthedocs.io>`_ — colored segment kinds,
box-drawn tables, a summary panel. ``format()`` honors the formatter
contract by exporting the rendering to a string (ANSI-styled when
``styled=True``); :meth:`print` renders straight to a live terminal, which
is what you want interactively.
"""

import io
from datetime import timedelta

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from diveplan.dive.dive_report import DiveReport, ReportRow
from diveplan.dive.formatters import BaseFormatter

__all__ = ["RichConsoleFormatter"]

_KIND_STYLES = {
    "DESCENT": "cyan",
    "BOTTOM": "bold white",
    "DECO_ASCENT": "green",
    "FORCED_ASCENT": "green",
    "STOP": "yellow",
    "GAS_SWITCH": "bold magenta",
}


def _minutes(td: timedelta) -> str:
    return f"{td.total_seconds() / 60:.1f}"


def _action(row: ReportRow) -> str:
    if row.kind == "GAS_SWITCH":
        return f"switch to {row.gas}"
    if row.start_depth_m == row.end_depth_m:
        return f"hold {row.start_depth_m:.0f} m"
    return f"{row.start_depth_m:.0f} m -> {row.end_depth_m:.0f} m"


class RichConsoleFormatter(BaseFormatter):
    """Styled terminal rendering of a dive report.

    Args:
        styled: Keep ANSI color codes in the string returned by ``format()``.
            Set False for plain (but still box-drawn) text, e.g. for logs.
        width: Render width in characters.
    """

    NAME = "rich"

    def __init__(self, *, styled: bool = True, width: int = 72):
        self.styled = styled
        self.width = width

    def print(self, report: DiveReport, console: Console | None = None) -> None:
        """Render the report directly to a terminal (auto-detected styling)."""
        (console or Console()).print(self._renderable(report))

    def format(self, report: DiveReport) -> str:
        """Render the report to a string (ANSI-styled when ``styled=True``)."""
        console = Console(
            record=True,
            width=self.width,
            force_terminal=self.styled,
            file=io.StringIO(),
        )
        console.print(self._renderable(report))
        return console.export_text(styles=self.styled)

    def _renderable(self, report: DiveReport) -> RenderableType:
        schedule = Table(
            title=f"Dive plan — {report.model_name}",
            title_style="bold",
            header_style="bold dim",
            row_styles=None,
        )
        schedule.add_column("runtime", justify="right")
        schedule.add_column("action")
        schedule.add_column("duration", justify="right")
        schedule.add_column("gas")
        schedule.add_column("kind")

        for row in report.rows:
            style = _KIND_STYLES.get(row.kind, "")
            schedule.add_row(
                _minutes(row.runtime - row.duration),
                _action(row),
                _minutes(row.duration),
                row.gas.name,
                Text(row.kind, style=style),
            )

        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="dim")
        summary.add_column()
        summary.add_row(
            "runtime / max depth",
            f"{_minutes(report.runtime)} min / {report.max_depth.depth_m:.1f} m",
        )
        for gas, litres in report.consumption_l:
            summary.add_row(f"{gas.name} consumed", f"{litres:.0f} L")
        summary.add_row(
            f"rock bottom @ {report.max_depth.depth_m:.0f} m",
            f"{report.rock_bottom_l:.0f} L",
        )
        summary.add_row("exposure", f"CNS {report.cns:.0f} %  ·  OTU {report.otus:.0f}")
        if report.tts_variations is not None:
            per_m = report.tts_variations.per_meter.total_seconds() / 60
            per_min = report.tts_variations.per_minute.total_seconds() / 60
            summary.add_row(
                "TTS variation", f"+{per_m:.1f} min/m  ·  +{per_min:.1f} min/min"
            )

        return Group(schedule, Panel(summary, title="summary", title_align="left"))
