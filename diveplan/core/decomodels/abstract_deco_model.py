from abc import ABC, abstractmethod
from typing import Any

from diveplan.core import utils
from diveplan.core.divestep import DiveStep
from diveplan.core.pressure import Pressure


class AbstractDecoModel(ABC):

    NAME: str = ""
    DECO_MODEL_VAR: str = ""

    def __init__(self, samplerate: float, **kwargs: Any) -> None:
        super(AbstractDecoModel, self).__init__()

        self.samplerate = samplerate

    @property
    def samplerate(self) -> float:
        return self._samplerate

    @samplerate.setter
    def samplerate(self, value: float) -> None:
        try:
            value = float(value)
        except:
            TypeError("Sample rate is not a number")

        if value <= 0:
            raise ValueError("samplerate should be > 0 !")

        self._samplerate: float = value

    def integrateDiveStep(self, divestep: DiveStep) -> None:
        for s in utils.frange(0, divestep.time, self.samplerate):
            self._integrateModel(divestep, s)

    @abstractmethod
    def _integrateModel(self, divestep: DiveStep, s: float) -> None:
        raise NotImplementedError()

    @abstractmethod
    def getCeiling(self) -> Pressure:
        raise NotImplementedError()
