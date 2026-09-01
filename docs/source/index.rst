Dive-Plan
=========

``diveplan`` is a pure-Python library for dive planning and decompression
calculation. It is the calculation core only — no UI, no CLI — designed for
both single-dive planning and large-scale batch simulation comparing
algorithms, gases, and conditions.

.. warning::

   **Do not use for real-world dive planning.** This is experimental
   software. Do not dive without certification or outside your
   certification limits.

Quickstart
----------

Build the bottom phase, run a model, complete the dive with its deco
schedule, and report:

.. code-block:: python

    from diveplan import Dive, DiveProfile, DiveReport, GasPlan
    from diveplan.registry import registry

    # Models and formatters are plugins — look them up by name:
    ZHL16C = registry.model("zhl16c")
    ConsoleFormatter = registry.formatter("console")

    bottom = DiveProfile().descend_to("40 m").stay(25)   # air by default
    carried = GasPlan(["air", "ean50"])

    dive = Dive.run(bottom, ZHL16C(gradient="30/70"))
    dive.ceiling_at(20).depth_m        # deco ceiling 20 min into the dive
    dive.tts(20, gas_plan=carried)     # time-to-surface if ascending now
    dive.max_tts(carried)              # peak TTS: the deco obligation carried
    dive.cns_at(20)                    # CNS % accumulated so far

    full = dive.with_ascent(carried)   # new Dive, completed with its deco stops
    report = DiveReport.from_dive(full, tts_variations=dive.tts_variations(carried))
    report.max_tts, report.deco_consumption_l   # obligation and deco-phase litres
    print(ConsoleFormatter().format(report))

Key ideas
---------

- **Pressure is ground truth** — integer millibar, never float depth;
  depth conversions read the active :class:`~diveplan.core.config.DiveConfig`.
- **Profiles are pure geometry** — model results (tissue states, ceilings,
  TTS) live on :class:`~diveplan.dive.dive.Dive`, so one profile can run
  under many models and be compared.
- **Checkpointing** — a Dive stores model state at segment boundaries only
  (O(segments) memory for batch runs); any time query re-integrates at most
  one partial segment, exactly.
- **Friendly notation** — depths as ``"40 m"`` strings, gases by name
  (``"ean50"``, ``"tx21/35"``), gradient factors as ``"30/70"``.

Runnable, commented examples live in the repository's ``examples/``
directory, starting with ``examples/complete_dive_plan.py``.

Public API
----------

Everything stable imports from the package root; submodule paths are
implementation detail unless documented otherwise:

.. code-block:: python

    from diveplan import (
        Pressure, Gas, DiveSegment, SegmentKind,     # core value types
        DiveConfig, diveconfig,                      # configuration (+ live proxy)
        DiveProfile, ProfileBuilderPolicy,           # profile building
        ProfileValidationError,                      #   … and its error family base
        Dive, TtsVariations,                         # running a model over a profile
        GasPlan,                                     # carried gases & selection
        AscentNotConvergingError,                    #   … planner failure mode
        DiveReport, ReportRow,                       # pure-data report
        BaseDecoModel, DecoState, BaseFormatter,     # plugin authoring contracts
    )

Deco ascents are planned from a :class:`~diveplan.dive.dive.Dive` —
``dive.plan_ascent(gas_plan)`` returns the schedule as segments,
``dive.with_ascent(gas_plan)`` a completed dive. The underlying pure
function, :func:`~diveplan.planning.ascent_plan.plan_ascent`, lives in
``diveplan.planning`` for the advanced case of planning from a bare
model state.

Built-in deco models and report formatters are plugins — get them by name
through :data:`diveplan.registry.registry`, the one documented submodule
import (see the quickstart above). Direct class imports are reserved for
API beyond the plugin contract: family-specific machinery from
``diveplan.models.buhlmann`` / ``diveplan.models.vpm`` (e.g.
:class:`~diveplan.models.buhlmann.Gradient`), formatter extras from
``diveplan.dive.formatters``, and the concrete validation-error
subclasses from ``diveplan.dive.dive_profile``.

.. toctree::
   :maxdepth: 1
   :caption: Core types

   api/pressure
   api/gas
   api/dive_segment
   api/config

.. toctree::
   :maxdepth: 1
   :caption: Profile and dive

   api/dive_profile
   api/dive

.. toctree::
   :maxdepth: 1
   :caption: Models and planning

   api/models
   api/planning

.. toctree::
   :maxdepth: 1
   :caption: Output and extension

   api/report
   api/registry
