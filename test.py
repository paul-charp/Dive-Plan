from diveplan.Dive import Dive, DiveStep
from diveplan.Gas import Gas, GasPlan
from diveplan.utils import utils

air = Gas()

dive = Dive([
    DiveStep(23, 40, 40, air)
    ])

dive.GF = (80, 80)
dive.initDecoModel()


dive.calc_steps()
dive.calc_ascend()
dive.report()

plan = GasPlan(
    [
        Gas(),
        Gas(1),
        Gas(0.5),
        Gas(0.21, 0.3),
        Gas(0.12, 0.5),
        Gas(0.5, 0.3)
    ]
)

depths = [6, 15, 20, 33, 60, 70, 100, 200]

for depth in depths:
    P_amb = utils.depth_to_P_amb(depth)
    
    
    print(f'Depth {depth}m')
    
    gases = plan.bestGases(P_amb)
    
    print(gases)
    
    
for depth in depths:
    print(f'Depth {depth}m')
    P_amb = utils.depth_to_P_amb(depth)
    gas = plan.makeBestMix(P_amb)
    print(gas)