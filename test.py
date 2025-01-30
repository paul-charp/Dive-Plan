from diveplan.Dive import Dive, DiveStep
from diveplan.Gas import Gas

air = Gas()

dive = Dive([
    DiveStep(23, 40, 40, air)
    ])

dive.GF = (80, 80)
dive.initDecoModel()


dive.calc_steps()
dive.calc_ascend()
dive.report()
