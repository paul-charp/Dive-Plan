"""
Tests for diveplan.planning (GasPlan, plan_ascent).

Planner checks are structural properties every valid schedule must satisfy:
segments are continuous from the start pressure to the surface, stops sit on
the configured grid and get monotonically shallower, the model's ceiling is
respected at every stop departure, and lower gradient factors produce longer
schedules. No external dive-table vectors — those depend on implementation
details (rounding, min stop time) that vary between planners.
"""

from datetime import timedelta

import pytest

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile, ProfileBuilderPolicy
from diveplan.models.buhlmann.common import Gradient
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.models.vpm.model import VpmB
from diveplan.planning.ascent_plan import plan_ascent
from diveplan.planning.gas_plan import GasPlan

AIR = Gas.air()
EAN50 = Gas.nitrox(0.50)
OXYGEN = Gas.oxygen()


def loaded_model(depth_m: float, minutes: float, gradient: Gradient) -> ZHL16C:
    model = ZHL16C(gradient=gradient)
    p = Pressure.from_depth_m(depth_m)
    model.integrate_segment(DiveSegment(Pressure.surface(), p, depth_m / 20, AIR))
    model.integrate_segment(DiveSegment(p, p, minutes, AIR))
    return model


def total_time(plan: list[DiveSegment]) -> timedelta:
    return sum((s.duration for s in plan), timedelta(0))


# ------------------------------------------------------------------
# GasPlan
# ------------------------------------------------------------------


class TestGasPlan:
    def test_needs_a_gas(self):
        with pytest.raises(ValueError):
            GasPlan([])

    def test_deduplicates_preserving_order(self):
        plan = GasPlan([AIR, EAN50, AIR])
        assert plan.gases == (AIR, EAN50)

    def test_accepts_gas_names(self):
        assert GasPlan(["air", "ean50"]).gases == (AIR, EAN50)
        assert GasPlan(["tx21/35", AIR]).gases == (Gas.trimix(0.21, 0.35), AIR)

    def test_breathability_window(self):
        # EAN50 at 21 m: ppO2 ≈ 1.56 bar — inside the 1.6 deco limit.
        assert GasPlan.is_breathable(EAN50, Pressure.from_depth_m(21))
        # EAN50 at 30 m: ppO2 ≈ 2.0 bar — out.
        assert not GasPlan.is_breathable(EAN50, Pressure.from_depth_m(30))
        # Air at the surface is fine; oxygen at 30 m is not.
        assert GasPlan.is_breathable(AIR, Pressure.surface())
        assert not GasPlan.is_breathable(OXYGEN, Pressure.from_depth_m(30))

    def test_hypoxic_floor(self):
        trimix_10_70 = Gas.trimix(0.10, 0.70)
        assert not GasPlan.is_breathable(trimix_10_70, Pressure.surface())

    def test_best_gas_picks_richest_usable(self):
        plan = GasPlan([AIR, EAN50, OXYGEN])
        assert plan.best_gas_at(Pressure.from_depth_m(21)) == EAN50
        assert plan.best_gas_at(Pressure.from_depth_m(3)) == OXYGEN
        assert plan.best_gas_at(Pressure.from_depth_m(35)) == AIR

    def test_best_gas_none_when_nothing_usable(self):
        plan = GasPlan([OXYGEN])
        assert plan.best_gas_at(Pressure.from_depth_m(35)) is None

    def test_limits_read_from_config(self):
        DiveConfig.current().gas.deco_ppo2_bar = 1.4
        assert not GasPlan.is_breathable(EAN50, Pressure.from_depth_m(21))


# ------------------------------------------------------------------
# plan_ascent
# ------------------------------------------------------------------


def assert_plan_well_formed(
    plan: list[DiveSegment], start: Pressure, planning_cfg=None
) -> None:
    """Structural invariants every ascent plan must satisfy."""
    planning = planning_cfg or DiveConfig.current().planning
    assert plan, "plan must not be empty"
    assert plan[0].start_pressure == start
    assert plan[-1].end_pressure == Pressure.surface()

    # Continuous, monotonically shallower (constant segments hold depth).
    # (validate_profile needs >= 2 segments; a direct ascent is one.)
    if len(plan) >= 2:
        profile = DiveProfile(ProfileBuilderPolicy.ALLOW_BAD_PROFILE)
        profile.add_segments(plan)
        assert profile.validate_profile() == ()
    depths = [s.start_pressure for s in plan]
    assert all(a >= b for a, b in zip(depths, depths[1:], strict=False))

    # Stops sit on the configured grid, at or below the last-stop depth.
    for segment in plan:
        if segment.kind is SegmentKind.Constant.STOP:
            depth = segment.start_pressure.depth_m
            assert depth >= planning.last_stop_m - 0.01
            remainder = depth % planning.stop_increment_m
            assert min(remainder, planning.stop_increment_m - remainder) < 0.05


