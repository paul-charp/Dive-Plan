from .. import utils
from ..utils import constants


class DiveStep():
    """docstring for DiveStep."""
    def __init__(self, time, samplerate, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()

        self.samplerate = samplerate
        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas = [gas]
        
        if self.start_depth > self.end_depth:
            self.type = 'ascent'
            self.rate = constants.ASC_RATE
            
        elif self.start_depth < self.end_depth:
            self.type = 'descent'
            self.rate = constants.DES_RATE
            
        else:
            self.type = 'const'


        if time == 0:
            self.time = (end_depth - start_depth) / constants.ASC_RATE
        else:
            self.time = time
    
    def get_P_amb_at_sample(self, s: float) -> float:
        
        depth_at_sample = self.start_depth + (s / (self.samplerate - 1)) * (self.end_depth - self.start_depth)
        
        return utils.depth_to_P_amb(depth_at_sample)

    