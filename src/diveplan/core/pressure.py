from dataclasses import dataclass


@dataclass(
    frozen=True
)  # ? Is dataclass appropriate for this use case? It provides immutability and auto-generated methods, but may be overkill for a simple wrapper class.
class Pressure:
    _mbar: int

    @classmethod
    def from_bar(cls, bar: float) -> Pressure:
        return cls(round(bar * 1000))

    @classmethod
    def from_depth_m(cls, depth_m: float) -> Pressure:
        return cls.from_bar(1.0 + depth_m * 0.1)  # TODO

    @property
    def mbar(self) -> int:
        return self._mbar

    @property
    def bar(self) -> float:
        return self._mbar / 1000.0

    @property
    def depth_m(self) -> float:
        return (self.bar - 1.0) * 10.0  # TODO:

    # TODO: add more methods for pressure manipulation (e.g., addition, subtraction, etc.)
