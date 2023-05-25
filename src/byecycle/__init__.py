from importlib import metadata

__version__ = metadata.version("byecycle")

from byecycle.cli import _run as run

__all__ = ["run", "__version__"]
