"""Shared Bühlmann machinery: gradient factors and Haldane tissue compartments.

Unit conventions
----------------
- Bühlmann ``a`` coefficients are published in **bar**; they are converted to
  mbar internally. ``b`` coefficients are dimensionless.
- Tissue tensions are tracked as **float mbar** internally, not integer-mbar
  :class:`Pressure`: at fine sample rates (1 s) a slow compartment's per-step
  change is far below 1 mbar, and integer quantization would silently freeze
  it. ``Pressure`` remains the boundary type for all inputs and outputs.
- Alveolar (inspired) inert-gas pressure subtracts water vapor at body
  temperature: ``(P_amb − 62.7 mbar) · fraction`` (Bühlmann's 0.0627 bar).

Gradient factors follow Erik Baker's convention: GF-low applies at the first
(deepest) stop, GF-high at the surface, interpolated linearly in ambient
pressure between the two. Factors are fractions (``Gradient(0.3, 0.85)`` is
GF 30/85); ``Gradient(1.0, 1.0)`` is raw Bühlmann.
"""

from datetime import timedelta
from typing import Optional

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = ("Gradient", "Compartment", "WATER_VAPOR_PRESSURE_MBAR")

# Alveolar water vapor pressure at 37 °C (Bühlmann: 0.0627 bar).
WATER_VAPOR_PRESSURE_MBAR = 62.7

# Inert-gas fraction of dry air used for default surface equilibrium.
_AIR_FN2 = 0.79


class Gradient:
    """A gradient-factor pair (Baker GF low/high), as fractions.

    GF-low is the allowed fraction of the Bühlmann M-value gradient at the
    first (deepest) stop; GF-high applies at the surface. ``factor()``
    interpolates linearly in ambient pressure between the two.
    """

    __slots__ = ("gf_low", "gf_high")

    gf_low: float
    gf_high: float

    def __init__(self, gf_low: float, gf_high: float):
        if gf_low <= 0 or gf_high <= 0:
            raise ValueError(
                f"Gradient factors must be > 0, got gf_low={gf_low}, gf_high={gf_high}."
            )
        self.gf_low = gf_low
        self.gf_high = gf_high

    def __repr__(self) -> str:
        return f"Gradient(gf_low={self.gf_low}, gf_high={self.gf_high})"

    def __str__(self) -> str:
        return f"GF {round(self.gf_low * 100)}/{round(self.gf_high * 100)}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gradient):
            return NotImplemented
        return self.gf_low == other.gf_low and self.gf_high == other.gf_high

    def __hash__(self) -> int:
        return hash((self.gf_low, self.gf_high))

    def factor(self, pressure: Pressure, first_stop_pressure: Pressure) -> float:
        """Gradient factor applicable at ``pressure``.

        Returns gf_low at (and below) the first stop, gf_high at (and above)
        the surface, linear in ambient pressure in between. Continuous over
        the whole range. Reads the current surface pressure from config.
        """
        surface = Pressure.surface()
        if pressure >= first_stop_pressure:
            return self.gf_low
        if pressure <= surface or first_stop_pressure <= surface:
            return self.gf_high

        fraction = (pressure - surface) / (first_stop_pressure - surface)
        return self.gf_high + (self.gf_low - self.gf_high) * fraction


