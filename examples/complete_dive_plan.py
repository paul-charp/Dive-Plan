"""Complete diveplan walkthrough — plan a 40 m deco dive on air with an
EAN50 deco gas, end to end.

Run from the repo root:

    uv run python examples/complete_dive_plan.py

Covers: configuration, gases, fluent profile building, running deco models,
dive queries (ceiling, TTS, tissue loading), ascent planning, model
comparison, serialization, and reporting.

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from datetime import timedelta

from diveplan import (
    Dive,
    DiveConfig,
    DiveProfile,
    DiveReport,
    Gas,
    GasPlan,
    Pressure,
)
from diveplan.core.dive_segment import SegmentKind
from diveplan.dive.formatters import (
    ConsoleFormatter,
    JsonFormatter,
    RuntimeFormatter,
    SubsurfaceXmlFormatter,
)
from diveplan.models.buhlmann.zhl16 import ZHL16C
from diveplan.models.vpm.model import VpmB


def minutes(td: timedelta) -> str:
    return f"{td.total_seconds() / 60:5.1f} min"


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
sea_level_bar = Pressure.from_str("30 m").bar

altitude = DiveConfig()
altitude.physics.surface_pressure_mbar = 900
altitude.physics.water_density = 1.0
with altitude:
    altitude_bar = Pressure.from_str("30 m").bar
print(
    f"30 m of water column = {altitude_bar:.3f} bar at altitude/fresh water, "
    f"{sea_level_bar:.3f} bar at sea level/salt"
)
print()

# ---------------------------------------------------------------------------
# 2. Gases — names, limits, best mix
# ---------------------------------------------------------------------------
print("=== 2. Gases ===")

# Gases parse from names: "air", "ean50"/"nx50", "tx21/35", "oxygen".
air = Gas.from_name("air")
ean50 = Gas.from_name("ean50")

print(f"EAN50 MOD @1.6 bar : {ean50.mod(ppo2_bar=1.6).depth_m:.1f} m")
print(f"best mix for 30 m  : {air.best_mix(30)}")
print(f"air END at 40 m    : {air.end(Pressure.from_str('40 m')).depth_m:.1f} m")
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
# 4. Run a deco model: a Dive — still in progress at this point
# ---------------------------------------------------------------------------
print("=== 4. Dive queries (ZHL-16C, GF 30/70) ===")

carried = GasPlan(["air", "ean50"])
dive = Dive.run(bottom, ZHL16C(gradient="30/70"))

for t in (5, 15, bottom.runtime):
    ceiling = dive.ceiling_at(t)
    depth = max(0.0, ceiling.depth_m)
    label = minutes(t if isinstance(t, timedelta) else timedelta(minutes=t))
    print(
        f"t={label}: ceiling {depth:4.1f} m   "
        f"TTS {minutes(dive.tts(t, gas_plan=carried))}"
    )

print(
    f"exposure at end of bottom: CNS {dive.cns_at(bottom.runtime):.1f} %, "
    f"OTU {dive.otu_at(bottom.runtime):.1f}"
)

# Tissue loading over time (leading compartment) — feed this to a plot:
print("leading-compartment N2 tension (mbar):")
for t, state in dive.tissue_series(timedelta(minutes=9)):
    print(f"  t={minutes(t)}: {state.tissues[0][0]:6.0f}")
print()

# ---------------------------------------------------------------------------
# 5. Complete the dive with its planned deco ascent
# ---------------------------------------------------------------------------
print("=== 5. Ascent plan ===")

ascent = dive.plan_ascent(carried)  # the deco schedule as segments
full_dive = dive.extend(ascent)  # or in one step: dive.with_ascent(carried)

print(ConsoleFormatter.format_schedule(full_dive.profile.segments))
print(f"total runtime : {minutes(full_dive.profile.runtime)}")
deco_time = sum(
    (s.duration for s in ascent if s.kind is SegmentKind.Constant.STOP),
    timedelta(0),
)
print(f"total stops   : {minutes(deco_time)}")
print()

# ---------------------------------------------------------------------------
# 6. Same dive, different models — the point of the Dive layer
# ---------------------------------------------------------------------------
print("=== 6. Model comparison (same bottom, EAN50 carried) ===")

candidates = [
    ("ZHL-16C raw", ZHL16C()),
    ("ZHL-16C GF 30/70", ZHL16C(gradient="30/70")),
    ("ZHL-16C GF 85/85", ZHL16C(gradient="85/85")),
    ("VPM-B +0 (pre-CVA)", VpmB(conservatism=0)),
    ("VPM-B +3 (pre-CVA)", VpmB(conservatism=3)),
]
for name, model in candidates:
    tts = Dive.run(bottom, model).tts(bottom.runtime, gas_plan=carried)
    print(f"  {name:<20} TTS at end of bottom: {minutes(tts)}")
print()

# ---------------------------------------------------------------------------
# 7. Serialization — profiles round-trip as JSON, unvalidated
# ---------------------------------------------------------------------------
print("=== 7. Serialization ===")

payload = full_dive.profile.to_json()
restored = DiveProfile.from_json(payload)
assert restored.segments == full_dive.profile.segments
print(f"JSON round-trip OK ({len(payload)} bytes, {restored.segment_count} segments)")
print()

# ---------------------------------------------------------------------------
# 8. Report — consumption, CNS/OTU, rock bottom, TTS variations, formatters
# ---------------------------------------------------------------------------
print("=== 8. Dive report ===")

report = DiveReport.from_dive(
    full_dive,
    # The "+1 m / +1 min" figures describe the *bottom* plan, so they are
    # computed on the in-progress dive and handed to the report.
    tts_variations=dive.tts_variations(carried),
)

print(ConsoleFormatter().format(report))
print()

# The runtime sheet: transitions folded into stops, whole minutes — what a
# diver actually writes on a slate. Save it with .write(report, "plan.txt").
print(RuntimeFormatter().format(report))
print()

# For a colored interactive rendering, try:
#   from diveplan.dive.formatters import RichConsoleFormatter
#   RichConsoleFormatter().print(report)

json_doc = JsonFormatter().format(report)
print(f"JSON report: {len(json_doc)} bytes")

xml_doc = SubsurfaceXmlFormatter().format(report)
print(f"Subsurface XML: {len(xml_doc)} bytes — write to a .ssrf file and")
print("import in Subsurface via File > Import > Import log files")
