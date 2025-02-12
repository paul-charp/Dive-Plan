from abc import ABC, abstractmethod

from diveplan.core.divestep import DiveStep
from diveplan.core import utils
from diveplan.core.pressure import Pressure


class AbstractDecoModel(ABC):

    NAME = ""

    def __init__(self, samplerate: float, parms: dict = {}):
        super(AbstractDecoModel, self).__init__()

        self.samplerate = samplerate
        self.parms = parms

    @property
    def samplerate(self):
        return self._samplerate

    @samplerate.setter
    def samplerate(self, value):
        try:
            value = float(value)
        except:
            TypeError("Sample rate is not a number")

        if value <= 0:
            raise ValueError("samplerate should be > 0 !")

        self._samplerate = value

    def integrateDiveStep(self, divestep: DiveStep):
        for s in utils.frange(0, divestep.time, self.samplerate):
            self._integrateModel(divestep, s)

    @abstractmethod
    def _integrateModel(self):
        raise NotImplementedError()

    @abstractmethod
    def getCeiling(self) -> Pressure:
        raise NotImplementedError()
