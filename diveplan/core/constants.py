from diveplan.core.pressure import Pressure

# SURFACE AIR COMPOSITION
AIR_FO2 = 0.21
AIR_FN2 = 0.79
AIR_FHE = 0

# PHYSICS
G = 9.81

# Algorithms Precisions
P_PRECISION = 5
DEPTH_PRECISION = 2

SAMPLE_RATE = 0.1

# TEMP DEFAULT VALUES
WATER_DENSITY = 1020
P_ATM = Pressure(1.01325)

# DIVE PLANING DEFAULT VALUES
ASC_RATE = 10  # m/min
DES_RATE = 20  # m/min

MIN_PPO2: Pressure = Pressure(0.18)
DECO_PP02: Pressure = Pressure(1.61362)
BOT_PPO2: Pressure = Pressure(1.4)

STOP_INC = 3
LAST_STOP = 6

SWITCH_AT_STOPS = False

DECO_SAC = 15
BOT_SAC = 20
