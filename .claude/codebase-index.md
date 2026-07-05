# diveplan codebase index

Auto-generated API map (regenerate: `uv run python .claude/generate-index.py`). Generated 2026-07-05.

Read this instead of source files when you only need signatures/structure. Read the actual source before *editing* anything listed here.

## `src/diveplan/__init__.py`
diveplan — dive planning and decompression calculation library.
### class `_ConfigProxy` — Transparent proxy to DiveConfig.current().
  `__slots__ = ()`
  - @property `gas(self) -> _GasConfig`
  - @property `physics(self) -> _PhysicsConfig`
  - @property `planning(self) -> _DivePlanningConfig`
  dunders: `__repr__, __str__`
- const `diveconfig = _ConfigProxy()`
`__all__ = ['Pressure', 'Gas', 'DiveSegment', 'SegmentKind', 'DiveConfig', 'diveconfig']`

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
  attrs: `min_ppo2_bar: float = Field(default=0.18, gt=0, description='bar — hypoxia floor'); max_ppo2_bar: float = Field(default=1.4, gt=0, description='bar — working/bottom ppO2 limit'); deco_ppo2_bar: float = Field(default=1.6, gt=0, description='bar — ppO2 limit at deco stops'); max_ppn2_bar: float = Field(default=3.2, gt=0, description='bar — narcosis/ppN2 ceiling'); max_end_m: float = Field(default=30.0, gt=0, description='meters — maximum equivalent narcotic depth'); sac_bottom: float = Field(default=20.0, gt=0, description='L/min — surface air consumption at bottom'); sac_deco: float = Field(default=15.0, gt=0, description='L/min — surface air consumption at deco stops'); gas_switch_minutes: float = Field(default=1.0, ge=0, description='minutes added per gas switch — 0 = instant'); gas_switch_at_stops_only: bool = Field(default=True, description='if True, gas switches only allowed at deco stops')`
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
`__all__ = ['SegmentKind', 'DiveSegment']`
### class `SegmentKind` — Kind of dive segment, used for categorization and special handling in algorithms.
  - class `Descent` (Enum)
    attrs: `DESCENT = auto()`
  - class `Ascent` (Enum)
    attrs: `FORCED_ASCENT = auto(); DECO_ASCENT = auto()`
  - class `Constant` (Enum)
    attrs: `BOTTOM = auto(); STOP = auto(); GAS_SWITCH = auto()`
  - @staticmethod `from_name(name: str) -> SegmentKind.Members`  — Look up a segment kind by member name, e.g. ``"DESCENT"``, ``"STOP"``.
  attrs: `DESCENT = Descent.DESCENT; ASCENT = Ascent.FORCED_ASCENT; CONSTANT = Constant.BOTTOM; Members = Descent | Ascent | Constant`
### class `DiveSegment` — A segment of a dive profile with a start and end pressure, duration, and gas.
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
  - @property `is_surface(self) -> bool`
  - `to_str(self, unit: PressureUnit = 'bar') -> str`  — Format pressure as a string in the specified unit.
  attrs: `_PSI_PER_MBAR = 0.0145038`
  dunders: `__add__, __delattr__, __eq__, __ge__, __gt__, __hash__, __le__, __lt__, __mul__, __repr__, __rmul__, __setattr__, __str__, __sub__, __truediv__, __truediv__, __truediv__`

## `src/diveplan/dive/__init__.py`
(empty stub)

