from diveplan.utils import constants


class Gas:
    def __init__(
        self, frac_O2: float = constants.AIR_FO2, frac_He: float = constants.AIR_FHE
    ):

        super(Gas, self).__init__()

        self.frac_O2 = frac_O2
        self.frac_He = frac_He
        self.frac_N2 = 1 - (frac_O2 + frac_He)

        self.consumption: float = 0

    def __repr__(self):
        if self.frac_He != constants.AIR_FHE:
            return f"Tx{self.frac_O2 * 100}/{self.frac_He * 100}"

        elif (self.frac_N2 == constants.AIR_FN2) and (
            self.frac_O2 == constants.AIR_FO2
        ):
            return "Air"

        else:
            return f"Nx{self.frac_O2 * 100}"

    def ppO2(self, P_amb: float) -> float:
        return P_amb * self.frac_O2

    def ppN2(self, P_amb: float) -> float:
        return P_amb * self.frac_N2

    def ppHe(self, P_amb: float) -> float:
        return P_amb * self.frac_He

    def equivalentNarcoticPressure(self, P_amb: float) -> float:
        return self.ppN2(P_amb) / constants.AIR_FO2

    def maxOperatingPressure(self, max_ppO2: float = 1.61362):
        return max_ppO2 / self.frac_O2

    def consume(self, P_amb: float, time: float, sac: float):
        self.consumption += P_amb * time * sac
