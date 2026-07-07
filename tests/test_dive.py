"""
Tests for diveplan.dive.dive (Dive) (and DiveProfile.iter_samples).

Key invariants: iter_samples steps tile the runtime exactly and never cross
segment boundaries; running a model through iter_samples reproduces
integrate_segment (integration composes); checkpoint-based state_at(t) is
exact, not approximate; nothing mutates the caller's profile or model.
"""

from datetime import timedelta

import pytest

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile
from diveplan.dive.dive import Dive
from diveplan.models.buhlmann.common import Gradient
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.models.vpm.model import VpmB

AIR = Gas.air()


def simple_profile() -> DiveProfile:
    """Surface → 30 m → 20 min bottom → surface (all air, RAISE-valid)."""
    return DiveProfile().descend_to("30 m").stay(20).surface()


def switch_profile() -> DiveProfile:
    """Deco-style profile with a gas switch during the ascent."""
    return (
        DiveProfile()
        .descend_to("40 m")
        .stay(25)
        .ascend_to("21 m")
        .switch_gas("ean50")
        .stay(3)
        .surface()
    )


# ------------------------------------------------------------------
# DiveProfile.iter_samples
# ------------------------------------------------------------------


class TestIterSamples:
    def test_steps_tile_the_runtime(self):
        profile = switch_profile()
        samples = list(profile.iter_samples(timedelta(seconds=7)))  # awkward step
        total = sum((s.dt for s in samples), timedelta(0))
        assert total == profile.runtime
        assert samples[-1].time == profile.runtime

    def test_steps_never_cross_segment_boundaries(self):
        profile = switch_profile()
        for sample in profile.iter_samples(timedelta(seconds=7)):
            start = profile.start_time_of_segment(sample.segment_index)
            segment = profile.segments[sample.segment_index]
            assert start < sample.time <= start + segment.duration

    def test_boundaries_hit_exactly(self):
        profile = simple_profile()
        times = {s.time for s in profile.iter_samples(timedelta(seconds=13))}
        for i in range(profile.segment_count):
            assert (
                profile.start_time_of_segment(i) + profile.segments[i].duration
            ) in times

    def test_pressure_is_end_of_interval(self):
        profile = simple_profile()
        first = next(iter(profile.iter_samples(timedelta(seconds=30))))
        assert first.pressure == profile.segments[0].pressure_at_time(first.dt)

    def test_gas_follows_segments(self):
        profile = switch_profile()
        ean50 = Gas.from_name("ean50")
        gases = {s.gas for s in profile.iter_samples(1)}
        assert gases == {AIR, ean50}

    def test_zero_duration_switch_yields_no_step(self):
        from diveplan.core.config import DiveConfig

        DiveConfig.current().gas.gas_switch_minutes = 0
        profile = DiveProfile().descend_to("30 m").switch_gas("ean32")
        switch_index = profile.segment_count - 1
        assert all(s.segment_index != switch_index for s in profile.iter_samples(1))

    def test_interval_validation(self):
        with pytest.raises(ValueError, match="> 0"):
            list(simple_profile().iter_samples(0))

    def test_matches_integrate_segment(self):
        # Driving a model through iter_samples must equal the segment API.
        profile = switch_profile()
        via_segments = ZHL16C()
        for segment in profile.segments:
            via_segments.integrate_segment(segment)

        via_samples = ZHL16C()
        for sample in profile.iter_samples(
            timedelta(seconds=via_samples.sample_rate_seconds)
        ):
            via_samples.integrate(sample.pressure, sample.gas, sample.dt)

        for (n2_a, he_a), (n2_b, he_b) in zip(
            via_segments.get_state().tissues,
            via_samples.get_state().tissues,
            strict=True,
        ):
            assert n2_a == pytest.approx(n2_b, rel=1e-9)
            assert he_a == pytest.approx(he_b, rel=1e-9)


# ------------------------------------------------------------------
# Dive
# ------------------------------------------------------------------


