"""Ascent planner: compute the decompression schedule from a model state.

``plan_ascent`` is a pure function of (model state, position, gases,
config) → list of DiveSegments. It clones the model and never mutates the
caller's — the property that makes TTS/counterfactual queries safe.

Algorithm (standard staged-decompression loop):

1. From the current depth, find the shallowest reachable target — the
   surface, or the deepest required stop on the configured stop grid
   (``stop_increment_m``, cut off at ``last_stop_m``).
2. Ascend there at ``ascent_rate`` (integrating the ascent into the model).
3. At a stop: switch to the best deco gas (richest ppO2-safe mix from the
   gas plan), then wait in ``min_stop_time_s`` increments until the next
   shallower target clears.
4. Repeat until surfaced.

Gradient-factor models: the ceiling test for a target uses the GF
interpolated at that target's depth (GF-low anchored at the deepest stop of
*this* ascent, GF-high at the surface). Until the first stop is known the
conservative GF-low applies. Non-GF models (VPM-B) are asked for their plain
ceiling; note that VPM-B's Critical Volume Algorithm and Boyle compensation
are not applied yet — its schedules use the conservative pre-CVA gradients.
"""

from datetime import timedelta
from typing import Any

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.base import BaseDecoModel
from diveplan.models.buhlmann.model import BuhlmannModel
from diveplan.planning.gas_plan import GasPlan
from diveplan.utils.conversions import coerce_depth_to_pressure, coerce_gas

__all__ = ["plan_ascent", "AscentNotConvergingError"]

# Hard cap on planning loop iterations — a schedule requiring more stop time
# than this is a bug (or an unsurfaceable profile), not a dive plan.
_MAX_ITERATIONS = 100_000


class AscentNotConvergingError(RuntimeError):
    """The stop loop failed to clear the next target within the iteration cap."""


def _ceiling(
    model: BaseDecoModel[Any],
    target: Pressure,
    first_stop: Pressure | None,
) -> Pressure:
    """Model ceiling for an ascent-to-`target` test.

    GF models interpolate the gradient factor at the target depth once the
    first (deepest) stop is anchored; before that, and for non-GF models,
    the model's default (conservative) ceiling applies.
    """
    if isinstance(model, BuhlmannModel) and first_stop is not None:
        return model.get_ceiling(model.gradient.factor(target, first_stop))
    return model.get_ceiling()


def _next_targets(current: Pressure) -> list[Pressure]:
    """Candidate ascent targets from shallowest to deepest: the surface, then
    the stop grid from last_stop_m down to just above `current`."""
    planning = DiveConfig.current().planning
    targets = [Pressure.surface()]
    depth = planning.last_stop_m
    while Pressure.from_depth_m(depth) < current:
        targets.append(Pressure.from_depth_m(depth))
        depth += planning.stop_increment_m
    return targets


