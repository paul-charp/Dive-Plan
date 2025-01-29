from ..Gas.Gas import Gas
from .DiveStep import DiveStep
from ..DecoModels.ZHL16C_GF import ZHL16C_GF
from ..DecoModels.AbstractDecoModel import AbstractDecoModel
from .. import utils

class Dive():
    """docstring for Dive."""
    def __init__(self, planned_steps):
        super(Dive, self).__init__()

        self.steps = []
        for step in planned_steps:
            self.steps.append(step)
            
        self.ascend: tuple[DiveStep] = []
        self.gases: list[Gas] = [Gas()]
        self.GF = (80, 80)
        self.bottom_sac = 20
        self.deco_sac = 15
        self.samplerate = 1
        
        self.decomodel: ZHL16C_GF = ZHL16C_GF(self.GF)
    
    def calc_ascend(self):
        bottom_depth = self.steps[-1].end_depth
        P_amb = utils.depth_to_P_amb(bottom_depth)
        P_surf = utils.depth_to_P_amb(0)
        
        while P_amb > P_surf:
            ceil = utils.round_to_stop_P(
                self.decomodel.getCeiling()
            )
            
            time = 0 
            if P_amb >= ceil:
                time = 1
                
            asc_step = DiveStep(time,
                                0.1, 
                                utils.P_amb_to_depth(P_amb),
                                utils.P_amb_to_depth(ceil),
                                self.gases[0])
            
            self.decomodel.integrateModel(asc_step)
            P_amb = ceil
    
    def calc_steps(self):
        for step in self.steps:
            self.decomodel.integrateModel(step)
    
    def calc_rockbottom():
        pass