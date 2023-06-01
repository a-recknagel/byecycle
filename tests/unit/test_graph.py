import pytest

from byecycle.graph import Module


def test_module_to_string():
    foo = Module("foo")
    Module("foo.bar")
    Module("foo.baz")
    foo.add("foo.bar", "vanilla")
    foo.add("foo.baz", "vanilla")

    assert str(foo) == "'foo' -> {'foo.baz': {'vanilla'}, 'foo.bar': {'vanilla'}}"

    Module.reset()


def test_module_add_external_import():
    foo = Module("foo")

    with pytest.raises(RuntimeError):
        foo.add("bar", "vanilla")


def test_module_add_bad_module_type():
    foo = Module("foo")

    with pytest.raises(RuntimeError):
        foo.add(5, "vanilla")
