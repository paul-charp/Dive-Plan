"""Batch simulation: compare deco models across a grid of dives.

The second use case diveplan is designed for: run many dives
programmatically and compare algorithms, conservatism settings, or
conditions. Profiles are cheap, models are independent, and scoped config
overrides are isolated per thread/async task, so grids parallelize safely.

Run from the repo root:

    uv run python examples/batch_model_comparison.py

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from collections.abc import Callable
from typing import Any

from diveplan import BaseDecoModel, Dive, DiveConfig, DiveProfile, GasPlan
from diveplan.registry import registry

# Models are plugins — look them up by registry name:
ZHL16C = registry.model("zhl16c")
VpmB = registry.model("vpmb")

CARRIED = GasPlan(["air", "ean50"])

# Model factories, not instances: each dive gets a fresh model.
MODELS = {
    "ZHL GF 30/70": lambda: ZHL16C(gradient="30/70"),
    "ZHL GF 50/80": lambda: ZHL16C(gradient="50/80"),
    "ZHL raw     ": lambda: ZHL16C(),
    "VPM-B +2    ": lambda: VpmB(conservatism=2),
}

DEPTHS_M = (30, 40, 50)
BOTTOM_MINUTES = (15, 20, 25)


def tts_minutes(
    depth_m: float,
    bottom_min: float,
    make_model: Callable[[], BaseDecoModel[Any]],
) -> float:
    """Time-to-surface (minutes) at the end of the given bottom plan."""
    profile = DiveProfile().descend_to(depth_m).stay(bottom_min)
    dive = Dive.run(profile, make_model())
    return dive.tts(profile.runtime, gas_plan=CARRIED).total_seconds() / 60


def print_grid(title: str) -> None:
    print(title)
    header = "  depth  bottom " + "".join(f"{name:>14}" for name in MODELS)
    print(header)
    for depth in DEPTHS_M:
        for minutes in BOTTOM_MINUTES:
            cells = "".join(
                f"{tts_minutes(depth, minutes, make):>14.1f}"
                for make in MODELS.values()
            )
            print(f"  {depth:>4} m  {minutes:>3} min{cells}")
    print()


# Sea-level, salt water (factory defaults).
print_grid("TTS (min) at end of bottom time — sea level, salt water")

# The same grid at altitude in fresh water: a scoped override changes what
# every depth string and ceiling means, without touching global state.
mountain_lake = DiveConfig()
mountain_lake.physics.surface_pressure_mbar = 800  # ~2000 m elevation
mountain_lake.physics.water_density = 1.0
with mountain_lake:
    print_grid("TTS (min) — mountain lake (800 mbar surface, fresh water)")

print("Scoped overrides are ContextVar-based: run grids in a thread pool or")
print("under asyncio and each task keeps its own physics/planning config.")
