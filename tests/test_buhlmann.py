"""
Tests for diveplan.models.buhlmann (Gradient, Compartment, ZHL16C).

Physics checks are property-based against the Haldane/Bühlmann equations
rather than external dive-table vectors: half-time behaviour is exact,
GF interpolation endpoints are exact, and deco/no-deco outcomes use dives
far on either side of published ZHL-16C no-stop limits so the assertions
are robust to small implementation differences (integer surface pressure,
water-vapor constant).
"""

from datetime import timedelta

import pytest

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.buhlmann.common import (
    WATER_VAPOR_PRESSURE_MBAR,
    Compartment,
    Gradient,
)
from diveplan.models.buhlmann.model import BuhlmannModel, BuhlmannState
from diveplan.models.buhlmann.zhl16 import ZHL16C

AIR = Gas.air()
COMPARTMENT_COUNT = 16


def surface_equilibrium_n2_mbar() -> float:
    return (Pressure.surface().mbar - WATER_VAPOR_PRESSURE_MBAR) * 0.79


def make_compartment(**overrides) -> Compartment:
    """Compartment 1b of ZHL-16C unless overridden."""
    kwargs = dict(
        ht_n2=5.0, ht_he=1.88, a_n2=1.1696, a_he=1.6189, b_n2=0.5578, b_he=0.4770
    )
    kwargs.update(overrides)
    return Compartment(**kwargs)


# ------------------------------------------------------------------
# Gradient
# ------------------------------------------------------------------


class TestGradient:
    def test_validation(self):
        with pytest.raises(ValueError):
            Gradient(0, 0.85)
        with pytest.raises(ValueError):
            Gradient(0.3, -1)

    def test_gf_high_at_surface(self):
        gf = Gradient(0.3, 0.85)
        first_stop = Pressure.from_depth_m(9)
        assert gf.factor(Pressure.surface(), first_stop) == 0.85

    def test_gf_low_at_and_below_first_stop(self):
        gf = Gradient(0.3, 0.85)
        first_stop = Pressure.from_depth_m(9)
        assert gf.factor(first_stop, first_stop) == 0.3
        assert gf.factor(Pressure.from_depth_m(30), first_stop) == 0.3

    def test_linear_midpoint(self):
        gf = Gradient(0.3, 0.85)
        surface = Pressure.surface()
        first_stop = Pressure.from_depth_m(10)
        midpoint = Pressure(round((surface.mbar + first_stop.mbar) / 2))
        assert gf.factor(midpoint, first_stop) == pytest.approx(
            (0.3 + 0.85) / 2, abs=1e-3
        )

    def test_continuous_near_surface(self):
        # No jump between the surface value and a point just below it.
        gf = Gradient(0.3, 0.85)
        first_stop = Pressure.from_depth_m(9)
        just_below = Pressure(Pressure.surface().mbar + 10)  # ~10 cm deep
        assert gf.factor(just_below, first_stop) == pytest.approx(0.85, abs=0.01)

    def test_flat_pair(self):
        gf = Gradient(0.8, 0.8)
        assert gf.factor(Pressure.from_depth_m(5), Pressure.from_depth_m(9)) == 0.8

    def test_first_stop_at_surface_returns_gf_high(self):
        gf = Gradient(0.3, 0.85)
        below = Pressure.from_depth_m(1)
        assert gf.factor(below, Pressure.surface()) == 0.3  # >= first stop
        assert gf.factor(Pressure.surface(), Pressure.surface()) == 0.3

    def test_str(self):
        assert str(Gradient(0.3, 0.85)) == "GF 30/85"


# ------------------------------------------------------------------
# Compartment
# ------------------------------------------------------------------


class TestCompartmentState:
    def test_default_surface_equilibrium(self):
        c = make_compartment()
        assert c.tensions_mbar[0] == pytest.approx(surface_equilibrium_n2_mbar())
        assert c.tensions_mbar[1] == 0.0

    def test_explicit_initial_tensions(self):
        c = make_compartment(ppn2=Pressure(2000), pphe=Pressure(500))
        assert c.tensions_mbar == (2000.0, 500.0)

    def test_validation(self):
        with pytest.raises(ValueError):
            make_compartment(ht_n2=0)
        with pytest.raises(ValueError):
            make_compartment(b_n2=0)
        with pytest.raises(ValueError):
            make_compartment().set_tensions_mbar(-1, 0)

    def test_copy_is_independent(self):
        c = make_compartment()
        clone = c.copy()
        assert clone == c
        clone.integrate(Pressure.from_depth_m(30), AIR, timedelta(minutes=10))
        assert clone != c


