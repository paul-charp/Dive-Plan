from diveplan.utils import constants


class Compartment:
    """docstring for Compartment."""

    def __init__(
        self,
        h_N2,
        h_He,
        a_N2,
        b_N2,
        a_He,
        b_He,
        ppN2=constants.AIR_FN2,
        ppHe=constants.AIR_FHE,
        init_P_amb=constants.P_ATM,
    ):

        super(Compartment, self).__init__()

        # CONSTANTS
        self.h_N2 = h_N2
        self.h_He = h_He

        self.a_N2 = a_N2
        self.b_N2 = b_N2

        self.a_He = a_He
        self.b_He = b_He

        # Inert Gas Pressures
        self.ppN2 = ppN2 * init_P_amb
        self.ppHe = ppHe * init_P_amb

        # Tolerated Intert Gas Pressure
        self.P_tol = -1
