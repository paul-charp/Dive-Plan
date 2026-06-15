"""
Tests for diveplan.dive.dive_profile.

Uses real DiveSegment / Pressure / Gas value objects rather than mocks: they
are cheap, and the conftest pins factory-default config so depth conversions
and ascent/descent rates are deterministic. This exercises the real continuity
logic instead of asserting against hand-wired mock return values.
"""

import pytest

from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import (
    DiveProfile,
    ProfileBuilderPolicy,
    ProfileDepthContinuityError,
    ProfileEmptyError,
    ProfileGasContinuityError,
    ProfileSimplicityError,
    ProfileStartEndError,
    ProfileTooShortError,
)

AIR = Gas.air()
EAN32 = Gas.nitrox(0.32)

SURF = Pressure.surface()
P1 = Pressure(1000)
P2 = Pressure(2000)
P3 = Pressure(3000)
P4 = Pressure(4000)

ALLOW = ProfileBuilderPolicy.ALLOW_BAD_PROFILE
RAISE = ProfileBuilderPolicy.RAISE_BAD_PROFILE
AUTOFIX = ProfileBuilderPolicy.AUTOFIX_BAD_PROFILE


def descent(start=SURF, end=P4, minutes=2, gas=AIR):
    return DiveSegment(start, end, minutes, gas)


def ascent(start=P4, end=SURF, minutes=5, gas=AIR):
    return DiveSegment(
        start, end, minutes, gas, ascent_kind=SegmentKind.Ascent.DECO_ASCENT
    )


def valid_profile(policy=ALLOW):
    """A minimal valid profile: surface → P4 → surface, continuous, not redundant."""
    p = DiveProfile(policy)
    p.add_segments([descent(), ascent()])
    return p


# ------------------------------------------------------------------
# Builder
# ------------------------------------------------------------------


