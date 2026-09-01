"""Dive: a deco model run over a profile, queryable and extendable.

The profile stays pure input geometry; everything a model computes lands
here. A :class:`Dive` may be complete or in progress (just the bottom
phase) — it stores model-state **checkpoints at segment boundaries** only
(O(segments) memory for batch runs) and answers time-addressed queries by
re-integrating at most one segment from the nearest checkpoint (exact,
since Haldane integration composes).

Queries and operations:

- ``state_at(t)`` / ``ceiling_at(t)`` — model state and ceiling at any runtime
- ``cns_at(t)`` / ``otu_at(t)`` — oxygen exposure accumulated by ``t``
- ``tissue_series(dt)`` — (time, state) samples for visualization
- ``tts(t)`` — time-to-surface: a counterfactual ascent planned from ``t``
- ``max_tts()`` — the peak of that over the dive: the deco obligation
- ``plan_ascent()`` — the deco schedule from the dive's current end
- ``with_ascent()`` / ``extend()`` — a new Dive continuing this one

One profile can be run under any number of models/settings and the dives
compared — nothing here mutates the profile or the caller's model.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any, NamedTuple

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile, ProfileBuilderPolicy, _as_timedelta
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.planning.ascent_plan import plan_ascent
from diveplan.planning.gas_plan import GasPlan, cns_percent, otu

__all__ = ["Dive", "TtsVariations"]


class TtsVariations(NamedTuple):
    """Sensitivity of the time-to-surface to small plan changes — the
    "+x /m +y /min" figures planners print next to a runtime."""

    per_meter: timedelta
    per_minute: timedelta


class Dive[StateT: DecoState]:
    """A deco model's run over a profile — complete or still in progress.

    Build via :meth:`run`. The dive owns an independent model copy and a
    copy of the profile's segment list; neither input is mutated. Extend an
    in-progress dive with :meth:`with_ascent` (plan and append the deco
    schedule) or :meth:`extend` (append arbitrary segments).
    """

    __slots__ = ("_profile", "_model", "_checkpoints")

    _profile: DiveProfile
    _model: BaseDecoModel[StateT]
    _checkpoints: tuple[StateT, ...]

    def __init__(
        self,
        profile: DiveProfile,
        model: BaseDecoModel[StateT],
        checkpoints: tuple[StateT, ...],
    ):
        self._profile = profile
        self._model = model
        self._checkpoints = checkpoints

    @classmethod
    def run(cls, profile: DiveProfile, model: BaseDecoModel[StateT]) -> "Dive[StateT]":
        """Integrate `model` over `profile` and capture boundary checkpoints.

        The caller's model is copied, not mutated — run the same profile
        under several models/settings and compare. The profile is integrated
        as-is; validate/repair it first if it may be discontinuous.
        """
        work = model.copy()
        checkpoints = [work.get_state()]
        for segment in profile.segments:
            checkpoints.append(work.integrate_segment(segment))
        return cls(profile.copy(), work, tuple(checkpoints))

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def profile(self) -> DiveProfile:
        """The dive profile this dive was computed from (own copy)."""
        return self._profile

    @property
    def checkpoints(self) -> tuple[StateT, ...]:
        """Model states at segment boundaries; ``[0]`` is the pre-dive state,
        ``[i]`` the state after segment ``i-1``."""
        return self._checkpoints

    @property
    def final_state(self) -> StateT:
        """Model state at the end of the profile."""
        return self._checkpoints[-1]

    def model_at(self, t: timedelta | float) -> BaseDecoModel[StateT]:
        """Independent model instance positioned at runtime `t`.

        Restores the checkpoint before `t`'s segment and re-integrates the
        partial segment — exact, since Haldane integration composes. The
        returned model is yours: integrating it further does not touch the
        result.
        """
        index = self._profile.segment_index_at(t)
        offset = _as_timedelta(t) - self._profile.start_time_of_segment(index)
        segment = self._profile.segments[index]

        work = self._model.copy()
        work.set_state(self._checkpoints[index])
        if offset > timedelta(0):
            partial = DiveSegment(
                segment.start_pressure,
                segment.pressure_at_time(offset),
                offset,
                segment.gas,
            )
            work.integrate_segment(partial)
        return work

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def state_at(self, t: timedelta | float) -> StateT:
        """Model state at runtime `t` (minutes or timedelta)."""
        return self.model_at(t).get_state()

    def ceiling_at(self, t: timedelta | float) -> Pressure:
        """Deco ceiling at runtime `t`."""
        return self.model_at(t).get_ceiling()

    def cns_at(self, t: timedelta | float) -> float:
        """CNS oxygen-toxicity clock accumulated by runtime `t`, in percent.

        ``cns_at(profile.runtime)`` is the whole dive so far — the figure a
        :class:`~diveplan.dive.dive_report.DiveReport` carries as ``cns``.
        """
        return cns_percent(self._segments_until(t))

    def otu_at(self, t: timedelta | float) -> float:
        """Pulmonary oxygen-toxicity units (REPEX) accumulated by runtime `t`."""
        return otu(self._segments_until(t))

    def _segments_until(self, t: timedelta | float) -> list[DiveSegment]:
        """The profile's segments up to `t`, the last one truncated exactly."""
        index = self._profile.segment_index_at(t)
        offset = _as_timedelta(t) - self._profile.start_time_of_segment(index)
        segments = list(self._profile.segments[:index])
        if offset > timedelta(0):
            segment = self._profile.segments[index]
            segments.append(
                DiveSegment(
                    segment.start_pressure,
                    segment.pressure_at_time(offset),
                    offset,
                    segment.gas,
                )
            )
        return segments

    def tissue_series(
        self, interval: timedelta | float
    ) -> Iterator[tuple[timedelta, StateT]]:
        """Yield (time, state) at each sample step — for tissue plots.

        Starts with the pre-dive state at t=0, then one snapshot per profile
        sample (see :meth:`DiveProfile.iter_samples`).
        """
        work = self._model.copy()
        work.set_state(self._checkpoints[0])
        yield (timedelta(0), work.get_state())
        for sample in self._profile.iter_samples(interval):
            work.integrate(sample.pressure, sample.gas, sample.dt)
            yield (sample.time, work.get_state())

    def tts(self, t: timedelta | float, gas_plan: GasPlan | None = None) -> timedelta:
        """Time-to-surface at runtime `t`: the duration of an ascent planned
        from the model state, depth, and gas at that moment.

        Args:
            t: Runtime to ask "if I ascended now, how long?" at.
            gas_plan: Deco gases available for the hypothetical ascent.
                Defaults to all gases appearing in the profile.
        """
        if gas_plan is None:
            gas_plan = GasPlan(self._unique_gases())
        ascent = plan_ascent(
            self.model_at(t),
            start_pressure=self._profile.pressure_at(t),
            gas=self._profile.gas_at(t),
            gas_plan=gas_plan,
            clock_offset=t,  # stop departures align to the dive clock
        )
        return sum((s.duration for s in ascent), timedelta(0))

    def max_tts(self, gas_plan: GasPlan | None = None) -> timedelta:
        """Peak time-to-surface over the dive — the largest :meth:`tts` at any
        segment boundary.

        This is the deco obligation the plan has to carry. On a bottom-phase
        dive it is the TTS at the moment of leaving the bottom; on a full dive
        (bottom plus its planned ascent) it is the same figure, found at the
        boundary where the ascent begins. Only boundaries are examined: TTS
        rises while on-gassing at depth and falls through the ascent, so its
        maximum sits on a seam, and the stored checkpoints make each one free
        of re-integration.

        Costs one ascent plan per boundary — keep the returned value rather
        than calling this inside a loop.

        Args:
            gas_plan: Deco gases available for the hypothetical ascents.
                Defaults to all gases appearing in the profile.
        """
        segments = self._profile.segments
        if not segments:
            return timedelta(0)
        if gas_plan is None:
            gas_plan = GasPlan(self._unique_gases())

        surface = Pressure.surface()
        peak = timedelta(0)
        elapsed = timedelta(0)
        for index, state in enumerate(self._checkpoints):
            if index:
                elapsed += segments[index - 1].duration
            pressure = (
                segments[0].start_pressure
                if index == 0
                else segments[index - 1].end_pressure
            )
            if pressure.mbar <= surface.mbar:
                continue  # already at the surface: nothing to ascend
            # Forward-looking gas, matching the profile's seam convention.
            gas = segments[index].gas if index < len(segments) else segments[-1].gas
            work = self._model.copy()
            work.set_state(state)
            peak = max(peak, _ascent_duration(work, pressure, gas, gas_plan, elapsed))
        return peak

    # ------------------------------------------------------------------
    # Continuing the dive
    # ------------------------------------------------------------------

    def plan_ascent(self, gas_plan: GasPlan | None = None) -> list[DiveSegment]:
        """Deco schedule from the dive's current end to the surface.

        Plans from the end-of-profile model state, depth, and gas, with stop
        departures aligned to the dive clock. The dive itself is untouched —
        use :meth:`with_ascent` to get a new Dive that includes the ascent.

        Args:
            gas_plan: Gases available for the ascent. Defaults to all gases
                appearing in the profile so far.
        """
        end = self._profile.runtime
        if gas_plan is None:
            gas_plan = GasPlan(self._unique_gases())
        return plan_ascent(
            self.model_at(end),
            start_pressure=self._profile.pressure_at(end),
            gas=self._profile.gas_at(end),
            gas_plan=gas_plan,
            clock_offset=end,
        )

    def extend(self, segments: list[DiveSegment]) -> "Dive[StateT]":
        """New Dive with `segments` appended and integrated.

        Cheap: the existing checkpoints are reused and only the new segments
        are integrated. The profile's builder policy applies to the new
        seams; this dive is not modified.
        """
        new_profile = self._profile.copy()
        new_profile.add_segments(segments)

        work = self._model.copy()  # already holds the end-of-profile state
        checkpoints = list(self._checkpoints)
        for segment in segments:
            checkpoints.append(work.integrate_segment(segment))
        return Dive(new_profile, work, tuple(checkpoints))

    def with_ascent(self, gas_plan: GasPlan | None = None) -> "Dive[StateT]":
        """New Dive completed with its planned deco ascent —
        ``dive.extend(dive.plan_ascent(gas_plan))``."""
        return self.extend(self.plan_ascent(gas_plan))

    def tts_variations(self, gas_plan: GasPlan | None = None) -> TtsVariations:
        """Extra time-to-surface per +1 m on the final segment and per +1 min
        of extra time at the current depth (both re-planned, not estimated).

        Meaningful when the profile ends in the bottom phase (the normal
        planning situation): "+1 m" re-runs the model over the profile with
        its final segment shifted one metre deeper (a transition is inserted
        automatically), "+1 min" extends the dive by a minute at the final
        depth. Deltas are clamped at zero — clock-aligned stop rounding can
        otherwise produce a spurious −few-seconds.
        """
        if gas_plan is None:
            gas_plan = GasPlan(self._unique_gases())
        end = self._profile.runtime
        base = self.tts(end, gas_plan)

        # +1 minute at the current depth.
        end_pressure = self._profile.pressure_at(end)
        end_gas = self._profile.gas_at(end)
        longer = self.model_at(end)
        longer.integrate_segment(DiveSegment(end_pressure, end_pressure, 1, end_gas))
        plus_minute = _ascent_duration(
            longer, end_pressure, end_gas, gas_plan, end + timedelta(minutes=1)
        )

        # Final segment 1 m deeper, transition auto-inserted, model re-run.
        delta_mbar = round(DiveConfig.current().physics.pressure_per_meter_mbar)
        last = self._profile.segments[-1]
        deeper = DiveSegment(
            Pressure(last.start_pressure.mbar + delta_mbar),
            Pressure(last.end_pressure.mbar + delta_mbar),
            last.duration,
            last.gas,
            ascent_kind=last.kind
            if isinstance(last.kind, SegmentKind.Ascent)
            else SegmentKind.ASCENT,
            constant_kind=last.kind
            if isinstance(last.kind, SegmentKind.Constant)
            else SegmentKind.CONSTANT,
        )
        variant = self._profile.copy(
            override_policy=ProfileBuilderPolicy.ALLOW_BAD_PROFILE
        )
        variant.replace_segment_at_index(-1, deeper)
        variant.fix_continuity()

        deep_model = self._model.copy()
        deep_model.set_state(self._checkpoints[0])
        for segment in variant.segments:
            deep_model.integrate_segment(segment)
        plus_meter = _ascent_duration(
            deep_model, deeper.end_pressure, deeper.gas, gas_plan, variant.runtime
        )

        zero = timedelta(0)
        return TtsVariations(
            per_meter=max(zero, plus_meter - base),
            per_minute=max(zero, plus_minute - base),
        )

    def _unique_gases(self) -> list[Gas]:
        gases: list[Gas] = []
        for segment in self._profile.segments:
            if segment.gas not in gases:
                gases.append(segment.gas)
        return gases

    @property
    def model_name(self) -> str:
        """Name of the model this result was computed with, conservatism
        included — e.g. ``"zhl16c GF 30/70"`` or ``"vpmb +3"``."""
        return self._model.name

    def __repr__(self) -> str:
        return (
            f"Dive({type(self._model).__name__}, "
            f"{self._profile.segment_count} segments, "
            f"runtime={self._profile.runtime})"
        )


def _ascent_duration(
    model: BaseDecoModel[Any],
    start_pressure: Pressure,
    gas: Gas,
    gas_plan: GasPlan,
    clock_offset: timedelta,
) -> timedelta:
    plan = plan_ascent(
        model,
        start_pressure=start_pressure,
        gas=gas,
        gas_plan=gas_plan,
        clock_offset=clock_offset,
    )
    return sum((s.duration for s in plan), timedelta(0))
