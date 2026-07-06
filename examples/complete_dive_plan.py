"""Complete diveplan walkthrough — plan a 40 m trimix-free deco dive on air
with an EAN50 deco gas, end to end.

Run from the repo root:

    uv run python examples/complete_dive_plan.py

Covers: configuration, gases, fluent profile building, running deco models,
result queries (ceiling, TTS, tissue loading), ascent planning, model
comparison, and JSON serialization.

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from datetime import timedelta

from diveplan import (
    DiveConfig,
    DiveProfile,
    DiveResult,
    Gas,
    GasPlan,
    Pressure,
    plan_ascent,
)
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.models.buhlmann.common import Gradient
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.models.vpm.model import VpmB


def minutes(td: timedelta) -> str:
    return f"{td.total_seconds() / 60:5.1f} min"


def describe(segment: DiveSegment, runtime: timedelta) -> str:
    depth_from = segment.start_pressure.depth_m
    depth_to = segment.end_pressure.depth_m
    if segment.kind is SegmentKind.Constant.GAS_SWITCH:
        what = f"switch to {segment.gas}"
    elif depth_from == depth_to:
        what = f"hold {depth_from:4.0f} m"
    else:
        what = f"{depth_from:4.0f} m -> {depth_to:3.0f} m"
    return (
        f"  {minutes(runtime):>9}  {what:<22} {minutes(segment.duration):>9}"
        f"   {segment.gas.name:<6} {segment.kind.name}"
    )


# ---------------------------------------------------------------------------
# 1. Configuration — one shared config; mutate it, or override it in a scope
# ---------------------------------------------------------------------------
print("=== 1. Configuration ===")

cfg = DiveConfig.current()
print(f"ascent rate     : {cfg.planning.ascent_rate} m/min")
print(
    f"stop grid       : every {cfg.planning.stop_increment_m} m, "
    f"last at {cfg.planning.last_stop_m} m"
)
print(f"deco ppO2 limit : {cfg.gas.deco_ppo2_bar} bar")

# Scoped override (fresh water, altitude...) — nestable, thread-safe:
sea_level_bar = Pressure.from_depth_m(30).bar

altitude = DiveConfig()
altitude.physics.surface_pressure_mbar = 900
altitude.physics.water_density = 1.0
with altitude:
    altitude_bar = Pressure.from_depth_m(30).bar
print(
    f"30 m of water column = {altitude_bar:.3f} bar at altitude/fresh water, "
    f"{sea_level_bar:.3f} bar at sea level/salt"
)
print()

# ---------------------------------------------------------------------------
# 2. Gases — named constructors, parsing, limits, best mix
# ---------------------------------------------------------------------------
print("=== 2. Gases ===")

air = Gas.air()
ean50 = Gas.from_name("ean50")  # or Gas.nitrox(0.50)

print(f"EAN50 MOD @1.6 bar : {ean50.mod(ppo2_bar=1.6).depth_m:.1f} m")
print(f"best mix for 30 m  : {air.best_mix(30)}")
print(f"air END at 40 m    : {air.end(Pressure.from_depth_m(40)).depth_m:.1f} m")
print()

# ---------------------------------------------------------------------------
# 3. Build the bottom portion of the dive — fluent, policy-checked
# ---------------------------------------------------------------------------
print("=== 3. Profile (bottom portion) ===")

bottom = (
    DiveProfile()  # RAISE policy: every seam validated as you build
    .descend_to("40 m")  # air by default, configured descent rate
    .stay(25)  # 25 min bottom time
)
print(f"segments: {bottom.segment_count}, runtime: {minutes(bottom.runtime)}")
print(
    f"depth at t=10 min : {bottom.pressure_at(10).depth_m:.1f} m on {bottom.gas_at(10)}"
)
print()

# ---------------------------------------------------------------------------
# 4. Run a deco model over it and query the result
# ---------------------------------------------------------------------------
print("=== 4. DiveResult queries (ZHL-16C, GF 30/70) ===")

zhl = ZHL16C(gradient=Gradient(0.3, 0.7))
carried = GasPlan([air, ean50])

result = DiveResult.run(bottom, zhl)

for t in (5, 15, bottom.runtime):
    ceiling = result.ceiling_at(t)
    depth = max(0.0, ceiling.depth_m)
    label = minutes(t if isinstance(t, timedelta) else timedelta(minutes=t))
    print(
        f"t={label}: ceiling {depth:4.1f} m   "
        f"TTS {minutes(result.tts(t, gas_plan=carried))}"
    )

# Tissue loading over time (leading compartment) — feed this to a plot:
print("leading-compartment N2 tension (mbar):")
for t, state in result.tissue_series(timedelta(minutes=9)):
    print(f"  t={minutes(t)}: {state.tissues[0][0]:6.0f}")
print()

# ---------------------------------------------------------------------------
# 5. Plan the deco ascent and assemble the full dive
# ---------------------------------------------------------------------------
print("=== 5. Ascent plan ===")

end = bottom.runtime
ascent = plan_ascent(
    result.model_at(end),  # model positioned at end of bottom time
    start_pressure=bottom.pressure_at(end),
    gas=bottom.gas_at(end),
    gas_plan=carried,
)

full_dive = bottom.copy()
full_dive.add_segments(ascent)  # seams stay policy-checked

print("runtime    action                  duration   gas    kind")
elapsed = timedelta(0)
for segment in full_dive.segments:
    print(describe(segment, elapsed))
    elapsed += segment.duration
print(f"total runtime : {minutes(full_dive.runtime)}")
deco_time = sum(
    (s.duration for s in ascent if s.kind is SegmentKind.Constant.STOP),
    timedelta(0),
)
print(f"total stops   : {minutes(deco_time)}")
print()

# ---------------------------------------------------------------------------
# 6. Same dive, different models — the point of the result layer
# ---------------------------------------------------------------------------
print("=== 6. Model comparison (same bottom, EAN50 carried) ===")

candidates = [
    ("ZHL-16C raw", ZHL16C()),
    ("ZHL-16C GF 30/70", ZHL16C(gradient=Gradient(0.3, 0.7))),
    ("ZHL-16C GF 85/85", ZHL16C(gradient=Gradient(0.85, 0.85))),
    ("VPM-B +0 (pre-CVA)", VpmB(conservatism=0)),
    ("VPM-B +3 (pre-CVA)", VpmB(conservatism=3)),
]
for name, model in candidates:
    res = DiveResult.run(bottom, model)
    tts = res.tts(bottom.runtime, gas_plan=carried)
    print(f"  {name:<20} TTS at end of bottom: {minutes(tts)}")
print()

# ---------------------------------------------------------------------------
# 7. Serialization — profiles round-trip as JSON, unvalidated
# ---------------------------------------------------------------------------
print("=== 7. Serialization ===")

payload = full_dive.to_json()
restored = DiveProfile.from_json(payload)
assert restored.segments == full_dive.segments
print(f"JSON round-trip OK ({len(payload)} bytes, {restored.segment_count} segments)")
