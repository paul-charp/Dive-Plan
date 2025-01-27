import math

COMPARTEMENT_CONST = [
    {"comp": 1, "htime": 4.0, "a": 1.2599, "b": 0.5050},
    {"comp": 2, "htime": 8.0, "a": 1.0000, "b": 0.6514},
    {"comp": 3, "htime": 12.5, "a": 0.8618, "b": 0.7222},
    {"comp": 4, "htime": 18.5, "a": 0.7562, "b": 0.7725},
    {"comp": 5, "htime": 27.0, "a": 0.6667, "b": 0.8125},
    {"comp": 6, "htime": 38.3, "a": 0.5933, "b": 0.8434},
    {"comp": 7, "htime": 54.3, "a": 0.5282, "b": 0.8693},
    {"comp": 8, "htime": 77.0, "a": 0.4701, "b": 0.8910},
    {"comp": 9, "htime": 109.0, "a": 0.4187, "b": 0.9092},
    {"comp": 10, "htime": 146.0, "a": 0.3798, "b": 0.9222},
    {"comp": 11, "htime": 187.0, "a": 0.3497, "b": 0.9319},
    {"comp": 12, "htime": 239.0, "a": 0.3223, "b": 0.9403},
    {"comp": 13, "htime": 305.0, "a": 0.2971, "b": 0.9477},
    {"comp": 14, "htime": 390.0, "a": 0.2737, "b": 0.9544},
    {"comp": 15, "htime": 498.0, "a": 0.2523, "b": 0.9602},
    {"comp": 16, "htime": 635.0, "a": 0.2327, "b": 0.9653},
]


DEPTH = 40
BOTTIME = 20
START_P = 0.80

DESC_RATE = 18
ASC_RATE = 9

def P_amb(depth):
    return (depth / 10) + 1

def depthConv(P):
    return (P - 1) * 10

def P_comp(comp, P_gas, time):
    P_begin = comp['p']
    return P_begin + (P_gas - P_begin) * (1-2**( - time / comp['htime']))

def P_tol(comp):
    return (comp['p'] - comp['a']) * comp['b']

def update_compartements(depth, time):
    P_gas = P_amb(depth) * START_P
    
    for compartement in COMPARTEMENT_CONST:
        
        
        
        compartement['p'] = P_comp(
            compartement,
            P_gas,
            time
        )
        
        compartement['pceil'] = P_tol(
            compartement
        )

def get_P_ceil():
    m = 0
    for compartement in COMPARTEMENT_CONST:
        m = max(compartement['pceil'], m)
        
    return m
    #return max(COMPARTEMENT_CONST, key=lambda x: x["pceil"])['pceil']
    
def round_ceil(value):
    value = depthConv(value)
    return P_amb(math.ceil(value / 3) * 3)


#Init Comp
for compartement in COMPARTEMENT_CONST:
    compartement['p'] = START_P

RT = 0
# Descent
desc_time = DEPTH/DESC_RATE

RT += desc_time
print(f'Desc to {DEPTH} @ {RT}')

update_compartements(DEPTH/2, desc_time)

#Bottom
update_compartements(DEPTH, BOTTIME-desc_time)

RT += BOTTIME-desc_time
print(f'End of bot time {DEPTH} @ {RT}')

#Asc
depth = P_amb(DEPTH)

while depth > 1:
    
    ceil = round_ceil(get_P_ceil())
    
    if ceil <= 1:
        print('DIRECT SURFACE ASC')
        break
    
    if (depth - 0.1) >= ceil:
        old_d = depth
        depth -= 0.1
        update_compartements(depthConv((old_d + depth)/2), 1/9)
        RT += 1/9
        print(f'Asc to {depthConv(depth)} @ {RT} // Ceil {depthConv(ceil)}')
        print(' ')
        
    else:
        print(f'STOP AT {depthConv(depth)} @ {RT}')
        print(' ')
        RT += 1
        update_compartements(depthConv(depth), 1)
