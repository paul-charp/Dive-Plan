# diveplan codebase index

Auto-generated API map (regenerate: `uv run python .claude/generate-index.py`). Generated 2026-07-07.

Read this instead of source files when you only need signatures/structure. Read the actual source before *editing* anything listed here.

## `src/diveplan/__init__.py`
diveplan — dive planning and decompression calculation library.
### class `_ConfigProxy` — Transparent proxy to DiveConfig.current().
  `__slots__ = ()`
  - @property `gas(self) -> _GasConfig`  — Gas limits and SAC rates of the active config.
  - @property `physics(self) -> _PhysicsConfig`  — Physical environment of the active config.
  - @property `planning(self) -> _DivePlanningConfig`  — Rates and stop parameters of the active config.
  dunders: `__repr__, __str__`
- const `diveconfig = _ConfigProxy()`
`__all__ = ['Pressure', 'Gas', 'DiveSegment', 'SegmentKind', 'DiveConfig', 'diveconfig', 'Dive', 'DiveProfile', 'DiveReport', 'GasPlan', 'plan_ascent']`

## `src/diveplan/core/__init__.py`
Core value objects and configuration for diveplan.

## `src/diveplan/core/config.py`
diveplan.core.config
- const `logger = logging.getLogger(__name__)`
`__all__ = ['DiveConfig']`
### class `_SubConfig` (BaseModel) — Base class for all DiveConfig sub-configs.
  attrs: `model_config = ConfigDict(validate_assignment=True)`
  dunders: `__repr__, __str__`
### class `_PhysicsConfig` (_SubConfig) — Physical constants for the dive environment.
  - @property `pressure_per_meter_mbar(self) -> float`  — Pressure increase per meter of depth in mbar.
  attrs: `water_density: float = Field(default=1.025, gt=0, description='kg/L — 1.025 seawater, 1.0 freshwater'); gravity: float = Field(default=9.80665, gt=0, description='m/s²'); surface_pressure_mbar: int = Field(default=1013, gt=0, description='mbar — sea level ~1013, lower at altitude')`
### class `_DivePlanningConfig` (_SubConfig) — Ascent/descent rates and stop parameters.
  attrs: `ascent_rate: float = Field(default=9.0, gt=0, description='m/min'); descent_rate: float = Field(default=20.0, gt=0, description='m/min'); stop_increment_m: float = Field(default=3.0, gt=0, description='meters between deco stops'); last_stop_m: float = Field(default=3.0, gt=0, description='depth of last deco stop in meters'); min_stop_time_s: int = Field(default=60, gt=0, description='minimum time at each stop in seconds'); sample_rate_s: int = Field(default=1, gt=0, description='integration sample rate in seconds'); default_model: str = Field(default='zhl16c', description='registry name of default deco model')`
### class `_GasConfig` (_SubConfig) — Gas planning limits and SAC rates.
  attrs: `min_ppo2_bar: float = Field(default=0.18, gt=0, description='bar — hypoxia floor'); max_ppo2_bar: float = Field(default=1.4, gt=0, description='bar — working/bottom ppO2 limit'); deco_ppo2_bar: float = Field(default=1.6, gt=0, description='bar — ppO2 limit at deco stops'); max_ppn2_bar: float = Field(default=3.2, gt=0, description='bar — narcosis/ppN2 ceiling'); max_end_m: float = Field(default=30.0, gt=0, description='meters — maximum equivalent narcotic depth'); sac_bottom: float = Field(default=20.0, gt=0, description='L/min — surface air consumption at bottom'); sac_deco: float = Field(default=15.0, gt=0, description='L/min — surface air consumption at deco stops'); sac_factor: float = Field(default=2.0, gt=0, description='stress multiplier on SAC for rock-bottom/emergency planning'); problem_solving_minutes: float = Field(default=1.0, ge=0, description='minutes spent solving a problem at depth (rock bottom)'); gas_switch_minutes: float = Field(default=1.0, ge=0, description='minutes added per gas switch — 0 = instant'); gas_switch_at_stops_only: bool = Field(default=True, description='if True, gas switches only allowed at deco stops')`
- `_try_load(path: Path | str, source: str, config_cls: type[DiveConfig]) -> DiveConfig | None`  — Attempt to load a DiveConfig from a file. Returns None on any failure.
- `_load_default_config() -> DiveConfig`  — Resolve the startup default config following the priority chain:
### class `DiveConfig` (BaseModel) — Root configuration object.
  - @classmethod `current(cls) -> DiveConfig`  — Return the active config — top of the (context-local) stack, or startup default.
  - @classmethod `set_default(cls, config: DiveConfig) -> None`  — Permanently replace the global default config.
  - @classmethod `reset_default(cls) -> None`  — Restore factory defaults and clear the stack — useful in tests.
  - `__enter__(self) -> DiveConfig`
  - `__exit__(self, *_) -> None`
  - `to_json(self, path: str | None = None, indent: int = 2) -> str`  — Serialize to JSON string, optionally writing to file.
  - @classmethod `from_json(cls, data: str | None = None, path: str | None = None) -> DiveConfig`  — Deserialize from JSON string or file path.
  attrs: `model_config = ConfigDict(frozen=True); physics: _PhysicsConfig = Field(default_factory=_PhysicsConfig); planning: _DivePlanningConfig = Field(default_factory=_DivePlanningConfig); gas: _GasConfig = Field(default_factory=_GasConfig)`
  dunders: `__repr__, __str__`

## `src/diveplan/core/dive_segment.py`
Dive segment: one leg of a dive profile.
`__all__ = ['SegmentKind', 'DiveSegment']`
### class `SegmentKind` — Namespace of segment-kind enums, grouped by direction of travel.
  - class `Descent` (Enum) — Downward traverses (start pressure below end pressure).
    attrs: `DESCENT = auto()`
  - class `Ascent` (Enum) — Upward traverses: planned deco legs vs. forced (direct) ascents.
    attrs: `FORCED_ASCENT = auto(); DECO_ASCENT = auto()`
  - class `Constant` (Enum) — Constant-depth segments: bottom time, deco stops, gas switches.
    attrs: `BOTTOM = auto(); STOP = auto(); GAS_SWITCH = auto()`
  - @staticmethod `from_name(name: str) -> SegmentKind.Members`  — Look up a segment kind by member name, e.g. ``"DESCENT"``, ``"STOP"``.
  attrs: `DESCENT = Descent.DESCENT; ASCENT = Ascent.FORCED_ASCENT; CONSTANT = Constant.BOTTOM; Members = Descent | Ascent | Constant`
