"""
tests/core/test_config.py
"""

import json
import logging
import os
from pathlib import Path

import pytest

from diveplan.core.config import (
    _ENV_VAR,
    _ENV_VAR_DISABLE,
    _PROJECT_FILE,
    _USER_FILE,  # NOQA
    DiveConfig,
)
from diveplan.core.config import (
    _DivePlanningConfig as DivePlanningConfig,
)
from diveplan.core.config import (
    _GasConfig as GasConfig,
)
from diveplan.core.config import (
    _PhysicsConfig as PhysicsConfig,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_config():
    """Clean global state and env vars before and after every test."""
    DiveConfig.reset_default()
    env_backup = {
        _ENV_VAR: os.environ.pop(_ENV_VAR, None),
        _ENV_VAR_DISABLE: os.environ.pop(_ENV_VAR_DISABLE, None),
    }
    yield
    DiveConfig.reset_default()
    for key, val in env_backup.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


# ---------------------------------------------------------------------------
# _SubConfig base behaviour
# ---------------------------------------------------------------------------


class TestSubConfigBase:
    def test_str_is_json(self):
        cfg = PhysicsConfig()
        parsed = json.loads(str(cfg))
        assert parsed["water_density"] == 1.025

    def test_repr_is_json(self):
        cfg = GasConfig()
        parsed = json.loads(repr(cfg))
        assert parsed["max_ppo2_bar"] == 1.4

    def test_validate_assignment_rejects_invalid(self):
        cfg = PhysicsConfig()
        with pytest.raises(Exception):
            cfg.water_density = -1.0

    def test_validate_assignment_accepts_valid(self):
        cfg = PhysicsConfig()
        cfg.water_density = 1.0
        assert cfg.water_density == 1.0


# ---------------------------------------------------------------------------
# PhysicsConfig
# ---------------------------------------------------------------------------


class TestPhysicsConfig:
    def test_defaults(self):
        cfg = PhysicsConfig()
        assert cfg.water_density == 1.025
        assert cfg.gravity == 9.80665
        assert cfg.surface_pressure_mbar == 1013

    def test_pressure_per_meter_seawater(self):
        cfg = PhysicsConfig()
        assert abs(cfg.pressure_per_meter_mbar - 100.518) < 0.001

    def test_pressure_per_meter_freshwater(self):
        cfg = PhysicsConfig(water_density=1.0)
        assert abs(cfg.pressure_per_meter_mbar - 98.0665) < 0.001

    def test_rejects_zero_gravity(self):
        with pytest.raises(Exception):
            PhysicsConfig(gravity=0)

    def test_rejects_zero_surface_pressure(self):
        with pytest.raises(Exception):
            PhysicsConfig(surface_pressure_mbar=0)

    def test_allows_altitude_pressure(self):
        cfg = PhysicsConfig(surface_pressure_mbar=700)
        assert cfg.surface_pressure_mbar == 700


# ---------------------------------------------------------------------------
# GasConfig
# ---------------------------------------------------------------------------


class TestGasConfig:
    def test_defaults(self):
        cfg = GasConfig()
        assert cfg.max_ppo2_bar == 1.4
        assert cfg.deco_ppo2_bar == 1.6
        assert cfg.min_ppo2_bar == 0.18

    def test_allows_experimental_ppo2(self):
        cfg = GasConfig(max_ppo2_bar=5.0)
        assert cfg.max_ppo2_bar == 5.0

    def test_allows_tiny_min_ppo2(self):
        cfg = GasConfig(min_ppo2_bar=0.001)
        assert cfg.min_ppo2_bar == 0.001

    def test_rejects_zero_ppo2(self):
        with pytest.raises(Exception):
            GasConfig(max_ppo2_bar=0)

    def test_allows_zero_switch_time(self):
        cfg = GasConfig(gas_switch_minutes=0)
        assert cfg.gas_switch_minutes == 0


# ---------------------------------------------------------------------------
# DivePlanningConfig
# ---------------------------------------------------------------------------


class TestDivePlanningConfig:
    def test_defaults(self):
        cfg = DivePlanningConfig()
        assert cfg.ascent_rate == 9.0
        assert cfg.descent_rate == 20.0
        assert cfg.sample_rate_s == 1

    def test_rejects_zero_ascent_rate(self):
        with pytest.raises(Exception):
            DivePlanningConfig(ascent_rate=0)

    def test_allows_fast_ascent_rate(self):
        cfg = DivePlanningConfig(ascent_rate=100.0)
        assert cfg.ascent_rate == 100.0


# ---------------------------------------------------------------------------
# DiveConfig structure
# ---------------------------------------------------------------------------


class TestDiveConfigStructure:
    def test_sub_config_types(self):
        cfg = DiveConfig()
        assert isinstance(cfg.physics, PhysicsConfig)
        assert isinstance(cfg.planning, DivePlanningConfig)
        assert isinstance(cfg.gas, GasConfig)

    def test_frozen_rejects_sub_config_replacement(self):
        cfg = DiveConfig()
        with pytest.raises(Exception):
            cfg.gas = GasConfig(max_ppo2_bar=1.2)

    def test_sub_config_mutation_allowed(self):
        DiveConfig.current().gas.max_ppo2_bar = 2.0
        assert DiveConfig.current().gas.max_ppo2_bar == 2.0

    def test_partial_override_leaves_others_intact(self):
        cfg = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        assert cfg.physics.water_density == 1.0
        assert cfg.gas.max_ppo2_bar == 1.4

    def test_str_is_json(self):
        cfg = DiveConfig()
        parsed = json.loads(str(cfg))
        assert "physics" in parsed
        assert "planning" in parsed
        assert "gas" in parsed


# ---------------------------------------------------------------------------
# Global default
# ---------------------------------------------------------------------------


class TestGlobalDefault:
    def test_current_returns_default(self):
        assert DiveConfig.current().physics.water_density == 1.025

    def test_set_default(self):
        DiveConfig.set_default(DiveConfig(physics=PhysicsConfig(water_density=1.0)))
        assert DiveConfig.current().physics.water_density == 1.0

    def test_reset_restores_factory(self):
        DiveConfig.set_default(DiveConfig(physics=PhysicsConfig(water_density=1.0)))
        DiveConfig.reset_default()
        assert DiveConfig.current().physics.water_density == 1.025


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_scoped_override(self):
        with DiveConfig(physics=PhysicsConfig(water_density=1.0)):
            assert DiveConfig.current().physics.water_density == 1.0
        assert DiveConfig.current().physics.water_density == 1.025

    def test_nesting(self):
        salt = DiveConfig(physics=PhysicsConfig(water_density=1.025))
        fresh = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        with salt:
            with fresh:
                assert DiveConfig.current().physics.water_density == 1.0
            assert DiveConfig.current().physics.water_density == 1.025

    def test_restores_on_exception(self):
        try:
            with DiveConfig(physics=PhysicsConfig(water_density=1.0)):
                raise RuntimeError
        except RuntimeError:
            pass
        assert DiveConfig.current().physics.water_density == 1.025

    def test_returns_self(self):
        cfg = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        with cfg as entered:
            assert entered is cfg

    def test_context_does_not_affect_default(self):
        original_default = DiveConfig._default
        with DiveConfig(physics=PhysicsConfig(water_density=1.0)):
            pass
        assert DiveConfig._default is original_default

    def test_scoped_override_is_thread_isolated(self):
        """A scoped override in one thread must not leak into another.

        The override stack is a ContextVar, so each thread starts with the
        startup default and only sees its own overrides.
        """
        import threading

        seen: dict[str, float] = {}

        def worker() -> None:
            # Worker starts fresh — should NOT see the main thread's override.
            seen["worker_before"] = DiveConfig.current().physics.water_density
            with DiveConfig(physics=PhysicsConfig(water_density=1.0)):
                seen["worker_inside"] = DiveConfig.current().physics.water_density

        with DiveConfig(physics=PhysicsConfig(water_density=1.5)):
            t = threading.Thread(target=worker)
            t.start()
            t.join()
            seen["main_inside"] = DiveConfig.current().physics.water_density

        assert seen["worker_before"] == 1.025  # factory default, not main's 1.5
        assert seen["worker_inside"] == 1.0
        assert seen["main_inside"] == 1.5  # worker's override did not leak back


# ---------------------------------------------------------------------------
# Default config loading — env var and file resolution
# ---------------------------------------------------------------------------


class TestDefaultConfigLoading:
    def test_disable_flag_uses_factory_defaults(self):
        os.environ[_ENV_VAR_DISABLE] = "1"
        assert DiveConfig.current().physics.water_density == 1.025

    def test_env_var_loads_config(self, tmp_path):
        cfg = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        path = str(tmp_path / "config.json")
        cfg.to_json(path=path)
        os.environ[_ENV_VAR] = path
        assert DiveConfig.current().physics.water_density == 1.0

    def test_env_var_invalid_falls_through_to_defaults(self, tmp_path):
        bad_path = str(tmp_path / "bad.json")
        Path(bad_path).write_text("not valid json", encoding="utf-8")
        os.environ[_ENV_VAR] = bad_path
        # should not raise — falls through to factory defaults
        assert DiveConfig.current().physics.water_density == 1.025

    def test_env_var_missing_file_falls_through(self, tmp_path):
        os.environ[_ENV_VAR] = str(tmp_path / "nonexistent.json")
        assert DiveConfig.current().physics.water_density == 1.025

    def test_project_file_loaded(self, tmp_path, monkeypatch):
        cfg = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        project_cfg = tmp_path / _PROJECT_FILE
        project_cfg.write_text(cfg.to_json(), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert DiveConfig.current().physics.water_density == 1.0

    def test_env_var_takes_priority_over_project_file(self, tmp_path, monkeypatch):
        # project file has density 1.0
        project_cfg = tmp_path / _PROJECT_FILE
        project_cfg.write_text(
            DiveConfig(physics=PhysicsConfig(water_density=1.0)).to_json(),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        # env var has density 0.9
        env_cfg_path = str(tmp_path / "env_config.json")
        DiveConfig(physics=PhysicsConfig(water_density=0.9)).to_json(path=env_cfg_path)
        os.environ[_ENV_VAR] = env_cfg_path

        assert DiveConfig.current().physics.water_density == 0.9

    def test_disable_flag_overrides_env_var(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        DiveConfig(physics=PhysicsConfig(water_density=1.0)).to_json(path=cfg_path)
        os.environ[_ENV_VAR] = cfg_path
        os.environ[_ENV_VAR_DISABLE] = "1"
        assert DiveConfig.current().physics.water_density == 1.025

    def test_invalid_project_file_falls_through(self, tmp_path, monkeypatch):
        project_cfg = tmp_path / _PROJECT_FILE
        project_cfg.write_text("not valid json", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert DiveConfig.current().physics.water_density == 1.025

    def test_loading_emits_warning_on_invalid_file(self, tmp_path, caplog):
        bad_path = str(tmp_path / "bad.json")
        Path(bad_path).write_text("not valid json", encoding="utf-8")
        os.environ[_ENV_VAR] = bad_path
        with caplog.at_level(logging.WARNING, logger="diveplan.core.config"):
            DiveConfig.current()
        assert any("invalid" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_json_roundtrip(self):
        original = DiveConfig(
            physics=PhysicsConfig(water_density=1.0),
            gas=GasConfig(max_ppo2_bar=2.0),
        )
        restored = DiveConfig.from_json(data=original.to_json())
        assert restored.physics.water_density == 1.0
        assert restored.gas.max_ppo2_bar == 2.0

    def test_json_structure(self):
        parsed = json.loads(DiveConfig().to_json())
        assert "physics" in parsed
        assert "planning" in parsed
        assert "gas" in parsed

    def test_json_file_roundtrip(self, tmp_path):
        path = str(tmp_path / "config.json")
        original = DiveConfig(physics=PhysicsConfig(water_density=1.0))
        original.to_json(path=path)
        restored = DiveConfig.from_json(path=path)
        assert restored.physics.water_density == 1.0

    def test_from_json_requires_argument(self):
        with pytest.raises(ValueError, match="path"):
            DiveConfig.from_json()
