from diveplan.Dive.DiveStep import DiveStep
from diveplan.Gas import Gas
from diveplan.DecoModels import ZHL16C_GF
from diveplan.utils import utils


class Dive:
    """docstring for Dive."""

    def __init__(self, planned_steps):
        super(Dive, self).__init__()

        self.steps = []
        for step in planned_steps:
            self.steps.append(step)

        self.ascend: list[DiveStep] = []
        self.gases: list[Gas] = [Gas()]
        self.GF = (100, 100)
        self.bottom_sac = 20
        self.deco_sac = 15
        self.samplerate = 0.1

        self.initDecoModel()

    def initDecoModel(self):
        self.decomodel: ZHL16C_GF = ZHL16C_GF(self.GF, self.samplerate)

    def calc_ascend(self):
        bottom_depth = self.steps[-1].end_depth
        P_amb = utils.depth_to_P_amb(bottom_depth)
        P_surf = utils.depth_to_P_amb(0)

        while P_amb > P_surf:
            ceil = utils.round_to_stop_P(self.decomodel.getCeiling())

            time = 0
            if P_amb == ceil:
                time = 1

            asc_step = DiveStep(
                time,
                utils.P_amb_to_depth(P_amb),
                utils.P_amb_to_depth(ceil),
                self.gases[0],
            )

            self.ascend.append(asc_step)

            self.decomodel.integrateDiveStep(asc_step)
            P_amb = utils.depth_to_P_amb(asc_step.end_depth)

    def calc_steps(self):

        first_step = self.steps[0]

        if first_step.start_depth != 0:
            self.steps.insert(
                0, DiveStep(0, 0, first_step.start_depth, first_step.gas[0])
            )

            self.steps[1].time -= self.steps[0].time

        for step in self.steps:
            self.decomodel.integrateDiveStep(step)

    def calc_rockbottom():
        pass

    def report(self):
        runtime = 0

        SYMBOL_MAP = {"descent": "▼", "ascent": "▲", "const": "-"}

        for i, step in enumerate(self.ascend):
            if step.type == "const" and i != 0:

                p_step = self.ascend[i - 1]

                if (step.start_depth == p_step.end_depth) and (p_step.type == "const"):
                    self.steps[-1].time += step.time
                    continue

            self.steps.append(step)

        print(self.decomodel.NAME, self.GF)

        for step in self.steps:

            symbol = SYMBOL_MAP[step.type]
            depth = round(step.end_depth)
            time = round(step.time)
            runtime += round(time)

            print(f"{symbol} {depth}m {time}min {runtime}min")
