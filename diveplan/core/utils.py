import importlib
import pkgutil
import inspect

from diveplan.core import dive
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

    new_divesteps: list[DiveStep] = []

    for i, divestep in enumerate(divesteps):
        try:
            next_step = divesteps[i + 1]

            if (
                (next_step.type == divestep.type)
                and (next_step.start_depth == divestep.end_depth)
                and (next_step.rate == divestep.rate)
                and (next_step.gas == divestep.gas)
            ):
                new_divesteps.append(
                    DiveStep(
                        next_step.time + divestep.time,
                        divestep.start_depth,
                        next_step.end_depth,
                        divestep.gas,
                    )
                )

            else:
                new_divesteps.append(divestep)

        except:
            new_divesteps.append(divestep)
            break

    return new_divesteps
