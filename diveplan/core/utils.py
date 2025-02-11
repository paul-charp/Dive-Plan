import importlib
import pkgutil
import inspect


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
