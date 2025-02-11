from diveplan.core import constants
from diveplan.core.decomodels.abstract_deco_model import AbstractDecoModel
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.core.gasplan import GasPlan
from diveplan.core.pressure import Pressure
from diveplan.core.utils import find_decomodels, simplify_divesteps


class Dive:
    """docstring for Dive."""

    def __init__(
        self,
        planned_steps: list[DiveStep],
        gases: list[Gas],
        decomodel_name: str,
        decomodel_parms: dict = {},
        decomodel_samplerate: float = constants.SAMPLE_RATE,
    ):
        super(Dive, self).__init__()

        self.steps: list[DiveStep] = []
        for step in planned_steps:
            self.steps.append(step)

        self.ascend: list[DiveStep] = []
        self.gases: list[Gas] = gases

        DecoModel = find_decomodels().get(decomodel_name)

        if DecoModel is not None:
            self.decomodel: AbstractDecoModel = DecoModel(
                decomodel_samplerate, decomodel_parms
            )

        else:
            raise ValueError(f"DecoModel '{decomodel_name}' not found !")

    def calc_ascend(self):
        bottom_depth = self.steps[-1].end_depth
        P_amb: Pressure = Pressure.from_depth(bottom_depth)
        P_surf: Pressure = Pressure.from_depth(0)
        gas: Gas = self.steps[-1].gas

        while P_amb > P_surf:

            ceil: Pressure = self.decomodel.getCeiling().round_to_deeper_depth_inc()

            time = 0
            if P_amb == ceil:
                time = 1

            asc_step = DiveStep(
                time,
                P_amb.to_depth(),
                ceil.to_depth(),
                gas,
            )

            self.ascend.append(asc_step)

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

        asc_step = simplify_divesteps(self.ascend)
        self.steps.extend(asc_step)

        print(self.decomodel)

        for step in self.steps:

            symbol = step.SYMBOL_MAP[step.type]
            depth = round(step.end_depth)
            time = round(step.time)
            runtime += round(time)
            gas = step.gas

            print(f"{symbol} {depth}m {time}min {runtime}min {gas}")
