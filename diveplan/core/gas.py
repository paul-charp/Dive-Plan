from typing import Optional

from diveplan.core import constants
from diveplan.core.pressure import Pressure


class Gas:
    """
    Gas Mixture Defined by fixed fraction of Oxygen, Nitrogen and Helium.
    Nitrogen makes up the rest of the gas.

    Args:
        frac_O2 (float=constants.AIR_FO2): Fraction of Oxygen (O2) in gas (0 to 1).
        frac_He (float=constants.AIR_FHE): Fraction of Helium (He) in gas (0 to 1).

    """

    def __init__(
        self, frac_O2: Optional[float] = None, frac_He: Optional[float] = None
    ) -> None:

        if frac_O2 is None:
            frac_O2 = constants.AIR_FO2

        if frac_He is None:
            frac_He = constants.AIR_FHE

        self.set_mix(frac_O2, frac_He)
        self._consumption: float = 0

        super(Gas, self).__init__()

    @classmethod
    def from_name(cls, gas_name: str) -> "Gas":

        gas_name = gas_name.lower()

        if gas_name == "air":
            frac_O2 = constants.AIR_FO2
            frac_He = constants.AIR_FHE

        elif gas_name.startswith("nx"):
            frac_O2 = float(gas_name[2:]) / 100.0
            frac_He = 0.0

        elif gas_name.startswith("tx"):
            frac_O2 = float(gas_name[2:3]) / 100.0
            frac_He = float(gas_name[4:5]) / 100.0

        else:
            raise ValueError("Not a correct gas name")

        return cls(frac_O2, frac_He)

    @staticmethod
    def _checkValidFrac(value: float) -> None:
        """
        Check if a value is between 0 and 1.

        Args:
            value (float): value to check

        """
        if value > 1.0 or value < 0:
            raise ValueError(f"Invalid Gas Fraction {value}")

    def set_mix(self, frac_O2: float, frac_He: float) -> None:
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

    @property
    def consumption(self) -> float:
        return self._consumption

    @property
    def name(self) -> str:
        if self.frac_He != constants.AIR_FHE:
            return f"Tx{int(self.frac_O2 * 100)}/{int(self.frac_He * 100)}"

        elif (self.frac_N2 == constants.AIR_FN2) and (
            self.frac_O2 == constants.AIR_FO2
        ):
            return "Air"

        else:
            return f"Nx{int(self.frac_O2 * 100)}"

    def consume(self, P_amb: Pressure, time: float, sac: float = constants.BOT_SAC):
        if time < 0:
            raise ValueError("Time cannot be negative !")

        if sac < 0:
            raise ValueError("SAC Rate cannot be negative !")

        self._consumption += P_amb * time * sac

    def ppO2(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of O2 at a given ambient pressure

        Args:
            P_amb (Pressure): Ambient Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_O2)

    def ppN2(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of Nitrogen at a given ambient pressure

        Args:
            P_amb (Pressure): Ambient Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_N2)

    def ppHe(self, P_amb: Pressure) -> Pressure:
        """
        Gas partial pressure of Helium at a given ambient pressure

        Args:
            P_amb (Pressure): Ambient Pressure

        Returns:
            Pressure

        """
        return Pressure(P_amb * self.frac_He)

    def equivalentNarcoticPressure(self, P_amb: Pressure) -> Pressure:
        """
        Gas equivalent narcotic pressure at a given ambient pressure, compared to surface (atmospheric) pressure.

        Args:
            P_amb (Pressure): Ambient Pressure

        Returns:
            Pressure

        """
        return self.ppN2(P_amb) / constants.AIR_FO2

    def maxOperatingPressure(
        self, max_ppO2: Pressure = Pressure(constants.DECO_PP02)
    ) -> Pressure:
        """
        Maximum operating pressure of gas mixture based on a maximum partial pressure of O2.

        Args:
            max_ppO2 (Pressure): Maximum partial pressure of O2

        Returns:
            Pressure

        """
        return Pressure(max_ppO2 / self.frac_O2)

    def minOperatingPressure(
        self, min_ppO2: Pressure = Pressure(constants.MIN_PPO2)
    ) -> Pressure:
        """
        Minimum operating pressure of gas mixture based on a minimum partial pressure of O2.
        (Useful for hypoxic mixes)

        Args:
            min_ppO2 (Pressure): Minimum partial pressure of O2

        Returns:
            Pressure

        """
        return Pressure(min_ppO2 / self.frac_O2)

    def is_breathable(self, P_amb: Pressure, enforce_max_ppN2: bool = True) -> bool:
        """
        Check if the gas is breathable at a given ambient pressure.
        """
        if enforce_max_ppN2:
            if self.ppN2(P_amb) > Pressure(constants.MAX_PPN2):
                return False

        return self.minOperatingPressure() <= P_amb <= self.maxOperatingPressure()

    @staticmethod
    def make_best_mix(
        depth: float, END: float = 30, ppO2: Optional[Pressure] = None
    ) -> "Gas":
        """
        Make the best Gas mix for a given depth, equivalent narcotic depth and partial pressure of oxygen.

        Args:
            depth (float): Depth at which this gas will be breathed
            END (float): Equivalent narcotic depth
            ppO2 (Pressure): ppO2 of wanted Gas at ambient pressure, default to constants.DECO_PPO2

        Returns:
            Gas

        """

        if ppO2 is None:
            ppO2 = Pressure(constants.DECO_PP02)

        P_amb = Pressure.from_depth(depth)
        P_end = Pressure.from_depth(END)
        ppN2 = P_end * constants.AIR_FN2

        frac_O2 = float(ppO2 / P_amb)
        frac_He = max(1 - ((ppN2 / P_amb) + frac_O2), 0)

        return Gas(round(frac_O2, 1), round(frac_He, 1))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Gas):
            return (self.frac_O2 == other.frac_O2) and (self.frac_He == other.frac_He)
        return False

    def __repr__(self) -> str:
        return self.name
