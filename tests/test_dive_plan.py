import pytest
from diveplan.Dive import Dive, DiveStep
from diveplan.Gas import Gas, GasPlan
from diveplan.utils import utils


# Test de la conversion de profondeur en pression ambiante
def test_depth_to_P_amb():
    """Test de la conversion profondeur -> pression ambiante"""
    depths_and_pressures = {
        0: 1,  # A la surface, la pression est 1 bar
        10: 2,  # A 10m, pression = 2 bars (1 bar + 1 bar d'eau)
        20: 3,  # A 20m, pression = 3 bars
        40: 5,  # A 40m, pression = 5 bars
        100: 11,  # A 100m, pression = 11 bars
    }

    for depth, expected_pressure in depths_and_pressures.items():
        P_amb = utils.depth_to_P_amb(depth)
        assert (
            P_amb == expected_pressure
        ), f"Expected {expected_pressure} bar at {depth}m, but got {P_amb}."


# Test du calcul des meilleurs gaz à chaque profondeur
def test_best_gas_mix():
    """Test de la sélection des meilleurs gaz à chaque profondeur"""
    plan = GasPlan(
        [
            Gas(),  # Air
            Gas(1),  # Nitrox 32
            Gas(0.5),  # Nitrox 50
            Gas(0.21, 0.3),  # Air enrichi
            Gas(0.12, 0.5),  # Mélange spécial
            Gas(0.5, 0.3),  # Mélange pour plongée profonde
        ]
    )

    depths = [6, 15, 20, 33, 60, 70, 100, 200]

    for depth in depths:
        P_amb = utils.depth_to_P_amb(depth)

        gases = plan.bestGases(P_amb)

        # On vérifie qu'il y a au moins un gaz choisi
        assert gases, f"No gases found for depth {depth}m."

        # Vérification qu'il n'y a pas de gaz avec une concentration en oxygène négative
        for gas in gases:
            assert (
                gas.O2 >= 0
            ), f"Invalid O2 concentration ({gas.O2}) in gas mix at {depth}m."


# Test de la plongée avec un plan de décompression
def test_dive_decompression():
    """Test du calcul de la décompression dans un plan de plongée"""
    air = Gas()  # Gaz de base (air)

    dive = Dive([DiveStep(23, 40, 40, air)])
    dive.GF = (80, 80)  # Facteurs de gradient
    dive.initDecoModel()

    # Test que les étapes de décompression et de remontée sont calculées sans erreur
    try:
        dive.calc_steps()
        dive.calc_ascend()
    except Exception as e:
        pytest.fail(f"Decompression steps calculation failed: {e}")

    # On vérifie que les étapes de décompression ne sont pas vides
    assert dive.decompression_steps, "No decompression steps found."

    # Vérification que le premier calcul de remontée est valide
    assert dive.ascend_steps, "No ascend steps found."


# Test de la fonction `makeBestMix`
def test_make_best_mix():
    """Test du calcul du meilleur mélange de gaz pour une profondeur"""
    plan = GasPlan(
        [
            Gas(),  # Air
            Gas(1),  # Nitrox 32
            Gas(0.5),  # Nitrox 50
            Gas(0.21, 0.3),  # Air enrichi
            Gas(0.12, 0.5),  # Mélange spécial
            Gas(0.5, 0.3),  # Mélange pour plongée profonde
        ]
    )

    depths = [6, 15, 20, 33, 60, 70, 100, 200]

    for depth in depths:
        P_amb = utils.depth_to_P_amb(depth)

        best_gas = plan.makeBestMix(P_amb)

        # Vérification que le mélange de gaz est valide
        assert best_gas, f"No best gas mix found for depth {depth}m."
        assert (
            best_gas.O2 >= 0
        ), f"Invalid O2 concentration ({best_gas.O2}) in best gas mix at {depth}m."
        assert (
            0 <= best_gas.O2 <= 1
        ), f"O2 concentration out of range (0-1) for best gas mix at {depth}m."


# Test de l'initialisation du modèle de décompression (pas de crash)
def test_init_deco_model():
    """Test que l'initialisation du modèle de décompression fonctionne"""
    air = Gas()  # Gaz de base (air)

    dive = Dive([DiveStep(23, 40, 40, air)])
    dive.GF = (80, 80)  # Facteurs de gradient
    try:
        dive.initDecoModel()
    except Exception as e:
        pytest.fail(f"Deco model initialization failed: {e}")


# Test des paramètres invalides (mauvaise profondeur ou gaz non valide)
def test_invalid_parameters():
    """Test des paramètres invalides dans le plan de plongée"""
    with pytest.raises(ValueError):
        # Gaz avec une concentration en oxygène supérieure à 1, ce qui est invalide
        invalid_gas = Gas(1.2)

    with pytest.raises(ValueError):
        # Profondeur invalide
        utils.depth_to_P_amb(-10)
