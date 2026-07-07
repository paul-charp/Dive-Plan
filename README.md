# Dive-Plan

`diveplan` is a pure-Python library for **dive planning and decompression
calculation**. It is the calculation core only — no UI, no CLI — designed to be
embedded in other tools and to scale from a single dive plan to large batch
simulations comparing algorithms, gases, and conditions.

> [!CAUTION]
> **DO NOT USE FOR REAL-WORLD DIVE PLANNING.**
>
> This is experimental software. Do not dive without certification or outside
> your certification limits.

## Status

Early development — **all layers below are implemented and tested** (483 tests, strict mypy):

| Component | Status |
|---|---|
| `Pressure` — integer-millibar value type & unit conversions | ✅ |
| `Gas` — O2/He/N2 mixes, MOD/END/best-mix | ✅ |
| `DiveSegment` / `SegmentKind` — one leg of a profile | ✅ |
| `DiveConfig` — physics / planning / gas config, scoped overrides | ✅ |
| `DiveProfile` — builder, validation & repair, timeline | ✅ |
| Plugin registry (entry-point deco-model discovery) | ✅ |
| Deco models — Bühlmann ZHL-16C (GF), VPM-B (pre-CVA) | ✅ |
| `Dive` — checkpoints, `state_at`/`ceiling_at`/`tts(t)`, `with_ascent` | ✅ |
| Ascent planner (`Dive.plan_ascent()`) + `GasPlan` | ✅ |
| `DiveReport` + formatters (console, rich, runtime sheet, JSON, Subsurface XML) | ✅ |
| Gas consumption, rock bottom, CNS/OTU, TTS variations | ✅ |
| VPM-B critical-volume/Boyle stage | 🚧 in progress |

## Design principles

- **Pressure is ground truth** — stored as integer millibar, never float depth.
- **Immutable value objects** — `Pressure`, `Gas`, `DiveSegment` are frozen with
  `__slots__` for memory efficiency in batch runs.
- **One shared, scoped configuration** — `DiveConfig` carries environment
  (physics), planning rates, and gas limits; overrides are stack-based and
  isolated per thread/async task.
- **Plugin architecture** — deco models and formatters are discovered via Python
  entry points.
- **Experimentation-friendly** — config rejects only physically impossible
  values (zero/negative), never operational limits.

## Public API

Everything stable imports from the package root; submodule paths are
implementation detail unless noted below.

```python
from diveplan import (
    Pressure, Gas, DiveSegment, SegmentKind,     # core value types
    DiveConfig, diveconfig,                      # configuration (+ live proxy)
    DiveProfile, ProfileBuilderPolicy,           # profile building
    ProfileValidationError,                      #   … and its error family base
    Dive, TtsVariations,                         # running a model over a profile
    GasPlan,                                     # carried gases & selection
    AscentNotConvergingError,                    #   … planner failure mode
    DiveReport, ReportRow,                       # pure-data report
    BaseDecoModel, DecoState, BaseFormatter,     # plugin authoring contracts
)
```

Deco ascents are planned from a `Dive` — `dive.plan_ascent(gas_plan)`
returns the schedule as segments, `dive.with_ascent(gas_plan)` a completed
dive. The underlying pure function lives in `diveplan.planning` for the
advanced case of planning from a bare model state.

Built-in deco models and report formatters are **plugins** — get them by
name through the registry (the one documented submodule import):

```python
from diveplan.registry import registry

ZHL16C = registry.model("zhl16c")               # or "vpmb"
ConsoleFormatter = registry.formatter("console")  # or "rich", "runtime", "json", "subsurface"
```

Import concrete classes directly only for API beyond the plugin contract:
family-specific machinery from `diveplan.models.buhlmann` / `diveplan.models.vpm`
(e.g. `Gradient`, `BuhlmannModel` for subclassing), formatter extras from
`diveplan.dive.formatters` (e.g. `ConsoleFormatter.format_schedule`, rich's
`console=`), and the concrete validation-error subclasses from
`diveplan.dive.dive_profile`.

## Installation

