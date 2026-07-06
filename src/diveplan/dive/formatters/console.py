"""Plain-text report formatter for terminals and logs."""

from datetime import timedelta

from diveplan.dive.dive_report import DiveReport, ReportRow
from diveplan.dive.formatters import BaseFormatter

__all__ = ["ConsoleFormatter"]


def _minutes(td: timedelta) -> str:
    return f"{td.total_seconds() / 60:6.1f} min"


def _describe(row: ReportRow) -> str:
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

    def format(self, report: DiveReport) -> str:
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
        lines.append("  runtime     action                  duration   gas    kind")
        lines.extend(_describe(row) for row in report.rows)
        lines.append("")

        for gas, litres in report.consumption_l:
            lines.append(f"  {gas.name:<6} consumed : {litres:7.0f} L")
        lines.append(
            f"  rock bottom @ {report.max_depth.depth_m:.0f} m : "
            f"{report.rock_bottom_l:7.0f} L"
        )
        lines.append(f"  CNS {report.cns:.0f} %   OTU {report.otus:.0f}")
        return "\n".join(lines)
