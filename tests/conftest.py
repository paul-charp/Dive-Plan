"""
Shared pytest fixtures for the diveplan test suite.

The whole suite runs against factory-default config. `DiveConfig` keeps
process-global state (the default config plus a context stack), so without
isolation a mutation in one test — e.g. ``DiveConfig.current().gas.max_ppo2_bar
= 2.0`` — would leak into every test that runs after it. Pinning a fresh
factory default around every test also makes the suite immune to any real
``diveplan.config.json`` / ``~/.diveplan/config.json`` present on the dev
machine.

``tests/test_config.py`` manages ``DiveConfig`` default/env state itself in a
local autouse fixture, so it is unaffected by this one.
"""

import pytest

from diveplan.core.config import DiveConfig


@pytest.fixture(autouse=True)
def factory_default_config():
    """Pin a fresh factory-default DiveConfig around every test."""
    DiveConfig.reset_default()
    DiveConfig.set_default(DiveConfig())
    yield
    DiveConfig.reset_default()
