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

Early development. The **core layer is implemented and tested**:

| Component | Status |
|---|---|
| `Pressure` — integer-millibar value type & unit conversions | ✅ |
| `Gas` — O2/He/N2 mixes, MOD/END/best-mix | ✅ |
| `DiveSegment` / `SegmentKind` — one leg of a profile | ✅ |
| `DiveConfig` — physics / planning / gas config, scoped overrides | ✅ |
| `DiveProfile` — builder, validation & repair | ✅ |
| Plugin registry (entry-point deco-model discovery) | ✅ |
| Deco models (ZHL-16C), ascent planner, reports | 🚧 in progress |

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

Building a profile:

```python
from diveplan import DiveSegment, Gas, Pressure
from diveplan.dive.dive_profile import DiveProfile

profile = DiveProfile()
profile.add_segment(
    DiveSegment(Pressure.surface(), Pressure.from_depth_m(40), 4, Gas.air())
)
profile.add_segment(
    DiveSegment(Pressure.from_depth_m(40), Pressure.from_depth_m(40), 20, Gas.air())
)

# Validate and auto-repair (insert transitions, gas switches, surface segments).
for error in profile.validate_profile(skip_start_end_segments=False):
    print(error.message)
profile.fix_all()
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
├── dive/        # DiveProfile, reports, formatters
├── models/      # deco models (ZHL-16C) + helpers
├── planning/    # ascent planner, gas plan
├── utils/       # conversions
└── registry.py  # entry-point plugin discovery
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
