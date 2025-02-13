from diveplan.core.dive import Dive
from diveplan.core.divestep import DiveStep
from diveplan.core.gas import Gas
from diveplan.core.gasplan import GasPlan
from diveplan.core.pressure import Pressure


gasplan = GasPlan([Gas(), Gas(0.5), Gas(1.0)])

depths = [40, 12, 21, 5, 3, 6]

print("Avail Gases")
print(gasplan.gases)

for depth in depths:

    P_amb = Pressure.from_depth(depth)
    current_gas = gasplan.bestGases(P_amb)[-1]

    gas_switches = gasplan.getNextGasSwitch(P_amb, current_gas)

    print(
        f"At a depth of {depth}m while breating {current_gas}, upcoming gas switches are : "
    )

    for gas_switch in gas_switches:
        P, gas = gas_switch
        print(f"switch at {P.to_depth()}m for {gas}")


air = Gas()
nx50 = Gas(0.5)
gases = [air]

steps = [DiveStep(20, 40, 40, air)]

dive = Dive(steps, gases, decomodel_parms={"GF": (80, 80)}, decomodel_samplerate=0.1)

dive.plan()
dive.report()

dive_2 = Dive([DiveStep(40, 20, 20, air)], gases)

dive_2.init_from_previous_dive(dive, 240)

dive_2.plan()
dive_2.report()
dive_2.plan()
dive_2.plan()
dive_2.plan()
dive_2.plan()
dive_2.report()
