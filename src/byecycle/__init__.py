"""
All names that can be imported from this module are considered public, stable, and
intended for general use.

The [byecycle.run][] function returns [a dictionary](../autodocs/misc.md#byecycle.misc.GraphDict) containing all the necessary
information, as well as a [`networkx.DiGraph`](https://networkx.org/documentation/stable/reference/classes/digraph.html#networkx.DiGraph)
with essentially the same information but a different interface, and the name of the
importable distribution, which is useful if you want to create artifacts with good names.

For analysis, the dictionary is probably all you need:

```py
from byecycle import run

imports, _, _ = run("byecycle")
print(imports["byecycle"]["byecycle.cli"]["cycle"])  # prints: 'complicated'
```
"""
from importlib import metadata

__version__ = metadata.version("byecycle")

from byecycle.cli import _run as run

__all__ = ["run", "__version__"]
