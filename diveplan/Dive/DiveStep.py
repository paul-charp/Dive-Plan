from .. import utils


class DiveStep():
    """docstring for DiveStep."""
    def __init__(self, time, samplerate, start_depth, end_depth, gas):
        super(DiveStep, self).__init__()
        self.time = time
        self.samplerate = samplerate
        self.start_depth = start_depth
        self.end_depth = end_depth
        self.gas = [gas]
        
        if self.start_depth > self.end_depth:
            self.type = 'ascent'
            
        elif self.start_depth < self.end_depth:
            self.type = 'descent'
            
        else:
            self.type = 'const'

    
    def get_P_amb_at_sample(self, s: float) -> float:
        
        depth_at_sample = self.start_depth + (s / (self.samplerate - 1)) * (self.end_depth - self.start_depth)
        
        return utils.depth_to_P_amb(depth_at_sample)

    