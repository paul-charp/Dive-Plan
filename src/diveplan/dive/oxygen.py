"""Oxygen-exposure tracking: NOAA CNS clock and REPEX OTUs.

Both accumulate over any sequence of segments (a profile's or an ascent
plan's). Constant-depth segments are evaluated in closed form; segments with
changing depth are integrated numerically at midpoint ppO2 with a
configurable step.

- **CNS %** — fraction of the NOAA single-exposure oxygen limit consumed:
  ``Σ dt / limit(ppO2)``. Limits are linearly interpolated between the NOAA
  table nodes; below 0.5 bar ppO2 nothing accrues; above 1.6 bar the last
  table slope is extrapolated with a floor (exposure that far past the
  limits is out of tested territory — treat those numbers as "far too
  much", not as physiology).
- **OTU** — pulmonary (whole-body) toxicity units, REPEX formula:
  ``dt · ((ppO2 − 0.5)/0.5)^0.83`` per minute above 0.5 bar.
"""

import math
from collections.abc import Iterable
from datetime import timedelta

from diveplan.core.dive_segment import DiveSegment

__all__ = ["cns_percent", "otu", "NOAA_CNS_LIMITS"]

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
