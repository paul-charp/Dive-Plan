from dataclasses import dataclass, field

from diveplan.utils import constants


@dataclass(frozen=True)
class GasMixture:
    """Represents the composition of a breathing gas mixture."""

    o2_fraction: float
    he_fraction: float = 0.0
    n2_fraction: float | None = None  # Allow automatic calculation of N2

    def __post_init__(self):
        if self.n2_fraction is None:
            n2 = 1.0 - (self.o2_fraction + self.he_fraction)
            object.__setattr__(self, "n2_fraction", n2)  # Calculate N2 if not provided
        # Validation (after calculating n2):
        if (
            not (
                0.0 <= self.o2_fraction <= 1.0
                and 0.0 <= self.he_fraction <= 1.0
                and 0.0 <= self.n2_fraction <= 1.0
            )
            or not abs(self.o2_fraction + self.he_fraction + self.n2_fraction - 1.0)
            < 1e-6
        ):  # tolerate small fp errors
            raise ValueError(
                "Invalid gas fractions. Must be between 0 and 1 and sum to 1."
            )

    def __str__(self):
        if self.he_fraction > 0:  # Trimix or Heliox
            return f"Tx {self.o2_fraction*100:.0f}/{self.he_fraction*100:.0f}"
        elif (
            self.n2_fraction == constants.AIR_FN2
            and self.o2_fraction == constants.AIR_FO2
        ):
            return "Air"  # Return Air if default Air fractions are used
        else:  # Nitrox or other binary mix
            return f"Nx {self.o2_fraction*100:.0f}"


@dataclass
class GasCylinder:
    """Represents a diving gas cylinder with its physical characteristics and gas mixture."""

    volume: float  # Liters (internal volume)
    working_pressure: float  # Bar
    gas_mixture: GasMixture
    reserve_pressure: float  # Bar, mandatory reserve pressure
    is_reserve_used: bool = field(
        default=False, init=False
    )  # Flag to track if the reserve has been used. Not in init, mutable

    @property  # allows you to call it like an attribute, while hiding the underlying calculation
    def current_pressure(self) -> float:
        """The current pressure in the tank, in bar."""
        if self.is_reserve_used:
            return 0.0
        return max(
            0.0,
            self.working_pressure
            - (self.reserve_pressure if self.is_reserve_used else 0.0),
        )

    def consume_gas(self, amount: float):
        """Consumes a specified amount of gas from the cylinder (in liters at surface pressure)."""
        if self.is_reserve_used:
            raise ValueError("Cannot consume gas, tank is empty!")

        consumed_volume_at_pressure = (
            amount / self.current_pressure
        )  # Convert surface volume to volume at current pressure

        if self.volume - consumed_volume_at_pressure < 0:

            self.is_reserve_used = True
            remaining_volume = (
                consumed_volume_at_pressure - self.volume
            )  # how much is not there in the tank
            raise ValueError(
                f"Not enough gas available, requires using {remaining_volume*constants.P_ATM} more liter of gas after using the reserve! Check your reserve setting!"
            )  # Warn user that there isn't enough gas even if using the reserve.

        self.volume -= consumed_volume_at_pressure

        if self.volume <= 0.0:
            self.is_reserve_used = True

    def use_reserve(self):
        """Switches to reserve gas."""

        if self.is_reserve_used:
            raise ValueError("Reserve already used!")

        self.is_reserve_used = True
