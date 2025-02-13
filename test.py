from diveplan.core.dive import Dive
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.core.gasplan import GasPlan
from diveplan.core.pressure import Pressure


air = Gas()
nx50 = Gas(0.5)
oxy = Gas(1)
bot_gas = Gas.make_best_mix(Pressure.from_depth(80))
gases = [air, nx50, oxy, bot_gas]

steps = [DiveStep(20, 80, 80, bot_gas)]

dive = Dive(steps, gases, decomodel_parms={"GF": (50, 70)}, decomodel_samplerate=0.1)

dive.plan()
dive.report()
