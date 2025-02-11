import math

from diveplan.core import constants


class Pressure(float):
    """
    Pressure type. Represents a pressure value in bars.
    Maximal number of decimals defined by _PRESSURE constant
    While Pressure cannot be negative, the types allows it because of decompression calculation
    that can result in negative "Pressures" in tissues (Inert Gas Tension)

    Inheritance:
        float

    """

    _PRECISION = 5

    def __new__(cls, value: float):

        # cls._validate_value(value) # Disable check for negative value causing error in deco calculations

        value = round(value, cls._PRECISION)
        value = float(value)
        return super().__new__(cls, value)

    @staticmethod
    def _validate_value(value: float):
        if value < 0:
            raise ValueError("Pressure cannot be negative")

    def to_depth(
        self,
        P_atm: "Pressure" = constants.P_ATM,
        water_density: float = constants.WATER_DENSITY,
    ) -> float:
        """
        Converts pressure value to depth in meters

        Args:
            P_atm ("Pressure"=constants.P_ATM): Atmospheric Pressure in bar
            water_density (float=constants.WATER_DENSITY): Water density in kg/m3

        Returns:
            float

        """
        depth: float = (self - P_atm) / (water_density * constants.G * 10**-5)
        return round(depth, constants.DEPTH_PRECISION)

    @staticmethod
    def from_depth(
        depth: float,
        P_atm: "Pressure" = constants.P_ATM,
        water_density: float = constants.WATER_DENSITY,
    ) -> "Pressure":
        """
        Pressure from depth value in meters

        Args:
            depth (float): Depth in meters
            P_atm ("Pressure"=constants.P_ATM): Atmospheric Pressure in bar
            water_density (float=constants.WATER_DENSITY): Water density in kg/m3

        Returns:
            Pressure

        """
        return P_atm + ((water_density * constants.G * 10**-5) * depth)

    def round_to_deeper_depth_inc(self, inc: float = constants.STOP_INC) -> "Pressure":
        """
        Rounds the Pressure value to the next deeper increments of depth in meters

        Args:
            inc (float=constants.STOP_INC): Depth increment in meters

        Returns:
            Pressure

        """
        rounded_depth = math.ceil(self.to_depth() / inc) * inc
        return Pressure.from_depth(rounded_depth)

    def round_to_shallower_depth_inc(
        self, inc: float = constants.STOP_INC
    ) -> "Pressure":
        """
        Rounds the Pressure value to the next shallower increments of depth in meters

        Args:
            inc (float=constants.STOP_INC): Depth increment in meters

        Returns:
            Pressure

        """
        rounded_depth = math.floor(self.to_depth() / inc) * inc
        return Pressure.from_depth(rounded_depth)

    # Basic math implementation.
    def __add__(self, other) -> "Pressure":
        return Pressure(float(self) + float(other))

    def __sub__(self, other) -> "Pressure":
        result = float(self) - float(other)
        return Pressure(result)

    def __mul__(self, other) -> "Pressure":
        return Pressure(float(self) * float(other))

    def __truediv__(self, other) -> "Pressure":
        return Pressure(float(self) / float(other))

    def __repr__(self):
        return f"{float(self)} bar"
