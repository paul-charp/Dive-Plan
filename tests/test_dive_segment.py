from datetime import timedelta

import pytest

from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

# ------------------------------------------------------------------
# Fixtures / Helpers
# ------------------------------------------------------------------


@pytest.fixture
def air():
    return Gas.air()


@pytest.fixture
def ean32():
    return Gas.nitrox(0.32)


@pytest.fixture
def p1000():
    return Pressure(1000)


@pytest.fixture
def p2000():
    return Pressure(2000)


@pytest.fixture
def p3000():
    return Pressure(3000)


@pytest.fixture
def p4000():
    return Pressure(4000)


def td(minutes=0, seconds=0):
    return timedelta(minutes=minutes, seconds=seconds)


# ------------------------------------------------------------------
# Construction & Kinds
# ------------------------------------------------------------------


class TestDiveSegmentConstruction:
    def test_descent_kind(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        assert seg.kind == SegmentKind.DESCENT
        assert seg.duration == td(minutes=2)

    def test_ascent_kind_default(self, p3000, p1000, air):
        seg = DiveSegment(p3000, p1000, 2, air)
        assert seg.kind == SegmentKind.ASCENT
        assert seg.kind == SegmentKind.Ascent.FORCED_ASCENT

    def test_ascent_kind_custom(self, p3000, p1000, air):
        seg = DiveSegment(
            p3000, p1000, 2, air, ascent_kind=SegmentKind.Ascent.DECO_ASCENT
        )
        assert seg.kind == SegmentKind.Ascent.DECO_ASCENT

    def test_constant_kind_default(self, p3000, air):
        seg = DiveSegment(p3000, p3000, 2, air)
        assert seg.kind == SegmentKind.CONSTANT
        assert seg.kind == SegmentKind.Constant.BOTTOM

    def test_constant_kind_custom(self, p3000, air):
        seg = DiveSegment(p3000, p3000, 2, air, constant_kind=SegmentKind.Constant.STOP)
        assert seg.kind == SegmentKind.Constant.STOP

    def test_timedelta_duration(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, timedelta(seconds=120), air)
        assert seg.duration == td(minutes=2)

    def test_zero_minutes_raises(self, p1000, p3000, air):
        with pytest.raises(ValueError, match="strictly positive"):
            DiveSegment(p1000, p3000, 0, air)

    def test_zero_timedelta_raises(self, p1000, p3000, air):
        with pytest.raises(ValueError, match="strictly positive"):
            DiveSegment(p1000, p3000, timedelta(0), air)

    def test_negative_duration_raises(self, p1000, p3000, air):
        with pytest.raises(ValueError, match="cannot be negative"):
            DiveSegment(p1000, p3000, -1, air)

    def test_split_at_boundary_raises(self, p1000, p3000, air):
        # Splitting at the very edge would produce a zero-duration traverse.
        seg = DiveSegment(p1000, p3000, 2, air)
        with pytest.raises(ValueError, match="strictly positive"):
            seg.split_at_fraction(0.0)

    def test_zero_duration_gas_switch_allowed(self, p2000, air):
        # A gas switch is a constant-depth boundary event — instant switches
        # (gas_switch_minutes = 0) are materialized as zero-duration segments.
        seg = DiveSegment(
            p2000, p2000, 0, air, constant_kind=SegmentKind.Constant.GAS_SWITCH
        )
        assert seg.duration == td()
        assert seg.kind is SegmentKind.Constant.GAS_SWITCH
        assert seg.pressure_rate == 0.0

    def test_zero_duration_non_switch_constant_raises(self, p2000, air):
        with pytest.raises(ValueError, match="strictly positive"):
            DiveSegment(p2000, p2000, 0, air)


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------


class TestDiveSegmentProperties:
    def test_average_pressure(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        assert seg.average_pressure == Pressure(2000)

    def test_absolute_pressure_change_descent(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        assert seg.absolute_pressure_change == Pressure(2000)

    def test_absolute_pressure_change_ascent(self, p3000, p1000, air):
        seg = DiveSegment(p3000, p1000, 2, air)
        assert seg.absolute_pressure_change == Pressure(2000)

    def test_pressure_rate_descent(self, p1000, p3000, air):
        # 2000 mbar / 120 seconds = 16.666...
        seg = DiveSegment(p1000, p3000, 2, air)
        assert seg.pressure_rate == pytest.approx(2000 / 120.0)

    def test_pressure_rate_ascent(self, p3000, p1000, air):
        seg = DiveSegment(p3000, p1000, 2, air)
        assert seg.pressure_rate == pytest.approx(-2000 / 120.0)

    def test_pressure_rate_constant(self, p3000, air):
        seg = DiveSegment(p3000, p3000, 2, air)
        assert seg.pressure_rate == 0.0


# ------------------------------------------------------------------
# Interpolation Methods
# ------------------------------------------------------------------


class TestDiveSegmentInterpolation:
    @pytest.fixture
    def descent(self, p1000, p3000, air):
        return DiveSegment(p1000, p3000, 2, air)

    def test_pressure_at_time(self, descent):
        assert descent.pressure_at_time(td(minutes=0)) == Pressure(1000)
        assert descent.pressure_at_time(td(minutes=1)) == Pressure(2000)
        assert descent.pressure_at_time(td(minutes=2)) == Pressure(3000)

    def test_pressure_at_time_out_of_bounds(self, descent):
        with pytest.raises(ValueError, match="outside segment duration"):
            descent.pressure_at_time(td(minutes=3))
        with pytest.raises(ValueError, match="outside segment duration"):
            descent.pressure_at_time(td(minutes=-1))

    def test_pressure_at_fraction(self, descent):
        assert descent.pressure_at_fraction(0.0) == Pressure(1000)
        assert descent.pressure_at_fraction(0.5) == Pressure(2000)
        assert descent.pressure_at_fraction(1.0) == Pressure(3000)

    def test_pressure_at_fraction_out_of_bounds(self, descent):
        with pytest.raises(ValueError, match="outside"):
            descent.pressure_at_fraction(-0.1)
        with pytest.raises(ValueError, match="outside"):
            descent.pressure_at_fraction(1.1)

    def test_time_at_pressure(self, descent):
        assert descent.time_at_pressure(Pressure(1000)) == td(minutes=0)
        assert descent.time_at_pressure(Pressure(2000)) == td(minutes=1)
        assert descent.time_at_pressure(Pressure(3000)) == td(minutes=2)

    def test_time_at_pressure_out_of_bounds(self, descent):
        with pytest.raises(ValueError, match="outside segment pressure range"):
            descent.time_at_pressure(Pressure(500))

    def test_time_at_pressure_constant_raises(self, p3000, air):
        seg = DiveSegment(p3000, p3000, 2, air)
        with pytest.raises(ValueError, match="undefined"):
            seg.time_at_pressure(p3000)

    def test_time_at_fraction(self, descent):
        assert descent.time_at_fraction(0.0) == td(minutes=0)
        assert descent.time_at_fraction(0.5) == td(minutes=1)
        assert descent.time_at_fraction(1.0) == td(minutes=2)

    def test_fraction_at_pressure(self, descent):
        assert descent.fraction_at_pressure(Pressure(1000)) == 0.0
        assert descent.fraction_at_pressure(Pressure(2000)) == 0.5
        assert descent.fraction_at_pressure(Pressure(3000)) == 1.0

    def test_fraction_at_pressure_constant_raises(self, p3000, air):
        seg = DiveSegment(p3000, p3000, 2, air)
        with pytest.raises(ValueError, match="undefined"):
            seg.fraction_at_pressure(p3000)

    def test_fraction_at_time(self, descent):
        assert descent.fraction_at_time(td(minutes=0)) == 0.0
        assert descent.fraction_at_time(td(minutes=1)) == 0.5
        assert descent.fraction_at_time(td(minutes=2)) == 1.0


# ------------------------------------------------------------------
# Splitting and Merging
# ------------------------------------------------------------------


class TestDiveSegmentSplitting:
    @pytest.fixture
    def seg(self, p1000, p3000, air):
        return DiveSegment(p1000, p3000, 2, air)

    def test_split_at_time(self, seg, p1000, p2000, p3000, air):
        a, b = seg.split_at_time(td(minutes=1))
        assert a == DiveSegment(p1000, p2000, 1, air)
        assert b == DiveSegment(p2000, p3000, 1, air)

    def test_split_at_fraction(self, seg, p1000, p2000, p3000, air):
        a, b = seg.split_at_fraction(0.5)
        assert a == DiveSegment(p1000, p2000, 1, air)
        assert b == DiveSegment(p2000, p3000, 1, air)


class TestDiveSegmentMerging:
    def test_merge_continuous(self, p1000, p2000, p3000, air):
        a = DiveSegment(p1000, p2000, 1, air)
        b = DiveSegment(p2000, p3000, 1, air)
        merged = a.merge_with(b)
        assert merged == DiveSegment(p1000, p3000, 2, air)

    def test_merge_not_continuous_raises(self, p1000, p2000, p3000, p4000, air, ean32):
        # Pressure mismatch
        a = DiveSegment(p1000, p2000, 1, air)
        b = DiveSegment(p3000, p4000, 1, air)
        with pytest.raises(ValueError, match="not fully continuous"):
            a.merge_with(b)

        # Gas mismatch
        b2 = DiveSegment(p2000, p3000, 1, ean32)
        with pytest.raises(ValueError, match="not fully continuous"):
            a.merge_with(b2)

        # Rate mismatch
        b3 = DiveSegment(p2000, p3000, 2, air)
        with pytest.raises(ValueError, match="not fully continuous"):
            a.merge_with(b3)

    def test_merge_force(self, p1000, p2000, p3000, p4000, air):
        a = DiveSegment(p1000, p2000, 1, air)
        b = DiveSegment(p3000, p4000, 2, air)
        merged = a.merge_with(b, force=True)
        assert merged == DiveSegment(p1000, p4000, 3, air)

    def test_merge_force_keeps_self_gas(self, p1000, p2000, p3000, air, ean32):
        # Documented limitation: force-merging across a gas change keeps
        # self.gas and silently discards other.gas.
        a = DiveSegment(p1000, p2000, 1, air)
        b = DiveSegment(p2000, p3000, 1, ean32)
        merged = a.merge_with(b, force=True)
        assert merged.gas == air


# ------------------------------------------------------------------
# Continuity
# ------------------------------------------------------------------


class TestDiveSegmentContinuity:
    @pytest.fixture
    def base(self, p1000, p2000, air):
        return DiveSegment(p1000, p2000, 1, air)

    def test_pressure_continuous(self, base, p2000, p3000, air):
        other = DiveSegment(p2000, p3000, 2, air)
        assert base.is_pressure_continuous_with(other)

    def test_pressure_not_continuous(self, base, p3000, p4000, air):
        other = DiveSegment(p3000, p4000, 2, air)
        assert not base.is_pressure_continuous_with(other)

    def test_gas_continuous(self, base, p2000, p3000, air):
        other = DiveSegment(p2000, p3000, 2, air)
        assert base.is_gas_continuous_with(other)

    def test_gas_not_continuous(self, base, p2000, p3000, ean32):
        other = DiveSegment(p2000, p3000, 2, ean32)
        assert not base.is_gas_continuous_with(other)

    def test_rate_continuous(self, base, p2000, p3000, air):
        other = DiveSegment(p2000, p3000, 1, air)
        assert base.is_rate_continuous_with(other)

    def test_rate_not_continuous(self, base, p2000, p3000, air):
        other = DiveSegment(p2000, p3000, 2, air)  # different rate
        assert not base.is_rate_continuous_with(other)

    def test_fully_continuous(self, base, p2000, p3000, air):
        other = DiveSegment(p2000, p3000, 1, air)
        assert base.is_fully_continuous_with(other)


# ------------------------------------------------------------------
# Iteration
# ------------------------------------------------------------------


class TestDiveSegmentIteration:
    def test_iter_pressures(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        pts = list(seg.iter_pressures(td(minutes=1)))
        assert len(pts) == 3
        assert pts[0] == (td(minutes=0), Pressure(1000))
        assert pts[1] == (td(minutes=1), Pressure(2000))
        assert pts[2] == (td(minutes=2), Pressure(3000))

    def test_iter_pressures_exclude_end(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        pts = list(seg.iter_pressures(td(minutes=1), include_end=False))
        assert len(pts) == 2
        assert pts[0] == (td(minutes=0), Pressure(1000))
        assert pts[1] == (td(minutes=1), Pressure(2000))

    def test_iter_pressures_non_matching_interval(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, td(seconds=45), air)
        pts = list(seg.iter_pressures(td(seconds=30)))
        assert len(pts) == 3
        assert pts[0] == (td(seconds=0), Pressure(1000))
        assert pts[1] == (
            td(seconds=30),
            Pressure(2333),
        )  # 1000 + 2000 * (30/45) = 2333.33...
        assert pts[2] == (td(seconds=45), Pressure(3000))


# ------------------------------------------------------------------
# Magic Methods
# ------------------------------------------------------------------


class TestDiveSegmentMagicMethods:
    def test_equality(self, p1000, p3000, air, ean32):
        seg1 = DiveSegment(p1000, p3000, 2, air)
        seg2 = DiveSegment(p1000, p3000, 2, air)
        seg3 = DiveSegment(p1000, p3000, 2, ean32)

        assert seg1 == seg2
        assert seg1 != seg3
        assert seg1 != "not a segment"

    def test_hash(self, p1000, p3000, air):
        seg1 = DiveSegment(p1000, p3000, 2, air)
        seg2 = DiveSegment(p1000, p3000, 2, air)
        assert hash(seg1) == hash(seg2)
        assert len({seg1, seg2}) == 1

    def test_repr(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        rep = repr(seg)
        assert "DiveSegment" in rep
        assert "start_pressure=Pressure(1000)" in rep
        assert "duration=0:02:00" in rep

    def test_str_constant(self, p1000, air):
        seg = DiveSegment(p1000, p1000, 2, air)
        s = str(seg)
        assert "BOTTOM segment at 1.000 bar (1000 mbar)" in s

    def test_str_moving(self, air):
        p1 = Pressure.from_depth_m(0)
        p2 = Pressure.from_depth_m(30)
        seg = DiveSegment(p1, p2, 3, air)
        s = str(seg)
        assert "DESCENT segment from 0.0m to 30.0m" in s


# ------------------------------------------------------------------
# Immutability
# ------------------------------------------------------------------


class TestDiveSegmentImmutability:
    def test_setattr_raises(self, p1000, p3000, air, ean32):
        seg = DiveSegment(p1000, p3000, 2, air)
        with pytest.raises(AttributeError, match="immutable"):
            seg.gas = ean32
        with pytest.raises(AttributeError, match="immutable"):
            seg.duration = td(minutes=99)

    def test_delattr_raises(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        with pytest.raises(AttributeError, match="immutable"):
            del seg.gas

    def test_hash_stable(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        assert hash(seg) == hash(DiveSegment(p1000, p3000, 2, air))


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


class TestDiveSegmentSerialization:
    def test_to_dict(self, p1000, p3000, air):
        seg = DiveSegment(p1000, p3000, 2, air)
        d = seg.to_dict()
        assert d["start_pressure_mbar"] == 1000
        assert d["end_pressure_mbar"] == 3000
        assert d["duration_s"] == 120.0
        assert d["gas"] == {"fo2": 0.21, "fhe": 0.0}
        assert d["kind"] == "DESCENT"

    @pytest.mark.parametrize(
        "make",
        [
            lambda p1000, p3000, air, ean32: DiveSegment(p1000, p3000, 2, air),
            lambda p1000, p3000, air, ean32: DiveSegment(
                p3000, p1000, 5, air, ascent_kind=SegmentKind.Ascent.DECO_ASCENT
            ),
            lambda p1000, p3000, air, ean32: DiveSegment(
                p3000, p3000, 3, air, constant_kind=SegmentKind.Constant.STOP
            ),
            lambda p1000, p3000, air, ean32: DiveSegment(
                p3000, p3000, 0, ean32, constant_kind=SegmentKind.Constant.GAS_SWITCH
            ),
        ],
        ids=["descent", "deco_ascent", "stop", "instant_gas_switch"],
    )
    def test_dict_round_trip(self, make, p1000, p3000, air, ean32):
        seg = make(p1000, p3000, air, ean32)
        assert DiveSegment.from_dict(seg.to_dict()) == seg

    def test_json_round_trip(self, p1000, p3000, ean32):
        seg = DiveSegment(p1000, p3000, 2, ean32)
        assert DiveSegment.from_json(seg.to_json()) == seg

    def test_from_dict_kind_geometry_mismatch(self, p1000, p3000, air):
        d = DiveSegment(p1000, p3000, 2, air).to_dict()
        d["kind"] = "DECO_ASCENT"  # but pressures describe a descent
        with pytest.raises(ValueError, match="contradicts pressure geometry"):
            DiveSegment.from_dict(d)

    def test_from_dict_unknown_kind(self, p1000, p3000, air):
        d = DiveSegment(p1000, p3000, 2, air).to_dict()
        d["kind"] = "SIDEWAYS"
        with pytest.raises(ValueError, match="Unknown segment kind"):
            DiveSegment.from_dict(d)

    def test_segment_kind_from_name(self):
        assert SegmentKind.from_name("descent") is SegmentKind.Descent.DESCENT
        assert SegmentKind.from_name("STOP") is SegmentKind.Constant.STOP
        assert SegmentKind.from_name("GAS_SWITCH") is SegmentKind.Constant.GAS_SWITCH
