from abc import ABC, abstractmethod

from diveplan.utils.physics import frange


class AbstractDecoModel(ABC):  # Inherit from ABC
    """Abstract base class for decompression models."""

    name: str  # Make name a class attribute

    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate

    @abstractmethod  # Mark _integrate_model as abstract
    def _integrate_model(self, dive_step, sample_time: float):
        """Integrates the model for a single time step."""
        raise NotImplementedError  # Raise a more specific error

    def integrate_dive_step(self, dive_step):
        """Integrates the model over a given dive step."""
        for sample_time in frange(0, dive_step.time, self.sample_rate):
            self._integrate_model(dive_step, sample_time)

    @abstractmethod  # Make get_ceiling abstract
    def get_ceiling(self) -> float:
        """Returns the current decompression ceiling."""
        raise NotImplementedError
