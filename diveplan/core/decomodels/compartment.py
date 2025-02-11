from diveplan.core import constants
from diveplan.core.pressure import Pressure


class Compartment:
    """docstring for Compartment."""

    def __init__(
        self,
        h_N2: float,
        h_He: float,
        a_N2: float,
        b_N2: float,
        a_He: float,
        b_He: float,
        ppN2: Pressure = Pressure(constants.AIR_FN2),
        ppHe: Pressure = Pressure(constants.AIR_FHE),
        init_P_amb: Pressure = Pressure(constants.P_ATM),
    ):

        super(Compartment, self).__init__()

        # CONSTANTS
        self.h_N2: float = h_N2
        self.h_He: float = h_He

        self.a_N2: float = a_N2
        self.b_N2: float = b_N2

        self.a_He: float = a_He
        self.b_He: float = b_He

        # Inert Gas Pressures
        self.ppN2: Pressure = ppN2 * init_P_amb
        self.ppHe: Pressure = ppHe * init_P_amb

        # Tolerated Intert Gas Pressure
        self.P_tol: Pressure = None
