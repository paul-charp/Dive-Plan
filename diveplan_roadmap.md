# diveplan — design summary & coding roadmap

## What we are building

`diveplan` is a pure Python library for dive planning and decompression calculation. It is the calculation core only — no UI, no CLI, no GUI. Those live in separate packages (`diveplan-cli`, `diveplan-gui`, etc.) that depend on this library.

Two primary use cases drive every design decision:

- **Single dive planning** — a diver or app builds a profile, runs it, reads the report
- **Batch simulation** — thousands of dives run programmatically to compare algorithms, conditions, or profiles

---

## Core design principles

- **Pressure is ground truth** — stored as `int` millibars, never float depth
- **Lazy execution** — `Dive` builds a plan, `.run()` integrates everything in one pass
- **Strategy pattern for deco models** — swap algorithms without touching the planner
- **Plugin architecture** — models and formatters are discoverable via Python entry points
- **No UI dependencies** in the core package
- **Experimentation-friendly** — no operational upper bounds on config values, only physical impossibilities rejected

---

## Object map

### Value objects (frozen, no side effects)

| Class | File | Responsibility |
|---|---|---|
| `Pressure` | `core/pressure.py` | Integer mbar ground truth, arithmetic, depth conversion via `DiveConfig` |
| `DiveStep` | `core/dive_step.py` | One segment: start/end pressure, duration, gas, kind |
| `StepKind` | `core/dive_step.py` | `CONST` (default), `DESCENT`, `ASCENT`, `DECO` |
| `AscentMode` | `core/dive_step.py` | `DECO` (planner runs), `FORCE` (integrate through violations) |
| `Gas` | `core/gas.py` | O2/He/N2 fractions, MOD, ppO2 at pressure, best_mix |
| `DiveConfig` | `core/config.py` | Physical constants + planning parameters + gas limits, global stack-based context |

### Planning

| Class | File | Responsibility |
|---|---|---|
| `GasPlan` | `planning/gas_plan.py` | Gas inventory + `select_gas(pressure)` → best safe mix |
| `AscentPlanner` | `planning/planner.py` | Main ascent loop — integrates model, calls `get_next_stop`, emits `DiveStep`s |
| `simulate_ascent()` | `planning/simulate.py` | Pure function — clones model, checks ceiling validity, returns `bool` |
| `calculate_fastest_continuous_ascent()` | `planning/tools.py` | Binary search on ascent rate, no stop violations |

### Deco models

| Class | File | Responsibility |
|---|---|---|
| `AbstractDecoModel` | `models/base.py` | ABC: `integrate(step)`, `ceiling()`, `clone()` |
| `Compartment` | `models/helpers.py` | Single Haldane tissue compartment, Bühlmann ceiling |
| `Gradient` | `models/helpers.py` | GF low/high interpolation, applies to any model with a ceiling |
| `ZHL16C` | `models/buhlmann/zhl16.py` | Built-in Bühlmann ZHL-16C implementation |

### Dive & output

| Class | File | Responsibility |
|---|---|---|
| `Dive` | `dive/dive.py` | Builder + runner. Three construction styles. `.run()` integrates all steps |
| `DiveReport` | `dive/report.py` | Read-only analyser over `list[DiveStep]`. Stats as `@property`. No calculations |
| `ReportFormatter` | `dive/formatters/base.py` | Protocol: `format(report) -> str` |
| `JSONFormatter` | `dive/formatters/json.py` | Built-in formatter |
| `CSVFormatter` | `dive/formatters/csv.py` | Built-in formatter |

### Infrastructure

| Class/Module | File | Responsibility |
|---|---|---|
| `PluginRegistry` | `registry.py` | Entry point discovery, `@cache`, manual escape hatch |
| `config` proxy | `core/__init__.py` | Module-level `_ConfigProxy` — `from diveplan.core import config` |
| `frange` | `utils/frange.py` | Integer-based range for integration loops |

---

## Key type decisions

### `Pressure` ✅ IMPLEMENTED

```python
class Pressure:
    __slots__ = ("_mbar",)
```

Plain class with `__slots__` — not a dataclass. Rationale: single field, all arithmetic defined manually, `frozen=True` overhead unnecessary, `__slots__` gives memory efficiency for batch simulation (tens of thousands of instances per run).

