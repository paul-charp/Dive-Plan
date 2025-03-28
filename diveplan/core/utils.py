import importlib
import inspect
import pkgutil

from diveplan.core.divestep import DiveStep


def frange(start: float, stop: float, step: float):
    """
    Yields a range of floats at specific interval.

    """
    while start < stop:
        yield round(start, 10)
        start += step


def find_decomodels() -> dict:
    """
    Finds all available DecoModels

    Returns:
        dict[Deco model Name] : Deco model class

    """

    package_name: str = "diveplan.core.decomodels"

    base_class = getattr(
        importlib.import_module(f"{package_name}.abstract_deco_model"),
        "AbstractDecoModel",
    )

    package = importlib.import_module(package_name)

    subclasses = {}

    for _, module_name, _ in pkgutil.iter_modules(package.__path__, package_name + "."):
        module = importlib.import_module(module_name)

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, base_class) and obj is not base_class:
                subclasses[obj.NAME] = obj

    return subclasses


def simplify_divesteps(divesteps: list[DiveStep]) -> list[DiveStep]:

    new_divesteps: list[DiveStep] = [divesteps[0]]

    for i in range(1, len(divesteps)):

        divestep = divesteps[i]

        if divestep.is_continuous(new_divesteps[-1]):
            new_divesteps[-1].extend(divestep)

        else:
            new_divesteps.append(divestep)

    return new_divesteps


def meters_to_feet(value: float) -> float:
    return value * 3.28084


def feet_to_meters(value: float) -> float:
    return value / 3.28084


def bar_to_psi(value: float) -> float:
    return value * 14.5038


def psi_to_bar(value: float) -> float:
    return value / 14.5038
