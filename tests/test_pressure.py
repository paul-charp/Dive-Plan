"""
tests/core/test_pressure.py
"""

from unittest.mock import MagicMock, patch

import pytest

from diveplan.core.pressure import Pressure

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def make_physics(surface_mbar: int = 1013, pressure_per_meter: float = 100.6625):
    """Returns a mock _PhysicsConfig with the two fields depth conversion needs."""
    m = MagicMock()
    m.surface_pressure_mbar = surface_mbar
    m.pressure_per_meter_mbar = pressure_per_meter
    return m


def mock_config(physics):
    """Patches DiveConfig.current().physics for depth conversion tests."""
    cfg = MagicMock()
    cfg.physics = physics
    return patch("diveplan.core.pressure.DiveConfig.current", return_value=cfg)


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------


class TestConstruction:
    def test_from_mbar_int(self):
        assert Pressure(1013).mbar == 1013

    def test_from_bar(self):
        assert Pressure.from_bar(1.013).mbar == 1013

    def test_from_bar_rounds(self):
        assert Pressure.from_bar(1.0001).mbar == 1000

    def test_from_mbar_float_rounds(self):
        assert Pressure.from_mbar(1013.6).mbar == 1014

    def test_zero_is_valid(self):
        assert Pressure(0).mbar == 0

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            Pressure(-1)

    def test_negative_float_raises(self):
        with pytest.raises(ValueError):
            Pressure.from_mbar(-0.1)

    def test_from_depth_m(self):
        physics = make_physics(surface_mbar=1013, pressure_per_meter=100.6625)
        with mock_config(physics):
            p = Pressure.from_depth_m(30.0)
        assert p.mbar == round(1013 + 30.0 * 100.6625)

    def test_from_depth_m_zero(self):
        physics = make_physics(surface_mbar=1013)
        with mock_config(physics):
            p = Pressure.from_depth_m(0.0)
        assert p.mbar == 1013

    def test_from_depth_m_altitude(self):
        physics = make_physics(surface_mbar=800, pressure_per_meter=100.6625)
        with mock_config(physics):
            p = Pressure.from_depth_m(30.0)
        assert p.mbar == round(800 + 30.0 * 100.6625)

    def test_from_depth_m_fresh_water(self):
        # fresh water: density 1.0 → pressure_per_meter ≈ 98.0665
        physics = make_physics(surface_mbar=1013, pressure_per_meter=98.0665)
        with mock_config(physics):
            p = Pressure.from_depth_m(30.0)
        assert p.mbar == round(1013 + 30.0 * 98.0665)


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------


class TestProperties:
    def test_mbar(self):
        assert Pressure(4013).mbar == 4013

    def test_bar(self):
        assert Pressure(4013).bar == pytest.approx(4.013)

    def test_bar_roundtrip(self):
        p = Pressure.from_bar(1.6)
        assert p.bar == pytest.approx(1.6)

    def test_depth_m(self):
        physics = make_physics(surface_mbar=1013, pressure_per_meter=100.6625)
        p = Pressure(round(1013 + 30.0 * 100.6625))
        with mock_config(physics):
            assert p.depth_m == pytest.approx(30.0, abs=0.01)

    def test_depth_m_surface(self):
        physics = make_physics(surface_mbar=1013, pressure_per_meter=100.6625)
        with mock_config(physics):
            assert Pressure(1013).depth_m == pytest.approx(0.0)

    def test_depth_m_roundtrip(self):
        physics = make_physics(surface_mbar=1013, pressure_per_meter=100.6625)
        with mock_config(physics):
            p = Pressure.from_depth_m(40.0)
            assert p.depth_m == pytest.approx(40.0, abs=0.01)

    def test_depth_m_altitude_config(self):
        physics = make_physics(surface_mbar=800, pressure_per_meter=100.6625)
        with mock_config(physics):
            p = Pressure.from_depth_m(30.0)
            assert p.depth_m == pytest.approx(30.0, abs=0.01)


# ------------------------------------------------------------------
# Alternate constructors & unit properties (real factory config)
# ------------------------------------------------------------------


class TestAltConstructorsAndProperties:
    def test_surface(self):
        assert Pressure.surface().mbar == 1013

    def test_from_atm(self):
        assert Pressure.from_atm(2.0).mbar == 2026

    def test_atm_property(self):
        assert Pressure(2026).atm == pytest.approx(2.0)

    def test_from_psi_value(self):
        # 1 atm ≈ 14.696 psi ≈ 1013 mbar
        assert Pressure.from_psi(14.696).mbar == pytest.approx(1013, abs=1)

    def test_psi_property(self):
        # absolute psi, not just round-trippable: 1013 mbar ≈ 14.7 psi
        assert Pressure(1013).psi == pytest.approx(14.7, abs=0.05)

    def test_psi_roundtrip(self):
        assert Pressure.from_psi(32.0).psi == pytest.approx(32.0, abs=0.05)

    def test_is_surface_true(self):
        assert Pressure(1013).is_surface is True
        assert Pressure(900).is_surface is True

    def test_is_surface_false(self):
        assert Pressure(2000).is_surface is False

    def test_depth_ft_roundtrip(self):
        assert Pressure.from_depth_ft(100.0).depth_ft == pytest.approx(100.0, abs=0.1)


# ------------------------------------------------------------------
# String parsing & formatting
# ------------------------------------------------------------------


