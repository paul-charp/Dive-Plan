from diveplan.core.dive import Dive
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.utils.utils import round_to_gas_switch_P

air = Gas()
nx50 = Gas(0.5)
gases = [air, nx50]


steps = [DiveStep(20, 40, 40, air)]

dive = Dive(steps, gases)

dive.calc_steps()
dive.calc_ascend()
