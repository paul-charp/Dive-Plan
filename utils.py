import math


WATER_DENSITY = 1020
G = 9.81
P_ATM = 1.01325
P_PRECISION = 5
DEPTH_PRECISION = 2


def depth_to_P_amb(depth: float,
                   P_atm: float=P_ATM,
                   water_density: float=WATER_DENSITY) -> float:
    
    P_amb: float = P_atm + ((water_density * G * 10**-5) * depth )
    return round(P_amb, P_PRECISION)


def P_amb_to_depth(P_amb: float,
                   P_atm: float=P_ATM,
                   water_density: float=WATER_DENSITY) -> float:
    
    depth: float = (P_amb - P_atm) / (water_density * G  * 10**-5)
    return round(depth, DEPTH_PRECISION)


def round_to_stop_P(P: float, stop_inc: float=3.0) -> float:
    depth = P_amb_to_depth(P)
    
    rounded_depth = math.ceil(depth / stop_inc) * stop_inc
    
    return depth_to_P_amb(rounded_depth)