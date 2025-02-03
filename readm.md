# Dive Plan

This Python project provides tools for planning dives, including calculating decompression stops, gas consumption, and generating dive profiles.

## Features

* **Decompression Modeling:**  Implements the ZHL16C_GF decompression model for calculating safe ascent profiles.  Supports configurable gradient factors.
* **Gas Management:**  Handles multiple gas mixtures (including air and trimix) and calculates partial pressures, equivalent narcotic depths, and maximum operating pressures.  Can suggest optimal gas mixes based on depth and desired partial pressure of oxygen (PPO2).
* **Dive Planning:**  Allows the creation of dive plans with multiple steps, including descent, bottom time, and ascent.  Calculates ascent profiles and integrates with the decompression model.
* **Dive Reporting:** Generates a human-readable dive report summarizing the dive profile, depths, times, and gas usage.


## Classes

* **`Gas`:** Represents a breathing gas mixture, storing fractions of oxygen, nitrogen, and helium.  Provides methods for calculating partial pressures, equivalent narcotic depths, and maximum operating pressures.
* **`GasPlan`:**  Manages collections of `Gas` objects and provides methods for selecting the optimal gas for a given depth based on constraints like maximum operating pressure and minimum PPO2. Can also generate optimal gas mixes based on depth and target PPO2.
* **`DiveStep`:** Represents a single step in a dive plan, including start depth, end depth, time, and gas used. Calculates the type of step (descent, ascent, or constant depth) automatically.
* **`Dive`:**  Represents a complete dive plan, composed of multiple `DiveStep` objects.  Integrates with the `ZHL16C_GF` decompression model to calculate ascent profiles and generates a dive report.


## Usage Example (Illustrative)

```python
from diveplan.Dive import Dive, DiveStep
from diveplan.Gas import Gas

# Define dive steps
steps = [
    DiveStep(0, 0, 20, [Gas()]),  # Descent to 20m
    DiveStep(20, 20, 20, [Gas()]), # 20 minutes at 20m
    DiveStep(0, 20, 5, [Gas()])  # Ascent to 5m
]


# Create a dive object
dive = Dive(steps)


# Calculate the ascent plan
dive.calculate_steps()
dive.calculate_ascent()

# Generate the dive report
dive.report()


# Create custom gases with gradient factors for a dive to 40m during 20min, with a TX 18/45 gas for the descent and bottom, and a Nx50 for the ascent
tx_18_45 = Gas(frac_O2=0.18, frac_He=0.45)
nx_50 = Gas(frac_O2=0.5)
gases = [tx_18_45, nx_50]
gradient_factors = (85, 40)

# Define dive steps
steps = [
    DiveStep(0, 0, 40, gases),  # Descent to 40m with Tx18/45
    DiveStep(20, 40, 40, gases), # 20 minutes at 40m with Tx18/45
    DiveStep(0, 40, 0, [nx_50])  # Ascent to surface with Nx50
]

# Create dive
dive = Dive(steps, gradient_factors=gradient_factors, gases=gases) # Initialize with gradient factors and gases
dive.calculate_steps()
dive.calculate_ascent()

# Generate the dive report
dive.report()
