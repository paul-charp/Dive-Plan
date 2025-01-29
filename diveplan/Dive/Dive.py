from ..Gas.Gas import Gas
from .DiveStep import DiveStep
from .. import utils

class Dive():
    """docstring for Dive."""
    def __init__(self, planned_steps):
        super(Dive, self).__init__()

        for step in planned_steps:
            self.steps.append(DiveStep(step))
            
        self.ascend: tuple[DiveStep] = ()
        self.gases: list[Gas] = []
        self.GF = (80/80)
        self.bottom_sac = 20
        self.deco_sac = 15
        self.samplerate = 1
        
    
    def calc_ascend():
        pass
    
    def calc_steps():
        pass
    
    def calc_rockbottom():
        pass