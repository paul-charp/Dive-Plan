from diveplan.DecoModels.AbstractDecoModel import AbstractDecoModel
from diveplan.DecoModels.Compartment import Compartment
from diveplan.DecoModels.Gradient import Gradient
from diveplan.utils import constants
from diveplan.Gas import Gas
from diveplan.Dive import DiveStep


class ZHL16C_GF(AbstractDecoModel):

    MODEL_CONSTANTS = [
        {
            "h_N2": 5.0,
            "a_N2": 1.1696,
            "b_N2": 0.5578,
            "h_He": 1.88,
            "a_He": 1.6189,
            "b_He": 0.4770,
        },
        {
            "h_N2": 8.0,
            "a_N2": 1.0000,
            "b_N2": 0.6514,
            "h_He": 3.02,
            "a_He": 1.3830,
            "b_He": 0.5747,
        },
        {
            "h_N2": 12.5,
            "a_N2": 0.8618,
            "b_N2": 0.7222,
            "h_He": 4.72,
            "a_He": 1.1919,
            "b_He": 0.6527,
        },
        {
            "h_N2": 18.5,
            "a_N2": 0.7562,
            "b_N2": 0.7825,
            "h_He": 6.99,
            "a_He": 1.0458,
            "b_He": 0.7223,
        },
        {
            "h_N2": 27.0,
            "a_N2": 0.6200,
            "b_N2": 0.8126,
            "h_He": 10.21,
            "a_He": 0.9220,
            "b_He": 0.7582,
        },
        {
            "h_N2": 38.3,
            "a_N2": 0.5043,
            "b_N2": 0.8434,
            "h_He": 14.48,
            "a_He": 0.8205,
            "b_He": 0.7957,
        },
        {
            "h_N2": 54.3,
            "a_N2": 0.4410,
            "b_N2": 0.8693,
            "h_He": 20.53,
            "a_He": 0.7305,
            "b_He": 0.8279,
        },
        {
            "h_N2": 77.0,
            "a_N2": 0.4000,
            "b_N2": 0.8910,
            "h_He": 29.11,
            "a_He": 0.6502,
            "b_He": 0.8553,
        },
        {
            "h_N2": 109.0,
            "a_N2": 0.3750,
            "b_N2": 0.9092,
            "h_He": 41.20,
            "a_He": 0.5950,
            "b_He": 0.8757,
        },
        {
            "h_N2": 146.0,
            "a_N2": 0.3500,
            "b_N2": 0.9222,
            "h_He": 55.19,
            "a_He": 0.5545,
            "b_He": 0.8903,
        },
        {
            "h_N2": 187.0,
            "a_N2": 0.3295,
            "b_N2": 0.9319,
            "h_He": 70.69,
            "a_He": 0.5333,
            "b_He": 0.8997,
        },
        {
            "h_N2": 239.0,
            "a_N2": 0.3065,
            "b_N2": 0.9403,
            "h_He": 90.34,
            "a_He": 0.5189,
            "b_He": 0.9073,
        },
        {
            "h_N2": 305.0,
            "a_N2": 0.2835,
            "b_N2": 0.9477,
            "h_He": 115.29,
            "a_He": 0.5181,
            "b_He": 0.9122,
        },
        {
            "h_N2": 390.0,
            "a_N2": 0.2610,
            "b_N2": 0.9544,
            "h_He": 147.42,
            "a_He": 0.5176,
            "b_He": 0.9171,
        },
        {
            "h_N2": 498.0,
            "a_N2": 0.2480,
            "b_N2": 0.9602,
            "h_He": 188.24,
            "a_He": 0.5172,
            "b_He": 0.9217,
        },
        {
            "h_N2": 635.0,
            "a_N2": 0.2327,
            "b_N2": 0.9653,
            "h_He": 240.03,
            "a_He": 0.5119,
            "b_He": 0.9267,
        },
    ]

    NAME = "Buhlmann ZHL16-C + GF"

    def __init__(self, GFs, samplerate):
        super(ZHL16C_GF, self).__init__(samplerate)

        # Initialize Compartments
        self.compartments = []

        for compConsts in self.MODEL_CONSTANTS:
            compartment = Compartment(
                compConsts["h_N2"],
                compConsts["h_He"],
                compConsts["a_N2"],
                compConsts["b_N2"],
                compConsts["a_He"],
                compConsts["b_He"],
            )

            self.compartments.append(compartment)

        self.GFs = Gradient(GFs)
        self.P_deep = constants.P_ATM

    # Model Physics Functions
    @staticmethod
    def __calcInertGasPressure(P_init, P_gas, dtime, htime):
        return P_init + (P_gas - P_init) * (1 - 2 ** (-dtime / htime))

    @staticmethod
    def __calcInertGasLimit(ppN2, ppHe, a_N2, b_N2, a_He, b_He, P_amb, GF):

        P_inert = ppN2 + ppHe
        r = ppHe / P_inert

        a = a_N2 * (1 - r) + a_He * r
        b = b_N2 * (1 - r) + b_He * r

        P_tol = (P_inert - a) * b
        return P_amb + GF * (P_tol - P_amb)

    def __updateCompartment(
        self, compartment: Compartment, gas: Gas, P_amb: float, time: float
    ) -> Compartment:

        gas_ppN2 = gas.ppN2(P_amb)
        gas_ppHe = gas.ppHe(P_amb)

        # Update Inert Gas Pressures
        compartment.ppN2 = self.__calcInertGasPressure(
            compartment.ppN2, gas_ppN2, time, compartment.h_N2
        )
        compartment.ppHe = self.__calcInertGasPressure(
            compartment.ppHe, gas_ppHe, time, compartment.h_He
        )

        # Calc GF at P_amb
        gf = self.GFs.getGF(P_amb, self.P_deep)

        # Update Inert Gas Limit
        compartment.P_tol = self.__calcInertGasLimit(
            compartment.ppN2,
            compartment.ppHe,
            compartment.a_N2,
            compartment.b_N2,
            compartment.a_He,
            compartment.b_He,
            P_amb,
            gf,
        )

        return compartment

    def _integrateModel(self, divestep: DiveStep, s: float):

        P_amb: float = divestep.get_P_amb_at_sample(s)
        self.P_deep = max(self.P_deep, P_amb)

        for compartment in self.compartments:
            self.__updateCompartment(
                compartment, divestep.gas[0], P_amb, self.samplerate
            )

    def getCeiling(self) -> float:
        ceiling: float = -1

        for compartment in self.compartments:
            ceiling = max(ceiling, compartment.P_tol)

        return ceiling
