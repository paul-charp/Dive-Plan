from diveplan.core.decomodels.abstract_deco_model import AbstractDecoModel
from diveplan.utils.constants import AIR_FN2, AIR_FHE, P_ATM


class ZHL16C(AbstractDecoModel):
    name = "ZHL-16C"  # Consistent naming

    # Class constants now define half-times and a/b values for N2 and He separately
    #   This improves clarity and simplifies calculation logic.

    # Class constants
    _MODEL_CONSTANTS: list[dict] = [
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

    def __init__(self, gradient_factors: tuple[int, int], sample_rate: float):
        super().__init__(sample_rate)

        # Convert GFs to fractions (0-1) and validate
        gf_low, gf_high = gradient_factors

        if not (0 <= gf_low <= 100 and 0 <= gf_high <= 100):
            raise ValueError("Gradient factors must be between 0 and 100.")

        self.gf_low = gf_low / 100.0
        self.gf_high = gf_high / 100.0

        # Initialize compartments – now using a more structured approach
        self.compartments: list[dict] = []  # Store as list of dict
        for data in self._MODEL_CONSTANTS:
            self.compartments.append(
                {
                    "n2_pressure": AIR_FN2 * P_ATM,
                    "he_pressure": AIR_FHE * P_ATM,
                    "n2_half_time": data["n2_half_time"],
                    "he_half_time": data["he_half_time"],
                    "n2_a": data["n2_a"],
                    "n2_b": data["n2_b"],
                    "he_a": data["he_a"],
                    "he_b": data["he_b"],
                    "tolerated_pressure": -1.0,  # Initialize tolerated pressure
                }
            )

        self.deepest_pressure = P_ATM

    def _integrate_model(self, dive_step, sample_time: float):
        ambient_pressure = dive_step.get_ambient_pressure_at_sample(sample_time)
        self.deepest_pressure = max(self.deepest_pressure, ambient_pressure)
        gas_mixture = dive_step.gas_cylinder.gas_mixture  # GasMixture

        for compartment in self.compartments:
            compartment["n2_pressure"] = self._calculate_inert_gas_pressure(
                compartment["n2_pressure"],
                gas_mixture.n2_fraction * ambient_pressure,  # Using GasMixture
                self.sample_rate,
                compartment["n2_half_time"],
            )

            compartment["he_pressure"] = self._calculate_inert_gas_pressure(
                compartment["he_pressure"],
                gas_mixture.he_fraction * ambient_pressure,  # Using GasMixture
                self.sample_rate,
                compartment["he_half_time"],
            )
            current_gf = self._calculate_gradient_factor(ambient_pressure)
            compartment["tolerated_pressure"] = self._calculate_tolerated_pressure(
                compartment, gas_mixture, ambient_pressure, current_gf
            )  # Use _calculate_tolerated_pressure

    def _calculate_tolerated_pressure(
        self, compartment, ambient_pressure, gf
    ):  # Corrected parameters' name
        return self._calculate_inert_gas_limit(
            compartment["n2_pressure"],
            compartment["he_pressure"],
            compartment["n2_a"],
            compartment["n2_b"],
            compartment["he_a"],
            compartment["he_b"],
            ambient_pressure,
            gf,
        )

    def get_ceiling(self) -> float:
        ceiling = 0.0  # Initialize ceiling
        for compartment in self.compartments:
            ceiling = max(
                ceiling, compartment["tolerated_pressure"]
            )  # Use updated compartment structure
        return ceiling

    # Private helper methods (unchanged logic, renamed for consistency)
    @staticmethod
    def _calculate_inert_gas_pressure(
        initial_pressure, gas_pressure, delta_time, half_time
    ):
        return initial_pressure + (gas_pressure - initial_pressure) * (
            1 - 2 ** (-delta_time / half_time)
        )

    @staticmethod
    def _calculate_inert_gas_limit(
        pp_n2, pp_he, a_n2, b_n2, a_he, b_he, ambient_pressure, gf
    ):
        P_inert = pp_n2 + pp_he
        r = pp_he / P_inert

        a = a_n2 * (1 - r) + a_he * r
        b = b_n2 * (1 - r) + b_he * r

        P_tol = (P_inert - a) * b
        return ambient_pressure + gf * (P_tol - ambient_pressure)

    def _calculate_gradient_factor(self, ambient_pressure):

        return self.gf_low + (
            (ambient_pressure - P_ATM) / (self.deepest_pressure - P_ATM)
        ) * (self.gf_high - self.gf_low)
