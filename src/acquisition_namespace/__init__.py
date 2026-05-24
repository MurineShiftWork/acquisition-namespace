from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from acquisition_namespace.spec import NamespaceBuilder, NamespaceLevelSpec, NamespaceSpec

try:
    __version__ = version("acquisition_namespace")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"

__all__ = [
    "NamespaceBuilder",
    "NamespaceLevelSpec",
    "NamespaceSpec",
]
