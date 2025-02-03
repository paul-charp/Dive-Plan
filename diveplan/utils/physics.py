# diveplan/utils/physics.py
import math
from diveplan.utils import constants


def depth_to_ambient_pressure(
    depth: float,
    atmospheric_pressure: float = constants.P_ATM,
    water_density: float = constants.WATER_DENSITY,
) -> float:
    """Converts depth to ambient pressure."""
    ambient_pressure: float = atmospheric_pressure + (
        constants.P_WATER_DEPTH_CONVERSION_FACTOR * depth
    )
    return round(ambient_pressure, constants.P_PRECISION)


def ambient_pressure_to_depth(
    ambient_pressure: float,
    atmospheric_pressure: float = constants.P_ATM,
    water_density: float = constants.WATER_DENSITY,
) -> float:
    """Converts ambient pressure to depth."""
    depth: float = (
        ambient_pressure - atmospheric_pressure
    ) / constants.P_WATER_DEPTH_CONVERSION_FACTOR
    return round(depth, constants.DEPTH_PRECISION)


def round_to_stop_pressure(
    pressure: float, stop_increment: float = constants.STOP_INC
) -> float:
    """Rounds pressure to the nearest stop pressure increment."""
    depth = ambient_pressure_to_depth(pressure)
    rounded_depth = math.ceil(depth / stop_increment) * stop_increment
    return depth_to_ambient_pressure(rounded_depth)


def frange(start: float, stop: float, step: float):
    """Generates a range of floating point numbers."""

    x = start
    while x < stop:
        yield x
        x += step
