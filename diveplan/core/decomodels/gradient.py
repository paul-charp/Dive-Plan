from diveplan.core.pressure import Pressure
from diveplan.core import constants


class Gradient:
    def __init__(self, gfs: tuple[int]):
        super(Gradient, self).__init__()

        self.gf_lo: float = gfs[0] * 0.01
        self.gf_hi: float = gfs[1] * 0.01

    def getGF(
        self,
        P_amb: Pressure,
        P_deep: Pressure,
        P_atm: Pressure = constants.P_ATM,
    ) -> float:

        if P_deep - P_atm == 0:
            return self.gf_hi

        return self.gf_lo + float((P_amb - P_atm) / (P_deep - P_atm)) * (
            self.gf_hi - self.gf_lo
        )

    def __repr__(self) -> str:
        gf_lo: int = int(self.gf_lo * 100)
        gf_hi: int = int(self.gf_hi * 100)

        return f"{gf_lo}/{gf_hi}"
