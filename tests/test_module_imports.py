import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    ["byecycle"],
)
def test_import(module):
    importlib.import_module(module)
