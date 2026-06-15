from functools import cached_property
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.base import BaseDecoModel

_ENTRY_POINT_GROUP = "diveplan.deco_models"


class PluginNotFoundError(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        hint = (
            f"No decompression model plugin named '{name}'.\n"
            f"Installed: {available or ['(none)']}\n"
            f"To add one try: pip install diveplan-{name}"
        )
        super().__init__(hint)
        self.name = name
        self.available = available


class PluginInvalidError(TypeError):
    pass


class PluginRegistry:
    def __init__(self) -> None:
        # Manual overrides live here — separate from the cached discovery.
        # Checked first so local overrides win over installed packages.
        self._overrides: dict[str, type[BaseDecoModel]] = {}

    @cached_property
    def _discovered(self) -> dict[str, type[BaseDecoModel]]:
        """Discovered once from entry points, then frozen."""
        from .models.base import BaseDecoModel

        found: dict[str, type[BaseDecoModel]] = {}
        for ep in entry_points(group=_ENTRY_POINT_GROUP):
            cls = ep.load()
            if not (isinstance(cls, type) and issubclass(cls, BaseDecoModel)):
                raise PluginInvalidError(
                    f"Entry point '{ep.name}' = {cls!r} does not "
                    f"subclass BaseDecoModel."
                )
            found[ep.name] = cls
        return found

    @property
    def _all(self) -> dict[str, type[BaseDecoModel]]:
        """Overrides shadow discovered plugins of the same name."""
        return {**self._discovered, **self._overrides}

    # ── Public API ──────────────────────────────────────────────────────────

    def model(self, name: str) -> type[BaseDecoModel]:
        """Return the plugin class for *name*, or raise PluginNotFoundError."""
        plugins = self._all
        if name not in plugins:
            raise PluginNotFoundError(name, available=list(plugins))
        return plugins[name]

    def all_models(self) -> dict[str, type[BaseDecoModel]]:
        """All registered plugins, keyed by name."""
        return dict(self._all)

    def register_model(self, name: str, cls: type[BaseDecoModel]) -> None:
        """
        Manually register a plugin class — escape hatch for tests,
        notebooks, or plugins that ship inside the core package.

        Overrides any discovered plugin with the same name.
        Does NOT invalidate the discovery cache.
        """
        from .models.base import BaseDecoModel

        if not (isinstance(cls, type) and issubclass(cls, BaseDecoModel)):
            raise PluginInvalidError(f"{cls!r} does not subclass BaseDecoModel.")
        self._overrides[name] = cls

    def invalidate(self) -> None:
        """
        Force re-discovery on next access.
        Useful in tests that install/uninstall packages at runtime.
        """
        self.__dict__.pop("_discovered", None)


registry = PluginRegistry()
