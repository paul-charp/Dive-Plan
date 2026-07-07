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
from typing import Any, ClassVar, Self

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
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the decompression model.

        Concrete models define their own configuration parameters
        (gradient factors, conservatism, …); this permissive abstract
        signature is what lets registry-typed construction
        (``registry.model(name)(**config)``) type-check. Arguments are
        still validated at runtime by the concrete ``__init__`` — do not
        forward them here.
        """
        self.sample_rate_seconds = 1

    @property
    def name(self) -> str:
        """Display name of this model instance, conservatism included.

        Defaults to the registry ``NAME``. Models with a conservatism
        setting (gradient factors, VPM conservatism level) append it, so
        the name alone says how a schedule was computed — e.g.
        ``"zhl16c GF 30/70"`` or ``"vpmb +3"``.
        """
        return getattr(type(self), "NAME", type(self).__name__)

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
        """Return the current (conservative) ceiling.

        Anything the ceiling depends on beyond tissue state — gradient
        factors, conservatism level — is instance configuration, baked in
        at construction. Overrides keep this exact signature.
        """

    def get_ascent_ceiling(
        self, target: Pressure, first_stop: Pressure | None = None
    ) -> Pressure:
        """Ceiling for testing an ascent to `target` during staged deco.

        The ascent planner calls this — never a model-specific API — so
        models whose tolerance evolves over the ascent can express that
        here: Bühlmann interpolates its gradient factor toward `target`,
        and VPM-B's Boyle/CVA compensation will land here too.
        `first_stop` is the first (deepest) stop of the ascent being
        planned, or None while it is not yet known.

        Default: the plain :meth:`get_ceiling`, which is correct for any
        model whose tolerance does not depend on ascent context.
        """
        return self.get_ceiling()

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
