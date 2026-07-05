"""Gas plan: the set of gases carried on a dive, and which to breathe when.

Selection reads the ppO2 limits from ``DiveConfig.current().gas`` at call
time: a gas is usable at a pressure if its ppO2 sits within
``[min_ppo2_bar, deco_ppo2_bar]`` (the deco limit — the planner switches
gases during ascent, where the deco ppO2 applies). Among usable gases the
richest (highest fO2) wins: it off-gasses inert load fastest.
"""

from collections.abc import Iterable
from typing import Optional

from diveplan.core.config import DiveConfig
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = ["GasPlan"]


class GasPlan:
    """An ordered collection of carried gases with depth-based selection."""

    __slots__ = ("_gases",)

    _gases: tuple[Gas, ...]

    def __init__(self, gases: Iterable[Gas]):
        unique: list[Gas] = []
        for gas in gases:
            if gas not in unique:
                unique.append(gas)
        if not unique:
            raise ValueError("GasPlan needs at least one gas.")
        self._gases = tuple(unique)

    @property
    def gases(self) -> tuple[Gas, ...]:
        """The carried gases (duplicates removed, insertion order)."""
        return self._gases

    @staticmethod
    def is_breathable(gas: Gas, pressure: Pressure) -> bool:
        """Whether `gas` is within the configured deco ppO2 window here."""
        limits = DiveConfig.current().gas
        ppo2 = gas.ppo2(pressure).bar
        return limits.min_ppo2_bar <= ppo2 <= limits.deco_ppo2_bar

    def best_gas_at(self, pressure: Pressure) -> Optional[Gas]:
        """Richest breathable gas at `pressure`, or None if none qualifies."""
        candidates = [g for g in self._gases if self.is_breathable(g, pressure)]
        if not candidates:
            return None
        return max(candidates, key=lambda g: g.fo2)

    def __repr__(self) -> str:
        return f"GasPlan({', '.join(str(g) for g in self._gases)})"
