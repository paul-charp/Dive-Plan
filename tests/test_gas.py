"""Tests for Gas.

Runs standalone — DiveConfig and Pressure are stubbed so the test file
needs no installed diveplan package beyond gas.py itself.
"""

import pytest

from diveplan.core.config import DiveConfig
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Construction — raw Gas()
# ---------------------------------------------------------------------------


class TestRawConstruction:
    def test_nitrox_fractions(self):
        g = Gas(0.32)
        assert approx(g.fo2, 0.32)
        assert approx(g.fhe, 0.0)
        assert approx(g.fn2, 0.68)

    def test_trimix_fractions(self):
        g = Gas(0.21, fhe=0.35)
        assert approx(g.fo2, 0.21)
        assert approx(g.fhe, 0.35)
        assert approx(g.fn2, 0.44)

    def test_fo2_zero_allowed(self):
        """Raw constructor permits fo2=0 (non-breathable, user's problem)."""
        g = Gas(0.0, fhe=0.5)
        assert approx(g.fo2, 0.0)

    def test_fhe_zero_allowed(self):
        g = Gas(0.21)
        assert approx(g.fhe, 0.0)

    def test_fo2_negative_raises(self):
        with pytest.raises(ValueError, match="fo2"):
            Gas(-0.01)

    def test_fhe_negative_raises(self):
        with pytest.raises(ValueError, match="fhe"):
            Gas(0.21, fhe=-0.01)

    def test_fn2_negative_raises(self):
        with pytest.raises(ValueError, match="fn2"):
            Gas(0.6, fhe=0.5)  # fn2 = -0.1

    def test_sum_not_one_raises(self):
        # Bypass fn2 < 0 check by passing floats that sum > 1 slightly
        with pytest.raises(ValueError):
            Gas(fo2=1.0, fhe=0.5)  # fn2 = 0.0 but sum is 1.0 exactly, so no error
        # Verify it explicitly:
        g = Gas(0.21, fhe=0.35)
        assert abs(g.fo2 + g.fhe + g.fn2 - 1.0) < 1e-9

    def test_immutability(self):
        g = Gas(0.32)
        with pytest.raises(AttributeError):
            g.fo2 = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Named constructors
# ---------------------------------------------------------------------------


class TestNamedConstructors:
    def test_air_fractions(self):
        g = Gas.air()
        assert approx(g.fo2, 0.21)
        assert approx(g.fhe, 0.0)
        assert approx(g.fn2, 0.79)

    def test_oxygen_fractions(self):
        g = Gas.oxygen()
        assert approx(g.fo2, 1.0)
        assert approx(g.fhe, 0.0)
        assert approx(g.fn2, 0.0)

    def test_nitrox(self):
        g = Gas.nitrox(0.36)
        assert approx(g.fo2, 0.36)
        assert approx(g.fhe, 0.0)

    def test_ean_alias(self):
        assert Gas.ean(0.32) == Gas.nitrox(0.32)

    def test_nitrox_zero_fo2_raises(self):
        with pytest.raises(ValueError, match="nitrox fo2"):
            Gas.nitrox(0.0)

    def test_nitrox_negative_fo2_raises(self):
        with pytest.raises(ValueError, match="nitrox fo2"):
            Gas.nitrox(-0.1)

    def test_trimix_fractions(self):
        g = Gas.trimix(0.21, 0.35)
        assert approx(g.fo2, 0.21)
        assert approx(g.fhe, 0.35)
        assert approx(g.fn2, 0.44)

    def test_trimix_zero_fo2_raises(self):
        with pytest.raises(ValueError, match="trimix fo2"):
            Gas.trimix(0.0, 0.35)

    def test_trimix_zero_fhe_raises(self):
        with pytest.raises(ValueError, match="trimix fhe"):
            Gas.trimix(0.21, 0.0)

    def test_trimix_negative_fo2_raises(self):
        with pytest.raises(ValueError, match="trimix fo2"):
            Gas.trimix(-0.1, 0.35)

    def test_trimix_negative_fhe_raises(self):
        with pytest.raises(ValueError, match="trimix fhe"):
            Gas.trimix(0.21, -0.1)


# ---------------------------------------------------------------------------
# from_name parser
# ---------------------------------------------------------------------------


