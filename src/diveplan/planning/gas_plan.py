"""Gas plan: carried gases, selection, consumption, and reserve planning.

Selection reads the ppO2 limits from ``DiveConfig.current().gas`` at call
time: a gas is usable at a pressure if its ppO2 sits within
``[min_ppo2_bar, deco_ppo2_bar]`` (the deco limit — the planner switches
gases during ascent, where the deco ppO2 applies). Among usable gases the
richest (highest fO2) wins: it off-gasses inert load fastest.

Also provides :func:`gas_consumption` (surface litres per gas over any
sequence of segments — a profile's or a plan's) and :func:`rock_bottom`
(the minimum reserve for an emergency shared-gas direct ascent).
"""

from collections.abc import Iterable
from typing import Optional

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.utils.conversions import coerce_depth_to_pressure, coerce_gas

__all__ = ["GasPlan", "gas_consumption", "rock_bottom"]

# Segment kinds billed at the deco SAC rate; everything else uses bottom SAC.
_DECO_KINDS = (
    SegmentKind.Ascent.DECO_ASCENT,
    SegmentKind.Constant.STOP,
    SegmentKind.Constant.GAS_SWITCH,
)


class GasPlan:
    """An ordered collection of carried gases with depth-based selection.

    Gases may be given as :class:`Gas` objects or names — ``GasPlan(["air",
    "ean50"])`` — parsed via :meth:`Gas.from_name`.
    """

    __slots__ = ("_gases",)

    _gases: tuple[Gas, ...]

    def __init__(self, gases: Iterable[Gas | str]):
        unique: list[Gas] = []
        for gas in gases:
            mix = coerce_gas(gas)
            if mix not in unique:
                unique.append(mix)
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


# ---------------------------------------------------------------------------
# Consumption and reserve planning
# ---------------------------------------------------------------------------


def gas_consumption(segments: Iterable[DiveSegment]) -> dict[Gas, float]:
    """Surface litres of each gas consumed over `segments`.

    Per segment: ``SAC × mean ambient pressure (atm) × minutes`` — exact,
    since the mean pressure of a linear traverse is its midpoint. Deco
    phases (deco ascents, stops, gas switches) are billed at
    ``gas.sac_deco``, everything else at ``gas.sac_bottom``. Works on a
    profile's segments or on a plan from :func:`plan_ascent`.
    """
    limits = DiveConfig.current().gas
    totals: dict[Gas, float] = {}
    for segment in segments:
        sac = limits.sac_deco if segment.kind in _DECO_KINDS else limits.sac_bottom
        minutes = segment.duration.total_seconds() / 60.0
        litres = sac * segment.average_pressure.atm * minutes
        totals[segment.gas] = totals.get(segment.gas, 0.0) + litres
    return totals


def rock_bottom(
    depth: Pressure | str | float,
    *,
    divers: int = 2,
) -> float:
    """Minimum gas reserve (surface litres) at `depth` for an emergency.

    Models the classic worst case: `divers` divers (out-of-gas buddy plus
    donor) breathe from one supply at a stressed rate
    (``sac_bottom × sac_factor``) while solving the problem at depth for
    ``problem_solving_minutes``, then ascend directly to the surface at the
    configured ascent rate. Decompression stops are **not** included —
    this is a direct-ascent reserve; divide by cylinder size × working
    pressure to express it in bar.

    Args:
        depth: Depth as a Pressure, a "40 m"-style string, or bare metres.
        divers: Divers sharing the supply. Defaults to 2.

    Raises:
        ValueError: If `divers` is not strictly positive.
    """
    if divers <= 0:
        raise ValueError(f"divers must be > 0, got {divers}")

    cfg = DiveConfig.current()
    pressure = coerce_depth_to_pressure(depth)

    stressed_sac = cfg.gas.sac_bottom * cfg.gas.sac_factor * divers
    solving = stressed_sac * pressure.atm * cfg.gas.problem_solving_minutes

    ascent_minutes = max(0.0, pressure.depth_m) / cfg.planning.ascent_rate
    mean_atm = (pressure.atm + 1.0) / 2.0  # linear ascent to the surface
    ascent = stressed_sac * mean_atm * ascent_minutes

    return solving + ascent
