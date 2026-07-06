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
core/          Pressure, Gas, DiveSegment, DiveConfig — value objects + config
dive/dive_profile.py  DiveProfile (builder/validation/timeline/iter_samples) — core only
models/        deco models (BaseDecoModel[StateT], Bühlmann family, VPM-B)
planning/      plan_ascent, GasPlan, consumption/rock-bottom/CNS/OTU — consumes models
dive/dive.py   Dive — top of the stack (profile + models + planning)
dive/dive_report.py   DiveReport (pure data) + dive/formatters/ (console, json, subsurface XML)
registry.py    entry-point plugin discovery for deco models
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

A profile is pure geometry (list of segments). Do **not** hang model results (tissue states, ceilings, TTS) on segments or the profile — results live in `Dive` (`dive/dive.py`) so one profile can be run under multiple models/GFs and compared. This is a deliberate, agreed design constraint.

`Dive.run(profile, model)` copies the model, integrates, and stores **state checkpoints at segment boundaries only** (O(segments) memory for batch). Time queries (`state_at`, `ceiling_at`, `model_at`, `tts(t)`) re-integrate at most one partial segment from the nearest checkpoint — exact, because Haldane integration composes. `tissue_series(dt)` reproduces checkpoints exactly only when sampled at the model's own rate (rectangle rule). `DiveProfile.iter_samples(interval)` is the single sampling authority: steps never cross segment boundaries, the last step of a segment is shortened, zero-duration switches yield no step.

Key mechanics spread across `dive/dive_profile.py`:

- **Builder policies** (`ProfileBuilderPolicy`): RAISE validates each touched seam O(1) and raises; ALLOW skips validation; AUTOFIX inserts transitions/gas switches after each mutation.
- **Validation errors are pure data** (`ProfileValidationError` subclasses): descriptors only — no profile reference, no repair logic. Repairs live on `DiveProfile.fix(error)` / `.fix_all()`. Keep this split when adding error types.
- **Fluent builders** (`descend_to`, `ascend_to`, `stay`, `switch_gas`, `surface`) coerce arguments: depths as `Pressure` | `"40 m"` strings (`Pressure.from_str`) | bare metres; gases as `Gas` | names (`Gas.from_name("ean50")`). They start from the current position (last segment's *end* pressure) and go through `add_segment`, so policies apply.
- **Timeline methods** (`runtime`, `segment_at(t)`, `pressure_at(t)`, `gas_at(t)`) accept minutes or timedelta. Seam convention: a segment owns `[start, end)`; the final segment also owns `t == runtime`; at a gas-switch boundary the *new* gas is reported.
- **Serialization** (`to_dict`/`from_dict`/`to_json`/`from_json`) round-trips without re-validating — a stored in-progress (discontinuous) profile must load as saved.

### Deco models and plugins

`BaseDecoModel[StateT: DecoState]` (PEP 695 generics): each model defines its own immutable `DecoState` subclass and returns typed state, not dicts. `set_state()`/`copy()`/`get_state()` are abstract contract — the result layer's checkpointing and TTS counterfactuals depend on them being lossless and cheap.

Model families: `BuhlmannModel` (models/buhlmann/model.py) is the whole Bühlmann algorithm; a variant like `ZHL16C` is only `NAME` + six coefficient tables, validated at class-definition time. VPM-B (models/vpm/) is a bubble model: same ZHL-16 half-times for loading, ceiling from nuclei mechanics; constants verified against Subsurface deco.cpp (bar/µm units). Tissue tensions are **float mbar internally** in both families — integer quantization would freeze slow compartments at 1 s steps; `Pressure` is the boundary type only.

### Ascent planner

`plan_ascent(model, start_pressure, gas, gas_plan)` (planning/ascent_plan.py) is a pure function: clones the model, returns continuous segments to the surface (deco ascents merged, stop chunks merged, gas switches at stops). GF models get the gradient interpolated at each target depth, anchored at the first (deepest) stop of the ascent; non-GF models are asked for their plain ceiling. Known limits: gas switches only at stops; VPM-B's Critical Volume Algorithm and Boyle compensation are **not applied yet** — its schedules use conservative pre-CVA gradients (`CRIT_VOLUME_LAMBDA_BAR_MIN` is exported for when CVA lands here).

Plugin discovery: entry-point group **`diveplan.deco_models`** (single source of truth: `_ENTRY_POINT_GROUP` in `registry.py`). The registry eagerly loads *every* entry point in the group on first access, so never register an entry point in `pyproject.toml` before its module exists — one dangling reference breaks all model lookups. The `zhl16c` and formatter entry points are commented out in `pyproject.toml` until their modules land; `DiveConfig.planning.default_model` defaults to `"zhl16c"`, so uncomment the entry point in the same PR that adds `zhl16.py`. `registry.register_model()` is the manual escape hatch for tests.

### Report layer

`DiveReport.from_dive(dive)` is pure data: schedule rows + gas consumption (surface litres, exact per linear segment), CNS/OTU (`planning/gas_plan.py`), rock bottom at max depth, and optional `TtsVariations` (the "+1 m / +1 min" figures — compute them on the *bottom* dive via `Dive.tts_variations()`, they are meaningless on a full dive with deco). Formatters (`BaseFormatter.format(report) -> str`) are presentation-only; entry-point group `diveplan.formatters` (console/json/subsurface). Consumption/CNS/OTU take `Iterable[DiveSegment]`, so they work on plans as well as profiles.

### Known state / gotchas

- The Subsurface XML formatter is experimental — validated structurally, not yet round-tripped through a real Subsurface import.
- VPM-B CVA + Boyle compensation pending in the planner (see above).
- `diveplan_roadmap.md` predates implementation and drifts from the code in places (e.g. `DiveStep`/`AbstractDecoModel` naming — the code's `DiveSegment`/`BaseDecoModel` won); trust the code.
- `__init__.py` re-exports core types, `Dive`, `DiveProfile`, `GasPlan`, `plan_ascent`, and a `diveconfig` proxy.