**Non-negative invariant:** `Pressure(-1)` raises `ValueError`. Represents absolute pressures only. Signed deltas are plain `int` mbar.

**Constructors:**
- `Pressure(mbar: int)` — ground truth
- `Pressure.from_bar(bar: float)` — rounds to nearest mbar
- `Pressure.from_mbar(mbar: float)` — rounds float mbar to int
- `Pressure.from_depth_m(depth_m: float)` — reads `DiveConfig.current().physics`

**Properties:** `.mbar`, `.bar`, `.depth_m` (reads `DiveConfig.current().physics`)

**Arithmetic:**
```
Pressure + Pressure  -> Pressure     (absolute pressures)
Pressure - Pressure  -> int          (signed mbar delta — NOT a Pressure)
Pressure * float     -> Pressure     (e.g. ppO2 = ambient * o2_fraction)
float   * Pressure   -> Pressure     (commutative)
Pressure / Pressure  -> float        (dimensionless ratio)
Pressure / float     -> Pressure     (scaling)
```

**Dependency:** `Pressure` imports `DiveConfig` at module level (top-level import, not local). `DiveConfig` never imports `Pressure` — one way only. This is safe because `DiveConfig` has no need for `Pressure` types internally (config fields are plain `int`/`float`).

**Depth conversion on `Pressure`:** `from_depth_m` and `depth_m` read `DiveConfig.current()` internally — consistent with how all other modules access config. The current environment (e.g. altitude, fresh water) is set via the context manager at a higher level; call sites need no extra arguments.

### `DiveConfig` ✅ IMPLEMENTED

Split into three sub-configs, each inheriting from `_SubConfig`:

```
DiveConfig (frozen)
├── physics:  _PhysicsConfig       (validate_assignment=True)
├── planning: _PlanningConfig      (validate_assignment=True)
└── gas:      _GasConfig           (validate_assignment=True)
```

Sub-config classes are prefixed with `_` — implementation details of `DiveConfig`, not part of the public API, not in `__all__`. Users never construct them directly.

**`_SubConfig` base** — shared by all three:
- `model_config = ConfigDict(validate_assignment=True)`
- `__str__` and `__repr__` return `model_dump_json(indent=2)`

**`_PhysicsConfig`** fields:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `water_density` | `float` | `1.025` | `gt=0` — kg/L |
| `gravity` | `float` | `9.80665` | `gt=0` — m/s² |
| `surface_pressure_mbar` | `int` | `1013` | `gt=0` — mbar |

Derived property: `pressure_per_meter_mbar = water_density * gravity * 100`

**`_PlanningConfig`** fields:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `ascent_rate` | `float` | `9.0` | `gt=0` — m/min |
| `descent_rate` | `float` | `20.0` | `gt=0` — m/min |
| `stop_increment_m` | `float` | `3.0` | `gt=0` — m |
| `last_stop_m` | `float` | `3.0` | `gt=0` — m |
| `min_stop_time_s` | `int` | `60` | `gt=0` — seconds |
| `sample_rate_s` | `int` | `1` | `gt=0` — seconds |
| `default_model` | `str` | `"zhl16c"` | registry hint only |

**`_GasConfig`** fields:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `min_ppo2_bar` | `float` | `0.18` | `gt=0` |
| `max_ppo2_bar` | `float` | `1.4` | `gt=0` |
| `deco_ppo2_bar` | `float` | `1.6` | `gt=0` |
| `max_ppn2_bar` | `float` | `3.2` | `gt=0` |
| `max_end_m` | `float` | `30.0` | `gt=0` |
| `sac_bottom` | `float` | `20.0` | `gt=0` — L/min |
| `sac_deco` | `float` | `15.0` | `gt=0` — L/min |
| `gas_switch_minutes` | `float` | `1.0` | `ge=0` — 0 = instant |
| `gas_switch_at_stops_only` | `bool` | `True` | |

**Validation philosophy:** `gt=0` only — no upper bounds. Users can set `max_ppo2_bar=5.0` for hyperbaric experimentation. Only physically impossible values (zero or negative) are rejected.

**Global access patterns:**

