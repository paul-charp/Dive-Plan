"""Decompression model base classes.

Each deco model defines its own :class:`DecoState` subclass — the typed,
copyable snapshot of everything the model knows at an instant (tissue
tensions, ceiling, …). Models are generic over their state type, so
``ZHL16C.integrate_segment(...)`` returns a ``ZHL16State``, not a bare dict.
State snapshots are what the result/report layer stores at checkpoints and
what counterfactual queries (TTS at time t) resume from.
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import ClassVar, Self

from diveplan.core.dive_segment import DiveSegment
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = ["BaseDecoModel", "DecoState"]


class DecoState:
    """Base class for model-specific decompression state snapshots.

    Subclasses should be immutable value objects (frozen dataclass or
    ``__slots__`` with guards) so they can be checkpointed, compared, and
    resumed from without defensive copying.
    """

    __slots__ = ()


class BaseDecoModel[StateT: DecoState](ABC):
    """Base class for all decompression models.

    Generic over the model's :class:`DecoState` subclass: each model type
    processes and returns its own state type.
    """

    __slots__ = ("sample_rate_seconds",)

    NAME: ClassVar[str]

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the decompression model."""
        self.sample_rate_seconds = 1

    def integrate_segment(self, segment: DiveSegment) -> StateT:
        """Integrate a dive segment into the model and return the state after it.

        Numerical scheme: rectangle rule — each sample step is integrated at
        the pressure of its end point over the actual elapsed dt (the final
        step may be shorter than the sample rate). Models with an analytic
        solution for linear pressure change (Schreiner) should override this.
        """
        interval = timedelta(seconds=self.sample_rate_seconds)

        previous = timedelta(0)
        for elapsed, pressure in segment.iter_pressures(interval):
            dt = elapsed - previous
            if dt > timedelta(0):
                self._integrate_model(pressure, segment.gas, dt)
            previous = elapsed

        return self._get_deco_state()

    def get_state(self) -> StateT:
        """Snapshot the current model state (public accessor)."""
        return self._get_deco_state()

    def integrate(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None:
        """Advance the model by a single step at the given pressure and gas.

        Public stepwise entry point for consumers that drive their own sample
        loop (result layer, planner); ``integrate_segment`` remains the
        segment-level API.
        """
        self._integrate_model(pressure, gas, dt)

    @abstractmethod
    def _integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None:
        """Advance the model by dt at the given ambient pressure and gas."""

    @abstractmethod
    def _get_deco_state(self) -> StateT:
        """Snapshot the current model state."""

    @abstractmethod
    def get_ceiling(self) -> Pressure:
        """Return the current ceiling depth."""

    @abstractmethod
    def set_state(self, state: StateT) -> None:
        """Restore the model to a previously snapshotted state (lossless).

        Together with :meth:`copy`, this is the checkpointing contract the
        result layer relies on for state-at-time and counterfactual (TTS)
        queries.
        """

    @abstractmethod
    def copy(self) -> Self:
        """Independent clone with identical configuration and current state."""
