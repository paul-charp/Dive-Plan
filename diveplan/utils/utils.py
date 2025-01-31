import math

from diveplan.utils import constants


def depth_to_P_amb(
    depth: float,
    P_atm: float = constants.P_ATM,
    water_density: float = constants.WATER_DENSITY,
) -> float:

    P_amb: float = P_atm + ((water_density * constants.G * 10**-5) * depth)
    return round(P_amb, constants.P_PRECISION)


def P_amb_to_depth(
    P_amb: float,
    P_atm: float = constants.P_ATM,
    water_density: float = constants.WATER_DENSITY,
) -> float:

    depth: float = (P_amb - P_atm) / (water_density * constants.G * 10**-5)
    return round(depth, constants.DEPTH_PRECISION)


def round_to_stop_P(P: float, stop_inc: float = constants.STOP_INC) -> float:
    depth = P_amb_to_depth(P)

    rounded_depth = math.ceil(depth / stop_inc) * stop_inc

    return depth_to_P_amb(rounded_depth)


def frange(start, stop, step):
    while start < stop:
        yield round(start, 10)
        start += step