### class `DiveSegment` — One leg of a dive profile: pressures, duration, gas, and kind.
  `__slots__ = ('start_pressure', 'end_pressure', 'duration', 'gas', 'kind')`
  - `__init__(self, start_pressure: Pressure, end_pressure: Pressure, duration: timedelta | int | float, gas: Gas, *, ascent_kind: SegmentKind.Ascent = SegmentKind.ASCENT, constant_kind: SegmentKind.Constant = SegmentKind.CONSTANT)`  — Args:
  - `_determine_kind(self, ascent_kind: SegmentKind.Ascent, constant_kind: SegmentKind.Constant) -> SegmentKind.Members`
  - @property `average_pressure(self) -> Pressure`  — Mean of the start and end pressures.
  - @property `absolute_pressure_change(self) -> Pressure`  — Magnitude of the pressure change from start to end (always non-negative).
  - @property `pressure_rate(self) -> float`  — Signed rate of pressure change in mbar per second.
  - `_validate_time(self, t: timedelta) -> None`
  - `_validate_fraction(self, fraction: float) -> None`
  - `_validate_pressure(self, pressure: Pressure) -> None`
  - `pressure_at_time(self, t: timedelta) -> Pressure`  — Pressure at time t into the segment. Linear interpolation.
  - `pressure_at_fraction(self, fraction: float) -> Pressure`  — Pressure at fraction (0 to 1) into the segment. Linear interpolation.
  - `time_at_pressure(self, pressure: Pressure) -> timedelta`  — Time at which a given pressure is reached. Linear interpolation.
  - `time_at_fraction(self, fraction: float) -> timedelta`  — Time at which a given fraction (0 to 1) is reached. Linear interpolation.
  - `fraction_at_pressure(self, pressure: Pressure) -> float`  — Fraction (0 to 1) at which a given pressure is reached. Linear interpolation.
  - `fraction_at_time(self, t: timedelta) -> float`  — Fraction (0 to 1) at time t into the segment. Linear interpolation.
  - `split_at_time(self, t: timedelta) -> tuple[DiveSegment, DiveSegment]`  — Split into two segments at time t — useful for injecting a gas switch mid-segment.
  - `split_at_fraction(self, fraction: float) -> tuple[DiveSegment, DiveSegment]`  — Split into two segments at fraction (0 to 1) — useful for injecting a gas switch mid-segment.
  - `merge_with(self, other: DiveSegment, *, force: bool = False) -> DiveSegment`  — Merge with another segment if they are continuous (end pressure of self matches start pressure of other).
  - `is_pressure_continuous_with(self, other: DiveSegment) -> bool`  — End pressure of self matches start pressure of other.
  - `is_gas_continuous_with(self, other: DiveSegment) -> bool`  — Same gas on both segments (Nones treated as unknown — not continuous).
  - `is_rate_continuous_with(self, other: DiveSegment) -> bool`  — Same pressure rate across the boundary — segments form an unbroken linear traverse.
  - `is_continuous_with(self, other: DiveSegment, *, check_gas: bool = False, check_rate: bool = False) -> bool`  — Pressure-continuous by default.
  - `is_fully_continuous_with(self, other: DiveSegment) -> bool`  — Convenience — checks pressure, gas, and rate together.
  - `iter_pressures(self, interval: timedelta, *, include_end: bool = True) -> Iterator[tuple[timedelta, Pressure]]`  — Yield (elapsed, pressure) at each interval through the segment.
  - `to_dict(self) -> dict[str, Any]`  — Serialize to a JSON-compatible dict.
  - @classmethod `from_dict(cls, data: Mapping[str, Any]) -> DiveSegment`  — Reconstruct a DiveSegment from :meth:`to_dict` output.
  - `to_json(self, indent: int | None = None) -> str`  — Serialize to a JSON string.
  - @classmethod `from_json(cls, data: str) -> DiveSegment`  — Reconstruct a DiveSegment from a JSON string (see :meth:`from_dict`).
  attrs: `start_pressure: Pressure; end_pressure: Pressure; duration: timedelta; gas: Gas; kind: SegmentKind.Members`
  dunders: `__delattr__, __eq__, __hash__, __repr__, __setattr__, __str__`

## `src/diveplan/core/gas.py`
Gas mix value object for diveplan.
`__all__ = ['Gas']`
### class `Gas` — Immutable O2/He/N2 breathing gas mixture.
  `__slots__ = ('_fo2', '_fhe', '_fn2')`
  - `__init__(self, fo2: float, fhe: float = 0.0) -> None`
  - @property `fo2(self) -> float`  — Oxygen fraction (0.0-1.0).
  - @property `fhe(self) -> float`  — Helium fraction (0.0-1.0).
  - @property `fn2(self) -> float`  — Nitrogen fraction (0.0-1.0), derived as ``1 - fo2 - fhe``.
  - @property `name(self) -> str`  — Human-readable name for this gas, e.g. "Air", "EAN32", "TX21/35".
  - @classmethod `air(cls) -> Gas`  — Return standard air (21 % O2, 79 % N2).
  - @classmethod `oxygen(cls) -> Gas`  — Return 100 % oxygen.
  - @classmethod `nitrox(cls, fo2: float) -> Gas`  — Return a nitrox (O2/N2) mix with the given O2 fraction.
  - @classmethod `ean(cls, fo2: float) -> Gas`  — Alias for :meth:`nitrox`.
  - @classmethod `trimix(cls, fo2: float, fhe: float) -> Gas`  — Return a trimix (O2/He/N2) gas.
  - @classmethod `from_name(cls, name: str) -> Gas`  — Parse a gas mix from a human-readable name string.
  - `ppo2(self, pressure: Pressure) -> Pressure`  — Return the partial pressure of O2 at the given ambient pressure.
  - `pphe(self, pressure: Pressure) -> Pressure`  — Return the partial pressure of He at the given ambient pressure.
  - `ppn2(self, pressure: Pressure) -> Pressure`  — Return the partial pressure of N2 at the given ambient pressure.
  - `mod(self, *, ppo2_bar: float) -> Pressure`  — Return the maximum operating depth (MOD) for a given ppO2 limit.
  - `end(self, pressure: Pressure) -> Pressure`  — Return the equivalent narcotic depth (END) at the given pressure.
  - `best_mix(self, depth: float | Pressure, *, trimix: bool = False, hypoxic: bool = False) -> Gas`  — Return the optimal gas mix for the given depth.
  dunders: `__eq__, __hash__, __repr__, __setattr__, __str__`

