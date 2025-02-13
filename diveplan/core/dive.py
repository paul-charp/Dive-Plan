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
        decomodel_name: str = constants.DEFAULT_DECO_MODEL,
        decomodel_parms: dict = {},
        decomodel_samplerate: float = constants.SAMPLE_RATE,
    ):
        super(Dive, self).__init__()

        self.steps: list[DiveStep] = []
        for step in planned_steps:
            self.steps.append(step)
            gases.append(step.gas)

        self.ascend: list[DiveStep] = []

        self.gasplan: GasPlan = GasPlan(gases)

        DecoModel = find_decomodels().get(decomodel_name)

        if DecoModel is not None:
            self.decomodel: AbstractDecoModel = DecoModel(
                decomodel_samplerate, decomodel_parms
            )

        else:
            raise ValueError(f"DecoModel '{decomodel_name}' not found !")

    def init_from_previous_dive(self, previous_dive: "Dive", surface_interval: float):
        if type(self.decomodel == previous_dive.decomodel):

            deco_var_name = self.decomodel.DECO_MODEL_VAR
            self.decomodel.__setattr__(
                deco_var_name, previous_dive.decomodel.__getattribute__(deco_var_name)
            )
            self.decomodel.integrateDiveStep(DiveStep(surface_interval, 0, 0, Gas()))

    def _calc_ascend(self):
        bottom_depth = self.steps[-1].end_depth
        P_amb: Pressure = Pressure.from_depth(bottom_depth)
        P_surf: Pressure = Pressure.from_depth(0)
        gas: Gas = self.steps[-1].gas
        P_switch, next_gas = None, None

        while P_amb > P_surf:
            ceil: Pressure = self.decomodel.getCeiling()
            print(
                P_amb.to_depth(),
                ceil.to_depth(),
                ceil.round_to_deeper_depth_inc().to_depth(),
            )
            ceil = ceil.round_to_deeper_depth_inc()

            try:
                P_switch, next_gas = self.gasplan.getNextGasSwitch(P_amb, gas)[0]

            except IndexError:
                P_switch, next_gas = None, None

            if ceil > P_surf:
                ceil = max(ceil, Pressure.from_depth(constants.LAST_STOP))

            if P_switch is not None:
                ceil = max(ceil, P_switch)

            time = 0
            if P_amb == ceil:
                if (next_gas is not None) and (next_gas != gas):
                    gas = next_gas

                time = 1

            else:
                ceil = P_amb - Pressure(
                    Pressure.from_depth(self.decomodel.samplerate * constants.ASC_RATE)
                    - Pressure(constants.P_ATM)
                )
                ceil = max(P_surf, ceil)

            asc_step = DiveStep(
                time,
                P_amb.to_depth(),
                ceil.to_depth(),
                gas,
            )

            self.ascend.append(asc_step)

            self.decomodel.integrateDiveStep(asc_step)

            self.gasplan.consume_gases(asc_step)
            P_amb = Pressure.from_depth(asc_step.end_depth)

        self.ascend = simplify_divesteps(self.ascend)

    def _calc_steps(self):

        first_step = self.steps[0]

        if first_step.start_depth != 0:
            self.steps.insert(0, DiveStep(0, 0, first_step.start_depth, first_step.gas))

            self.steps[1].time -= self.steps[0].time

        for step in self.steps:
            self.decomodel.integrateDiveStep(step)
            self.gasplan.consume_gases(step)

    def calc_rockbottom():
        pass

    def plan(self):
        self._calc_steps()
        self._calc_ascend()

    def report(self):
        runtime = 0

        self.steps.extend(self.ascend)

        print(self.decomodel)

        for step in self.steps:

            symbol = step.SYMBOL_MAP[step.type]
            depth = round(step.end_depth)

            time = step.time  # round(step.time)
            time_m = int(time)
            time_s = int((time - time_m) * 60)

            runtime += round(time)
            gas = step.gas

            print(f"{symbol} {depth}m {time_m}'{time_s}'' {runtime}min {gas}")

        for gas in self.gasplan.gases:
            print(f"{gas} : {round(gas.consumption)}L")

        print(f"OTU : {self.gasplan.otu}")
        print(f"CNS : {self.gasplan.cns}%")


class DiveReport:
    def __init__(self, dive: Dive):
        super(DiveReport, self).__init__()

    @property
    def tts(self):
        pass

    @property
    def total_stop_time(self):
        pass
