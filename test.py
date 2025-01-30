from diveplan.Dive.Dive import Dive
from diveplan.Dive.DiveStep import DiveStep
from diveplan.Gas.Gas import Gas

air = Gas()

dive = Dive([
    DiveStep(0, 0.1, 0, 40, air),
    DiveStep(23, 0.1, 40, 40, air)
    ])

dive.GF = (80, 80)
dive.initDecoModel()


dive.calc_steps()
dive.calc_ascend()
dive.report()
