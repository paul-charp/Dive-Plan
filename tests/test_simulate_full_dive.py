import pytest

from diveplan.core.dive import Dive, DiveStep
from diveplan.core.gas import GasCylinder, GasMixture

# Constants for testing
STANDARD_CYLINDER_VOLUME = 12  # Liters
STANDARD_CYLINDER_PRESSURE = 200  # Bar
STANDARD_RESERVE_PRESSURE = 50 # Bar
FIO2_AIR = 0.21
FIO2_NITROX32 = 0.32
FIO2_TX1845 = 0.18
FHE_TX1845 = 0.45


# ----- Gas and Cylinder Tests -----
def test_gas_mixture_creation():
    """Tests valid and invalid gas mixture creation."""

    # Valid mixtures
    GasMixture(o2_fraction=FIO2_AIR, he_fraction=0.0)  # Air
    GasMixture(o2_fraction=FIO2_NITROX32, he_fraction=0.0)  # Nitrox 32
    GasMixture(o2_fraction=FIO2_TX1845, he_fraction=FHE_TX1845)  # Trimix 18/45

    # Invalid mixtures (should raise ValueError)
    with pytest.raises(ValueError):
        GasMixture(o2_fraction=1.2, he_fraction=0.0)  # O2 > 1
    with pytest.raises(ValueError):
        GasMixture(o2_fraction=FIO2_AIR, he_fraction=-0.1)  # He < 0
    with pytest.raises(ValueError):
        GasMixture(o2_fraction=0.3, he_fraction=0.8)  # O2 + He > 1


def test_gas_consumption():
    """Tests gas consumption and reserve usage."""
    mix = GasMixture(FIO2_AIR)  # Air
    cylinder = GasCylinder(
        volume=STANDARD_CYLINDER_VOLUME,
        working_pressure=STANDARD_CYLINDER_PRESSURE,
        gas_mixture=mix,
        reserve_pressure=STANDARD_RESERVE_PRESSURE,
    )

    # Simulate gas consumption
    cylinder.consume_gas(200)  # Consume 200 liters at surface pressure
    assert cylinder.current_pressure == pytest.approx(
       STANDARD_CYLINDER_PRESSURE * ((STANDARD_CYLINDER_VOLUME - 200/STANDARD_CYLINDER_PRESSURE) / STANDARD_CYLINDER_VOLUME)
    )

    cylinder.consume_gas(200)
    with pytest.raises(ValueError):  # Check it raises error correctly
        cylinder.consume_gas(1)  # Exceed reserve, expect ValueError


def test_empty_gas_cylinder():
    """Tests behavior with an empty gas cylinder."""

    mix = GasMixture(FIO2_AIR)  # Air
    cylinder = GasCylinder(
        volume=STANDARD_CYLINDER_VOLUME,
        working_pressure=STANDARD_RESERVE_PRESSURE,  # Already at reserve pressure
        gas_mixture=mix,
        reserve_pressure=STANDARD_RESERVE_PRESSURE,
    )
    #Try to consume when at reserve pressure. Should raise a ValueError as if we were trying to go below 0 in regular cases.
    with pytest.raises(ValueError):
        cylinder.consume_gas(1)


# ----- Dive Tests -----


def test_simple_dive_no_deco():
    """Tests a simple dive with no decompression required."""
    mix = GasMixture(FIO2_AIR)  # Air
    cylinder = GasCylinder(
        volume=STANDARD_CYLINDER_VOLUME,
        working_pressure=STANDARD_CYLINDER_PRESSURE,
        gas_mixture=mix,
        reserve_pressure=STANDARD_RESERVE_PRESSURE,
    )
    steps = [
        DiveStep(0, 0, 10, cylinder),  # Descent to 10m
        DiveStep(10, 10, 10, cylinder),  # 10 min at 10m
        DiveStep(0, 10, 0, cylinder),  # Ascent to surface
    ]

    dive = Dive(steps, [cylinder])
    dive.calculate_steps()
    dive.calculate_ascent()  # Should not add any deco stops

    assert len(dive.ascent) == 0  # No deco stops
    assert len(dive.steps) == 3  # Original steps + surface start


def test_dive_multi_levels_no_deco():
    """Tests a multi-level dive with no decompression required."""

    mix = GasMixture(FIO2_AIR)  # Air
    cylinder = GasCylinder(
        volume=STANDARD_CYLINDER_VOLUME,
        working_pressure=STANDARD_CYLINDER_PRESSURE,
        gas_mixture=mix,
        reserve_pressure=STANDARD_RESERVE_PRESSURE,
    )

    steps = [
        DiveStep(0, 0, 20, cylinder),  # Descent to 20m
        DiveStep(10, 20, 20, cylinder),  # 10 min at 20m
        DiveStep(0, 20, 10, cylinder),  # Ascent to 10m
        DiveStep(5, 10, 10, cylinder),  # 5 min at 10m
        DiveStep(0, 10, 0, cylinder),  # Ascent to surface
    ]


    dive = Dive(steps, [cylinder])
    dive.calculate_steps()
    dive.calculate_ascent()

    assert len(dive.ascent) == 0  # No decompression stops added
    assert len(dive.steps) == 5 +1 # Original steps + starting step at surface

