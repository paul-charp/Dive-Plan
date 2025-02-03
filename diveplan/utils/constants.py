# Surface Air Composition
AIR_FO2: float = 0.21
AIR_FN2: float = 0.79
AIR_FHE: float = 0.0

# Physics (using scientific notation for clarity)
G: float = 9.81  # m/s^2
WATER_DENSITY: float = 1020  # kg/m^3
P_ATM: float = 1.01325  # bar

# Algorithm Precision
# Algorithm Precision
P_PRECISION: int = 5  # For pressure calculations
COMPARTMENT_PRECISION: int = (
    5  # For compartment related calculations (gas loading, tolerated pressure, etc.)
)
DEPTH_PRECISION: int = 2  # Number of decimal places for depth

# Dive Parameters
ASC_RATE: float = 10.0  # m/min
DES_RATE: float = 20.0  # m/min
STOP_INC: float = 3.0  # m
LAST_STOP_DEPTH: float = 6.0  # m  More descriptive name
MIN_PPO2: float = 0.18  # bar
DECO_PPO2: float = 1.6  # bar  Consistent naming

# --- Derived Constants (Calculated for efficiency) ---

# Pre-calculate common values used in depth/pressure conversions. These are computed once at import time, and avoids calculating them repeatedly,
# hence improving overall code performance slightly.
P_WATER_DEPTH_CONVERSION_FACTOR = (
    WATER_DENSITY * G * 1e-5
)  # pre-calculated value for clarity
