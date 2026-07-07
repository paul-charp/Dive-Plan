"""Generic Bühlmann decompression engine.

All Bühlmann-family models share the same algorithm — parallel Haldane
compartments integrated toward alveolar inert-gas pressures, with a ceiling
from the a/b M-value line (optionally scaled by Baker gradient factors).
Variants differ only in their coefficient tables: number of compartments,
half-times, and a/b values.

:class:`BuhlmannModel` implements the whole algorithm; a concrete model
(e.g. :class:`~diveplan.models.buhlmann.zhl16.ZHL16C`) supplies only ``NAME``
and the six class-level tables. Table consistency is validated at class
definition time. Running without gradient factors is the default
(``Gradient(1.0, 1.0)`` — raw Bühlmann); pass a :class:`Gradient` for GF.
"""

from datetime import timedelta
from typing import ClassVar, Self

from diveplan.core.config import DiveConfig
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.models.buhlmann.common import Compartment, Gradient

__all__ = ["BuhlmannModel", "BuhlmannState"]

_TABLE_NAMES = ("N2_HALF_TIMES", "N2_A", "N2_B", "HE_HALF_TIMES", "HE_A", "HE_B")


class BuhlmannState(DecoState):
    """Frozen snapshot of (ppn2, pphe) tissue tensions in float mbar.

    Shared by all Bühlmann-family models; the tuple length equals the
    model's compartment count.
    """

    __slots__ = ("tissues",)

    tissues: tuple[tuple[float, float], ...]

    def __init__(self, tissues: tuple[tuple[float, float], ...]):
        if not tissues:
            raise ValueError("BuhlmannState needs at least one tissue tension pair.")
        object.__setattr__(self, "tissues", tissues)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("BuhlmannState is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("BuhlmannState is immutable.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BuhlmannState):
            return NotImplemented
        return self.tissues == other.tissues

    def __hash__(self) -> int:
        return hash(self.tissues)

    def __repr__(self) -> str:
        leading = ", ".join(f"({n:.0f}, {h:.0f})" for n, h in self.tissues[:3])
        return (
            f"BuhlmannState({len(self.tissues)} compartments, "
            f"tissues=[{leading}, …] mbar)"
        )


