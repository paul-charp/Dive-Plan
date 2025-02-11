from diveplan.core.pressure import Pressure
from diveplan.core import constants


class Gas:
    """
    Gas Mixture Defined by fixed fraction of Oxygen, Nitrogen and Helium.
    Nitrogen makes up the rest of the gas.

    Args:
        frac_O2 (float=constants.AIR_FO2): Fraction of Oxygen (O2) in gas (0 to 1).
        frac_He (float=constants.AIR_FHE): Fraction of Helium (He) in gas (0 to 1).

    """

    def __init__(
        self, frac_O2: float = constants.AIR_FO2, frac_He: float = constants.AIR_FHE
    ):

        self.set_mix(frac_O2, frac_He)

        super(Gas, self).__init__()

    @staticmethod
    def _checkValidFrac(value: float):
        """
        Check if a value is between 0 and 1.

        Args:
            value (float): value to check

        """
        if value > 1.0 or value < 0:
            raise ValueError(f"Invalid Gas Fraction {value}")

    def set_mix(
        self, frac_O2: float = constants.AIR_FO2, frac_He: float = constants.AIR_FHE
    ):
        """
        Set the gas mixture from fraction of O2 and He.

        Args:
            frac_O2 (float=constants.AIR_FO2):
            frac_He (float=constants.AIR_FHE):

        """
        self._checkValidFrac(frac_O2)
        self._checkValidFrac(frac_He)

        frac_N2: float = 1 - (frac_O2 + frac_He)

        if frac_N2 < 0:
            raise ValueError("Total Gas fractions exceed 1")

        self._frac_O2 = frac_O2
        self._frac_He = frac_He
        self._frac_N2 = frac_N2

    # Properties Getters
    # To set gas mixes use 'set_mix()' method
    @property
    def frac_O2(self) -> float:
        return self._frac_O2

    @property
    def frac_N2(self) -> float:
        return self._frac_N2

    @property
    def frac_He(self) -> float:
        return self._frac_He

    def ppO2(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of O2 at a given ambiant pressure

        Args:
            P_amb (Pressure): Ambiant Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_O2)

    def ppN2(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of Nitrogen at a given ambiant pressure

        Args:
            P_amb (Pressure): Ambiant Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_N2)

    def ppHe(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of Helium at a given ambiant pressure

        Args:
            P_amb (Pressure): Ambiant Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_He)

    def equivalentNarcoticPressure(self, P_amb: Pressure) -> Pressure:
        """
        Gas equivalent narcotic pressure at a given ambiant pressure, compared to surface (atmospheric) pressure.

        Args:
            P_amb (Pressure): Ambiant Pressure

        Returns:
            Pressure

        """
        return self.ppN2(P_amb) / constants.AIR_FO2

    def maxOperatingPressure(
        self, max_ppO2: Pressure = constants.DECO_PP02
    ) -> Pressure:
        """
        Maximum operating pressure of gas mixture based on a maximum partial pressure of O2.

        Args:
            max_ppO2 (Pressure): Maximum partial pressure of O2

        Returns:
            Pressure

        """
        return Pressure(max_ppO2 / self.frac_O2)

    def minOperatinPressure(self, min_ppO2: Pressure = constants.MIN_PPO2) -> Pressure:
        """
        Minimum operating pressure of gas mixture based on a minimum partial pressure of O2.
        (Usefull for hypoxic mixes)

        Args:
            min_ppO2 (Pressure): Minimum partial pressure of O2

        Returns:
            Pressure

        """
        return Pressure(min_ppO2 / self.frac_O2)

    @staticmethod
    def make_best_mix(
        P_amb: Pressure, END: float = 30, ppO2: Pressure = Pressure(constants.DECO_PP02)
    ) -> "Gas":
        """
        Make the best Gas mix for a given ambient pressure, equivalent narcotic depth and partial pressure of oxygen.

        Args:
            P_amb (Pressure): Ambiant Pressure
            END (float): Equivalent narcotic depth
            ppO2 (Pressure): ppO2 of wanted Gas at ambiant pressure

        Returns:
            Gas

        """

        P_end = Pressure.from_depth(END)
        ppN2 = P_end * constants.AIR_FN2

        frac_O2 = ppO2 / P_amb
        frac_He = max(1 - ((ppN2 / P_amb) + frac_O2), 0)

        return Gas(round(frac_O2, 1), round(frac_He, 1))

    def __eq__(self, other: "Gas") -> bool:
        try:
            return (self.frac_O2 == other.frac_O2) and (self.frac_He == other.frac_He)
        except:
            return False

    def __repr__(self):
        if self.frac_He != constants.AIR_FHE:
            return f"Tx{int(self.frac_O2 * 100)}/{int(self.frac_He * 100)}"

        elif (self.frac_N2 == constants.AIR_FN2) and (
            self.frac_O2 == constants.AIR_FO2
        ):
            return "Air"

        else:
            return f"Nx{int(self.frac_O2 * 100)}"