class TestDiveProfileBuilder:
    def test_init_default_policy(self):
        profile = DiveProfile()
        assert profile.builder_policy is RAISE
        assert profile.segment_count == 0
        assert profile.is_valid is False  # empty profile is invalid

    def test_init_custom_policy(self):
        assert DiveProfile(ALLOW).builder_policy is ALLOW

    def test_copy(self):
        profile = valid_profile()
        copied = profile.copy()
        assert copied is not profile
        assert copied.builder_policy is profile.builder_policy
        assert copied.segments == profile.segments
        assert copied.segments is not profile.segments

    def test_copy_override_policy(self):
        copied = valid_profile(ALLOW).copy(override_policy=RAISE)
        assert copied.builder_policy is RAISE

    def test_add_segment_allow(self):
        profile = DiveProfile(ALLOW)
        seg = descent()
        profile.add_segment(seg)
        assert profile.segment_count == 1
        assert profile.get_segment(0) == seg

    def test_add_segment_raise_continuous_ok(self):
        profile = DiveProfile(RAISE)
        profile.add_segment(descent(SURF, P4))
        profile.add_segment(ascent(P4, SURF))
        assert profile.segment_count == 2

    def test_add_segment_raise_depth_discontinuity(self):
        profile = DiveProfile(RAISE)
        profile.add_segment(descent(SURF, P2))
        with pytest.raises(ProfileDepthContinuityError):
            profile.add_segment(descent(P3, P4))
        assert profile.segment_count == 1

    def test_add_segment_raise_gas_discontinuity(self):
        profile = DiveProfile(RAISE)
        profile.add_segment(descent(SURF, P2, gas=AIR))
        with pytest.raises(ProfileGasContinuityError):
            profile.add_segment(descent(P2, P4, gas=EAN32))
        assert profile.segment_count == 1

    def test_add_segment_raise_gas_switch_allowed(self):
        profile = DiveProfile(RAISE)
        profile.add_segment(descent(SURF, P2, gas=AIR))
        switch = DiveSegment(
            P2, P2, 1, EAN32, constant_kind=SegmentKind.Constant.GAS_SWITCH
        )
        profile.add_segment(switch)  # gas changes, but it is a GAS_SWITCH seam
        assert profile.segment_count == 2

    def test_add_segment_autofix_inserts_transition(self):
        profile = DiveProfile(AUTOFIX)
        profile.add_segment(descent(SURF, P2))
        profile.add_segment(descent(P3, P4))  # depth gap P2 → P3
        assert profile.segment_count == 3
        assert profile.get_segment(1).kind == SegmentKind.DESCENT  # transition

    def test_remove_interior_raise_breaks_continuity(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2), descent(P2, P3), ascent(P3, SURF)])
        profile._builder_policy = RAISE
        with pytest.raises(ProfileDepthContinuityError):
            profile.remove_segment_at_index(1)  # P2 → ... → P3 gap
        assert profile.segment_count == 3

    def test_remove_end_segment_allowed_under_raise(self):
        profile = valid_profile(RAISE)
        profile.remove_segment_at_index(profile.segment_count - 1)
        assert profile.segment_count == 1

    def test_remove_out_of_bounds(self):
        with pytest.raises(IndexError):
            DiveProfile(ALLOW).remove_segment_at_index(5)

    def test_replace_out_of_bounds(self):
        with pytest.raises(IndexError):
            DiveProfile(ALLOW).replace_segment_at_index(5, descent())

    def test_get_out_of_bounds(self):
        with pytest.raises(IndexError):
            DiveProfile(ALLOW).get_segment(0)

    def test_clear_profile(self):
        profile = valid_profile()
        profile.clear_profile()
        assert profile.segment_count == 0

    def test_remove_segment_at_indices(self):
        profile = DiveProfile(ALLOW)
        a, b, c = descent(SURF, P2), descent(P2, P3), ascent(P3, SURF)
        profile.add_segments([a, b, c])
        profile.remove_segment_at_indices([0, 2])
        assert profile.segment_count == 1
        assert profile.get_segment(0) == b

    def test_remove_segment_instance(self):
        profile = DiveProfile(ALLOW)
        seg = descent()
        profile.add_segment(seg)
        profile.remove_segment(seg)
        assert profile.segment_count == 0

    def test_remove_segments(self):
        profile = DiveProfile(ALLOW)
        a, b = descent(SURF, P2), ascent(P2, SURF)
        profile.add_segments([a, b])
        profile.remove_segments([a, b])
        assert profile.segment_count == 0

    def test_remove_last_segment(self):
        profile = DiveProfile(ALLOW)
        profile.add_segment(descent())
        profile.remove_last_segment()
        assert profile.segment_count == 0

    def test_insert_segments_at_index(self):
        profile = DiveProfile(ALLOW)
        a, b = descent(SURF, P2), ascent(P2, SURF)
        profile.add_segment(a)
        profile.insert_segments_at_index(0, [b])
        assert profile.get_segment(0) == b
        assert profile.get_segment(1) == a

    def test_get_first_last_segment(self):
        profile = valid_profile()
        assert profile.get_first_segment() == profile.get_segment(0)
        assert profile.get_last_segment() == profile.get_segment(-1)

    def test_last_pressure_and_gas_empty(self):
        profile = DiveProfile(ALLOW)
        assert profile._get_last_pressure() == SURF
        assert profile._get_last_gas() == AIR

    def test_last_pressure_and_gas(self):
        profile = DiveProfile(ALLOW)
        seg = descent(P1, P2)
        profile.add_segment(seg)
        assert profile._get_last_pressure() == seg.start_pressure
        assert profile._get_last_gas() == seg.gas


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestDiveProfileValidation:
    def test_valid_profile(self):
        assert valid_profile().is_valid is True

    def test_validate_empty_profile(self):
        errors = DiveProfile(ALLOW).validate_profile()
        assert len(errors) == 1
        assert isinstance(errors[0], ProfileEmptyError)
        assert errors[0].fixable is False

    def test_validate_too_short_profile(self):
        profile = DiveProfile(ALLOW)
        profile.add_segment(descent())
        errors = profile.validate_profile()
        assert len(errors) == 1
        assert isinstance(errors[0], ProfileTooShortError)
        assert errors[0].fixable is False

    def test_validate_start_end_surface_error(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(P1, P2), ascent(P2, P1)])
        errors = profile.validate_profile(skip_start_end_segments=False)
        assert any(isinstance(e, ProfileStartEndError) for e in errors)

    def test_start_end_not_checked_by_default(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(P1, P2), ascent(P2, P1)])
        errors = profile.validate_profile()
        assert not any(isinstance(e, ProfileStartEndError) for e in errors)

    def test_validate_depth_continuity_error(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2), descent(P3, P4)])
        errors = profile.validate_profile()
        err = next(e for e in errors if isinstance(e, ProfileDepthContinuityError))
        assert err.segment_index == 0
        assert err.fixable is True

    def test_validate_gas_continuity_error(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2, gas=AIR), descent(P2, P4, gas=EAN32)])
        errors = profile.validate_profile()
        assert any(isinstance(e, ProfileGasContinuityError) for e in errors)

    def test_gas_switch_seam_is_not_an_error(self):
        profile = DiveProfile(ALLOW)
        switch = DiveSegment(
            P2, P2, 1, EAN32, constant_kind=SegmentKind.Constant.GAS_SWITCH
        )
        profile.add_segments(
            [descent(SURF, P2, gas=AIR), switch, ascent(P2, SURF, gas=EAN32)]
        )
        assert not any(
            isinstance(e, ProfileGasContinuityError)
            for e in profile.validate_profile()
        )

    def test_validate_simplicity_error(self):
        profile = DiveProfile(ALLOW)
        # equal rate, same gas, pressure-continuous → fully continuous (mergeable)
        profile.add_segments([descent(P1, P2, 1), descent(P2, P3, 1)])
        errors = profile.validate_profile(skip_simplicity=False)
        assert any(isinstance(e, ProfileSimplicityError) for e in errors)

    def test_simplicity_skipped_by_default_in_is_valid(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(P1, P2, 1), descent(P2, P3, 1)])
        assert profile.is_valid is True  # simplicity not enforced by is_valid