```python
# inside core/ — direct import only (avoids circular import)
from diveplan.core.config import DiveConfig
DiveConfig.current().gas.max_ppo2_bar

# outside core/ (models/, planning/, dive/) and user code — proxy shortcut
from diveplan import diveconfig
diveconfig.gas.max_ppo2_bar          # proxy forwards __getattr__ to DiveConfig.current()
diveconfig.gas.max_ppo2_bar = 1.6   # mutates sub-config on current default

# permanent global replacement
DiveConfig.set_default(custom_cfg)

# scoped override — stack-based, supports nesting
with DiveConfig(physics=_PhysicsConfig(surface_pressure_mbar=800)):
    ...  # altitude dive

# reset to factory defaults
DiveConfig.reset_default()   # useful in tests
```

**Default config loading — priority chain:**

```
1. DIVEPLAN_CONFIG env var        → path to JSON file
2. ./diveplan.config.json         → project-level (CWD)
3. ~/.diveplan/config.json        → user-level (home dir)
4. factory defaults               → always available
```

Set `DIVEPLAN_NO_FILE_CONFIG=1` to skip 1–3 (CI, testing, predictable defaults).
Invalid files at any level log a warning and fall through to the next level silently.

**Serialization:**
```python
cfg.to_json()                        # → JSON string
cfg.to_json(path="my_config.json")   # → write to file
DiveConfig.from_json(data=json_str)
DiveConfig.from_json(path="my_config.json")
```

### `DiveStep`

```python
@dataclass
class DiveStep:
    start_pressure: Pressure
    end_pressure: Pressure
    duration: timedelta
    gas: Gas
    kind: StepKind | None = None        # inferred in __post_init__ if None

    def __post_init__(self):
        if self.kind is None:
            self.kind = self._infer_kind()

    def _infer_kind(self) -> StepKind:
        if self.end_pressure < self.start_pressure: return StepKind.ASCENT
        if self.end_pressure > self.start_pressure: return StepKind.DESCENT
        return StepKind.CONST            # default — planner sets DECO explicitly
```

`CONST` is the zero-assumption default. Ascent planner tags its stops as `DECO` explicitly.

### `Compartment`

```python
@dataclass
class Compartment:
    half_time_n2: float
    half_time_he: float
    a: float
    b: float
    loading_n2: Pressure
    loading_he: Pressure

    def integrate(self, pp_n2: Pressure, pp_he: Pressure, minutes: float) -> None:
        # Haldane for each gas

    def ceiling(self) -> Pressure:
        # Bühlmann: combined N2+He loading → P_amb_tol

    def clone(self) -> "Compartment": ...
```

One compartment holds both N2 and He loadings — 16 compartments total for ZHL-16C.

### `Gradient`

```python
@dataclass(frozen=True)
class Gradient:
    low: float      # e.g. 0.30
    high: float     # e.g. 0.85

    def factor(
        self,
        current: Pressure,
        surface: Pressure,
        deepest_ceiling: Pressure,
    ) -> float:
        # linear interpolation between GF low (at depth) and GF high (at surface)
```

`Gradient(1.0, 1.0)` = no GF, pure Bühlmann. GF lives on the model instance, not in `DiveConfig`.

### `Dive` construction styles

All three produce the same internal `list[DiveStep]`. Nothing integrates until `.run()`.

```python
# action-like (chainable)
report = (
    Dive(model=ZHL16C(gf_low=0.3, gf_high=0.85), gas_plan=plan)
    .descend(to=40, rate=20)
    .const(duration=25)
    .ascent_to_surface()
    .run()
)

# declarative with natural args
dive = Dive(model=ZHL16C(), gas_plan=plan)
dive.add_segment(depth=40, duration=25)
dive.ascent_to_surface()
report = dive.run()

# declarative with DiveSteps
dive = Dive.from_steps(steps=[...], model=ZHL16C(), gas_plan=plan)
report = dive.run()
```

### `Dive.ascent()` signature

```python
def ascent(
    self,
    to: Pressure | float | None = None,    # None = surface, float = depth in meters
    rate: float | None = None,             # m/min, falls back to DiveConfig.current().planning.ascent_rate
    mode: AscentMode = AscentMode.DECO,    # DECO or FORCE
) -> "Dive": ...

def ascent_to_surface(self, rate: float | None = None) -> "Dive":
    return self.ascent(to=None, rate=rate)
```

### `DiveReport`

