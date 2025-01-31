from diveplan.Gas import Gas
from diveplan.utils import constants
from diveplan.utils import utils


class GasPlan:
    """docstring for GasPlan."""

    def __init__(self, gases):
        super(GasPlan, self).__init__()
        self.gases: list[Gas] = gases

    def bestGases(self, P_amb):

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

    @staticmethod
    def makeBestMix(P_amb: float, END: float = 30, ppO2: float = 1.61362):

        P_end = utils.depth_to_P_amb(END)
        ppN2 = P_end * constants.AIR_FN2

        frac_O2 = ppO2 / P_amb
        frac_He = max(1 - ((ppN2 / P_amb) + frac_O2), 0)

        return Gas(round(frac_O2, 2), round(frac_He, 2))
