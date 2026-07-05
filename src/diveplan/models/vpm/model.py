"""VPM-B decompression model (Varying Permeability Model, revision B).

A dual-phase (bubble) model: gas loading uses the same Haldane compartments
and ZHL-16 half-times as Bühlmann, but the ceiling comes from bubble-nuclei
mechanics instead of M-values — the allowable supersaturation gradient of a
compartment is set by the size of its gas nuclei, which are crushed smaller
by descent (raising the allowed gradient) and regenerate over weeks.

Scope
-----
This class implements the VPM-B *core*: tissue loading, crushing-pressure
tracking (permeable and impermeable regimes), nuclear regeneration, and the
ceiling from **initial allowable gradients** (Baker's ``vpmb_start_gradient``
stage). The Critical Volume Algorithm and Boyle-law stop compensation operate
on a full ascent schedule and therefore live in the ascent planner, not here;
until the planner applies them, ceilings from this model are the conservative
pre-CVA values. :data:`CRIT_VOLUME_LAMBDA_BAR_MIN` is exported for that later
stage.

Constants and formulas follow the Subsurface implementation of Erik Baker's
VPM-B (core/deco.cpp), which uses bar/µm units: gamma quantities are the
Yount surface-tension values pre-scaled so that ``2·γ/r`` with ``r`` in µm
yields bar.
"""

import math
from datetime import timedelta
from typing import ClassVar, Self

from diveplan.core.config import DiveConfig
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.models.buhlmann.common import Compartment
from diveplan.models.buhlmann.zhl16 import ZHL16C

__all__ = ["VpmB", "VpmState"]

# --- VPM-B constants (Subsurface core/deco.cpp; bar / µm / minutes) ---------

SURFACE_TENSION_GAMMA = 0.18137175  # γ  — bar·µm
SKIN_COMPRESSION_GAMMA_C = 2.6040525  # γc — bar·µm
CRIT_RADIUS_N2_UM = 0.55
CRIT_RADIUS_HE_UM = 0.45
GRADIENT_OF_IMPERMEABILITY_BAR = 8.30865
REGENERATION_TIME_MIN = 20160.0  # two weeks
OTHER_GASES_PRESSURE_BAR = 0.1359888  # O2/CO2/H2O contribution to tension
CRIT_VOLUME_LAMBDA_BAR_MIN = 199.58  # for the planner's Critical Volume Algorithm

# Conservatism level -> critical radius scale (larger nuclei = less allowed
# supersaturation = more conservative).
CONSERVATISM_RADIUS_SCALE = (1.0, 1.05, 1.12, 1.22, 1.35)

_B_TERM = 2.0 * (SKIN_COMPRESSION_GAMMA_C - SURFACE_TENSION_GAMMA)  # bar·µm


# --- Pure bubble-mechanics helpers (bar / µm) --------------------------------


def allowable_gradient_bar(radius_um: float) -> float:
    """Initial allowable supersaturation gradient for a nucleus of `radius_um`.

    ``2 · (γ/γc) · (γc − γ) / r`` — Yount's minimum gradient for bubble
    formation. Nominal N2 (0.55 µm) ≈ 0.614 bar.
    """
    if radius_um <= 0:
        raise ValueError(f"radius must be > 0, got {radius_um}")
    return (
        2.0
        * (SURFACE_TENSION_GAMMA / SKIN_COMPRESSION_GAMMA_C)
        * ((SKIN_COMPRESSION_GAMMA_C - SURFACE_TENSION_GAMMA) / radius_um)
    )


def crushed_radius_um(max_crushing_bar: float, initial_radius_um: float) -> float:
    """Nucleus radius after being crushed by `max_crushing_bar`.

    ``1/r = ΔP_max / (2(γc − γ)) + 1/r0`` — monotonically shrinking with
    crushing pressure; equals r0 at zero crushing.
    """
    if max_crushing_bar < 0:
        raise ValueError(f"crushing pressure must be >= 0, got {max_crushing_bar}")
    return 1.0 / (max_crushing_bar / _B_TERM + 1.0 / initial_radius_um)


def regenerated_radius_um(
    crushed_um: float, initial_radius_um: float, elapsed_min: float
) -> float:
    """Crushed nucleus regrowing toward its initial radius (τ = 2 weeks)."""
    return crushed_um + (initial_radius_um - crushed_um) * (
        1.0 - math.exp(-elapsed_min / REGENERATION_TIME_MIN)
    )


