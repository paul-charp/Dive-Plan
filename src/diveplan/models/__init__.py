"""Decompression models: plugin contract plus the built-in families.

Import the plugin bases from the package root (``from diveplan import
BaseDecoModel, DecoState``) and look built-in models up by name through
the registry (``registry.model("zhl16c")``). Import from the family
subpackages (``diveplan.models.buhlmann``, ``diveplan.models.vpm``) only
for family-specific API such as :class:`~diveplan.models.buhlmann.Gradient`.
"""
