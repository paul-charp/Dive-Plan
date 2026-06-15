import math
from datetime import timedelta
from enum import Enum, auto
from typing import Iterator

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = ["SegmentKind", "DiveSegment"]

# ------------------------------------------------------------------
# Segment kinds
# ------------------------------------------------------------------


class SegmentKind:
    """Kind of dive segment, used for categorization and special handling in algorithms.
    Descent, ascent, and constant depth segments are categorized separately, with sub-kinds for different types of ascents and constant depth segments.
    Use `SegmentKind.DESCENT`, `SegmentKind.ASCENT`, and `SegmentKind.CONSTANT` for convenience when creating segments with default kinds.
    `SegmentKind.Members` is the union of all possible segment kinds for type annotations.
    `SegmentKind.Constant.STOP in SegmentKind.Constant` returns `True`, allowing for easy checks of whether a segment belongs to a certain parent kind (descent, ascent, or constant) regardless of sub-kind.
    """

    class Descent(Enum):
        DESCENT = auto()

    class Ascent(Enum):
        FORCED_ASCENT = auto()
        DECO_ASCENT = auto()

    class Constant(Enum):
        BOTTOM = auto()
        STOP = auto()
        GAS_SWITCH = auto()

    # Convenience members / default values for each parent kind
    DESCENT = Descent.DESCENT
    ASCENT = Ascent.FORCED_ASCENT
    CONSTANT = Constant.BOTTOM

    # Union of all possible segment kinds for type annotations
    Members = Descent | Ascent | Constant


