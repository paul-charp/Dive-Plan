"""
core/pressure.py — Pressure value type.

Ground truth is always integer millibar. Pressure represents absolute pressures
only (ambient, partial pressures, tissue loadings) — always >= 0.

Arithmetic:
    Pressure + Pressure  -> Pressure     (e.g. surface + hydrostatic)
    Pressure - Pressure  -> int          (signed mbar delta — NOT a Pressure)
    Pressure * float     -> Pressure     (e.g. ppO2 = ambient * o2_fraction)
    float   * Pressure   -> Pressure     (commutative)
    Pressure / Pressure  -> float        (dimensionless ratio)
    Pressure / float     -> Pressure     (scaling)

Depth conversion:
    Pressure.from_depth_m(depth_m)       reads DiveConfig.current().physics
    pressure.depth_m                     reads DiveConfig.current().physics

Dependency: Pressure -> DiveConfig (one way only, never reversed).
"""

from typing import overload

from diveplan.core.config import DiveConfig


class Pressure:
    """Absolute pressure stored as integer millibar.

    Immutable. __slots__ for memory efficiency in batch simulation.

    Examples:
        >>> Pressure(1013)
        Pressure(1013)
        >>> Pressure.from_bar(4.013).depth_m   # at standard surface pressure, salt water
        30.0
    """

    __slots__ = ("_mbar",)
    _mbar: int  # For type checker only — actual storage is in __slots__ for immutability and memory efficiency.

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, mbar: int) -> None:
        if mbar < 0:
            raise ValueError(
                f"Pressure cannot be negative (got {mbar} mbar). Use plain int mbar for signed deltas."
            )
        object.__setattr__(self, "_mbar", int(mbar))

    @classmethod
    def from_bar(cls, bar: float) -> Pressure:
        """Construct from bar. Rounds to nearest mbar."""
        return cls(round(bar * 1000))

    @classmethod
    def from_mbar(cls, mbar: float) -> Pressure:
        """Construct from float mbar. Rounds to nearest integer mbar."""
        if mbar < 0:
            raise ValueError(f"Pressure cannot be negative (got {mbar} mbar).")
        return cls(round(mbar))

    @classmethod
    def from_depth_m(cls, depth_m: float) -> Pressure:
        """Construct from depth in metres using the current DiveConfig environment.

        Reads DiveConfig.current().physics — context manager overrides apply:
            with DiveConfig(physics=_PhysicsConfig(surface_pressure_mbar=800)):
                Pressure.from_depth_m(40)  # altitude dive
        """
        physics = DiveConfig.current().physics
        mbar = physics.surface_pressure_mbar + depth_m * physics.pressure_per_meter_mbar
        return cls(round(mbar))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mbar(self) -> int:
        return self._mbar

    @property
    def bar(self) -> float:
        return self._mbar / 1000.0

    @property
    def depth_m(self) -> float:
        """Depth in metres in the context of the current DiveConfig environment.

        Reads DiveConfig.current().physics — context manager overrides apply.
        Returns a negative value if pressure is below surface pressure
        (e.g. altitude surface, though that shouldn't arise in normal use).
        """
        physics = DiveConfig.current().physics
        return (
            self._mbar - physics.surface_pressure_mbar
        ) / physics.pressure_per_meter_mbar

    # ------------------------------------------------------------------
    # Immutability guard
    # ------------------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Pressure is immutable — create a new instance instead.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Pressure is immutable.")

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __add__(self, other: object) -> Pressure:
        if isinstance(other, Pressure):
            return Pressure(self._mbar + other._mbar)
        return NotImplemented

    def __sub__(self, other: object) -> int:
        """Returns a signed int delta in mbar — NOT a Pressure.

        Subtraction of two absolute pressures is a delta (dimensionally
        different). Returning int prevents accidental use as an absolute pressure.
        """
        if isinstance(other, Pressure):
            return self._mbar - other._mbar
        return NotImplemented

    def __mul__(self, scalar: object) -> Pressure:
        if isinstance(scalar, (int, float)):
            result = round(self._mbar * scalar)
            if result < 0:
                raise ValueError(
                    f"Pressure * {scalar} yields negative result ({result} mbar)."
                )
            return Pressure(result)
        return NotImplemented

    def __rmul__(self, scalar: object) -> Pressure:
        return self.__mul__(scalar)

    @overload
    def __truediv__(self, other: Pressure) -> float: ...
    @overload
    def __truediv__(self, other: int | float) -> Pressure: ...

    def __truediv__(self, other: object) -> float | Pressure:
        if isinstance(other, Pressure):
            if other._mbar == 0:
                raise ZeroDivisionError("Cannot divide Pressure by zero Pressure.")
            return self._mbar / other._mbar

        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide Pressure by zero.")
            result = round(self._mbar / other)
            if result < 0:
                raise ValueError(
                    f"Pressure / {other} yields negative result ({result} mbar)."
                )
            return Pressure(result)

        return NotImplemented

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Pressure):
            return self._mbar == other._mbar
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Pressure):
            return self._mbar < other._mbar
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Pressure):
            return self._mbar <= other._mbar
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Pressure):
            return self._mbar > other._mbar
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Pressure):
            return self._mbar >= other._mbar
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._mbar)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Pressure({self._mbar})"

    def __str__(self) -> str:
        return f"{self.bar:.3f} bar ({self._mbar} mbar)"
