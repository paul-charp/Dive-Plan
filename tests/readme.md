# Tests pour Dive-Plan

Ce dossier contient l'ensemble des tests unitaires et fonctionnels pour le projet **Dive-Plan**. Ces tests vérifient les fonctionnalités principales du modèle de plongée, y compris la gestion des gaz, des plongées, et des calculs de décompression.

## Structure du Dossier

- **`tests/test_dive_plan.py`** : Tests unitaires pour les fonctionnalités principales du module `DivePlan`, incluant la conversion de profondeur en pression ambiante, la gestion des mélanges de gaz, et le calcul des étapes de décompression.
- **`/pytest.ini`** : Configuration de pytest, permettant de spécifier des options globales pour l'exécution des tests.

## Fonctionnalités Testées

1. **Conversion de profondeur en pression ambiante** :
   - Teste la fonction `depth_to_P_amb()` pour convertir la profondeur en pression ambiante (P_amb). Cela prend en compte la pression de l'eau et la pression atmosphérique.

2. **Calcul des meilleurs gaz à chaque profondeur** :
   - Teste la fonction `bestGases()` dans la classe `GasPlan` pour s'assurer que les meilleurs gaz sont choisis pour chaque profondeur de plongée.

3. **Calcul du mélange optimal de gaz pour une plongée** :
   - Teste la fonction `makeBestMix()` pour s'assurer qu'un mélange optimal de gaz est calculé en fonction de la profondeur et de la pression ambiante.

4. **Calcul des étapes de décompression** :
   - Teste la classe `Dive` pour vérifier que le modèle de décompression fonctionne correctement, avec des tests sur les étapes de décompression et de remontée.

5. **Gestion des exceptions pour des paramètres invalides** :
   - Teste la gestion des erreurs dans les entrées de gaz (par exemple, une concentration d'oxygène supérieure à 1) et de profondeur (par exemple, une profondeur négative).

## Exécution des Tests

### Prérequis

Avant d'exécuter les tests, assure-toi d'avoir installé les dépendances nécessaires avec `pytest` et autres modules de test :

```bash
pip install -r requirements.txt
```

### Exécuter tous les tests
Pour exécuter tous les tests, utilise la commande suivante dans le terminal :
```bash
pytest

```

### Exécution d'un seul test spécifique
Si tu souhaites exécuter un test particulier, utilise la commande suivante (en remplaçant `test_name` par le nom du test) :
```bash
pytest -k test_name

```