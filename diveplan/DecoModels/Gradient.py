from ..utils import constants


class Gradient():
    """docstring for Gradient."""
    def __init__(self, gfs: tuple[int]):
        super(Gradient, self).__init__()
        
        self.gf_lo: int = gfs[0]
        self.gf_hi: int = gfs[1]

    def getGF(self, P_amb: float, P_deep: float, P_atm=constants.P_ATM) -> float:
        return self.gf_lo + ((P_amb - P_atm) / (P_deep - P_atm)) * (self.gf_hi - self.gf_lo)