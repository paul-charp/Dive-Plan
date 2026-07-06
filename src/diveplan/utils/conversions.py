"""Argument-coercion helpers shared across the user-facing API.

These power the "friendly notation" accepted by the fluent profile builders,
:class:`~diveplan.planning.gas_plan.GasPlan`, and
:func:`~diveplan.planning.ascent_plan.plan_ascent`: depths as ``"40 m"``
strings or bare metres, gases by name. Library code coerces at its public
boundary and works with :class:`Pressure`/:class:`Gas` values internally.
"""

from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

__all__ = [
    "coerce_depth_to_pressure",
    "coerce_gas",
    "duration_from_rate",
    "DEPTH_TYPES",
    "GAS_TYPES",
]

DEPTH_TYPES = float | int | str | Pressure
"""Accepted spellings of a depth: metres, a parseable string, or a Pressure."""

GAS_TYPES = str | Gas
"""Accepted spellings of a gas: a name like ``"ean50"`` or a Gas."""


def coerce_depth_to_pressure(value: DEPTH_TYPES) -> Pressure:
    """Convert a user-facing depth argument to an absolute :class:`Pressure`.

    Args:
        value: A :class:`Pressure` (returned as-is), a string parsed by
            :meth:`Pressure.from_str` (``"40 m"``, ``"4.5 bar"``, ``"130 ft"``…),
            or a bare number interpreted as metres of depth.

    Returns:
        The corresponding absolute pressure under the current config.

    Raises:
        ValueError: If the value is a string that cannot be parsed, or an
            unsupported type.
    """
    if isinstance(value, Pressure):
        return value

    if isinstance(value, (float, int)):
        return Pressure.from_depth_m(value)

    if isinstance(value, str):
        return Pressure.from_str(value)

    raise ValueError(f"Invalid depth type: {type(value)}")


def coerce_gas(value: GAS_TYPES) -> Gas:
    """Convert a user-facing gas argument to a :class:`Gas`.

    Args:
        value: A :class:`Gas` (returned as-is) or a name parsed by
            :meth:`Gas.from_name` (``"air"``, ``"ean50"``, ``"tx21/35"``…).

    Returns:
        The corresponding gas mixture.

    Raises:
        ValueError: If the value is a string that cannot be parsed, or an
            unsupported type.
    """
    if isinstance(value, Gas):
        return value

    if isinstance(value, str):
        return Gas.from_name(value)

    raise ValueError(f"Invalid gas type: {type(value)}")


def duration_from_rate(
    rate: float, start_pressure: Pressure, end_pressure: Pressure
) -> float:
    """Traverse duration implied by a rate of pressure change.

    Args:
        rate: Rate of pressure change in mbar per minute (always positive;
            direction is taken from the pressures).
        start_pressure: Pressure at the start of the traverse.
        end_pressure: Pressure at the end of the traverse.

    Returns:
        Duration in minutes.
    """
    return abs(end_pressure - start_pressure) / rate
