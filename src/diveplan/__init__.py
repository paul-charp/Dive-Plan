"""
diveplan — dive planning and decompression calculation library.

Everything listed in ``__all__`` below is the stable public API; import it
from the package root. Submodule paths are implementation detail unless
documented otherwise.

**Core value types**

* ``Pressure`` — integer-millibar pressure value type
* ``Gas`` — O2/He/N2 breathing mixture
* ``DiveSegment`` / ``SegmentKind`` — a single leg of a dive profile

**Configuration**

* ``DiveConfig`` — physics, planning, and gas configuration
* ``diveconfig`` — proxy forwarding attribute access to ``DiveConfig.current()``

**Profile building**

* ``DiveProfile`` — fluent builder, validation & repair, timeline queries
* ``ProfileBuilderPolicy`` — raise / allow / autofix during construction
* ``ProfileValidationError`` — base of the validation-error family
  (concrete subclasses importable from ``diveplan.dive.dive_profile``)

**Running dives**

* ``Dive`` — a deco model's run over a profile; ceilings, TTS, oxygen clocks
* ``TtsVariations`` — the "+1 m / +1 min" TTS sensitivity pair

**Ascent and gas planning**

* ``GasPlan`` — carried gases with depth-based selection
* ``AscentNotConvergingError`` — raised when a deco stop cannot clear

Ascents are planned from a ``Dive``: ``dive.plan_ascent(gas_plan)`` returns
the deco schedule as segments, ``dive.with_ascent(gas_plan)`` a completed
dive. The underlying pure function lives in ``diveplan.planning`` for the
advanced case of planning from a bare model state.

**Reports**

* ``DiveReport`` — pure-data summary of a computed dive
* ``ReportRow`` — one schedule line of a report

**Plugin authoring**

* ``BaseDecoModel`` / ``DecoState`` — deco-model plugin contract
  (entry-point group ``diveplan.deco_models``)
* ``BaseFormatter`` — report-formatter plugin contract
  (entry-point group ``diveplan.formatters``)

**Plugin lookup** — the one documented submodule import::

    from diveplan.registry import registry

    ZHL16C = registry.model("zhl16c")
    ConsoleFormatter = registry.formatter("console")

Built-in model and formatter classes are looked up through the registry;
import them directly only for API beyond the plugin contract (e.g.
``diveplan.models.buhlmann.Gradient``, rich's ``console=`` parameter).
"""

import logging

# -- core value types --------------------------------------------------------
from diveplan.core.config import (
    DiveConfig,
    _DivePlanningConfig,
    _GasConfig,
    _PhysicsConfig,
)
from diveplan.core.dive_segment import DiveSegment, SegmentKind
from diveplan.core.gas import Gas
from diveplan.core.pressure import Pressure

# -- dive / planning / report layers -----------------------------------------
from diveplan.dive.dive import Dive, TtsVariations
from diveplan.dive.dive_profile import (
    DiveProfile,
    ProfileBuilderPolicy,
    ProfileValidationError,
)
from diveplan.dive.dive_report import DiveReport, ReportRow
from diveplan.dive.formatters import BaseFormatter

# -- plugin bases -------------------------------------------------------------
from diveplan.models.base import BaseDecoModel, DecoState
from diveplan.planning.ascent_plan import AscentNotConvergingError
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
    # profile building
    "DiveProfile",
    "ProfileBuilderPolicy",
    "ProfileValidationError",
    # running dives
    "Dive",
    "TtsVariations",
    # ascent and gas planning
    "GasPlan",
    "AscentNotConvergingError",
    # reports
    "DiveReport",
    "ReportRow",
    # plugin authoring
    "BaseDecoModel",
    "DecoState",
    "BaseFormatter",
]

__version__ = "0.1.0"
