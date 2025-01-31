from diveplan.utils import constants


class Gradient:
    """docstring for Gradient."""

    def __init__(self, gfs: tuple[int]):
        super(Gradient, self).__init__()

        self.gf_lo: float = gfs[0] * 0.01
        self.gf_hi: float = gfs[1] * 0.01

    def getGF(self, P_amb: float, P_deep: float, P_atm=constants.P_ATM) -> float:

        if P_deep - P_atm == 0:
            return self.gf_hi

        return self.gf_lo + ((P_amb - P_atm) / (P_deep - P_atm)) * (
            self.gf_hi - self.gf_lo
        )
