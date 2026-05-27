import math
from datetime import timedelta
from enum import Enum, auto
from typing import Iterator

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = ["SegmentKind", "SegmentKindMember", "DiveSegment"]

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
    ASCENT = Ascent.DECO_ASCENT
    CONSTANT = Constant.BOTTOM

    # Union of all possible segment kinds for type annotations
    Members = Descent | Ascent | Constant


class DiveSegment:
    """A segment of a dive profile with a start and end pressure, duration, and gas.
    Immutable. __slots__ for memory efficiency in batch simulation.

    """

    __slots__ = ("start_pressure", "end_pressure", "duration", "gas", "kind")

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
            duration_minutes: Duration of the segment (in minutes or timedelta).
            gas: Gas mixture for the segment.
            ascent_kind: If the segment is an ascent, the kind of ascent. Defaults to SegmentKind.ASCENT.
            constant_kind: If the segment is at constant depth, the kind of constant depth. Defaults to SegmentKind.CONSTANT.
        """

        self.start_pressure = start_pressure
        self.end_pressure = end_pressure

        self.duration = (
            duration if isinstance(duration, timedelta) else timedelta(minutes=duration)
        )

        self.gas = gas
        self.kind = self._determine_kind(ascent_kind, constant_kind)

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
        return (self.start_pressure + self.end_pressure) / 2

    @property
    def absolute_pressure_change(self) -> Pressure:
        """Returns the absolute pressure change from start to end. Can be negative (ascent) or positive (descent, or no change if constant)."""
        return Pressure.from_mbar(abs(self.end_pressure - self.start_pressure))

    @property
    def pressure_rate(self) -> float:
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

        return (
            self.start_pressure + (self.end_pressure - self.start_pressure) * fraction
        )

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

    # TODO: Test repr
    def __repr__(self) -> str:
        return (
            f"DiveSegment(start_pressure={self.start_pressure}, "
            f"end_pressure={self.end_pressure}, "
            f"duration={self.duration}, "
            f"gas={self.gas}, "
            f"kind={self.kind})"
        )

    def __str__(self) -> str:
        if self.kind in SegmentKind.Constant:
            return f"{self.kind.name} segment at {self.start_pressure} for {self.duration}, breathing {self.gas}"

        return (
            f"{self.kind.name} segment from {self.start_pressure} to {self.end_pressure} "
            f"over {self.duration}, breathing {self.gas}"
        )

    # TODO: to_dict, from_dict, to_json, from_json, etc.
