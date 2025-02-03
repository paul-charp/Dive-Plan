# diveplan/core/dive.py
from dataclasses import dataclass
from typing import List, Tuple

from diveplan.utils import constants, physics
from diveplan.core import gas
from diveplan.core.decomodels.abstract_deco_model import AbstractDecoModel
from diveplan.core.decomodels.zhl16c import ZHL16C


@dataclass
class DiveStep:
    """Represents a single step in a dive plan."""

    time: float
    start_depth: float
    end_depth: float
    gas_cylinder: gas.GasCylinder

    @property
    def type(self):  # Simplify step type management
        if self.end_depth > self.start_depth:
            return "descent"
        elif self.end_depth < self.start_depth:
            return "ascent"
        else:
            return "const"

    def get_ambient_pressure_at_sample(self, sample_time: float) -> float:
        """Calculates ambient pressure at a specific time during the dive step."""
        depth_at_sample = self.start_depth + (sample_time / self.time) * (
            self.end_depth - self.start_depth
        )
        return physics.depth_to_ambient_pressure(depth_at_sample)


class Dive:
    """Represents a planned dive, including descent, bottom time, and ascent."""

    def __init__(
        self,
        planned_steps: List[DiveStep],
        gas_cylinders: List[gas.GasCylinder],
        gradient_factors: Tuple[int, int] = (100, 100),
        sample_rate: float = 0.1,
    ):
        # DiveStep objects are now checked
        if any(step.time < 0 for step in planned_steps):
            raise ValueError("Time cannot be negative")

        self.steps: List[DiveStep] = planned_steps[
            :
        ]  # Copy the list to avoid modifying the original
        self.ascent: List[DiveStep] = []

        # Check for empty gas_cylinders list
        if not gas_cylinders:
            raise ValueError("gas_cylinders cannot be empty.")
        self.gas_cylinders = gas_cylinders

        self.gradient_factors = gradient_factors
        self.sample_rate = sample_rate

        self.deco_model: AbstractDecoModel = ZHL16C(
            self.gradient_factors, self.sample_rate
        )  # Create an instance of a decompression model

    def calculate_ascent(self):
        """Calculates the ascent profile based on the decompression model."""
        current_pressure = physics.depth_to_ambient_pressure(self.steps[-1].end_depth)
        surface_pressure = physics.depth_to_ambient_pressure(0.0)

        while current_pressure > surface_pressure:
            ceiling_pressure = physics.round_to_stop_pressure(
                self.deco_model.get_ceiling()
            )

            time = 1.0 if current_pressure == ceiling_pressure else 0.0

            ascent_step = DiveStep(
                time,
                physics.ambient_pressure_to_depth(current_pressure),
                physics.ambient_pressure_to_depth(ceiling_pressure),
                self.gas_cylinders[0],  # Use the first provided gas cylinder
            )
            self.ascent.append(ascent_step)

            self.deco_model.integrate_dive_step(ascent_step)
            current_pressure = physics.depth_to_ambient_pressure(ascent_step.end_depth)
        # Complete the last ascent to surface (to 0 pressure, which may not perfectly align with 0 depth due to rounding).
        if self.ascent[-1].end_depth != 0.0:
            last_ascent = DiveStep(
                0, self.ascent[-1].end_depth, 0.0, self.gas_cylinders[0]
            )
            self.ascent.append(last_ascent)

    def calculate_steps(self):
        """Calculates the dive steps based on depth changes and integrates with the deco model."""

        if (
            self.steps[0].start_depth != 0.0
        ):  # Assuming first step should always start from surface.
            self.steps.insert(
                0, DiveStep(0, 0, self.steps[0].start_depth, self.steps[0].gas_cylinder)
            )
            self.steps[1].time -= self.steps[0].time  # Correct the duration

        for step in self.steps:
            self.deco_model.integrate_dive_step(step)

    def report(self):
        """Prints a human-readable dive report."""

        symbol_map = {"descent": "▼", "ascent": "▲", "const": "-"}

        # Merge ascent steps into main steps
        for i, ascent_step in enumerate(self.ascent):
            if ascent_step.type == "const" and i > 0:
                previous_step = self.ascent[i - 1]
                if (
                    ascent_step.start_depth == previous_step.end_depth
                    and previous_step.type == "const"
                ):
                    self.steps[-1].time += ascent_step.time
                    continue

            self.steps.append(ascent_step)

        print(
            self.deco_model.name, self.gradient_factors
        )  # Use correct name from DecoModel

        runtime = 0
        for step in self.steps:
            symbol = symbol_map.get(step.type, "?")
            depth = int(round(step.end_depth))
            time = int(round(step.time))
            runtime += time

            print(f"{symbol} {depth}m {time}min {runtime}min")

    def select_best_gas_cylinder(self, depth: float) -> gas.GasCylinder | None:
        """Selects best gas cylinder based on depth and constraints."""

        ambient_pressure = physics.depth_to_ambient_pressure(depth)

        suitable_cylinders = []

        for cylinder in self.gas_cylinders:
            mixture = cylinder.gas_mixture

            if (
                mixture.max_operating_pressure() >= ambient_pressure
                and mixture.partial_pressure("O2", ambient_pressure)
                >= constants.MIN_PPO2
            ):
                suitable_cylinders.append(cylinder)

        if not suitable_cylinders:
            return None  # No suitable gas

        # Find cylinder with highest ppO2, then highest ppHe among available gases, using the current_pressure
        best_cylinder = sorted(
            suitable_cylinders,
            key=lambda cyl: (
                cyl.gas_mixture.partial_pressure("O2", ambient_pressure),
                cyl.gas_mixture.partial_pressure("He", ambient_pressure),
            ),
            reverse=True,
        )[0]

        # Check remaining gas before suggesting the cylinder (raise error if no gas remains)
        if best_cylinder.current_pressure <= 0:
            raise ValueError("No gas remaining in the suggested cylinder.")

        return best_cylinder

    def add_optimal_gas_cylinder(
        self,
        volume: float,
        working_pressure: float,
        end_depth: float,
        target_ppo2: float = constants.DECO_PPO2,
    ):
        """Adds a cylinder with optimal gas mix to the gas list."""
        ambient_pressure = physics.depth_to_ambient_pressure(end_depth)
        end_pressure = physics.depth_to_ambient_pressure(end_depth)
        ppn2 = end_pressure * constants.AIR_FN2

        frac_o2 = target_ppo2 / ambient_pressure
        frac_he = max(1.0 - (ppn2 / ambient_pressure + frac_o2), 0.0)

        if frac_o2 > 1.0:
            raise ValueError(
                "Impossible to create optimal mix: required o2 fraction would be above 100%."
            )

        mix = gas.GasMixture(frac_o2, frac_he)  # Create the GasMixture
        cylinder = gas.GasCylinder(
            volume, working_pressure, mix
        )  # Create the GasCylinder
        self.gas_cylinders.append(cylinder)
