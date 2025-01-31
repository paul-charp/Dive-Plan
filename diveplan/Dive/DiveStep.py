from diveplan.utils import utils
from diveplan.utils import constants


class DiveStep:
    """docstring for DiveStep."""

    def __init__(self, time, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()

        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas = [gas]

        if time == 0:

            depth_change = end_depth - start_depth

            if depth_change < 0:
                self.type = "ascent"
                self.time = abs(depth_change) / constants.ASC_RATE

            elif depth_change > 0:
                self.type = "descent"
                self.time = abs(depth_change) / constants.DES_RATE

            else:
                self.type = "const"
                self.time = 1  # Minimum divestep time

        else:

            depth_change = end_depth - start_depth

            if depth_change < 0:
                self.type = "ascent"

            elif depth_change > 0:
                self.type = "descent"

            else:
                self.type = "const"

            self.time = time

    def get_P_amb_at_sample(self, s: float) -> float:

        depth_at_sample = self.start_depth + (s / self.time) * (
            self.end_depth - self.start_depth
        )

        return utils.depth_to_P_amb(depth_at_sample)
