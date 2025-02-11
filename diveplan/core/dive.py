from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.core.decomodels.zhl16c_gf import ZHL16C_GF
from diveplan.core.gasplan import GasPlan
from diveplan.core.pressure import Pressure


class Dive:
    """docstring for Dive."""

    def __init__(self, planned_steps, gases):
        super(Dive, self).__init__()

        self.steps = []
        for step in planned_steps:
            self.steps.append(step)

        self.ascend: list[DiveStep] = []
        self.gases: list[Gas] = gases
        self.GF = (100, 100)
        self.bottom_sac = 20
        self.deco_sac = 15
        self.samplerate = 0.1

        self.initDecoModel()

    def initDecoModel(self):
        self.decomodel: ZHL16C_GF = ZHL16C_GF(self.GF, self.samplerate)

    def calc_ascend(self):
        bottom_depth = self.steps[-1].end_depth
        P_amb: Pressure = Pressure.from_depth(bottom_depth)
        P_surf: Pressure = Pressure.from_depth(0)
        gas: Gas = self.steps[-1].gas

        gasplan = GasPlan(self.gases)

        while P_amb > P_surf:

            deco_ceil: Pressure = (
                self.decomodel.getCeiling().round_to_deeper_depth_inc()
            )

            switch_P, next_gas = gasplan.getNextGasSwitch(P_amb)
            # print(switch_P.to_depth(), next_gas)

            if (next_gas != None) and (next_gas != gas) and (deco_ceil <= switch_P):
                ceil = switch_P

            else:
                ceil = deco_ceil

            time = 0
            if P_amb == ceil:
                time = 1

                if next_gas != None:
                    gas = next_gas

            asc_step = DiveStep(
                time,
                P_amb.to_depth(),
                ceil.to_depth(),
                gas,
            )

            self.ascend.append(asc_step)

            print(asc_step)  # FOR DEBUG

            self.decomodel.integrateDiveStep(asc_step)
            P_amb: Pressure = Pressure.from_depth(asc_step.end_depth)

    def calc_steps(self):

        first_step = self.steps[0]

        if first_step.start_depth != 0:
            self.steps.insert(0, DiveStep(0, 0, first_step.start_depth, first_step.gas))

            self.steps[1].time -= self.steps[0].time

        for step in self.steps:
            self.decomodel.integrateDiveStep(step)

    def calc_rockbottom():
        pass

    def report(self):
        runtime = 0

        for i, step in enumerate(self.ascend):
            if step.type == "const" and i != 0:

                p_step = self.ascend[i - 1]

                if (step.start_depth == p_step.end_depth) and (p_step.type == "const"):
                    self.steps[-1].time += step.time
                    continue

            self.steps.append(step)

        self.steps.extend(self.ascend)

        print(self.decomodel.NAME, self.GF)

        for step in self.steps:

            symbol = step.SYMBOL_MAP[step.type]
            depth = round(step.end_depth)
            time = round(step.time)
            runtime += round(time)
            gas = step.gas

            print(f"{symbol} {depth}m {time}min {runtime}min {gas}")