def impermeable_crushing_bar(
    ambient_bar: float, onset_tension_bar: float, initial_radius_um: float
) -> float:
    """Crushing pressure in the impermeable regime (gradient > 8.30865 bar).

    Above the onset gradient the bubble skin stops exchanging gas and the
    nucleus compresses per Boyle's law. Mechanical equilibrium + Boyle give
    ``A·r³ − B·r² − C = 0`` with ``A = P_amb − ΔP_onset + B/r0``,
    ``B = 2(γc − γ)``, ``C = T_onset·r0³``; the crushing pressure is then
    ``P_amb − T_onset·(r0/r)³``. Solved by Newton from r0 (single positive
    root for physical parameters).
    """
    a = ambient_bar - GRADIENT_OF_IMPERMEABILITY_BAR + _B_TERM / initial_radius_um
    b = _B_TERM
    c = onset_tension_bar * initial_radius_um**3

    radius = initial_radius_um
    for _ in range(100):
        f = a * radius**3 - b * radius**2 - c
        df = 3.0 * a * radius**2 - 2.0 * b * radius
        step = f / df
        radius -= step
        if abs(step) < 1e-12:
            break

    inner_pressure = c / radius**3
    return ambient_bar - inner_pressure


# --- State -------------------------------------------------------------------


class VpmState(DecoState):
    """Frozen VPM-B snapshot.

    Per compartment: ``(ppn2, pphe, max_crush_n2, max_crush_he,
    onset_tension)`` — tensions in float mbar, crushing pressures and onset
    tension in bar (the bubble-mechanics unit). ``runtime_min`` drives
    nuclear regeneration.
    """

    __slots__ = ("compartments", "runtime_min")

    compartments: tuple[tuple[float, float, float, float, float], ...]
    runtime_min: float

    def __init__(
        self,
        compartments: tuple[tuple[float, float, float, float, float], ...],
        runtime_min: float,
    ):
        if not compartments:
            raise ValueError("VpmState needs at least one compartment entry.")
        object.__setattr__(self, "compartments", compartments)
        object.__setattr__(self, "runtime_min", runtime_min)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("VpmState is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("VpmState is immutable.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VpmState):
            return NotImplemented
        return (
            self.compartments == other.compartments
            and self.runtime_min == other.runtime_min
        )

    def __hash__(self) -> int:
        return hash((self.compartments, self.runtime_min))

    def __repr__(self) -> str:
        return (
            f"VpmState({len(self.compartments)} compartments, "
            f"runtime={self.runtime_min:.1f} min)"
        )


# --- Model -------------------------------------------------------------------