class BuhlmannModel(BaseDecoModel[BuhlmannState]):
    """Bühlmann algorithm over a subclass-supplied coefficient table.

    Subclasses define ``NAME`` and the six tables (half-times in minutes,
    ``a`` in bar, ``b`` dimensionless), all of equal length::

        class ZHL16C(BuhlmannModel):
            NAME = "zhl16c"
            N2_HALF_TIMES = (5.0, 8.0, ...)
            ...

    Fresh instances start at surface equilibrium on air. The sample rate is
    read from ``DiveConfig.current().planning.sample_rate_s`` at construction.

    Args:
        gradient: GF pair — a :class:`Gradient` or the usual string notation
            (``"30/70"``, percentages). Defaults to raw Bühlmann (GF 100/100).
    """

    # Coefficient tables — supplied by concrete subclasses.
    N2_HALF_TIMES: ClassVar[tuple[float, ...]]
    N2_A: ClassVar[tuple[float, ...]]
    N2_B: ClassVar[tuple[float, ...]]
    HE_HALF_TIMES: ClassVar[tuple[float, ...]]
    HE_A: ClassVar[tuple[float, ...]]
    HE_B: ClassVar[tuple[float, ...]]

    __slots__ = ("gradient", "_compartments")

    gradient: Gradient
    _compartments: list[Compartment]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate coefficient tables at class definition time."""
        super().__init_subclass__(**kwargs)
        defined = [name for name in _TABLE_NAMES if hasattr(cls, name)]
        if not defined:
            return  # abstract intermediate subclass — tables come later
        missing = [name for name in _TABLE_NAMES if name not in defined]
        if missing:
            raise TypeError(
                f"{cls.__name__} defines {defined} but is missing {missing}."
            )
        lengths = {name: len(getattr(cls, name)) for name in _TABLE_NAMES}
        if len(set(lengths.values())) != 1:
            raise TypeError(
                f"{cls.__name__} coefficient tables have mismatched lengths: {lengths}."
            )
        if 0 in lengths.values():
            raise TypeError(f"{cls.__name__} coefficient tables are empty.")

    def __init__(self, gradient: Gradient | str | None = None):
        if not hasattr(type(self), "N2_HALF_TIMES"):
            raise TypeError(
                "BuhlmannModel is an abstract engine — instantiate a concrete "
                "model (e.g. ZHL16C) that supplies coefficient tables."
            )
        super().__init__()
        self.sample_rate_seconds = DiveConfig.current().planning.sample_rate_s
        if gradient is None:
            self.gradient = Gradient(1.0, 1.0)
        elif isinstance(gradient, str):
            self.gradient = Gradient.from_str(gradient)
        else:
            self.gradient = gradient
        self._compartments = [
            Compartment(
                ht_n2=self.N2_HALF_TIMES[i],
                ht_he=self.HE_HALF_TIMES[i],
                a_n2=self.N2_A[i],
                a_he=self.HE_A[i],
                b_n2=self.N2_B[i],
                b_he=self.HE_B[i],
            )
            for i in range(self.compartment_count)
        ]

    @property
    def name(self) -> str:
        """Registry name plus gradient factors — e.g. ``"zhl16c GF 30/70"``."""
        gf = self.gradient
        return f"{super().name} GF {round(gf.gf_low * 100)}/{round(gf.gf_high * 100)}"

    @property
    def compartment_count(self) -> int:
        """Number of tissue compartments in this model's table."""
        return len(self.N2_HALF_TIMES)

    # ------------------------------------------------------------------
    # BaseDecoModel contract
    # ------------------------------------------------------------------

    def _integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None:
        for compartment in self._compartments:
            compartment.integrate(pressure, gas, dt)

    def _get_deco_state(self) -> BuhlmannState:
        return BuhlmannState(tuple(c.tensions_mbar for c in self._compartments))

    def get_ceiling(self, gradient_factor: float | None = None) -> Pressure:
        """Minimum tolerated ambient pressure across all compartments.

        A ceiling above surface pressure means decompression stops are
        required. Defaults to GF-low (the conservative bound during the deep
        phase); the ascent planner passes interpolated factors from
        ``Gradient.factor()`` as the diver approaches the surface.
        """
        gf = gradient_factor if gradient_factor is not None else self.gradient.gf_low
        return max(c.tolerated_ambient_pressure(gf) for c in self._compartments)

    # ------------------------------------------------------------------
    # State snapshot / restore (checkpointing, counterfactual queries)
    # ------------------------------------------------------------------

    def set_state(self, state: BuhlmannState) -> None:
        """Restore tissue tensions from a snapshot (exact, lossless).

        Raises:
            ValueError: If the snapshot's compartment count does not match
                this model's table.
        """
        if len(state.tissues) != self.compartment_count:
            raise ValueError(
                f"State has {len(state.tissues)} compartments, "
                f"{type(self).__name__} has {self.compartment_count}."
            )
        for compartment, (ppn2, pphe) in zip(
            self._compartments, state.tissues, strict=True
        ):
            compartment.set_tensions_mbar(ppn2, pphe)

    def copy(self) -> Self:
        """Independent clone with the same gradient and tissue tensions —
        for hypothetical ascents (TTS queries) without disturbing the run.

        Subclasses that change the ``__init__`` signature must override.
        """
        clone = type(self)(gradient=self.gradient)
        clone.sample_rate_seconds = self.sample_rate_seconds
        clone.set_state(self._get_deco_state())
        return clone

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(gradient={self.gradient!r}, "
            f"ceiling={self.get_ceiling()})"
        )