## `src/diveplan/core/pressure.py`
core/pressure.py — Pressure value type.
`__all__ = ['Pressure', 'PressureUnit']`
- const `PressureUnit = Literal['bar', 'mbar', 'atm', 'psi', 'm', 'ft']`
### class `Pressure` — Absolute pressure stored as integer millibar.
  `__slots__ = ('_mbar',)`
  - `__init__(self, mbar: int) -> None`
  - @classmethod `from_bar(cls, bar: float) -> Pressure`  — Construct from bar. Rounds to nearest mbar.
  - @classmethod `from_mbar(cls, mbar: float) -> Pressure`  — Construct from float mbar. Rounds to nearest integer mbar.
  - @classmethod `from_depth_m(cls, depth_m: float) -> Pressure`  — Construct from depth in metres using the current DiveConfig environment.
  - @classmethod `from_atm(cls, atm: float) -> Pressure`  — Construct from atmospheres. Rounds to nearest mbar.
  - @classmethod `from_psi(cls, psi: float) -> Pressure`  — Construct from psi. Rounds to nearest mbar.
  - @classmethod `from_depth_ft(cls, depth_ft: float) -> Pressure`  — Construct from depth in feet using the current DiveConfig environment.
  - @classmethod `surface(cls) -> Pressure`  — Convenience constructor for surface pressure in the current DiveConfig environment.
  - @classmethod `from_str(cls, s: str) -> Pressure`  — Parse a pressure from a string with unit suffix. Supported formats:
  - @property `mbar(self) -> int`  — Absolute pressure in integer millibar (the ground-truth value).
  - @property `bar(self) -> float`  — Absolute pressure in bar.
  - @property `depth_m(self) -> float`  — Depth in metres in the context of the current DiveConfig environment.
  - @property `depth_ft(self) -> float`  — Depth in feet in the context of the current DiveConfig environment.
  - @property `atm(self) -> float`  — Absolute pressure in atmospheres, relative to the current surface pressure.
  - @property `psi(self) -> float`  — Absolute pressure in pounds per square inch.
  - @property `is_surface(self) -> bool`  — Whether this pressure is at (or above) the configured surface.
  - `to_str(self, unit: PressureUnit = 'bar') -> str`  — Format pressure as a string in the specified unit.
  attrs: `_PSI_PER_MBAR = 0.0145038`
  dunders: `__add__, __delattr__, __eq__, __ge__, __gt__, __hash__, __le__, __lt__, __mul__, __repr__, __rmul__, __setattr__, __str__, __sub__, __truediv__, __truediv__, __truediv__`

## `src/diveplan/dive/__init__.py`
(empty stub)

## `src/diveplan/dive/dive.py`
Dive: a deco model run over a profile, queryable and extendable.
`__all__ = ['Dive', 'TtsVariations']`
### class `TtsVariations` (NamedTuple) — Sensitivity of the time-to-surface to small plan changes — the
  attrs: `per_meter: timedelta; per_minute: timedelta`
### class `Dive[StateT: DecoState]` — A deco model's run over a profile — complete or still in progress.
  `__slots__ = ('_profile', '_model', '_checkpoints')`
  - `__init__(self, profile: DiveProfile, model: BaseDecoModel[StateT], checkpoints: tuple[StateT, ...])`
  - @classmethod `run(cls, profile: DiveProfile, model: BaseDecoModel[StateT]) -> 'Dive[StateT]'`  — Integrate `model` over `profile` and capture boundary checkpoints.
  - @property `profile(self) -> DiveProfile`  — The dive profile this dive was computed from (own copy).
  - @property `checkpoints(self) -> tuple[StateT, ...]`  — Model states at segment boundaries; ``[0]`` is the pre-dive state,
  - @property `final_state(self) -> StateT`  — Model state at the end of the profile.
  - `model_at(self, t: timedelta | float) -> BaseDecoModel[StateT]`  — Independent model instance positioned at runtime `t`.
  - `state_at(self, t: timedelta | float) -> StateT`  — Model state at runtime `t` (minutes or timedelta).
  - `ceiling_at(self, t: timedelta | float) -> Pressure`  — Deco ceiling at runtime `t`.
  - `cns_at(self, t: timedelta | float) -> float`  — CNS oxygen-toxicity clock accumulated by runtime `t`, in percent.
  - `otu_at(self, t: timedelta | float) -> float`  — Pulmonary oxygen-toxicity units (REPEX) accumulated by runtime `t`.
  - `_segments_until(self, t: timedelta | float) -> list[DiveSegment]`  — The profile's segments up to `t`, the last one truncated exactly.
  - `tissue_series(self, interval: timedelta | float) -> Iterator[tuple[timedelta, StateT]]`  — Yield (time, state) at each sample step — for tissue plots.
  - `tts(self, t: timedelta | float, gas_plan: GasPlan | None = None) -> timedelta`  — Time-to-surface at runtime `t`: the duration of an ascent planned
  - `plan_ascent(self, gas_plan: GasPlan | None = None) -> list[DiveSegment]`  — Deco schedule from the dive's current end to the surface.
  - `extend(self, segments: list[DiveSegment]) -> 'Dive[StateT]'`  — New Dive with `segments` appended and integrated.
  - `with_ascent(self, gas_plan: GasPlan | None = None) -> 'Dive[StateT]'`  — New Dive completed with its planned deco ascent —
  - `tts_variations(self, gas_plan: GasPlan | None = None) -> TtsVariations`  — Extra time-to-surface per +1 m on the final segment and per +1 min
  - `_unique_gases(self) -> list[Gas]`
  - @property `model_name(self) -> str`  — Name of the model this result was computed with, conservatism
  dunders: `__repr__`
- `_ascent_duration(model: BaseDecoModel[Any], start_pressure: Pressure, gas: Gas, gas_plan: GasPlan, clock_offset: timedelta) -> timedelta`

## `src/diveplan/dive/dive_profile.py`
Dive profile: the geometric plan of a dive.
`__all__ = ('DiveProfile', 'ProfileSample', 'ProfileValidationError', 'ProfileContinuityError', 'ProfileSimplicityError', 'ProfileStartEndError', 'ProfileDepthContinuityError', 'ProfileGasContinuityError', 'ProfileEmptyError', 'ProfileTooShortError', 'ProfileBuilderPolicy')`
### class `ProfileValidationError` (ValueError) — Base descriptor for a dive profile validation problem.
  - `__init__(self, message: str, *, segment_index: int | None = None, segments: tuple[DiveSegment, ...] = ())`
  attrs: `fixable: bool = False`
### class `ProfileEmptyError` (ProfileValidationError) — The profile has no segments. Not auto-fixable.
  - `__init__(self) -> None`
  attrs: `fixable = False`
### class `ProfileTooShortError` (ProfileValidationError) — The profile has fewer than 2 segments (surface → dive → surface). Not auto-fixable.
  - `__init__(self, segment_count: int) -> None`
  attrs: `fixable = False`
### class `ProfileStartEndError` (ProfileValidationError) — The profile does not start and end at the surface. Fixable via add_surface_segments().
  - `__init__(self, first_segment: DiveSegment, last_segment: DiveSegment) -> None`
  attrs: `fixable = True`
### class `ProfileContinuityError` (ProfileValidationError) — Base for problems at the seam between two adjacent segments.
  - `__init__(self, message: str, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment)`
  attrs: `segment_index: int`
### class `ProfileDepthContinuityError` (ProfileContinuityError) — The end pressure of one segment does not match the start of the next. Fixable via a transition segment.
  - `__init__(self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment) -> None`
  attrs: `fixable = True`
