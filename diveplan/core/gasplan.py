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

    def best_gases(self, P_amb: Pressure, enforce_max_ppN2: bool = True) -> list[Gas]:
        """
        Get the best gases for the given ambient pressure.

        Arguments:
            P_amb -- _description_

        Returns:
            _description_
        """
        best_gases: list[Gas] = [
            gas for gas in self.gases if gas.is_breathable(P_amb, enforce_max_ppN2)
        ]

        best_gases.sort(
            key=lambda gas: (gas.ppO2(P_amb), gas.ppHe(P_amb)), reverse=True
        )

        return best_gases

    def get_next_gas_switches(
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
            best_gas = self.best_gases(P_amb)[0]

            if best_gas != current_gas:
                gas_switches.append((P_amb, best_gas))
                current_gas = best_gas

            P_amb = Pressure.from_depth(P_amb.to_depth() - stop_inc)

        return gas_switches

    def get_matching_gases(self, gas: Gas) -> list[Gas]:
        """
        Get all gases that match the given gas."
        """
        matching_gases: list[Gas] = []

        for g in self.gases:
            if g == gas:
                matching_gases.append(g)

        return matching_gases

    def consume_gases(self, divestep: DiveStep) -> None:

        gas: Gas = divestep.gas

        if gas not in self.gases:
            self.gases.append(gas)

        depth: float = divestep.average_depth
        time: float = divestep.time

        P_amb: Pressure = Pressure.from_depth(depth)
        gas.consume(P_amb, time)
