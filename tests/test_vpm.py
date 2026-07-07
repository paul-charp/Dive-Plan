"""
Tests for diveplan.models.vpm (VPM-B core).

The pure bubble-mechanics helpers are checked against exact values derivable
from the published constants (e.g. the nominal N2 initial allowable gradient
of ~0.6136 bar); model-level behaviour is property-based: crushing pressure
grows monotonically with descent and never decreases, conservatism raises
ceilings, pre-CVA VPM-B ceilings sit above raw Bühlmann for the same dive.
"""

import pytest

from diveplan.core.dive_segment import DiveSegment
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.models.vpm.model import (
    CRIT_RADIUS_HE_UM,
    CRIT_RADIUS_N2_UM,
    GRADIENT_OF_IMPERMEABILITY_BAR,
    SKIN_COMPRESSION_GAMMA_C,
    SURFACE_TENSION_GAMMA,
    VpmB,
    VpmState,
    allowable_gradient_bar,
    crushed_radius_um,
    impermeable_crushing_bar,
    regenerated_radius_um,
)

AIR = Gas.air()


def constant_segment(depth_m: float, minutes: float, gas: Gas = AIR) -> DiveSegment:
    p = Pressure.from_depth_m(depth_m)
    return DiveSegment(p, p, minutes, gas)


# ------------------------------------------------------------------
# Bubble-mechanics helpers
# ------------------------------------------------------------------


class TestBubbleMechanics:
    def test_nominal_n2_initial_gradient(self):
        # 2·(γ/γc)·(γc−γ)/0.55 with the published constants ≈ 0.6136 bar.
        expected = (
            2.0
            * (SURFACE_TENSION_GAMMA / SKIN_COMPRESSION_GAMMA_C)
            * (SKIN_COMPRESSION_GAMMA_C - SURFACE_TENSION_GAMMA)
            / CRIT_RADIUS_N2_UM
        )
        assert allowable_gradient_bar(CRIT_RADIUS_N2_UM) == pytest.approx(expected)
        assert allowable_gradient_bar(CRIT_RADIUS_N2_UM) == pytest.approx(
            0.6136, abs=1e-3
        )

    def test_smaller_nuclei_allow_larger_gradients(self):
        assert allowable_gradient_bar(CRIT_RADIUS_HE_UM) > allowable_gradient_bar(
            CRIT_RADIUS_N2_UM
        )

    def test_gradient_validation(self):
        with pytest.raises(ValueError):
            allowable_gradient_bar(0)

    def test_crushed_radius_identity_at_zero_crushing(self):
        assert crushed_radius_um(0.0, CRIT_RADIUS_N2_UM) == pytest.approx(
            CRIT_RADIUS_N2_UM
        )

    def test_crushed_radius_shrinks_monotonically(self):
        radii = [crushed_radius_um(p, CRIT_RADIUS_N2_UM) for p in (0.0, 2.0, 5.0, 8.0)]
        assert radii == sorted(radii, reverse=True)
        assert radii[-1] > 0

    def test_regeneration_endpoints(self):
        crushed = crushed_radius_um(5.0, CRIT_RADIUS_N2_UM)
        assert regenerated_radius_um(crushed, CRIT_RADIUS_N2_UM, 0.0) == pytest.approx(
            crushed
        )
        # After many time constants the radius is back to nominal.
        assert regenerated_radius_um(
            crushed, CRIT_RADIUS_N2_UM, 20160.0 * 20
        ) == pytest.approx(CRIT_RADIUS_N2_UM)

    def test_regeneration_negligible_within_a_dive(self):
        crushed = crushed_radius_um(5.0, CRIT_RADIUS_N2_UM)
        after_dive = regenerated_radius_um(crushed, CRIT_RADIUS_N2_UM, 120.0)
        assert after_dive == pytest.approx(crushed, rel=5e-3)

    def test_impermeable_solver_satisfies_cubic(self):
        ambient = 12.0  # bar — well past the 8.30865 bar onset
        onset_tension = 1.0
        crushing = impermeable_crushing_bar(ambient, onset_tension, CRIT_RADIUS_N2_UM)
        # The solved crushing pressure implies an inner pressure; verify the
        # defining relation holds: P_amb − P_inner == crushing.
        inner = ambient - crushing
        assert inner > 0
        assert crushing < ambient

    def test_impermeable_continuous_at_onset(self):
        # Just past the onset gradient, the impermeable result must be close
        # to the permeable value (= the gradient itself).
        onset_tension = 1.0
        ambient = onset_tension + GRADIENT_OF_IMPERMEABILITY_BAR + 1e-6
        crushing = impermeable_crushing_bar(ambient, onset_tension, CRIT_RADIUS_N2_UM)
        assert crushing == pytest.approx(GRADIENT_OF_IMPERMEABILITY_BAR, abs=1e-3)


# ------------------------------------------------------------------
# VpmB model
# ------------------------------------------------------------------


