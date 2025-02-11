from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure
from diveplan.core import constants


class GasPlan:

    def __init__(self, gases):
        super(GasPlan, self).__init__()

        # Remove duplicate gases
        unique_gases = []
        for gas in gases:
            if gas not in unique_gases:
                unique_gases.append(gas)

        self.gases: list[Gas] = unique_gases

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
        P_surf: Pressure = constants.P_ATM,
        stop_inc: float = constants.STOP_INC,
    ) -> list[tuple[Pressure, Gas]]:

        best_gas: Gas = None

        gas_switches: list[tuple[Pressure, Gas]] = []

        P_amb = P_amb.round_to_shallower_depth_inc()

        while P_amb > P_surf:
            best_gas = self.bestGases(P_amb)[0]

            if best_gas != current_gas:
                gas_switches.append((P_amb, best_gas))
                current_gas = best_gas

            P_amb = Pressure.from_depth(P_amb.to_depth() - stop_inc)

        return gas_switches
