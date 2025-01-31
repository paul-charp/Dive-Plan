from diveplan.Dive import DiveStep
from diveplan.utils import utils


class AbstractDecoModel:
    """docstring for DecoModel."""

    NAME = ""

    def __init__(self, samplerate):
        super(AbstractDecoModel, self).__init__()

        self.samplerate = samplerate

    def integrateDiveStep(self, divestep: DiveStep):
        for s in utils.frange(0, divestep.time, self.samplerate):
            self._integrateModel(divestep, s)

    def _integrateModel(self):
        pass

    def getCeiling(self) -> float:
        return -1
