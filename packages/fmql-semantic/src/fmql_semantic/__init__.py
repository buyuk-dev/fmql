from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("fmql-semantic")

from fmql_semantic.backend import SemanticBackend  # noqa: E402

__all__ = ["SemanticBackend", "__version__"]
