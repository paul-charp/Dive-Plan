"""Plain-text report formatter for terminals and logs."""

from collections.abc import Iterable
from datetime import timedelta

from diveplan.core.dive_segment import DiveSegment
from diveplan.dive.dive_report import DiveReport, ReportRow
from diveplan.dive.formatters import BaseFormatter

__all__ = ["ConsoleFormatter"]

_SCHEDULE_HEADER = "  runtime     action                  duration   gas    kind"


def _minutes(td: timedelta) -> str:
    return f"{td.total_seconds() / 60:6.1f} min"


def _row_line(row: ReportRow) -> str:
    if row.kind == "GAS_SWITCH":
        action = f"switch to {row.gas}"
    elif row.start_depth_m == row.end_depth_m:
        action = f"hold {row.start_depth_m:4.0f} m"
    else:
        action = f"{row.start_depth_m:4.0f} m -> {row.end_depth_m:3.0f} m"
    runtime_start = row.runtime - row.duration
    return (
        f"  {_minutes(runtime_start)}  {action:<22}"
        f"{_minutes(row.duration)}   {row.gas.name:<6} {row.kind}"
    )


class ConsoleFormatter(BaseFormatter):
    """Human-readable dive plan table with a summary block."""

    NAME = "console"

    @staticmethod
    def format_schedule(segments: Iterable[DiveSegment]) -> str:
        """Render any segment sequence (a profile's or an ascent plan) as a
        runtime table — reusable outside full reports."""
        rows: list[ReportRow] = []
        elapsed = timedelta(0)
        for segment in segments:
            elapsed += segment.duration
            rows.append(
                ReportRow(
                    runtime=elapsed,
                    start_depth_m=segment.start_pressure.depth_m,
                    end_depth_m=segment.end_pressure.depth_m,
                    duration=segment.duration,
                    gas=segment.gas,
                    kind=segment.kind.name,
                )
            )
        return "\n".join([_SCHEDULE_HEADER, *map(_row_line, rows)])

    def format(self, report: DiveReport) -> str:
        """Render the full report: header, schedule table, totals block."""
        lines = [
            f"Dive plan — {report.model_name}",
            f"runtime {_minutes(report.runtime).strip()}, "
            f"max depth {report.max_depth.depth_m:.1f} m",
        ]
        if report.tts_variations is not None:
            per_m = report.tts_variations.per_meter.total_seconds()
            per_min = report.tts_variations.per_minute.total_seconds()
            lines.append(
                f"TTS variation: +{per_m / 60:.1f} min/m, +{per_min / 60:.1f} min/min"
            )
        lines.append("")
        lines.append(_SCHEDULE_HEADER)
        lines.extend(_row_line(row) for row in report.rows)
        lines.append("")

        for gas, litres in report.consumption_l:
            lines.append(f"  {gas.name:<6} consumed : {litres:7.0f} L")
        lines.append(
            f"  rock bottom @ {report.max_depth.depth_m:.0f} m : "
            f"{report.rock_bottom_l:7.0f} L"
        )
        lines.append(f"  CNS {report.cns:.0f} %   OTU {report.otus:.0f}")
        return "\n".join(lines)
