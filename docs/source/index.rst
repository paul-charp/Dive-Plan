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
    from diveplan.dive.formatters import ConsoleFormatter
    from diveplan.models.buhlmann.zhl16 import ZHL16C

    bottom = DiveProfile().descend_to("40 m").stay(25)   # air by default
    carried = GasPlan(["air", "ean50"])

    dive = Dive.run(bottom, ZHL16C(gradient="30/70"))
    dive.ceiling_at(20).depth_m        # deco ceiling 20 min into the dive
    dive.tts(20, gas_plan=carried)     # time-to-surface if ascending now

    full = dive.with_ascent(carried)   # new Dive, completed with its deco stops
    report = DiveReport.from_dive(full, tts_variations=dive.tts_variations(carried))
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