class VpmB(BaseDecoModel[VpmState]):
    """VPM-B core model (pre-CVA ceilings; see module docstring for scope).

    Gas loading runs on the ZHL-16 half-times (the standard VPM-B choice),
    reusing the Bühlmann :class:`Compartment` — its a/b coefficients are
    inert here; the ceiling comes from bubble mechanics.

    Args:
        conservatism: 0 (nominal) … 4 — scales the initial critical radii
            by ``(1.0, 1.05, 1.12, 1.22, 1.35)``.
    """

    NAME = "vpmb"

    COMPARTMENT_COUNT: ClassVar[int] = len(ZHL16C.N2_HALF_TIMES)

    __slots__ = (
        "conservatism",
        "_compartments",
        "_max_crush_n2_bar",
        "_max_crush_he_bar",
        "_onset_tension_bar",
        "_runtime_min",
    )

    conservatism: int
    _compartments: list[Compartment]
    _max_crush_n2_bar: list[float]
    _max_crush_he_bar: list[float]
    _onset_tension_bar: list[float]
    _runtime_min: float

    def __init__(self, conservatism: int = 0):
        if not 0 <= conservatism < len(CONSERVATISM_RADIUS_SCALE):
            raise ValueError(
                f"conservatism must be 0..{len(CONSERVATISM_RADIUS_SCALE) - 1}, "
                f"got {conservatism}"
            )
        super().__init__()
        self.sample_rate_seconds = DiveConfig.current().planning.sample_rate_s
        self.conservatism = conservatism
        self._compartments = [
            Compartment(
                ht_n2=ZHL16C.N2_HALF_TIMES[i],
                ht_he=ZHL16C.HE_HALF_TIMES[i],
                a_n2=ZHL16C.N2_A[i],
                a_he=ZHL16C.HE_A[i],
                b_n2=ZHL16C.N2_B[i],
                b_he=ZHL16C.HE_B[i],
            )
            for i in range(self.COMPARTMENT_COUNT)
        ]
        n = self.COMPARTMENT_COUNT
        self._max_crush_n2_bar = [0.0] * n
        self._max_crush_he_bar = [0.0] * n
        # Onset tension: last total tension seen while still permeable —
        # initialized to the fresh-compartment tension.
        self._onset_tension_bar = [
            self._total_tension_bar(c) for c in self._compartments
        ]
        self._runtime_min = 0.0

    # ------------------------------------------------------------------
    # Bubble bookkeeping
    # ------------------------------------------------------------------

    @property
    def crit_radius_n2_um(self) -> float:
        """Initial N2 critical radius after conservatism scaling."""
        return CRIT_RADIUS_N2_UM * CONSERVATISM_RADIUS_SCALE[self.conservatism]

    @property
    def crit_radius_he_um(self) -> float:
        """Initial He critical radius after conservatism scaling."""
        return CRIT_RADIUS_HE_UM * CONSERVATISM_RADIUS_SCALE[self.conservatism]

    @staticmethod
    def _total_tension_bar(compartment: Compartment) -> float:
        ppn2, pphe = compartment.tensions_mbar
        return (ppn2 + pphe) / 1000.0 + OTHER_GASES_PRESSURE_BAR

    def _update_crushing(self, ambient_bar: float, index: int) -> None:
        """Track the maximum crushing pressure seen by compartment `index`."""
        tension = self._total_tension_bar(self._compartments[index])
        gradient = ambient_bar - tension

        if gradient <= GRADIENT_OF_IMPERMEABILITY_BAR:
            # Permeable regime: skin transmits the full gradient; remember the
            # tension in case the next step crosses into impermeability.
            crush_n2 = crush_he = gradient
            self._onset_tension_bar[index] = tension
        else:
            onset = self._onset_tension_bar[index]
            crush_n2 = impermeable_crushing_bar(
                ambient_bar, onset, self.crit_radius_n2_um
            )
            crush_he = impermeable_crushing_bar(
                ambient_bar, onset, self.crit_radius_he_um
            )

        if crush_n2 > self._max_crush_n2_bar[index]:
            self._max_crush_n2_bar[index] = crush_n2
        if crush_he > self._max_crush_he_bar[index]:
            self._max_crush_he_bar[index] = crush_he

    def _allowable_gradients_bar(self, index: int) -> tuple[float, float]:
        """Current (N2, He) allowable gradients for compartment `index` —
        initial radii crushed by the dive so far, then regenerated."""
        gradients = []
        for max_crush, r0 in (
            (self._max_crush_n2_bar[index], self.crit_radius_n2_um),
            (self._max_crush_he_bar[index], self.crit_radius_he_um),
        ):
            crushed = crushed_radius_um(max_crush, r0)
            regenerated = regenerated_radius_um(crushed, r0, self._runtime_min)
            gradients.append(allowable_gradient_bar(regenerated))
        return (gradients[0], gradients[1])

    # ------------------------------------------------------------------
    # BaseDecoModel contract
    # ------------------------------------------------------------------

    def _integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None:
        ambient_bar = pressure.mbar / 1000.0
        self._runtime_min += dt.total_seconds() / 60.0
        for i, compartment in enumerate(self._compartments):
            compartment.integrate(pressure, gas, dt)
            self._update_crushing(ambient_bar, i)

    def _get_deco_state(self) -> VpmState:
        return VpmState(
            tuple(
                (
                    *self._compartments[i].tensions_mbar,
                    self._max_crush_n2_bar[i],
                    self._max_crush_he_bar[i],
                    self._onset_tension_bar[i],
                )
                for i in range(self.COMPARTMENT_COUNT)
            ),
            self._runtime_min,
        )

    def get_ceiling(self) -> Pressure:
        """Minimum tolerated ambient pressure across compartments (pre-CVA).

        Per compartment: total inert tension (+ fixed other-gases pressure)
        minus the tension-weighted (N2, He) allowable gradient.
        """
        worst_mbar = 0.0
        for i, compartment in enumerate(self._compartments):
            ppn2, pphe = compartment.tensions_mbar
            inert = ppn2 + pphe
            if inert <= 0:
                continue
            grad_n2, grad_he = self._allowable_gradients_bar(i)
            weighted_bar = (grad_n2 * ppn2 + grad_he * pphe) / inert
            tolerated_mbar = (
                inert + OTHER_GASES_PRESSURE_BAR * 1000.0 - weighted_bar * 1000.0
            )
            worst_mbar = max(worst_mbar, tolerated_mbar)
        return Pressure.from_mbar(max(0.0, worst_mbar))

    # ------------------------------------------------------------------
    # State snapshot / restore
    # ------------------------------------------------------------------

    def set_state(self, state: VpmState) -> None:
        """Restore tissue tensions and bubble bookkeeping from a snapshot."""
        if len(state.compartments) != self.COMPARTMENT_COUNT:
            raise ValueError(
                f"State has {len(state.compartments)} compartments, "
                f"{type(self).__name__} has {self.COMPARTMENT_COUNT}."
            )
        for i, (ppn2, pphe, crush_n2, crush_he, onset) in enumerate(state.compartments):
            self._compartments[i].set_tensions_mbar(ppn2, pphe)
            self._max_crush_n2_bar[i] = crush_n2
            self._max_crush_he_bar[i] = crush_he
            self._onset_tension_bar[i] = onset
        self._runtime_min = state.runtime_min

    def copy(self) -> Self:
        """Independent clone (same conservatism, tensions, crushing history)."""
        clone = type(self)(conservatism=self.conservatism)
        clone.sample_rate_seconds = self.sample_rate_seconds
        clone.set_state(self._get_deco_state())
        return clone

    def __repr__(self) -> str:
        return f"VpmB(conservatism=+{self.conservatism}, ceiling={self.get_ceiling()})"