class DiveSegment:
    """A segment of a dive profile with a start and end pressure, duration, and gas.
    Immutable. __slots__ for memory efficiency in batch simulation.

    """

    __slots__ = "start_pressure", "end_pressure", "duration", "gas", "kind"

    # Just for type checker — actual storage is in __slots__ for immutability and memory efficiency.
    start_pressure: Pressure
    end_pressure: Pressure
    duration: timedelta
    gas: Gas
    kind: SegmentKind.Members

    def __init__(
        self,
        start_pressure: Pressure,
        end_pressure: Pressure,
        duration: timedelta | int | float,
        gas: Gas,
        *,
        ascent_kind: SegmentKind.Ascent = SegmentKind.ASCENT,
        constant_kind: SegmentKind.Constant = SegmentKind.CONSTANT,
    ):
        """
        Args:
            start_pressure: Starting absolute pressure of the segment.
            end_pressure: Ending absolute pressure of the segment.
            duration: Duration of the segment (minutes as int/float, or a timedelta).
            gas: Gas mixture for the segment.
            ascent_kind: If the segment is an ascent, the kind of ascent. Defaults to SegmentKind.ASCENT.
            constant_kind: If the segment is at constant depth, the kind of constant depth. Defaults to SegmentKind.CONSTANT.

        Raises:
            ValueError: If the duration is negative, or zero for anything other
                than a gas switch. A zero-duration *traverse* is degenerate (no
                time elapses, rate undefined), so it is rejected. A gas switch is
                a boundary event at constant depth — it is materialized as a
                segment for serialization/display and may legitimately have zero
                duration (an instant switch, gas_switch_minutes = 0).
        """

        self.start_pressure = start_pressure
        self.end_pressure = end_pressure

        self.duration = (
            duration if isinstance(duration, timedelta) else timedelta(minutes=duration)
        )

        self.gas = gas
        self.kind = self._determine_kind(ascent_kind, constant_kind)

        if self.duration < timedelta(0):
            raise ValueError(
                f"DiveSegment duration cannot be negative, got {self.duration}."
            )
        if (
            self.duration == timedelta(0)
            and self.kind is not SegmentKind.Constant.GAS_SWITCH
        ):
            raise ValueError(
                f"DiveSegment duration must be strictly positive, got {self.duration}. "
                "Only a gas switch (constant depth) may have zero duration."
            )

    def _determine_kind(
        self,
        ascent_kind: SegmentKind.Ascent,
        constant_kind: SegmentKind.Constant,
    ) -> SegmentKind.Members:
        if self.start_pressure < self.end_pressure:
            return SegmentKind.DESCENT
        elif self.start_pressure > self.end_pressure:
            return ascent_kind
        else:
            return constant_kind

    # -------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------

    @property
    def average_pressure(self) -> Pressure:
        """Mean of the start and end pressures."""
        return (self.start_pressure + self.end_pressure) / 2

    @property
    def absolute_pressure_change(self) -> Pressure:
        """Magnitude of the pressure change from start to end (always non-negative)."""
        return Pressure.from_mbar(abs(self.end_pressure - self.start_pressure))

    @property
    def pressure_rate(self) -> float:
        """Signed rate of pressure change in mbar per second.

        Positive when descending, negative when ascending, and zero for a
        constant-depth segment (including a possibly zero-duration gas switch,
        which would otherwise divide by zero).
        """
        # Constant depth has zero rate by definition — avoids a 0/0 division.
        if self.start_pressure == self.end_pressure:
            return 0.0
        return (self.end_pressure - self.start_pressure) / self.duration.total_seconds()

    # -------------------------------------------------------------------
    # Segment operations
    # -------------------------------------------------------------------

    def _validate_time(self, t: timedelta) -> None:
        if not (timedelta(0) <= t <= self.duration):
            raise ValueError(f"t={t} outside segment duration {self.duration}")

    def _validate_fraction(self, fraction: float) -> None:
        if not (0 <= fraction <= 1):
            raise ValueError(f"fraction={fraction} outside [0, 1]")

    def _validate_pressure(self, pressure: Pressure) -> None:
        if not (
            min(self.start_pressure, self.end_pressure)
            <= pressure
            <= max(self.start_pressure, self.end_pressure)
        ):
            raise ValueError(
                f"pressure={pressure} outside segment pressure range [{self.start_pressure}, {self.end_pressure}]"
            )

    def pressure_at_time(self, t: timedelta) -> Pressure:
        """Pressure at time t into the segment. Linear interpolation."""
        self._validate_time(t)

        fraction = t.total_seconds() / self.duration.total_seconds()
        return self.pressure_at_fraction(fraction)

    def pressure_at_fraction(self, fraction: float) -> Pressure:
        """Pressure at fraction (0 to 1) into the segment. Linear interpolation."""
        self._validate_fraction(fraction)

        delta_mbar = (self.end_pressure - self.start_pressure) * fraction
        return Pressure.from_mbar(self.start_pressure.mbar + delta_mbar)

    def time_at_pressure(self, pressure: Pressure) -> timedelta:
        """Time at which a given pressure is reached. Linear interpolation."""
        self._validate_pressure(pressure)

        if self.start_pressure == self.end_pressure:
            raise ValueError(
                "Segment has no pressure change; time_at_pressure is undefined."
            )

        fraction = (pressure - self.start_pressure) / (
            self.end_pressure - self.start_pressure
        )
        return timedelta(seconds=self.duration.total_seconds() * fraction)

    def time_at_fraction(self, fraction: float) -> timedelta:
        """Time at which a given fraction (0 to 1) is reached. Linear interpolation."""
        self._validate_fraction(fraction)

        return timedelta(seconds=self.duration.total_seconds() * fraction)

    def fraction_at_pressure(self, pressure: Pressure) -> float:
        """Fraction (0 to 1) at which a given pressure is reached. Linear interpolation."""
        self._validate_pressure(pressure)

        if self.start_pressure == self.end_pressure:
            raise ValueError(
                "Segment has no pressure change; fraction_at_pressure is undefined."
            )

        return (pressure - self.start_pressure) / (
            self.end_pressure - self.start_pressure
        )

    def fraction_at_time(self, t: timedelta) -> float:
        """Fraction (0 to 1) at time t into the segment. Linear interpolation."""
        self._validate_time(t)

        return t.total_seconds() / self.duration.total_seconds()

    # -------------------------------------------------------------------
    # Segment splitting and merging
    # -------------------------------------------------------------------

    def split_at_time(self, t: timedelta) -> tuple[DiveSegment, DiveSegment]:
        """Split into two segments at time t — useful for injecting a gas switch mid-segment."""
        mid = self.pressure_at_time(t)
        a = DiveSegment(self.start_pressure, mid, t, self.gas)
        b = DiveSegment(mid, self.end_pressure, self.duration - t, self.gas)
        return a, b

    def split_at_fraction(self, fraction: float) -> tuple[DiveSegment, DiveSegment]:
        """Split into two segments at fraction (0 to 1) — useful for injecting a gas switch mid-segment."""
        mid = self.pressure_at_fraction(fraction)
        t = self.duration * fraction
        a = DiveSegment(self.start_pressure, mid, t, self.gas)
        b = DiveSegment(mid, self.end_pressure, self.duration - t, self.gas)
        return a, b

    def merge_with(self, other: DiveSegment, *, force: bool = False) -> DiveSegment:
        """Merge with another segment if they are continuous (end pressure of self matches start pressure of other).
        If force=True, merges regardless of continuity (use with caution — may produce unrealistic segments).
        The resulting segment takes the start pressure of self and end pressure of other, with duration combined.
        Gas and kind are taken from self if continuous.
        Ascent and constant kinds are preserved if self is ascent or constant, otherwise default to SegmentKind.ASCENT or SegmentKind.CONSTANT.

        Known limitation: the merged segment always keeps ``self.gas``. When
        ``force=True`` is used to merge two segments with *different* gases (e.g.
        across a gas discontinuity), ``other.gas`` is silently discarded. The
        caller is responsible for only force-merging segments where dropping the
        other gas is acceptable.

        Args:
            other: The other segment to merge with.
            force: Whether to merge regardless of continuity. Defaults to False.

        Raises:
            ValueError: If segments are not fully continuous and force is False.

        Returns:
            The merged dive segment.
        """

        if not force and not self.is_fully_continuous_with(other):
            raise ValueError("Segments are not fully continuous and cannot be merged.")

        return DiveSegment(
            start_pressure=self.start_pressure,
            end_pressure=other.end_pressure,
            duration=self.duration + other.duration,
            gas=self.gas,  # Assuming gas is the same for both segments if continuous
            ascent_kind=self.kind
            if isinstance(self.kind, SegmentKind.Ascent)
            else SegmentKind.ASCENT,
            constant_kind=self.kind
            if isinstance(self.kind, SegmentKind.Constant)
            else SegmentKind.CONSTANT,
        )

    # -------------------------------------------------------------------
    # Segment continuity checks
    # -------------------------------------------------------------------

    def is_pressure_continuous_with(self, other: DiveSegment) -> bool:
        """End pressure of self matches start pressure of other."""
        return self.end_pressure == other.start_pressure

    def is_gas_continuous_with(self, other: DiveSegment) -> bool:
        """Same gas on both segments (Nones treated as unknown — not continuous)."""
        return self.gas is not None and other.gas is not None and self.gas == other.gas

    def is_rate_continuous_with(self, other: DiveSegment) -> bool:
        """Same pressure rate across the boundary — segments form an unbroken linear traverse."""
        return math.isclose(
            self.pressure_rate,
            other.pressure_rate,
            rel_tol=1e-6,
        )

    def is_continuous_with(
        self,
        other: DiveSegment,
        *,
        check_gas: bool = False,
        check_rate: bool = False,
    ) -> bool:
        """
        Pressure-continuous by default.
        Optionally also checks gas and/or rate continuity.
        All three true = fully continuous (no seam between segments).
        """
        result = self.is_pressure_continuous_with(other)
        if check_gas:
            result = result and self.is_gas_continuous_with(other)
        if check_rate:
            result = result and self.is_rate_continuous_with(other)
        return result

    def is_fully_continuous_with(self, other: DiveSegment) -> bool:
        """Convenience — checks pressure, gas, and rate together."""
        return self.is_continuous_with(other, check_gas=True, check_rate=True)

    # -------------------------------------------------------------------
    # Segment iteration
    # -------------------------------------------------------------------

    def iter_pressures(
        self,
        interval: timedelta,
        *,
        include_end: bool = True,
    ) -> Iterator[tuple[timedelta, Pressure]]:
        """
        Yield (elapsed, pressure) at each interval through the segment.
        The start point is always yielded. The end point is yielded if
        include_end=True and it doesn't coincide with the last interval tick.

        Example:
            for t, p in segment.iter_pressures(timedelta(seconds=30)):
                tissue_model.update(p, timedelta(seconds=30))
        """
        t = timedelta(0)
        while t < self.duration:
            yield t, self.pressure_at_time(t)
            t += interval

        if include_end:
            yield self.duration, self.end_pressure

    def __hash__(self) -> int:
        return hash(
            (self.start_pressure, self.end_pressure, self.duration, self.gas, self.kind)
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DiveSegment):
            return NotImplemented
        return (
            self.start_pressure == other.start_pressure
            and self.end_pressure == other.end_pressure
            and self.duration == other.duration
            and self.gas == other.gas
            and self.kind == other.kind
        )

    def __repr__(self) -> str:
        return (
            f"DiveSegment(start_pressure={repr(self.start_pressure)}, "
            f"end_pressure={repr(self.end_pressure)}, "
            f"duration={self.duration}, "
            f"gas={self.gas}, "
            f"kind={self.kind})"
        )

    def __str__(self) -> str:
        if self.kind in SegmentKind.Constant:
            return f"{self.kind.name} segment at {self.start_pressure} for {self.duration}, breathing {self.gas}"

        return (
            f"{self.kind.name} segment from {self.start_pressure.depth_m:.1f}m to {self.end_pressure.depth_m:.1f}m "
            f"over {self.duration.total_seconds() / 60:.1f} minutes, breathing {self.gas.name}"
        )

    # TODO: to_dict, from_dict, to_json, from_json, etc.