## `src/diveplan/dive/dive_profile.py`
`__all__ = ('DiveProfile', 'ProfileValidationError', 'ProfileContinuityError', 'ProfileSimplicityError', 'ProfileStartEndError', 'ProfileDepthContinuityError', 'ProfileGasContinuityError', 'ProfileEmptyError', 'ProfileTooShortError', 'ProfileBuilderPolicy')`
### class `ProfileValidationError` (ValueError) — Base descriptor for a dive profile validation problem.
  - `__init__(self, message: str, *, segment_index: Optional[int] = None, segments: tuple[DiveSegment, ...] = ())`
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
### class `DiveProfile` — A dive profile consisting of a sequence of dive segments.
  `__slots__ = ('_segments', '_builder_policy')`
  - `__init__(self, builder_policy: ProfileBuilderPolicy = ProfileBuilderPolicy.RAISE_BAD_PROFILE)`  — Initialize a new DiveProfile.
  - @property `builder_policy(self) -> ProfileBuilderPolicy`  — The active profile builder policy.
  - `copy(self, *, override_policy: Optional[ProfileBuilderPolicy] = None) -> DiveProfile`  — Create a copy of the dive profile.
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
  - @staticmethod `_is_gas_switch_seam(a: DiveSegment, b: DiveSegment) -> bool`  — A seam is a legitimate gas switch if either side is a GAS_SWITCH segment.
  - `_seam_error(self, a: DiveSegment, b: DiveSegment, index: int) -> Optional[ProfileValidationError]`  — Return the most fundamental continuity error at the seam (a → b), or None.
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
  - `descend_to(self, depth: Pressure | str | float, *, rate: Optional[float] = None, gas: Gas | str | None = None) -> DiveProfile`  — Append a descent from the current position to `depth`.
  - `ascend_to(self, depth: Pressure | str | float, *, rate: Optional[float] = None, gas: Gas | str | None = None, kind: SegmentKind.Ascent = SegmentKind.ASCENT) -> DiveProfile`  — Append an ascent from the current position to `depth`.
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
  - `to_json(self, path: Optional[str] = None, indent: int = 2) -> str`  — Serialize to a JSON string, optionally writing to a file.
  - @classmethod `from_json(cls, data: Optional[str] = None, path: Optional[str] = None) -> DiveProfile`  — Deserialize from a JSON string or file path (see :meth:`from_dict`).

## `src/diveplan/dive/dive_report.py`
(empty stub)

## `src/diveplan/dive/formatters/__init__.py`
(empty stub)

## `src/diveplan/models/__init__.py`
(empty stub)

## `src/diveplan/models/base.py`
Decompression model base classes.
`__all__ = ['BaseDecoModel', 'DecoState']`
### class `DecoState` — Base class for model-specific decompression state snapshots.
  `__slots__ = ()`
### class `BaseDecoModel[StateT: DecoState]` (ABC) — Base class for all decompression models.
  `__slots__ = ('sample_rate_seconds',)`
  - @abstract `__init__(self) -> None`  — Initialize the decompression model.
  - `integrate_segment(self, segment: DiveSegment) -> StateT`  — Integrate a dive segment into the model and return the state after it.
  - @abstract `_integrate_model(self, pressure: Pressure, gas: Gas, dt: timedelta) -> None`  — Advance the model by dt at the given ambient pressure and gas.
  - @abstract `_get_deco_state(self) -> StateT`  — Snapshot the current model state.
  - @abstract `get_ceiling(self) -> Pressure`  — Return the current ceiling depth.
  attrs: `NAME: ClassVar[str]`

## `src/diveplan/models/buhlmann/__init__.py`
(empty stub)

## `src/diveplan/models/buhlmann/common.py`
`__all__ = ('Gradient', 'Compartment')`
### class `Gradient` — Helper for computing gradients of dive segments.
  `__slots__ = ('gf_low', 'gf_high')`
  - `__init__(self, gf_low: float, gf_high: float)`
  - `factor(self, depth_pressure: Pressure, max_depth_pressure: Pressure) -> float`  — Linearly interpolate the gradient for a given depth.
  attrs: `gf_low: float; gf_high: float`
  dunders: `__eq__, __hash__, __repr__, __str__`
### class `Compartment` — Helper for tracking compartment constants and saturation.
  `__slots__ = ('ppn2', 'pphe', 'ht_n2', 'ht_he', 'a_n2', 'a_he', 'b_n2', 'b_he', 'tolerated_pressure')`
  - `__init__(self, *, ht_n2: float, ht_he: float, a_n2: float, a_he: float, b_n2: float, b_he: float, ppn2: Optional[Pressure] = None, pphe: Optional[Pressure] = None)`
  - `update_compartment(self, pressure: Pressure, gas: Gas, duration: timedelta, gradient_factor: float)`
  - `_integrate_compartment(self, pressure: Pressure, gas: Gas, duration: timedelta)`
  - `_update_compartment_max_tolerated_pressure(self, ambiant_pressure: Pressure, gradient_factor: float)`
  - @staticmethod `_calc_inert_gas_pressure(ambiant_pressure: Pressure, inspired_gas_pressure: Pressure, time_minutes: float, half_time_minutes: float) -> Pressure`
  - @staticmethod `_calcInertGasLimit(ppn2: Pressure, pphe: Pressure, a_n2: float, b_n2: float, a_he: float, b_he: float, ambiant_pressure: Pressure, gradient_factor: float) -> Pressure`
  - `is_eq_pressures_only(self, other: Compartment) -> bool`
  - `is_eq_with_pressures(self, other: Compartment) -> bool`
  attrs: `ppn2: Pressure; pphe: Pressure; ht_n2: float; ht_he: float; a_n2: float; a_he: float; b_n2: float; b_he: float`
  dunders: `__eq__, __hash__, __repr__, __str__`

