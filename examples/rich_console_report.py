"""Rich terminal dive report — the same 40 m deco dive as
``complete_dive_plan.py``, rendered with the rich formatter.

Run from the repo root:

    uv run python examples/rich_console_report.py

Covers: looking up deco models and formatters through the plugin registry,
building a full dive (bottom + planned ascent), assembling a DiveReport,
printing it styled to the live terminal, and exporting the same rendering
as plain or ANSI text.

DO NOT USE FOR REAL-WORLD DIVE PLANNING — experimental software.
"""

from diveplan import Dive, DiveProfile, DiveReport, GasPlan
from diveplan.registry import registry

# Deco models and formatters are plugins, discovered from entry points —
# look them up by registry name instead of importing their classes:
ZHL16C = registry.model("zhl16c")
RichConsoleFormatter = registry.formatter("rich")

# ---------------------------------------------------------------------------
# 1. Plan a dive: 25 min at 40 m on air, EAN50 carried for deco
# ---------------------------------------------------------------------------
bottom = DiveProfile().descend_to("40 m").stay(25)
carried = GasPlan(["air", "ean50"])

dive = Dive.run(bottom, ZHL16C(gradient="30/70"))
full_dive = dive.with_ascent(carried)  # bottom + planned deco schedule

report = DiveReport.from_dive(
    full_dive,
    # "+1 m / +1 min" figures describe the bottom plan, so they are
    # computed on the in-progress dive and handed to the report.
    tts_variations=dive.tts_variations(carried),
)

# ---------------------------------------------------------------------------
# 2. Print straight to the terminal — colors auto-detected
# ---------------------------------------------------------------------------
formatter = RichConsoleFormatter()
formatter.print(report)

# ---------------------------------------------------------------------------
# 3. The formatter contract still applies: format() returns a string
# ---------------------------------------------------------------------------
# ANSI-styled text (paste into anything that understands escape codes):
styled = formatter.format(report)

# Plain text with the box-drawn tables kept — e.g. for logs or files:
plain = RichConsoleFormatter(styled=False).format(report)
# RichConsoleFormatter(styled=False).write(report, "plan.txt")

print(f"format() exports: {len(styled)} bytes styled, {len(plain)} bytes plain")