def plan_ascent(
    model: BaseDecoModel[Any],
    start_pressure: Pressure | str | float,
    gas: Gas | str,
    gas_plan: GasPlan | None = None,
    clock_offset: timedelta | float = timedelta(0),
) -> list[DiveSegment]:
    """Plan the decompression ascent from the given position and model state.

    Args:
        model: Deco model holding the tissue state at `start_pressure`.
            Cloned internally — the caller's instance is not touched.
        start_pressure: Current position — a Pressure, a "40 m"-style
            string, or bare metres.
        gas: Gas currently being breathed — a Gas or a name like "ean50".
        gas_plan: Gases available for switches during the ascent. Defaults
            to just the current gas.
        clock_offset: Dive runtime at which this ascent starts (minutes or
            timedelta). Stop departures are extended to whole multiples of
            ``min_stop_time_s`` on this clock — the dive-table convention
            (a stop ends at e.g. runtime 31:00, not 30:26), which keeps
            schedules comparable with planners like Subsurface. Pass the
            bottom runtime when planning a real dive; the default plans on
            an ascent-relative clock.

    Returns:
        Continuous segments from `start_pressure` to the surface: deco
        ascents, stops, and gas switches. Empty if already at the surface.

    Raises:
        AscentNotConvergingError: If stops fail to clear within the
            iteration cap (pathological state or misconfiguration).
    """
    planning = DiveConfig.current().planning
    gas_limits = DiveConfig.current().gas
    surface = Pressure.surface()

    start_pressure = coerce_depth_to_pressure(start_pressure)
    gas = coerce_gas(gas)
    if gas_plan is None:
        gas_plan = GasPlan([gas])
    if not isinstance(clock_offset, timedelta):
        clock_offset = timedelta(minutes=clock_offset)

    work = model.copy()
    current = start_pressure
    current_gas = gas
    first_stop: Pressure | None = None
    plan: list[DiveSegment] = []

    def runtime_now() -> timedelta:
        """Dive-clock runtime at the current end of the plan."""
        return clock_offset + sum((s.duration for s in plan), timedelta(0))

    def wait_duration() -> timedelta:
        """Wait until the next whole stop-time boundary on the dive clock."""
        increment = float(planning.min_stop_time_s)
        into_increment = runtime_now().total_seconds() % increment
        remaining = increment - into_increment
        # Already (numerically) on a boundary: wait a full increment.
        if remaining < 0.5:
            remaining += increment
        return timedelta(seconds=remaining)

    def integrate_and_append(segment: DiveSegment) -> None:
        """Advance the working model through `segment` and record it."""
        work.integrate_segment(segment)
        plan.append(segment)

    def ascend_to(target: Pressure) -> None:
        """Emit an ascent leg to `target`, merging continuation legs."""
        depth_change = current.depth_m - target.depth_m
        leg = DiveSegment(
            current,
            target,
            depth_change / planning.ascent_rate,
            current_gas,
            ascent_kind=SegmentKind.Ascent.DECO_ASCENT,
        )
        work.integrate_segment(leg)
        # Off-gassing during an ascent can clear the next target immediately;
        # fold such continuation legs into one segment instead of stacking
        # rate-identical back-to-back ascents.
        if plan and plan[-1].is_fully_continuous_with(leg):
            plan[-1] = plan[-1].merge_with(leg)
        else:
            plan.append(leg)

    def reachable(target: Pressure) -> bool:
        """Whether the ceiling permits ascending to `target` right now."""
        return _ceiling(work, target, first_stop) <= target

    for _ in range(_MAX_ITERATIONS):
        if current <= surface:
            return plan

        # Shallowest target we may ascend to right now.
        target = next((p for p in _next_targets(current) if reachable(p)), None)

        if target is not None:
            ascend_to(target)
            current = target
            if current <= surface:
                return plan
            continue

        # No target clears: `current` is a stop. The first (deepest) stop of
        # the ascent anchors GF-low for gradient-factor interpolation.
        if first_stop is None:
            first_stop = current

        best = gas_plan.best_gas_at(current)
        if best is not None and best != current_gas and best.fo2 > current_gas.fo2:
            switch = DiveSegment(
                current,
                current,
                gas_limits.gas_switch_minutes,
                best,
                constant_kind=SegmentKind.Constant.GAS_SWITCH,
            )
            if switch.duration > timedelta(0):
                integrate_and_append(switch)
            else:
                plan.append(switch)  # instant switch — nothing to integrate
            current_gas = best

        chunk = DiveSegment(
            current,
            current,
            wait_duration(),
            current_gas,
            constant_kind=SegmentKind.Constant.STOP,
        )
        work.integrate_segment(chunk)
        # Extend the previous stop segment instead of stacking 1-min chunks.
        if (
            plan
            and plan[-1].kind is SegmentKind.Constant.STOP
            and plan[-1].gas == current_gas
            and plan[-1].start_pressure == current
        ):
            plan[-1] = plan[-1].merge_with(chunk)
        else:
            plan.append(chunk)

    raise AscentNotConvergingError(
        f"Ascent from {start_pressure} did not surface within "
        f"{_MAX_ITERATIONS} planning iterations."
    )
