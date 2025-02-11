from diveplan.core.dive import Dive
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas


air = Gas()
nx50 = Gas(0.5)
gases = [air, nx50]

steps = [DiveStep(20, 40, 40, air)]

dive = Dive(steps, gases, "Buhlmann ZHL16-C + GF", {"GF": (100, 100)})

dive.calc_steps()
dive.calc_ascend()
dive.report()
