Dive-Plan
=========

``diveplan`` is a pure-Python library for dive planning and decompression
calculation. It is the calculation core only — no UI, no CLI — designed for both
single-dive planning and large-scale batch simulation.

This documentation currently covers the **core** layer: the foundational value
objects (:class:`~diveplan.core.pressure.Pressure`,
:class:`~diveplan.core.gas.Gas`,
:class:`~diveplan.core.dive_segment.DiveSegment`) and the configuration system
(:class:`~diveplan.core.config.DiveConfig`). The planning, deco-model, and
report layers are documented as they land.

Quickstart
----------

.. code-block:: python

    from diveplan import Pressure, Gas, DiveConfig

    # Pressure is integer-millibar ground truth; depth conversion reads config.
    p = Pressure.from_depth_m(30)
    p.bar        # ~4.0
    p.depth_m    # 30.0

    # Gas mixes and their limits.
    ean32 = Gas.nitrox(0.32)
    ean32.mod(ppo2_bar=1.4).depth_m   # max operating depth

    # Scoped config override — e.g. a fresh-water dive.
    fresh = DiveConfig()
    fresh.physics.water_density = 1.0
    with fresh:
        Pressure.from_depth_m(30).bar   # uses fresh-water density

.. toctree::
   :maxdepth: 1
   :caption: Core types

   api/pressure
   api/gas
   api/dive_segment
   api/config

.. toctree::
   :maxdepth: 1
   :caption: Dive profile

   api/dive_profile
