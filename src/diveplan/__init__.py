"""
diveplan — dive planning and decompression calculation library.

Public API
----------
Core types:
    Pressure, DiveStep, StepKind, AscentMode
    GasMix, DiveConfig
    Dive, DiveReport, GasPlan

Config proxy:
    diveconfig      — forwards attribute access to DiveConfig.current()

Extension points (import directly from submodules):
    diveplan.models          — AbstractDecoModel, ZHL16C
    diveplan.models.helpers  — Compartment, Gradient
    diveplan.dive.formatters — ReportFormatter
    diveplan.registry        — PluginRegistry
"""

import logging

# -- core types ----------------------------------------------------------------
from diveplan.core.config import DiveConfig, _DivePlanningConfig, _GasConfig, _PhysicsConfig
from diveplan.core.pressure import Pressure

# populated as subsequent modules are implemented:
# from diveplan.core.gas_mix import GasMix
# from diveplan.core.dive_step import DiveStep, StepKind, AscentMode
# from diveplan.planning.gas_plan import GasPlan
# from diveplan.dive.dive import Dive
# from diveplan.dive.report import DiveReport

# -- config proxy --------------------------------------------------------------


class _ConfigProxy:
    """Transparent proxy to DiveConfig.current().

    Forwards all attribute access to the current config — stack-aware,
    picks up context manager overrides automatically.

        from diveplan import diveconfig
        diveconfig.gas.max_ppo2_bar          # read
        diveconfig.gas.max_ppo2_bar = 1.6   # mutate (validate_assignment enforced)
        diveconfig.planning.ascent_rate      # read

    For core/ modules use DiveConfig.current() directly to avoid circular imports.
    """

    __slots__ = ()

    @property
    def gas(self) -> _GasConfig:
        return DiveConfig.current().gas

    @property
    def physics(self) -> _PhysicsConfig:
        return DiveConfig.current().physics

    @property
    def planning(self) -> _DivePlanningConfig:
        return DiveConfig.current().planning

    def __repr__(self) -> str:
        return f"<diveconfig → {DiveConfig.current()!r}>"

    def __str__(self) -> str:
        return str(DiveConfig.current())


diveconfig = _ConfigProxy()

# -- logging -------------------------------------------------------------------
logging.getLogger("diveplan").addHandler(logging.NullHandler())

# -- public surface ------------------------------------------------------------
__all__ = [
    # config
    "DiveConfig",
    "diveconfig",
    # core types
    "Pressure",
    # populated as implemented:
    # "GasMix",
    # "DiveStep",
    # "StepKind",
    # "AscentMode",
    # "GasPlan",
    # "Dive",
    # "DiveReport",
]
