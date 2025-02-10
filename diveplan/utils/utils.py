import math

from diveplan.core.pressure import Pressure
from diveplan.utils import constants


def round_to_stop_P(P: Pressure, stop_inc: float = constants.STOP_INC) -> float:
    depth = P.to_depth()

    rounded_depth = math.ceil(depth / stop_inc) * stop_inc

    return Pressure.from_depth(rounded_depth)


def round_to_gas_switch_P(P: Pressure, stop_inc: float = constants.STOP_INC) -> float:
    depth = P.to_depth()

    rounded_depth = math.floor(depth / stop_inc) * stop_inc

    return Pressure.from_depth(rounded_depth)


def frange(start, stop, step):
    while start < stop:
        yield round(start, 10)
        start += step
