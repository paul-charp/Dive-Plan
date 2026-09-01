"""Gas plan: carried gases, selection, consumption, and reserve planning.

Selection delegates breathability to :meth:`Gas.is_breathable` (the
configured deco ppO2 window — the planner switches gases during ascent,
where the deco limit applies). Among breathable carried gases the richest
(highest fO2) wins: it off-gasses inert load fastest.

Everything about breathing gas over a dive lives here: :class:`GasPlan`
(selection), :func:`gas_consumption` / :func:`deco_gas_consumption`
(surface litres per gas, whole dive or deco phase only),
:func:`rock_bottom` (emergency reserve), and the oxygen-exposure trackers
:func:`cns_percent` / :func:`otu`. The accounting functions all take any
sequence of segments — a profile's or an ascent plan's. They are module
functions, not GasPlan methods, deliberately: toxicity and consumption
depend on what was *breathed* (the profile), not on what was *carried*.
"""

import math
from collections.abc import Iterable
from datetime import timedelta

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.utils.conversions import coerce_depth_to_pressure, coerce_gas

__all__ = [
    "GasPlan",
    "gas_consumption",
    "deco_gas_consumption",
    "rock_bottom",
    "cns_percent",
    "otu",
    "NOAA_CNS_LIMITS",
]

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

    def best_gas_at(self, pressure: Pressure) -> Gas | None:
        """Richest breathable gas at `pressure`, or None if none qualifies.

        Breathability is :meth:`Gas.is_breathable` — the configured deco
        ppO2 window.
        """
        candidates = [g for g in self._gases if g.is_breathable(pressure)]
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


def deco_gas_consumption(segments: Iterable[DiveSegment]) -> dict[Gas, float]:
    """Surface litres of each gas consumed in the **deco phase** of `segments`.

    Same accounting as :func:`gas_consumption`, restricted to the segments
    billed at ``gas.sac_deco`` — deco ascents, stops, and gas switches. It
    is the "how much deco gas do I need" figure: on a full dive it covers
    everything from leaving the bottom, and a gas absent from the result was
    never breathed in deco.

    Note that the ascent from the bottom to the first stop is a deco ascent,
    so it counts here; a no-stop dive's plain ascent to the surface (a
    forced ascent) does not.
    """
    return gas_consumption(s for s in segments if s.kind in _DECO_KINDS)


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


# ---------------------------------------------------------------------------
# Oxygen exposure: NOAA CNS clock and REPEX OTUs
# ---------------------------------------------------------------------------
# Constant-depth segments are evaluated in closed form; segments with
# changing depth are integrated numerically at midpoint ppO2.
#
# - CNS %: fraction of the NOAA single-exposure oxygen limit consumed,
#   linearly interpolated between table nodes; nothing accrues below 0.5 bar
#   ppO2; above 1.6 bar the last table slope is extrapolated with a floor
#   (exposure that far past the limits is out of tested territory — treat
#   those numbers as "far too much", not as physiology).
# - OTU: pulmonary toxicity units, REPEX: dt * ((ppO2 - 0.5)/0.5)^0.83.


# NOAA single-exposure oxygen limits: (ppO2 bar, max minutes), ascending.
NOAA_CNS_LIMITS: tuple[tuple[float, float], ...] = (
    (0.6, 720.0),
    (0.7, 570.0),
    (0.8, 450.0),
    (0.9, 360.0),
    (1.0, 300.0),
    (1.1, 240.0),
    (1.2, 210.0),
    (1.3, 180.0),
    (1.4, 150.0),
    (1.5, 120.0),
    (1.6, 45.0),
)

_CNS_PPO2_FLOOR = 0.5
_OTU_PPO2_FLOOR = 0.5
# Slope of the last table interval (1.5 -> 1.6 bar: 120 -> 45 min).
_EXTRAPOLATION_SLOPE = (45.0 - 120.0) / 0.1
_MIN_LIMIT_MINUTES = 4.0


def _cns_limit_minutes(ppo2_bar: float) -> float | None:
    """NOAA limit at `ppo2_bar`, linearly interpolated; None below the floor."""
    if ppo2_bar <= _CNS_PPO2_FLOOR:
        return None
    first_ppo2, first_limit = NOAA_CNS_LIMITS[0]
    if ppo2_bar <= first_ppo2:
        return first_limit

    last_ppo2, last_limit = NOAA_CNS_LIMITS[-1]
    if ppo2_bar > last_ppo2:
        extrapolated = last_limit + _EXTRAPOLATION_SLOPE * (ppo2_bar - last_ppo2)
        return max(_MIN_LIMIT_MINUTES, extrapolated)

    for (lo_p, lo_lim), (hi_p, hi_lim) in zip(
        NOAA_CNS_LIMITS, NOAA_CNS_LIMITS[1:], strict=False
    ):
        if lo_p <= ppo2_bar <= hi_p:
            fraction = (ppo2_bar - lo_p) / (hi_p - lo_p)
            return lo_lim + (hi_lim - lo_lim) * fraction
    raise AssertionError("unreachable")  # table scan is exhaustive


def _iter_ppo2(
    segments: Iterable[DiveSegment], step: timedelta
) -> Iterable[tuple[float, float]]:
    """Yield (minutes, ppO2 bar) exposures: one per constant segment, midpoint
    sub-steps for depth-changing segments."""
    for segment in segments:
        minutes = segment.duration.total_seconds() / 60.0
        if minutes <= 0:
            continue
        if segment.start_pressure == segment.end_pressure:
            yield minutes, segment.gas.ppo2(segment.start_pressure).bar
            continue

        substeps = max(1, math.ceil(segment.duration / step))
        sub_minutes = minutes / substeps
        for i in range(substeps):
            midpoint = segment.pressure_at_fraction((i + 0.5) / substeps)
            yield sub_minutes, segment.gas.ppo2(midpoint).bar


def cns_percent(
    segments: Iterable[DiveSegment], *, step: timedelta = timedelta(seconds=10)
) -> float:
    """CNS oxygen-toxicity clock over `segments`, in percent (100 = NOAA limit)."""
    total = 0.0
    for minutes, ppo2 in _iter_ppo2(segments, step):
        limit = _cns_limit_minutes(ppo2)
        if limit is not None:
            total += minutes / limit
    return total * 100.0


def otu(
    segments: Iterable[DiveSegment], *, step: timedelta = timedelta(seconds=10)
) -> float:
    """Pulmonary oxygen-toxicity units (REPEX) accumulated over `segments`."""
    total = 0.0
    for minutes, ppo2 in _iter_ppo2(segments, step):
        if ppo2 > _OTU_PPO2_FLOOR:
            total += minutes * ((ppo2 - _OTU_PPO2_FLOOR) / 0.5) ** 0.83
    return total
