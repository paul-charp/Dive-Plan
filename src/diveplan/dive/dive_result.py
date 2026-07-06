"""Result layer: a deco model run over a profile, queryable by time.

The profile stays pure input geometry; everything a model computes lands
here. A :class:`DiveResult` stores model-state **checkpoints at segment
boundaries** only — O(segments) memory for batch runs — and answers
time-addressed queries by re-integrating at most one segment from the
nearest checkpoint (exact, since Haldane integration composes).

Queries:

- ``state_at(t)`` — model state at any runtime
- ``ceiling_at(t)`` — ceiling at any runtime
- ``tissue_series(dt)`` — (time, state) samples for visualization
- ``tts(t)`` — time-to-surface: a counterfactual ascent planned from the
  state at ``t`` (see :mod:`diveplan.planning.ascent_plan`)

One profile can be run under any number of models/settings and the results
compared — nothing here mutates the profile or the caller's model.
"""

from datetime import timedelta
from typing import Iterator

from diveplan.core.dive_segment import DiveSegment
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile, _as_timedelta
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.planning.ascent_plan import plan_ascent
from diveplan.planning.gas_plan import GasPlan

__all__ = ["DiveResult"]


class DiveResult[StateT: DecoState]:
    """A deco model's run over a profile: checkpoints + time queries.

    Build via :meth:`run`. The result owns an independent model copy and a
    copy of the profile's segment list; neither input is mutated.
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
    def run(
        cls, profile: DiveProfile, model: BaseDecoModel[StateT]
    ) -> "DiveResult[StateT]":
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
        """The dive profile this result was computed from (own copy)."""
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

    def _unique_gases(self) -> list[Gas]:
        gases: list[Gas] = []
        for segment in self._profile.segments:
            if segment.gas not in gases:
                gases.append(segment.gas)
        return gases

    def __repr__(self) -> str:
        return (
            f"DiveResult({type(self._model).__name__}, "
            f"{self._profile.segment_count} segments, "
            f"runtime={self._profile.runtime})"
        )
