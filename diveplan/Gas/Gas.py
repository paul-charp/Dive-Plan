from ..utils import constants


class Gas():
    def __init__(self,
                 frac_O2: float=constants.AIR_FO2,
                 frac_He: float=constants.AIR_FHE):
        
        super(Gas, self).__init__()
        
        self.frac_O2 = frac_O2
        self.frac_He = frac_He
        self.frac_N2 = 1 - (frac_O2 + frac_He)
        
        self.consumption: float = 0
  
        
    def ppO2(self, P_amb: float) -> float:
        return P_amb * self.frac_O2
    
    
    def ppN2(self, P_amb: float) -> float:
        return P_amb * self.frac_N2
   
    
    def ppHe(self, P_amb: float) -> float:
        return P_amb * self.frac_He
    
    
    def equivalentNarcoticPressure(self, P_amb: float) -> float:
        return self.ppN2(P_amb) / constants.AIR_FO2


    def maxOperatingPressure(self, max_ppO2: float=1.6):
        return max_ppO2 / self.frac_O2
    
    
    def consume(self, P_amb: float, time: float, sac: float):
        self.consumption += P_amb * time * sac    
    
    