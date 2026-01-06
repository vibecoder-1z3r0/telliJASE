"""tellijase package: PySide6 tools for composing AY-3-8914 music."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("tellijase")
except PackageNotFoundError:  # pragma: no cover - during local dev without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