Requires **Python ≥ 3.14**. The project uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync                 # create the venv and install (incl. dev deps)
```

Or with pip, in editable mode:

```bash
pip install -e ".[dev]"
```

## Quickstart

Runnable, commented examples live in [`examples/`](examples/):

| Example | Shows |
|---|---|
| [`complete_dive_plan.py`](examples/complete_dive_plan.py) | The full workflow: config, gases, profile, Dive, ascent, report, formatters |
| [`batch_model_comparison.py`](examples/batch_model_comparison.py) | TTS grids across depths/times/models, incl. an altitude/fresh-water override |
| [`custom_deco_model.py`](examples/custom_deco_model.py) | Writing and registering your own (Bühlmann-family) deco model |
| [`tissue_loading_chart.py`](examples/tissue_loading_chart.py) | Dependency-free visualization of depth, ceiling, and tissue loading |
| [`rich_console_report.py`](examples/rich_console_report.py) | Styled terminal report with the rich formatter — live print and text export |

```bash
uv run python examples/complete_dive_plan.py
```

```python
from diveplan import Pressure, Gas, DiveConfig

# Pressure — integer-millibar ground truth; depth conversion reads config.
p = Pressure.from_depth_m(30)
p.bar        # ~4.0
p.depth_m    # 30.0

# Gas mixes and their limits.
ean32 = Gas.nitrox(0.32)
ean32.mod(ppo2_bar=1.4).depth_m       # max operating depth
Gas.air().best_mix(30)                # richest safe mix for 30 m

# Scoped configuration override — e.g. a fresh-water dive.
fresh = DiveConfig()
fresh.physics.water_density = 1.0
with fresh:
    Pressure.from_depth_m(30).bar     # uses fresh-water density
```

Building a profile — fluent style, with depths as `"40 m"` strings and gases
by name:

```python
from diveplan import DiveProfile

profile = (
    DiveProfile()
    .descend_to("40 m")        # air by default, configured descent rate
    .stay(20)                  # 20 min bottom time
    .ascend_to("21 m")
    .switch_gas("ean50")       # gas switch at the configured switch time
    .surface()                 # ascend to the surface
)

# Address the profile by runtime:
profile.runtime                # total timedelta
profile.pressure_at(23).depth_m   # depth 23 minutes into the dive
profile.gas_at(23)                # gas breathed at that moment

# JSON round-trip:
profile.to_json(path="dive.json")
restored = DiveProfile.from_json(path="dive.json")
```

Running a deco model over the profile — a `Dive` can be in progress (just
the bottom phase) and completed with its planned ascent:

```python
from diveplan import Dive
from diveplan.registry import registry

# Deco models (and report formatters) are plugins — look them up by name:
ZHL16C = registry.model("zhl16c")

bottom = DiveProfile().descend_to("40 m").stay(25)
dive = Dive.run(bottom, ZHL16C(gradient="30/70"))

dive.ceiling_at(23).depth_m   # deco ceiling 23 minutes into the dive
dive.tts(23)                  # time-to-surface if ascending right now
dive.cns_at(23), dive.otu_at(23)   # oxygen exposure accumulated so far
for t, state in dive.tissue_series(1):   # tissue loading, 1-min samples
    ...

full = dive.with_ascent()     # new Dive completed with the deco schedule
full.profile.runtime          # total runtime including stops
```

Segments can still be added explicitly (`add_segment`, `insert_segment_at_index`,
…) and repaired after the fact:

```python
for error in profile.validate_profile(skip_start_end_segments=False):
    print(error.message)
profile.fix_all()   # insert transitions, gas switches, surface segments
```

## Configuration

`DiveConfig` resolves a startup default from the first source that exists:

1. `DIVEPLAN_CONFIG_FILE` environment variable — path to a JSON config file
2. `./diveplan.config.json` — project-level config in the working directory
3. `~/.diveplan/config.json` — user-level config
4. built-in factory defaults

Set `DIVEPLAN_NO_FILE_CONFIG=1` to skip the files and always use factory
defaults (useful in CI and tests). Overrides apply via `DiveConfig.set_default()`
(permanent) or the `with` context manager (scoped, nestable, thread-safe).

## Project structure

```
src/diveplan/
├── core/        # value objects + config (Pressure, Gas, DiveSegment, DiveConfig)
├── dive/        # DiveProfile, Dive, DiveReport, oxygen exposure, formatters
├── models/      # deco models: Bühlmann family (ZHL-16C), VPM-B
├── planning/    # ascent planner, gas plan, consumption, rock bottom
├── utils/       # argument coercion ("40 m", "ean50")
└── registry.py  # entry-point plugin discovery (deco models + formatters)
```

## Development

```bash
uv run pytest         # tests
uv run ruff check .   # lint
uv run ruff format .  # format
uv run mypy src       # type-check (strict)
```

## Documentation

API docs are built with Sphinx (furo theme):

```bash
uv run sphinx-build -b html docs/source docs/_build/html
```

Then open `docs/_build/html/index.html`.

## License

MIT © Paul Charpentier
