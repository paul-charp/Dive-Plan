"""Entry-point plugin discovery for decompression models and formatters.

Third-party packages register plugin classes in their ``pyproject.toml``
under the ``diveplan.deco_models`` group (subclasses of
:class:`~diveplan.models.base.BaseDecoModel`) or the ``diveplan.formatters``
group (subclasses of :class:`~diveplan.dive.formatters.BaseFormatter`)::

    [project.entry-points."diveplan.deco_models"]
    mymodel = "my_package.model:MyModel"

    [project.entry-points."diveplan.formatters"]
    myformat = "my_package.output:MyFormatter"

The module-level :data:`registry` singleton discovers every entry point in
a group **eagerly on first access** — never register an entry point whose
module does not exist yet, as one dangling reference breaks all lookups in
its group. :meth:`PluginRegistry.register_model` and
:meth:`PluginRegistry.register_formatter` are the manual escape hatches for
tests and notebooks.
"""

from functools import cached_property
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dive.formatters import BaseFormatter
    from .models.base import BaseDecoModel

_ENTRY_POINT_GROUP = "diveplan.deco_models"
_FORMATTER_ENTRY_POINT_GROUP = "diveplan.formatters"


class PluginNotFoundError(KeyError):
    """No plugin is registered under the requested name.

    Attributes:
        name: The name that was looked up.
        available: Names of all currently registered plugins of that kind.
    """

    def __init__(
        self, name: str, available: list[str], kind: str = "decompression model"
    ) -> None:
        hint = (
            f"No {kind} plugin named '{name}'.\n"
            f"Installed: {available or ['(none)']}\n"
            f"To add one try: pip install diveplan-{name}"
        )
        super().__init__(hint)
        self.name = name
        self.available = available


class PluginInvalidError(TypeError):
    """A discovered or registered plugin does not subclass its plugin base."""


def _discover[T](group: str, base: type[T]) -> dict[str, type[T]]:
    """Load every entry point in `group`, validating against `base`."""
    found: dict[str, type[T]] = {}
    for ep in entry_points(group=group):
        cls = ep.load()
        if not (isinstance(cls, type) and issubclass(cls, base)):
            raise PluginInvalidError(
                f"Entry point '{ep.name}' = {cls!r} does not subclass {base.__name__}."
            )
        found[ep.name] = cls
    return found


class PluginRegistry:
    """Deco-model and formatter lookup: entry-point discovery plus manual
    registration.

    Discovery runs once per group and is cached; :meth:`invalidate` forces
    a re-scan. Manual registrations shadow discovered plugins of the same
    name.
    """

    def __init__(self) -> None:
        # Manual overrides live here — separate from the cached discovery.
        # Checked first so local overrides win over installed packages.
        self._overrides: dict[str, type[BaseDecoModel[Any]]] = {}
        self._formatter_overrides: dict[str, type[BaseFormatter]] = {}

    @cached_property
    def _discovered(self) -> dict[str, type[BaseDecoModel[Any]]]:
        """Discovered once from entry points, then frozen."""
        from .models.base import BaseDecoModel

        # Abstract base passed on purpose: it is the issubclass validator.
        return _discover(_ENTRY_POINT_GROUP, BaseDecoModel)  # type: ignore[type-abstract]

    @cached_property
    def _discovered_formatters(self) -> dict[str, type[BaseFormatter]]:
        """Discovered once from entry points, then frozen."""
        from .dive.formatters import BaseFormatter

        # Abstract base passed on purpose: it is the issubclass validator.
        return _discover(_FORMATTER_ENTRY_POINT_GROUP, BaseFormatter)  # type: ignore[type-abstract]

    @property
    def _all(self) -> dict[str, type[BaseDecoModel[Any]]]:
        """Overrides shadow discovered plugins of the same name."""
        return {**self._discovered, **self._overrides}

    @property
    def _all_formatters(self) -> dict[str, type[BaseFormatter]]:
        """Overrides shadow discovered plugins of the same name."""
        return {**self._discovered_formatters, **self._formatter_overrides}

    # ── Public API: deco models ──────────────────────────────────────────────

    def model(self, name: str) -> type[BaseDecoModel[Any]]:
        """Return the plugin class for *name*, or raise PluginNotFoundError."""
        plugins = self._all
        if name not in plugins:
            raise PluginNotFoundError(name, available=list(plugins))
        return plugins[name]

    def all_models(self) -> dict[str, type[BaseDecoModel[Any]]]:
        """All registered plugins, keyed by name."""
        return dict(self._all)

    def register_model(self, name: str, cls: type[BaseDecoModel[Any]]) -> None:
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

    # ── Public API: formatters ───────────────────────────────────────────────

    def formatter(self, name: str) -> type[BaseFormatter]:
        """Return the formatter class for *name*, or raise PluginNotFoundError."""
        plugins = self._all_formatters
        if name not in plugins:
            raise PluginNotFoundError(name, available=list(plugins), kind="formatter")
        return plugins[name]

    def all_formatters(self) -> dict[str, type[BaseFormatter]]:
        """All registered formatters, keyed by name."""
        return dict(self._all_formatters)

    def register_formatter(self, name: str, cls: type[BaseFormatter]) -> None:
        """
        Manually register a formatter class — escape hatch for tests,
        notebooks, or plugins that ship inside the core package.

        Overrides any discovered plugin with the same name.
        Does NOT invalidate the discovery cache.
        """
        from .dive.formatters import BaseFormatter

        if not (isinstance(cls, type) and issubclass(cls, BaseFormatter)):
            raise PluginInvalidError(f"{cls!r} does not subclass BaseFormatter.")
        self._formatter_overrides[name] = cls

    def invalidate(self) -> None:
        """
        Force re-discovery of both groups on next access.
        Useful in tests that install/uninstall packages at runtime.
        """
        self.__dict__.pop("_discovered", None)
        self.__dict__.pop("_discovered_formatters", None)


registry = PluginRegistry()
