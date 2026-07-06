"""
diveplan — dive planning and decompression calculation library.

**Core types**

* ``Pressure`` — integer-millibar pressure value type
* ``Gas`` — O2/He/N2 breathing mixture
* ``DiveSegment`` / ``SegmentKind`` — a single leg of a dive profile
* ``DiveConfig`` — physics, planning, and gas configuration

**Config proxy**

* ``diveconfig`` — forwards attribute access to ``DiveConfig.current()``

**Extension points** (import directly from submodules)

* ``diveplan.registry`` — ``PluginRegistry``

The planning, deco-model, and dive/report layers are still under construction;
their public symbols will be re-exported here as they land.
"""

import logging

# -- core types ----------------------------------------------------------------
from diveplan.core.config import (
    DiveConfig,
    _DivePlanningConfig,
    _GasConfig,
    _PhysicsConfig,
)
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

# -- dive / planning layers ------------------------------------------------
from diveplan.dive.dive import Dive
from diveplan.dive.dive_profile import DiveProfile
from diveplan.dive.dive_report import DiveReport
from diveplan.planning.ascent_plan import plan_ascent
from diveplan.planning.gas_plan import GasPlan

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
        """Gas limits and SAC rates of the active config."""
        return DiveConfig.current().gas

    @property
    def physics(self) -> _PhysicsConfig:
        """Physical environment of the active config."""
        return DiveConfig.current().physics

    @property
    def planning(self) -> _DivePlanningConfig:
        """Rates and stop parameters of the active config."""
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
    # core value types
    "Pressure",
    "Gas",
    "DiveSegment",
    "SegmentKind",
    # configuration
    "DiveConfig",
    "diveconfig",
    # dive / planning layers
    "Dive",
    "DiveProfile",
    "DiveReport",
    "GasPlan",
    "plan_ascent",
]

__version__ = "0.1.0"