class TestCompartmentIntegration:
    def test_half_time_is_exact(self):
        # After exactly one half-time at constant conditions, the tension
        # closes exactly half the gap to the alveolar pressure.
        c = make_compartment()
        start = c.tensions_mbar[0]
        depth = Pressure.from_depth_m(30)
        alveolar_n2 = (depth.mbar - WATER_VAPOR_PRESSURE_MBAR) * AIR.fn2

        c.integrate(depth, AIR, timedelta(minutes=5.0))  # ht_n2 = 5.0
        expected = start + (alveolar_n2 - start) * 0.5
        assert c.tensions_mbar[0] == pytest.approx(expected, rel=1e-9)

    def test_integration_is_composable(self):
        # Two 5-minute steps must equal one 10-minute step (exponential decay
        # composes) — the property the segment integrator relies on.
        depth = Pressure.from_depth_m(40)
        one_step = make_compartment()
        two_steps = make_compartment()
        one_step.integrate(depth, AIR, timedelta(minutes=10))
        two_steps.integrate(depth, AIR, timedelta(minutes=5))
        two_steps.integrate(depth, AIR, timedelta(minutes=5))
        assert two_steps.tensions_mbar[0] == pytest.approx(
            one_step.tensions_mbar[0], rel=1e-9
        )

    def test_saturation_approaches_alveolar(self):
        c = make_compartment()
        depth = Pressure.from_depth_m(30)
        alveolar_n2 = (depth.mbar - WATER_VAPOR_PRESSURE_MBAR) * AIR.fn2
        c.integrate(depth, AIR, timedelta(minutes=5.0 * 20))  # 20 half-times
        assert c.tensions_mbar[0] == pytest.approx(alveolar_n2, rel=1e-5)

    def test_helium_loads_on_trimix(self):
        c = make_compartment()
        c.integrate(
            Pressure.from_depth_m(50), Gas.trimix(0.18, 0.45), timedelta(minutes=20)
        )
        assert c.tensions_mbar[1] > 1000  # substantial He uptake

    def test_slow_tissue_not_frozen_by_small_steps(self):
        # Regression guard for integer-quantization starvation: 1-second steps
        # on the slowest compartment must still accumulate tension.
        c = make_compartment(ht_n2=635.0, ht_he=240.03)
        start = c.tensions_mbar[0]
        depth = Pressure.from_depth_m(40)
        for _ in range(600):  # 10 minutes of 1 s steps
            c.integrate(depth, AIR, timedelta(seconds=1))
        assert c.tensions_mbar[0] > start + 10  # moved by whole mbars


class TestCompartmentToleratedPressure:
    def test_gf1_reduces_to_buhlmann(self):
        # Baker formula at GF=1 must equal the classic (P_t - a) * b.
        c = make_compartment(ppn2=Pressure(4000), pphe=Pressure(0))
        expected = (4000 - 1.1696 * 1000) * 0.5578
        assert c.tolerated_ambient_pressure(1.0).mbar == pytest.approx(
            expected, abs=1.0
        )

    def test_lower_gf_is_more_conservative(self):
        # Lower GF allows less supersaturation → deeper ceiling (higher
        # tolerated ambient pressure). At GF→0 the ceiling approaches the
        # tissue tension itself.
        c = make_compartment(ppn2=Pressure(4000))
        assert c.tolerated_ambient_pressure(0.3) > c.tolerated_ambient_pressure(1.0)
        assert c.tolerated_ambient_pressure(0.001).mbar == pytest.approx(4000, abs=5)

    def test_surface_equilibrium_needs_no_deco(self):
        c = make_compartment()
        assert c.tolerated_ambient_pressure(1.0) < Pressure.surface()

    def test_desaturated_compartment_clamps_to_zero(self):
        c = make_compartment(ppn2=Pressure(0), pphe=Pressure(0))
        assert c.tolerated_ambient_pressure(1.0) == Pressure(0)

    def test_gf_validation(self):
        with pytest.raises(ValueError):
            make_compartment().tolerated_ambient_pressure(0)


# ------------------------------------------------------------------
# ZHL16C
# ------------------------------------------------------------------


class TestZHL16CTables:
    def test_table_shapes(self):
        for table in (
            ZHL16C.N2_HALF_TIMES,
            ZHL16C.N2_A,
            ZHL16C.N2_B,
            ZHL16C.HE_HALF_TIMES,
        ):
            assert len(table) == COMPARTMENT_COUNT
        assert ZHL16C().compartment_count == COMPARTMENT_COUNT

    def test_half_times_monotonic(self):
        assert list(ZHL16C.N2_HALF_TIMES) == sorted(ZHL16C.N2_HALF_TIMES)
        assert list(ZHL16C.HE_HALF_TIMES) == sorted(ZHL16C.HE_HALF_TIMES)

    def test_b_coefficients_bounded(self):
        assert all(0 < b < 1 for b in ZHL16C.N2_B)


