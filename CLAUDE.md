# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`diveplan` is a pure-Python library (Python ≥ 3.14) for dive planning and decompression calculation — calculation core only, no UI/CLI. Designed for two use cases that drive every decision: single dive planning and large batch simulations. Experimental software; never soften the README's "do not use for real dives" caution.

## Token-efficient navigation

`.claude/codebase-index.md` is an auto-generated API map of the whole library: every module with class/method/function signatures, docstring one-liners, `__slots__`, and per-file test-class listings. **Read it first instead of reading source files** when you need to know what exists, its signature, or where something lives. Only read actual source before editing it. Regenerate after changing public APIs:

```bash
uv run python .claude/generate-index.py
```

## Commands

The project uses [uv](https://docs.astral.sh/uv/); prefix everything with `uv run`.

```bash
uv sync                                     # create venv + install incl. dev deps
uv run pytest                               # full test suite
uv run pytest tests/test_gas.py             # one file
uv run pytest tests/test_gas.py::TestBestMix::test_air_at_30m   # one test
uv run ruff check . && uv run ruff format . # lint + format (line length 88)
uv run mypy src                             # type-check — strict mode is on
uv run sphinx-build -b html docs/source docs/_build/html   # API docs (furo)
```

Line endings are LF, enforced via `.gitattributes`.

## Architecture

Layering (imports flow strictly downward; `core/` never imports from upper layers):

```
core/      Pressure, Gas, DiveSegment, DiveConfig — value objects + config
dive/      DiveProfile (builder/validation/timeline), reports, formatters
models/    deco models (BaseDecoModel, DecoState, Bühlmann helpers)
planning/  ascent planner, gas plan (stubs — in progress)
registry.py  entry-point plugin discovery for deco models
```

### Pressure is ground truth

`Pressure` stores integer millibar — never float depth. Exact equality and hashing are meaningful; use them. Two type-discipline rules to preserve:

- `Pressure - Pressure` returns a **signed int mbar delta**, deliberately not a `Pressure` (absolute pressure vs. difference are different quantities).
- Depth/atm conversions (`from_depth_m`, `.depth_m`, `.surface()`…) read `DiveConfig.current().physics` **at call time** — the same Pressure renders as different depths under different configs. Dependency is one-way: Pressure → DiveConfig, never reversed.

### DiveConfig: one shared, scoped config

Frozen Pydantic root with mutable, validated sub-configs (`physics`, `planning`, `gas`). Access via `DiveConfig.current()`. Overrides are a ContextVar stack (`with cfg:` — nestable, isolated per thread/asyncio task for parallel batch runs) over a process-global default (`set_default()`). Startup default resolves: `DIVEPLAN_CONFIG_FILE` env var → `./diveplan.config.json` → `~/.diveplan/config.json` → factory defaults; `DIVEPLAN_NO_FILE_CONFIG=1` skips files. Validation philosophy: reject only physically impossible values (zero/negative), never operational limits — this is an experimentation platform.

Tests: `tests/conftest.py` has an autouse fixture pinning a fresh factory-default config around every test, so tests may mutate config freely.

### Immutable value objects

`Pressure`, `Gas`, `DiveSegment` are frozen: `__slots__` plus `__setattr__`/`__delattr__` guards, constructed via `object.__setattr__`. Keep it that way — `DiveProfile.copy()` does a shallow list copy on the assumption segments are true values, and segments are hashable. `DiveSegment` duration must be strictly positive except zero-duration `GAS_SWITCH` segments (instant switch).

### DiveProfile: plan is input, results are output

A profile is pure geometry (list of segments). Do **not** hang model results (tissue states, ceilings, TTS) on segments or the profile — results belong in a separate result layer so one profile can be run under multiple models/GFs and compared. This is a deliberate, agreed design constraint.

Key mechanics spread across `dive/dive_profile.py`:

- **Builder policies** (`ProfileBuilderPolicy`): RAISE validates each touched seam O(1) and raises; ALLOW skips validation; AUTOFIX inserts transitions/gas switches after each mutation.
- **Validation errors are pure data** (`ProfileValidationError` subclasses): descriptors only — no profile reference, no repair logic. Repairs live on `DiveProfile.fix(error)` / `.fix_all()`. Keep this split when adding error types.
- **Fluent builders** (`descend_to`, `ascend_to`, `stay`, `switch_gas`, `surface`) coerce arguments: depths as `Pressure` | `"40 m"` strings (`Pressure.from_str`) | bare metres; gases as `Gas` | names (`Gas.from_name("ean50")`). They start from the current position (last segment's *end* pressure) and go through `add_segment`, so policies apply.
- **Timeline methods** (`runtime`, `segment_at(t)`, `pressure_at(t)`, `gas_at(t)`) accept minutes or timedelta. Seam convention: a segment owns `[start, end)`; the final segment also owns `t == runtime`; at a gas-switch boundary the *new* gas is reported.
- **Serialization** (`to_dict`/`from_dict`/`to_json`/`from_json`) round-trips without re-validating — a stored in-progress (discontinuous) profile must load as saved.

### Deco models and plugins

`BaseDecoModel[StateT: DecoState]` (PEP 695 generics): each model defines its own immutable `DecoState` subclass and returns typed state, not dicts. State snapshots are the currency for future checkpointing and counterfactual queries (TTS at time t) — keep them cheap to copy.

Plugin discovery: entry-point group **`diveplan.deco_models`** (single source of truth: `_ENTRY_POINT_GROUP` in `registry.py`). The registry eagerly loads *every* entry point in the group on first access, so never register an entry point in `pyproject.toml` before its module exists — one dangling reference breaks all model lookups. The `zhl16c` and formatter entry points are commented out in `pyproject.toml` until their modules land; `DiveConfig.planning.default_model` defaults to `"zhl16c"`, so uncomment the entry point in the same PR that adds `zhl16.py`. `registry.register_model()` is the manual escape hatch for tests.

### Known state / gotchas

- `models/buhlmann/common.py` is in-progress and has known issues: `Gradient.factor` is inverted vs. standard gradient-factor convention (GF-low belongs at the deepest stop, GF-high at surface) and interpolates on absolute-pressure ratio; it also fails strict mypy. Fix before building the ascent planner on it.
- `planning/` and `dive/dive_report.py` are empty stubs.
- `diveplan_roadmap.md` predates implementation and drifts from the code in places (e.g. `DiveStep`/`AbstractDecoModel` naming — the code's `DiveSegment`/`BaseDecoModel` won); trust the code.
- `__init__.py` re-exports core types and a `diveconfig` proxy; planning/dive/report symbols get re-exported there as layers land.
