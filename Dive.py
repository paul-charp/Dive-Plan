class Dive():
    """docstring for Dive."""
    def __init__(self, planned_steps):
        super(Dive, self).__init__()

        for step in planned_steps:
            self.steps.append(Divestep(step))
            
        self.ascend = [Divesteps,]
        self.gases = [Gas,]
        self.GF = (80/80)
        self.bottom_sac = 20
        self.deco_sac = 15
        self.compartments = [Compartment, ]
        self.samplerate = 1
        
    
    def calc_ascend():
        pass
    
    def calc_steps():
        pass
    
    def calc_rockbottom():
        pass
    
    def report() -> DiveReport:
        pass