## `src/diveplan/planning/__init__.py`
(empty stub)

## `src/diveplan/planning/ascent_plan.py`
(empty stub)

## `src/diveplan/planning/gas_plan.py`
(empty stub)

## `src/diveplan/registry.py`
### class `PluginNotFoundError` (KeyError)
  - `__init__(self, name: str, available: list[str]) -> None`
### class `PluginInvalidError` (TypeError)
### class `PluginRegistry`
  - `__init__(self) -> None`
  - @cached_property `_discovered(self) -> dict[str, type[BaseDecoModel[Any]]]`  — Discovered once from entry points, then frozen.
  - @property `_all(self) -> dict[str, type[BaseDecoModel[Any]]]`  — Overrides shadow discovered plugins of the same name.
  - `model(self, name: str) -> type[BaseDecoModel[Any]]`  — Return the plugin class for *name*, or raise PluginNotFoundError.
  - `all_models(self) -> dict[str, type[BaseDecoModel[Any]]]`  — All registered plugins, keyed by name.
  - `register_model(self, name: str, cls: type[BaseDecoModel[Any]]) -> None`  — Manually register a plugin class — escape hatch for tests,
  - `invalidate(self) -> None`  — Force re-discovery on next access.
- const `registry = PluginRegistry()`

## `src/diveplan/utils/__init__.py`
(empty stub)

## `src/diveplan/utils/conversions.py`
`__all__ = ['coerce_depth_to_pressure', 'coerce_gas', 'duration_from_rate', 'DEPTH_TYPES', 'GAS_TYPES']`
- const `DEPTH_TYPES = float | int | str | Pressure`
- const `GAS_TYPES = str | Gas`
- `coerce_depth_to_pressure(value: DEPTH_TYPES) -> Pressure`
- `coerce_gas(value: GAS_TYPES) -> Gas`
- `duration_from_rate(rate: float, start_pressure: Pressure, end_pressure: Pressure) -> float`

# Tests (tests/)
- `conftest.py` (0 tests)
- `test_config.py` (45 tests) — TestSubConfigBase, TestPhysicsConfig, TestGasConfig, TestDivePlanningConfig, TestDiveConfigStructure, TestGlobalDefault, TestContextManager, TestDefaultConfigLoading, TestSerialization
- `test_dive_profile.py` (74 tests) — TestDiveProfileBuilder, TestDiveProfileValidation, TestDiveProfileFixes, TestDiveProfileTimeline, TestDiveProfileFluentBuilders, TestDiveProfileSerialization
- `test_dive_segment.py` (59 tests) — TestDiveSegmentConstruction, TestDiveSegmentProperties, TestDiveSegmentInterpolation, TestDiveSegmentSplitting, TestDiveSegmentMerging, TestDiveSegmentContinuity, TestDiveSegmentIteration, TestDiveSegmentMagicMethods, TestDiveSegmentImmutability, TestDiveSegmentSerialization
- `test_gas.py` (61 tests) — TestRawConstruction, TestNamedConstructors, TestFromName, TestPartialPressures, TestMod, TestEnd, TestBestMix, TestEqualityAndHash, TestStringRepresentation
- `test_pressure.py` (70 tests) — TestConstruction, TestProperties, TestAltConstructorsAndProperties, TestStringParsing, TestImmutability, TestAddition, TestSubtraction, TestMultiplication, TestDivision, TestOrdering, TestHashing, TestDisplay