```python
@dataclass(frozen=True)
class DiveReport:
    steps: list[DiveStep]

    @property
    def max_depth(self) -> Pressure: ...
    @property
    def dive_time(self) -> timedelta: ...
    @property
    def deco_time(self) -> timedelta: ...   # sum of DECO steps
    @property
    def tts(self) -> timedelta: ...         # time to surface
    @property
    def otu(self) -> float: ...
    @property
    def cns(self) -> float: ...
    @property
    def avg_depth(self) -> Pressure: ...    # pressure-time weighted
    @property
    def ceiling_violations(self) -> list[CeilingViolation]: ...  # FORCE ascents only
    @property
    def is_clean(self) -> bool: ...

    def format(self, formatter: ReportFormatter) -> str: ...
```

---

## Ascent algorithm

### `get_next_stop()`

```
candidate = nearest 3m stop above current ceiling
while candidate > surface:
    sim = model.clone()
    if simulate_ascent(sim, current, candidate, rate, gas):
        return candidate        # safe — go here
    candidate -= 3m             # try one stop deeper
return current                  # can't move yet
```

### Main loop

```
while current > surface:
    gas = gas_plan.select_gas(current)
    next_stop = get_next_stop(model, current, gas, rate)

    if next_stop == current:
        integrate(DiveStep(current, current, 1min, gas, DECO))
    else:
        integrate(DiveStep(current, next_stop, ..., gas, ASCENT))
        current = next_stop
```

### `simulate_ascent()` signature

```python
def simulate_ascent(
    model: AbstractDecoModel,   # already a clone — will be mutated
    start: Pressure,
    end: Pressure,
    rate: float,
    gas: Gas,
) -> bool:                      # True = ceiling never violated
```

### Stop grid

- 3m increments (`DiveConfig.current().planning.stop_increment_m`)
- `round_up_to_3m(ceiling)` = nearest 3m stop shallower than ceiling
- If ceiling is exactly on a 3m stop → stay there
- Surface pressure from `DiveConfig.current().physics.surface_pressure_mbar`

### Gas switching

- Select richest mix where `pressure * o2_fraction <= max_ppo2`
- Switch adds `gas_switch_minutes` integrated at current stop with old gas, then switches
- Switches only at deco stops when `gas_switch_at_stops_only = True`
- After switch, re-simulate ascent with new gas before committing

---

## Plugin architecture

Plugins register via Python entry points in their own `pyproject.toml`:

```toml
# diveplan-vpm/pyproject.toml
[project.entry-points."diveplan.models"]
vpm = "diveplan_vpm:VPMModel"

[project.entry-points."diveplan.formatters"]
table = "diveplan_cli.formatters:TableFormatter"
```

`diveplan` discovers them at runtime, cached per process:

```python
from diveplan import registry

registry.model("vpm")                       # → VPMModel class
registry.models()                           # → all installed models
registry.register_model("exp", MyModel)     # manual escape hatch
```

Built-in models and formatters self-register via `diveplan`'s own `pyproject.toml`.

**Plugin groups:** `diveplan.models`, `diveplan.formatters`

---

## Package structure

```
diveplan/
├── src/
│   └── diveplan/
│       ├── __init__.py              # public API + NullHandler
│       ├── py.typed                 # empty — enables downstream type checking
│       ├── registry.py              # plugin discovery + manual registration
│       ├── core/
│       │   ├── __init__.py          # config proxy: from diveplan.core import config
│       │   ├── pressure.py          # Pressure
│       │   ├── dive_step.py         # DiveStep, StepKind, AscentMode
│       │   ├── gas.py               # Gas
│       │   └── config.py            # DiveConfig, PhysicsConfig, DivePlanningConfig, GasConfig
│       ├── models/
│       │   ├── base.py              # AbstractDecoModel
│       │   ├── helpers.py           # Compartment, Gradient
│       │   └── buhlmann/
│       │       └── zhl16.py         # ZHL16C
│       ├── planning/
│       │   ├── planner.py           # AscentPlanner, get_next_stop, main loop
│       │   ├── simulate.py          # simulate_ascent()
│       │   ├── gas_plan.py          # GasPlan, select_gas()
│       │   └── tools.py             # calculate_fastest_continuous_ascent()
│       ├── dive/
│       │   ├── dive.py              # Dive builder + runner
│       │   ├── report.py            # DiveReport
│       │   └── formatters/
│       │       ├── base.py          # ReportFormatter protocol
│       │       ├── json.py
│       │       └── csv.py
│       └── utils/
│           ├── frange.py            # integer-based range for integration
│           └── units.py
├── tests/                           # mirrors src/ structure
│   └── conftest.py                  # shared fixtures
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── .gitignore
├── .vscode/settings.json
└── .github/workflows/ci.yml
```