class Compartment:
    """One Haldane tissue compartment with Bühlmann a/b coefficients.

    Holds the compartment constants (N2/He half-times in minutes, ``a`` in
    bar, ``b`` dimensionless) and the current inert-gas tensions. Fresh
    compartments default to surface equilibrium on air: N2 at
    ``(P_surface − P_H2O) · 0.79``, He at zero.
    """

    __slots__ = (
        "ht_n2",
        "ht_he",
        "a_n2",
        "a_he",
        "b_n2",
        "b_he",
        "_ppn2_mbar",
        "_pphe_mbar",
    )

    ht_n2: float
    ht_he: float
    a_n2: float
    a_he: float
    b_n2: float
    b_he: float
    _ppn2_mbar: float
    _pphe_mbar: float

    def __init__(
        self,
        *,
        ht_n2: float,
        ht_he: float,
        a_n2: float,
        a_he: float,
        b_n2: float,
        b_he: float,
        ppn2: Optional[Pressure] = None,
        pphe: Optional[Pressure] = None,
    ):
        if ht_n2 <= 0 or ht_he <= 0:
            raise ValueError(f"Half-times must be > 0, got {ht_n2=}, {ht_he=}.")
        if b_n2 <= 0 or b_he <= 0:
            raise ValueError(f"b coefficients must be > 0, got {b_n2=}, {b_he=}.")

        self.ht_n2 = ht_n2
        self.ht_he = ht_he
        self.a_n2 = a_n2
        self.a_he = a_he
        self.b_n2 = b_n2
        self.b_he = b_he

        if ppn2 is not None:
            self._ppn2_mbar = float(ppn2.mbar)
        else:
            surface = Pressure.surface()
            self._ppn2_mbar = (surface.mbar - WATER_VAPOR_PRESSURE_MBAR) * _AIR_FN2
        self._pphe_mbar = float(pphe.mbar) if pphe is not None else 0.0

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def ppn2(self) -> Pressure:
        """Current N2 tension (rounded to integer mbar for display/compare)."""
        return Pressure.from_mbar(self._ppn2_mbar)

    @property
    def pphe(self) -> Pressure:
        """Current He tension (rounded to integer mbar for display/compare)."""
        return Pressure.from_mbar(self._pphe_mbar)

    @property
    def tensions_mbar(self) -> tuple[float, float]:
        """Exact (ppn2, pphe) tensions in float mbar — for state snapshots."""
        return (self._ppn2_mbar, self._pphe_mbar)

    def set_tensions_mbar(self, ppn2_mbar: float, pphe_mbar: float) -> None:
        """Restore exact tensions from a state snapshot."""
        if ppn2_mbar < 0 or pphe_mbar < 0:
            raise ValueError(
                f"Tensions cannot be negative, got {ppn2_mbar=}, {pphe_mbar=}."
            )
        self._ppn2_mbar = ppn2_mbar
        self._pphe_mbar = pphe_mbar

    def copy(self) -> "Compartment":
        """Independent copy with the same constants and current tensions."""
        clone = Compartment(
            ht_n2=self.ht_n2,
            ht_he=self.ht_he,
            a_n2=self.a_n2,
            a_he=self.a_he,
            b_n2=self.b_n2,
            b_he=self.b_he,
        )
        clone.set_tensions_mbar(self._ppn2_mbar, self._pphe_mbar)
        return clone

    # ------------------------------------------------------------------
    # Integration
    # ------------------------------------------------------------------

    def integrate(self, pressure: Pressure, gas: Gas, duration: timedelta) -> None:
        """Haldane exponential update toward the alveolar inert pressures.

        ``P(t+Δt) = P(t) + (P_alv − P(t)) · (1 − 2^(−Δt/ht))`` per inert gas,
        with ``P_alv = (P_amb − P_H2O) · fraction``.
        """
        minutes = duration.total_seconds() / 60.0
        alveolar_mbar = pressure.mbar - WATER_VAPOR_PRESSURE_MBAR

        self._ppn2_mbar += (alveolar_mbar * gas.fn2 - self._ppn2_mbar) * (
            1.0 - 2.0 ** (-minutes / self.ht_n2)
        )
        self._pphe_mbar += (alveolar_mbar * gas.fhe - self._pphe_mbar) * (
            1.0 - 2.0 ** (-minutes / self.ht_he)
        )

    # ------------------------------------------------------------------
    # Tolerated ambient pressure (ceiling contribution)
    # ------------------------------------------------------------------

    def tolerated_ambient_pressure(self, gradient_factor: float = 1.0) -> Pressure:
        """Minimum ambient pressure this compartment tolerates (Baker formula).

        ``P_amb_tol = (P_t − a·GF) / (GF/b + 1 − GF)`` with tension-weighted
        a/b for the N2/He mix. At GF = 1 this reduces to Bühlmann's
        ``(P_t − a) · b``. Clamped at zero (a fully desaturated compartment
        tolerates any ambient pressure).
        """
        if gradient_factor <= 0:
            raise ValueError(f"gradient_factor must be > 0, got {gradient_factor}.")

        total = self._ppn2_mbar + self._pphe_mbar
        if total <= 0:
            return Pressure(0)

        # Tension-weighted coefficients; a converted bar -> mbar.
        a_mbar = 1000.0 * (
            (self.a_n2 * self._ppn2_mbar + self.a_he * self._pphe_mbar) / total
        )
        b = (self.b_n2 * self._ppn2_mbar + self.b_he * self._pphe_mbar) / total

        tolerated = (total - a_mbar * gradient_factor) / (
            gradient_factor / b + 1.0 - gradient_factor
        )
        return Pressure.from_mbar(max(0.0, tolerated))

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Compartment):
            return NotImplemented
        return (
            self.ht_n2 == other.ht_n2
            and self.ht_he == other.ht_he
            and self.a_n2 == other.a_n2
            and self.a_he == other.a_he
            and self.b_n2 == other.b_n2
            and self.b_he == other.b_he
            and self._ppn2_mbar == other._ppn2_mbar
            and self._pphe_mbar == other._pphe_mbar
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.ht_n2,
                self.ht_he,
                self.a_n2,
                self.a_he,
                self.b_n2,
                self.b_he,
                self._ppn2_mbar,
                self._pphe_mbar,
            )
        )

    def __repr__(self) -> str:
        return (
            f"Compartment(ht_n2={self.ht_n2}, ppn2={self._ppn2_mbar:.1f} mbar, "
            f"pphe={self._pphe_mbar:.1f} mbar)"
        )

    def __str__(self) -> str:
        return f"PPN2: {self.ppn2}, PPHE: {self.pphe}"