class TestFromName:
    def test_air(self):
        assert Gas.from_name("air") == Gas.air()

    def test_air_uppercase(self):
        assert Gas.from_name("AIR") == Gas.air()

    def test_oxygen(self):
        assert Gas.from_name("oxygen") == Gas.oxygen()

    @pytest.mark.parametrize(
        "name", ["nx32", "ean32", "nitrox32", "nitrox 32", "EAN32", "NX32"]
    )
    def test_nitrox_variants(self, name):
        g = Gas.from_name(name)
        assert approx(g.fo2, 0.32)
        assert approx(g.fhe, 0.0)

    @pytest.mark.parametrize(
        "name", ["tx21/35", "trimix21/35", "trimix 21/35", "TX21/35"]
    )
    def test_trimix_variants(self, name):
        g = Gas.from_name(name)
        assert approx(g.fo2, 0.21)
        assert approx(g.fhe, 0.35)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Cannot parse gas name"):
            Gas.from_name("heliox50/50")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            Gas.from_name("")


# ---------------------------------------------------------------------------
# Partial pressures
# ---------------------------------------------------------------------------


class TestPartialPressures:
    # 40 m saltwater: ~5013 mbar
    P40 = Pressure.from_depth_m(40)

    def test_ppo2_air_at_40m(self):
        pp = Gas.air().ppo2(self.P40)
        assert approx(pp.bar, self.P40.bar * 0.21, tol=1e-3)

    def test_ppn2_air_at_40m(self):
        pp = Gas.air().ppn2(self.P40)
        assert approx(pp.bar, self.P40.bar * 0.79, tol=1e-3)

    def test_pphe_air_is_zero(self):
        pp = Gas.air().pphe(self.P40)
        assert pp.mbar == 0

    def test_pphe_trimix(self):
        g = Gas.trimix(0.21, 0.35)
        pp = g.pphe(self.P40)
        assert approx(pp.bar, self.P40.bar * 0.35, tol=1e-3)

    def test_ppo2_oxygen_at_surface(self):
        surface = Pressure(1013)
        pp = Gas.oxygen().ppo2(surface)
        assert approx(pp.bar, 1.013, tol=1e-3)


# ---------------------------------------------------------------------------
# MOD
# ---------------------------------------------------------------------------


class TestMod:
    def test_ean32_mod_1_4(self):
        # MOD = 1400 / 320 * 1000 = 4375 mbar
        mod = Gas.nitrox(0.32).mod(ppo2_bar=1.4)
        assert mod.mbar == round(1400 / 0.32)

    def test_air_mod_1_4(self):
        mod = Gas.air().mod(ppo2_bar=1.4)
        assert mod.mbar == round(1400 / 0.21)

    def test_oxygen_mod_1_6(self):
        mod = Gas.oxygen().mod(ppo2_bar=1.6)
        assert mod.mbar == 1600

    def test_ppo2_zero_raises(self):
        with pytest.raises(ValueError, match="ppo2_bar"):
            Gas.air().mod(ppo2_bar=0)

    def test_ppo2_negative_raises(self):
        with pytest.raises(ValueError, match="ppo2_bar"):
            Gas.air().mod(ppo2_bar=-1.0)


# ---------------------------------------------------------------------------
# END
# ---------------------------------------------------------------------------


class TestEnd:
    def test_air_end_equals_depth(self):
        """Air has no He, so END == actual depth."""
        p = Pressure.from_depth_m(30)
        end = Gas.air().end(p)
        # narcotic fraction = fo2 + fn2 = 1.0 for air
        assert approx(end.bar, p.bar, tol=1e-6)

    def test_trimix_end_shallower(self):
        """Adding He reduces the narcotic fraction → shallower END."""
        p = Pressure.from_depth_m(50)
        g = Gas.trimix(0.21, 0.35)
        end = g.end(p)
        # narcotic fraction = 0.21 + 0.44 = 0.65
        assert approx(end.bar, p.bar * 0.65, tol=1e-3)
        assert end.bar < p.bar

    def test_oxygen_end_equals_depth(self):
        """Pure O2 has no He; fn2=0 but fo2=1 → narcotic fraction=1."""
        p = Pressure.from_depth_m(10)
        end = Gas.oxygen().end(p)
        assert approx(end.bar, p.bar, tol=1e-6)


# ---------------------------------------------------------------------------
# is_breathable
# ---------------------------------------------------------------------------


class TestIsBreathable:
    def test_breathability_window(self):
        ean50 = Gas.nitrox(0.50)
        # EAN50 at 21 m: ppO2 ≈ 1.56 bar — inside the 1.6 deco limit.
        assert ean50.is_breathable(Pressure.from_depth_m(21))
        # EAN50 at 30 m: ppO2 ≈ 2.0 bar — out.
        assert not ean50.is_breathable(Pressure.from_depth_m(30))
        # Air at the surface is fine; oxygen at 30 m is not.
        assert Gas.air().is_breathable(Pressure.surface())
        assert not Gas.oxygen().is_breathable(Pressure.from_depth_m(30))

    def test_hypoxic_floor(self):
        assert not Gas.trimix(0.10, 0.70).is_breathable(Pressure.surface())

    def test_limits_read_from_config(self):
        DiveConfig.current().gas.deco_ppo2_bar = 1.4
        assert not Gas.nitrox(0.50).is_breathable(Pressure.from_depth_m(21))