### class `ProfileGasContinuityError` (ProfileContinuityError) — Adjacent segments use different gases without a gas switch. Fixable via a gas switch segment.
  - `__init__(self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment) -> None`
  attrs: `fixable = True`
### class `ProfileSimplicityError` (ProfileContinuityError) — Adjacent segments are fully continuous and could be merged. Fixable via merge.
  - `__init__(self, segment_index: int, segment_a: DiveSegment, segment_b: DiveSegment) -> None`
  attrs: `fixable = True`
### class `ProfileBuilderPolicy` (Enum) — Policies for handling validation during dive profile construction.
  attrs: `RAISE_BAD_PROFILE = auto(); ALLOW_BAD_PROFILE = auto(); AUTOFIX_BAD_PROFILE = auto()`
- `_as_timedelta(value: timedelta | float) -> timedelta`  — Coerce a time argument: timedelta as-is, bare numbers as minutes
### class `ProfileSample` (NamedTuple) — One integration step on the profile's global timeline.
  attrs: `time: timedelta; dt: timedelta; pressure: Pressure; gas: Gas; segment_index: int`
### class `DiveProfile` — A dive profile consisting of a sequence of dive segments.
  `__slots__ = ('_segments', '_builder_policy')`
  - `__init__(self, builder_policy: ProfileBuilderPolicy = ProfileBuilderPolicy.RAISE_BAD_PROFILE)`  — Initialize a new DiveProfile.
  - @property `builder_policy(self) -> ProfileBuilderPolicy`  — The active profile builder policy.
  - `copy(self, *, override_policy: ProfileBuilderPolicy | None = None) -> DiveProfile`  — Create a copy of the dive profile.
  - `_get_last_pressure(self) -> Pressure`  — Current position — the end pressure of the last segment, or surface if empty.
  - `_get_last_gas(self) -> Gas`  — Get the gas of the last segment, or air if empty.
  - @property `segments(self) -> list[DiveSegment]`  — The list of segments in the profile.
  - @property `segment_count(self) -> int`  — The number of segments in the profile.
  - @property `runtime(self) -> timedelta`  — Total duration of the profile (sum of all segment durations).
  - `start_time_of_segment(self, index: int) -> timedelta`  — Elapsed runtime at which the segment at `index` begins.
  - `segment_index_at(self, t: timedelta | float) -> int`  — Index of the segment active at runtime `t` (minutes or timedelta).
  - `segment_at(self, t: timedelta | float) -> DiveSegment`  — The segment active at runtime `t` (minutes or timedelta).
  - `pressure_at(self, t: timedelta | float) -> Pressure`  — Ambient pressure at runtime `t` (minutes or timedelta), interpolated
  - `gas_at(self, t: timedelta | float) -> Gas`  — Breathing gas at runtime `t` (minutes or timedelta).
  - `iter_samples(self, interval: timedelta | float) -> Iterator[ProfileSample]`  — Yield integration steps over the whole profile timeline.
  - @staticmethod `_is_gas_switch_seam(a: DiveSegment, b: DiveSegment) -> bool`  — A seam is a legitimate gas switch if either side is a GAS_SWITCH segment.
  - @staticmethod `_is_mergeable(a: DiveSegment, b: DiveSegment) -> bool`  — Adjacent segments are redundant only if fully continuous AND of the
  - `_seam_error(self, a: DiveSegment, b: DiveSegment, index: int) -> ProfileValidationError | None`  — Return the most fundamental continuity error at the seam (a → b), or None.
  - `_raise_on_seam(self, a: DiveSegment, b: DiveSegment, index: int) -> None`  — Under RAISE policy, raise the seam error (a → b) if there is one.
  - `_check_insertion(self, index: int, segment: DiveSegment) -> None`  — Under RAISE policy, validate the seam(s) a new segment at `index` would create.
  - `_autofix(self) -> None`  — Under AUTOFIX policy, insert transitions and gas switches.
  - `add_segment(self, segment: DiveSegment) -> DiveProfile`  — Append a segment to the profile.
  - `add_segments(self, segments: list[DiveSegment]) -> DiveProfile`  — Append multiple segments to the profile (each via add_segment).
  - `remove_segment_at_index(self, index: int) -> DiveProfile`  — Remove a segment at a specific index.
  - `remove_segment_at_indices(self, indices: list[int]) -> DiveProfile`  — Remove multiple segments at specific indices.
  - `remove_segment(self, segment: DiveSegment) -> DiveProfile`  — Remove a segment by value.
  - `remove_segments(self, segments: list[DiveSegment]) -> DiveProfile`  — Remove multiple segments by value.
  - `remove_last_segment(self) -> DiveProfile`  — Remove the final segment from the profile.
  - `clear_profile(self) -> DiveProfile`  — Clear all segments from the profile.
  - `insert_segment_at_index(self, index: int, segment: DiveSegment) -> DiveProfile`  — Insert a segment at a specific index.
  - `insert_segments_at_index(self, index: int, segments: list[DiveSegment]) -> DiveProfile`  — Insert multiple segments at a specific index, in order.
  - `replace_segment_at_index(self, index: int, segment: DiveSegment) -> DiveProfile`  — Replace a segment at a specific index.
  - `get_segment(self, index: int) -> DiveSegment`  — Retrieve a segment by its index.
  - `get_last_segment(self) -> DiveSegment`  — Get the last segment in the profile.
  - `get_first_segment(self) -> DiveSegment`  — Get the first segment in the profile.
  - `get_segment_index(self, segment: DiveSegment) -> int`  — Find the index of a specific segment.
  - `descend_to(self, depth: Pressure | str | float, *, rate: float | None = None, gas: Gas | str | None = None) -> DiveProfile`  — Append a descent from the current position to `depth`.
  - `ascend_to(self, depth: Pressure | str | float, *, rate: float | None = None, gas: Gas | str | None = None, kind: SegmentKind.Ascent = SegmentKind.ASCENT) -> DiveProfile`  — Append an ascent from the current position to `depth`.
  - `stay(self, duration: timedelta | float, *, gas: Gas | str | None = None, kind: SegmentKind.Constant = SegmentKind.CONSTANT) -> DiveProfile`  — Append a constant-depth segment at the current position.
  - `switch_gas(self, gas: Gas | str) -> DiveProfile`  — Append a gas switch at the current position.
  - `surface(self) -> DiveProfile`  — Append an ascent from the current position to the surface at the
  - @property `is_valid(self) -> bool`  — Whether the profile is continuous and gas-continuous.
  - `validate_profile(self, *, skip_simplicity: bool = False, skip_start_end_segments: bool = True) -> tuple[ProfileValidationError, ...]`  — Validate the whole profile and return all problems found.
  - `fix(self, error: ProfileValidationError) -> DiveProfile`  — Apply the canonical repair for a single validation error.
  - `fix_all(self) -> DiveProfile`  — Repeatedly validate and repair until no fixable error remains.
  - @staticmethod `make_transition_segment(segment_a: DiveSegment, segment_b: DiveSegment) -> DiveSegment`  — Create a segment bridging a pressure gap between two segments.
  - @staticmethod `make_gas_switch_segment(segment_a: DiveSegment, segment_b: DiveSegment) -> DiveSegment`  — Create a gas switch segment between two pressure-continuous segments.
  - `simplify_profile(self) -> DiveProfile`  — Merge fully continuous adjacent segments to simplify the profile.
  - `fix_continuity(self) -> DiveProfile`  — Insert transition segments to resolve pressure discontinuities (in place).
  - `fix_gas_continuity(self) -> DiveProfile`  — Insert gas switch segments to resolve gas discontinuities (in place).
  - `add_start_surface_segment(self) -> DiveProfile`  — Ensure the profile starts with a descent from the surface.
  - `add_end_surface_segment(self) -> DiveProfile`  — Ensure the profile ends with an ascent to the surface.
  - `add_surface_segments(self) -> DiveProfile`  — Ensure the profile both starts and ends at the surface.
  - `to_dict(self) -> dict[str, Any]`  — Serialize to a JSON-compatible dict (builder policy + segments).
  - @classmethod `from_dict(cls, data: Mapping[str, Any]) -> DiveProfile`  — Reconstruct a DiveProfile from :meth:`to_dict` output.
  - `to_json(self, path: str | None = None, indent: int = 2) -> str`  — Serialize to a JSON string, optionally writing to a file.
  - @classmethod `from_json(cls, data: str | None = None, path: str | None = None) -> DiveProfile`  — Deserialize from a JSON string or file path (see :meth:`from_dict`).

