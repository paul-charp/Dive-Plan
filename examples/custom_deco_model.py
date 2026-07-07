"""Write and register a custom decompression model.

A Bühlmann-family variant is a *table-only* subclass of the shared engine:
``NAME`` plus six coefficient tuples. Table shape is validated at class
definition time, so a mistyped table fails at import, not mid-dive. Models
register either via the ``diveplan.deco_models`` entry-point group (for
installable packages) or manually at runtime, as here.

Run from the repo root:

    uv run python examples/custom_deco_model.py

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from diveplan import Dive, DiveProfile
from diveplan.models.buhlmann import BuhlmannModel, ZHL16C
from diveplan.registry import registry

# ---------------------------------------------------------------------------
# 1. A custom variant: the five fastest ZHL-16C compartments only.
#    (A toy — real variants would transcribe a published, verified table.)
# ---------------------------------------------------------------------------


class FastTissues(BuhlmannModel):
    """Bühlmann engine over the five fastest ZHL-16C compartments."""

    NAME = "fast5"

    N2_HALF_TIMES = ZHL16C.N2_HALF_TIMES[:5]
    N2_A = ZHL16C.N2_A[:5]
    N2_B = ZHL16C.N2_B[:5]
    HE_HALF_TIMES = ZHL16C.HE_HALF_TIMES[:5]
    HE_A = ZHL16C.HE_A[:5]
    HE_B = ZHL16C.HE_B[:5]

    __slots__ = ()


# ---------------------------------------------------------------------------
# 2. Register it and look it up like any built-in model.
# ---------------------------------------------------------------------------

registry.register_model("fast5", FastTissues)

# The registry returns the class typed as the generic BaseDecoModel — use
# your own class for its specific API, the registry for discovery.
assert registry.model("fast5") is FastTissues
print(f"registered models : {sorted(registry.all_models())}")
print(f"fast5 compartments: {FastTissues().compartment_count}")
print()

# ---------------------------------------------------------------------------
# 3. Run the same dive under the custom model and the full ZHL-16C.
#    Slow compartments dominate long/deep exposure, so the truncated model
#    is (dangerously) optimistic on the long dive — which is the point of
#    having 16 of them.
# ---------------------------------------------------------------------------

for label, minutes in (("short (10 min)", 10), ("long (45 min)", 45)):
    profile = DiveProfile().descend_to("30 m").stay(minutes)
    full = Dive.run(profile, ZHL16C(gradient="30/70"))
    fast = Dive.run(profile, FastTissues(gradient="30/70"))
    t = profile.runtime
    print(
        f"30 m {label:<15} TTS: full ZHL-16C "
        f"{full.tts(t).total_seconds() / 60:5.1f} min | "
        f"fast5 {fast.tts(t).total_seconds() / 60:5.1f} min"
    )

print()
print("Entry-point registration for installable packages:")
print('  [project.entry-points."diveplan.deco_models"]')
print('  mymodel = "my_package.model:MyModel"')
