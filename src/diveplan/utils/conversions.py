from ..core.gas import Gas
from ..core.pressure import Pressure

__all__ = [
    "coerce_depth_to_pressure",
    "coerce_gas",
    "duration_from_rate",
    "DEPTH_TYPES",
    "GAS_TYPES",
]

DEPTH_TYPES = float | int | str | Pressure
GAS_TYPES = str | Gas


def coerce_depth_to_pressure(value: DEPTH_TYPES) -> Pressure:
    if isinstance(value, Pressure):
        return value

    if isinstance(value, (float, int)):
        return Pressure.from_depth_m(value)

    if isinstance(value, str):
        return Pressure.from_str(value)

    raise ValueError(f"Invalid depth type: {type(value)}")


def coerce_gas(value: GAS_TYPES) -> Gas:
    if isinstance(value, Gas):
        return value

    if isinstance(value, str):
        return Gas.from_name(value)

    raise ValueError(f"Invalid gas type: {type(value)}")


def duration_from_rate(
    rate: float, start_pressure: Pressure, end_pressure: Pressure
) -> float:
    return abs(end_pressure - start_pressure) / rate
