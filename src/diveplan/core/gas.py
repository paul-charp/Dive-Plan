"""Gas mix value object for diveplan.

Represents an immutable O2/He/N2 breathing gas mixture. Provides partial
pressure calculations, operating limits, and best-mix selection.
"""

import re

from diveplan.core.config import DiveConfig
from diveplan.core.pressure import Pressure

__all__ = ["Gas"]


class Gas:
    """Immutable O2/He/N2 breathing gas mixture.

    Fractions are stored as floats (0.0-1.0). ``fn2`` is derived:
    ``fn2 = 1.0 - fo2 - fhe``. The three fractions always sum to 1.0
    within a tolerance of 1e-6.

    Use the named constructors (``air``, ``nitrox``, ``trimix``, …)
    rather than the raw constructor wherever possible.

    Args:
        fo2: Oxygen fraction, e.g. ``0.21``.
        fhe: Helium fraction. Defaults to ``0.0`` (no helium).

    Raises:
        ValueError: If any fraction is negative, or the fractions do not
            sum to 1.0 within 1e-6.

    Example:
        >>> Gas(0.32)
        Gas(fo2=0.32, fhe=0.00, fn2=0.68)
        >>> Gas(0.21, fhe=0.35)
        Gas(fo2=0.21, fhe=0.35, fn2=0.44)
    """

    __slots__ = ("_fo2", "_fhe", "_fn2")

    def __init__(self, fo2: float, fhe: float = 0.0) -> None:
        fn2 = 1.0 - fo2 - fhe
        if fo2 < 0:
            raise ValueError(f"fo2 must be >= 0, got {fo2}")
        if fhe < 0:
            raise ValueError(f"fhe must be >= 0, got {fhe}")
        if fn2 < 0:
            raise ValueError(f"fn2 must be >= 0, got {fn2:.6f} (fo2={fo2}, fhe={fhe})")
        if abs(fo2 + fhe + fn2 - 1.0) > 1e-6:
            raise ValueError(f"Gas fractions must sum to 1.0, got {fo2 + fhe + fn2:.8f}")
        object.__setattr__(self, "_fo2", float(fo2))
        object.__setattr__(self, "_fhe", float(fhe))
        object.__setattr__(self, "_fn2", float(fn2))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Gas is immutable")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def fo2(self) -> float:
        """Oxygen fraction (0.0-1.0)."""
        return self._fo2

    @property
    def fhe(self) -> float:
        """Helium fraction (0.0-1.0)."""
        return self._fhe

    @property
    def fn2(self) -> float:
        """Nitrogen fraction (0.0-1.0), derived as ``1 - fo2 - fhe``."""
        return self._fn2

    # ------------------------------------------------------------------
    # Named constructors
    # ------------------------------------------------------------------

    @classmethod
    def air(cls) -> Gas:
        """Return standard air (21 % O2, 79 % N2).

        Returns:
            A ``Gas`` representing atmospheric air.
        """
        return cls(0.21, fhe=0.0)

    @classmethod
    def oxygen(cls) -> Gas:
        """Return 100 % oxygen.

        Returns:
            A ``Gas`` with ``fo2=1.0``.
        """
        return cls(1.0, fhe=0.0)

    @classmethod
    def nitrox(cls, fo2: float) -> Gas:
        """Return a nitrox (O2/N2) mix with the given O2 fraction.

        Args:
            fo2: Oxygen fraction, e.g. ``0.32`` for EAN32.

        Returns:
            A ``Gas`` with no helium and nitrogen making up the remainder.

        Raises:
            ValueError: If ``fo2 <= 0`` or ``fo2 > 1``.
        """
        if fo2 <= 0:
            raise ValueError(f"nitrox fo2 must be > 0, got {fo2}")
        return cls(fo2, fhe=0.0)

    @classmethod
    def ean(cls, fo2: float) -> Gas:
        """Alias for :meth:`nitrox`.

        Args:
            fo2: Oxygen fraction, e.g. ``0.32`` for EAN32.

        Returns:
            A ``Gas`` with no helium.
        """
        return cls.nitrox(fo2)

    @classmethod
    def trimix(cls, fo2: float, fhe: float) -> Gas:
        """Return a trimix (O2/He/N2) gas.

        Args:
            fo2: Oxygen fraction.
            fhe: Helium fraction.

        Returns:
            A ``Gas`` where nitrogen fills the remainder.

        Raises:
            ValueError: If ``fo2 <= 0``, ``fhe <= 0``, or fractions are
                otherwise invalid.
        """
        if fo2 <= 0:
            raise ValueError(f"trimix fo2 must be > 0, got {fo2}")
        if fhe <= 0:
            raise ValueError(f"trimix fhe must be > 0, got {fhe}")
        return cls(fo2, fhe=fhe)

    # ------------------------------------------------------------------
    # Name parser
    # ------------------------------------------------------------------

    @classmethod
    def from_name(cls, name: str) -> Gas:
        """Parse a gas mix from a human-readable name string.

        Supported formats (case-insensitive):

        * ``"air"``
        * ``"oxygen"``
        * ``"nx32"``, ``"ean32"``, ``"nitrox 32"`` — O2 % as integer
        * ``"tx21/35"``, ``"trimix 21/35"`` — O2%/He%

        Args:
            name: Human-readable gas name.

        Returns:
            The corresponding ``Gas`` instance.

        Raises:
            ValueError: If the name cannot be parsed.

        Example:
            >>> Gas.from_name("ean32")
            Gas(fo2=0.32, fhe=0.00, fn2=0.68)
            >>> Gas.from_name("tx21/35")
            Gas(fo2=0.21, fhe=0.35, fn2=0.44)
        """
        s = name.strip().lower()

        if s == "air":
            return cls.air()
        if s == "oxygen":
            return cls.oxygen()

        # nitrox: nx32, ean32, nitrox 32, nitrox32
        m = re.fullmatch(r"(?:nx|ean|nitrox)\s*(\d+(?:\.\d+)?)", s)
        if m:
            return cls.nitrox(float(m.group(1)) / 100)

        # trimix: tx21/35, trimix21/35, trimix 21/35
        m = re.fullmatch(r"(?:tx|trimix)\s*(\d+(?:\.\d+)?)[/\s](\d+(?:\.\d+)?)", s)
        if m:
            return cls.trimix(
                float(m.group(1)) / 100,
                float(m.group(2)) / 100,
            )

        raise ValueError(f"Cannot parse gas name: {name!r}")

    # ------------------------------------------------------------------
    # Partial pressures
    # ------------------------------------------------------------------

    def ppo2(self, pressure: Pressure) -> Pressure:  # noqa: F821
        """Return the partial pressure of O2 at the given ambient pressure.

        Args:
            pressure: Ambient pressure.

        Returns:
            Partial pressure of oxygen.
        """
        return pressure * self._fo2

    def pphe(self, pressure: Pressure) -> Pressure:  # noqa: F821
        """Return the partial pressure of He at the given ambient pressure.

        Args:
            pressure: Ambient pressure.

        Returns:
            Partial pressure of helium.
        """
        return pressure * self._fhe

    def ppn2(self, pressure: Pressure) -> Pressure:  # noqa: F821
        """Return the partial pressure of N2 at the given ambient pressure.

        Args:
            pressure: Ambient pressure.

        Returns:
            Partial pressure of nitrogen.
        """
        return pressure * self._fn2

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    def mod(self, *, ppo2_bar: float) -> Pressure:  # noqa: F821
        """Return the maximum operating depth (MOD) for a given ppO2 limit.

        Args:
            ppo2_bar: ppO2 ceiling in bar, e.g. ``1.4``.

        Returns:
            The MOD as a :class:`Pressure`.

        Raises:
            ValueError: If ``ppo2_bar <= 0``.

        Example:
            >>> from diveplan.core.pressure import Pressure
            >>> Gas.nitrox(0.32).mod(ppo2_bar=1.4).bar
            4.375
        """
        from diveplan.core.pressure import Pressure  # local to avoid circular

        if ppo2_bar <= 0:
            raise ValueError(f"ppo2_bar must be > 0, got {ppo2_bar}")

        return Pressure.from_bar(ppo2_bar / self._fo2)

    def end(self, pressure: Pressure) -> Pressure:  # noqa: F821
        """Return the equivalent narcotic depth (END) at the given pressure.

        Helium is assumed non-narcotic; the narcotic fraction is
        ``fo2 + fn2``.

        Args:
            pressure: Ambient pressure at depth.

        Returns:
            The END as a :class:`Pressure`.
        """
        narcotic_fraction = self._fo2 + self._fn2
        return pressure * narcotic_fraction

    def best_mix(
        self,
        depth: float | Pressure,
        *,
        trimix: bool = False,
        hypoxic: bool = False,
    ) -> "Gas":
        """Return the optimal gas mix for the given depth.

        Maximises ``fo2`` within the ppO2 and END/ppN2 constraints
        taken from :func:`diveplan.core.config.DiveConfig.current`.

        ``hypoxic=True`` implies ``trimix=True``.

        Args:
            depth: Target depth as metres (``float``) or a
                :class:`~diveplan.core.pressure.Pressure`.
            trimix: Allow helium in the mix.
            hypoxic: Allow fo2 below ``min_ppo2_bar`` at surface
                (implies ``trimix=True``).

        Returns:
            The best ``Gas`` for the given depth and constraints.

        Raises:
            ValueError: If the constraints cannot be satisfied (e.g.
                ``best_mix(120, trimix=False)``).

        Example:
            >>> Gas.air().best_mix(30)
            Gas(fo2=0.32, fhe=0.00, fn2=0.68)
        """

        if hypoxic:
            trimix = True

        if not isinstance(depth, Pressure):
            pressure = Pressure.from_depth_m(float(depth))
        else:
            pressure = depth

        cfg = DiveConfig.current().gas
        max_ppo2 = cfg.deco_ppo2_bar if hypoxic else cfg.max_ppo2_bar
        min_ppo2 = cfg.min_ppo2_bar
        max_end_mbar = Pressure.from_depth_m(cfg.max_end_m).mbar
        max_ppn2_bar = cfg.max_ppn2_bar

        # Best fo2: highest fraction that keeps ppO2 <= max_ppo2
        best_fo2 = min(1.0, max_ppo2 / pressure.bar)

        if not hypoxic:
            min_fo2 = min_ppo2 / pressure.bar
            if min_fo2 > 1.0:
                raise ValueError(
                    f"Cannot satisfy min ppO2 {min_ppo2} bar at {pressure.depth_m:.1f} m with any nitrox mix"
                )
            best_fo2 = max(best_fo2, min_fo2)

        if not trimix:
            # Pure nitrox — check END (narcotic fraction = 1 since fhe = 0)
            fn2 = 1.0 - best_fo2
            ppn2 = pressure.bar * fn2
            if ppn2 > max_ppn2_bar or pressure.mbar > max_end_mbar:
                raise ValueError(
                    f"Cannot satisfy END/ppN2 constraints at {pressure.depth_m:.1f} m without helium — use trimix=True"
                )
            return Gas(best_fo2, fhe=0.0)

        # Trimix: find minimum helium to satisfy END and ppN2 limits.
        # narcotic_fraction = fo2 + fn2 = 1 - fhe
        # END constraint:  pressure_mbar * (1 - fhe) <= max_end_mbar
        # ppN2 constraint: pressure_bar * (1 - fo2 - fhe) <= max_ppn2_bar
        end_limit_fhe = max(0.0, 1.0 - max_end_mbar / pressure.mbar)
        ppn2_limit_fhe = max(0.0, 1.0 - best_fo2 - max_ppn2_bar / pressure.bar)
        min_fhe = max(end_limit_fhe, ppn2_limit_fhe)

        fn2 = 1.0 - best_fo2 - min_fhe
        if fn2 < -1e-9:
            raise ValueError(
                f"Cannot satisfy constraints at {pressure.depth_m:.1f} m: fo2={best_fo2:.3f} + fhe={min_fhe:.3f} > 1.0"
            )

        return Gas(best_fo2, fhe=max(0.0, min_fhe))

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gas):
            return NotImplemented
        return abs(self._fo2 - other._fo2) < 1e-9 and abs(self._fhe - other._fhe) < 1e-9

    def __hash__(self) -> int:
        return hash((round(self._fo2, 9), round(self._fhe, 9)))

    def __repr__(self) -> str:
        return f"Gas(fo2={self._fo2:.2f}, fhe={self._fhe:.2f}, fn2={self._fn2:.2f})"

    def __str__(self) -> str:
        o2_pct = round(self._fo2 * 100)
        he_pct = round(self._fhe * 100)
        if he_pct == 0:
            if o2_pct == 21:
                return "Air"
            if o2_pct == 100:
                return "O2"
            return f"EAN{o2_pct}"
        return f"TX{o2_pct}/{he_pct}"
