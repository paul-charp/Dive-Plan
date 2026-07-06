"""Subsurface dive-log XML formatter (experimental).

Emits a minimal Subsurface-compatible dive log: one dive with cylinders
(one per gas), a planned-dive computer with depth samples and gas-change
events. Written against Subsurface's XML dive-log format as of v6; treat
as experimental until round-tripped through your Subsurface version —
the importer is lenient, but the format is theirs, not a public standard.
"""

from datetime import datetime, timedelta
from xml.etree import ElementTree

from diveplan.core.gas import Gas
from diveplan.dive.dive_report import DiveReport
from diveplan.dive.formatters import BaseFormatter

__all__ = ["SubsurfaceXmlFormatter"]


def _mmss(td: timedelta) -> str:
    total = round(td.total_seconds())
    return f"{total // 60}:{total % 60:02d} min"


def _depth(metres: float) -> str:
    return f"{max(0.0, metres):.1f} m"


def _gas_attrs(gas: Gas) -> dict[str, str]:
    attrs = {"o2": f"{gas.fo2 * 100:.1f}%"}
    if gas.fhe > 0:
        attrs["he"] = f"{gas.fhe * 100:.1f}%"
    return attrs


class SubsurfaceXmlFormatter(BaseFormatter):
    """Render the report as a Subsurface dive-log XML document."""

    NAME = "subsurface"

    SAMPLE_STEP = timedelta(seconds=10)

    def __init__(self, *, planned_at: datetime | None = None):
        self.planned_at = planned_at if planned_at is not None else datetime.now()

    def format(self, report: DiveReport) -> str:
        """Render the report as a Subsurface dive-log XML string."""
        profile = report.profile
        segments = profile.segments

        divelog = ElementTree.Element(
            "divelog", {"program": "diveplan", "version": "3"}
        )
        dives = ElementTree.SubElement(divelog, "dives")
        dive = ElementTree.SubElement(
            dives,
            "dive",
            {
                "number": "1",
                "date": self.planned_at.strftime("%Y-%m-%d"),
                "time": self.planned_at.strftime("%H:%M:%S"),
                "duration": _mmss(report.runtime),
            },
        )

        # One cylinder per distinct gas, in order of first use.
        gases: list[Gas] = []
        for segment in segments:
            if segment.gas not in gases:
                gases.append(segment.gas)
        for gas in gases:
            ElementTree.SubElement(
                dive, "cylinder", {**_gas_attrs(gas), "description": gas.name}
            )

        computer = ElementTree.SubElement(
            dive, "divecomputer", {"model": "diveplan (planned dive)"}
        )

        # Time-weighted mean depth (exact for linear segments).
        total_s = report.runtime.total_seconds()
        mean_m = 0.0
        if total_s > 0:
            weighted = sum(
                s.average_pressure.depth_m * s.duration.total_seconds()
                for s in segments
            )
            mean_m = weighted / total_s
        ElementTree.SubElement(
            computer,
            "depth",
            {"max": _depth(report.max_depth.depth_m), "mean": _depth(mean_m)},
        )

        # Gas-change events at the segment boundaries where the gas changes.
        elapsed = timedelta(0)
        current_gas = segments[0].gas if segments else None
        for segment in segments:
            if segment.gas != current_gas:
                ElementTree.SubElement(
                    computer,
                    "event",
                    {
                        "time": _mmss(elapsed),
                        "name": "gaschange",
                        "cylinder": str(gases.index(segment.gas)),
                        **_gas_attrs(segment.gas),
                    },
                )
                current_gas = segment.gas
            elapsed += segment.duration

        # Depth samples on a fixed grid (plus the exact start and end).
        ElementTree.SubElement(
            computer, "sample", {"time": _mmss(timedelta(0)), "depth": _depth(0.0)}
        )
        for sample in profile.iter_samples(self.SAMPLE_STEP):
            ElementTree.SubElement(
                computer,
                "sample",
                {
                    "time": _mmss(sample.time),
                    "depth": _depth(sample.pressure.depth_m),
                },
            )

        ElementTree.indent(divelog)
        return ElementTree.tostring(divelog, encoding="unicode", xml_declaration=True)
