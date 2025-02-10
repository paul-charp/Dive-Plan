from diveplan.core.dive import Dive
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas

air = Gas()

steps = [DiveStep(20, 40, 40, air)]

dive = Dive(steps)

dive.calc_steps()

dive.calc_ascend()

dive.report()
