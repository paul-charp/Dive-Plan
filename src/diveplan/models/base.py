from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

from diveplan.core.gas import Gas

from ..core.dive_segment import DiveSegment
from ..core.pressure import Pressure

__all__ = ["BaseDecoModel"]


class BaseDecoModel(ABC):
    """Base class for all decompression models."""

    __slots__ = ["sample_rate_seconds"]

    NAME: str

    @abstractmethod
    def __init__(self, *args, **kwargs):
        """Initialize the decompression model."""
        self.sample_rate_seconds = 1
        pass

    def integrate_segment(self, segment: DiveSegment) -> dict[str, Any]:
        """Integrate a dive segment into the model."""

        sample_time = timedelta(seconds=self.sample_rate_seconds)

        for duration, pressure in segment.iter_pressures(sample_time):
            self._integrate_model(pressure, segment.gas, duration)

        return self._get_deco_state()

    @abstractmethod
    def _integrate_model(self, pressure: Pressure, gas: Gas, duration: timedelta):
        pass

    @abstractmethod
    def _get_deco_state(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_ceiling(self) -> Pressure:
        """Return the current ceiling depth."""
        pass