## `src/diveplan/dive/dive_report.py`
Dive report: everything about a computed dive, ready for presentation.
`__all__ = ['DiveReport', 'ReportRow']`
### class `ReportRow` (NamedTuple) — One schedule line: a segment with its cumulative runtime at the end.
  attrs: `runtime: timedelta; start_depth_m: float; end_depth_m: float; duration: timedelta; gas: Gas; kind: str`
### class `DiveReport` — Immutable summary of a computed dive.
  `__slots__ = ('profile', 'model_name', 'rows', 'runtime', 'max_depth', 'consumption_l', 'cns', 'otus', 'rock_bottom_l', 'sac_bottom', 'sac_deco', 'sac_factor', 'tts_variations')`
  - `__init__(self, *, profile: DiveProfile, model_name: str, rows: tuple[ReportRow, ...], runtime: timedelta, max_depth: Pressure, consumption_l: tuple[tuple[Gas, float], ...], cns: float, otus: float, rock_bottom_l: float, sac_bottom: float, sac_deco: float, sac_factor: float, tts_variations: TtsVariations | None)`
  - @classmethod `from_dive(cls, dive: Dive[DecoState], *, gas_plan: GasPlan | None = None, tts_variations: TtsVariations | None = None) -> 'DiveReport'`  — Assemble a report from a computed dive.
  attrs: `profile: DiveProfile; model_name: str; rows: tuple[ReportRow, ...]; runtime: timedelta; max_depth: Pressure; consumption_l: tuple[tuple[Gas, float], ...]; cns: float; otus: float; rock_bottom_l: float; sac_bottom: float; sac_deco: float; sac_factor: float; tts_variations: TtsVariations | None`
  dunders: `__repr__`

## `src/diveplan/dive/formatters/__init__.py`
Report formatters: turn a DiveReport into an output document.
`__all__ = ['BaseFormatter']`
### class `BaseFormatter` (ABC) — Base class for all report formatters.
  - `__init__(self, **options) -> None`  — Formatters take keyword options only, defined per formatter.
  - @abstract `format(self, report: DiveReport) -> str`  — Render the report as a string in this formatter's output format.
  - `write(self, report: DiveReport, path: str | Path) -> None`  — Render the report and write it to `path` (UTF-8, LF endings).
  - `print(self, report: DiveReport) -> None`  — Render the report and print it to stdout.
  attrs: `NAME: ClassVar[str]`

