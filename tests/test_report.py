"""
Tests for gas consumption, rock bottom, CNS/OTU, TTS variations, DiveReport,
and the formatters.

Consumption and rock bottom are checked against hand-computed arithmetic
(they are closed-form). CNS uses the exact NOAA table nodes (45 min at
ppO2 1.6 = 100 %); OTU uses the exact identity that ppO2 1.0 accrues one
unit per minute. Formatters are checked structurally (parseable, right
fields), not against golden strings.
"""

import json as jsonlib
from datetime import timedelta
from xml.etree import ElementTree

import pytest

from diveplan.core.config import DiveConfig
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.dive.dive_profile import DiveProfile
from diveplan.dive.dive_report import DiveReport
from diveplan.dive.dive_result import DiveResult, TtsVariations
from diveplan.dive.formatters import (
    ConsoleFormatter,
    JsonFormatter,
    SubsurfaceXmlFormatter,
)
from diveplan.dive.oxygen import cns_percent, otu
from diveplan.models.buhlmann.common import Gradient
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.planning.ascent_plan import plan_ascent
from diveplan.planning.gas_plan import GasPlan, gas_consumption, rock_bottom

AIR = Gas.air()
EAN50 = Gas.nitrox(0.50)


def two_atm() -> Pressure:
    """Ambient pressure of exactly 2 atm under the current config."""
    return Pressure.from_atm(2.0)


# ------------------------------------------------------------------
# Gas consumption
# ------------------------------------------------------------------


class TestGasConsumption:
    def test_bottom_segment_exact(self):
        # 10 min at exactly 2 atm, bottom SAC 20 L/min -> 400 L.
        seg = DiveSegment(two_atm(), two_atm(), 10, AIR)
        assert gas_consumption([seg]) == {AIR: pytest.approx(400.0)}

    def test_deco_kinds_use_deco_sac(self):
        DiveConfig.current().gas.sac_deco = 10.0
        stop = DiveSegment(
            two_atm(), two_atm(), 10, AIR, constant_kind=SegmentKind.Constant.STOP
        )
        assert gas_consumption([stop]) == {AIR: pytest.approx(200.0)}

    def test_linear_traverse_uses_mean_pressure(self):
        # Descent 1 atm -> 3 atm over 5 min: mean 2 atm, SAC 20 -> 200 L.
        seg = DiveSegment(Pressure.from_atm(1.0), Pressure.from_atm(3.0), 5, AIR)
        assert gas_consumption([seg])[AIR] == pytest.approx(200.0, rel=1e-3)

    def test_totals_split_per_gas(self):
        a = DiveSegment(two_atm(), two_atm(), 10, AIR)
        b = DiveSegment(
            two_atm(), two_atm(), 5, EAN50, constant_kind=SegmentKind.Constant.STOP
        )
        totals = gas_consumption([a, b])
        assert set(totals) == {AIR, EAN50}
        assert totals[AIR] == pytest.approx(400.0)
        assert totals[EAN50] == pytest.approx(150.0)  # deco SAC 15 by default


# ------------------------------------------------------------------
# Rock bottom
# ------------------------------------------------------------------


class TestRockBottom:
    def test_hand_computed(self):
        # Defaults: SAC 20, factor 2, 2 divers, 1 min solving, ascent 9 m/min.
        cfg = DiveConfig.current()
        depth = Pressure.from_depth_m(30)
        stressed = 20.0 * 2.0 * 2  # 80 L/min
        # Use the quantized pressure's own depth — from_depth_m rounds to
        # integer mbar, so "30 m" is not exactly 30.0 m coming back.
        expected = stressed * depth.atm * 1.0 + stressed * ((depth.atm + 1.0) / 2.0) * (
            depth.depth_m / cfg.planning.ascent_rate
        )
        assert rock_bottom("30 m") == pytest.approx(expected)

    def test_monotonic_with_depth(self):
        assert rock_bottom(40) > rock_bottom(30) > rock_bottom(20)

    def test_scales_with_config(self):
        base = rock_bottom(30)
        DiveConfig.current().gas.sac_factor = 4.0
        assert rock_bottom(30) == pytest.approx(base * 2.0)

    def test_divers_validation(self):
        with pytest.raises(ValueError):
            rock_bottom(30, divers=0)

    def test_zero_at_surface_with_no_solving_time(self):
        DiveConfig.current().gas.problem_solving_minutes = 0.0
        assert rock_bottom(Pressure.surface()) == pytest.approx(0.0)


# ------------------------------------------------------------------
# CNS / OTU
# ------------------------------------------------------------------


def segment_at_ppo2(ppo2_bar: float, minutes: float, gas: Gas = AIR) -> DiveSegment:
    """Constant-depth segment where `gas` gives exactly `ppo2_bar`."""
    pressure = Pressure.from_bar(ppo2_bar / gas.fo2)
    return DiveSegment(pressure, pressure, minutes, gas)


