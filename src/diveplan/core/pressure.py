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

from typing import Literal, overload

from diveplan.core.config import DiveConfig

__all__ = ["Pressure", "PressureUnit"]

PressureUnit = Literal["bar", "mbar", "atm", "psi", "m", "ft"]
"""Unit names accepted by :meth:`Pressure.to_str`."""


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

    @classmethod
    def from_atm(cls, atm: float) -> Pressure:
        """Construct from atmospheres. Rounds to nearest mbar."""
        physics = DiveConfig.current().physics
        return cls.from_mbar(atm * physics.surface_pressure_mbar)

    # psi ↔ mbar: 1 mbar = 0.0145038 psi  ⇒  mbar = psi / 0.0145038
    _PSI_PER_MBAR = 0.0145038

    @classmethod
    def from_psi(cls, psi: float) -> Pressure:
        """Construct from psi. Rounds to nearest mbar."""
        return cls.from_mbar(psi / cls._PSI_PER_MBAR)

    @classmethod
    def from_depth_ft(cls, depth_ft: float) -> Pressure:
        """Construct from depth in feet using the current DiveConfig environment.

        Reads DiveConfig.current().physics — context manager overrides apply:
            with DiveConfig(physics=_PhysicsConfig(surface_pressure_mbar=800)):
                Pressure.from_depth_ft(130)  # altitude dive
        """
        physics = DiveConfig.current().physics
        mbar = (
            physics.surface_pressure_mbar
            + depth_ft * 0.3048 * physics.pressure_per_meter_mbar
        )
        return cls(round(mbar))

    @classmethod
    def surface(cls) -> Pressure:
        """Convenience constructor for surface pressure in the current DiveConfig environment."""
        return cls.from_atm(1.0)

    @classmethod
    def from_str(cls, s: str) -> Pressure:
        """Parse a pressure from a string with unit suffix. Supported formats:
            "4.013 bar"
            "4013 mbar"
            "1 atm"
            "14.7 psi"
            "30 m"
            "98 ft"

        Args:
            s: Input string to parse.

        Raises:
            ValueError: If the input string has an invalid format or unit.
            ValueError: If the parsed value is negative.
            ValueError: If the parsed value is not a valid number.

        Returns:
            Pressure: The parsed pressure instance.
        """

        s = s.strip().lower()

        # NB: order matters — "mbar" ends with "bar", and "atm" ends with "m",
        # so the more specific suffixes must be tested first.
        if s.endswith("mbar"):
            try:
                mbar = float(s[:-4].strip())
                return cls.from_mbar(mbar)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        elif s.endswith("bar"):
            try:
                bar = float(s[:-3].strip())
                return cls.from_bar(bar)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        elif s.endswith("atm"):
            try:
                atm = float(s[:-3].strip())
                return cls.from_atm(atm)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        elif s.endswith("psi"):
            try:
                psi = float(s[:-3].strip())
                return cls.from_psi(psi)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        elif s.endswith("ft"):
            try:
                depth_ft = float(s[:-2].strip())
                return cls.from_depth_ft(depth_ft)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        elif s.endswith("m"):
            try:
                depth_m = float(s[:-1].strip())
                return cls.from_depth_m(depth_m)
            except ValueError:
                raise ValueError(f"Invalid pressure string: '{s}'")

        else:
            raise ValueError(
                f"Invalid pressure string: '{s}' (must end with 'bar', 'mbar', 'atm', 'psi', 'ft', or 'm')"
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mbar(self) -> int:
        """Absolute pressure in integer millibar (the ground-truth value)."""
        return self._mbar

    @property
    def bar(self) -> float:
        """Absolute pressure in bar."""
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

    @property
    def depth_ft(self) -> float:
        """Depth in feet in the context of the current DiveConfig environment.

        Reads DiveConfig.current().physics — context manager overrides apply.
        Returns a negative value if pressure is below surface pressure
        (e.g. altitude surface, though that shouldn't arise in normal use).
        """
        physics = DiveConfig.current().physics
        return (self._mbar - physics.surface_pressure_mbar) / (
            0.3048 * physics.pressure_per_meter_mbar
        )

    @property
    def atm(self) -> float:
        """Absolute pressure in atmospheres, relative to the current surface pressure."""
        physics = DiveConfig.current().physics
        return self._mbar / physics.surface_pressure_mbar

    @property
    def psi(self) -> float:
        """Absolute pressure in pounds per square inch."""
        return self._mbar * self._PSI_PER_MBAR

    @property
    def is_surface(self) -> bool:
        """Whether this pressure is at (or above) the configured surface."""
        physics = DiveConfig.current().physics
        return self._mbar <= physics.surface_pressure_mbar

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

    def to_str(self, unit: PressureUnit = "bar") -> str:
        """Format pressure as a string in the specified unit.

        Supported units: 'bar', 'mbar', 'atm', 'psi', 'm' (depth in metres), 'ft' (depth in feet).
        """
        u = unit.lower()
        if u == "bar":
            return f"{self.bar:.3f} bar"
        elif u == "mbar":
            return f"{self.mbar} mbar"
        elif u == "atm":
            return f"{self.atm:.3f} atm"
        elif u == "psi":
            return f"{self.psi:.2f} psi"
        elif u == "m":
            return f"{self.depth_m:.1f} m"
        elif u == "ft":
            return f"{self.depth_ft:.1f} ft"
        else:
            raise ValueError(
                f"Unsupported unit '{unit}' for Pressure.to_str (must be 'bar', 'mbar', 'atm', 'psi', 'm', or 'ft')."
            )

    def __repr__(self) -> str:
        return f"Pressure({self._mbar})"

    def __str__(self) -> str:
        return f"{self.bar:.3f} bar ({self._mbar} mbar)"