---

## Public API surface

```python
# core — always stable
from diveplan import Pressure, DiveStep, StepKind, AscentMode
from diveplan import Gas, DiveConfig
from diveplan import Dive, DiveReport, GasPlan

# config proxy — same import for users and downstream modules (models/, planning/, dive/)
from diveplan import diveconfig
diveconfig.gas.max_ppo2_bar = 1.4

# extension points
from diveplan.models import AbstractDecoModel, ZHL16C
from diveplan.models.helpers import Compartment, Gradient
from diveplan.dive.formatters.base import ReportFormatter

# plugin registry
from diveplan import registry
```

Sub-config types (`_PhysicsConfig`, `_PlanningConfig`, `_GasConfig`) are **not** exported — implementation details of `DiveConfig`.

Internal modules (`planning/`, `utils/`) are importable but not part of the stable contract.

---

## Logging

```python
# src/diveplan/__init__.py
import logging
logging.getLogger("diveplan").addHandler(logging.NullHandler())
```

- Library never calls `basicConfig` — the caller configures handlers
- Silent by default — opt in with `logging.getLogger("diveplan").setLevel(logging.DEBUG)`
- All submodules use `logging.getLogger(__name__)` — inherit from root `diveplan` logger
- Config loading logs `INFO` on success, `WARNING` on invalid file, `DEBUG` on fallback

---

## Tooling

| Tool | Purpose |
|---|---|
| `uv` | package manager, venv, publish |
| `hatchling` | build backend |
| `pydantic` | config validation and serialization |
| `ruff` | linting + formatting |
| `mypy` | type checking |
| `pytest` + `pytest-cov` | tests |

```toml
[project.optional-dependencies]
numpy = ["numpy>=1.26"]     # optional — batch simulation only
dev   = ["pytest", "pytest-cov", "ruff", "mypy"]
```

---

## Roadmap

---

### Phase 1 — foundation

#### ✅ 1.1 Project setup
- `uv init diveplan --lib` with `src/` layout
- `pyproject.toml` with hatchling + pydantic dependency
- `py.typed`, `.vscode/settings.json`, `.gitignore`
- Folder structure created, editable install verified

#### ✅ 1.2 `DiveConfig`
- Pydantic-based, split into `_PhysicsConfig`, `_PlanningConfig`, `_GasConfig`
- Sub-config classes prefixed `_` — not public API, not in `__all__`
- `_SubConfig` base: `validate_assignment=True`, JSON `__str__`/`__repr__`
- `DiveConfig` root: `frozen=True`, stack-based context manager, `set_default()`, `reset_default()`
- Default loading chain: `DIVEPLAN_CONFIG` → `./diveplan.config.json` → `~/.diveplan/config.json` → factory
- `DIVEPLAN_NO_FILE_CONFIG=1` disables file loading
- Logging: `WARNING` on invalid files, `INFO` on successful load, `DEBUG` on fallback
- Full test suite: validation, context manager nesting, env var loading, file loading, serialization

#### ✅ 1.3 `Pressure`
- Plain class with `__slots__ = ("_mbar",)` — not a dataclass
- Non-negative invariant enforced in `__init__`
- Constructors: `Pressure(mbar)`, `from_bar()`, `from_mbar()`, `from_depth_m()`
- Properties: `.mbar`, `.bar`, `.depth_m` — depth conversion reads `DiveConfig.current().physics`
- `Pressure - Pressure → int` (signed mbar delta, not a `Pressure`)
- Full arithmetic: `+`, `-`, `*` (scalar), `/` (Pressure→float, float→Pressure), full ordering
- `__str__`: e.g. `"4.013 bar (4013 mbar)"`
- Top-level import of `DiveConfig` — no local import, no circular risk (`DiveConfig` never imports `Pressure`)
- Tests: construction, immutability, all operators, depth conversion with varied configs (salt/fresh/altitude)

