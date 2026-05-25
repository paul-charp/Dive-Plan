"""
diveplan.core.config
~~~~~~~~~~~~~~~~~~~~
Dive configuration — physical constants, planning parameters, gas limits.

Validation philosophy: reject physically impossible values (negative pressure,
zero density) but impose no operational upper bounds — diveplan is an
experimentation platform.

Default config loading — priority chain (highest to lowest)
-----------------------------------------------------------
1. DIVEPLAN_CONFIG env var        — path to a JSON config file
2. ./diveplan.config.json         — project-level config in CWD
3. ~/.diveplan/config.json        — user-level config in home directory
4. factory defaults               — built-in defaults

Set DIVEPLAN_NO_FILE_CONFIG=1 to skip steps 1-3 and always use factory defaults.
Useful for CI, testing, or any environment where predictable defaults are required.

Invalid files at any level are skipped with a warning and the next level is tried.

Usage
-----
    # read and mutate the global config
    from diveplan.core.config import DiveConfig

    DiveConfig.current().physics.water_density = 1.0
    DiveConfig.current().physics.surface_pressure_mbar = 800
    DiveConfig.current().physics.gravity = 9.7

    DiveConfig.current().planning.ascent_rate = 9.0
    DiveConfig.current().planning.last_stop_m = 6.0
    DiveConfig.current().planning.sample_rate_s = 2

    DiveConfig.current().gas.max_ppo2_bar = 1.4
    DiveConfig.current().gas.deco_ppo2_bar = 1.6
    DiveConfig.current().gas.min_ppo2_bar = 0.18
    DiveConfig.current().gas.max_ppn2_bar = 3.2
    DiveConfig.current().gas.max_end_m = 30.0
    DiveConfig.current().gas.sac_bottom = 20.0
    DiveConfig.current().gas.sac_deco = 15.0
    DiveConfig.current().gas.gas_switch_minutes = 1.0
    DiveConfig.current().gas.gas_switch_at_stops_only = True

    # permanent global replacement
    custom = DiveConfig()
    custom.gas.max_ppo2_bar = 1.2
    custom.planning.ascent_rate = 8.0
    DiveConfig.set_default(custom)

    # scoped override — stack-based, supports nesting
    altitude = DiveConfig()
    altitude.physics.surface_pressure_mbar = 800
    altitude.physics.water_density = 1.0

    with altitude:
        DiveConfig.current().physics.surface_pressure_mbar  # 800
    DiveConfig.current().physics.surface_pressure_mbar      # restored

    # JSON round-trip
    DiveConfig.current().to_json(path="my_config.json")
    cfg = DiveConfig.from_json(path="my_config.json")
    DiveConfig.set_default(cfg)
"""

import logging
import os
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-config base
# ---------------------------------------------------------------------------


class _SubConfig(BaseModel):
    """Base class for all DiveConfig sub-configs.

    Provides validated assignment and JSON repr for all sub-configs.
    Not intended for direct instantiation.
    """

    model_config = ConfigDict(validate_assignment=True)

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)

    def __repr__(self) -> str:
        return self.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------


class PhysicsConfig(_SubConfig):
    """Physical constants for the dive environment."""

    water_density: float = Field(
        default=1.025,
        gt=0,
        description="kg/L — 1.025 seawater, 1.0 freshwater",
    )
    gravity: float = Field(
        default=9.80665,
        gt=0,
        description="m/s²",
    )
    surface_pressure_mbar: int = Field(
        default=1013,
        gt=0,
        description="mbar — sea level ~1013, lower at altitude",
    )

    @property
    def pressure_per_meter_mbar(self) -> float:
        """Pressure increase per meter of depth in mbar."""
        return self.water_density * self.gravity * 10


class DivePlanningConfig(_SubConfig):
    """Ascent/descent rates and stop parameters."""

    ascent_rate: float = Field(
        default=9.0,
        gt=0,
        description="m/min",
    )
    descent_rate: float = Field(
        default=20.0,
        gt=0,
        description="m/min",
    )
    stop_increment_m: float = Field(
        default=3.0,
        gt=0,
        description="meters between deco stops",
    )
    last_stop_m: float = Field(
        default=3.0,
        gt=0,
        description="depth of last deco stop in meters",
    )
    min_stop_time_s: int = Field(
        default=60,
        gt=0,
        description="minimum time at each stop in seconds",
    )
    sample_rate_s: int = Field(
        default=1,
        gt=0,
        description="integration sample rate in seconds",
    )
    default_model: str = Field(
        default="zhl16c",
        description="registry name of default deco model",
    )


class GasConfig(_SubConfig):
    """Gas planning limits and SAC rates."""

    min_ppo2_bar: float = Field(
        default=0.18,
        gt=0,
        description="bar — hypoxia floor",
    )
    max_ppo2_bar: float = Field(
        default=1.4,
        gt=0,
        description="bar — working/bottom ppO2 limit",
    )
    deco_ppo2_bar: float = Field(
        default=1.6,
        gt=0,
        description="bar — ppO2 limit at deco stops",
    )
    max_ppn2_bar: float = Field(
        default=3.2,
        gt=0,
        description="bar — narcosis/ppN2 ceiling",
    )
    max_end_m: float = Field(
        default=30.0,
        gt=0,
        description="meters — maximum equivalent narcotic depth",
    )
    sac_bottom: float = Field(
        default=20.0,
        gt=0,
        description="L/min — surface air consumption at bottom",
    )
    sac_deco: float = Field(
        default=15.0,
        gt=0,
        description="L/min — surface air consumption at deco stops",
    )
    gas_switch_minutes: float = Field(
        default=1.0,
        ge=0,
        description="minutes added per gas switch — 0 = instant",
    )
    gas_switch_at_stops_only: bool = Field(
        default=True,
        description="if True, gas switches only allowed at deco stops",
    )


