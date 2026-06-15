"""Core value objects and configuration for diveplan.

This subpackage holds the foundational, dependency-free building blocks:

- ``Pressure`` — integer-millibar pressure value type and unit conversions.
- ``Gas`` — immutable O2/He/N2 breathing mixture.
- ``DiveSegment`` / ``SegmentKind`` — a single leg of a dive profile.
- ``DiveConfig`` — physics, planning, and gas configuration with scoped overrides.

Import these from the package root (``from diveplan import Pressure``) rather
than from here; the submodule paths are not part of the stable public API.
"""