class TestOxygenExposure:
    def test_cns_100_percent_at_table_node(self):
        # NOAA: 45 min at ppO2 1.6 is exactly the single-exposure limit.
        seg = segment_at_ppo2(1.6, 45, EAN50)
        assert cns_percent([seg]) == pytest.approx(100.0, rel=1e-3)

    def test_cns_zero_below_floor(self):
        seg = segment_at_ppo2(0.4, 60)
        assert cns_percent([seg]) == 0.0

    def test_cns_interpolates_between_nodes(self):
        # ppO2 1.45 -> limit between 150 (1.4) and 120 (1.5) = 135 min.
        seg = segment_at_ppo2(1.45, 135, EAN50)
        assert cns_percent([seg]) == pytest.approx(100.0, rel=5e-3)

    def test_cns_additive_over_segments(self):
        half = segment_at_ppo2(1.6, 22.5, EAN50)
        assert cns_percent([half, half]) == pytest.approx(100.0, rel=1e-3)

    def test_otu_unit_rate_at_ppo2_one(self):
        # ((1.0 - 0.5)/0.5)^0.83 = 1 -> one OTU per minute.
        seg = segment_at_ppo2(1.0, 30)
        assert otu([seg]) == pytest.approx(30.0, rel=1e-6)

    def test_otu_zero_below_floor(self):
        assert otu([segment_at_ppo2(0.5, 60)]) == 0.0

    def test_changing_depth_integrates(self):
        # Descent through varying ppO2 accrues something between the
        # endpoint rates.
        start, end = Pressure.from_bar(1.0 / 0.21), Pressure.from_bar(1.4 / 0.21)
        seg = DiveSegment(start, end, 10, AIR)
        accrued = otu([seg])
        assert 10.0 < accrued < 10.0 * ((1.4 - 0.5) / 0.5) ** 0.83


# ------------------------------------------------------------------
# TTS variations
# ------------------------------------------------------------------


class TestTtsVariations:
    def test_deco_dive_variations_positive_and_sane(self):
        bottom = DiveProfile().descend_to("40 m").stay(25)
        result = DiveResult.run(bottom, ZHL16C(gradient=Gradient(0.3, 0.7)))
        variations = result.tts_variations(GasPlan([AIR, EAN50]))
        assert variations.per_meter >= timedelta(0)
        assert variations.per_minute > timedelta(0)
        assert variations.per_meter < timedelta(minutes=10)
        assert variations.per_minute < timedelta(minutes=10)


# ------------------------------------------------------------------
# DiveReport + formatters
# ------------------------------------------------------------------


def full_dive_report() -> DiveReport:
    bottom = DiveProfile().descend_to("40 m").stay(25)
    gases = GasPlan([AIR, EAN50])
    model = ZHL16C(gradient=Gradient(0.3, 0.7))
    bottom_result = DiveResult.run(bottom, model)

    end = bottom.runtime
    ascent = plan_ascent(
        bottom_result.model_at(end),
        start_pressure=bottom.pressure_at(end),
        gas=bottom.gas_at(end),
        gas_plan=gases,
        clock_offset=end,
    )
    full = bottom.copy()
    full.add_segments(ascent)
    full_result = DiveResult.run(full, model)
    return DiveReport.from_result(
        full_result, tts_variations=bottom_result.tts_variations(gases)
    )


class TestDiveReport:
    def test_fields(self):
        report = full_dive_report()
        assert report.model_name == "zhl16c"
        assert report.max_depth == Pressure.from_depth_m(40)
        assert report.runtime == report.rows[-1].runtime
        assert len(report.rows) == report.profile.segment_count
        assert {g for g, _ in report.consumption_l} == {AIR, EAN50}
        assert all(litres > 0 for _, litres in report.consumption_l)
        assert 0 < report.cns < 100
        assert report.otus > 0
        assert report.rock_bottom_l == pytest.approx(rock_bottom(40), rel=1e-6)
        assert isinstance(report.tts_variations, TtsVariations)

    def test_console_formatter(self):
        text = ConsoleFormatter().format(full_dive_report())
        assert "zhl16c" in text
        assert "switch to EAN50" in text
        assert "CNS" in text and "OTU" in text
        assert "rock bottom" in text
        assert "TTS variation" in text

    def test_json_formatter_round_trips(self):
        document = jsonlib.loads(JsonFormatter().format(full_dive_report()))
        assert document["model"] == "zhl16c"
        assert document["max_depth_m"] == pytest.approx(40.0, abs=0.1)
        assert document["segments"][0]["kind"] == "DESCENT"
        assert document["consumption_l"]["EAN50"] > 0
        assert document["cns_percent"] > 0
        assert document["tts_variations"]["per_minute_s"] > 0

    def test_subsurface_formatter_structure(self):
        xml = SubsurfaceXmlFormatter().format(full_dive_report())
        root = ElementTree.fromstring(xml)
        assert root.tag == "divelog"
        dive = root.find("./dives/dive")
        assert dive is not None
        cylinders = dive.findall("cylinder")
        assert [c.get("o2") for c in cylinders] == ["21.0%", "50.0%"]
        computer = dive.find("divecomputer")
        assert computer is not None
        samples = computer.findall("sample")
        assert len(samples) > 100  # 10 s grid over ~1 h
        events = computer.findall("event")
        assert any(e.get("name") == "gaschange" for e in events)
        depth = computer.find("depth")
        assert depth is not None and depth.get("max") == "40.0 m"