# ---------------------------------------------------------------------------
# Default config loading
# ---------------------------------------------------------------------------

_ENV_VAR = "DIVEPLAN_CONFIG_FILE"
_ENV_VAR_DISABLE = "DIVEPLAN_NO_FILE_CONFIG"
_PROJECT_FILE = "diveplan.config.json"
_USER_FILE = Path.home() / ".diveplan" / "config.json"


def _try_load(
    path: Path | str, source: str, config_cls: type[DiveConfig]
) -> "DiveConfig | None":
    """Attempt to load a DiveConfig from a file. Returns None on any failure."""
    try:
        cfg = config_cls.from_json(path=str(path))
        logger.info("diveplan: loaded config from %s (%s)", path, source)
        return cfg
    except FileNotFoundError:
        return None  # missing file is silent — not an error
    except Exception as e:
        logger.warning(
            "diveplan: invalid config at %s (%s) — %s, skipping", path, source, e
        )
        return None


def _load_default_config() -> "DiveConfig":
    """
    Resolve the startup default config following the priority chain:
      1. DIVEPLAN_CONFIG env var
      2. ./diveplan.config.json  (CWD)
      3. ~/.diveplan/config.json (user home)
      4. factory defaults
    Skipped entirely if DIVEPLAN_NO_FILE_CONFIG=1.
    """
    if os.environ.get(_ENV_VAR_DISABLE, "").strip() == "1":
        logger.debug("diveplan: DIVEPLAN_NO_FILE_CONFIG set — using factory defaults")
        return DiveConfig()

    # 1. env var
    env_path = os.environ.get(_ENV_VAR, "").strip()
    if env_path:
        cfg = _try_load(env_path, _ENV_VAR, DiveConfig)
        if cfg is not None:
            return cfg
        logger.warning("diveplan: falling through to next config source")

    # 2. project-level (CWD)
    project_path = Path.cwd() / _PROJECT_FILE
    if project_path.exists():
        cfg = _try_load(project_path, "project", DiveConfig)
        if cfg is not None:
            return cfg

    # 3. user-level (home)
    if _USER_FILE.exists():
        cfg = _try_load(_USER_FILE, "user", DiveConfig)
        if cfg is not None:
            return cfg

    logger.debug("diveplan: no config file found — using factory defaults")
    return DiveConfig()


# ---------------------------------------------------------------------------
# DiveConfig — root config with context manager + global stack
# ---------------------------------------------------------------------------


class DiveConfig(BaseModel):
    """
    Root configuration object.

    DiveConfig itself is frozen — sub-configs are swapped at construction
    time or via scoped overrides. Mutations happen inside sub-configs:

        DiveConfig.current().gas.max_ppo2_bar = 2.0   # ✅ sub-config mutation
        DiveConfig.current().gas = GasConfig(...)      # ❌ frozen, not allowed

    See module docstring for the full default loading priority chain.
    """

    model_config = ConfigDict(frozen=True)

    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    planning: DivePlanningConfig = Field(default_factory=DivePlanningConfig)
    gas: GasConfig = Field(default_factory=GasConfig)

    # class-level state — shared across all instances
    _default: ClassVar[DiveConfig | None] = None
    _stack: ClassVar[list[DiveConfig]] = []

    # -------------------------------------------------------------------
    # Global access
    # -------------------------------------------------------------------

    @classmethod
    def current(cls) -> DiveConfig:
        """Return the active config — top of stack, or startup default."""
        if cls._stack:
            return cls._stack[-1]
        if cls._default is None:
            cls._default = _load_default_config()
        return cls._default

    @classmethod
    def set_default(cls, config: DiveConfig) -> None:
        """Permanently replace the global default config."""
        logger.debug("diveplan: default config replaced programmatically")
        cls._default = config

    @classmethod
    def reset_default(cls) -> None:
        """Restore factory defaults and clear the stack — useful in tests."""
        cls._default = None
        cls._stack.clear()

    # -------------------------------------------------------------------
    # Context manager — stack-based, supports nesting
    # -------------------------------------------------------------------

    def __enter__(self) -> DiveConfig:
        DiveConfig._stack.append(self)
        logger.debug(
            "diveplan: config context entered (stack depth %d)", len(DiveConfig._stack)
        )
        return self

    def __exit__(self, *_: object) -> None:
        DiveConfig._stack.pop()
        logger.debug(
            "diveplan: config context exited (stack depth %d)", len(DiveConfig._stack)
        )

    # -------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        """Serialize to JSON string, optionally writing to file."""
        data = self.model_dump_json(indent=indent)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            logger.debug("diveplan: config written to %s", path)
        return data

    @classmethod
    def from_json(cls, data: str | None = None, path: str | None = None) -> DiveConfig:
        """Deserialize from JSON string or file path."""
        if path:
            with open(path, encoding="utf-8") as f:
                data = f.read()
        if data is None:
            raise ValueError("Provide either 'data' or 'path'")
        return cls.model_validate_json(data)

    def __str__(self) -> str:
        return self.to_json()

    def __repr__(self) -> str:
        return self.to_json()