#### 1.4 `Gas` ← next
- Renamed from `GasMix` — shorter, unambiguous in context
- Plain immutable class with `__slots__`, same pattern as `Pressure` — not Pydantic
- Fields: `fo2: float`, `fhe: float`, `fn2: float` (computed: `1.0 - fo2 - fhe`)
- Fractions validated on init: `abs(fo2 + fhe + fn2 - 1.0) < 1e-6`, else `ValueError`
- All fractions `>= 0`, `fo2 > 0` (physically required)

**Named constructors:**
- `Gas.air()` — 21% O2, 79% N2
- `Gas.oxygen()` — 100% O2
- `Gas.nitrox(fo2)` / `Gas.ean(fo2)` — alias, N2 fills remainder
- `Gas.trimix(fo2, fhe)` — N2 fills remainder
- `Gas(fo2, fhe=0.0)` — direct construction, positional fo2, keyword fhe

**Name parser:**
- `Gas.from_name(name: str) -> Gas` — regex parser
- Handles: `"air"`, `"oxygen"`, `"nx32"`, `"ean32"`, `"nitrox 32"`, `"tx 21/35"`, `"trimix 21/35"`

**Partial pressures** (take `Pressure`, return `Pressure`):
- `ppo2(pressure)`, `ppn2(pressure)`, `pphe(pressure)`

**Limits:**
- `mod(*, ppo2_bar: float) -> Pressure` — maximum operating depth
- `end(pressure) -> Pressure` — equivalent narcotic depth
- `best_mix(depth_m_or_pressure, *, trimix=False, hypoxic=False) -> Gas`:
  - overloaded: accepts `float` (depth) or `Pressure`
  - reads `DiveConfig.current().gas` for `min_ppo2_bar`, `max_ppo2_bar`, `max_end_m`, `max_ppn2_bar`
  - maximises fo2 within ppO2 and END/ppN2 constraints
  - `hypoxic=True` implies `trimix=True`
  - raises `ValueError` if constraints cannot be satisfied (e.g. `best_mix(120, trimix=False)`)

- Tests: fractions, sum-to-one validation, MOD, partial pressures, END, best_mix variants (air range, trimix, hypoxic, unsatisfiable)

#### 1.5 `DiveStep`
- Fields: `start_pressure`, `end_pressure`, `duration: timedelta`, `gas: Gas`, `kind: StepKind | None`
- `StepKind`: `CONST` (default), `DESCENT`, `ASCENT`, `DECO`
- `AscentMode`: `DECO`, `FORCE`
- `__post_init__` kind inference
- `duration` stored as `timedelta` — iterate as integer seconds internally
- Tests: all inference cases, explicit override, timedelta arithmetic

#### 1.6 `diveplan/__init__.py` — public API + `diveconfig` proxy
- `diveconfig` proxy defined and exported here — NOT in `core/` (would shadow `core/config.py` module)
- `_ConfigProxy.__getattr__` forwards to `DiveConfig.current()` — no `.current()` needed at call sites
- Usage is identical for downstream library modules and external users:
  ```python
  from diveplan import diveconfig
  diveconfig.gas.max_ppo2_bar        # read
  diveconfig.gas.max_ppo2_bar = 1.6  # mutate sub-config
  ```
- `core/` modules use `DiveConfig.current()` directly — importing from `diveplan` root would risk circular imports
- `logging.getLogger("diveplan").addHandler(logging.NullHandler())`
- Explicit `__all__` — includes `diveconfig`, excludes `_PhysicsConfig`, `_PlanningConfig`, `_GasConfig`

---

### Phase 2 — deco model layer

Goal: `AbstractDecoModel` + working `ZHL16C`. Can integrate a step sequence and return a ceiling.

**2.1 `Compartment` and `Gradient`**
- `Compartment`: N2+He loadings as `Pressure`, Haldane `integrate()`, Bühlmann `ceiling()`, `clone()`
- `Gradient`: `factor()` linear interpolation, `Gradient(1.0, 1.0)` = no GF
- GF lives on model instance — not in `DiveConfig`
- Tests: single compartment loading, ceiling at known saturation, GF scaling

