from datetime import timedelta
from typing import Optional

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = "Gradient", "Compartment"


class Gradient:
    """Helper for computing gradients of dive segments."""

    __slots__ = "gf_low", "gf_high"

    # For type annotations only, since these are set in __init__ and not declared as class variables.
    gf_low: float
    gf_high: float

    def __init__(self, gf_low: float, gf_high: float):
        self.gf_low = gf_low
        self.gf_high = gf_high

    def __repr__(self) -> str:
        return f"Gradient(gf_low={self.gf_low}, gf_high={self.gf_high})"

    def __str__(self) -> str:
        return f"GF Low: {self.gf_low}%, GF High: {self.gf_high}%"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gradient):
            return NotImplemented
        return self.gf_low == other.gf_low and self.gf_high == other.gf_high

    def __hash__(self) -> int:
        return hash((self.gf_low, self.gf_high))

    def factor(self, depth_pressure: Pressure, max_depth_pressure: Pressure) -> float:
        """Linearly interpolate the gradient for a given depth."""
        if self.gf_low == self.gf_high:
            return self.gf_low

        if depth_pressure.is_surface:
            return self.gf_low

        elif depth_pressure >= max_depth_pressure:
            return self.gf_high

        else:
            return self.gf_low + (self.gf_high - self.gf_low) * (
                depth_pressure / max_depth_pressure
            )


class Compartment:
    """Helper for tracking compartment constants and saturation."""

    __slots__ = (
        "ppn2",
        "pphe",
        "ht_n2",
        "ht_he",
        "a_n2",
        "a_he",
        "b_n2",
        "b_he",
        "tolerated_pressure",
    )

    ppn2: Pressure
    pphe: Pressure
    ht_n2: float
    ht_he: float
    a_n2: float
    a_he: float
    b_n2: float
    b_he: float

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

        if ppn2 is None:
            ppn2 = Pressure.surface()
        if pphe is None:
            pphe = Pressure.surface()

        self.ppn2 = ppn2
        self.pphe = pphe
        self.ht_n2 = ht_n2
        self.ht_he = ht_he
        self.a_n2 = a_n2
        self.a_he = a_he
        self.b_n2 = b_n2
        self.b_he = b_he

    def update_compartment(
        self,
        pressure: Pressure,
        gas: Gas,
        duration: timedelta,
        gradient_factor: float,
    ):

        self._integrate_compartment(pressure, gas, duration)
        self._update_compartment_max_tolerated_pressure(pressure, gradient_factor)

    def _integrate_compartment(self, pressure: Pressure, gas: Gas, duration: timedelta):
        gas_ppn2 = gas.ppo2(pressure)
        gas_pphe = gas.pphe(pressure)

        duration_minutes = duration.total_seconds() / 60.0

        self.ppn2 = self._calc_inert_gas_pressure(
            self.ppn2, gas_ppn2, duration_minutes, self.ht_n2
        )

        self.pphe = self._calc_inert_gas_pressure(
            self.pphe, gas_pphe, duration_minutes, self.ht_he
        )

    def _update_compartment_max_tolerated_pressure(
        self, ambiant_pressure: Pressure, gradient_factor: float
    ):
        self.tolerated_pressure = self._calcInertGasLimit(
            self.ppn2,
            self.pphe,
            self.a_n2,
            self.b_n2,
            self.a_he,
            self.b_he,
            ambiant_pressure,
            gradient_factor,
        )

    @staticmethod
    def _calc_inert_gas_pressure(
        ambiant_pressure: Pressure,
        inspired_gas_pressure: Pressure,
        time_minutes: float,
        half_time_minutes: float,
    ) -> Pressure:
        return ambiant_pressure + (inspired_gas_pressure - ambiant_pressure) * (
            1 - 2 ** (-time_minutes / half_time_minutes)
        )

    @staticmethod
    def _calcInertGasLimit(
        ppn2: Pressure,
        pphe: Pressure,
        a_n2: float,
        b_n2: float,
        a_he: float,
        b_he: float,
        ambiant_pressure: Pressure,
        gradient_factor: float,
    ) -> Pressure:

        inert_pressure = ppn2 + pphe
        inert_gas_ratio = pphe / inert_pressure

        a = a_n2 * (1 - inert_gas_ratio) + a_he * inert_gas_ratio
        b = b_n2 * (1 - inert_gas_ratio) + b_he * inert_gas_ratio

        max_tolerated_pressure = (inert_pressure - a) * b
        return ambiant_pressure + gradient_factor * (
            max_tolerated_pressure - ambiant_pressure.mbar
        )

    def is_eq_pressures_only(self, other: Compartment) -> bool:
        return self.ppn2 == other.ppn2 and self.pphe == other.pphe

    def is_eq_with_pressures(self, other: Compartment) -> bool:
        return self.is_eq_pressures_only(other) and self == other

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
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.ppn2,
                self.pphe,
                self.ht_n2,
                self.ht_he,
                self.a_n2,
                self.a_he,
                self.b_n2,
                self.b_he,
            )
        )

    def __repr__(self) -> str:
        return f"Compartment(ppn2={self.ppn2}, pphe={self.pphe})"

    def __str__(self) -> str:
        return f"PPN2: {self.ppn2}, PPHE: {self.pphe}"
