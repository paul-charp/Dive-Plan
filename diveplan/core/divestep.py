from diveplan.core import constants
from diveplan.core.pressure import Pressure
from diveplan.core.gas import Gas


class DiveStep:
    """
    Represents part of a dive, with end and start depths, a time and a breathing gas.
    Depths in meters, time in minutes
    """

    SYMBOL_MAP = {"descent": "▼", "ascent": "▲", "const": "-"}

    def __init__(self, time, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()

        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas: Gas = gas
        self.time = time

    # Getters and Setters
    @property
    def start_depth(self) -> float:
        return self._start_depth

    @start_depth.setter
    def start_depth(self, value: float):
        if value >= 0:
            self._start_depth = value
        else:
            raise ValueError("Depth cannot be a negative value !")

    @property
    def end_depth(self) -> float:
        return self._end_depth

    @end_depth.setter
    def end_depth(self, value: float):
        if value >= 0:
            self._end_depth = value
        else:
            raise ValueError("Depth cannot be a negative value !")

    @property
    def time(self) -> float:
        return self._time

    @time.setter
    def time(self, value: float):
        if value == 0:
            # If time is set to 0, default ascent and descent rates are used to set the appropriate time regarding the start and end depths
            if self.depth_change < 0:
                self._time = abs(self.depth_change) / constants.ASC_RATE

            elif self.depth_change > 0:
                self._time = abs(self.depth_change) / constants.DES_RATE

            else:
                self._time = constants.MIN_STOP_TIME

        elif value > 0:
            self._time = value

        else:
            raise ValueError("Time cannot be a negative value !")

    @property
    def rate(self) -> float:
        return self.depth_change / self.time

    @property
    def depth_change(self) -> float:
        return self.end_depth - self.start_depth

    @property
    def type(self) -> str:
        if self.depth_change < 0:
            return "ascent"

        elif self.depth_change > 0:
            return "descent"

        else:
            return "const"

    def get_P_amb_at_sample(self, s: float) -> Pressure:
        """
        Gets the ambiant pressure for a given timesample of this divestep.

        Arguments:
            s: float -- The time sample value.

        Returns:
            Pressure
        """
        depth_at_sample = self.start_depth + (s / self.time) * (
            self.end_depth - self.start_depth
        )

        return Pressure.from_depth(depth_at_sample)

    def extend(self, divestep: "DiveStep"):
        """
        Extends "merge" this divestep with another.

        Arguments:
            divestep -- The divestep to merge with
        """
        self.time += divestep.time
        self.end_depth = divestep.end_depth

    def is_continuous(self, divestep: "DiveStep") -> bool:
        """
        Returns True is this divestep and another are continuous in depths, rate and gas.

        Arguments:
            divestep -- Divestep to compare with

        Returns:
            bool
        """
        return all(
            [
                self.start_depth == divestep.end_depth,
                self.rate == divestep.rate,
                self.gas == divestep.gas,
            ]
        )

    def __repr__(self) -> str:
        symbol = self.SYMBOL_MAP[self.type]

        start_depth = round(self.start_depth)
        end_depth = round(self.end_depth)
        time = round(self.time)
        gas = self.gas

        return f"{start_depth}m {symbol} {end_depth}m {time}min {gas}"