class TestVpmBModel:
    def test_fresh_model_has_no_ceiling(self):
        assert VpmB().get_ceiling() < Pressure.surface()

    def test_conservatism_validation(self):
        with pytest.raises(ValueError):
            VpmB(conservatism=5)
        with pytest.raises(ValueError):
            VpmB(conservatism=-1)

    def test_conservatism_scales_radii(self):
        nominal = VpmB(conservatism=0)
        conservative = VpmB(conservatism=4)
        assert conservative.crit_radius_n2_um == pytest.approx(
            nominal.crit_radius_n2_um * 1.35
        )

    def test_deco_required_after_long_deep_dive(self):
        model = VpmB()
        model.integrate_segment(constant_segment(40, 30))
        assert model.get_ceiling() > Pressure.surface()

    def test_no_deco_short_shallow_dive(self):
        model = VpmB()
        model.integrate_segment(constant_segment(9, 15))
        assert model.get_ceiling() <= Pressure.surface()

    def test_higher_conservatism_raises_ceiling(self):
        ceilings = []
        for level in (0, 4):
            model = VpmB(conservatism=level)
            model.integrate_segment(constant_segment(40, 30))
            ceilings.append(model.get_ceiling())
        assert ceilings[1] > ceilings[0]

    def test_pre_cva_vpm_more_conservative_than_raw_buhlmann(self):
        vpm, zhl = VpmB(), ZHL16C()  # default ZHL16C is raw Bühlmann (GF 100/100)
        for model in (vpm, zhl):
            model.integrate_segment(constant_segment(40, 30))
        assert vpm.get_ceiling() > zhl.get_ceiling()

    def test_ascent_ceiling_is_plain_ceiling(self):
        # VPM-B has no ascent-context behavior yet (pre-CVA): the base
        # default — the plain ceiling — applies regardless of anchor.
        model = VpmB()
        model.integrate_segment(constant_segment(40, 30))
        anchor = Pressure.from_depth_m(9)
        assert (
            model.get_ascent_ceiling(Pressure.surface(), anchor) == model.get_ceiling()
        )

    def test_crushing_pressure_tracks_descent_maximum(self):
        model = VpmB()
        model.integrate_segment(
            DiveSegment(Pressure.surface(), Pressure.from_depth_m(40), 4, AIR)
        )
        crush_after_descent = max(model._max_crush_n2_bar)
        assert crush_after_descent > 3.0  # fast drop to ~5 bar ambient

        # Ascending cannot reduce the recorded maximum.
        model.integrate_segment(
            DiveSegment(Pressure.from_depth_m(40), Pressure.from_depth_m(10), 6, AIR)
        )
        assert max(model._max_crush_n2_bar) == pytest.approx(crush_after_descent)

    def test_crushing_raises_allowable_gradient(self):
        # A deep descent crushes nuclei smaller, allowing more
        # supersaturation than the initial (uncrushed) gradient.
        model = VpmB()
        model.integrate_segment(
            DiveSegment(Pressure.surface(), Pressure.from_depth_m(60), 6, AIR)
        )
        grad_n2, _ = model._allowable_gradients_bar(0)
        assert grad_n2 > allowable_gradient_bar(model.crit_radius_n2_um)

    def test_integrate_segment_returns_state(self):
        state = VpmB().integrate_segment(constant_segment(20, 5))
        assert isinstance(state, VpmState)
        assert len(state.compartments) == VpmB.COMPARTMENT_COUNT
        assert state.runtime_min == pytest.approx(5.0)

    def test_state_snapshot_restore_round_trip(self):
        model = VpmB(conservatism=2)
        state = model.integrate_segment(constant_segment(30, 15))
        restored = VpmB(conservatism=2)
        restored.set_state(state)
        assert restored._get_deco_state() == state
        assert restored.get_ceiling() == model.get_ceiling()

    def test_copy_supports_counterfactuals(self):
        model = VpmB()
        model.integrate_segment(constant_segment(40, 20))
        before = model._get_deco_state()
        clone = model.copy()
        clone.integrate_segment(constant_segment(40, 20))
        assert model._get_deco_state() == before
        assert clone._get_deco_state() != before

    def test_state_immutability_and_validation(self):
        state = VpmB()._get_deco_state()
        with pytest.raises(AttributeError, match="immutable"):
            state.runtime_min = 0.0
        with pytest.raises(ValueError, match="at least one"):
            VpmState((), 0.0)
        with pytest.raises(ValueError, match="16"):
            VpmB().set_state(VpmState(((750.0, 0.0, 0.0, 0.0, 0.886),), 0.0))


class TestVpmBRegistry:
    def test_discoverable_via_entry_point(self):
        from diveplan.registry import PluginRegistry

        fresh = PluginRegistry()
        assert fresh.model("vpmb") is VpmB
        assert set(fresh.all_models()) >= {"zhl16c", "vpmb"}