## `src/diveplan/dive/formatters/console.py`
Plain-text report formatter for terminals and logs.
`__all__ = ['ConsoleFormatter']`
- `_minutes(td: timedelta) -> str`
- `_row_line(row: ReportRow) -> str`
### class `ConsoleFormatter` (BaseFormatter) — Human-readable dive plan table with a summary block.
  - @staticmethod `format_schedule(segments: Iterable[DiveSegment]) -> str`  — Render any segment sequence (a profile's or an ascent plan) as a
  - `format(self, report: DiveReport) -> str`  — Render the full report: header, schedule table, totals block.
  attrs: `NAME = 'console'`

## `src/diveplan/dive/formatters/json.py`
JSON report formatter — machine-readable dive plan document.
`__all__ = ['JsonFormatter']`
### class `JsonFormatter` (BaseFormatter) — Serialize the whole report to a JSON document.
  - `__init__(self, *, indent: int | None = 2)`
  - `format(self, report: DiveReport) -> str`  — Render the report as a JSON document string.
  attrs: `NAME = 'json'`

## `src/diveplan/dive/formatters/rich_console.py`
Rich terminal formatter: the report as styled tables.
`__all__ = ['RichConsoleFormatter']`
- `_minutes(td: timedelta) -> str`
- `_action(row: ReportRow) -> str`
### class `RichConsoleFormatter` (BaseFormatter) — Styled terminal rendering of a dive report.
  - `__init__(self, *, styled: bool = True, width: int = 72)`
  - `print(self, report: DiveReport, console: Console | None = None) -> None`  — Render the report directly to a terminal (auto-detected styling).
  - `format(self, report: DiveReport) -> str`  — Render the report to a string (ANSI-styled when ``styled=True``).
  - `_renderable(self, report: DiveReport) -> RenderableType`
  attrs: `NAME = 'rich'`

## `src/diveplan/dive/formatters/runtime.py`
Runtime-table formatter: the plan as a diver would write it on a slate.
`__all__ = ['RuntimeFormatter']`
- `_minutes(td: timedelta) -> int`
### class `RuntimeFormatter` (BaseFormatter) — Printable runtime sheet: depth / duration / runtime / gas.
  - `format(self, report: DiveReport) -> str`  — Render the runtime sheet as plain ASCII text.
  - @staticmethod `_table_rows(report: DiveReport) -> list[tuple[str, float, timedelta, timedelta, Gas]]`  — Fold deco travel/switches into stop rows; keep phase boundaries.
  attrs: `NAME = 'runtime'`

## `src/diveplan/dive/formatters/subsurface.py`
Subsurface dive-log XML formatter.
`__all__ = ['SubsurfaceXmlFormatter']`
- `_mmss(td: timedelta) -> str`
- `_depth(metres: float) -> str`
- `_gas_attrs(gas: Gas) -> dict[str, str]`
### class `SubsurfaceXmlFormatter` (BaseFormatter) — Render the report as a Subsurface dive-log XML document.
  - `__init__(self, *, planned_at: datetime | None = None)`
  - `format(self, report: DiveReport) -> str`  — Render the report as a Subsurface dive-log XML string.
  attrs: `NAME = 'subsurface'; SAMPLE_STEP = timedelta(seconds=10)`

## `src/diveplan/models/__init__.py`
(empty stub)

## `src/diveplan/models/base.py`
Decompression model base classes.
`__all__ = ['BaseDecoModel', 'DecoState']`
### class `DecoState` — Base class for model-specific decompression state snapshots.
  `__slots__ = ()`
### class `BaseDecoModel[StateT: DecoState]` (ABC) — Base class for all decompression models.
  `__slots__ = ('sample_rate_seconds',)`
  - @abstract `__init__(self, *args, **kwargs) -> None`  — Initialize the decompression model.
  - @property `name(self) -> str`  — Display name of this model instance, conservatism included.
  - `integrate_segment(self, segment: DiveSegment) -> StateT`  — Integrate a dive segment into the model and return the state after it.
  - `get_state(self) -> StateT`  — Snapshot the current model state (public accessor).
  - `integrate(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None`  — Advance the model by a single step at the given pressure and gas.
  - @abstract `_integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None`  — Advance the model by dt at the given ambient pressure and gas.
  - @abstract `_get_deco_state(self) -> StateT`  — Snapshot the current model state.
  - @abstract `get_ceiling(self) -> Pressure`  — Return the current ceiling depth.
  - @abstract `set_state(self, state: StateT) -> None`  — Restore the model to a previously snapshotted state (lossless).
  - @abstract `copy(self) -> Self`  — Independent clone with identical configuration and current state.
  attrs: `NAME: ClassVar[str]`

## `src/diveplan/models/buhlmann/__init__.py`
Bühlmann-family decompression models.
`__all__ = ['BuhlmannModel', 'BuhlmannState', 'ZHL16C', 'Compartment', 'Gradient']`

## `src/diveplan/models/buhlmann/common.py`
Shared Bühlmann machinery: gradient factors and Haldane tissue compartments.
`__all__ = ('Gradient', 'Compartment', 'WATER_VAPOR_PRESSURE_MBAR')`
- const `WATER_VAPOR_PRESSURE_MBAR = 62.7`
### class `Gradient` — A gradient-factor pair (Baker GF low/high), as fractions.
  `__slots__ = ('gf_low', 'gf_high')`
  - `__init__(self, gf_low: float, gf_high: float)`
  - @classmethod `from_str(cls, s: str) -> 'Gradient'`  — Parse the usual GF notation: ``"30/70"``, ``"GF 30/70"``, ``"85/85"``.
  - `factor(self, pressure: Pressure, first_stop_pressure: Pressure) -> float`  — Gradient factor applicable at ``pressure``.
  attrs: `gf_low: float; gf_high: float`
  dunders: `__eq__, __hash__, __repr__, __str__`
### class `Compartment` — One Haldane tissue compartment with Bühlmann a/b coefficients.
  `__slots__ = ('ht_n2', 'ht_he', 'a_n2', 'a_he', 'b_n2', 'b_he', '_ppn2_mbar', '_pphe_mbar')`
  - `__init__(self, *, ht_n2: float, ht_he: float, a_n2: float, a_he: float, b_n2: float, b_he: float, ppn2: Pressure | None = None, pphe: Pressure | None = None)`
  - @property `ppn2(self) -> Pressure`  — Current N2 tension (rounded to integer mbar for display/compare).
  - @property `pphe(self) -> Pressure`  — Current He tension (rounded to integer mbar for display/compare).
  - @property `tensions_mbar(self) -> tuple[float, float]`  — Exact (ppn2, pphe) tensions in float mbar — for state snapshots.
  - `set_tensions_mbar(self, ppn2_mbar: float, pphe_mbar: float) -> None`  — Restore exact tensions from a state snapshot.
  - `copy(self) -> 'Compartment'`  — Independent copy with the same constants and current tensions.
  - `integrate(self, pressure: Pressure, gas: Gas, duration: timedelta) -> None`  — Haldane exponential update toward the alveolar inert pressures.
  - `tolerated_ambient_pressure(self, gradient_factor: float = 1.0) -> Pressure`  — Minimum ambient pressure this compartment tolerates (Baker formula).
  attrs: `ht_n2: float; ht_he: float; a_n2: float; a_he: float; b_n2: float; b_he: float`
  dunders: `__eq__, __hash__, __repr__, __str__`

## `src/diveplan/models/buhlmann/model.py`
Generic Bühlmann decompression engine.
`__all__ = ['BuhlmannModel', 'BuhlmannState']`
### class `BuhlmannState` (DecoState) — Frozen snapshot of (ppn2, pphe) tissue tensions in float mbar.
  `__slots__ = ('tissues',)`
  - `__init__(self, tissues: tuple[tuple[float, float], ...])`
  attrs: `tissues: tuple[tuple[float, float], ...]`
  dunders: `__delattr__, __eq__, __hash__, __repr__, __setattr__`
### class `BuhlmannModel` (BaseDecoModel[BuhlmannState]) — Bühlmann algorithm over a subclass-supplied coefficient table.
  `__slots__ = ('gradient', '_compartments')`
  - `__init__(self, gradient: Gradient | str | None = None)`
  - @property `name(self) -> str`  — Registry name plus gradient factors — e.g. ``"zhl16c GF 30/70"``.
  - @property `compartment_count(self) -> int`  — Number of tissue compartments in this model's table.
  - `_integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None`
  - `_get_deco_state(self) -> BuhlmannState`
  - `get_ceiling(self, gradient_factor: float | None = None) -> Pressure`  — Minimum tolerated ambient pressure across all compartments.
  - `set_state(self, state: BuhlmannState) -> None`  — Restore tissue tensions from a snapshot (exact, lossless).
  - `copy(self) -> Self`  — Independent clone with the same gradient and tissue tensions —
  attrs: `N2_HALF_TIMES: ClassVar[tuple[float, ...]]; N2_A: ClassVar[tuple[float, ...]]; N2_B: ClassVar[tuple[float, ...]]; HE_HALF_TIMES: ClassVar[tuple[float, ...]]; HE_A: ClassVar[tuple[float, ...]]; HE_B: ClassVar[tuple[float, ...]]; gradient: Gradient`
  dunders: `__init_subclass__, __repr__`

## `src/diveplan/models/buhlmann/zhl16.py`
Bühlmann ZHL-16 variants — coefficient tables over the shared engine.
`__all__ = ['ZHL16C', 'BuhlmannState']`
### class `ZHL16C` (BuhlmannModel) — Bühlmann ZHL-16C, 16 compartments (1b first-compartment variant).
  `__slots__ = ()`
  attrs: `NAME = 'zhl16c'; N2_HALF_TIMES = (5.0, 8.0, 12.5, 18.5, 27.0, 38.3, 54.3, 77.0, 109.0, 146.0, 187.0, 239.0, 305.0, 390.0, 498.0, 635.0); N2_A = (1.1696, 1.0, 0.8618, 0.7562, 0.62, 0.5043, 0.441, 0.4, 0.375, 0.35, 0.3295, 0.3065, 0.2835, 0.261, 0.248, 0.2327); N2_B = (0.5578, 0.6514, 0.7222, 0.7825, 0.8126, 0.8434, 0.8693, 0.891, 0.9092, 0.9222, 0.9319, 0.9403, 0.9477, 0.9544, 0.9602, 0.9653); HE_HALF_TIMES = (1.88, 3.02, 4.72, 6.99, 10.21, 14.48, 20.53, 29.11, 41.2, 55.19, 70.69, 90.34, 115.29, 147.42, 188.24, 240.03); HE_A = (1.6189, 1.383, 1.1919, 1.0458, 0.922, 0.8205, 0.7305, 0.6502, 0.595, 0.5545, 0.5333, 0.5189, 0.5181, 0.5176, 0.5172, 0.5119); HE_B = (0.477, 0.5747, 0.6527, 0.7223, 0.7582, 0.7957, 0.8279, 0.8553, 0.8757, 0.8903, 0.8997, 0.9073, 0.9122, 0.9171, 0.9217, 0.9267)`

## `src/diveplan/models/vpm/__init__.py`
VPM-family (bubble) decompression models.
`__all__ = ['VpmB', 'VpmState']`

## `src/diveplan/models/vpm/model.py`
VPM-B decompression model (Varying Permeability Model, revision B).
`__all__ = ['VpmB', 'VpmState']`
- const `SURFACE_TENSION_GAMMA = 0.18137175`
- const `SKIN_COMPRESSION_GAMMA_C = 2.6040525`
- const `CRIT_RADIUS_N2_UM = 0.55`
- const `CRIT_RADIUS_HE_UM = 0.45`
- const `GRADIENT_OF_IMPERMEABILITY_BAR = 8.30865`
- const `REGENERATION_TIME_MIN = 20160.0`
- const `OTHER_GASES_PRESSURE_BAR = 0.1359888`
- const `CRIT_VOLUME_LAMBDA_BAR_MIN = 199.58`
- const `CONSERVATISM_RADIUS_SCALE = (1.0, 1.05, 1.12, 1.22, 1.35)`
- `allowable_gradient_bar(radius_um: float) -> float`  — Initial allowable supersaturation gradient for a nucleus of `radius_um`.
- `crushed_radius_um(max_crushing_bar: float, initial_radius_um: float) -> float`  — Nucleus radius after being crushed by `max_crushing_bar`.
- `regenerated_radius_um(crushed_um: float, initial_radius_um: float, elapsed_min: float) -> float`  — Crushed nucleus regrowing toward its initial radius (τ = 2 weeks).
- `impermeable_crushing_bar(ambient_bar: float, onset_tension_bar: float, initial_radius_um: float) -> float`  — Crushing pressure in the impermeable regime (gradient > 8.30865 bar).
### class `VpmState` (DecoState) — Frozen VPM-B snapshot.
  `__slots__ = ('compartments', 'runtime_min')`
  - `__init__(self, compartments: tuple[tuple[float, float, float, float, float], ...], runtime_min: float)`
  attrs: `compartments: tuple[tuple[float, float, float, float, float], ...]; runtime_min: float`
  dunders: `__delattr__, __eq__, __hash__, __repr__, __setattr__`
### class `VpmB` (BaseDecoModel[VpmState]) — VPM-B core model (pre-CVA ceilings; see module docstring for scope).
  `__slots__ = ('conservatism', '_compartments', '_max_crush_n2_bar', '_max_crush_he_bar', '_onset_tension_bar', '_runtime_min')`
  - `__init__(self, conservatism: int = 0)`
  - @property `name(self) -> str`  — Registry name plus conservatism level — e.g. ``"vpmb +3"``.
  - @property `crit_radius_n2_um(self) -> float`  — Initial N2 critical radius after conservatism scaling.
  - @property `crit_radius_he_um(self) -> float`  — Initial He critical radius after conservatism scaling.
  - @staticmethod `_total_tension_bar(compartment: Compartment) -> float`
  - `_update_crushing(self, ambient_bar: float, index: int) -> None`  — Track the maximum crushing pressure seen by compartment `index`.
  - `_allowable_gradients_bar(self, index: int) -> tuple[float, float]`  — Current (N2, He) allowable gradients for compartment `index` —
  - `_integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None`
  - `_get_deco_state(self) -> VpmState`
  - `get_ceiling(self) -> Pressure`  — Minimum tolerated ambient pressure across compartments (pre-CVA).
  - `set_state(self, state: VpmState) -> None`  — Restore tissue tensions and bubble bookkeeping from a snapshot.
  - `copy(self) -> Self`  — Independent clone (same conservatism, tensions, crushing history).
  attrs: `NAME = 'vpmb'; COMPARTMENT_COUNT: ClassVar[int] = len(ZHL16C.N2_HALF_TIMES); conservatism: int`
  dunders: `__repr__`

## `src/diveplan/planning/__init__.py`
Ascent planning: deco schedules and gas selection.
`__all__ = ['plan_ascent', 'GasPlan', 'AscentNotConvergingError']`

## `src/diveplan/planning/ascent_plan.py`
Ascent planner: compute the decompression schedule from a model state.
`__all__ = ['plan_ascent', 'AscentNotConvergingError']`
### class `AscentNotConvergingError` (RuntimeError) — The stop loop failed to clear the next target within the iteration cap.
- `_ceiling(model: BaseDecoModel[Any], target: Pressure, first_stop: Pressure | None) -> Pressure`  — Model ceiling for an ascent-to-`target` test.
- `_next_targets(current: Pressure) -> list[Pressure]`  — Candidate ascent targets from shallowest to deepest: the surface, then
- `plan_ascent(model: BaseDecoModel[Any], start_pressure: Pressure | str | float, gas: Gas | str, gas_plan: GasPlan | None = None, clock_offset: timedelta | float = timedelta(0)) -> list[DiveSegment]`  — Plan the decompression ascent from the given position and model state.

## `src/diveplan/planning/gas_plan.py`
Gas plan: carried gases, selection, consumption, and reserve planning.
`__all__ = ['GasPlan', 'gas_consumption', 'rock_bottom', 'cns_percent', 'otu', 'NOAA_CNS_LIMITS']`
### class `GasPlan` — An ordered collection of carried gases with depth-based selection.
  `__slots__ = ('_gases',)`
  - `__init__(self, gases: Iterable[Gas | str])`
  - @property `gases(self) -> tuple[Gas, ...]`  — The carried gases (duplicates removed, insertion order).
  - @staticmethod `is_breathable(gas: Gas, pressure: Pressure) -> bool`  — Whether `gas` is within the configured deco ppO2 window here.
  - `best_gas_at(self, pressure: Pressure) -> Gas | None`  — Richest breathable gas at `pressure`, or None if none qualifies.
  dunders: `__repr__`
- `gas_consumption(segments: Iterable[DiveSegment]) -> dict[Gas, float]`  — Surface litres of each gas consumed over `segments`.
- `rock_bottom(depth: Pressure | str | float, *, divers: int = 2) -> float`  — Minimum gas reserve (surface litres) at `depth` for an emergency.
- `_cns_limit_minutes(ppo2_bar: float) -> float | None`  — NOAA limit at `ppo2_bar`, linearly interpolated; None below the floor.
- `_iter_ppo2(segments: Iterable[DiveSegment], step: timedelta) -> Iterable[tuple[float, float]]`  — Yield (minutes, ppO2 bar) exposures: one per constant segment, midpoint
- `cns_percent(segments: Iterable[DiveSegment], *, step: timedelta = timedelta(seconds=10)) -> float`  — CNS oxygen-toxicity clock over `segments`, in percent (100 = NOAA limit).
- `otu(segments: Iterable[DiveSegment], *, step: timedelta = timedelta(seconds=10)) -> float`  — Pulmonary oxygen-toxicity units (REPEX) accumulated over `segments`.

## `src/diveplan/registry.py`
Entry-point plugin discovery for decompression models and formatters.
### class `PluginNotFoundError` (KeyError) — No plugin is registered under the requested name.
  - `__init__(self, name: str, available: list[str], kind: str = 'decompression model') -> None`
### class `PluginInvalidError` (TypeError) — A discovered or registered plugin does not subclass its plugin base.
- `_discover(group: str, base: type[T]) -> dict[str, type[T]]`  — Load every entry point in `group`, validating against `base`.
### class `PluginRegistry` — Deco-model and formatter lookup: entry-point discovery plus manual
  - `__init__(self) -> None`
  - @cached_property `_discovered(self) -> dict[str, type[BaseDecoModel[Any]]]`  — Discovered once from entry points, then frozen.
  - @cached_property `_discovered_formatters(self) -> dict[str, type[BaseFormatter]]`  — Discovered once from entry points, then frozen.
  - @property `_all(self) -> dict[str, type[BaseDecoModel[Any]]]`  — Overrides shadow discovered plugins of the same name.
  - @property `_all_formatters(self) -> dict[str, type[BaseFormatter]]`  — Overrides shadow discovered plugins of the same name.
  - `model(self, name: str) -> type[BaseDecoModel[Any]]`  — Return the plugin class for *name*, or raise PluginNotFoundError.
  - `all_models(self) -> dict[str, type[BaseDecoModel[Any]]]`  — All registered plugins, keyed by name.
  - `register_model(self, name: str, cls: type[BaseDecoModel[Any]]) -> None`  — Manually register a plugin class — escape hatch for tests,
  - `formatter(self, name: str) -> type[BaseFormatter]`  — Return the formatter class for *name*, or raise PluginNotFoundError.
  - `all_formatters(self) -> dict[str, type[BaseFormatter]]`  — All registered formatters, keyed by name.
  - `register_formatter(self, name: str, cls: type[BaseFormatter]) -> None`  — Manually register a formatter class — escape hatch for tests,
  - `invalidate(self) -> None`  — Force re-discovery of both groups on next access.
- const `registry = PluginRegistry()`

## `src/diveplan/utils/__init__.py`
(empty stub)

## `src/diveplan/utils/conversions.py`
Argument-coercion helpers shared across the user-facing API.
`__all__ = ['coerce_depth_to_pressure', 'coerce_gas', 'duration_from_rate', 'DEPTH_TYPES', 'GAS_TYPES']`
- const `DEPTH_TYPES = float | int | str | Pressure`
- const `GAS_TYPES = str | Gas`
- `coerce_depth_to_pressure(value: DEPTH_TYPES) -> Pressure`  — Convert a user-facing depth argument to an absolute :class:`Pressure`.
- `coerce_gas(value: GAS_TYPES) -> Gas`  — Convert a user-facing gas argument to a :class:`Gas`.
- `duration_from_rate(rate: float, start_pressure: Pressure, end_pressure: Pressure) -> float`  — Traverse duration implied by a rate of pressure change.

# Tests (tests/)
- `conftest.py` (0 tests)
- `test_buhlmann.py` (47 tests) — TestGradient, TestCompartmentState, TestCompartmentIntegration, TestCompartmentToleratedPressure, TestZHL16CTables, TestZHL16CModel, MiniBuhlmann, TestBuhlmannFamily, TestZHL16CRegistry
- `test_config.py` (45 tests) — TestSubConfigBase, TestPhysicsConfig, TestGasConfig, TestDivePlanningConfig, TestDiveConfigStructure, TestGlobalDefault, TestContextManager, TestDefaultConfigLoading, TestSerialization
- `test_dive.py` (28 tests) — TestIterSamples, TestDiveRun, TestDiveQueries, TestDiveContinuation, TestOxygenQueries
- `test_dive_profile.py` (74 tests) — TestDiveProfileBuilder, TestDiveProfileValidation, TestDiveProfileFixes, TestDiveProfileTimeline, TestDiveProfileFluentBuilders, TestDiveProfileSerialization
- `test_dive_segment.py` (59 tests) — TestDiveSegmentConstruction, TestDiveSegmentProperties, TestDiveSegmentInterpolation, TestDiveSegmentSplitting, TestDiveSegmentMerging, TestDiveSegmentContinuity, TestDiveSegmentIteration, TestDiveSegmentMagicMethods, TestDiveSegmentImmutability, TestDiveSegmentSerialization
- `test_gas.py` (61 tests) — TestRawConstruction, TestNamedConstructors, TestFromName, TestPartialPressures, TestMod, TestEnd, TestBestMix, TestEqualityAndHash, TestStringRepresentation
- `test_planning.py` (18 tests) — TestGasPlan, TestPlanAscentNoDeco, TestPlanAscentDeco
- `test_pressure.py` (70 tests) — TestConstruction, TestProperties, TestAltConstructorsAndProperties, TestStringParsing, TestImmutability, TestAddition, TestSubtraction, TestMultiplication, TestDivision, TestOrdering, TestHashing, TestDisplay
- `test_report.py` (39 tests) — TestGasConsumption, TestRockBottom, TestOxygenExposure, TestTtsVariations, TestDiveReport, TestRuntimeFormatter, TestRichConsoleFormatter, TestFormatterRegistry, TestBaseFormatterContract
- `test_vpm.py` (23 tests) — TestBubbleMechanics, TestVpmBModel, TestVpmBRegistry
