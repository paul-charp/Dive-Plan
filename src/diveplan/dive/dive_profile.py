"""Dive profile: the geometric plan of a dive.

A :class:`DiveProfile` is a validated sequence of
:class:`~diveplan.core.dive_segment.DiveSegment` — pure input geometry,
deliberately free of model results. It offers three ways of working:

- **building** — fluent methods (``descend_to("40 m")``, ``stay``,
  ``switch_gas("ean50")``…) and explicit segment surgery, governed by a
  :class:`ProfileBuilderPolicy`;
- **validation & repair** — problems are returned as pure-data
  :class:`ProfileValidationError` descriptors; canonical repairs live on
  ``fix``/``fix_all``;
- **timeline** — address the profile by runtime (``pressure_at(23)``), and
  sample it for integration via ``iter_samples`` (the single sampling
  authority used by models and visualization).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import timedelta
from enum import Enum, auto
from typing import Any, NamedTuple

from ..core.config import DiveConfig
from ..core.dive_segment import DiveSegment, SegmentKind
from ..core.gas import Gas
from ..core.pressure import Pressure
from ..utils.conversions import coerce_depth_to_pressure, coerce_gas

__all__ = (
    "DiveProfile",
    "ProfileSample",
    "ProfileValidationError",
    "ProfileContinuityError",
    "ProfileSimplicityError",
    "ProfileStartEndError",
    "ProfileDepthContinuityError",
    "ProfileGasContinuityError",
    "ProfileEmptyError",
    "ProfileTooShortError",
    "ProfileBuilderPolicy",
)

# ------------------------------------------------------------------
# Profile Validation Errors
# ------------------------------------------------------------------
# These are pure *descriptors* of a validation problem: an error type, the
# index/segments involved, a human-readable message, and a `fixable` flag.
#
# They deliberately do NOT hold a reference to the profile and do NOT know how
# to repair themselves. Repairs live on DiveProfile (see `.fix()` / `.fix_all()`),
# where all the canonical mutation logic already lives. This keeps the single
# responsibility of an exception — describing a problem — intact, makes the
# errors serializable for downstream consumers (CLI/GUI), and removes the
# duplicated/divergent fix logic that previously lived on each error.
#
# They remain `ValueError` subclasses so they can still be raised (e.g. by the
# RAISE builder policy) as well as collected and returned by `validate_profile`.


class ProfileValidationError(ValueError):
    """Base descriptor for a dive profile validation problem.

    Attributes:
        message: Human-readable description of the problem.
        segment_index: Index of the first segment involved, if applicable.
        segments: The offending segment(s), if applicable.
        fixable: Whether DiveProfile.fix() knows how to repair this error.
    """

    fixable: bool = False

    def __init__(
        self,
        message: str,
        *,
        segment_index: int | None = None,
        segments: tuple[DiveSegment, ...] = (),
    ):
        super().__init__(message)
        self.message = message
        self.segment_index = segment_index
        self.segments = segments


class ProfileEmptyError(ProfileValidationError):
    """The profile has no segments. Not auto-fixable."""

    fixable = False

    def __init__(self) -> None:
        super().__init__("Dive profile is empty.")


class ProfileTooShortError(ProfileValidationError):
    """The profile has fewer than 2 segments (surface → dive → surface). Not auto-fixable."""

    fixable = False

    def __init__(self, segment_count: int) -> None:
        self.segment_count = segment_count
        super().__init__(
            f"Dive profile must have at least 2 segments (surface → dive → surface), "
            f"but has only {segment_count}."
        )


class ProfileStartEndError(ProfileValidationError):
    """The profile does not start and end at the surface. Fixable via add_surface_segments()."""

    fixable = True

    def __init__(self, first_segment: DiveSegment, last_segment: DiveSegment) -> None:
        super().__init__(
            f"Dive profile must start and end at the surface, but starts with "
            f"{first_segment} and ends with {last_segment}. "
            f"Use .add_surface_segments() (or .fix()) to add surface segments.",
            segments=(first_segment, last_segment),
        )
        self.first_segment = first_segment
        self.last_segment = last_segment


class ProfileContinuityError(ProfileValidationError):
    """Base for problems at the seam between two adjacent segments."""

    segment_index: int  # always set for seam errors (narrows the Optional base)

    def __init__(
        self,
        message: str,
        segment_index: int,
        segment_a: DiveSegment,
        segment_b: DiveSegment,
    ):
        super().__init__(
            message,
            segment_index=segment_index,
            segments=(segment_a, segment_b),
        )
        self.segment_a = segment_a
        self.segment_b = segment_b


class ProfileDepthContinuityError(ProfileContinuityError):
    """The end pressure of one segment does not match the start of the next. Fixable via a transition segment."""

    fixable = True

    def __init__(
        self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment
    ) -> None:
        super().__init__(
            f"Depth discontinuity between segments {segment_index} and "
            f"{segment_index + 1}: {segment_a} → {segment_b}. "
            f"Use .fix_continuity() (or .fix()) to insert a transition segment.",
            segment_index,
            segment_a,
            segment_b,
        )


class ProfileGasContinuityError(ProfileContinuityError):
    """Adjacent segments use different gases without a gas switch. Fixable via a gas switch segment."""

    fixable = True

    def __init__(
        self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment
    ) -> None:
        super().__init__(
            f"Gas discontinuity between segments {segment_index} and "
            f"{segment_index + 1} that are not gas switches: {segment_a} → {segment_b}. "
            f"Use .fix_gas_continuity() (or .fix()) to insert a gas switch segment.",
            segment_index,
            segment_a,
            segment_b,
        )


class ProfileSimplicityError(ProfileContinuityError):
    """Adjacent segments are fully continuous and could be merged. Fixable via merge."""

    fixable = True

    def __init__(
        self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment
    ) -> None:
        super().__init__(
            f"Redundant segments {segment_index} and {segment_index + 1} could be "
            f"merged: {segment_a} → {segment_b}. "
            f"Use .simplify_profile() (or .fix()) to merge fully continuous segments.",
            segment_index,
            segment_a,
            segment_b,
        )


# ------------------------------------------------------------------
# Profile Builder Policy
# ------------------------------------------------------------------
class ProfileBuilderPolicy(Enum):
    """Policies for handling validation during dive profile construction.

    `RAISE_BAD_PROFILE`: Each mutating builder call validates only the seam(s)
        it touches (O(1)) and raises the specific ProfileValidationError on the
        first problem. Start/end-surface and simplicity are not enforced here —
        an in-progress profile is allowed to not yet return to the surface.
    `ALLOW_BAD_PROFILE`: No validation during construction. Call .validate_profile()
        and .fix()/.fix_all() before handing the profile to the planner.
    `AUTOFIX_BAD_PROFILE`: After each mutation, transitions and gas switches are
        inserted automatically. Convenient, but can produce unexpected geometry.
    """

    RAISE_BAD_PROFILE = auto()
    ALLOW_BAD_PROFILE = auto()
    AUTOFIX_BAD_PROFILE = auto()


# ------------------------------------------------------------------
# Argument coercion helpers (fluent builder + timeline ergonomics)
# ------------------------------------------------------------------

# Depth/gas coercion is shared with the rest of the library.
_as_pressure = coerce_depth_to_pressure
_as_gas = coerce_gas


def _as_timedelta(value: timedelta | float) -> timedelta:
    """Coerce a time argument: timedelta as-is, bare numbers as minutes
    (matching the DiveSegment duration convention)."""
    if isinstance(value, timedelta):
        return value
    return timedelta(minutes=value)


class ProfileSample(NamedTuple):
    """One integration step on the profile's global timeline.

    Represents the half-open interval ``(time - dt, time]``: ``pressure`` is
    the ambient pressure at the *end* of the step (rectangle rule, matching
    BaseDecoModel), ``gas`` the breathing gas throughout it.
    """

    time: timedelta
    dt: timedelta
    pressure: Pressure
    gas: Gas
    segment_index: int


# ------------------------------------------------------------------
# Dive Profile
# ------------------------------------------------------------------
class DiveProfile:
    """A dive profile consisting of a sequence of dive segments.

    Provides builder methods to construct a profile and validation methods to
    ensure it is continuous and well-formed.

    - A profile should be continuous (pressure continuity, plus gas continuity
      except across explicit gas switches).
    - A profile should be as simple as possible (no redundant mergeable
      segments) — not strictly required; enforce with .simplify_profile().
    - Validation strictness during construction is controlled by `builder_policy`
      (see `ProfileBuilderPolicy`). Use .validate_profile() to check the whole
      profile after building with validation disabled.

    Repairs: errors returned by .validate_profile() are pure descriptors. Apply
    a single repair with .fix(error), or repair everything with .fix_all().
    """

    __slots__ = ("_segments", "_builder_policy")

    _segments: list[DiveSegment]

    def __init__(
        self,
        builder_policy: ProfileBuilderPolicy = ProfileBuilderPolicy.RAISE_BAD_PROFILE,
    ):
        """Initialize a new DiveProfile.

        Args:
            builder_policy: The policy to use when validation problems occur
                during construction.
        """
        self._segments = []
        self._builder_policy = builder_policy

    @property
    def builder_policy(self) -> ProfileBuilderPolicy:
        """The active profile builder policy."""
        return self._builder_policy

    def copy(
        self, *, override_policy: ProfileBuilderPolicy | None = None
    ) -> DiveProfile:
        """Create a copy of the dive profile.

        Segments are immutable value objects, so copying the segment *list*
        (a shallow list copy) is sufficient — the segments themselves are shared
        safely.

        Returns:
            A new DiveProfile with a fresh segment list and the same (or
            overridden) builder policy.
        """
        new_profile = DiveProfile.__new__(DiveProfile)
        new_profile._segments = list(self._segments)
        new_profile._builder_policy = override_policy or self._builder_policy
        return new_profile

    def _get_last_pressure(self) -> Pressure:
        """Current position — the end pressure of the last segment, or surface if empty."""
        if not self._segments:
            return Pressure.surface()
        return self.get_segment(-1).end_pressure

    def _get_last_gas(self) -> Gas:
        """Get the gas of the last segment, or air if empty."""
        if not self._segments:
            return Gas.air()
        return self.get_segment(-1).gas

    @property
    def segments(self) -> list[DiveSegment]:
        """The list of segments in the profile."""
        return self._segments

    @property
    def segment_count(self) -> int:
        """The number of segments in the profile."""
        return len(self._segments)

    # ------------------------------------------------------------------
    # Timeline — address the profile by runtime instead of segment index
    # ------------------------------------------------------------------
    # Convention: a segment owns the half-open interval [start, end) of the
    # global timeline; the final segment additionally owns its end instant
    # (t == runtime). At a seam this resolves to the *later* segment, so
    # gas_at() at a gas-switch boundary reports the new gas. Zero-duration
    # segments (instant gas switches) own no interval and are skipped.

    @property
    def runtime(self) -> timedelta:
        """Total duration of the profile (sum of all segment durations)."""
        return sum((s.duration for s in self._segments), timedelta(0))

    def start_time_of_segment(self, index: int) -> timedelta:
        """Elapsed runtime at which the segment at `index` begins.

        Raises:
            IndexError: If the index is out of range.
        """
        n = len(self._segments)
        pos = index if index >= 0 else n + index
        if not 0 <= pos < n:
            raise IndexError(
                f"Segment index {index} is out of range for dive profile with "
                f"{n} segments."
            )
        return sum((s.duration for s in self._segments[:pos]), timedelta(0))

    def segment_index_at(self, t: timedelta | float) -> int:
        """Index of the segment active at runtime `t` (minutes or timedelta).

        Raises:
            ProfileEmptyError: If the profile has no segments.
            ValueError: If `t` is negative or beyond the total runtime.
        """
        if not self._segments:
            raise ProfileEmptyError()

        t = _as_timedelta(t)
        if t < timedelta(0):
            raise ValueError(f"t={t} is negative.")

        elapsed = timedelta(0)
        for i, segment in enumerate(self._segments):
            end = elapsed + segment.duration
            if t < end:
                return i
            elapsed = end

        if t == elapsed:  # t == runtime → owned by the final segment
            return len(self._segments) - 1
        raise ValueError(f"t={t} is beyond the profile runtime {elapsed}.")

    def segment_at(self, t: timedelta | float) -> DiveSegment:
        """The segment active at runtime `t` (minutes or timedelta)."""
        return self._segments[self.segment_index_at(t)]

    def pressure_at(self, t: timedelta | float) -> Pressure:
        """Ambient pressure at runtime `t` (minutes or timedelta), interpolated
        linearly within the active segment."""
        index = self.segment_index_at(t)
        segment = self._segments[index]
        # A zero-duration segment (instant gas switch) is a single instant at
        # constant depth — interpolation would divide by zero.
        if segment.duration == timedelta(0):
            return segment.start_pressure
        offset = _as_timedelta(t) - self.start_time_of_segment(index)
        return segment.pressure_at_time(offset)

    def gas_at(self, t: timedelta | float) -> Gas:
        """Breathing gas at runtime `t` (minutes or timedelta)."""
        return self.segment_at(t).gas

    def iter_samples(self, interval: timedelta | float) -> Iterator[ProfileSample]:
        """Yield integration steps over the whole profile timeline.

        The single sampling authority for model integration and
        visualization: steps never cross a segment boundary (the last step of
        each segment is shortened as needed, so boundaries are hit exactly —
        checkpoints depend on this), zero-duration gas-switch segments yield
        no step, and each step's dt sums exactly to the total runtime.

        Args:
            interval: Sample step — minutes as a number, or a timedelta.

        Raises:
            ValueError: If the interval is not strictly positive.
        """
        step_size = _as_timedelta(interval)
        if step_size <= timedelta(0):
            raise ValueError(f"Sample interval must be > 0, got {step_size}.")

        elapsed = timedelta(0)
        for index, segment in enumerate(self._segments):
            into_segment = timedelta(0)
            while into_segment < segment.duration:
                dt = min(step_size, segment.duration - into_segment)
                into_segment += dt
                yield ProfileSample(
                    time=elapsed + into_segment,
                    dt=dt,
                    pressure=segment.pressure_at_time(into_segment),
                    gas=segment.gas,
                    segment_index=index,
                )
            elapsed += segment.duration

    # ------------------------------------------------------------------
    # Seam helpers — local (O(1)) validation between two adjacent segments
    # ------------------------------------------------------------------

    @staticmethod
    def _is_gas_switch_seam(a: DiveSegment, b: DiveSegment) -> bool:
        """A seam is a legitimate gas switch if either side is a GAS_SWITCH segment."""
        return (
            a.kind is SegmentKind.Constant.GAS_SWITCH
            or b.kind is SegmentKind.Constant.GAS_SWITCH
        )

    @staticmethod
    def _is_mergeable(a: DiveSegment, b: DiveSegment) -> bool:
        """Adjacent segments are redundant only if fully continuous AND of the
        same kind — merging a GAS_SWITCH into a stop (or a deco ascent into a
        forced one) would erase meaningful semantics, not simplify."""
        return a.kind == b.kind and a.is_fully_continuous_with(b)

    def _seam_error(
        self, a: DiveSegment, b: DiveSegment, index: int
    ) -> ProfileValidationError | None:
        """Return the most fundamental continuity error at the seam (a → b), or None.

        Pressure continuity is a prerequisite for a gas switch, so a depth
        discontinuity is reported in preference to a gas one.
        """
        if not a.is_pressure_continuous_with(b):
            return ProfileDepthContinuityError(index, a, b)
        if not a.is_gas_continuous_with(b) and not self._is_gas_switch_seam(a, b):
            return ProfileGasContinuityError(index, a, b)
        return None

    def _raise_on_seam(self, a: DiveSegment, b: DiveSegment, index: int) -> None:
        """Under RAISE policy, raise the seam error (a → b) if there is one."""
        error = self._seam_error(a, b, index)
        if error is not None:
            raise error

    def _check_insertion(self, index: int, segment: DiveSegment) -> None:
        """Under RAISE policy, validate the seam(s) a new segment at `index` would create."""
        if self._builder_policy is not ProfileBuilderPolicy.RAISE_BAD_PROFILE:
            return
        n = len(self._segments)
        pos = index if index >= 0 else n + index
        pos = max(0, min(pos, n))
        if pos - 1 >= 0:
            self._raise_on_seam(self._segments[pos - 1], segment, pos - 1)
        if pos < n:
            self._raise_on_seam(segment, self._segments[pos], pos)

    def _autofix(self) -> None:
        """Under AUTOFIX policy, insert transitions and gas switches."""
        if self._builder_policy is ProfileBuilderPolicy.AUTOFIX_BAD_PROFILE:
            self.fix_continuity().fix_gas_continuity()

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------
    def add_segment(self, segment: DiveSegment) -> DiveProfile:
        """Append a segment to the profile.

        Raises:
            ProfileValidationError: Under RAISE policy, if the new segment is not
                continuous with the current last segment.
        """
        if (
            self._builder_policy is ProfileBuilderPolicy.RAISE_BAD_PROFILE
            and self._segments
        ):
            self._raise_on_seam(self._segments[-1], segment, len(self._segments) - 1)

        self._segments.append(segment)
        self._autofix()
        return self

    def add_segments(self, segments: list[DiveSegment]) -> DiveProfile:
        """Append multiple segments to the profile (each via add_segment)."""
        for segment in segments:
            self.add_segment(segment)
        return self

    def remove_segment_at_index(self, index: int) -> DiveProfile:
        """Remove a segment at a specific index.

        Raises:
            IndexError: If the index is out of range.
            ProfileValidationError: Under RAISE policy, if removing an interior
                segment would break continuity at the resulting seam.
        """
        n = len(self._segments)
        pos = index if index >= 0 else n + index
        if not 0 <= pos < n:
            raise IndexError(
                f"Index {index} is out of range for dive profile with {n} segments."
            )

        # Removing the first or last segment cannot break an interior seam.
        is_end = pos == 0 or pos == n - 1
        if (
            not is_end
            and self._builder_policy is ProfileBuilderPolicy.RAISE_BAD_PROFILE
        ):
            self._raise_on_seam(
                self._segments[pos - 1], self._segments[pos + 1], pos - 1
            )

        self._segments.pop(pos)
        self._autofix()
        return self

    def remove_segment_at_indices(self, indices: list[int]) -> DiveProfile:
        """Remove multiple segments at specific indices."""
        for index in sorted(indices, reverse=True):
            self.remove_segment_at_index(index)
        return self

    def remove_segment(self, segment: DiveSegment) -> DiveProfile:
        """Remove a segment by value."""
        self.remove_segment_at_index(self.get_segment_index(segment))
        return self

    def remove_segments(self, segments: list[DiveSegment]) -> DiveProfile:
        """Remove multiple segments by value."""
        for segment in segments:
            self.remove_segment(segment)
        return self

    def remove_last_segment(self) -> DiveProfile:
        """Remove the final segment from the profile."""
        if self._segments:
            self._segments.pop()
        return self

    def clear_profile(self) -> DiveProfile:
        """Clear all segments from the profile."""
        self._segments = []
        return self

    def insert_segment_at_index(self, index: int, segment: DiveSegment) -> DiveProfile:
        """Insert a segment at a specific index.

        Raises:
            ProfileValidationError: Under RAISE policy, if the insertion would
                create a discontinuous seam.
        """
        self._check_insertion(index, segment)
        self._segments.insert(index, segment)
        self._autofix()
        return self

    def insert_segments_at_index(
        self, index: int, segments: list[DiveSegment]
    ) -> DiveProfile:
        """Insert multiple segments at a specific index, in order."""
        pos_index = index if index >= 0 else len(self._segments) + index
        pos_index = max(0, pos_index)
        for offset, segment in enumerate(segments):
            self.insert_segment_at_index(pos_index + offset, segment)
        return self

    def replace_segment_at_index(self, index: int, segment: DiveSegment) -> DiveProfile:
        """Replace a segment at a specific index.

        Raises:
            IndexError: If the index is out of range.
            ProfileValidationError: Under RAISE policy, if the replacement breaks
                continuity at either adjacent seam.
        """
        n = len(self._segments)
        pos = index if index >= 0 else n + index
        if not 0 <= pos < n:
            raise IndexError(
                f"Index {index} is out of range for dive profile with {n} segments."
            )

        if self._builder_policy is ProfileBuilderPolicy.RAISE_BAD_PROFILE:
            if pos - 1 >= 0:
                self._raise_on_seam(self._segments[pos - 1], segment, pos - 1)
            if pos + 1 < n:
                self._raise_on_seam(segment, self._segments[pos + 1], pos)

        self._segments[pos] = segment
        self._autofix()
        return self

    def get_segment(self, index: int) -> DiveSegment:
        """Retrieve a segment by its index.

        Raises:
            IndexError: If the index is out of bounds.
        """
        try:
            return self._segments[index]
        except IndexError:
            raise IndexError(
                f"Segment index {index} is out of range for dive profile with "
                f"{len(self._segments)} segments."
            )

    def get_last_segment(self) -> DiveSegment:
        """Get the last segment in the profile."""
        return self.get_segment(-1)

    def get_first_segment(self) -> DiveSegment:
        """Get the first segment in the profile."""
        return self.get_segment(0)

    def get_segment_index(self, segment: DiveSegment) -> int:
        """Find the index of a specific segment."""
        return self._segments.index(segment)

    # ------------------------------------------------------------------
    # Fluent builders — chainable, coerce "40 m" / "ean50" style arguments
    # ------------------------------------------------------------------
    # Each method starts from the current position (end pressure of the last
    # segment, or the surface for an empty profile) and appends via
    # add_segment(), so the active builder policy applies as usual.
    #
    #     profile = (
    #         DiveProfile()
    #         .descend_to("40 m")
    #         .stay(20)
    #         .ascend_to("21 m")
    #         .switch_gas("ean50")
    #         .surface()
    #     )

    def descend_to(
        self,
        depth: Pressure | str | float,
        *,
        rate: float | None = None,
        gas: Gas | str | None = None,
    ) -> DiveProfile:
        """Append a descent from the current position to `depth`.

        Args:
            depth: Target as a Pressure, a parseable string ("40 m", "5 bar"),
                or a bare number in metres.
            rate: Descent rate in m/min. Defaults to the configured
                planning.descent_rate.
            gas: Gas for the descent (Gas or name like "ean32"). Defaults to
                the current gas (air on an empty profile).

        Raises:
            ValueError: If `depth` is not below the current position.
        """
        target = _as_pressure(depth)
        start = self._get_last_pressure()
        if target <= start:
            raise ValueError(
                f"descend_to target {target.depth_m:.1f} m is not below the "
                f"current position {start.depth_m:.1f} m — use ascend_to()."
            )
        rate = rate if rate is not None else DiveConfig.current().planning.descent_rate
        gas_mix = _as_gas(gas) if gas is not None else self._get_last_gas()
        duration = abs(target.depth_m - start.depth_m) / rate
        return self.add_segment(DiveSegment(start, target, duration, gas_mix))

    def ascend_to(
        self,
        depth: Pressure | str | float,
        *,
        rate: float | None = None,
        gas: Gas | str | None = None,
        kind: SegmentKind.Ascent = SegmentKind.ASCENT,
    ) -> DiveProfile:
        """Append an ascent from the current position to `depth`.

        Args:
            depth: Target as a Pressure, a parseable string ("21 m", "2 bar"),
                or a bare number in metres.
            rate: Ascent rate in m/min. Defaults to the configured
                planning.ascent_rate.
            gas: Gas for the ascent (Gas or name). Defaults to the current gas.
            kind: Ascent kind. Defaults to SegmentKind.ASCENT (forced ascent).

        Raises:
            ValueError: If `depth` is not above the current position.
        """
        target = _as_pressure(depth)
        start = self._get_last_pressure()
        if target >= start:
            raise ValueError(
                f"ascend_to target {target.depth_m:.1f} m is not above the "
                f"current position {start.depth_m:.1f} m — use descend_to()."
            )
        rate = rate if rate is not None else DiveConfig.current().planning.ascent_rate
        gas_mix = _as_gas(gas) if gas is not None else self._get_last_gas()
        duration = abs(target.depth_m - start.depth_m) / rate
        return self.add_segment(
            DiveSegment(start, target, duration, gas_mix, ascent_kind=kind)
        )

    def stay(
        self,
        duration: timedelta | float,
        *,
        gas: Gas | str | None = None,
        kind: SegmentKind.Constant = SegmentKind.CONSTANT,
    ) -> DiveProfile:
        """Append a constant-depth segment at the current position.

        Args:
            duration: Time to stay — minutes as a number, or a timedelta.
            gas: Gas for the segment (Gas or name). Defaults to the current gas.
            kind: Constant kind, e.g. SegmentKind.Constant.STOP for a deco
                stop. Defaults to SegmentKind.CONSTANT (bottom time).
        """
        here = self._get_last_pressure()
        gas_mix = _as_gas(gas) if gas is not None else self._get_last_gas()
        return self.add_segment(
            DiveSegment(here, here, duration, gas_mix, constant_kind=kind)
        )

    def switch_gas(self, gas: Gas | str) -> DiveProfile:
        """Append a gas switch at the current position.

        The switch takes the configured gas.gas_switch_minutes (zero = instant
        switch). Switching to the gas already in use is a no-op.

        Args:
            gas: The new gas (Gas or name like "ean50").
        """
        new_gas = _as_gas(gas)
        if new_gas == self._get_last_gas():
            return self
        here = self._get_last_pressure()
        return self.add_segment(
            DiveSegment(
                here,
                here,
                DiveConfig.current().gas.gas_switch_minutes,
                new_gas,
                constant_kind=SegmentKind.Constant.GAS_SWITCH,
            )
        )

    def surface(self) -> DiveProfile:
        """Append an ascent from the current position to the surface at the
        configured ascent rate (alias for add_end_surface_segment).

        Raises:
            ProfileEmptyError: If the profile has no segments.
        """
        return self.add_end_surface_segment()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        """Whether the profile is continuous and gas-continuous.

        Skips simplicity and start/end-surface checks — an in-progress profile
        is allowed to be non-simple and to not yet return to the surface.
        """
        return (
            len(
                self.validate_profile(
                    skip_simplicity=True, skip_start_end_segments=True
                )
            )
            == 0
        )

    def validate_profile(
        self,
        *,
        skip_simplicity: bool = False,
        skip_start_end_segments: bool = True,
    ) -> tuple[ProfileValidationError, ...]:
        """Validate the whole profile and return all problems found.

        Args:
            skip_simplicity: If True, do not report mergeable (redundant) seams.
            skip_start_end_segments: If True, do not require the profile to start
                and end at the surface.

        Returns:
            A tuple of validation errors, empty if the profile is valid.
        """
        errors: list[ProfileValidationError] = []

        if not self._segments:
            return (ProfileEmptyError(),)

        if len(self._segments) < 2:
            return (ProfileTooShortError(len(self._segments)),)

        if not skip_start_end_segments:
            if (
                self._segments[0].start_pressure != Pressure.surface()
                or self._segments[-1].end_pressure != Pressure.surface()
            ):
                errors.append(
                    ProfileStartEndError(self._segments[0], self._segments[-1])
                )

        # Pressure continuity
        for i, current in enumerate(self._segments[:-1]):
            next_seg = self._segments[i + 1]
            if not current.is_pressure_continuous_with(next_seg):
                errors.append(ProfileDepthContinuityError(i, current, next_seg))

        # Gas continuity (independent of pressure — gas switches excepted)
        for i, current in enumerate(self._segments[:-1]):
            next_seg = self._segments[i + 1]
            if not current.is_gas_continuous_with(
                next_seg
            ) and not self._is_gas_switch_seam(current, next_seg):
                errors.append(ProfileGasContinuityError(i, current, next_seg))

        # Simplicity (mergeable seams)
        if not skip_simplicity:
            for i, current in enumerate(self._segments[:-1]):
                next_seg = self._segments[i + 1]
                if self._is_mergeable(current, next_seg):
                    errors.append(ProfileSimplicityError(i, current, next_seg))

        return tuple(errors)

    # ------------------------------------------------------------------
    # Repair — fixes live here, not on the errors
    # ------------------------------------------------------------------

    def fix(self, error: ProfileValidationError) -> DiveProfile:
        """Apply the canonical repair for a single validation error.

        Repair strategies are dispatched on the error type. Errors flagged
        `fixable = False` (empty / too-short profiles) have no repair and raise.

        Args:
            error: An error returned by .validate_profile().

        Returns:
            The profile instance (for chaining).

        Raises:
            ValueError: If the error type is not auto-fixable.
        """
        if isinstance(error, ProfileStartEndError):
            self.add_surface_segments()
        elif isinstance(error, ProfileDepthContinuityError):
            transition = self.make_transition_segment(error.segment_a, error.segment_b)
            self._segments.insert(error.segment_index + 1, transition)
        elif isinstance(error, ProfileGasContinuityError):
            switch = self.make_gas_switch_segment(error.segment_a, error.segment_b)
            self._segments.insert(error.segment_index + 1, switch)
        elif isinstance(error, ProfileSimplicityError):
            merged = error.segment_a.merge_with(error.segment_b)
            self._segments[error.segment_index] = merged
            del self._segments[error.segment_index + 1]
        else:
            raise ValueError(f"{type(error).__name__} is not auto-fixable.")
        return self

    def fix_all(self) -> DiveProfile:
        """Repeatedly validate and repair until no fixable error remains.

        Fixes are applied one at a time and the profile re-validated each pass,
        because a single repair shifts segment indices and invalidates the
        indices captured by later errors.

        Returns:
            The profile instance (for chaining).
        """
        while True:
            errors = self.validate_profile(skip_start_end_segments=False)
            fixable = [e for e in errors if e.fixable]
            if not fixable:
                break
            self.fix(fixable[0])
        return self

    # ------------------------------------------------------------------
    # Canonical segment construction (shared by fixes and bulk operations)
    # ------------------------------------------------------------------

    @staticmethod
    def make_transition_segment(
        segment_a: DiveSegment, segment_b: DiveSegment
    ) -> DiveSegment:
        """Create a segment bridging a pressure gap between two segments.

        The transition travels from the end of `segment_a` to the start of
        `segment_b` at the configured ascent/descent rate, carrying
        `segment_a`'s gas. A gas mismatch between the two segments is a separate
        concern resolved by a gas switch — it does not block a transition.

        Raises:
            ValueError: If the segments are already pressure-continuous.
        """
        if segment_a.is_pressure_continuous_with(segment_b):
            raise ValueError(
                f"Segments {segment_a} and {segment_b} are already pressure-continuous, "
                "no transition segment needed."
            )

        planning = DiveConfig.current().planning
        depth_change = abs(
            segment_b.start_pressure.depth_m - segment_a.end_pressure.depth_m
        )
        rate = (
            planning.ascent_rate
            if segment_b.start_pressure < segment_a.end_pressure
            else planning.descent_rate
        )

        return DiveSegment(
            start_pressure=segment_a.end_pressure,
            end_pressure=segment_b.start_pressure,
            duration=depth_change / rate,
            gas=segment_a.gas,
        )

    @staticmethod
    def make_gas_switch_segment(
        segment_a: DiveSegment, segment_b: DiveSegment
    ) -> DiveSegment:
        """Create a gas switch segment between two pressure-continuous segments.

        Raises:
            ValueError: If the segments are already gas continuous, or are not
                pressure-continuous (a gas switch happens at a single depth).
        """
        if segment_a.is_gas_continuous_with(segment_b):
            raise ValueError(
                f"Segments {segment_a} and {segment_b} are already gas continuous, "
                "no gas switch segment needed."
            )
        if not segment_a.is_pressure_continuous_with(segment_b):
            raise ValueError(
                f"Segments {segment_a} and {segment_b} have a pressure discontinuity, "
                "cannot create a gas switch segment."
            )

        gas_switch_minutes = DiveConfig.current().gas.gas_switch_minutes
        return DiveSegment(
            start_pressure=segment_a.end_pressure,
            end_pressure=segment_b.start_pressure,
            duration=gas_switch_minutes,
            gas=segment_b.gas,
            constant_kind=SegmentKind.Constant.GAS_SWITCH,
        )

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def simplify_profile(self) -> DiveProfile:
        """Merge fully continuous adjacent segments to simplify the profile.

        Returns:
            A new simplified DiveProfile instance.
        """
        simplified = self.copy(override_policy=ProfileBuilderPolicy.ALLOW_BAD_PROFILE)
        simplified.clear_profile()

        if not self._segments:
            simplified._builder_policy = self._builder_policy
            return simplified

        current_merged = self._segments[0]
        for next_seg in self._segments[1:]:
            if self._is_mergeable(current_merged, next_seg):
                current_merged = current_merged.merge_with(next_seg)
            else:
                simplified.add_segment(current_merged)
                current_merged = next_seg
        simplified.add_segment(current_merged)

        simplified._builder_policy = self._builder_policy
        return simplified

    def fix_continuity(self) -> DiveProfile:
        """Insert transition segments to resolve pressure discontinuities (in place)."""
        if not self._segments:
            return self

        fixed_segments: list[DiveSegment] = [self._segments[0]]
        for i, current in enumerate(self._segments[:-1]):
            next_seg = self._segments[i + 1]
            if not current.is_pressure_continuous_with(next_seg):
                fixed_segments.append(self.make_transition_segment(current, next_seg))
            fixed_segments.append(next_seg)

        self._segments = fixed_segments
        return self

    def fix_gas_continuity(self) -> DiveProfile:
        """Insert gas switch segments to resolve gas discontinuities (in place)."""
        if not self._segments:
            return self

        fixed_segments: list[DiveSegment] = [self._segments[0]]
        for i, current in enumerate(self._segments[:-1]):
            next_seg = self._segments[i + 1]
            if not current.is_gas_continuous_with(
                next_seg
            ) and not self._is_gas_switch_seam(current, next_seg):
                fixed_segments.append(self.make_gas_switch_segment(current, next_seg))
            fixed_segments.append(next_seg)

        self._segments = fixed_segments
        return self

    def add_start_surface_segment(self) -> DiveProfile:
        """Ensure the profile starts with a descent from the surface.

        Raises:
            ProfileEmptyError: If the profile has no segments.
        """
        if not self._segments:
            raise ProfileEmptyError()

        if self._segments[0].start_pressure != Pressure.surface():
            descent_rate = DiveConfig.current().planning.descent_rate
            depth_change = abs(
                self._segments[0].start_pressure.depth_m - Pressure.surface().depth_m
            )
            self._segments.insert(
                0,
                DiveSegment(
                    start_pressure=Pressure.surface(),
                    end_pressure=self._segments[0].start_pressure,
                    duration=depth_change / descent_rate,
                    gas=self._segments[0].gas,
                ),
            )
        return self

    def add_end_surface_segment(self) -> DiveProfile:
        """Ensure the profile ends with an ascent to the surface.

        Raises:
            ProfileEmptyError: If the profile has no segments.
        """
        if not self._segments:
            raise ProfileEmptyError()

        if self._segments[-1].end_pressure != Pressure.surface():
            ascent_rate = DiveConfig.current().planning.ascent_rate
            depth_change = abs(
                Pressure.surface().depth_m - self._segments[-1].end_pressure.depth_m
            )
            self._segments.append(
                DiveSegment(
                    start_pressure=self._segments[-1].end_pressure,
                    end_pressure=Pressure.surface(),
                    duration=depth_change / ascent_rate,
                    gas=self._segments[-1].gas,
                    ascent_kind=SegmentKind.Ascent.DECO_ASCENT,
                )
            )
        return self

    def add_surface_segments(self) -> DiveProfile:
        """Ensure the profile both starts and ends at the surface.

        Raises:
            ProfileEmptyError: If the profile has no segments.
        """
        if not self._segments:
            raise ProfileEmptyError()
        return self.add_end_surface_segment().add_start_surface_segment()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict (builder policy + segments)."""
        return {
            "builder_policy": self._builder_policy.name,
            "segments": [segment.to_dict() for segment in self._segments],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DiveProfile:
        """Reconstruct a DiveProfile from :meth:`to_dict` output.

        Segments are loaded exactly as saved, *without* re-validating seams —
        a stored in-progress profile must round-trip even if it is not (yet)
        continuous. Call .validate_profile() after loading if you need the
        guarantees of the RAISE policy.

        Raises:
            KeyError: If the "segments" field is missing, or an unknown
                builder policy name is given.
            ValueError: If a segment entry is malformed.
        """
        profile = cls.__new__(cls)
        profile._builder_policy = ProfileBuilderPolicy[
            data.get("builder_policy", ProfileBuilderPolicy.RAISE_BAD_PROFILE.name)
        ]
        profile._segments = [DiveSegment.from_dict(entry) for entry in data["segments"]]
        return profile

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        """Serialize to a JSON string, optionally writing to a file."""
        data = json.dumps(self.to_dict(), indent=indent)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
        return data

    @classmethod
    def from_json(cls, data: str | None = None, path: str | None = None) -> DiveProfile:
        """Deserialize from a JSON string or file path (see :meth:`from_dict`)."""
        if path:
            with open(path, encoding="utf-8") as f:
                data = f.read()
        if data is None:
            raise ValueError("Provide either 'data' or 'path'")
        return cls.from_dict(json.loads(data))
