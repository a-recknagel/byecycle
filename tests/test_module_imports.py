import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    ["byecycle", "byecycle.cli", "byecycle.draw", "byecycle.graph", "byecycle.misc"],
)
def test_import(module):
    importlib.import_module(module)
