# diveplan/interfaces/cli.py

import argparse

from diveplan.core.dive import Dive, DiveStep
from diveplan.core.gas import GasCylinder, GasMixture


def main():
    """Main function for the command-line interface."""

    parser = argparse.ArgumentParser(description="Dive Planner CLI")

    # Dive profile arguments
    parser.add_argument("--depth", type=float, required=True, help="Target depth (m)")
    parser.add_argument("--time", type=float, required=True, help="Bottom time (min)")

    # Gas information arguments (example - you can expand this)

    parser.add_argument(
        "--o2", type=float, required=True, help="O2 fraction (e.g., 0.21 for air)"
    )
    parser.add_argument(
        "--he", type=float, default=0.0, help="He fraction (e.g., 0.35 for trimix)"
    )
    parser.add_argument(
        "--tank_volume", type=float, required=True, help="Tank volume in liters"
    )
    parser.add_argument(
        "--tank_pressure", type=float, required=True, help="Tank pressure in bars"
    )
    parser.add_argument(
        "--reserve_pressure", type=float, required=True, help="Reserve pressure in bars"
    )

    # Gradient factor arguments
    parser.add_argument(
        "--gf_low", type=int, default=100, help="Low gradient factor (0-100)"
    )
    parser.add_argument(
        "--gf_high", type=int, default=100, help="High gradient factor (0-100)"
    )

    args = parser.parse_args()

    # Create gas mixture
    try:
        gas_mixture = GasMixture(args.o2, args.he)
    except ValueError as e:
        print(f"Error: {e}")  # Handle invalid gas mixture error and exit
        return

    # Create gas cylinder
    gas_cylinder = GasCylinder(
        args.tank_volume, args.tank_pressure, gas_mixture, args.reserve_pressure
    )

    # Create dive steps
    steps = [
        DiveStep(0, 0, args.depth, gas_cylinder),  # Descent
        DiveStep(args.time, args.depth, args.depth, gas_cylinder),  # Bottom time
        DiveStep(0, args.depth, 0, gas_cylinder),  # Ascent to surface
    ]

    # Create dive object
    try:
        dive = Dive(
            steps, [gas_cylinder], (args.gf_low, args.gf_high)
        )  # Initialize with gas cylinder list
    except ValueError as e:
        print(f"Error creating dive: {e}")
        return

    # Calculate and report the dive plan
    dive.calculate_steps()
    dive.calculate_ascent()

    try:
        dive.report()
    except ValueError as e:
        print(f"Error during dive report: {e}")


# Entry point
if __name__ == "__main__":
    main()
