class Gas():
    
    AIR_FO2 = 0.21
    AIR_FN2 = 0.80
    
    def __init__(self, frac_O2: float=AIR_FO2, frac_H2: float=0.0):
        super(Gas, self).__init__()
        self.frac_O2 = frac_O2
        self.frac_H2 = frac_H2
        self.frac_N2 = 1 - (frac_O2 + frac_H2)
  
        
    def ppO2(self, P_amb: float) -> float:
        return P_amb * self.frac_O2
    
    
    def ppN2(self, P_amb: float) -> float:
        return P_amb * self.frac_N2
   
    
    def ppH2(self, P_amb: float) -> float:
        return P_amb * self.frac_H2
    
    
    def equivalentNarcoticPressure(self, P_amb: float) -> float:
        return self.ppN2(P_amb) / self.AIR_FO2


    def maxOperatingPressure(self, max_ppO2: float=1.6):
        return max_ppO2 / self.frac_O2
    
    
    