class TestZHL16CModel:
    def test_fresh_model_has_no_ceiling(self):
        model = ZHL16C()
        assert model.get_ceiling() < Pressure.surface()

    def test_sample_rate_from_config(self):
        DiveConfig.current().planning.sample_rate_s = 4
        assert ZHL16C().sample_rate_seconds == 4

    def test_no_deco_short_shallow_dive(self):
        # 12 m for 10 min on air is far inside any no-stop limit.
        model = ZHL16C()
        segment = DiveSegment(
            Pressure.from_depth_m(12), Pressure.from_depth_m(12), 10, AIR
        )
        model.integrate_segment(segment)
        assert model.get_ceiling() <= Pressure.surface()

    def test_deco_required_after_long_deep_dive(self):
        # 40 m for 30 min on air is far beyond the no-stop limit (~9 min).
        model = ZHL16C()
        segment = DiveSegment(
            Pressure.from_depth_m(40), Pressure.from_depth_m(40), 30, AIR
        )
        model.integrate_segment(segment)
        assert model.get_ceiling() > Pressure.surface()

    def test_lower_gf_raises_ceiling(self):
        bottom = DiveSegment(
            Pressure.from_depth_m(40), Pressure.from_depth_m(40), 30, AIR
        )
        model = ZHL16C()
        model.integrate_segment(bottom)
        assert model.get_ceiling(0.3) > model.get_ceiling(1.0)

    def test_integrate_segment_returns_state(self):
        model = ZHL16C()
        state = model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(20), Pressure.from_depth_m(20), 5, AIR)
        )
        assert isinstance(state, BuhlmannState)
        assert len(state.tissues) == COMPARTMENT_COUNT

    def test_fast_compartment_leads_on_short_exposure(self):
        model = ZHL16C()
        state = model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(30), Pressure.from_depth_m(30), 5, AIR)
        )
        assert state.tissues[0][0] > state.tissues[-1][0]

    def test_state_snapshot_restore_round_trip(self):
        model = ZHL16C()
        state = model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(30), Pressure.from_depth_m(30), 15, AIR)
        )
        restored = ZHL16C()
        restored.set_state(state)
        assert restored._get_deco_state() == state
        assert restored.get_ceiling() == model.get_ceiling()

    def test_copy_supports_counterfactuals(self):
        model = ZHL16C(gradient=Gradient(0.3, 0.85))
        model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(40), Pressure.from_depth_m(40), 20, AIR)
        )
        before = model._get_deco_state()
        clone = model.copy()
        clone.integrate_segment(  # hypothetical extra bottom time
            DiveSegment(Pressure.from_depth_m(40), Pressure.from_depth_m(40), 20, AIR)
        )
        assert model._get_deco_state() == before  # original undisturbed
        assert clone._get_deco_state() != before

    def test_state_immutability(self):
        state = ZHL16C()._get_deco_state()
        with pytest.raises(AttributeError, match="immutable"):
            state.tissues = ()

    def test_empty_state_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            BuhlmannState(())

    def test_set_state_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="1 compartments.*16"):
            ZHL16C().set_state(BuhlmannState(((750.0, 0.0),)))


# ------------------------------------------------------------------
# Bühlmann family (engine/table separation)
# ------------------------------------------------------------------


class MiniBuhlmann(BuhlmannModel):
    """Two-compartment toy variant — proves models are table-only subclasses."""

    NAME = "mini"
    N2_HALF_TIMES = (5.0, 635.0)
    N2_A = (1.1696, 0.2327)
    N2_B = (0.5578, 0.9653)
    HE_HALF_TIMES = (1.88, 240.03)
    HE_A = (1.6189, 0.5119)
    HE_B = (0.4770, 0.9267)

    __slots__ = ()


class TestBuhlmannFamily:
    def test_engine_is_abstract(self):
        with pytest.raises(TypeError, match="abstract engine"):
            BuhlmannModel()

    def test_variant_is_table_only(self):
        model = MiniBuhlmann()
        assert model.compartment_count == 2
        state = model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(30), Pressure.from_depth_m(30), 10, AIR)
        )
        assert len(state.tissues) == 2
        assert model.get_ceiling() < Pressure.surface()

    def test_mismatched_tables_rejected_at_class_definition(self):
        with pytest.raises(TypeError, match="mismatched lengths"):

            class Broken(BuhlmannModel):
                NAME = "broken"
                N2_HALF_TIMES = (5.0, 8.0)
                N2_A = (1.1696,)  # wrong length
                N2_B = (0.5578, 0.6514)
                HE_HALF_TIMES = (1.88, 3.02)
                HE_A = (1.6189, 1.3830)
                HE_B = (0.4770, 0.5747)

    def test_partial_tables_rejected_at_class_definition(self):
        with pytest.raises(TypeError, match="missing"):

            class Incomplete(BuhlmannModel):
                NAME = "incomplete"
                N2_HALF_TIMES = (5.0,)

    def test_copy_preserves_subclass(self):
        clone = MiniBuhlmann(gradient=Gradient(0.4, 0.9)).copy()
        assert type(clone) is MiniBuhlmann
        assert clone.gradient == Gradient(0.4, 0.9)


class TestZHL16CRegistry:
    def test_discoverable_via_entry_point(self):
        from diveplan.registry import PluginRegistry

        fresh = PluginRegistry()  # bypass the module singleton's cache
        assert fresh.model("zhl16c") is ZHL16C

    def test_default_model_config_matches(self):
        assert DiveConfig.current().planning.default_model == "zhl16c"
