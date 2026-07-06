"""Dive report: everything about a computed dive, ready for presentation.

:class:`DiveReport` is pure data assembled from a :class:`~diveplan.dive.dive.Dive` — the
schedule rows plus derived figures (gas consumption, CNS/OTU, rock bottom,
TTS variations). Formatters (`diveplan.dive.formatters`) turn a report into
console text, JSON, or a Subsurface dive log; they never touch models or
profiles directly, so a new output format is a single class.
"""

from datetime import timedelta
from typing import NamedTuple, Optional

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile
from diveplan.dive.dive import Dive, TtsVariations
from diveplan.dive.oxygen import cns_percent, otu
from diveplan.models.base import DecoState
from diveplan.planning.gas_plan import GasPlan, gas_consumption, rock_bottom

__all__ = ["DiveReport", "ReportRow"]


class ReportRow(NamedTuple):
    """One schedule line: a segment with its cumulative runtime at the end."""

    runtime: timedelta  # at the END of the segment
    start_depth_m: float
    end_depth_m: float
    duration: timedelta
    gas: Gas
    kind: str  # SegmentKind member name


class DiveReport:
    """Immutable summary of a computed dive.

    Build via :meth:`from_dive`. Holds the schedule and the derived
    numbers; formatting belongs to `diveplan.dive.formatters`.
    """

    __slots__ = (
        "profile",
        "model_name",
        "rows",
        "runtime",
        "max_depth",
        "consumption_l",
        "cns",
        "otus",
        "rock_bottom_l",
        "tts_variations",
    )

    profile: DiveProfile
    model_name: str
    rows: tuple[ReportRow, ...]
    runtime: timedelta
    max_depth: Pressure
    consumption_l: tuple[tuple[Gas, float], ...]
    cns: float
    otus: float
    rock_bottom_l: float
    tts_variations: Optional[TtsVariations]

    def __init__(
        self,
        *,
        profile: DiveProfile,
        model_name: str,
        rows: tuple[ReportRow, ...],
        runtime: timedelta,
        max_depth: Pressure,
        consumption_l: tuple[tuple[Gas, float], ...],
        cns: float,
        otus: float,
        rock_bottom_l: float,
        tts_variations: Optional[TtsVariations],
    ):
        self.profile = profile
        self.model_name = model_name
        self.rows = rows
        self.runtime = runtime
        self.max_depth = max_depth
        self.consumption_l = consumption_l
        self.cns = cns
        self.otus = otus
        self.rock_bottom_l = rock_bottom_l
        self.tts_variations = tts_variations

    @classmethod
    def from_dive(
        cls,
        dive: Dive[DecoState],
        *,
        gas_plan: Optional[GasPlan] = None,
        tts_variations: Optional[TtsVariations] = None,
    ) -> "DiveReport":
        """Assemble a report from a computed dive.

        Args:
            dive: The computed dive (normally the *full* dive, bottom plus
                planned ascent — see :meth:`Dive.with_ascent`).
            gas_plan: Unused for consumption (which follows the profile's
                own gases) — reserved for future reserve summaries.
            tts_variations: The "+1 m / +1 min" figures. They are meaningful
                for a *bottom-phase* dive, so compute them on the bottom
                dive (``bottom.tts_variations()``) and pass them here; a
                report over a full dive cannot derive them itself.
        """
        profile = dive.profile
        segments = profile.segments

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

        max_pressure = max(
            (p for s in segments for p in (s.start_pressure, s.end_pressure)),
            default=Pressure.surface(),
        )

        return cls(
            profile=profile,
            model_name=dive.model_name,
            rows=tuple(rows),
            runtime=profile.runtime,
            max_depth=max_pressure,
            consumption_l=tuple(gas_consumption(segments).items()),
            cns=cns_percent(segments),
            otus=otu(segments),
            rock_bottom_l=rock_bottom(max_pressure),
            tts_variations=tts_variations,
        )

    def __repr__(self) -> str:
        return (
            f"DiveReport({self.model_name}, {len(self.rows)} rows, "
            f"runtime={self.runtime}, max depth {self.max_depth.depth_m:.1f} m)"
        )
