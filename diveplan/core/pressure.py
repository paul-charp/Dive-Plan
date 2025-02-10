from diveplan.utils import constants


class Pressure(float):
    """
    Wrapper around float type.
    Minimal implementation, assumes that the float base type is dealing with most of the error handling.
    """

    _PRECISION = 5

    def __new__(cls, value: float):

        # cls._validate_value(value)

        value = round(value, cls._PRECISION)
        value = float(value)
        return super().__new__(cls, value)

    @staticmethod
    def _validate_value(value: float):
        if value < 0:
            raise ValueError("Pressure cannot be negative")

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

    def to_depth(
        self,
        P_atm: float = constants.P_ATM,
        water_density: float = constants.WATER_DENSITY,
    ) -> float:

        depth: float = (self - P_atm) / (water_density * constants.G * 10**-5)
        return round(depth, constants.DEPTH_PRECISION)

    @staticmethod
    def from_depth(
        depth: float,
        P_atm: float = constants.P_ATM,
        water_density: float = constants.WATER_DENSITY,
    ) -> float:

        P_amb: float = P_atm + ((water_density * constants.G * 10**-5) * depth)
        return Pressure(P_amb)