# ------------------------------------------------------------------
# Repair
# ------------------------------------------------------------------


class TestDiveProfileFixes:
    def test_fix_depth_continuity_inserts_transition(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2), descent(P3, P4)])
        error = next(
            e
            for e in profile.validate_profile()
            if isinstance(e, ProfileDepthContinuityError)
        )
        profile.fix(error)
        assert profile.segment_count == 3
        # the inserted transition bridges P2 → P3
        assert profile.get_segment(1).start_pressure == P2
        assert profile.get_segment(1).end_pressure == P3

    def test_fix_gas_continuity_inserts_switch(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2, gas=AIR), descent(P2, P4, gas=EAN32)])
        error = next(
            e
            for e in profile.validate_profile()
            if isinstance(e, ProfileGasContinuityError)
        )
        profile.fix(error)
        assert profile.segment_count == 3
        assert profile.get_segment(1).kind is SegmentKind.Constant.GAS_SWITCH

    def test_fix_simplicity_merges(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(P1, P2, 1), descent(P2, P3, 1)])
        error = next(
            e
            for e in profile.validate_profile(skip_simplicity=False)
            if isinstance(e, ProfileSimplicityError)
        )
        profile.fix(error)
        assert profile.segment_count == 1
        assert profile.get_segment(0) == DiveSegment(P1, P3, 2, AIR)

    def test_fix_start_end_adds_surface(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(P2, P3), ascent(P3, P2)])
        error = next(
            e
            for e in profile.validate_profile(skip_start_end_segments=False)
            if isinstance(e, ProfileStartEndError)
        )
        profile.fix(error)
        assert profile.get_first_segment().start_pressure == SURF
        assert profile.get_last_segment().end_pressure == SURF

    def test_fix_non_fixable_raises(self):
        profile = DiveProfile(ALLOW)
        error = profile.validate_profile()[0]
        assert isinstance(error, ProfileEmptyError)
        with pytest.raises(ValueError, match="not auto-fixable"):
            profile.fix(error)

    def test_fix_all_converges_to_valid(self):
        profile = DiveProfile(ALLOW)
        # not at surface + gas discontinuity at a pressure-continuous seam
        profile.add_segments([descent(P2, P3, gas=AIR), ascent(P3, P2, gas=EAN32)])
        profile.fix_all()
        assert profile.is_valid is True
        assert profile.get_first_segment().start_pressure == SURF
        assert profile.get_last_segment().end_pressure == SURF
        assert profile.validate_profile(skip_start_end_segments=False) == ()

    def test_simplify_profile(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments(
            [descent(P1, P2, 1), descent(P2, P3, 1), ascent(P3, P1, 2)]
        )
        simplified = profile.simplify_profile()
        assert simplified.segment_count == 2
        assert simplified.get_segment(0) == DiveSegment(P1, P3, 2, AIR)

    def test_fix_continuity_inserts_transition(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2), descent(P3, P4)])
        profile.fix_continuity()
        assert profile.segment_count == 3
        assert profile.get_segment(0).end_pressure == P2
        assert profile.get_segment(2).start_pressure == P3

    def test_bulk_fix_gas_continuity_inserts_switch(self):
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2, gas=AIR), descent(P2, P4, gas=EAN32)])
        profile.fix_gas_continuity()
        assert profile.segment_count == 3
        assert profile.get_segment(1).kind is SegmentKind.Constant.GAS_SWITCH

    def test_add_surface_segments(self):
        profile = DiveProfile(ALLOW)
        profile.add_segment(descent(P2, P3))
        profile.add_surface_segments()
        assert profile.segment_count == 3
        assert profile.get_first_segment().start_pressure == SURF
        assert profile.get_last_segment().end_pressure == SURF

    def test_add_surface_segments_empty_raises(self):
        with pytest.raises(ProfileEmptyError):
            DiveProfile(ALLOW).add_surface_segments()

    def test_make_transition_segment_raises_when_continuous(self):
        a = descent(SURF, P2)
        b = descent(P2, P4)  # already pressure-continuous
        with pytest.raises(ValueError, match="already pressure-continuous"):
            DiveProfile.make_transition_segment(a, b)

    def test_make_transition_segment_allows_gas_mismatch(self):
        a = descent(SURF, P2, gas=AIR)
        b = descent(P3, P4, gas=EAN32)  # pressure gap + gas mismatch
        transition = DiveProfile.make_transition_segment(a, b)
        assert transition.start_pressure == P2
        assert transition.end_pressure == P3
        assert transition.gas == AIR  # carries segment_a's gas

    def test_make_gas_switch_segment_zero_time(self):
        # gas_switch_minutes = 0 → the switch is still materialized as a segment,
        # just with zero duration (instant switch).
        from datetime import timedelta

        from diveplan.core.config import DiveConfig

        DiveConfig.current().gas.gas_switch_minutes = 0
        switch = DiveProfile.make_gas_switch_segment(
            descent(SURF, P2, gas=AIR), descent(P2, P4, gas=EAN32)
        )
        assert switch.kind is SegmentKind.Constant.GAS_SWITCH
        assert switch.duration == timedelta(0)
        assert switch.gas == EAN32

    def test_fix_gas_continuity_zero_time(self):
        # An instant gas switch still materializes in the profile via fix().
        from diveplan.core.config import DiveConfig

        DiveConfig.current().gas.gas_switch_minutes = 0
        profile = DiveProfile(ALLOW)
        profile.add_segments([descent(SURF, P2, gas=AIR), descent(P2, P4, gas=EAN32)])
        error = next(
            e
            for e in profile.validate_profile()
            if isinstance(e, ProfileGasContinuityError)
        )
        profile.fix(error)
        assert profile.segment_count == 3
        assert profile.get_segment(1).kind is SegmentKind.Constant.GAS_SWITCH

    def test_make_gas_switch_segment_raises(self):
        a = descent(SURF, P2, gas=AIR)
        same_gas = descent(P2, P4, gas=AIR)
        with pytest.raises(ValueError, match="already gas continuous"):
            DiveProfile.make_gas_switch_segment(a, same_gas)

        pressure_gap = descent(P3, P4, gas=EAN32)
        with pytest.raises(ValueError, match="pressure discontinuity"):
            DiveProfile.make_gas_switch_segment(a, pressure_gap)