**2.2 `AbstractDecoModel`**
- ABC: `integrate(step: DiveStep)`, `ceiling() -> Pressure`, `clone()`
- `sample_rate_s: int` instance variable — reads `DiveConfig.current().planning.sample_rate_s` as default
- Tests: interface enforcement, sample rate override

**2.3 `ZHL16C`**
- 16 compartments, published ZHL-16C N2+He coefficients
- `integrate()` loops `range(0, step.duration_s, sample_rate_s)`, calls `_integrate_model(step, t)`
- `_integrate_model()` interpolates pressure linearly across step
- `ceiling()` applies `Gradient.factor()` to worst compartment
- `clone()` deep copies all compartment loadings
- Tests: known profile vs published deco tables, ceiling after saturation

---

### Phase 3 — ascent planner

Goal: given a model state and a target, produce a valid sequence of `DiveStep`s.

**3.1 `GasPlan`**
- `list[Gas]` sorted by O2 descending
- `select_gas(pressure) -> Gas` — richest within `DiveConfig.current().gas.max_ppo2_bar`
- `best_deco_gas(pressure) -> Gas` — using `deco_ppo2_bar`
- Tests: selection at depth, edge cases (no valid gas)

**3.2 `simulate_ascent()`**
- Pre-cloned model, integrates 1s steps, checks ceiling ≤ target throughout
- Returns `bool`
- Tests: clean ascent, violated ascent, borderline

**3.3 `get_next_stop()`**
- Stop grid from `DiveConfig.current().planning.stop_increment_m`
- Walk candidates shallow → deep, simulate each
- Returns shallowest safe stop or current pressure
- Tests: NDL (surface), ceiling-limited, gas switch interaction

**3.4 `AscentPlanner` main loop**
- Gas switch: `gas_switch_minutes` of old gas → switch → re-simulate
- `FORCE` mode: integrate through violations, record `CeilingViolation`s
- Returns `list[DiveStep]`
- Tests: NDL, deco profile, multi-gas, force ascent

**3.5 `calculate_fastest_continuous_ascent()`**
- Binary search 1–30 m/min, ~5 iterations
- Tests: no ceiling violation at returned rate

---

### Phase 4 — `Dive` builder and `DiveReport`

**4.1 `Dive`**
- Three construction styles, all lazy until `.run()`
- `.run()` integrates segments, fires planner at ascent sentinels
- Chainable, returns `self`

**4.2 `DiveReport`**
- `@property` stats: `max_depth`, `dive_time`, `deco_time`, `tts`, `otu`, `cns`, `avg_depth`
- `ceiling_violations`, `is_clean`
- `format(formatter)` dispatch

**4.3 Formatters**
- `ReportFormatter` protocol
- `JSONFormatter`, `CSVFormatter`

---

### Phase 5 — plugin registry

**5.1 `PluginRegistry`**
- Entry point discovery with `@cache`
- `registry.model(name)` with `PluginNotFoundError` + install hint
- `registry.register_model()` manual escape hatch
- Built-ins self-register in `pyproject.toml`

**5.2 `__init__.py` public surface**
- Explicit `__all__`
- Tests: `from diveplan import *` gives exactly the intended surface

---

### Phase 6 — hardening

**6.1** `mypy --strict` zero errors, `py.typed` in place
**6.2** Regression suite — ZHL16C vs published tables, ≥5 known profiles
**6.3** Benchmark — 1000 dives, identify hot paths, numpy acceleration if needed
**6.4** Docs — docstrings, README quickstart, `CHANGELOG.md`
**6.5** PyPI publish — `uv build`, `uv publish`, tag `v0.1.0`

---

## Dependency rules

- `core/` has no internal imports — everything else imports from it
- `Pressure` → `DiveConfig` (one way only, never reversed)
- `models/` and `planning/` are independent of each other
- `dive/` is the only layer that assembles everything
- `DiveReport` only imports from `core/`

---

## What comes after `diveplan`

Once `v0.1.0` is stable:

- `diveplan-cli` — terminal interface, `TableFormatter`, rich profile display
- `diveplan-jupyter` — notebook helpers, matplotlib profile plots
- `diveplan-vpm` — VPM-B model as a plugin
- `diveplan-gui` — desktop or web UI

Each is a separate package, separate repo, depends on `diveplan` via PyPI.