class TestPlanAscentNoDeco:
    def test_direct_ascent_when_no_ceiling(self):
        model = loaded_model(12, 10, Gradient(1.0, 1.0))
        plan = plan_ascent(model, Pressure.from_depth_m(12), AIR)
        assert_plan_well_formed(plan, Pressure.from_depth_m(12))
        assert len(plan) == 1
        assert plan[0].kind is SegmentKind.Ascent.DECO_ASCENT

    def test_already_at_surface(self):
        plan = plan_ascent(ZHL16C(), Pressure.surface(), AIR)
        assert plan == []

    def test_friendly_argument_coercion(self):
        # Depths as "12 m" strings, gases by name — like the fluent builders.
        model = loaded_model(12, 10, Gradient(1.0, 1.0))
        plan = plan_ascent(model, "12 m", "air")
        assert plan[0].start_pressure == Pressure.from_depth_m(12)
        assert plan[0].gas == AIR

    def test_input_model_not_mutated(self):
        model = loaded_model(40, 25, Gradient(0.3, 0.7))
        before = model.get_state()
        plan_ascent(model, Pressure.from_depth_m(40), AIR)
        assert model.get_state() == before


class TestPlanAscentDeco:
    def test_deco_schedule_structure(self):
        model = loaded_model(40, 25, Gradient(0.3, 0.7))
        plan = plan_ascent(model, Pressure.from_depth_m(40), AIR)
        assert_plan_well_formed(plan, Pressure.from_depth_m(40))
        stops = [s for s in plan if s.kind is SegmentKind.Constant.STOP]
        assert stops, "a 25 min dive at 40 m on air must require stops"
        # Consecutive same-depth stop chunks are merged into one segment.
        stop_depths = [s.start_pressure for s in stops]
        assert len(stop_depths) == len(set(stop_depths))

    def test_ceiling_respected_at_every_waypoint(self):
        # Re-run the plan through an independent model: after each segment,
        # the diver must never be shallower than the ceiling prevailing at
        # that moment (continuation ascents make departure-time checks too
        # strict — off-gassing en route is what clears the next target).
        gradient = Gradient(0.3, 0.7)
        model = loaded_model(40, 25, gradient)
        plan = plan_ascent(model, Pressure.from_depth_m(40), AIR)

        first_stop = next(
            (s.start_pressure for s in plan if s.kind is SegmentKind.Constant.STOP),
            None,
        )
        verify = model.copy()
        for segment in plan:
            verify.integrate_segment(segment)
            here = segment.end_pressure
            gf = (
                gradient.factor(here, first_stop)
                if first_stop is not None
                else gradient.gf_low
            )
            assert verify.get_ceiling(gf) <= here

    def test_lower_gf_longer_schedule(self):
        conservative = plan_ascent(
            loaded_model(40, 25, Gradient(0.3, 0.7)), Pressure.from_depth_m(40), AIR
        )
        liberal = plan_ascent(
            loaded_model(40, 25, Gradient(0.9, 0.9)), Pressure.from_depth_m(40), AIR
        )
        assert total_time(conservative) > total_time(liberal)

    def test_deco_gas_shortens_schedule_and_switches_at_stop(self):
        gases = GasPlan([AIR, EAN50])
        air_only = plan_ascent(
            loaded_model(40, 25, Gradient(0.3, 0.7)), Pressure.from_depth_m(40), AIR
        )
        with_deco_gas = plan_ascent(
            loaded_model(40, 25, Gradient(0.3, 0.7)),
            Pressure.from_depth_m(40),
            AIR,
            gas_plan=gases,
        )
        assert total_time(with_deco_gas) < total_time(air_only)

        switches = [
            s for s in with_deco_gas if s.kind is SegmentKind.Constant.GAS_SWITCH
        ]
        assert len(switches) == 1
        assert switches[0].gas == EAN50
        # Switch must happen where EAN50 is breathable (≤ ~21 m).
        assert GasPlan.is_breathable(EAN50, switches[0].start_pressure)
        assert_plan_well_formed(with_deco_gas, Pressure.from_depth_m(40))

    def test_stop_departures_align_to_dive_clock(self):
        # Dive-table convention (matches Subsurface): stops are extended so
        # that departures land on whole min_stop_time boundaries of the dive
        # clock, even though ascent legs arrive at fractional times.
        bottom_runtime = timedelta(minutes=27)
        model = loaded_model(40, 25, Gradient(0.3, 0.7))
        plan = plan_ascent(
            model,
            Pressure.from_depth_m(40),
            AIR,
            gas_plan=GasPlan([AIR, EAN50]),
            clock_offset=bottom_runtime,
        )
        elapsed = bottom_runtime
        for segment in plan:
            elapsed += segment.duration
            if segment.kind is SegmentKind.Constant.STOP:
                departure_s = elapsed.total_seconds()
                assert (
                    departure_s % 60 == pytest.approx(0, abs=0.51)
                    or (60 - departure_s % 60) < 0.51
                )

    def test_vpm_plan_terminates_and_is_well_formed(self):
        model = VpmB()
        p30 = Pressure.from_depth_m(30)
        model.integrate_segment(DiveSegment(Pressure.surface(), p30, 1.5, AIR))
        model.integrate_segment(DiveSegment(p30, p30, 12, AIR))
        plan = plan_ascent(model, p30, AIR)
        assert_plan_well_formed(plan, p30)
        assert any(s.kind is SegmentKind.Constant.STOP for s in plan)