class TestStringParsing:
    @pytest.mark.parametrize(
        "text, expected_mbar",
        [
            ("4.013 bar", 4013),
            ("4013 mbar", 4013),
            ("1 atm", 1013),
            ("0 m", 1013),
        ],
    )
    def test_from_str_units(self, text, expected_mbar):
        assert Pressure.from_str(text).mbar == expected_mbar

    def test_from_str_is_case_insensitive(self):
        assert Pressure.from_str("4.013 BAR") == Pressure(4013)

    def test_from_str_depth_uses_config(self):
        # 30 m at factory salt water ≈ 1013 + 30 * 100.518
        assert Pressure.from_str("30 m") == Pressure.from_depth_m(30)

    def test_from_str_invalid_unit_raises(self):
        with pytest.raises(ValueError, match="Invalid pressure string"):
            Pressure.from_str("30 kelvin")

    def test_from_str_invalid_number_raises(self):
        with pytest.raises(ValueError, match="Invalid pressure string"):
            Pressure.from_str("abc bar")

    @pytest.mark.parametrize(
        "unit, expected",
        [
            ("bar", "4.013 bar"),
            ("mbar", "4013 mbar"),
            ("atm", "3.962 atm"),
        ],
    )
    def test_to_str_units(self, unit, expected):
        assert Pressure(4013).to_str(unit) == expected

    def test_to_str_invalid_unit_raises(self):
        with pytest.raises(ValueError, match="Unsupported unit"):
            Pressure(4013).to_str("kelvin")

    def test_bar_str_roundtrip(self):
        assert Pressure.from_str(Pressure(4013).to_str("bar")) == Pressure(4013)


# ------------------------------------------------------------------
# Immutability
# ------------------------------------------------------------------


class TestImmutability:
    def test_setattr_raises(self):
        p = Pressure(1013)
        with pytest.raises(AttributeError):
            p._mbar = 999  # type: ignore[misc]

    def test_delattr_raises(self):
        p = Pressure(1013)
        with pytest.raises(AttributeError):
            del p._mbar  # type: ignore[misc]


# ------------------------------------------------------------------
# Arithmetic
# ------------------------------------------------------------------


class TestAddition:
    def test_add_two_pressures(self):
        assert Pressure(1000) + Pressure(500) == Pressure(1500)

    def test_add_returns_pressure(self):
        assert isinstance(Pressure(100) + Pressure(200), Pressure)

    def test_add_unsupported_type(self):
        assert Pressure(100).__add__(42) is NotImplemented


class TestSubtraction:
    def test_sub_returns_int(self):
        result = Pressure(4013) - Pressure(1013)
        assert result == 3000
        assert isinstance(result, int)

    def test_sub_can_be_negative(self):
        result = Pressure(1013) - Pressure(4013)
        assert result == -3000

    def test_sub_equal(self):
        assert Pressure(1013) - Pressure(1013) == 0

    def test_sub_unsupported_type(self):
        assert Pressure(100).__sub__(42) is NotImplemented


class TestMultiplication:
    def test_mul_float(self):
        # ppO2 at 40m: ambient * o2_fraction
        assert Pressure(4000) * 0.21 == Pressure(840)

    def test_rmul_float(self):
        assert 0.21 * Pressure(4000) == Pressure(840)

    def test_mul_int(self):
        assert Pressure(1000) * 2 == Pressure(2000)

    def test_mul_negative_raises(self):
        with pytest.raises(ValueError):
            Pressure(1000) * -1

    def test_mul_unsupported_type(self):
        assert Pressure(100).__mul__("x") is NotImplemented


class TestDivision:
    def test_div_by_pressure_returns_float(self):
        result = Pressure(4000) / Pressure(2000)
        assert result == pytest.approx(2.0)
        assert isinstance(result, float)

    def test_div_by_scalar_returns_pressure(self):
        assert Pressure(4000) / 2.0 == Pressure(2000)

    def test_div_by_pressure_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Pressure(1000) / Pressure(0)

    def test_div_by_scalar_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Pressure(1000) / 0

    def test_div_unsupported_type(self):
        assert Pressure(100).__truediv__("x") is NotImplemented


# ------------------------------------------------------------------
# Ordering
# ------------------------------------------------------------------


class TestOrdering:
    def test_lt(self):
        assert Pressure(1000) < Pressure(2000)

    def test_gt(self):
        assert Pressure(2000) > Pressure(1000)

    def test_le_less(self):
        assert Pressure(999) <= Pressure(1000)

    def test_le_equal(self):
        assert Pressure(1000) <= Pressure(1000)

    def test_ge_greater(self):
        assert Pressure(1001) >= Pressure(1000)

    def test_ge_equal(self):
        assert Pressure(1000) >= Pressure(1000)

    def test_eq(self):
        assert Pressure(1013) == Pressure(1013)

    def test_ne(self):
        assert Pressure(1013) != Pressure(1014)

    def test_eq_unsupported_type(self):
        assert Pressure(1013).__eq__(1013) is NotImplemented

    def test_sortable(self):
        pressures = [Pressure(3000), Pressure(1000), Pressure(2000)]
        assert sorted(pressures) == [Pressure(1000), Pressure(2000), Pressure(3000)]


# ------------------------------------------------------------------
# Hashing
# ------------------------------------------------------------------


class TestHashing:
    def test_hashable(self):
        assert hash(Pressure(1013)) == hash(Pressure(1013))

    def test_usable_as_dict_key(self):
        d = {Pressure(1013): "surface"}
        assert d[Pressure(1013)] == "surface"

    def test_usable_in_set(self):
        s = {Pressure(1013), Pressure(1013), Pressure(2000)}
        assert len(s) == 2


# ------------------------------------------------------------------
# Display
# ------------------------------------------------------------------


class TestDisplay:
    def test_repr(self):
        assert repr(Pressure(4013)) == "Pressure(4013)"

    def test_str(self):
        assert str(Pressure(4013)) == "4.013 bar (4013 mbar)"

    def test_str_surface(self):
        assert str(Pressure(1013)) == "1.013 bar (1013 mbar)"
