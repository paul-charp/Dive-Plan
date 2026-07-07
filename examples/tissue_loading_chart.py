"""ASCII visualization of a dive: depth, ceiling, and tissue loading.

Demonstrates the query side of a :class:`Dive` — ``tissue_series`` for the
tension curve, ``ceiling_at`` for the ceiling, timeline methods for depth —
with no plotting dependency. Swap the ASCII rendering for matplotlib and
the same queries feed a real chart.

Run from the repo root:

    uv run python examples/tissue_loading_chart.py

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from datetime import timedelta

from diveplan import Dive, DiveProfile, GasPlan
from diveplan.registry import registry

# Models are plugins — look them up by registry name:
ZHL16C = registry.model("zhl16c")

WIDTH = 46  # characters for the 0..max-depth axis
SAMPLE_MINUTES = 2

carried = GasPlan(["air", "ean50"])
bottom = DiveProfile().descend_to("40 m").stay(25)
dive = Dive.run(bottom, ZHL16C(gradient="30/70")).with_ascent(carried)

profile = dive.profile
max_depth = max(s.start_pressure.depth_m for s in profile.segments)


def column(depth_m: float) -> int:
    """Map a depth to a character column (0 = surface, WIDTH = max depth)."""
    return round(WIDTH * max(0.0, depth_m) / max_depth)


print(f"depth/ceiling over time — {dive.model_name}, EAN50 carried")
print("'#' diver depth, '~' deco ceiling, leading-tissue N2 tension at right")
print()
print("  time    0 m" + " " * (WIDTH - 8) + f"{max_depth:.0f} m")

for t, state in dive.tissue_series(timedelta(minutes=SAMPLE_MINUTES)):
    depth = profile.pressure_at(t).depth_m
    ceiling = dive.ceiling_at(t).depth_m

    row = [" "] * (WIDTH + 1)
    if ceiling > 0:
        row[column(ceiling)] = "~"
    row[column(depth)] = "#"

    n2 = state.tissues[0][0]  # fastest compartment, mbar
    minutes = t.total_seconds() / 60
    print(f"  {minutes:5.0f}  |{''.join(row)}|  {n2:5.0f} mbar")

print()
print(f"total runtime: {profile.runtime.total_seconds() / 60:.1f} min")
