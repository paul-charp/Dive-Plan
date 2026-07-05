"""Bühlmann ZHL-16C decompression model.

Sixteen parallel Haldane compartments (the 1b variant of the first
compartment, 5.0 min N2 half-time — the set used by most implementations).
Coefficient tables are the published ZHL-16C values: half-times in minutes,
``a`` in bar, ``b`` dimensionless.

The model is generic over :class:`ZHL16State` — a frozen snapshot of the 16
(N2, He) tissue tensions in float mbar (see ``common.py`` for why tensions
are floats, not integer-mbar Pressures).
"""

from datetime import timedelta

from diveplan.core.config import DiveConfig
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.models.buhlmann.common import Compartment, Gradient

__all__ = ["ZHL16C", "ZHL16State"]

# ZHL-16C coefficient tables (compartment 1b first). Sources: Bühlmann,
# Tauchmedizin; identical values are used by Subsurface/OSTC.
# fmt: off
N2_HALF_TIMES = (
    5.0, 8.0, 12.5, 18.5, 27.0, 38.3, 54.3, 77.0,
    109.0, 146.0, 187.0, 239.0, 305.0, 390.0, 498.0, 635.0,
)
N2_A = (
    1.1696, 1.0000, 0.8618, 0.7562, 0.6200, 0.5043, 0.4410, 0.4000,
    0.3750, 0.3500, 0.3295, 0.3065, 0.2835, 0.2610, 0.2480, 0.2327,
)
N2_B = (
    0.5578, 0.6514, 0.7222, 0.7825, 0.8126, 0.8434, 0.8693, 0.8910,
    0.9092, 0.9222, 0.9319, 0.9403, 0.9477, 0.9544, 0.9602, 0.9653,
)
HE_HALF_TIMES = (
    1.88, 3.02, 4.72, 6.99, 10.21, 14.48, 20.53, 29.11,
    41.20, 55.19, 70.69, 90.34, 115.29, 147.42, 188.24, 240.03,
)
HE_A = (
    1.6189, 1.3830, 1.1919, 1.0458, 0.9220, 0.8205, 0.7305, 0.6502,
    0.5950, 0.5545, 0.5333, 0.5189, 0.5181, 0.5176, 0.5172, 0.5119,
)
HE_B = (
    0.4770, 0.5747, 0.6527, 0.7223, 0.7582, 0.7957, 0.8279, 0.8553,
    0.8757, 0.8903, 0.8997, 0.9073, 0.9122, 0.9171, 0.9217, 0.9267,
)
# fmt: on

COMPARTMENT_COUNT = 16


class ZHL16State(DecoState):
    """Frozen snapshot of the 16 (ppn2, pphe) tissue tensions in float mbar."""

    __slots__ = ("tissues",)

    tissues: tuple[tuple[float, float], ...]

    def __init__(self, tissues: tuple[tuple[float, float], ...]):
        if len(tissues) != COMPARTMENT_COUNT:
            raise ValueError(
                f"ZHL16State needs {COMPARTMENT_COUNT} tissue tension pairs, "
                f"got {len(tissues)}."
            )
        object.__setattr__(self, "tissues", tissues)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ZHL16State is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ZHL16State is immutable.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ZHL16State):
            return NotImplemented
        return self.tissues == other.tissues

    def __hash__(self) -> int:
        return hash(self.tissues)

    def __repr__(self) -> str:
        leading = ", ".join(f"({n:.0f}, {h:.0f})" for n, h in self.tissues[:3])
        return f"ZHL16State(tissues=[{leading}, …] mbar)"


class ZHL16C(BaseDecoModel[ZHL16State]):
    """Bühlmann ZHL-16C with Baker gradient factors.

    Fresh instances start at surface equilibrium on air. The sample rate is
    read from ``DiveConfig.current().planning.sample_rate_s`` at construction.

    Args:
        gradient: GF pair; defaults to ``Gradient(1.0, 1.0)`` (raw Bühlmann).
    """

    NAME = "zhl16c"

    __slots__ = ("gradient", "_compartments")

    gradient: Gradient
    _compartments: list[Compartment]

    def __init__(self, gradient: Gradient | None = None):
        super().__init__()
        self.sample_rate_seconds = DiveConfig.current().planning.sample_rate_s
        self.gradient = gradient if gradient is not None else Gradient(1.0, 1.0)
        self._compartments = [
            Compartment(
                ht_n2=N2_HALF_TIMES[i],
                ht_he=HE_HALF_TIMES[i],
                a_n2=N2_A[i],
                a_he=HE_A[i],
                b_n2=N2_B[i],
                b_he=HE_B[i],
            )
            for i in range(COMPARTMENT_COUNT)
        ]

    # ------------------------------------------------------------------
    # BaseDecoModel contract
    # ------------------------------------------------------------------

    def _integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None:
        for compartment in self._compartments:
            compartment.integrate(pressure, gas, dt)

    def _get_deco_state(self) -> ZHL16State:
        return ZHL16State(tuple(c.tensions_mbar for c in self._compartments))

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

    def set_state(self, state: ZHL16State) -> None:
        """Restore tissue tensions from a snapshot (exact, lossless)."""
        for compartment, (ppn2, pphe) in zip(
            self._compartments, state.tissues, strict=True
        ):
            compartment.set_tensions_mbar(ppn2, pphe)

    def copy(self) -> "ZHL16C":
        """Independent clone with the same gradient and tissue tensions —
        for hypothetical ascents (TTS queries) without disturbing the run."""
        clone = ZHL16C(gradient=self.gradient)
        clone.sample_rate_seconds = self.sample_rate_seconds
        clone.set_state(self._get_deco_state())
        return clone

    def __repr__(self) -> str:
        return f"ZHL16C(gradient={self.gradient!r}, ceiling={self.get_ceiling()})"
