from diveplan.core import constants
from diveplan.core.pressure import Pressure
from diveplan.core.gas import Gas


class DiveStep:
    """docstring for DiveStep."""

    SYMBOL_MAP = {"descent": "▼", "ascent": "▲", "const": "-"}

    def __init__(self, time, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()

        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas: Gas = gas

        if time == 0:
            if self.depth_change < 0:
                self.time = abs(self.depth_change) / constants.ASC_RATE

            elif self.depth_change > 0:
                self.time = abs(self.depth_change) / constants.DES_RATE

            else:
                self.time = 1  # Minimum divestep time

        else:
            self.time = time

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

    def get_P_amb_at_sample(self, s: float) -> float:

        depth_at_sample = self.start_depth + (s / self.time) * (
            self.end_depth - self.start_depth
        )

        return Pressure.from_depth(depth_at_sample)

    def extend(self, divestep: "DiveStep") -> "DiveStep":
        self.time += divestep.time
        self.end_depth = divestep.end_depth

    def is_continuous(self, divestep: "DiveStep") -> bool:
        return all(
            [
                self.type == divestep.type,
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