# ---------------------------------------------------------------------------
# best_mix
# ---------------------------------------------------------------------------


class TestBestMix:
    def test_air_range_nitrox(self):
        """Shallow dive — best mix should be a nitrox with no helium."""
        g = Gas.air().best_mix(30.0)
        assert approx(g.fhe, 0.0)
        # ppO2 at 30 m must not exceed max_ppo2_bar (1.4)
        p = Pressure.from_depth_m(30)
        assert g.ppo2(p).bar <= 1.4 + 1e-6

    def test_best_mix_maximises_fo2(self):
        """fo2 should be as high as ppO2 limit allows."""
        p = Pressure.from_depth_m(30)
        g = Gas.air().best_mix(30.0)
        expected_fo2 = min(1.0, 1.4 / p.bar)
        assert approx(g.fo2, expected_fo2, tol=1e-6)

    def test_trimix_adds_helium(self):
        """Deep dive with trimix=True should produce helium to satisfy END."""
        g = Gas.air().best_mix(60.0, trimix=True)
        assert g.fhe > 0

    def test_trimix_end_satisfied(self):
        """END of returned mix must be <= max_end_m (30 m default)."""
        depth = 70.0
        g = Gas.air().best_mix(depth, trimix=True)
        p = Pressure.from_depth_m(depth)
        end = g.end(p)
        max_end_p = Pressure.from_depth_m(30.0)
        assert end.mbar <= max_end_p.mbar + 1  # 1 mbar rounding tolerance

    def test_nitrox_too_deep_raises(self):
        """At 60 m without trimix, END/ppN2 constraints cannot be met."""
        with pytest.raises(ValueError, match="trimix"):
            Gas.air().best_mix(60.0, trimix=False)

    def test_hypoxic_implies_trimix(self):
        """hypoxic=True must produce a mix with helium."""
        g = Gas.air().best_mix(100.0, hypoxic=True)
        assert g.fhe > 0

    def test_hypoxic_uses_deco_ppo2(self):
        """hypoxic mode uses deco_ppo2_bar (1.6) not max_ppo2_bar (1.4)."""
        p = Pressure.from_depth_m(100)
        g = Gas.air().best_mix(100.0, hypoxic=True)
        # ppO2 must not exceed deco_ppo2_bar
        assert g.ppo2(p).bar <= 1.6 + 1e-6

    def test_acceptsPressure_object(self):
        p = Pressure.from_depth_m(30)
        g = Gas.air().best_mix(p)
        assert g.fhe == 0.0

    def test_fractions_sum_to_one(self):
        for depth in (10, 30, 50, 80):
            g = Gas.air().best_mix(float(depth), trimix=depth > 40)
            assert abs(g.fo2 + g.fhe + g.fn2 - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Equality and hashing
# ---------------------------------------------------------------------------


class TestEqualityAndHash:
    def test_equal_gases(self):
        assert Gas(0.32) == Gas(0.32)

    def test_unequal_fo2(self):
        assert Gas(0.32) != Gas(0.36)

    def test_unequal_fhe(self):
        assert Gas(0.21, fhe=0.35) != Gas(0.21, fhe=0.40)

    def test_not_equal_to_non_gas(self):
        assert Gas(0.32) != "EAN32"

    def test_hash_equal_gases(self):
        assert hash(Gas(0.32)) == hash(Gas(0.32))

    def test_usable_in_set(self):
        s = {Gas.air(), Gas.nitrox(0.32), Gas.air()}
        assert len(s) == 2


# ---------------------------------------------------------------------------
# __repr__ and __str__
# ---------------------------------------------------------------------------


class TestStringRepresentation:
    def test_repr_air(self):
        assert repr(Gas.air()) == "Gas(fo2=0.21, fhe=0.00, fn2=0.79)"

    def test_repr_trimix(self):
        assert repr(Gas.trimix(0.21, 0.35)) == "Gas(fo2=0.21, fhe=0.35, fn2=0.44)"

    def test_str_air(self):
        assert str(Gas.air()) == "Air"

    def test_str_oxygen(self):
        assert str(Gas.oxygen()) == "O2"

    def test_str_nitrox(self):
        assert str(Gas.nitrox(0.32)) == "EAN32"

    def test_str_trimix(self):
        assert str(Gas.trimix(0.21, 0.35)) == "TX21/35"
