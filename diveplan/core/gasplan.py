from typing import Optional

from diveplan.core import constants
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure


class GasPlan:

    def __init__(self, gases: list[Gas]):
        super(GasPlan, self).__init__()

        # Remove duplicate gases
        unique_gases: list[Gas] = []
        for gas in gases:
            if gas not in unique_gases:
                unique_gases.append(gas)

        self.gases: list[Gas] = unique_gases

        self.otu: float = 0
        self.cns: float = 0

    def bestGases(self, P_amb: Pressure) -> list[Gas]:

        best_gases: list[Gas] = []

        for gas in self.gases:
            if (gas.maxOperatingPressure() >= P_amb) and (
                gas.ppO2(P_amb) >= constants.MIN_PPO2
            ):
                best_gases.append(gas)

        best_gases.sort(
            key=lambda gas: (gas.ppO2(P_amb), gas.ppHe(P_amb)), reverse=True
        )

        return best_gases

    def getNextGasSwitch(
        self,
        P_amb: Pressure,
        current_gas: Gas,
        P_surf: Optional[Pressure] = None,
        stop_inc: Optional[Pressure] = None,
    ) -> list[tuple[Pressure, Gas]]:

        if P_surf is None:
            P_surf = Pressure(constants.P_ATM)

        if stop_inc is None:
            stop_inc = Pressure(constants.STOP_INC)

        best_gas: Optional[Gas] = None

        gas_switches: list[tuple[Pressure, Gas]] = []

        P_amb = P_amb.round_to_shallower_depth_inc()

        while P_amb > P_surf:
            best_gas = self.bestGases(P_amb)[0]

            if best_gas != current_gas:
                gas_switches.append((P_amb, best_gas))
                current_gas = best_gas

            P_amb = Pressure.from_depth(P_amb.to_depth() - stop_inc)

        return gas_switches

    @staticmethod
    def TI(t: float, pO2: float, c: float):
        return (t**2) * (float(pO2) ** c)

    def consume_gases(self, divestep: DiveStep):

        try:
            breathing_gas: Gas = next(
                (gas for gas in self.gases if divestep.gas == gas)
            )

        except StopIteration:
            self.gases.append(breathing_gas)
            breathing_gas: Gas = divestep.gas

        if breathing_gas in self.gases:
            # Get the gas
            pass

        else:
            self.gases.append(breathing_gas)

        for gas in self.gases:
            if gas == divestep.gas:
                breathing_gas = gas
                break

        if breathing_gas is None:
            breathing_gas = divestep.gas
            self.gases.append(breathing_gas)

        depth = divestep.average_depth
        time = divestep.time

        P_amb = Pressure.from_depth(depth)
        breathing_gas.consume(P_amb, time)

        ppO2 = breathing_gas.ppO2(P_amb)
        self.otu += self.TI((time / 60), ppO2, 4.57)
        self.cns += self.TI(time, ppO2, 6.8) / 26.108