class TestDiveRun:
    def test_checkpoint_shape(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        assert len(result.checkpoints) == profile.segment_count + 1
        assert result.checkpoints[0] == ZHL16C().get_state()  # pre-dive
        assert result.final_state == result.checkpoints[-1]

    def test_caller_model_and_profile_untouched(self):
        profile = simple_profile()
        model = ZHL16C()
        before = model.get_state()
        segment_count = profile.segment_count
        Dive.run(profile, model)
        assert model.get_state() == before
        assert profile.segment_count == segment_count

    def test_result_profile_is_a_copy(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        assert result.profile is not profile
        assert result.profile.segments == profile.segments

    def test_generic_over_models(self):
        profile = simple_profile()
        for model in (ZHL16C(gradient=Gradient(0.3, 0.85)), VpmB(conservatism=1)):
            result = Dive.run(profile, model)
            assert len(result.checkpoints) == profile.segment_count + 1


class TestDiveQueries:
    def test_state_at_boundaries_equals_checkpoints(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        assert result.state_at(0) == result.checkpoints[0]
        assert result.state_at(profile.runtime) == result.final_state

    def test_state_at_mid_segment_is_exact(self):
        # state_at re-integrates from the checkpoint; compare against a
        # model integrated directly to the same instant.
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        t = profile.start_time_of_segment(1) + timedelta(minutes=7)

        direct = ZHL16C()
        direct.integrate_segment(profile.segments[0])
        from diveplan.core.dive_segment import DiveSegment

        seg = profile.segments[1]
        direct.integrate_segment(
            DiveSegment(seg.start_pressure, seg.start_pressure, 7, seg.gas)
        )

        for (a_n2, a_he), (b_n2, b_he) in zip(
            result.state_at(t).tissues, direct.get_state().tissues, strict=True
        ):
            assert a_n2 == pytest.approx(b_n2, rel=1e-9)
            assert a_he == pytest.approx(b_he, rel=1e-9)

    def test_ceiling_rises_with_bottom_time(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        bottom_start = profile.start_time_of_segment(1)
        early = result.ceiling_at(bottom_start + timedelta(minutes=2))
        late = result.ceiling_at(bottom_start + timedelta(minutes=19))
        assert late > early

    def test_tissue_series_shape(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        series = list(result.tissue_series(timedelta(minutes=1)))
        assert series[0][0] == timedelta(0)
        assert series[0][1] == result.checkpoints[0]
        assert series[-1][0] == profile.runtime

    def test_tissue_series_matches_checkpoints_at_model_rate(self):
        # Sampled at the model's own rate, the series must land exactly on
        # the final checkpoint (the rectangle rule reproduces only at the
        # same step size — coarser sampling is approximate by design).
        profile = simple_profile()
        model = ZHL16C()
        result = Dive.run(profile, model)
        series = list(
            result.tissue_series(timedelta(seconds=model.sample_rate_seconds))
        )
        for (a_n2, a_he), (b_n2, b_he) in zip(
            series[-1][1].tissues, result.final_state.tissues, strict=True
        ):
            assert a_n2 == pytest.approx(b_n2, rel=1e-9)
            assert a_he == pytest.approx(b_he, rel=1e-9)

    def test_queries_do_not_mutate_result(self):
        profile = simple_profile()
        result = Dive.run(profile, ZHL16C())
        final_before = result.final_state
        result.state_at(5)
        result.ceiling_at(15)
        list(result.tissue_series(5))
        assert result.final_state == final_before

    def test_tts_no_deco_dive_is_ascent_time_only(self):
        from diveplan.core.config import DiveConfig

        profile = DiveProfile().descend_to("12 m").stay(10).surface()
        result = Dive.run(profile, ZHL16C())
        t = profile.start_time_of_segment(1) + timedelta(minutes=5)
        expected = timedelta(minutes=12 / DiveConfig.current().planning.ascent_rate)
        assert abs(result.tts(t) - expected) < timedelta(seconds=5)

    def test_tts_grows_with_bottom_time_on_deco_dive(self):
        profile = (
            DiveProfile(  # long deep bottom, air only
            )
            .descend_to("40 m")
            .stay(30)
            .surface()
        )
        result = Dive.run(profile, ZHL16C(gradient=Gradient(0.3, 0.7)))
        bottom_start = profile.start_time_of_segment(1)
        early = result.tts(bottom_start + timedelta(minutes=5))
        late = result.tts(bottom_start + timedelta(minutes=25))
        assert late > early
        assert late > timedelta(minutes=10)  # real deco obligation


# ------------------------------------------------------------------
# Continuing a dive: plan_ascent / extend / with_ascent
# ------------------------------------------------------------------


class TestDiveContinuation:
    def make_bottom_dive(self):
        from diveplan.planning.gas_plan import GasPlan

        bottom = DiveProfile().descend_to("40 m").stay(25)
        dive = Dive.run(bottom, ZHL16C(gradient=Gradient(0.3, 0.7)))
        return dive, GasPlan(["air", "ean50"])

    def test_plan_ascent_reaches_surface(self):
        dive, gases = self.make_bottom_dive()
        ascent = dive.plan_ascent(gases)
        assert ascent[0].start_pressure == Pressure.from_depth_m(40)
        assert ascent[-1].end_pressure == Pressure.surface()

    def test_extend_appends_and_reuses_checkpoints(self):
        dive, gases = self.make_bottom_dive()
        ascent = dive.plan_ascent(gases)
        full = dive.extend(ascent)

        # Original dive untouched; new dive covers everything.
        assert dive.profile.segment_count == 2
        assert full.profile.segment_count == 2 + len(ascent)
        assert len(full.checkpoints) == full.profile.segment_count + 1
        assert full.checkpoints[: len(dive.checkpoints)] == dive.checkpoints

    def test_extend_equivalent_to_fresh_run(self):
        dive, gases = self.make_bottom_dive()
        full = dive.with_ascent(gases)
        rerun = Dive.run(full.profile, ZHL16C(gradient=Gradient(0.3, 0.7)))
        for (a_n2, a_he), (b_n2, b_he) in zip(
            full.final_state.tissues, rerun.final_state.tissues, strict=True
        ):
            assert a_n2 == pytest.approx(b_n2, rel=1e-9)
            assert a_he == pytest.approx(b_he, rel=1e-9)

    def test_with_ascent_surfaces_clean(self):
        dive, gases = self.make_bottom_dive()
        full = dive.with_ascent(gases)
        assert full.profile.segments[-1].end_pressure == Pressure.surface()
        # At surfacing the GF-high ceiling must clear the surface (that is
        # the planner's criterion; get_ceiling() is the conservative GF-low
        # bound and legitimately does not). GF is instance configuration —
        # view the surfaced state through a GF 70/70 model.
        surfaced = full.model_at(full.profile.runtime)
        gf_high_view = ZHL16C(gradient=Gradient(0.7, 0.7))
        gf_high_view.set_state(surfaced.get_state())
        assert gf_high_view.get_ceiling() <= Pressure.surface()


# ------------------------------------------------------------------
# Oxygen-exposure time queries
# ------------------------------------------------------------------


class TestOxygenQueries:
    def make_dive(self):
        from diveplan.planning.gas_plan import GasPlan

        bottom = DiveProfile().descend_to("40 m").stay(25)
        dive = Dive.run(bottom, ZHL16C(gradient=Gradient(0.3, 0.7)))
        return dive.with_ascent(GasPlan(["air", "ean50"]))

    def test_zero_at_start(self):
        dive = self.make_dive()
        assert dive.cns_at(0) == 0.0
        assert dive.otu_at(0) == 0.0

    def test_monotonically_increasing(self):
        dive = self.make_dive()
        runtime = dive.profile.runtime
        times = [runtime * f for f in (0.25, 0.5, 0.75, 1.0)]
        cns_values = [dive.cns_at(t) for t in times]
        otu_values = [dive.otu_at(t) for t in times]
        assert cns_values == sorted(cns_values)
        assert otu_values == sorted(otu_values)
        assert cns_values[-1] > 0 and otu_values[-1] > 0

    def test_full_dive_matches_kernel_functions(self):
        from diveplan.planning.gas_plan import cns_percent, otu

        dive = self.make_dive()
        segments = dive.profile.segments
        assert dive.cns_at(dive.profile.runtime) == pytest.approx(
            cns_percent(segments), rel=1e-6
        )
        assert dive.otu_at(dive.profile.runtime) == pytest.approx(
            otu(segments), rel=1e-6
        )

    def test_partial_segment_is_truncated_exactly(self):
        dive = self.make_dive()
        bottom_start = dive.profile.start_time_of_segment(1)
        # Constant-depth bottom: exposure accrues linearly with time there.
        a = dive.cns_at(bottom_start + timedelta(minutes=10))
        b = dive.cns_at(bottom_start + timedelta(minutes=20))
        at_start = dive.cns_at(bottom_start)
        assert (b - at_start) == pytest.approx(2 * (a - at_start), rel=1e-6)
